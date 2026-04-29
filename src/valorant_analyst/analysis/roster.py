"""Roster-aware helpers.

A "roster" is the set of players that make up a Valorant Premier team. The
helpers here let the caller:

* parse roster entries (Riot IDs or raw PUUIDs) coming from ``.env``
* resolve those entries to PUUIDs using existing ``match_players`` rows
* discover likely teammates from a player's match history
* find matches where the roster played together
* filter a raw HenrikDev payload to roster-relevant matches before ingest
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

import pandas as pd

DISCOVER_COLUMNS: list[str] = [
    "name",
    "tag",
    "puuid",
    "games_together",
    "avg_kills_together",
]

ROSTER_MATCH_COLUMNS: list[str] = [
    "match_id",
    "team",
    "roster_present",
    "members",
]


@dataclass(frozen=True)
class RosterEntry:
    """One parsed entry from ``PREMIER_ROSTER``.

    Either ``puuid`` or ``(name, tag)`` is set; both can be set if the user
    provides a Riot ID and we manage to resolve it via ``match_players``.
    """

    raw: str
    name: str | None
    tag: str | None
    puuid: str | None

    @property
    def is_puuid_only(self) -> bool:
        return self.puuid is not None and self.name is None and self.tag is None


def members_from_premier_team(team_payload: dict[str, Any]) -> list[RosterEntry]:
    """Extract the official roster from a ``/v1/premier/{name}/{tag}`` response.

    HenrikDev returns ``data.member[]`` with ``puuid``/``name``/``tag`` for each
    enrolled team member. We turn that into :class:`RosterEntry` objects with
    *both* puuid and Riot ID populated, so downstream filters can match either
    way.
    """
    entries: list[RosterEntry] = []
    if not isinstance(team_payload, dict):
        return entries
    data = team_payload.get("data")
    if not isinstance(data, dict):
        return entries
    members = data.get("member") or data.get("members")
    if not isinstance(members, list):
        return entries

    seen: set[str] = set()
    for m in members:
        if not isinstance(m, dict):
            continue
        puuid = m.get("puuid")
        name = m.get("name")
        tag = m.get("tag")
        raw = (
            f"{name}#{tag}"
            if isinstance(name, str) and isinstance(tag, str) and name and tag
            else (puuid if isinstance(puuid, str) else None)
        )
        if not raw or raw in seen:
            continue
        seen.add(raw)
        entries.append(
            RosterEntry(
                raw=raw,
                name=name if isinstance(name, str) and name else None,
                tag=tag if isinstance(tag, str) and tag else None,
                puuid=puuid if isinstance(puuid, str) and puuid else None,
            )
        )
    return entries


def league_match_ids(history_payload: dict[str, Any]) -> list[str]:
    """Pull match ids out of a ``/v1/premier/.../history`` response, in order."""
    if not isinstance(history_payload, dict):
        return []
    data = history_payload.get("data")
    if not isinstance(data, dict):
        return []
    league = data.get("league_matches") or data.get("matches") or []
    if not isinstance(league, list):
        return []

    ids: list[str] = []
    seen: set[str] = set()
    for entry in league:
        if not isinstance(entry, dict):
            continue
        match_id = entry.get("id") or entry.get("match_id") or entry.get("matchid")
        if not isinstance(match_id, str) or not match_id or match_id in seen:
            continue
        seen.add(match_id)
        ids.append(match_id)
    return ids


def parse_roster_entries(entries: Iterable[str]) -> list[RosterEntry]:
    """Parse raw strings from ``.env`` into :class:`RosterEntry` objects.

    Heuristic:

    * ``Name#Tag`` (contains ``#``) → Riot ID
    * everything else → assume a raw PUUID

    Empty / whitespace-only entries are dropped.
    """
    parsed: list[RosterEntry] = []
    for raw in entries:
        if not isinstance(raw, str):
            continue
        text = raw.strip()
        if not text:
            continue
        if "#" in text:
            name, _, tag = text.partition("#")
            name = name.strip()
            tag = tag.strip()
            if not name or not tag:
                continue
            parsed.append(RosterEntry(raw=text, name=name, tag=tag, puuid=None))
        else:
            parsed.append(RosterEntry(raw=text, name=None, tag=None, puuid=text))
    return parsed


def _matches_riot_id(row: pd.Series, name: str, tag: str) -> bool:
    row_name = row.get("name")
    row_tag = row.get("tag")
    if not isinstance(row_name, str) or not isinstance(row_tag, str):
        return False
    return row_name.lower() == name.lower() and row_tag.lower() == tag.lower()


def resolve_roster_puuids(
    entries: Iterable[RosterEntry],
    match_players: pd.DataFrame,
) -> tuple[set[str], list[RosterEntry]]:
    """Resolve roster entries to PUUIDs using ``match_players``.

    Returns ``(resolved_puuids, unresolved_entries)``. Unresolved entries are
    Riot IDs that never appeared in ``match_players`` — typically because the
    user mistyped or that teammate's matches haven't been ingested yet.
    """
    resolved: set[str] = set()
    unresolved: list[RosterEntry] = []

    if match_players is None or match_players.empty:
        for entry in entries:
            if entry.puuid:
                resolved.add(entry.puuid)
            else:
                unresolved.append(entry)
        return resolved, unresolved

    for entry in entries:
        if entry.puuid:
            resolved.add(entry.puuid)
            continue
        if entry.name is None or entry.tag is None:
            unresolved.append(entry)
            continue
        match_rows = match_players[
            match_players.apply(
                lambda row, n=entry.name, t=entry.tag: _matches_riot_id(row, n, t),
                axis=1,
            )
        ]
        puuids = [p for p in match_rows.get("puuid", pd.Series(dtype=object)) if p]
        if not puuids:
            unresolved.append(entry)
            continue
        # If the same name#tag corresponds to multiple puuids (should be rare),
        # keep them all so we don't accidentally drop matches.
        for p in set(puuids):
            resolved.add(str(p))

    return resolved, unresolved


def find_user_puuid(
    match_players: pd.DataFrame,
    name: str,
    tag: str,
) -> str | None:
    """Return the user's PUUID (most common one) from ``match_players``."""
    if match_players is None or match_players.empty:
        return None
    mask = match_players.apply(
        lambda row, n=name, t=tag: _matches_riot_id(row, n, t),
        axis=1,
    )
    rows = match_players[mask]
    if rows.empty:
        return None
    counts = rows["puuid"].value_counts(dropna=True)
    if counts.empty:
        return None
    return str(counts.index[0])


