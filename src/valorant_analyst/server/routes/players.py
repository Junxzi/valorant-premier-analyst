"""Player overview route — backs the vlr.gg-style player detail page."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from ..deps import db_path, open_duckdb
from ..schemas import (
    PlayerAgentStat,
    PlayerMapStat,
    PlayerMatchEntry,
    PlayerOverview,
    PlayerSummary,
    PlayerTeamAffiliation,
)
from ..vods import load_vods

router = APIRouter(prefix="/players", tags=["players"])


def _round2(value: object) -> float | None:
    if value is None:
        return None
    try:
        return round(float(value), 2)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _safe_int(value: object) -> int | None:
    if value is None:
        return None
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _winrate(wins: int, games: int) -> float:
    return round(100.0 * wins / games, 1) if games else 0.0


@router.get("/{puuid}", response_model=PlayerOverview)
def get_player(
    puuid: str,
    recent_limit: int = Query(default=20, ge=1, le=200),
    path: Path = Depends(db_path),
) -> PlayerOverview:
    """Return a player's full Premier history snapshot.

    Mirrors what vlr.gg shows on a player page: header (Riot ID + current
    team), summary tiles, agent usage, map performance, team affiliation
    history and a list of recent matches.
    """
    with open_duckdb(path) as con:
        seen = con.execute(
            'SELECT COUNT(*) FROM "match_players" WHERE puuid = ?',
            [puuid],
        ).fetchone()
        if not seen or not seen[0]:
            raise HTTPException(
                status_code=404,
                detail=f"Player not found in DuckDB: {puuid}",
            )

        # Backfill the player's display name from any match where it isn't
        # anonymized. HenrikDev redacts name/tag on the latest Premier season,
        # so we may only have the real Riot ID on older matches.
        name_row = con.execute(
            '''
            SELECT
                ANY_VALUE(name) FILTER (WHERE name IS NOT NULL AND name <> '') AS name,
                ANY_VALUE(tag)  FILTER (WHERE tag  IS NOT NULL AND tag  <> '') AS tag
            FROM "match_players"
            WHERE puuid = ?
            ''',
            [puuid],
        ).fetchone()
        display_name = name_row[0] if name_row else None
        display_tag = name_row[1] if name_row else None

        # ------------------------------------------------------------- summary
        summary_row = con.execute(
            '''
            WITH match_rounds AS (
                SELECT match_id, SUM(rounds_won) AS total_rounds
                FROM "match_teams" GROUP BY match_id
            ),
            player_match AS (
                SELECT mp.match_id, mp.team, mp.kills, mp.deaths, mp.assists,
                       mp.score, mp.damage_made,
                       mr.total_rounds, mt.has_won
                FROM "match_players" mp
                JOIN match_rounds mr ON mr.match_id = mp.match_id
                LEFT JOIN "match_teams" mt
                    ON mt.match_id = mp.match_id AND mt.team = mp.team
                WHERE mp.puuid = ?
            )
            SELECT
                COUNT(*) AS games,
                SUM(CASE WHEN has_won THEN 1 ELSE 0 END) AS wins,
                SUM(CASE WHEN has_won = FALSE THEN 1 ELSE 0 END) AS losses,
                COALESCE(SUM(total_rounds), 0) AS rounds,
                AVG(kills)   AS avg_kills,
                AVG(deaths)  AS avg_deaths,
                AVG(assists) AS avg_assists,
                CASE WHEN SUM(total_rounds) > 0
                     THEN SUM(score) * 1.0 / SUM(total_rounds)
                     ELSE NULL END AS avg_acs,
                CASE WHEN SUM(total_rounds) > 0
                     THEN SUM(damage_made) * 1.0 / SUM(total_rounds)
                     ELSE NULL END AS avg_adr,
                AVG(kills - deaths) AS avg_plus_minus,
                CASE WHEN SUM(deaths) > 0
                     THEN SUM(kills) * 1.0 / SUM(deaths)
                     ELSE NULL END AS kd_ratio
            FROM player_match
            ''',
            [puuid],
        ).fetchone()
        agent_main_row = con.execute(
            'SELECT mode(agent) FROM "match_players" WHERE puuid = ?',
            [puuid],
        ).fetchone()
        agent_main = agent_main_row[0] if agent_main_row else None

        games = int(summary_row[0] or 0)
        wins = int(summary_row[1] or 0)
        losses = int(summary_row[2] or 0)
        summary = PlayerSummary(
            games=games,
            wins=wins,
            losses=losses,
            winrate_pct=_winrate(wins, games),
            rounds=int(summary_row[3] or 0),
            avg_kills=_round2(summary_row[4]),
            avg_deaths=_round2(summary_row[5]),
            avg_assists=_round2(summary_row[6]),
            avg_acs=_round2(summary_row[7]),
            avg_adr=_round2(summary_row[8]),
            avg_plus_minus=_round2(summary_row[9]),
            kd_ratio=_round2(summary_row[10]),
            agent_main=agent_main,
        )

        # ------------------------------------------------- team affiliations
        team_rows = con.execute(
            '''
            SELECT mt.premier_team_id,
                   ANY_VALUE(mt.premier_team_name) AS premier_team_name,
                   ANY_VALUE(mt.premier_team_tag)  AS premier_team_tag,
                   COUNT(DISTINCT mt.match_id) AS games,
                   SUM(CASE WHEN mt.has_won THEN 1 ELSE 0 END) AS wins,
                   MIN(m.game_start) AS first_seen,
                   MAX(m.game_start) AS last_seen
            FROM "match_players" mp
            JOIN "match_teams" mt
              ON mt.match_id = mp.match_id AND mt.team = mp.team
            LEFT JOIN "matches" m ON m.match_id = mp.match_id
            WHERE mp.puuid = ?
            GROUP BY mt.premier_team_id
            ORDER BY last_seen DESC NULLS LAST, games DESC
            ''',
            [puuid],
        ).fetchall()
        teams = [
            PlayerTeamAffiliation(
                premier_team_id=r[0],
                premier_team_name=r[1],
                premier_team_tag=r[2],
                games=int(r[3] or 0),
                wins=int(r[4] or 0),
                first_seen=_safe_int(r[5]),
                last_seen=_safe_int(r[6]),
            )
            for r in team_rows
        ]
        # The "current" team is the most recently played one
        current_team = teams[0] if teams else None

        # --------------------------------------------------------- agent stats
        total_games = games  # from summary computed above
        agent_rows = con.execute(
            '''
            WITH match_rounds AS (
                SELECT match_id, SUM(rounds_won) AS total_rounds
                FROM "match_teams" GROUP BY match_id
            )
            SELECT mp.agent,
                   COUNT(*) AS games,
                   COALESCE(SUM(mr.total_rounds), 0) AS rounds,
                   AVG(mp.kills)   AS avg_kills,
                   AVG(mp.deaths)  AS avg_deaths,
                   AVG(mp.assists) AS avg_assists,
                   CASE WHEN SUM(mr.total_rounds) > 0
                        THEN SUM(mp.score) * 1.0 / SUM(mr.total_rounds)
                        ELSE NULL END AS avg_acs,
                   CASE WHEN SUM(mr.total_rounds) > 0
                        THEN SUM(mp.damage_made) * 1.0 / SUM(mr.total_rounds)
                        ELSE NULL END AS avg_adr,
                   CASE WHEN SUM(mp.deaths) > 0
                        THEN SUM(mp.kills) * 1.0 / SUM(mp.deaths)
                        ELSE NULL END AS kd_ratio,
                   CASE WHEN SUM(mr.total_rounds) > 0
                        THEN SUM(mp.kills) * 1.0 / SUM(mr.total_rounds)
                        ELSE NULL END AS kpr,
                   CASE WHEN SUM(mr.total_rounds) > 0
                        THEN SUM(mp.assists) * 1.0 / SUM(mr.total_rounds)
                        ELSE NULL END AS apr,
                   CASE WHEN SUM(mr.total_rounds) > 0
                        THEN SUM(mp.first_kills) * 1.0 / SUM(mr.total_rounds)
                        ELSE NULL END AS fkpr,
                   CASE WHEN SUM(mr.total_rounds) > 0
                        THEN SUM(mp.first_deaths) * 1.0 / SUM(mr.total_rounds)
                        ELSE NULL END AS fdpr,
                   CASE WHEN SUM(mr.total_rounds) > 0
                        THEN SUM(COALESCE(mp.kast_rounds, 0)) * 100.0 / SUM(mr.total_rounds)
                        ELSE NULL END AS kast_pct,
                   COALESCE(SUM(mp.kills), 0)        AS total_kills,
                   COALESCE(SUM(mp.deaths), 0)       AS total_deaths,
                   COALESCE(SUM(mp.assists), 0)      AS total_assists,
                   COALESCE(SUM(mp.first_kills), 0)  AS total_first_kills,
                   COALESCE(SUM(mp.first_deaths), 0) AS total_first_deaths
            FROM "match_players" mp
            JOIN match_rounds mr ON mr.match_id = mp.match_id
            WHERE mp.puuid = ?
            GROUP BY mp.agent
            ORDER BY games DESC, mp.agent
            ''',
            [puuid],
        ).fetchall()
        agents = [
            PlayerAgentStat(
                agent=r[0],
                games=int(r[1] or 0),
                rounds=int(r[2] or 0),
                use_pct=round(100.0 * int(r[1] or 0) / total_games, 1) if total_games else 0.0,
                avg_kills=_round2(r[3]),
                avg_deaths=_round2(r[4]),
                avg_assists=_round2(r[5]),
                avg_acs=_round2(r[6]),
                avg_adr=_round2(r[7]),
                kd_ratio=_round2(r[8]),
                kpr=_round2(r[9]),
                apr=_round2(r[10]),
                fkpr=_round2(r[11]),
                fdpr=_round2(r[12]),
                kast_pct=_round2(r[13]),
                total_kills=int(r[14] or 0),
                total_deaths=int(r[15] or 0),
                total_assists=int(r[16] or 0),
                total_first_kills=int(r[17] or 0),
                total_first_deaths=int(r[18] or 0),
            )
            for r in agent_rows
        ]

        # ----------------------------------------------------------- map stats
        map_rows = con.execute(
            '''
            WITH match_rounds AS (
                SELECT match_id, SUM(rounds_won) AS total_rounds
                FROM "match_teams" GROUP BY match_id
            )
            SELECT m.map_name,
                   COUNT(*) AS games,
                   SUM(CASE WHEN mt.has_won THEN 1 ELSE 0 END) AS wins,
                   CASE WHEN SUM(mr.total_rounds) > 0
                        THEN SUM(mp.score) * 1.0 / SUM(mr.total_rounds)
                        ELSE NULL END AS avg_acs,
                   CASE WHEN SUM(mr.total_rounds) > 0
                        THEN SUM(mp.damage_made) * 1.0 / SUM(mr.total_rounds)
                        ELSE NULL END AS avg_adr
            FROM "match_players" mp
            JOIN "matches" m ON m.match_id = mp.match_id
            JOIN match_rounds mr ON mr.match_id = mp.match_id
            LEFT JOIN "match_teams" mt
                ON mt.match_id = mp.match_id AND mt.team = mp.team
            WHERE mp.puuid = ?
            GROUP BY m.map_name
            ORDER BY games DESC, m.map_name
            ''',
            [puuid],
        ).fetchall()
        maps = [
            PlayerMapStat(
                map_name=r[0],
                games=int(r[1] or 0),
                wins=int(r[2] or 0),
                winrate_pct=_winrate(int(r[2] or 0), int(r[1] or 0)),
                avg_acs=_round2(r[3]),
                avg_adr=_round2(r[4]),
            )
            for r in map_rows
        ]

        # ----------------------------------------------------- recent matches
        recent_rows = con.execute(
            '''
            WITH match_rounds AS (
                SELECT match_id, SUM(rounds_won) AS total_rounds
                FROM "match_teams" GROUP BY match_id
            )
            SELECT
                m.match_id, m.map_name, m.game_start,
                mp.team, mp.agent,
                mp.kills, mp.deaths, mp.assists,
                mp.score, mp.damage_made,
                mr.total_rounds,
                mt.has_won, mt.rounds_won, mt.rounds_lost,
                mt.premier_team_name, mt.premier_team_tag,
                opp.premier_team_name, opp.premier_team_tag
            FROM "match_players" mp
            JOIN "matches" m ON m.match_id = mp.match_id
            JOIN match_rounds mr ON mr.match_id = mp.match_id
            LEFT JOIN "match_teams" mt
                ON mt.match_id = mp.match_id AND mt.team = mp.team
            LEFT JOIN "match_teams" opp
                ON opp.match_id = mp.match_id AND opp.team != mp.team
            WHERE mp.puuid = ?
            ORDER BY m.game_start DESC NULLS LAST
            LIMIT ?
            ''',
            [puuid, recent_limit],
        ).fetchall()
        vods = load_vods()
        recent_matches: list[PlayerMatchEntry] = []
        for r in recent_rows:
            score = _safe_int(r[8])
            damage_made = _safe_int(r[9])
            total_rounds = _safe_int(r[10]) or 0
            kills = _safe_int(r[5])
            deaths = _safe_int(r[6])
            mid = str(r[0])
            recent_matches.append(
                PlayerMatchEntry(
                    match_id=mid,
                    vod_url=vods.get(mid),
                    map_name=r[1],
                    game_start=_safe_int(r[2]),
                    team=r[3],
                    agent=r[4],
                    kills=kills,
                    deaths=deaths,
                    assists=_safe_int(r[7]),
                    acs=(
                        round(score / total_rounds, 1)
                        if score is not None and total_rounds > 0
                        else None
                    ),
                    adr=(
                        round(damage_made / total_rounds, 1)
                        if damage_made is not None and total_rounds > 0
                        else None
                    ),
                    plus_minus=(
                        kills - deaths
                        if kills is not None and deaths is not None
                        else None
                    ),
                    has_won=bool(r[11]) if r[11] is not None else None,
                    rounds_won=_safe_int(r[12]),
                    rounds_lost=_safe_int(r[13]),
                    premier_team_name=r[14],
                    premier_team_tag=r[15],
                    opponent_name=r[16],
                    opponent_tag=r[17],
                )
            )

        return PlayerOverview(
            puuid=puuid,
            name=display_name,
            tag=display_tag,
            current_team=current_team,
            summary=summary,
            teams=teams,
            agents=agents,
            maps=maps,
            recent_matches=recent_matches,
        )


# ---------------------------------------------------------------------------
# Player bio — per-player markdown stored as flat files
# ---------------------------------------------------------------------------

_BIO_DIR = Path(__file__).resolve().parents[4] / "data" / "bios"


class _BioBody(BaseModel):
    content: str


@router.get("/{puuid}/bio", response_model=_BioBody)
def get_player_bio(puuid: str) -> _BioBody:
    """Return the saved bio for a player."""
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in puuid)
    path = _BIO_DIR / f"{safe}.md"
    if not path.exists():
        return _BioBody(content="")
    return _BioBody(content=path.read_text(encoding="utf-8"))


@router.put("/{puuid}/bio", response_model=_BioBody)
def put_player_bio(puuid: str, body: _BioBody) -> _BioBody:
    """Save (overwrite) the bio for a player."""
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in puuid)
    path = _BIO_DIR / f"{safe}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body.content, encoding="utf-8")
    return body
