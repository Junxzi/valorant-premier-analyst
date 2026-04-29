"""Integration tests for the FastAPI player endpoint."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from valorant_analyst.server.app import create_app
from valorant_analyst.server.deps import db_path
from valorant_analyst.storage.duckdb_store import upsert_dataframe


@pytest.fixture()
def seeded_db(tmp_path: Path) -> Path:
    """Seed two matches across two different Premier teams for the same player.

    Player ``p1`` plays:
    - m1 on team MyTeam (Red side, won 13-7) — Jett, 20/10/5 score=4500 dmg=3000
    - m2 on team MyTeam (Blue side, lost 11-13) — Jett, 15/12/4 score=3700 dmg=2800
    - m3 on a different team OldTeam (Red side, won 13-9) — Reyna,
      16/9/3 score=4000 dmg=2600

    So aggregated:
    - 3 games / 2W-1L
    - 2 distinct teams (MyTeam current, OldTeam past)
    - 2 distinct agents (Jett 2, Reyna 1)
    - 2 distinct maps (Ascent x2 — m1+m3, Bind x1 — m2)
    """
    db = tmp_path / "test.duckdb"

    matches = pd.DataFrame(
        [
            {"match_id": "m1", "map_name": "Ascent", "mode": "Premier",
             "queue": "premier", "game_start": 1700000000, "game_length": 1800},
            {"match_id": "m2", "map_name": "Bind", "mode": "Premier",
             "queue": "premier", "game_start": 1700001000, "game_length": 1500},
            {"match_id": "m3", "map_name": "Ascent", "mode": "Premier",
             "queue": "premier", "game_start": 1690000000, "game_length": 1700},
        ]
    )
    upsert_dataframe(matches, db, "matches", ["match_id"])

    teams = pd.DataFrame(
        [
            {"match_id": "m1", "team": "Red", "has_won": True,
             "rounds_won": 13, "rounds_lost": 7,
             "premier_team_id": "us", "premier_team_name": "MyTeam",
             "premier_team_tag": "MTM"},
            {"match_id": "m1", "team": "Blue", "has_won": False,
             "rounds_won": 7, "rounds_lost": 13,
             "premier_team_id": "op1", "premier_team_name": "Opp1",
             "premier_team_tag": "OP1"},
            {"match_id": "m2", "team": "Blue", "has_won": False,
             "rounds_won": 11, "rounds_lost": 13,
             "premier_team_id": "us", "premier_team_name": "MyTeam",
             "premier_team_tag": "MTM"},
            {"match_id": "m2", "team": "Red", "has_won": True,
             "rounds_won": 13, "rounds_lost": 11,
             "premier_team_id": "op2", "premier_team_name": "Opp2",
             "premier_team_tag": "OP2"},
            {"match_id": "m3", "team": "Red", "has_won": True,
             "rounds_won": 13, "rounds_lost": 9,
             "premier_team_id": "old", "premier_team_name": "OldTeam",
             "premier_team_tag": "OLD"},
            {"match_id": "m3", "team": "Blue", "has_won": False,
             "rounds_won": 9, "rounds_lost": 13,
             "premier_team_id": "op3", "premier_team_name": "Opp3",
             "premier_team_tag": "OP3"},
        ]
    )
    upsert_dataframe(teams, db, "match_teams", ["match_id", "team"])

    players = pd.DataFrame(
        [
            {"match_id": "m1", "puuid": "p1", "name": "Alice", "tag": "JP1",
             "team": "Red", "agent": "Jett", "kills": 20, "deaths": 10,
             "assists": 5, "score": 4500, "damage_made": 3000,
             "damage_received": 2200},
            {"match_id": "m2", "puuid": "p1", "name": "", "tag": "",
             "team": "Blue", "agent": "Jett", "kills": 15, "deaths": 12,
             "assists": 4, "score": 3700, "damage_made": 2800,
             "damage_received": 2300},
            {"match_id": "m3", "puuid": "p1", "name": "Alice", "tag": "JP1",
             "team": "Red", "agent": "Reyna", "kills": 16, "deaths": 9,
             "assists": 3, "score": 4000, "damage_made": 2600,
             "damage_received": 2000},
            # A second player so we have something to skip in aggregations
            {"match_id": "m1", "puuid": "p2", "name": "Bob", "tag": "JP1",
             "team": "Red", "agent": "Sage", "kills": 10, "deaths": 12,
             "assists": 8, "score": 3000, "damage_made": 1900,
             "damage_received": 2100},
        ]
    )
    upsert_dataframe(players, db, "match_players", ["match_id", "puuid"])

    return db


@pytest.fixture()
def client(seeded_db: Path) -> TestClient:
    app = create_app()
    app.dependency_overrides[db_path] = lambda: seeded_db
    return TestClient(app)


def test_player_endpoint_returns_summary(client: TestClient) -> None:
    res = client.get("/api/players/p1")
    assert res.status_code == 200, res.text
    body = res.json()

    assert body["puuid"] == "p1"
    # Anonymized in m2, but we should backfill from m1/m3
    assert body["name"] == "Alice"
    assert body["tag"] == "JP1"

    s = body["summary"]
    assert s["games"] == 3
    assert s["wins"] == 2
    assert s["losses"] == 1
    assert s["winrate_pct"] == round(100 * 2 / 3, 1)
    # Total rounds across the 3 matches = 20 + 24 + 22 = 66
    assert s["rounds"] == 66
    # K/D = total kills / total deaths
    assert s["kd_ratio"] == round((20 + 15 + 16) / (10 + 12 + 9), 2)
    # ACS = total score / total rounds
    assert s["avg_acs"] == round((4500 + 3700 + 4000) / 66, 2)
    # Most-played agent is Jett (2 of 3 matches)
    assert s["agent_main"] == "Jett"


def test_player_endpoint_lists_team_affiliations(client: TestClient) -> None:
    body = client.get("/api/players/p1").json()
    teams = {t["premier_team_id"]: t for t in body["teams"]}
    assert teams["us"]["games"] == 2
    assert teams["us"]["wins"] == 1
    assert teams["old"]["games"] == 1
    assert teams["old"]["wins"] == 1
    # Most recent appearance was on MyTeam (m2 > m3 by game_start)
    assert body["current_team"]["premier_team_id"] == "us"


def test_player_endpoint_includes_agents_and_maps(client: TestClient) -> None:
    body = client.get("/api/players/p1").json()
    agents = {a["agent"]: a for a in body["agents"]}
    assert agents["Jett"]["games"] == 2
    assert agents["Reyna"]["games"] == 1

    maps = {m["map_name"]: m for m in body["maps"]}
    assert maps["Ascent"]["games"] == 2
    assert maps["Ascent"]["wins"] == 2
    assert maps["Ascent"]["winrate_pct"] == 100.0
    assert maps["Bind"]["games"] == 1


def test_player_endpoint_recent_matches_sorted_desc(client: TestClient) -> None:
    body = client.get("/api/players/p1").json()
    # Newest first by game_start: m2, m1, m3
    ids = [m["match_id"] for m in body["recent_matches"]]
    assert ids == ["m2", "m1", "m3"]
    m2 = body["recent_matches"][0]
    assert m2["agent"] == "Jett"
    assert m2["team"] == "Blue"
    assert m2["has_won"] is False
    assert m2["premier_team_name"] == "MyTeam"
    assert m2["opponent_name"] == "Opp2"
    # ACS = score / total_rounds for the match
    assert m2["acs"] == round(3700 / 24, 1)


def test_player_endpoint_404_for_unknown_puuid(client: TestClient) -> None:
    res = client.get("/api/players/ghost")
    assert res.status_code == 404
