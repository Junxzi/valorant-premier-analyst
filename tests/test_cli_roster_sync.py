"""Tests for cmd_roster_sync, _scan_team_members_from_db and the resolver."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from valorant_analyst.api.henrik_client import HenrikAPIError
from valorant_analyst.cli import (
    _resolve_roster_entries_or_team,
    _scan_team_members_from_db,
    cmd_roster_sync,
)
from valorant_analyst.config import AppConfig, ConfigError
from valorant_analyst.storage.duckdb_store import upsert_dataframe
from valorant_analyst.storage.roster_history import (
    MemberRecord,
    RosterHistory,
    TeamHistory,
    load_roster_history,
    member_records,
    save_roster_history,
)

TEAM_NAME = "MyTeam"
TEAM_TAG = "MTM"


def _config(roster_entries: tuple[str, ...] = ()) -> AppConfig:
    return AppConfig(
        henrik_api_key="test-key",
        region="ap",
        name="Me",
        tag="JP1",
        match_size=10,
        roster_entries=roster_entries,
        roster_min_present=4,
        premier_team_name=TEAM_NAME,
        premier_team_tag=TEAM_TAG,
    )


def _seed_db_with_team(db_path: Path) -> None:
    """Build a tiny DuckDB where p-alice/p-bob played on TEAM_NAME's side."""
    teams = pd.DataFrame(
        [
            {
                "match_id": "m1",
                "team": "Red",
                "premier_team_name": TEAM_NAME,
                "premier_team_tag": TEAM_TAG,
            },
            {
                "match_id": "m1",
                "team": "Blue",
                "premier_team_name": "Other",
                "premier_team_tag": "OTH",
            },
        ]
    )
    upsert_dataframe(teams, db_path, "match_teams", ["match_id", "team"])

    players = pd.DataFrame(
        [
            {
                "match_id": "m1", "team": "Red", "puuid": "p-alice",
                "name": "Alice", "tag": "JP1",
            },
            {
                "match_id": "m1", "team": "Red", "puuid": "p-bob",
                "name": "Bob", "tag": "JP1",
            },
            {
                "match_id": "m1", "team": "Blue", "puuid": "p-enemy",
                "name": "Enemy", "tag": "X",
            },
        ]
    )
    upsert_dataframe(players, db_path, "match_players", ["match_id", "puuid"])


class _FakeClient:
    """Minimal stand-in for HenrikClient.get_premier_team."""

    def __init__(self, payload: dict[str, Any] | Exception) -> None:
        self._payload = payload

    def get_premier_team(self, name: str, tag: str) -> dict[str, Any]:
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload


@pytest.fixture()
def patch_client(monkeypatch: pytest.MonkeyPatch):
    """Helper to swap HenrikClient inside cli.cmd_roster_sync with a fake."""

    def _patch(payload: dict[str, Any] | Exception) -> None:
        def factory(api_key: str = "x", **kwargs: Any) -> _FakeClient:
            return _FakeClient(payload)

        monkeypatch.setattr("valorant_analyst.cli.HenrikClient", factory)

    return _patch


# ---------------------------------------------------------------------------
# _scan_team_members_from_db
# ---------------------------------------------------------------------------


def test_scan_db_returns_team_side_puuids(tmp_path: Path) -> None:
    db = tmp_path / "test.duckdb"
    _seed_db_with_team(db)

    entries = _scan_team_members_from_db(db, TEAM_NAME, TEAM_TAG)
    by_puuid = {e.puuid: e for e in entries}
    assert set(by_puuid) == {"p-alice", "p-bob"}
    assert by_puuid["p-alice"].name == "Alice"


def test_scan_db_returns_empty_when_db_missing(tmp_path: Path) -> None:
    assert _scan_team_members_from_db(tmp_path / "nope.db", TEAM_NAME, TEAM_TAG) == []


def test_scan_db_returns_empty_when_tables_missing(tmp_path: Path) -> None:
    db = tmp_path / "empty.duckdb"
    # create the file but no tables
    import duckdb

    duckdb.connect(str(db)).close()
    assert _scan_team_members_from_db(db, TEAM_NAME, TEAM_TAG) == []


# ---------------------------------------------------------------------------
# cmd_roster_sync
# ---------------------------------------------------------------------------


