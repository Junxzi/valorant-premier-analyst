"""Premier team routes — vlr.gg-style team page data."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from ..deps import db_path, open_duckdb
from ..vods import load_vods
from ..schemas import (
    MapWinrate,
    OpponentSummary,
    OurTeamSummary,
    RecentMatch,
    RosterMember,
    TeamAgentUsage,
    TeamMapAgentComp,
    TeamMapStat,
    TeamMapStatsResponse,
    TeamMatchListResponse,
    TeamPlayerStat,
    TeamRecord,
    TeamResponse,
    TeamStatsResponse,
    UpcomingMatch,
)

router = APIRouter(prefix="/teams", tags=["teams"])


def _winrate(wins: int, games: int) -> float:
    return round(100.0 * wins / games, 1) if games else 0.0


def _ensure_team_seen(con: object, name: str, tag: str) -> None:
    """Raise 404 if no match in DuckDB references the given Premier team."""
    seen = con.execute(  # type: ignore[attr-defined]
        'SELECT COUNT(*) FROM "match_teams" '
        "WHERE premier_team_name = ? AND premier_team_tag = ?",
        [name, tag],
    ).fetchone()
    if not seen or not seen[0]:
        raise HTTPException(
            status_code=404,
            detail=f"Premier team not found in DuckDB: {name}#{tag}",
        )


def _fetch_recent_matches(
    con: object, name: str, tag: str, limit: int | None
) -> list[RecentMatch]:
    """Shared helper for `/teams/...` and `/teams/.../matches` endpoints."""
    sql = '''
        WITH ours AS (
            SELECT match_id, team, rounds_won, rounds_lost, has_won
            FROM "match_teams"
            WHERE premier_team_name = ? AND premier_team_tag = ?
        )
        SELECT
            m.match_id, m.map_name, m.mode, m.queue, m.game_start,
            ours.team AS our_team_color,
            ours.rounds_won AS our_rw,
            ours.rounds_lost AS our_rl,
            ours.has_won AS our_won,
            opp.team AS opp_team_color,
            opp.premier_team_name AS opp_name,
            opp.premier_team_tag AS opp_tag,
            opp.rounds_won AS opp_rw,
            opp.rounds_lost AS opp_rl
        FROM ours
        JOIN "matches" m ON m.match_id = ours.match_id
        LEFT JOIN "match_teams" opp
          ON opp.match_id = ours.match_id AND opp.team != ours.team
        ORDER BY m.game_start DESC NULLS LAST
    '''
    params: list[object] = [name, tag]
    if limit is not None:
        sql += " LIMIT ?"
        params.append(limit)

    rows = con.execute(sql, params).fetchall()  # type: ignore[attr-defined]
    vods = load_vods()
    out: list[RecentMatch] = []
    for r in rows:
        mid = str(r[0])
        out.append(
            RecentMatch(
                match_id=mid,
                vod_url=vods.get(mid),
                map_name=r[1],
                mode=r[2],
                queue=r[3],
                game_start=int(r[4]) if r[4] is not None else None,
                our_team=OurTeamSummary(
                    team=str(r[5]) if r[5] is not None else "Unknown",
                    rounds_won=int(r[6]) if r[6] is not None else None,
                    rounds_lost=int(r[7]) if r[7] is not None else None,
                    has_won=bool(r[8]) if r[8] is not None else None,
                ),
                opponent=OpponentSummary(
                    team=r[9],
                    name=r[10],
                    tag=r[11],
                    rounds_won=int(r[12]) if r[12] is not None else None,
                    rounds_lost=int(r[13]) if r[13] is not None else None,
                ),
            )
        )
    return out


@router.get("/{name}/{tag}", response_model=TeamResponse)
def get_team(
    name: str,
    tag: str,
    recent_limit: int = Query(default=10, ge=1, le=100),
    path: Path = Depends(db_path),
) -> TeamResponse:
    """Return a Premier team's overview, recent matches, map winrates and roster."""
    with open_duckdb(path) as con:
        _ensure_team_seen(con, name, tag)

        rec = con.execute(
            '''
            SELECT
                COUNT(*) AS games,
                SUM(CASE WHEN has_won THEN 1 ELSE 0 END) AS wins,
                SUM(CASE WHEN has_won = FALSE THEN 1 ELSE 0 END) AS losses
            FROM "match_teams"
            WHERE premier_team_name = ? AND premier_team_tag = ?
            ''',
            [name, tag],
        ).fetchone()
        games = int(rec[0] or 0)
        wins = int(rec[1] or 0)
        losses = int(rec[2] or 0)
        record = TeamRecord(
            games=games, wins=wins, losses=losses, winrate_pct=_winrate(wins, games)
        )

        recent = _fetch_recent_matches(con, name, tag, recent_limit)

        # Upcoming matches from premier_schedule (table may not exist yet)
        upcoming: list[UpcomingMatch] = []
        try:
            sched_rows = con.execute(  # type: ignore[attr-defined]
                """
                SELECT scheduled_at, map_name, opponent_name, opponent_tag
                FROM "premier_schedule"
                WHERE premier_team_name = ? AND premier_team_tag = ?
                  AND scheduled_at > EXTRACT(EPOCH FROM NOW())
                ORDER BY scheduled_at
                """,
                [name, tag],
            ).fetchall()
            upcoming = [
                UpcomingMatch(
                    scheduled_at=int(r[0]),
                    map_name=r[1],
                    opponent_name=r[2],
                    opponent_tag=r[3],
                )
                for r in sched_rows
            ]
        except Exception:
            pass  # table doesn't exist yet — return empty list

        # Per-map winrates
        map_rows = con.execute(
            '''
            SELECT m.map_name,
                   COUNT(*) AS games,
                   SUM(CASE WHEN t.has_won THEN 1 ELSE 0 END) AS wins
            FROM "matches" m
            JOIN "match_teams" t ON m.match_id = t.match_id
            WHERE t.premier_team_name = ? AND t.premier_team_tag = ?
            GROUP BY 1 ORDER BY games DESC, m.map_name
            ''',
            [name, tag],
        ).fetchall()
        map_winrates = [
            MapWinrate(
                map_name=r[0],
                games=int(r[1] or 0),
                wins=int(r[2] or 0),
                winrate_pct=_winrate(int(r[2] or 0), int(r[1] or 0)),
            )
            for r in map_rows
        ]

        # Roster: players who played on this team's side
        roster_rows = con.execute(
            '''
            WITH our_matches AS (
                SELECT match_id, team
                FROM "match_teams"
                WHERE premier_team_name = ? AND premier_team_tag = ?
            )
            SELECT mp.puuid,
                   ANY_VALUE(mp.name) AS name,
                   ANY_VALUE(mp.tag)  AS tag,
                   COUNT(DISTINCT mp.match_id) AS games,
                   AVG(mp.kills) AS avg_kills,
                   AVG(mp.deaths) AS avg_deaths,
                   CASE WHEN SUM(mp.deaths) > 0
                        THEN ROUND(SUM(mp.kills) * 1.0 / SUM(mp.deaths), 2)
                        ELSE NULL END AS kd_ratio,
                   mode(mp.agent) AS agent_main
            FROM "match_players" mp
            JOIN our_matches om
              ON mp.match_id = om.match_id AND mp.team = om.team
            GROUP BY mp.puuid
            ORDER BY games DESC, name
            ''',
            [name, tag],
        ).fetchall()
        roster = [
            RosterMember(
                puuid=str(r[0]),
                name=r[1],
                tag=r[2],
                games=int(r[3] or 0),
                avg_kills=round(float(r[4]), 2) if r[4] is not None else None,
                avg_deaths=round(float(r[5]), 2) if r[5] is not None else None,
                kd_ratio=float(r[6]) if r[6] is not None else None,
                agent_main=r[7],
            )
            for r in roster_rows
        ]

        return TeamResponse(
            name=name,
            tag=tag,
            record=record,
            upcoming_matches=upcoming,
            recent_matches=recent,
            map_winrates=map_winrates,
            roster=roster,
        )


