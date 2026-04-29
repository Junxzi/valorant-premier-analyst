"""Normalize HenrikDev API responses into tidy DataFrames.

The functions here are intentionally defensive: HenrikDev's response shape can
change across versions, so we use ``.get`` everywhere and fall back to empty
DataFrames with the documented columns when fields are missing.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

MATCH_COLUMNS: list[str] = [
    "match_id",
    "map_name",
    "mode",
    "queue",
    "game_start",
    "game_length",
]

PLAYER_COLUMNS: list[str] = [
    "match_id",
    "puuid",
    "name",
    "tag",
    "team",
    "agent",
    "kills",
    "deaths",
    "assists",
    "score",
    "damage_made",
    "damage_received",
    "kast_rounds",
    "first_kills",
    "first_deaths",
]

TEAM_COLUMNS: list[str] = [
    "match_id",
    "team",
    "has_won",
    "rounds_won",
    "rounds_lost",
    "premier_team_id",
    "premier_team_name",
    "premier_team_tag",
]

ROUND_COLUMNS: list[str] = [
    "match_id",
    "round_num",
    "winning_team",
    "end_type",
    "bomb_planted",
    "bomb_defused",
]

ROUND_ECONOMY_COLUMNS: list[str] = [
    "match_id",
    "round_num",
    "team",
    "total_loadout",
    "avg_loadout",
    "total_spent",
    "player_count",
]


def _iter_matches(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Return the list of match objects from a HenrikDev payload, defensively."""
    if not isinstance(payload, dict):
        return []
    data = payload.get("data")
    if isinstance(data, list):
        return [m for m in data if isinstance(m, dict)]
    if isinstance(data, dict):
        return [data]
    return []


def _extract_match_id(metadata: dict[str, Any]) -> str | None:
    for key in ("matchid", "match_id", "id"):
        value = metadata.get(key)
        if value:
            return str(value)
    return None


def _player_list(match: dict[str, Any]) -> list[dict[str, Any]]:
    """Pull the per-player list out of a match, supporting both v3 shapes."""
    players_field = match.get("players")
    if isinstance(players_field, dict):
        all_players = players_field.get("all_players")
        if isinstance(all_players, list):
            return [p for p in all_players if isinstance(p, dict)]
    if isinstance(players_field, list):
        return [p for p in players_field if isinstance(p, dict)]
    return []


def _coerce_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _coerce_bool(value: Any) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        text = value.strip().lower()
        if text in {"true", "1", "yes"}:
            return True
        if text in {"false", "0", "no"}:
            return False
    return None


