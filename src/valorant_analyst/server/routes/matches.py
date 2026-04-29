"""Single-match detail route — used by the vlr.gg-style match page."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException

from ..deps import db_path, open_duckdb
from ..schemas import (
    MatchDetail,
    MatchPlayerStat,
    MatchTeamSummary,
    RoundEntry,
    RoundEconomyEntry,
)
from ..vods import vod_url_for

router = APIRouter(prefix="/matches", tags=["matches"])


def _safe_int(value: object) -> int | None:
    if value is None:
        return None
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _round_div(numerator: int | None, denom: int) -> float | None:
    if numerator is None or denom <= 0:
        return None
    return round(numerator / denom, 1)


@router.get("/{match_id}", response_model=MatchDetail)
def get_match(
    match_id: str,
    path: Path = Depends(db_path),
) -> MatchDetail:
    """Return everything needed to render a vlr.gg-style match page.

    Combines:
    - ``matches`` (map / mode / queue / start / duration)
    - ``match_teams`` (Red & Blue side scores + Premier identity)
    - ``rounds`` (round-by-round timeline)
    - ``match_players`` (per-player stats with derived ACS / ADR / +/-)
    """
    with open_duckdb(path) as con:
        match_row = con.execute(
            'SELECT match_id, map_name, mode, queue, game_start, game_length '
            'FROM "matches" WHERE match_id = ?',
            [match_id],
        ).fetchone()
        if not match_row:
            raise HTTPException(
                status_code=404,
                detail=f"Match not found: {match_id}",
            )

        team_rows = con.execute(
            'SELECT team, has_won, rounds_won, rounds_lost, '
            'premier_team_id, premier_team_name, premier_team_tag '
            'FROM "match_teams" WHERE match_id = ? ORDER BY team',
            [match_id],
        ).fetchall()
        teams = [
            MatchTeamSummary(
                team=str(r[0]),
                has_won=bool(r[1]) if r[1] is not None else None,
                rounds_won=_safe_int(r[2]),
                rounds_lost=_safe_int(r[3]),
                premier_team_id=r[4],
                premier_team_name=r[5],
                premier_team_tag=r[6],
            )
            for r in team_rows
        ]

        round_rows = con.execute(
            'SELECT round_num, winning_team, end_type, bomb_planted, bomb_defused '
            'FROM "rounds" WHERE match_id = ? ORDER BY round_num',
            [match_id],
        ).fetchall()
        rounds = [
            RoundEntry(
                round_num=int(r[0]),
                winning_team=r[1],
                end_type=r[2],
                bomb_planted=bool(r[3]) if r[3] is not None else None,
                bomb_defused=bool(r[4]) if r[4] is not None else None,
            )
            for r in round_rows
        ]

        # Total rounds: prefer the rounds table count; fall back to summing
        # rounds_won across both teams (handles old DB rows without rounds).
        total_rounds = len(rounds)
        if total_rounds == 0:
            total_rounds = sum((t.rounds_won or 0) for t in teams)

        # Sort players by score desc so the scoreboard already comes out sorted.
        #
        # HenrikDev anonymizes name/tag on very recent Premier matches (returns
        # empty strings, not nulls). When that happens we backfill name/tag by
        # looking up the same ``puuid`` in any *other* match — Riot IDs are
        # stable across matches, so this is safe.
        player_rows = con.execute(
            '''
            WITH known AS (
                SELECT puuid,
                       ANY_VALUE(name) FILTER (
                           WHERE name IS NOT NULL AND name <> ''
                       ) AS name,
                       ANY_VALUE(tag) FILTER (
                           WHERE tag IS NOT NULL AND tag <> ''
                       ) AS tag
                FROM "match_players"
                GROUP BY puuid
            )
            SELECT mp.puuid,
                   COALESCE(NULLIF(mp.name, ''), k.name) AS name,
                   COALESCE(NULLIF(mp.tag,  ''), k.tag)  AS tag,
                   mp.team, mp.agent,
                   mp.kills, mp.deaths, mp.assists,
                   mp.score, mp.damage_made, mp.damage_received
            FROM "match_players" mp
            LEFT JOIN known k ON k.puuid = mp.puuid
            WHERE mp.match_id = ?
            ORDER BY mp.score DESC NULLS LAST
            ''',
            [match_id],
        ).fetchall()

        players: list[MatchPlayerStat] = []
        for r in player_rows:
            puuid, name, tag, team, agent = r[0], r[1], r[2], r[3], r[4]
            kills = _safe_int(r[5])
            deaths = _safe_int(r[6])
            assists = _safe_int(r[7])
            score = _safe_int(r[8])
            damage_made = _safe_int(r[9])
            damage_received = _safe_int(r[10])

            acs = _round_div(score, total_rounds)
            adr = _round_div(damage_made, total_rounds)
            kd = (
                round(kills / deaths, 2)
                if kills is not None and deaths not in (None, 0)
                else None
            )
            plus_minus = (
                kills - deaths if kills is not None and deaths is not None else None
            )

            players.append(
                MatchPlayerStat(
                    puuid=str(puuid),
                    name=name,
                    tag=tag,
                    team=team,
                    agent=agent,
                    kills=kills,
                    deaths=deaths,
                    assists=assists,
                    score=score,
                    damage_made=damage_made,
                    damage_received=damage_received,
                    acs=acs,
                    adr=adr,
                    kd_ratio=kd,
                    plus_minus=plus_minus,
                )
            )

        return MatchDetail(
            match_id=str(match_row[0]),
            vod_url=vod_url_for(match_id),
            map_name=match_row[1],
            mode=match_row[2],
            queue=match_row[3],
            game_start=_safe_int(match_row[4]),
            game_length=_safe_int(match_row[5]),
            total_rounds=total_rounds,
            teams=teams,
            rounds=rounds,
            players=players,
        )


@router.get("/{match_id}/economy", response_model=list[RoundEconomyEntry])
def get_match_economy(
    match_id: str,
    path: Path = Depends(db_path),
) -> list[RoundEconomyEntry]:
    """Return per-round team economy for a match."""
    with open_duckdb(path) as con:
        exists = con.execute(
            "SELECT 1 FROM information_schema.tables WHERE table_name = 'round_economy' LIMIT 1"
        ).fetchone()
        if not exists:
            raise HTTPException(status_code=404, detail="round_economy table not found.")

        rows = con.execute(
            '''
            SELECT round_num, team, total_loadout, avg_loadout, total_spent, player_count
            FROM "round_economy"
            WHERE match_id = ?
            ORDER BY round_num, team
            ''',
            [match_id],
        ).fetchall()

    return [
        RoundEconomyEntry(
            round_num=int(r[0]),
            team=str(r[1]),
            total_loadout=int(r[2] or 0),
            avg_loadout=float(r[3] or 0),
            total_spent=int(r[4] or 0),
            player_count=int(r[5] or 0),
        )
        for r in rows
    ]