@router.get("/{name}/{tag}/matches", response_model=TeamMatchListResponse)
def get_team_matches(
    name: str,
    tag: str,
    limit: int | None = Query(default=None, ge=1, le=500),
    path: Path = Depends(db_path),
) -> TeamMatchListResponse:
    """Return every match the Premier team has played.

    The schema is intentionally identical to ``recent_matches`` on the team
    overview so the frontend can reuse the same row component.
    """
    with open_duckdb(path) as con:
        _ensure_team_seen(con, name, tag)
        matches = _fetch_recent_matches(con, name, tag, limit)
        return TeamMatchListResponse(
            name=name,
            tag=tag,
            total=len(matches),
            matches=matches,
        )


def _round2(value: object) -> float | None:
    if value is None:
        return None
    try:
        return round(float(value), 2)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


@router.get("/{name}/{tag}/stats", response_model=TeamStatsResponse)
def get_team_stats(
    name: str,
    tag: str,
    path: Path = Depends(db_path),
) -> TeamStatsResponse:
    """Per-player aggregates (ACS, ADR, K/D, +/−) and team-wide agent usage.

    Used by the `Stats` tab on the team page. Anonymized player names from
    very recent Premier matches are backfilled by looking the same ``puuid``
    up across the rest of the dataset.
    """
    with open_duckdb(path) as con:
        _ensure_team_seen(con, name, tag)

        totals = con.execute(
            '''
            WITH our_matches AS (
                SELECT match_id FROM "match_teams"
                WHERE premier_team_name = ? AND premier_team_tag = ?
            ),
            match_rounds AS (
                SELECT match_id, SUM(rounds_won) AS total_rounds
                FROM "match_teams" GROUP BY match_id
            )
            SELECT
                COUNT(DISTINCT om.match_id) AS games,
                COALESCE(SUM(mr.total_rounds), 0) AS rounds
            FROM our_matches om
            LEFT JOIN match_rounds mr USING (match_id)
            ''',
            [name, tag],
        ).fetchone()
        total_games = int(totals[0] or 0)
        total_rounds = int(totals[1] or 0)

        player_rows = con.execute(
            '''
            WITH our_matches AS (
                SELECT match_id, team FROM "match_teams"
                WHERE premier_team_name = ? AND premier_team_tag = ?
            ),
            match_rounds AS (
                SELECT match_id, SUM(rounds_won) AS total_rounds
                FROM "match_teams" GROUP BY match_id
            ),
            known_names AS (
                SELECT puuid,
                       ANY_VALUE(name) FILTER (
                           WHERE name IS NOT NULL AND name <> ''
                       ) AS name,
                       ANY_VALUE(tag) FILTER (
                           WHERE tag  IS NOT NULL AND tag  <> ''
                       ) AS tag
                FROM "match_players"
                GROUP BY puuid
            )
            SELECT mp.puuid,
                   kn.name AS name,
                   kn.tag  AS tag,
                   COUNT(DISTINCT mp.match_id) AS games,
                   SUM(mr.total_rounds)        AS rounds,
                   AVG(mp.kills)               AS avg_kills,
                   AVG(mp.deaths)              AS avg_deaths,
                   AVG(mp.assists)             AS avg_assists,
                   CASE WHEN SUM(mr.total_rounds) > 0
                        THEN SUM(mp.score) * 1.0 / SUM(mr.total_rounds)
                        ELSE NULL END          AS avg_acs,
                   CASE WHEN SUM(mr.total_rounds) > 0
                        THEN SUM(mp.damage_made) * 1.0 / SUM(mr.total_rounds)
                        ELSE NULL END          AS avg_adr,
                   AVG(mp.kills - mp.deaths)   AS avg_plus_minus,
                   CASE WHEN SUM(mp.deaths) > 0
                        THEN SUM(mp.kills) * 1.0 / SUM(mp.deaths)
                        ELSE NULL END          AS kd_ratio,
                   mode(mp.agent)              AS agent_main
            FROM "match_players" mp
            JOIN our_matches om
              ON mp.match_id = om.match_id AND mp.team = om.team
            JOIN match_rounds mr ON mr.match_id = mp.match_id
            LEFT JOIN known_names kn ON kn.puuid = mp.puuid
            GROUP BY mp.puuid, kn.name, kn.tag
            ORDER BY games DESC, avg_acs DESC NULLS LAST
            ''',
            [name, tag],
        ).fetchall()
        players = [
            TeamPlayerStat(
                puuid=str(r[0]),
                name=r[1],
                tag=r[2],
                games=int(r[3] or 0),
                rounds=int(r[4] or 0),
                avg_kills=_round2(r[5]),
                avg_deaths=_round2(r[6]),
                avg_assists=_round2(r[7]),
                avg_acs=_round2(r[8]),
                avg_adr=_round2(r[9]),
                avg_plus_minus=_round2(r[10]),
                kd_ratio=_round2(r[11]),
                agent_main=r[12],
            )
            for r in player_rows
        ]

        agent_rows = con.execute(
            '''
            WITH our_matches AS (
                SELECT match_id, team FROM "match_teams"
                WHERE premier_team_name = ? AND premier_team_tag = ?
            ),
            match_rounds AS (
                SELECT match_id, SUM(rounds_won) AS total_rounds
                FROM "match_teams" GROUP BY match_id
            )
            SELECT mp.agent,
                   COUNT(*) AS games,
                   CASE WHEN SUM(mr.total_rounds) > 0
                        THEN SUM(mp.score) * 1.0 / SUM(mr.total_rounds)
                        ELSE NULL END AS avg_acs,
                   CASE WHEN SUM(mr.total_rounds) > 0
                        THEN SUM(mp.damage_made) * 1.0 / SUM(mr.total_rounds)
                        ELSE NULL END AS avg_adr
            FROM "match_players" mp
            JOIN our_matches om
              ON mp.match_id = om.match_id AND mp.team = om.team
            JOIN match_rounds mr ON mr.match_id = mp.match_id
            GROUP BY mp.agent
            ORDER BY games DESC, mp.agent
            ''',
            [name, tag],
        ).fetchall()
        agent_usage = [
            TeamAgentUsage(
                agent=r[0],
                games=int(r[1] or 0),
                pick_rate_pct=(
                    round(100.0 * int(r[1] or 0) / total_games, 1)
                    if total_games
                    else 0.0
                ),
                avg_acs=_round2(r[2]),
                avg_adr=_round2(r[3]),
            )
            for r in agent_rows
        ]

        return TeamStatsResponse(
            name=name,
            tag=tag,
            total_games=total_games,
            total_rounds=total_rounds,
            players=players,
            agent_usage=agent_usage,
        )


