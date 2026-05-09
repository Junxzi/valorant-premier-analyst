"""Command line entry point: ``python -m valorant_analyst.cli <command>``.

Commands focus on building an incremental Valorant **Premier** match dataset:

* ``fetch``    — call HenrikDev API, save the bundled JSON, archive each match.
* ``ingest``   — load raw matches and upsert ``matches`` / ``match_players``
  into DuckDB (only new ``match_id`` rows are inserted).
* ``backfill`` — walk the player's full history via stored-matches and pull
  every Premier match in detail (skipping already-archived ones).
* ``status``   — print row counts and the most recent match in DuckDB.
* ``run``      — fetch + ingest.
* ``report``   — optional Markdown summary built from the current DuckDB state.
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import duckdb
import pandas as pd

from .analysis.metrics import map_summary, player_summary
from .analysis.roster import (
    RosterEntry,
    discover_teammates,
    filter_payload_by_roster,
    find_user_puuid,
    league_match_ids,
    matches_with_roster,
    members_from_premier_team,
    parse_roster_entries,
    resolve_roster_puuids,
)
from .api.henrik_client import HenrikAPIError, HenrikClient
from .config import (
    DB_DIR,
    DEFAULT_ARCHIVE_DIR,
    DEFAULT_DB_PATH,
    DEFAULT_RAW_MATCHES_PATH,
    DEFAULT_REPORT_PATH,
    DEFAULT_ROSTER_HISTORY_PATH,
    AppConfig,
    ConfigError,
    load_config,
)
from .processing.normalize import (
    extract_match_ids_from_stored,
    filter_premier,
    normalize_match_players,
    normalize_match_teams,
    normalize_matches,
    normalize_round_economy,
    normalize_rounds,
    stored_pagination,
)
from .reporting.markdown_report import build_markdown_report, save_markdown_report
from .storage.duckdb_store import (
    UpsertResult,
    drop_table_if_exists,
    table_row_count,
    upsert_dataframe,
)
from .storage.raw_store import (
    archive_matches,
    archived_match_ids,
    load_archive_as_payload,
    load_raw_json,
    save_match_archive,
    save_raw_json,
)
from .storage.roster_history import (
    all_members as roster_history_all_members,
)
from .storage.roster_history import (
    load_roster_history,
    merge_team_members,
    save_roster_history,
)

logger = logging.getLogger("valorant_analyst")

MATCHES_TABLE = "matches"
PLAYERS_TABLE = "match_players"
TEAMS_TABLE = "match_teams"
ROUNDS_TABLE = "rounds"
ROUND_ECONOMY_TABLE = "round_economy"
MATCHES_KEY = ("match_id",)
PLAYERS_KEY = ("match_id", "puuid")
TEAMS_KEY = ("match_id", "team")
ROUNDS_KEY = ("match_id", "round_num")
ROUND_ECONOMY_KEY = ("match_id", "round_num", "team")


def _configure_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )


def _stamp_ingested_at(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        if df is None:
            return pd.DataFrame(columns=["ingested_at"])
        df = df.copy()
        df["ingested_at"] = pd.Series(dtype="datetime64[ns, UTC]")
        return df
    df = df.copy()
    df["ingested_at"] = datetime.now(UTC)
    return df


def cmd_fetch(
    config: AppConfig,
    raw_path: Path,
    archive_dir: Path,
) -> None:
    api_key = config.require_api_key()
    name, tag = config.require_player()

    logger.info(
        "Fetching last %d matches for %s#%s in region %s ...",
        config.match_size,
        name,
        tag,
        config.region,
    )
    client = HenrikClient(api_key=api_key)
    payload = client.get_matches_by_player(
        region=config.region,
        name=name,
        tag=tag,
        size=config.match_size,
    )
    save_raw_json(payload, raw_path)
    logger.info("Saved bundled raw payload to %s", raw_path)

    written = archive_matches(payload, archive_dir)
    logger.info(
        "Archived %d match file(s) under %s",
        len(written),
        archive_dir,
    )


def cmd_ingest(
    raw_path: Path,
    archive_dir: Path,
    db_path: Path,
    *,
    use_archive: bool,
    premier_only: bool,
    roster_only: bool = False,
    roster_entries: list[RosterEntry] | None = None,
    roster_min_present: int = 4,
    rebuild_players: bool = False,
) -> tuple[UpsertResult, UpsertResult]:
    if use_archive:
        logger.info("Loading matches from archive directory %s", archive_dir)
        payload = load_archive_as_payload(archive_dir)
    else:
        logger.info("Loading bundled raw payload from %s", raw_path)
        payload = load_raw_json(raw_path)

    if premier_only:
        before = len(payload.get("data") or [])
        payload = filter_premier(payload)
        after = len(payload.get("data") or [])
        logger.info("Premier filter: kept %d / %d matches", after, before)

    if roster_only:
        if not roster_entries:
            raise ConfigError(
                "--roster-only requires a non-empty roster. Set PREMIER_ROSTER "
                "in .env, populate data/roster_history.json via `roster-sync`, "
                "or configure PREMIER_TEAM_NAME/TAG + HENRIK_API_KEY for "
                "auto-discovery."
            )
        before = len(payload.get("data") or [])
        payload = filter_payload_by_roster(payload, roster_entries, roster_min_present)
        after = len(payload.get("data") or [])
        logger.info(
            "Roster filter (>= %d members on same team): kept %d / %d matches",
            roster_min_present,
            after,
            before,
        )

    matches_df = _stamp_ingested_at(normalize_matches(payload))
    players_df = _stamp_ingested_at(normalize_match_players(payload))
    teams_df = _stamp_ingested_at(normalize_match_teams(payload))
    rounds_df = _stamp_ingested_at(normalize_rounds(payload))
    round_economy_df = _stamp_ingested_at(normalize_round_economy(payload))

    if rebuild_players:
        logger.info("--rebuild-players: dropping match_players table for full rebuild.")
        drop_table_if_exists(db_path, PLAYERS_TABLE)

    matches_result = upsert_dataframe(
        matches_df, db_path, MATCHES_TABLE, list(MATCHES_KEY)
    )
    players_result = upsert_dataframe(
        players_df, db_path, PLAYERS_TABLE, list(PLAYERS_KEY)
    )
    teams_result = upsert_dataframe(
        teams_df, db_path, TEAMS_TABLE, list(TEAMS_KEY)
    )
    rounds_result = upsert_dataframe(
        rounds_df, db_path, ROUNDS_TABLE, list(ROUNDS_KEY)
    )
    round_economy_result = upsert_dataframe(
        round_economy_df, db_path, ROUND_ECONOMY_TABLE, list(ROUND_ECONOMY_KEY)
    )

    for r in (matches_result, players_result, teams_result, rounds_result, round_economy_result):
        logger.info(
            "%-15s inserted=%d skipped=%d",
            r.table + ":",
            r.inserted,
            r.skipped,
        )
    logger.info("DuckDB now at %s", db_path)
    return matches_result, players_result


def cmd_backfill(
    config: AppConfig,
    archive_dir: Path,
    *,
    page_size: int,
    max_pages: int | None,
    sleep_seconds: float,
    premier_only: bool,
) -> None:
    """Walk stored-matches and pull each (Premier) match in detail."""
    api_key = config.require_api_key()
    name, tag = config.require_player()
    client = HenrikClient(api_key=api_key, max_retries=2)

    archive_dir.mkdir(parents=True, exist_ok=True)
    already = archived_match_ids(archive_dir)
    logger.info(
        "Backfill start: region=%s player=%s#%s premier_only=%s "
        "page_size=%d max_pages=%s sleep=%.1fs already_archived=%d",
        config.region,
        name,
        tag,
        premier_only,
        page_size,
        max_pages if max_pages is not None else "unlimited",
        sleep_seconds,
        len(already),
    )

    server_mode_filter = "premier" if premier_only else None
    discovered: list[str] = []
    page = 1
    while True:
        if max_pages is not None and page > max_pages:
            logger.info("Reached --max-pages=%d, stopping discovery.", max_pages)
            break

        logger.info("Listing stored matches: page=%d size=%d", page, page_size)
        try:
            stored = client.get_stored_matches(
                region=config.region,
                name=name,
                tag=tag,
                page=page,
                size=page_size,
                mode=server_mode_filter,
            )
        except HenrikAPIError as exc:
            if exc.status_code == 404:
                logger.info("No more matches at page=%d (404).", page)
                break
            raise

        ids_this_page = extract_match_ids_from_stored(
            stored, premier_only=premier_only
        )
        page_total = len(stored.get("data") or [])
        pagination = stored_pagination(stored)
        logger.info(
            "  page=%d entries=%d kept=%d total=%s",
            page,
            page_total,
            len(ids_this_page),
            pagination.get("total", "?"),
        )

        new_for_page = [mid for mid in ids_this_page if mid not in already]
        discovered.extend(new_for_page)

        if page_total == 0:
            break
        if max_pages is None and page_total < page_size:
            break

        page += 1
        time.sleep(sleep_seconds)

    logger.info(
        "Discovery done: %d new match id(s) to download (already had %d).",
        len(discovered),
        len(already),
    )

    fetched = 0
    failures = 0
    for idx, match_id in enumerate(discovered, start=1):
        logger.info("[%d/%d] fetching match %s", idx, len(discovered), match_id)
        try:
            detail = client.get_match_by_id(match_id)
        except HenrikAPIError as exc:
            failures += 1
            logger.warning("  skipped: %s", exc)
            time.sleep(sleep_seconds)
            continue

        match_obj = detail.get("data") if isinstance(detail, dict) else None
        if not isinstance(match_obj, dict):
            failures += 1
            logger.warning("  skipped: unexpected response shape for %s", match_id)
            time.sleep(sleep_seconds)
            continue

        path = save_match_archive(match_obj, archive_dir)
        if path is None:
            failures += 1
            logger.warning("  skipped: could not extract match_id from response")
        else:
            fetched += 1
            logger.debug("  saved %s", path)
        time.sleep(sleep_seconds)

    logger.info(
        "Backfill summary: archived=%d failed=%d (archive=%s)",
        fetched,
        failures,
        archive_dir,
    )


def cmd_team_info(config: AppConfig) -> None:
    """Fetch and pretty-print Premier team details."""
    api_key = config.require_api_key()
    team_name, team_tag = config.require_premier_team()
    client = HenrikClient(api_key=api_key)

    payload = client.get_premier_team(team_name, team_tag)
    data = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(data, dict):
        logger.error("Unexpected Premier team payload (no .data object).")
        return

    stats = data.get("stats") or {}
    placement = data.get("placement") or {}
    logger.info(
        "Team: %s#%s  id=%s  enrolled=%s",
        data.get("name"),
        data.get("tag"),
        data.get("id"),
        data.get("enrolled"),
    )
    logger.info(
        "  record: %s W / %s L  (matches=%s)",
        stats.get("wins"),
        stats.get("losses"),
        stats.get("matches"),
    )
    logger.info(
        "  placement: conference=%s division=%s place=%s points=%s",
        placement.get("conference"),
        placement.get("division"),
        placement.get("place"),
        placement.get("points"),
    )

    members = members_from_premier_team(payload)
    if not members:
        logger.warning(
            "Members are not yet populated by HenrikDev for this team "
            "(stats are returned but `data.member` is empty). This is common "
            "right after enrollment or when the basic API key has limited "
            "access. team-backfill does NOT need member info — proceed with:"
        )
        logger.warning(
            "  team-backfill  →  ingest --from-archive  →  roster-discover"
        )
        logger.warning(
            "  Then copy the discovered Riot IDs into PREMIER_ROSTER in .env."
        )
        return
    logger.info("Members (%d):", len(members))
    for entry in members:
        logger.info(
            "  - %-30s puuid=%s",
            f"{entry.name}#{entry.tag}" if entry.name and entry.tag else entry.raw,
            entry.puuid or "-",
        )


def cmd_team_backfill(
    config: AppConfig,
    archive_dir: Path,
    db_path: Path,
    history_path: Path,
    *,
    sleep_seconds: float,
    max_matches: int | None,
    sync_roster: bool = True,
) -> None:
    """Pull every official Premier league match's full detail into the archive.

    When ``sync_roster`` is true, also refreshes ``data/roster_history.json``
    at the end so any new members are captured automatically. The sync runs
    with ``scan_db=True`` so departed members already in DuckDB are picked
    up too. Sync failures are logged but do not fail the backfill itself.
    """
    api_key = config.require_api_key()
    team_name, team_tag = config.require_premier_team()
    client = HenrikClient(api_key=api_key, max_retries=2)

    archive_dir.mkdir(parents=True, exist_ok=True)
    already = archived_match_ids(archive_dir)

    logger.info(
        "Team backfill start: team=%s#%s sleep=%.1fs already_archived=%d",
        team_name,
        team_tag,
        sleep_seconds,
        len(already),
    )

    history = client.get_premier_team_history(team_name, team_tag)
    ids = league_match_ids(history)
    logger.info("Premier history: %d league_matches", len(ids))

    new_ids = [mid for mid in ids if mid not in already]
    skipped_already = len(ids) - len(new_ids)
    pending = new_ids
    truncated = 0
    if max_matches is not None and len(pending) > max_matches:
        truncated = len(pending) - max_matches
        pending = pending[:max_matches]
    logger.info(
        "Will fetch %d new match(es)  (already-archived=%d, "
        "deferred-by-max-matches=%d).",
        len(pending),
        skipped_already,
        truncated,
    )

    fetched = 0
    failures = 0
    for idx, match_id in enumerate(pending, start=1):
        logger.info("[%d/%d] fetching match %s", idx, len(pending), match_id)
        try:
            detail = client.get_match_by_id(match_id)
        except HenrikAPIError as exc:
            failures += 1
            logger.warning("  skipped: %s", exc)
            time.sleep(sleep_seconds)
            continue

        match_obj = detail.get("data") if isinstance(detail, dict) else None
        if not isinstance(match_obj, dict):
            failures += 1
            logger.warning("  skipped: unexpected response shape for %s", match_id)
            time.sleep(sleep_seconds)
            continue

        path = save_match_archive(match_obj, archive_dir)
        if path is None:
            failures += 1
            logger.warning("  skipped: could not extract match_id from response")
        else:
            fetched += 1
            logger.debug("  saved %s", path)
        time.sleep(sleep_seconds)

    logger.info(
        "Team backfill summary: archived=%d failed=%d (archive=%s)",
        fetched,
        failures,
        archive_dir,
    )

    if sync_roster:
        try:
            cmd_roster_sync(config, db_path, history_path, scan_db=True)
        except Exception as exc:  # noqa: BLE001 - sync is best-effort
            logger.warning(
                "roster-sync after team-backfill failed (non-fatal): %s", exc
            )


def cmd_team_sync(
    config: AppConfig,
    archive_dir: Path,
    db_path: Path,
    history_path: Path,
    *,
    sleep_seconds: float,
    max_matches: int | None,
    rebuild_players: bool = False,
) -> None:
    """End-to-end Premier sync: ``team-backfill`` then ``ingest --from-archive``.

    Composed shortcut used both by the CLI and the FastAPI scheduler so a
    single command keeps DuckDB up to date with the team's official matches.
    Roster history is refreshed automatically as part of ``team-backfill``.
    """
    logger.info("team-sync: step 1/2 — team-backfill")
    cmd_team_backfill(
        config,
        archive_dir,
        db_path,
        history_path,
        sleep_seconds=sleep_seconds,
        max_matches=max_matches,
    )

    logger.info("team-sync: step 2/2 — ingest --from-archive")
    cmd_ingest(
        DEFAULT_RAW_MATCHES_PATH,
        archive_dir,
        db_path,
        use_archive=True,
        premier_only=True,
        rebuild_players=rebuild_players,
    )

    logger.info("team-sync: done")


def _read_match_players(db_path: Path) -> pd.DataFrame:
    if not db_path.exists():
        raise FileNotFoundError(
            f"DuckDB not found at {db_path}. Run `fetch` and `ingest` (or "
            "`backfill` then `ingest --from-archive`) first."
        )
    con = duckdb.connect(str(db_path), read_only=True)
    try:
        return con.execute(f'SELECT * FROM "{PLAYERS_TABLE}"').fetchdf()
    finally:
        con.close()


def _print_dataframe(df: pd.DataFrame) -> None:
    if df is None or df.empty:
        logger.info("(no rows)")
        return
    text = df.to_string(index=False)
    for line in text.splitlines():
        logger.info("%s", line)


def cmd_roster_discover(config: AppConfig, db_path: Path, top_n: int) -> None:
    name, tag = config.require_player()
    players_df = _read_match_players(db_path)

    user_puuid = find_user_puuid(players_df, name, tag)
    if user_puuid is None:
        logger.error(
            "Could not find %s#%s in match_players. "
            "Did you ingest matches that include this player?",
            name,
            tag,
        )
        return
    logger.info("User %s#%s -> puuid=%s", name, tag, user_puuid)

    discovered = discover_teammates(players_df, user_puuid, top_n=top_n)
    if discovered.empty:
        logger.info("No teammates found.")
        return

    logger.info("Top teammates (most games on the same team):")
    _print_dataframe(discovered)
    logger.info(
        "Tip: copy the Riot IDs into PREMIER_ROSTER in .env, "
        "e.g. PREMIER_ROSTER=%s#%s,Teammate1#JP1,Teammate2#JP1",
        name,
        tag,
    )


def _roster_from_history(
    config: AppConfig,
    history_path: Path,
    *,
    only_current: bool,
) -> list[RosterEntry]:
    """Return roster entries from ``data/roster_history.json`` (if any)."""
    if not (config.premier_team_name and config.premier_team_tag):
        return []
    from .storage.roster_history import member_records as _member_records

    history = load_roster_history(history_path)
    records = _member_records(
        history, config.premier_team_name, config.premier_team_tag
    )
    if only_current:
        records = [r for r in records if r.is_current]
    return [r.to_roster_entry() for r in records]


def _resolve_roster_entries_or_team(
    config: AppConfig,
    history_path: Path = DEFAULT_ROSTER_HISTORY_PATH,
    *,
    source: str = "auto",
) -> list[RosterEntry]:
    """Pick roster entries to use for filters / analysis.

    *source* controls precedence:

    * ``"auto"``    — ``PREMIER_ROSTER`` (env) > history union > current API
    * ``"env"``     — strictly ``PREMIER_ROSTER``; raises if empty
    * ``"history"`` — full union (current + departed) from
      ``data/roster_history.json``; raises if file is empty for this team
    * ``"current"`` — only members marked ``is_current=True`` in the history
      file, falling back to the live API if the file is empty
    """
    if source == "env":
        if not config.roster_entries:
            raise ConfigError(
                "--roster-source=env requires PREMIER_ROSTER to be set in .env."
            )
        return parse_roster_entries(config.roster_entries)

    if source == "auto" and config.roster_entries:
        return parse_roster_entries(config.roster_entries)

    if source in ("auto", "history"):
        union = _roster_from_history(config, history_path, only_current=False)
        if union:
            logger.info(
                "Using roster history union (%d members) from %s",
                len(union),
                history_path,
            )
            return union
        if source == "history":
            raise ConfigError(
                f"--roster-source=history but {history_path} has no entries "
                f"for {config.premier_team_name}#{config.premier_team_tag}. "
                "Run `roster-sync --scan-db` first."
            )

    if source == "current":
        active = _roster_from_history(config, history_path, only_current=True)
        if active:
            logger.info(
                "Using %d current member(s) from roster history at %s",
                len(active),
                history_path,
            )
            return active

    if config.premier_team_name and config.premier_team_tag and config.henrik_api_key:
        logger.info(
            "Falling back to live Premier team API for %s#%s ...",
            config.premier_team_name,
            config.premier_team_tag,
        )
        client = HenrikClient(api_key=config.henrik_api_key)
        payload = client.get_premier_team(
            config.premier_team_name, config.premier_team_tag
        )
        members = members_from_premier_team(payload)
        if members:
            return members

    raise ConfigError(
        "Roster is empty: set PREMIER_ROSTER in .env, run `roster-sync` to "
        "populate data/roster_history.json, or configure PREMIER_TEAM_NAME / "
        "PREMIER_TEAM_TAG so the team API can supply it."
    )


def cmd_roster_matches(
    config: AppConfig,
    db_path: Path,
    history_path: Path = DEFAULT_ROSTER_HISTORY_PATH,
    *,
    source: str = "auto",
) -> None:
    parsed = _resolve_roster_entries_or_team(config, history_path, source=source)
    players_df = _read_match_players(db_path)
    resolved, unresolved = resolve_roster_puuids(parsed, players_df)
    logger.info(
        "Roster: %d entries -> %d resolved puuids (min_present=%d)",
        len(parsed),
        len(resolved),
        config.roster_min_present,
    )
    for entry in unresolved:
        logger.warning(
            "  unresolved entry: %s (no matching name#tag in match_players yet)",
            entry.raw,
        )

    matches = matches_with_roster(players_df, resolved, config.roster_min_present)
    if matches.empty:
        logger.info("No matches found with the roster on the same team.")
        return

    logger.info("Matches where >= %d roster members shared a team:", config.roster_min_present)
    _print_dataframe(matches)


def _scan_team_members_from_db(
    db_path: Path, team_name: str, team_tag: str
) -> list[RosterEntry]:
    """Pull every puuid that ever played on this team's side, from DuckDB.

    Used as a complement to the API roster: the API only returns *current*
    members, so a fresh DB scan is the simplest way to recover departed
    members and seed the history file the first time it's built.
    """
    if not db_path.exists():
        return []
    con = duckdb.connect(str(db_path), read_only=True)
    try:
        rows = con.execute(
            f'''
            WITH ours AS (
                SELECT match_id, team
                FROM "{TEAMS_TABLE}"
                WHERE premier_team_name = ? AND premier_team_tag = ?
            )
            SELECT mp.puuid,
                   ANY_VALUE(mp.name) AS name,
                   ANY_VALUE(mp.tag)  AS tag
            FROM "{PLAYERS_TABLE}" mp
            JOIN ours o
              ON mp.match_id = o.match_id AND mp.team = o.team
            WHERE mp.puuid IS NOT NULL AND mp.puuid <> ''
            GROUP BY mp.puuid
            ''',
            [team_name, team_tag],
        ).fetchall()
    except duckdb.CatalogException:
        return []
    finally:
        con.close()

    entries: list[RosterEntry] = []
    for r in rows:
        puuid = str(r[0]) if r[0] is not None else None
        name = str(r[1]) if r[1] is not None else None
        tag = str(r[2]) if r[2] is not None else None
        if not puuid:
            continue
        raw = f"{name}#{tag}" if name and tag else puuid
        entries.append(RosterEntry(raw=raw, name=name, tag=tag, puuid=puuid))
    return entries


def cmd_roster_sync(
    config: AppConfig,
    db_path: Path,
    history_path: Path,
    *,
    scan_db: bool,
) -> None:
    """Refresh ``data/roster_history.json`` from the API (and optionally DuckDB).

    The API is the source of truth for ``is_current``; the optional DB scan
    only adds previously-seen members that the API forgot about (common when
    a player has left the team).
    """
    api_key = config.require_api_key()
    team_name, team_tag = config.require_premier_team()

    history = load_roster_history(history_path)

    client = HenrikClient(api_key=api_key)
    api_entries: list[RosterEntry] = []
    try:
        payload = client.get_premier_team(team_name, team_tag)
        api_entries = members_from_premier_team(payload)
    except HenrikAPIError as exc:
        logger.warning(
            "Premier team API call failed (%s) — proceeding with DB scan only "
            "if --scan-db was requested.",
            exc,
        )

    logger.info(
        "roster-sync: team=%s#%s api_members=%d scan_db=%s",
        team_name,
        team_tag,
        len(api_entries),
        scan_db,
    )

    api_report = merge_team_members(
        history,
        team_name,
        team_tag,
        api_entries,
        source="api",
        # Only let the API mark people inactive when it actually returned a
        # roster. An empty `data.member` is common right after enrollment and
        # we don't want to flip everyone to is_current=False in that case.
        mark_missing_inactive=bool(api_entries),
    )

    db_report = None
    if scan_db:
        db_entries = _scan_team_members_from_db(db_path, team_name, team_tag)
        logger.info("roster-sync: db_scan recovered %d puuid(s)", len(db_entries))
        # If the API gave us a real roster, treat new DB-scan entries as
        # *not current* — anyone the API didn't list shouldn't be promoted
        # to "active" just because they show up in old matches. But when the
        # API returned nothing (empty `data.member` is a common HenrikDev
        # quirk for newly-enrolled teams), the DB scan is our only signal
        # for who is on the roster, so default to is_current=True.
        db_default_current = not bool(api_entries)
        db_report = merge_team_members(
            history,
            team_name,
            team_tag,
            db_entries,
            source="match_players",
            mark_missing_inactive=False,
            default_is_current=db_default_current,
        )

    save_roster_history(history, history_path)

    def _log_report(label: str, report) -> None:
        if report is None:
            return
        for added in report.added:
            who = (
                f"{added.name}#{added.tag}" if added.name and added.tag else added.puuid
            )
            logger.info("  [%s] added: %s (puuid=%s)", label, who, added.puuid or "-")
        for rejoined in report.rejoined:
            who = (
                f"{rejoined.name}#{rejoined.tag}"
                if rejoined.name and rejoined.tag
                else rejoined.puuid
            )
            logger.info("  [%s] rejoined: %s", label, who)
        for departed in report.departed:
            who = (
                f"{departed.name}#{departed.tag}"
                if departed.name and departed.tag
                else departed.puuid
            )
            logger.info("  [%s] departed: %s (kept in history)", label, who)

    _log_report("api", api_report)
    _log_report("db", db_report)

    members = roster_history_all_members(history, team_name, team_tag)
    logger.info(
        "roster-sync done: %d total member(s) in history at %s",
        len(members),
        history_path,
    )


def cmd_status(db_path: Path) -> None:
    if not db_path.exists():
        logger.info("No DuckDB file at %s yet — run `fetch` then `ingest`.", db_path)
        return

    counts = {
        MATCHES_TABLE: table_row_count(db_path, MATCHES_TABLE),
        PLAYERS_TABLE: table_row_count(db_path, PLAYERS_TABLE),
        TEAMS_TABLE: table_row_count(db_path, TEAMS_TABLE),
        ROUNDS_TABLE: table_row_count(db_path, ROUNDS_TABLE),
    }
    logger.info("DuckDB: %s", db_path)
    for name, n in counts.items():
        logger.info("  %-18s %d rows", name, n)

    if counts[MATCHES_TABLE] == 0:
        return

    con = duckdb.connect(str(db_path), read_only=True)
    try:
        latest = con.execute(
            f'SELECT match_id, map_name, mode, queue, game_start '
            f'FROM "{MATCHES_TABLE}" '
            f"ORDER BY game_start DESC NULLS LAST LIMIT 1"
        ).fetchone()
        distinct_maps = con.execute(
            f'SELECT COUNT(DISTINCT map_name) FROM "{MATCHES_TABLE}"'
        ).fetchone()[0]
        # If we have team rosters, surface a quick W/L for the most-seen team
        record = None
        if counts[TEAMS_TABLE] > 0:
            record = con.execute(
                f'''
                WITH our AS (
                    SELECT premier_team_name, premier_team_tag, COUNT(*) AS n
                    FROM "{TEAMS_TABLE}"
                    WHERE premier_team_name IS NOT NULL
                    GROUP BY 1, 2
                    ORDER BY n DESC
                    LIMIT 1
                )
                SELECT our.premier_team_name, our.premier_team_tag,
                       SUM(CASE WHEN t.has_won THEN 1 ELSE 0 END) AS wins,
                       SUM(CASE WHEN t.has_won = FALSE THEN 1 ELSE 0 END) AS losses
                FROM our
                JOIN "{TEAMS_TABLE}" t
                  ON t.premier_team_name = our.premier_team_name
                 AND t.premier_team_tag  = our.premier_team_tag
                GROUP BY 1, 2
                '''
            ).fetchone()
    finally:
        con.close()

    if latest is not None:
        logger.info(
            "  latest match: id=%s map=%s mode=%s queue=%s game_start=%s",
            *latest,
        )
    logger.info("  distinct maps: %d", int(distinct_maps))
    if record is not None:
        logger.info(
            "  team record: %s#%s  %s W / %s L",
            record[0],
            record[1],
            record[2],
            record[3],
        )


def cmd_report(db_path: Path, report_path: Path) -> None:
    if not db_path.exists():
        raise FileNotFoundError(
            f"DuckDB not found at {db_path}. "
            "Run `fetch` and `ingest` first."
        )
    con = duckdb.connect(str(db_path), read_only=True)
    try:
        matches_df = con.execute(f'SELECT * FROM "{MATCHES_TABLE}"').fetchdf()
        players_df = con.execute(f'SELECT * FROM "{PLAYERS_TABLE}"').fetchdf()
    finally:
        con.close()

    report = build_markdown_report(
        player_summary(players_df),
        map_summary(matches_df, players_df),
    )
    save_markdown_report(report, report_path)
    logger.info("Wrote Markdown report to %s", report_path)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="valorant-analyst",
        description=(
            "Build an incremental Valorant Premier match dataset in DuckDB."
        ),
    )
    parser.add_argument(
        "command",
        choices=[
            "fetch",
            "ingest",
            "backfill",
            "status",
            "run",
            "report",
            "roster-discover",
            "roster-matches",
            "roster-sync",
            "team-info",
            "team-backfill",
            "team-sync",
        ],
        help=(
            "fetch / ingest / backfill / status / run / report; "
            "team-info, team-backfill (Premier team API: official roster + "
            "league_matches); team-sync (team-backfill + ingest --from-archive "
            "in one shot, used by the FastAPI auto-sync scheduler); "
            "roster-discover, roster-matches (analyze who played together); "
            "roster-sync (merge API + DB into data/roster_history.json so "
            "departed members stick around)."
        ),
    )
    parser.add_argument(
        "--raw-path",
        type=Path,
        default=DEFAULT_RAW_MATCHES_PATH,
        help=f"Bundled raw JSON path (default: {DEFAULT_RAW_MATCHES_PATH}).",
    )
    parser.add_argument(
        "--archive-dir",
        type=Path,
        default=DEFAULT_ARCHIVE_DIR,
        help=(
            "Per-match raw JSON archive directory "
            f"(default: {DEFAULT_ARCHIVE_DIR})."
        ),
    )
    parser.add_argument(
        "--db-path",
        type=Path,
        default=DEFAULT_DB_PATH,
        help=f"DuckDB database path (default: {DEFAULT_DB_PATH}).",
    )
    parser.add_argument(
        "--report-path",
        type=Path,
        default=DEFAULT_REPORT_PATH,
        help=f"Markdown report output path (default: {DEFAULT_REPORT_PATH}).",
    )
    parser.add_argument(
        "--from-archive",
        action="store_true",
        help=(
            "Ingest from the per-match archive directory instead of the "
            "latest bundled raw JSON. Useful for rebuilding DuckDB from scratch."
        ),
    )
    parser.add_argument(
        "--all-modes",
        action="store_true",
        help="Ingest every game mode. By default only Premier matches are kept.",
    )
    parser.add_argument(
        "--page-size",
        type=int,
        default=25,
        help="Backfill: stored-matches page size (default: 25).",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=None,
        help="Backfill: stop after this many pages (default: walk all pages).",
    )
    parser.add_argument(
        "--sleep-seconds",
        type=float,
        default=2.5,
        help=(
            "Backfill: seconds between API calls "
            "(default: 2.5, tuned for the 30 req/min basic key)."
        ),
    )
    parser.add_argument(
        "--rebuild-players",
        action="store_true",
        help=(
            "Drop and recreate the match_players table before ingesting. "
            "Use this after adding new columns (e.g. kast_rounds)."
        ),
    )
    parser.add_argument(
        "--roster-only",
        action="store_true",
        help=(
            "Ingest only matches where >= ROSTER_MIN_PRESENT roster members "
            "shared a team (requires PREMIER_ROSTER in .env)."
        ),
    )
    parser.add_argument(
        "--top-n",
        type=int,
        default=20,
        help="roster-discover: how many teammates to display (default: 20).",
    )
    parser.add_argument(
        "--max-matches",
        type=int,
        default=None,
        help="team-backfill: cap the number of matches downloaded.",
    )
    parser.add_argument(
        "--roster-history-path",
        type=Path,
        default=DEFAULT_ROSTER_HISTORY_PATH,
        help=(
            "roster-sync: path to the persisted roster history JSON "
            f"(default: {DEFAULT_ROSTER_HISTORY_PATH})."
        ),
    )
    parser.add_argument(
        "--scan-db",
        action="store_true",
        help=(
            "roster-sync: also scan match_players for puuids that played on "
            "this team's side, so departed members are rediscovered."
        ),
    )
    parser.add_argument(
        "--roster-source",
        choices=["auto", "history", "current", "env"],
        default="auto",
        help=(
            "ingest --roster-only / roster-matches: where to pull the roster "
            "from. 'auto' (default) = env > history union > API. "
            "'history' = union of all members ever seen on the team. "
            "'current' = only members still on the active roster from the "
            "API or roster_history.json. 'env' = strictly PREMIER_ROSTER."
        ),
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable debug logging.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    _configure_logging(args.verbose)

    DB_DIR.mkdir(parents=True, exist_ok=True)
    args.archive_dir.mkdir(parents=True, exist_ok=True)

    try:
        config = load_config()

        resolved_roster: list[RosterEntry] | None = None
        if args.roster_only:
            resolved_roster = _resolve_roster_entries_or_team(
                config,
                args.roster_history_path,
                source=args.roster_source,
            )

        ingest_kwargs = {
            "use_archive": args.from_archive,
            "premier_only": not args.all_modes,
            "roster_only": args.roster_only,
            "roster_entries": resolved_roster,
            "roster_min_present": config.roster_min_present,
            "rebuild_players": args.rebuild_players,
        }

        if args.command == "fetch":
            cmd_fetch(config, args.raw_path, args.archive_dir)
        elif args.command == "ingest":
            cmd_ingest(
                args.raw_path,
                args.archive_dir,
                args.db_path,
                **ingest_kwargs,
            )
        elif args.command == "backfill":
            cmd_backfill(
                config,
                args.archive_dir,
                page_size=args.page_size,
                max_pages=args.max_pages,
                sleep_seconds=args.sleep_seconds,
                premier_only=not args.all_modes,
            )
        elif args.command == "status":
            cmd_status(args.db_path)
        elif args.command == "run":
            cmd_fetch(config, args.raw_path, args.archive_dir)
            cmd_ingest(
                args.raw_path,
                args.archive_dir,
                args.db_path,
                **{**ingest_kwargs, "use_archive": False},
            )
            cmd_status(args.db_path)
        elif args.command == "report":
            cmd_report(args.db_path, args.report_path)
        elif args.command == "roster-discover":
            cmd_roster_discover(config, args.db_path, args.top_n)
        elif args.command == "roster-matches":
            cmd_roster_matches(
                config,
                args.db_path,
                args.roster_history_path,
                source=args.roster_source,
            )
        elif args.command == "roster-sync":
            cmd_roster_sync(
                config,
                args.db_path,
                args.roster_history_path,
                scan_db=args.scan_db,
            )
        elif args.command == "team-info":
            cmd_team_info(config)
        elif args.command == "team-backfill":
            cmd_team_backfill(
                config,
                args.archive_dir,
                args.db_path,
                args.roster_history_path,
                sleep_seconds=args.sleep_seconds,
                max_matches=args.max_matches,
            )
        elif args.command == "team-sync":
            cmd_team_sync(
                config,
                args.archive_dir,
                args.db_path,
                args.roster_history_path,
                sleep_seconds=args.sleep_seconds,
                max_matches=args.max_matches,
                rebuild_players=args.rebuild_players,
            )
        else:  # pragma: no cover - argparse already restricts choices
            parser.error(f"Unknown command: {args.command}")
    except ConfigError as exc:
        logger.error("Configuration error: %s", exc)
        return 2
    except HenrikAPIError as exc:
        logger.error("HenrikDev API error: %s", exc)
        return 3
    except FileNotFoundError as exc:
        logger.error("%s", exc)
        return 4
    except Exception as exc:  # noqa: BLE001
        logger.exception("Unexpected error: %s", exc)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
