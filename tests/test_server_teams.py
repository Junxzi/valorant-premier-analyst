"""Integration tests for the FastAPI team endpoint."""

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
    """Build a tiny DuckDB with two matches against two opponents."""
    db = tmp_path / "test.duckdb"

    matches = pd.DataFrame(
        [
            {"match_id": "m1", "map_name": "Ascent", "mode": "Premier",
             "queue": "premier", "game_start": 1700000000, "game_length": 1800},
            {"match_id": "m2", "map_name": "Bind", "mode": "Premier",
             "queue": "premier", "game_start": 1700001000, "game_length": 1500},
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
        ]
    )
    upsert_dataframe(teams, db, "match_teams", ["match_id", "team"])

    players = pd.DataFrame(
        [
            {"match_id": "m1", "puuid": "p1", "name": "Alice", "tag": "JP1",
             "team": "Red", "agent": "Jett", "kills": 20, "deaths": 10,
             "assists": 5, "score": 4500, "damage_made": 3000,
             "damage_received": 2200},
            {"match_id": "m2", "puuid": "p1", "name": "Alice", "tag": "JP1",
             "team": "Blue", "agent": "Jett", "kills": 15, "deaths": 12,
             "assists": 4, "score": 3700, "damage_made": 2800,
             "damage_received": 2300},
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


def test_health_reports_db_present(client: TestClient) -> None:
    res = client.get("/api/health")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ok"
    assert body["db_present"] is True


def test_team_endpoint_returns_record_and_recent_matches(client: TestClient) -> None:
    res = client.get("/api/teams/MyTeam/MTM")
    assert res.status_code == 200, res.text
    body = res.json()

    assert body["name"] == "MyTeam"
    assert body["tag"] == "MTM"
    assert body["record"] == {
        "games": 2,
        "wins": 1,
        "losses": 1,
        "winrate_pct": 50.0,
    }

    # Recent matches sorted desc by game_start (m2 newest)
    assert [m["match_id"] for m in body["recent_matches"]] == ["m2", "m1"]
    m2 = body["recent_matches"][0]
    assert m2["our_team"]["team"] == "Blue"
    assert m2["our_team"]["has_won"] is False
    assert m2["opponent"]["name"] == "Opp2"


def test_team_endpoint_includes_map_winrates(client: TestClient) -> None:
    body = client.get("/api/teams/MyTeam/MTM").json()
    maps = {m["map_name"]: m for m in body["map_winrates"]}
    assert maps["Ascent"]["games"] == 1
    assert maps["Ascent"]["wins"] == 1
    assert maps["Ascent"]["winrate_pct"] == 100.0
    assert maps["Bind"]["winrate_pct"] == 0.0


def test_team_endpoint_includes_roster(client: TestClient) -> None:
    body = client.get("/api/teams/MyTeam/MTM").json()
    roster = {r["name"]: r for r in body["roster"]}
    # Alice played on our team in both matches
    assert roster["Alice"]["games"] == 2
    assert roster["Alice"]["agent_main"] == "Jett"
    # Bob played only m1 (and never on our side in m2)
    assert roster["Bob"]["games"] == 1


def test_team_endpoint_404_for_unknown_team(client: TestClient) -> None:
    res = client.get("/api/teams/Ghost/GHST")
    assert res.status_code == 404


def test_team_endpoint_returns_503_when_db_missing(tmp_path: Path) -> None:
    missing = tmp_path / "nope.duckdb"
    app = create_app()
    app.dependency_overrides[db_path] = lambda: missing
    res = TestClient(app).get("/api/teams/MyTeam/MTM")
    assert res.status_code == 503


# ----------------------------- /matches -------------------------------------


def test_team_matches_endpoint_returns_full_history(client: TestClient) -> None:
    res = client.get("/api/teams/MyTeam/MTM/matches")
    assert res.status_code == 200, res.text
    body = res.json()

    assert body["name"] == "MyTeam"
    assert body["tag"] == "MTM"
    assert body["total"] == 2
    # Newest first (m2 was started later than m1)
    assert [m["match_id"] for m in body["matches"]] == ["m2", "m1"]
    # Same shape as the overview's recent_matches
    assert "our_team" in body["matches"][0]
    assert "opponent" in body["matches"][0]


def test_team_matches_endpoint_respects_limit(client: TestClient) -> None:
    res = client.get("/api/teams/MyTeam/MTM/matches?limit=1")
    assert res.status_code == 200
    body = res.json()
    assert body["total"] == 1
    assert [m["match_id"] for m in body["matches"]] == ["m2"]


def test_team_matches_endpoint_404_for_unknown_team(client: TestClient) -> None:
    res = client.get("/api/teams/Ghost/GHST/matches")
    assert res.status_code == 404


# ----------------------------- /stats ---------------------------------------


def test_team_stats_endpoint_aggregates_player_metrics(client: TestClient) -> None:
    res = client.get("/api/teams/MyTeam/MTM/stats")
    assert res.status_code == 200, res.text
    body = res.json()

    assert body["name"] == "MyTeam"
    assert body["total_games"] == 2
    # Sum of rounds_won across both teams in m1 (13+7=20) and m2 (13+11=24)
    assert body["total_rounds"] == 44

    players = {p["puuid"]: p for p in body["players"]}
    alice = players["p1"]
    assert alice["games"] == 2
    assert alice["rounds"] == 20 + 24
    # avg ACS = total score / total rounds = (4500+3700) / 44
    assert alice["avg_acs"] == round((4500 + 3700) / 44, 2)
    # avg ADR = total damage / total rounds
    assert alice["avg_adr"] == round((3000 + 2800) / 44, 2)
    # K/D ratio = total kills / total deaths
    assert alice["kd_ratio"] == round((20 + 15) / (10 + 12), 2)
    assert alice["agent_main"] == "Jett"

    bob = players["p2"]
    assert bob["games"] == 1
    assert bob["rounds"] == 20

    # Bob doesn't appear on our side in m2 (he's nowhere in m2 here), so
    # he's only counted once.
    assert bob["agent_main"] == "Sage"


def test_team_stats_endpoint_includes_agent_usage(client: TestClient) -> None:
    body = client.get("/api/teams/MyTeam/MTM/stats").json()
    usage = {a["agent"]: a for a in body["agent_usage"]}
    # Jett used in 2 of our team's 2 games -> 100% pick rate
    assert usage["Jett"]["games"] == 2
    assert usage["Jett"]["pick_rate_pct"] == 100.0
    # Sage used in 1 game -> 50% pick rate
    assert usage["Sage"]["games"] == 1
    assert usage["Sage"]["pick_rate_pct"] == 50.0


def test_team_stats_endpoint_404_for_unknown_team(client: TestClient) -> None:
    res = client.get("/api/teams/Ghost/GHST/stats")
    assert res.status_code == 404