@router.get("/{name}/{tag}/map-stats", response_model=TeamMapStatsResponse)
def get_team_map_stats(
    name: str,
    tag: str,
    path: Path = Depends(db_path),
) -> TeamMapStatsResponse:
    """Per-map ATK/DEF round breakdown + agent compositions.

    ATK/DEF side is inferred from round-level bomb data:
    - bomb exploded (planted AND NOT defused) → attacker won that round
    - otherwise (no plant OR defused) → defender won that round
    Starting side is determined from round 1 of each match.
    """
    with open_duckdb(path) as con:
        _ensure_team_seen(con, name, tag)

        map_rows = con.execute(
            """
            WITH our_matches AS (
                SELECT match_id, team AS our_color, has_won
                FROM "match_teams"
                WHERE premier_team_name = ? AND premier_team_tag = ?
            ),
            round_sides AS (
                -- For each round, determine if OUR team was on ATK side.
                -- ATK wins by detonation (bomb_planted AND NOT bomb_defused),
                -- DEF wins in all other outcomes.
                SELECT
                    r.match_id,
                    CASE
                        WHEN r.bomb_planted AND NOT COALESCE(r.bomb_defused, FALSE)
                            THEN (r.winning_team = om.our_color)
                        ELSE (r.winning_team <> om.our_color)
                    END AS we_were_atk,
                    (r.winning_team = om.our_color) AS we_won_round,
                    r.round_num
                FROM "rounds" r
                JOIN our_matches om ON r.match_id = om.match_id
            ),
            per_match_rounds AS (
                SELECT
                    match_id,
                    SUM(CASE WHEN     we_were_atk AND     we_won_round  THEN 1 ELSE 0 END) AS atk_rw,
                    SUM(CASE WHEN     we_were_atk AND NOT we_won_round  THEN 1 ELSE 0 END) AS atk_rl,
                    SUM(CASE WHEN NOT we_were_atk AND     we_won_round  THEN 1 ELSE 0 END) AS def_rw,
                    SUM(CASE WHEN NOT we_were_atk AND NOT we_won_round  THEN 1 ELSE 0 END) AS def_rl,
                    MAX(CASE WHEN round_num = 1 THEN we_were_atk END) AS atk_first
                FROM round_sides
                GROUP BY match_id
            )
            SELECT
                m.map_name,
                COUNT(*)                                                       AS games,
                SUM(CASE WHEN om.has_won THEN 1 ELSE 0 END)                   AS wins,
                COALESCE(SUM(pmr.atk_rw), 0)                                  AS atk_rw,
                COALESCE(SUM(pmr.atk_rl), 0)                                  AS atk_rl,
                COALESCE(SUM(pmr.def_rw), 0)                                  AS def_rw,
                COALESCE(SUM(pmr.def_rl), 0)                                  AS def_rl,
                SUM(CASE WHEN pmr.atk_first AND     om.has_won THEN 1 ELSE 0 END) AS atk_first_wins,
                SUM(CASE WHEN pmr.atk_first                    THEN 1 ELSE 0 END) AS atk_first_games,
                SUM(CASE WHEN NOT pmr.atk_first AND om.has_won THEN 1 ELSE 0 END) AS def_first_wins,
                SUM(CASE WHEN NOT pmr.atk_first                THEN 1 ELSE 0 END) AS def_first_games
            FROM our_matches om
            JOIN "matches" m ON m.match_id = om.match_id
            LEFT JOIN per_match_rounds pmr ON pmr.match_id = om.match_id
            GROUP BY m.map_name
            ORDER BY games DESC, m.map_name
            """,
            [name, tag],
        ).fetchall()

        # Agent compositions per map: sort agents alphabetically, count occurrences
        comp_rows = con.execute(
            """
            WITH our_matches AS (
                SELECT match_id, team AS our_color
                FROM "match_teams"
                WHERE premier_team_name = ? AND premier_team_tag = ?
            ),
            match_comps AS (
                SELECT m.map_name, mp.match_id,
                       STRING_AGG(mp.agent, '|' ORDER BY mp.agent) AS comp
                FROM "match_players" mp
                JOIN our_matches om ON mp.match_id = om.match_id AND mp.team = om.our_color
                JOIN "matches" m ON m.match_id = mp.match_id
                WHERE mp.agent IS NOT NULL
                GROUP BY m.map_name, mp.match_id
            )
            SELECT map_name, comp, COUNT(*) AS cnt
            FROM match_comps
            GROUP BY map_name, comp
            ORDER BY map_name, cnt DESC
            """,
            [name, tag],
        ).fetchall()

        # Per-match detail for expanded rows
        match_detail_rows = con.execute(
            """
            WITH our_matches AS (
                SELECT match_id, team AS our_color, has_won,
                       rounds_won, rounds_lost
                FROM "match_teams"
                WHERE premier_team_name = ? AND premier_team_tag = ?
            ),
            round_sides AS (
                SELECT
                    r.match_id,
                    CASE
                        WHEN r.bomb_planted AND NOT COALESCE(r.bomb_defused, FALSE)
                            THEN (r.winning_team = om.our_color)
                        ELSE (r.winning_team <> om.our_color)
                    END AS we_were_atk,
                    (r.winning_team = om.our_color) AS we_won_round,
                    r.round_num
                FROM "rounds" r
                JOIN our_matches om ON r.match_id = om.match_id
            ),
            per_match_rounds AS (
                SELECT
                    match_id,
                    SUM(CASE WHEN     we_were_atk AND     we_won_round  THEN 1 ELSE 0 END) AS atk_rw,
                    SUM(CASE WHEN     we_were_atk AND NOT we_won_round  THEN 1 ELSE 0 END) AS atk_rl,
                    SUM(CASE WHEN NOT we_were_atk AND     we_won_round  THEN 1 ELSE 0 END) AS def_rw,
                    SUM(CASE WHEN NOT we_were_atk AND NOT we_won_round  THEN 1 ELSE 0 END) AS def_rl,
                    MAX(CASE WHEN round_num = 1 THEN we_were_atk END) AS atk_first
                FROM round_sides
                GROUP BY match_id
            ),
            match_agents AS (
                SELECT mp.match_id,
                       STRING_AGG(mp.agent, '|' ORDER BY mp.agent) AS agents
                FROM "match_players" mp
                JOIN our_matches om ON mp.match_id = om.match_id AND mp.team = om.our_color
                WHERE mp.agent IS NOT NULL
                GROUP BY mp.match_id
            )
            SELECT
                om.match_id,
                m.map_name,
                m.game_start,
                om.has_won,
                om.rounds_won,
                om.rounds_lost,
                opp.premier_team_name AS opp_name,
                opp.premier_team_tag  AS opp_tag,
                COALESCE(pmr.atk_first, FALSE)  AS atk_first,
                COALESCE(pmr.atk_rw, 0)         AS atk_rw,
                COALESCE(pmr.atk_rl, 0)         AS atk_rl,
                COALESCE(pmr.def_rw, 0)         AS def_rw,
                COALESCE(pmr.def_rl, 0)         AS def_rl,
                COALESCE(ma.agents, '')          AS agents
            FROM our_matches om
            JOIN "matches" m ON m.match_id = om.match_id
            LEFT JOIN per_match_rounds pmr ON pmr.match_id = om.match_id
            LEFT JOIN "match_teams" opp
              ON opp.match_id = om.match_id AND opp.team <> om.our_color
                 AND opp.premier_team_name IS NOT NULL
            LEFT JOIN match_agents ma ON ma.match_id = om.match_id
            ORDER BY m.map_name, m.game_start DESC NULLS LAST
            """,
            [name, tag],
        ).fetchall()

        # Index comps by map_name → top 3
        from collections import defaultdict

        comps_by_map: dict[str, list[TeamMapAgentComp]] = defaultdict(list)
        for cr in comp_rows:
            map_key = cr[0]
            if len(comps_by_map[map_key]) < 3:
                agents = [a for a in str(cr[1]).split("|") if a]
                comps_by_map[map_key].append(
                    TeamMapAgentComp(agents=agents, count=int(cr[2]))
                )

        # Index per-match details by map_name
        from ..schemas import TeamMapMatchDetail  # noqa: PLC0415

        vods = load_vods()
        matches_by_map: dict[str, list[TeamMapMatchDetail]] = defaultdict(list)
        for mr in match_detail_rows:
            map_key = mr[1] or ""
            mid = str(mr[0])
            matches_by_map[map_key].append(
                TeamMapMatchDetail(
                    match_id=mid,
                    vod_url=vods.get(mid),
                    game_start=int(mr[2]) if mr[2] is not None else None,
                    has_won=bool(mr[3]) if mr[3] is not None else None,
                    rounds_won=int(mr[4]) if mr[4] is not None else None,
                    rounds_lost=int(mr[5]) if mr[5] is not None else None,
                    opponent_name=mr[6],
                    opponent_tag=mr[7],
                    atk_first=bool(mr[8]),
                    atk_rounds_won=int(mr[9] or 0),
                    atk_rounds_lost=int(mr[10] or 0),
                    def_rounds_won=int(mr[11] or 0),
                    def_rounds_lost=int(mr[12] or 0),
                    agents=[a for a in str(mr[13]).split("|") if a],
                )
            )

        def _pct(wins: int, games: int) -> float:
            return round(100.0 * wins / games, 1) if games else 0.0

        maps: list[TeamMapStat] = []
        for r in map_rows:
            map_name = r[0]
            games = int(r[1] or 0)
            wins = int(r[2] or 0)
            atk_rw = int(r[3] or 0)
            atk_rl = int(r[4] or 0)
            def_rw = int(r[5] or 0)
            def_rl = int(r[6] or 0)
            atk_fw = int(r[7] or 0)
            atk_fg = int(r[8] or 0)
            def_fw = int(r[9] or 0)
            def_fg = int(r[10] or 0)
            maps.append(
                TeamMapStat(
                    map_name=map_name,
                    games=games,
                    wins=wins,
                    losses=games - wins,
                    winrate_pct=_pct(wins, games),
                    atk_rounds_won=atk_rw,
                    atk_rounds_lost=atk_rl,
                    atk_rw_pct=_pct(atk_rw, atk_rw + atk_rl),
                    def_rounds_won=def_rw,
                    def_rounds_lost=def_rl,
                    def_rw_pct=_pct(def_rw, def_rw + def_rl),
                    atk_first_games=atk_fg,
                    atk_first_wins=atk_fw,
                    atk_first_winrate_pct=_pct(atk_fw, atk_fg),
                    def_first_games=def_fg,
                    def_first_wins=def_fw,
                    def_first_winrate_pct=_pct(def_fw, def_fg),
                    agent_comps=comps_by_map.get(map_name or "", []),
                    matches=matches_by_map.get(map_name or "", []),
                )
            )

        return TeamMapStatsResponse(name=name, tag=tag, maps=maps)


