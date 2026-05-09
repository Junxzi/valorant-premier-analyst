"""Tests for the team strategy endpoint — covers the notes-saving fix."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from valorant_analyst.server.app import create_app
from valorant_analyst.server.routes import teams as teams_route


@pytest.fixture()
def strategy_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """Spin up the API with the strategy directory redirected to a tmp dir."""
    sandbox = tmp_path / "strategy"
    sandbox.mkdir()
    monkeypatch.setattr(teams_route, "_STRATEGY_DIR", sandbox)
    return TestClient(create_app())


def test_strategy_get_returns_empty_when_no_files(strategy_client: TestClient) -> None:
    res = strategy_client.get("/api/teams/MyTeam/MTM/strategy")
    assert res.status_code == 200
    body = res.json()
    assert body == {"data": {}, "notes": {}}


def test_strategy_put_then_get_round_trips_data_and_notes(
    strategy_client: TestClient,
) -> None:
    payload = {
        "data": {"Ascent": {"Alice": "Jett", "Bob": "Sage"}},
        "notes": {"Ascent": "# Default plan\n- A site exec"},
    }
    put = strategy_client.put("/api/teams/MyTeam/MTM/strategy", json=payload)
    assert put.status_code == 200, put.text
    assert put.json() == payload

    got = strategy_client.get("/api/teams/MyTeam/MTM/strategy")
    assert got.status_code == 200
    assert got.json() == payload


def test_strategy_notes_persist_to_sibling_file(
    strategy_client: TestClient, tmp_path: Path
) -> None:
    strategy_client.put(
        "/api/teams/MyTeam/MTM/strategy",
        json={"data": {"Ascent": {}}, "notes": {"Ascent": "note body"}},
    )
    strategy_dir: Path = teams_route._STRATEGY_DIR
    assert (strategy_dir / "MyTeam__MTM.json").exists()
    notes_file = strategy_dir / "MyTeam__MTM.notes.json"
    assert notes_file.exists()
    assert json.loads(notes_file.read_text(encoding="utf-8")) == {
        "Ascent": "note body"
    }


def test_strategy_clearing_notes_removes_sibling_file(
    strategy_client: TestClient,
) -> None:
    # Seed with a note
    strategy_client.put(
        "/api/teams/MyTeam/MTM/strategy",
        json={"data": {"Ascent": {}}, "notes": {"Ascent": "first"}},
    )
    notes_file = teams_route._STRATEGY_DIR / "MyTeam__MTM.notes.json"
    assert notes_file.exists()

    # Clear notes — the sibling file should disappear so future GETs return {}
    strategy_client.put(
        "/api/teams/MyTeam/MTM/strategy",
        json={"data": {"Ascent": {}}, "notes": {}},
    )
    assert not notes_file.exists()

    res = strategy_client.get("/api/teams/MyTeam/MTM/strategy")
    assert res.json()["notes"] == {}


def test_strategy_handles_special_chars_in_team_name(
    strategy_client: TestClient,
) -> None:
    """Japanese / non-ascii team names must save without filesystem errors."""
    payload = {"data": {"Lotus": {"へい": "Yoru"}}, "notes": {}}
    res = strategy_client.put(
        "/api/teams/120pingがIGL/120/strategy",
        json=payload,
    )
    assert res.status_code == 200, res.text
    got = strategy_client.get("/api/teams/120pingがIGL/120/strategy")
    assert got.json()["data"] == payload["data"]


def test_strategy_get_tolerates_corrupt_json(
    strategy_client: TestClient,
) -> None:
    bad = teams_route._STRATEGY_DIR / "Bad__BAD.json"
    bad.write_text("{ not json", encoding="utf-8")
    res = strategy_client.get("/api/teams/Bad/BAD/strategy")
    assert res.status_code == 200
    assert res.json() == {"data": {}, "notes": {}}