def test_cmd_roster_sync_persists_api_members(
    tmp_path: Path, patch_client
) -> None:
    history_path = tmp_path / "rh.json"
    db = tmp_path / "test.duckdb"
    patch_client(
        {
            "data": {
                "name": TEAM_NAME, "tag": TEAM_TAG,
                "member": [
                    {"puuid": "p-alice", "name": "Alice", "tag": "JP1"},
                    {"puuid": "p-bob", "name": "Bob", "tag": "JP1"},
                ],
            }
        }
    )

    cmd_roster_sync(_config(), db, history_path, scan_db=False)

    assert history_path.exists()
    history = load_roster_history(history_path)
    records = member_records(history, TEAM_NAME, TEAM_TAG)
    assert {r.puuid for r in records} == {"p-alice", "p-bob"}
    assert all(r.is_current for r in records)
    assert all(r.source == "api" for r in records)


def test_cmd_roster_sync_marks_departed_on_subsequent_call(
    tmp_path: Path, patch_client
) -> None:
    history_path = tmp_path / "rh.json"
    db = tmp_path / "test.duckdb"

    patch_client(
        {
            "data": {
                "member": [
                    {"puuid": "p-alice", "name": "Alice", "tag": "JP1"},
                    {"puuid": "p-bob", "name": "Bob", "tag": "JP1"},
                ]
            }
        }
    )
    cmd_roster_sync(_config(), db, history_path, scan_db=False)

    # Second call: Bob is gone from the API, Carol joined.
    patch_client(
        {
            "data": {
                "member": [
                    {"puuid": "p-alice", "name": "Alice", "tag": "JP1"},
                    {"puuid": "p-carol", "name": "Carol", "tag": "JP1"},
                ]
            }
        }
    )
    cmd_roster_sync(_config(), db, history_path, scan_db=False)

    history = load_roster_history(history_path)
    records = {r.puuid: r for r in member_records(history, TEAM_NAME, TEAM_TAG)}
    assert records["p-alice"].is_current is True
    assert records["p-bob"].is_current is False  # departed but kept
    assert records["p-carol"].is_current is True
    assert records["p-carol"].source == "api"


def test_cmd_roster_sync_empty_api_does_not_mark_inactive(
    tmp_path: Path, patch_client
) -> None:
    """An empty `data.member` from the API is common right after enrollment.

    We should NOT flip everyone in the history file to is_current=False just
    because the API returned nothing.
    """
    history_path = tmp_path / "rh.json"
    db = tmp_path / "test.duckdb"
    save_roster_history(
        RosterHistory(
            teams={
                f"{TEAM_NAME}#{TEAM_TAG}": TeamHistory(
                    last_synced_at=None,
                    members=[
                        MemberRecord(
                            puuid="p-alice", name="Alice", tag="JP1",
                            first_seen_at="2025-01-01T00:00:00+00:00",
                            last_seen_at="2025-01-01T00:00:00+00:00",
                            is_current=True, source="api",
                        )
                    ],
                )
            }
        ),
        history_path,
    )
    patch_client({"data": {"member": []}})

    cmd_roster_sync(_config(), db, history_path, scan_db=False)

    rec = member_records(load_roster_history(history_path), TEAM_NAME, TEAM_TAG)[0]
    assert rec.is_current is True


def test_cmd_roster_sync_scan_db_recovers_departed(
    tmp_path: Path, patch_client
) -> None:
    history_path = tmp_path / "rh.json"
    db = tmp_path / "test.duckdb"
    _seed_db_with_team(db)

    # API only knows Alice; DuckDB knows Alice + Bob.
    patch_client(
        {
            "data": {
                "member": [{"puuid": "p-alice", "name": "Alice", "tag": "JP1"}]
            }
        }
    )

    cmd_roster_sync(_config(), db, history_path, scan_db=True)

    records = {
        r.puuid: r
        for r in member_records(load_roster_history(history_path), TEAM_NAME, TEAM_TAG)
    }
    assert set(records) == {"p-alice", "p-bob"}
    assert records["p-alice"].source == "api"
    # Bob came from the DB scan and should be present but is_current=False
    # (the API said only Alice is active, and the DB scan was additive).
    assert records["p-bob"].source == "match_players"
    assert records["p-bob"].is_current is False


def test_cmd_roster_sync_scan_db_promotes_when_api_returned_nothing(
    tmp_path: Path, patch_client
) -> None:
    """When the API returns 0 members (common right after enrollment), the DB
    scan is the only signal we have for who is on the roster — treat newly
    discovered DB members as is_current=True so the dashboard isn't empty."""
    history_path = tmp_path / "rh.json"
    db = tmp_path / "test.duckdb"
    _seed_db_with_team(db)

    patch_client({"data": {"member": []}})  # API returned nothing

    cmd_roster_sync(_config(), db, history_path, scan_db=True)

    records = {
        r.puuid: r
        for r in member_records(load_roster_history(history_path), TEAM_NAME, TEAM_TAG)
    }
    assert set(records) == {"p-alice", "p-bob"}
    for rec in records.values():
        assert rec.is_current is True
        assert rec.source == "match_players"