# ---------------------------------------------------------------------------
# Team notes — simple per-team markdown stored as flat files
# ---------------------------------------------------------------------------

_NOTES_DIR = Path(__file__).resolve().parents[4] / "data" / "notes"


def _note_path(name: str, tag: str) -> Path:
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in f"{name}__{tag}")
    return _NOTES_DIR / f"{safe}.md"


class _NoteBody(BaseModel):
    content: str


@router.get("/{name}/{tag}/note", response_model=_NoteBody)
def get_team_note(name: str, tag: str) -> _NoteBody:
    """Return the saved markdown note for a team."""
    path = _note_path(name, tag)
    if not path.exists():
        return _NoteBody(content="")
    return _NoteBody(content=path.read_text(encoding="utf-8"))


@router.put("/{name}/{tag}/note", response_model=_NoteBody)
def put_team_note(name: str, tag: str, body: _NoteBody) -> _NoteBody:
    """Save (overwrite) the markdown note for a team."""
    path = _note_path(name, tag)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body.content, encoding="utf-8")
    return body


# ---------------------------------------------------------------------------
# Team strategy — per-map agent compositions stored as JSON files
# ---------------------------------------------------------------------------

_STRATEGY_DIR = Path(__file__).resolve().parents[4] / "data" / "strategy"


def _strategy_path(name: str, tag: str) -> Path:
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in f"{name}__{tag}")
    return _STRATEGY_DIR / f"{safe}.json"


class _StrategyBody(BaseModel):
    # map name → { player name → agent name | null }
    data: dict[str, dict[str, str | None]]
    # map name → markdown note text
    notes: dict[str, str] = {}


@router.get("/{name}/{tag}/strategy", response_model=_StrategyBody)
def get_team_strategy(name: str, tag: str) -> _StrategyBody:
    """Return saved per-map agent compositions for a team."""
    path = _strategy_path(name, tag)
    if not path.exists():
        return _StrategyBody(data={})
    import json
    return _StrategyBody(data=json.loads(path.read_text(encoding="utf-8")))


@router.put("/{name}/{tag}/strategy", response_model=_StrategyBody)
def put_team_strategy(name: str, tag: str, body: _StrategyBody) -> _StrategyBody:
    """Save per-map agent compositions for a team."""
    import json
    path = _strategy_path(name, tag)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(body.data, ensure_ascii=False, indent=2), encoding="utf-8")
    return body