def _team_sections(match: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Return ``{"red": {...}, "blue": {...}}`` regardless of input shape."""
    teams = match.get("teams") if isinstance(match, dict) else None
    if isinstance(teams, dict):
        return {
            str(k).lower(): v
            for k, v in teams.items()
            if isinstance(v, dict)
        }
    if isinstance(teams, list):
        out: dict[str, dict[str, Any]] = {}
        for entry in teams:
            if not isinstance(entry, dict):
                continue
            color = (
                entry.get("team_id")
                or entry.get("team")
                or entry.get("color")
                or entry.get("name")
            )
            if isinstance(color, str) and color:
                out[color.lower()] = entry
        return out
    return {}


def _player_team(player: dict[str, Any]) -> str | None:
    team = player.get("team")
    if isinstance(team, str):
        return team
    if isinstance(team, dict):
        for key in ("name", "team", "id"):
            v = team.get(key)
            if isinstance(v, str):
                return v
    return None


def _player_stats(player: dict[str, Any]) -> dict[str, Any]:
    stats = player.get("stats")
    return stats if isinstance(stats, dict) else {}


def _player_damage(player: dict[str, Any], key: str) -> int | None:
    """Find a damage field that may live at the top level or inside ``stats``."""
    if key in player:
        coerced = _coerce_int(player.get(key))
        if coerced is not None:
            return coerced
    stats = _player_stats(player)
    return _coerce_int(stats.get(key))


def _is_premier_match(match: dict[str, Any]) -> bool:
    """Return True if a match looks like a Valorant Premier match.

    HenrikDev's payloads tag Premier matches with ``queue == "premier"`` and/or
    ``mode == "Premier"``. Newer payloads also expose ``metadata.premier_info``
    with non-null ``tournament_id`` for Premier games. We accept either signal
    so spelling/version differences still match.
    """
    if not isinstance(match, dict):
        return False
    metadata = match.get("metadata")
    if not isinstance(metadata, dict):
        return False

    premier_info = metadata.get("premier_info")
    if isinstance(premier_info, dict) and (
        premier_info.get("tournament_id") or premier_info.get("matchup_id")
    ):
        return True

    candidates = [
        metadata.get("queue"),
        metadata.get("queue_id"),
        metadata.get("mode"),
        metadata.get("mode_id"),
    ]
    return any(
        isinstance(value, str) and "premier" in value.lower()
        for value in candidates
    )


def _stored_match_id(meta: dict[str, Any]) -> str | None:
    for key in ("id", "matchid", "match_id"):
        value = meta.get(key)
        if value:
            return str(value)
    return None


def _is_premier_stored_entry(entry: dict[str, Any]) -> bool:
    """Premier check for ``/v1/stored-matches`` items (uses ``meta`` not ``metadata``)."""
    if not isinstance(entry, dict):
        return False
    meta = entry.get("meta")
    if not isinstance(meta, dict):
        return False
    candidates = [meta.get("mode"), meta.get("queue"), meta.get("queue_id")]
    return any(
        isinstance(value, str) and "premier" in value.lower()
        for value in candidates
    )


def extract_match_ids_from_stored(
    payload: dict[str, Any],
    *,
    premier_only: bool = True,
) -> list[str]:
    """Return ``match_id`` values found in a ``/v1/stored-matches`` response.

    Order is preserved (newest first as the API returns them) and duplicates
    are removed. When ``premier_only`` is True, non-Premier entries are
    skipped so the caller can immediately fan out to ``get_match_by_id``.
    """
    if not isinstance(payload, dict):
        return []
    data = payload.get("data")
    if not isinstance(data, list):
        return []

    seen: set[str] = set()
    ids: list[str] = []
    for entry in data:
        if not isinstance(entry, dict):
            continue
        meta = entry.get("meta") if isinstance(entry.get("meta"), dict) else {}
        match_id = _stored_match_id(meta)
        if not match_id or match_id in seen:
            continue
        if premier_only and not _is_premier_stored_entry(entry):
            continue
        seen.add(match_id)
        ids.append(match_id)
    return ids


def stored_pagination(payload: dict[str, Any]) -> dict[str, Any]:
    """Return the ``results`` pagination block from a stored-matches payload."""
    if not isinstance(payload, dict):
        return {}
    results = payload.get("results")
    return results if isinstance(results, dict) else {}


def wrap_single_match(match_payload: dict[str, Any]) -> dict[str, Any]:
    """Wrap ``/v2/match/{matchid}`` response into the ``/v3/matches`` shape.

    ``get_match_by_id`` returns ``{"status": ..., "data": <match>}`` where
    ``data`` is a single dict. The rest of the pipeline expects ``data`` to be
    a list, so we re-wrap once at the boundary.
    """
    if not isinstance(match_payload, dict):
        return {"status": 200, "data": []}
    inner = match_payload.get("data")
    if isinstance(inner, dict):
        return {"status": match_payload.get("status", 200), "data": [inner]}
    if isinstance(inner, list):
        return {"status": match_payload.get("status", 200), "data": inner}
    return {"status": match_payload.get("status", 200), "data": []}


def filter_premier(payload: dict[str, Any]) -> dict[str, Any]:
    """Return a new payload containing only Premier matches.

    The shape mirrors HenrikDev's response (``{"status": ..., "data": [...]}``)
    so downstream normalization works without changes.
    """
    premier = [m for m in _iter_matches(payload) if _is_premier_match(m)]
    status = payload.get("status") if isinstance(payload, dict) else None
    return {"status": status if status is not None else 200, "data": premier}


def normalize_matches(payload: dict[str, Any]) -> pd.DataFrame:
    """Build a per-match DataFrame from a HenrikDev matches payload."""
    rows: list[dict[str, Any]] = []
    for match in _iter_matches(payload):
        metadata = match.get("metadata") or {}
        if not isinstance(metadata, dict):
            metadata = {}
        rows.append(
            {
                "match_id": _extract_match_id(metadata),
                "map_name": metadata.get("map") or metadata.get("map_name"),
                "mode": metadata.get("mode"),
                "queue": metadata.get("queue") or metadata.get("queue_id"),
                "game_start": metadata.get("game_start")
                or metadata.get("game_start_patched"),
                "game_length": metadata.get("game_length"),
            }
        )

    if not rows:
        return pd.DataFrame(columns=MATCH_COLUMNS)
    return pd.DataFrame(rows, columns=MATCH_COLUMNS)


def normalize_match_teams(payload: dict[str, Any]) -> pd.DataFrame:
    """Build a per-team-per-match DataFrame.

    Includes the Premier roster identity (``id``/``name``/``tag``) when the
    payload exposes it under ``teams.<color>.roster``. This is what lets us
    tell *which Premier team* was on each side and identify opponents.
    """
    rows: list[dict[str, Any]] = []
    for match in _iter_matches(payload):
        metadata = match.get("metadata") or {}
        if not isinstance(metadata, dict):
            metadata = {}
        match_id = _extract_match_id(metadata)

        for team_key, section in _team_sections(match).items():
            roster = section.get("roster")
            if not isinstance(roster, dict):
                roster = {}
            rows.append(
                {
                    "match_id": match_id,
                    "team": team_key.capitalize(),
                    "has_won": _coerce_bool(section.get("has_won")),
                    "rounds_won": _coerce_int(section.get("rounds_won")),
                    "rounds_lost": _coerce_int(section.get("rounds_lost")),
                    "premier_team_id": roster.get("id"),
                    "premier_team_name": roster.get("name"),
                    "premier_team_tag": roster.get("tag"),
                }
            )

    if not rows:
        return pd.DataFrame(columns=TEAM_COLUMNS)
    return pd.DataFrame(rows, columns=TEAM_COLUMNS)


def normalize_rounds(payload: dict[str, Any]) -> pd.DataFrame:
    """Build a per-round DataFrame.

    Stores the minimum useful round-level info (winner, end type, bomb plant /
    defuse). Per-player round stats and kill events are intentionally left for
    a later phase to keep the initial schema small.
    """
    rows: list[dict[str, Any]] = []
    for match in _iter_matches(payload):
        metadata = match.get("metadata") or {}
        if not isinstance(metadata, dict):
            metadata = {}
        match_id = _extract_match_id(metadata)
        rounds = match.get("rounds")
        if not isinstance(rounds, list):
            continue
        for idx, r in enumerate(rounds, start=1):
            if not isinstance(r, dict):
                continue
            winning = (
                r.get("winning_team")
                or r.get("winning_team_id")
                or r.get("winner")
            )
            end_type = (
                r.get("end_type")
                or r.get("round_result")
                or r.get("result")
            )
            rows.append(
                {
                    "match_id": match_id,
                    "round_num": idx,
                    "winning_team": (
                        winning.capitalize()
                        if isinstance(winning, str) and winning
                        else None
                    ),
                    "end_type": end_type if isinstance(end_type, str) else None,
                    "bomb_planted": _coerce_bool(r.get("bomb_planted")),
                    "bomb_defused": _coerce_bool(r.get("bomb_defused")),
                }
            )

    if not rows:
        return pd.DataFrame(columns=ROUND_COLUMNS)
    return pd.DataFrame(rows, columns=ROUND_COLUMNS)


def _compute_first_kills_deaths(match: dict[str, Any]) -> tuple[dict[str, int], dict[str, int]]:
    """Return ({puuid: first_kills}, {puuid: first_deaths}) for a match.

    For each round, the kill with the lowest kill_time_in_round is the
    'opening duel'. The killer gets +1 FK and the victim gets +1 FD.
    All players (both teams) are included.
    """
    kills_list = match.get("kills")
    rounds_list = match.get("rounds")
    if not isinstance(kills_list, list) or not isinstance(rounds_list, list):
        return {}, {}

    # Group kill events by round
    round_kills: dict[int, list[dict[str, Any]]] = {}
    for k in kills_list:
        if not isinstance(k, dict):
            continue
        rnd = k.get("round")
        if rnd is None:
            continue
        try:
            rnd = int(rnd)
        except (TypeError, ValueError):
            continue
        round_kills.setdefault(rnd, []).append(k)

    first_kills: dict[str, int] = {}
    first_deaths: dict[str, int] = {}

    for kills_in_round in round_kills.values():
        # Find the opening kill (minimum kill_time_in_round)
        opening = min(
            kills_in_round,
            key=lambda k: k.get("kill_time_in_round") or 0,
        )
        killer = opening.get("killer_puuid")
        victim = opening.get("victim_puuid")
        if killer:
            first_kills[killer] = first_kills.get(killer, 0) + 1
        if victim:
            first_deaths[victim] = first_deaths.get(victim, 0) + 1

    return first_kills, first_deaths


def _compute_kast_rounds(match: dict[str, Any]) -> dict[str, int]:
    """Return {puuid: kast_rounds_count} for every player in a match.

    A round counts for a player if they had a Kill, Assist, Survived, or
    were Traded (died but their killer was killed within 5 000 ms by a teammate).
    """
    kills_list = match.get("kills")
    rounds_list = match.get("rounds")
    if not isinstance(kills_list, list) or not isinstance(rounds_list, list):
        return {}
    total_rounds = len(rounds_list)
    if total_rounds == 0:
        return {}

    # Collect all puuids from kill events
    all_puuids: set[str] = set()
    for k in kills_list:
        if not isinstance(k, dict):
            continue
        if k.get("killer_puuid"):
            all_puuids.add(k["killer_puuid"])
        if k.get("victim_puuid"):
            all_puuids.add(k["victim_puuid"])
        for a in k.get("assistants") or []:
            if isinstance(a, dict) and a.get("assistant_puuid"):
                all_puuids.add(a["assistant_puuid"])

    # Also collect from per-round player_stats (catches players who went 0/0/0)
    for r in rounds_list:
        if not isinstance(r, dict):
            continue
        for ps in r.get("player_stats") or []:
            if isinstance(ps, dict) and ps.get("player_puuid"):
                all_puuids.add(ps["player_puuid"])

    if not all_puuids:
        return {}

    # Index kills by round number
    round_kills: dict[int, list[dict[str, Any]]] = {}
    for k in kills_list:
        if not isinstance(k, dict):
            continue
        rnd = k.get("round")
        if rnd is None:
            continue
        try:
            rnd = int(rnd)
        except (TypeError, ValueError):
            continue
        round_kills.setdefault(rnd, []).append(k)

    kast_rounds: dict[str, int] = {p: 0 for p in all_puuids}

    for rnd_idx in range(total_rounds):
        kills_in_round = round_kills.get(rnd_idx, [])

        killers: set[str] = set()
        victims: set[str] = set()
        assistants: set[str] = set()
        # (victim_puuid -> kill_time_in_round, killer_puuid)
        death_info: dict[str, tuple[int, str]] = {}

        for k in kills_in_round:
            killer = k.get("killer_puuid")
            victim = k.get("victim_puuid")
            t = k.get("kill_time_in_round") or 0
            if killer:
                killers.add(killer)
            if victim:
                victims.add(victim)
                if killer:
                    death_info[victim] = (int(t), killer)
            for a in k.get("assistants") or []:
                if isinstance(a, dict) and a.get("assistant_puuid"):
                    assistants.add(a["assistant_puuid"])

        # Trade: player died, but their killer was killed within 5 000 ms
        traded: set[str] = set()
        for victim, (death_time, killer_puuid) in death_info.items():
            killer_death = death_info.get(killer_puuid)
            if killer_death is not None:
                trade_delta = abs(killer_death[0] - death_time)
                if trade_delta <= 5000:
                    traded.add(victim)

        for puuid in all_puuids:
            if (
                puuid in killers
                or puuid in assistants
                or puuid not in victims   # survived
                or puuid in traded
            ):
                kast_rounds[puuid] = kast_rounds.get(puuid, 0) + 1

    return kast_rounds


def normalize_match_players(payload: dict[str, Any]) -> pd.DataFrame:
    """Build a long, per-player-per-match DataFrame."""
    rows: list[dict[str, Any]] = []
    for match in _iter_matches(payload):
        metadata = match.get("metadata") or {}
        if not isinstance(metadata, dict):
            metadata = {}
        match_id = _extract_match_id(metadata)

        kast_map = _compute_kast_rounds(match)
        fk_map, fd_map = _compute_first_kills_deaths(match)

        for player in _player_list(match):
            stats = _player_stats(player)
            puuid = player.get("puuid")
            rows.append(
                {
                    "match_id": match_id,
                    "puuid": puuid,
                    "name": player.get("name"),
                    "tag": player.get("tag"),
                    "team": _player_team(player),
                    "agent": player.get("character") or player.get("agent"),
                    "kills": _coerce_int(stats.get("kills") or player.get("kills")),
                    "deaths": _coerce_int(stats.get("deaths") or player.get("deaths")),
                    "assists": _coerce_int(
                        stats.get("assists") or player.get("assists")
                    ),
                    "score": _coerce_int(stats.get("score") or player.get("score")),
                    "damage_made": _player_damage(player, "damage_made"),
                    "damage_received": _player_damage(player, "damage_received"),
                    "kast_rounds": kast_map.get(puuid) if puuid else None,
                    "first_kills": fk_map.get(puuid, 0) if puuid else 0,
                    "first_deaths": fd_map.get(puuid, 0) if puuid else 0,
                }
            )

    if not rows:
        return pd.DataFrame(columns=PLAYER_COLUMNS)
    return pd.DataFrame(rows, columns=PLAYER_COLUMNS)


def normalize_round_economy(payload: dict[str, Any]) -> pd.DataFrame:
    """Build a per-round-per-team economy DataFrame.

    For each round, aggregate each team's loadout_value and spent across all
    players. One row per (match_id, round_num, team).
    """
    rows: list[dict[str, Any]] = []

    for match in _iter_matches(payload):
        metadata = match.get("metadata") or {}
        if not isinstance(metadata, dict):
            metadata = {}
        match_id = _extract_match_id(metadata)

        rounds_list = match.get("rounds")
        if not isinstance(rounds_list, list):
            continue

        for round_idx, rnd in enumerate(rounds_list, start=1):
            if not isinstance(rnd, dict):
                continue

            player_stats = rnd.get("player_stats")
            if not isinstance(player_stats, list):
                continue

            # Aggregate per team
            team_data: dict[str, dict[str, Any]] = {}
            for ps in player_stats:
                if not isinstance(ps, dict):
                    continue
                team = ps.get("player_team")
                if not isinstance(team, str) or not team:
                    continue
                econ = ps.get("economy") or {}
                if not isinstance(econ, dict):
                    econ = {}
                loadout = _coerce_int(econ.get("loadout_value")) or 0
                spent = _coerce_int(econ.get("spent")) or 0

                if team not in team_data:
                    team_data[team] = {
                        "total_loadout": 0,
                        "total_spent": 0,
                        "player_count": 0,
                    }
                team_data[team]["total_loadout"] += loadout
                team_data[team]["total_spent"] += spent
                team_data[team]["player_count"] += 1

            for team, td in team_data.items():
                count = td["player_count"]
                rows.append(
                    {
                        "match_id": match_id,
                        "round_num": round_idx,
                        "team": team,
                        "total_loadout": td["total_loadout"],
                        "avg_loadout": round(td["total_loadout"] / count, 1)
                        if count > 0
                        else 0.0,
                        "total_spent": td["total_spent"],
                        "player_count": count,
                    }
                )

    if not rows:
        return pd.DataFrame(columns=ROUND_ECONOMY_COLUMNS)
    return pd.DataFrame(rows, columns=ROUND_ECONOMY_COLUMNS)