def test_cmd_roster_sync_continues_when_api_errors(
    tmp_path: Path, patch_client
) -> None:
    history_path = tmp_path / "rh.json"
    db = tmp_path / "test.duckdb"
    _seed_db_with_team(db)

    patch_client(HenrikAPIError("boom", status_code=500))

    cmd_roster_sync(_config(), db, history_path, scan_db=True)

    # Even though the API failed, the DB scan still populated the history.
    records = member_records(load_roster_history(history_path), TEAM_NAME, TEAM_TAG)
    puuids = {r.puuid for r in records}
    assert "p-alice" in puuids
    assert "p-bob" in puuids


# ---------------------------------------------------------------------------
# _resolve_roster_entries_or_team
# ---------------------------------------------------------------------------


def test_resolver_env_takes_precedence_in_auto_mode(
    tmp_path: Path, patch_client
) -> None:
    history_path = tmp_path / "rh.json"
    save_roster_history(
        RosterHistory(
            teams={
                f"{TEAM_NAME}#{TEAM_TAG}": TeamHistory(
                    last_synced_at=None,
                    members=[
                        MemberRecord(
                            puuid="p-history", name="HistOnly", tag="JP1",
                            first_seen_at="2025-01-01T00:00:00+00:00",
                            last_seen_at="2025-01-01T00:00:00+00:00",
                            is_current=True, source="api",
                        )
                    ],
                )
            }
        ),
        history_path,
    )
    config = _config(roster_entries=("EnvOnly#JP1",))
    entries = _resolve_roster_entries_or_team(config, history_path, source="auto")
    assert [e.raw for e in entries] == ["EnvOnly#JP1"]


def test_resolver_falls_back_to_history_when_env_empty(tmp_path: Path) -> None:
    history_path = tmp_path / "rh.json"
    save_roster_history(
        RosterHistory(
            teams={
                f"{TEAM_NAME}#{TEAM_TAG}": TeamHistory(
                    last_synced_at=None,
                    members=[
                        MemberRecord(
                            puuid="p-alice", name="Alice", tag="JP1",
                            first_seen_at="2025-01-01T00:00:00+00:00",
                            last_seen_at="2025-01-01T00:00:00+00:00",
                            is_current=True, source="api",
                        ),
                        MemberRecord(
                            puuid="p-bob", name="Bob", tag="JP1",
                            first_seen_at="2025-01-01T00:00:00+00:00",
                            last_seen_at="2025-01-01T00:00:00+00:00",
                            is_current=False, source="api",
                        ),
                    ],
                )
            }
        ),
        history_path,
    )
    entries = _resolve_roster_entries_or_team(_config(), history_path, source="auto")
    # union (current + departed)
    assert {e.puuid for e in entries} == {"p-alice", "p-bob"}


def test_resolver_current_source_returns_only_active(tmp_path: Path) -> None:
    history_path = tmp_path / "rh.json"
    save_roster_history(
        RosterHistory(
            teams={
                f"{TEAM_NAME}#{TEAM_TAG}": TeamHistory(
                    last_synced_at=None,
                    members=[
                        MemberRecord(
                            puuid="p-alice", name="Alice", tag="JP1",
                            first_seen_at="2025-01-01T00:00:00+00:00",
                            last_seen_at="2025-01-01T00:00:00+00:00",
                            is_current=True, source="api",
                        ),
                        MemberRecord(
                            puuid="p-bob", name="Bob", tag="JP1",
                            first_seen_at="2025-01-01T00:00:00+00:00",
                            last_seen_at="2025-01-01T00:00:00+00:00",
                            is_current=False, source="api",
                        ),
                    ],
                )
            }
        ),
        history_path,
    )
    entries = _resolve_roster_entries_or_team(
        _config(), history_path, source="current"
    )
    assert {e.puuid for e in entries} == {"p-alice"}


def test_resolver_env_source_requires_premier_roster(tmp_path: Path) -> None:
    with pytest.raises(ConfigError):
        _resolve_roster_entries_or_team(_config(), tmp_path / "rh.json", source="env")


def test_resolver_history_source_raises_when_empty(tmp_path: Path) -> None:
    with pytest.raises(ConfigError):
        _resolve_roster_entries_or_team(
            _config(), tmp_path / "missing.json", source="history"
        )