def discover_teammates(
    match_players: pd.DataFrame,
    user_puuid: str,
    *,
    top_n: int | None = 20,
) -> pd.DataFrame:
    """Return players who most often appear on the user's team.

    Useful for filling in ``PREMIER_ROSTER`` after running ``backfill``.
    """
    if match_players is None or match_players.empty or not user_puuid:
        return pd.DataFrame(columns=DISCOVER_COLUMNS)

    df = match_players.copy()
    user_rows = df[df["puuid"] == user_puuid][["match_id", "team"]]
    if user_rows.empty:
        return pd.DataFrame(columns=DISCOVER_COLUMNS)

    same_team = df.merge(user_rows, on=["match_id", "team"], how="inner")
    same_team = same_team[same_team["puuid"] != user_puuid]
    if same_team.empty:
        return pd.DataFrame(columns=DISCOVER_COLUMNS)

    same_team["kills"] = pd.to_numeric(same_team["kills"], errors="coerce")
    grouped = (
        same_team.groupby(["name", "tag", "puuid"], dropna=False)
        .agg(
            games_together=("match_id", "nunique"),
            avg_kills_together=("kills", "mean"),
        )
        .reset_index()
    )
    grouped["avg_kills_together"] = grouped["avg_kills_together"].astype(float).round(2)
    grouped = grouped.sort_values(
        ["games_together", "avg_kills_together"],
        ascending=[False, False],
        kind="stable",
    ).reset_index(drop=True)
    if top_n is not None:
        grouped = grouped.head(top_n)
    return grouped[DISCOVER_COLUMNS]


def matches_with_roster(
    match_players: pd.DataFrame,
    roster_puuids: set[str],
    min_present: int,
) -> pd.DataFrame:
    """Find ``(match_id, team)`` pairs where the roster played together.

    Only one of red/blue per match should match for genuine team play, but we
    return all qualifying ``(match_id, team)`` tuples so the caller can decide.
    """
    if (
        match_players is None
        or match_players.empty
        or not roster_puuids
        or min_present <= 0
    ):
        return pd.DataFrame(columns=ROSTER_MATCH_COLUMNS)

    df = match_players[match_players["puuid"].isin(roster_puuids)].copy()
    if df.empty:
        return pd.DataFrame(columns=ROSTER_MATCH_COLUMNS)

    grouped = (
        df.groupby(["match_id", "team"], dropna=False)
        .agg(
            roster_present=("puuid", "nunique"),
            members=("name", lambda s: sorted({str(x) for x in s if pd.notna(x)})),
        )
        .reset_index()
    )
    grouped = grouped[grouped["roster_present"] >= min_present]
    grouped = grouped.sort_values(
        "roster_present", ascending=False, kind="stable"
    ).reset_index(drop=True)
    return grouped[ROSTER_MATCH_COLUMNS]


def _player_riot_id(player: dict[str, Any]) -> tuple[str | None, str | None]:
    name = player.get("name")
    tag = player.get("tag")
    return (
        name.strip().lower() if isinstance(name, str) else None,
        tag.strip().lower() if isinstance(tag, str) else None,
    )


def _match_has_roster(
    match: dict[str, Any],
    entries: list[RosterEntry],
    min_present: int,
) -> bool:
    """Return True if any team in *match* has ``>= min_present`` roster members.

    Operates on raw HenrikDev payload shape: ``match["players"]["all_players"]``
    or the legacy ``match["players"]`` list. Each player has ``name``, ``tag``,
    ``puuid``, ``team``.
    """
    if min_present <= 0 or not entries:
        return False

    players_field = match.get("players") if isinstance(match, dict) else None
    if isinstance(players_field, dict):
        all_players = players_field.get("all_players")
    elif isinstance(players_field, list):
        all_players = players_field
    else:
        all_players = None
    if not isinstance(all_players, list):
        return False

    puuid_set: set[str] = set()
    riot_id_set: set[tuple[str, str]] = set()
    for entry in entries:
        if entry.puuid:
            puuid_set.add(entry.puuid)
        if entry.name and entry.tag:
            riot_id_set.add((entry.name.lower(), entry.tag.lower()))

    by_team: dict[str, set[str]] = {}
    for player in all_players:
        if not isinstance(player, dict):
            continue
        team = player.get("team")
        team_key = team if isinstance(team, str) else "unknown"
        puuid = player.get("puuid")
        riot_id = _player_riot_id(player)

        matched_id: str | None = None
        if isinstance(puuid, str) and puuid in puuid_set:
            matched_id = puuid
        elif (
            riot_id[0] is not None
            and riot_id[1] is not None
            and (riot_id[0], riot_id[1]) in riot_id_set
        ):
            matched_id = f"{riot_id[0]}#{riot_id[1]}"

        if matched_id:
            by_team.setdefault(team_key, set()).add(matched_id)

    return any(len(members) >= min_present for members in by_team.values())


def filter_payload_by_roster(
    payload: dict[str, Any],
    entries: list[RosterEntry],
    min_present: int,
) -> dict[str, Any]:
    """Return a payload containing only matches where the roster played together."""
    if not isinstance(payload, dict):
        return {"status": 200, "data": []}

    data = payload.get("data")
    if isinstance(data, dict):
        data = [data]
    if not isinstance(data, list):
        return {"status": payload.get("status", 200), "data": []}

    kept = [
        match
        for match in data
        if isinstance(match, dict)
        and _match_has_roster(match, entries, min_present)
    ]
    return {"status": payload.get("status", 200), "data": kept}
