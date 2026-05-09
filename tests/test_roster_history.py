"""Tests for storage.roster_history persistence and merge logic."""

from __future__ import annotations

import json
from pathlib import Path

from valorant_analyst.analysis.roster import RosterEntry
from valorant_analyst.storage.roster_history import (
    MemberRecord,
    RosterHistory,
    TeamHistory,
    all_members,
    current_members,
    load_roster_history,
    member_records,
    merge_team_members,
    save_roster_history,
)

TEAM_NAME = "MyTeam"
TEAM_TAG = "MTM"


def _entry(name: str, tag: str = "JP1", puuid: str | None = None) -> RosterEntry:
    raw = f"{name}#{tag}" if name and tag else (puuid or "")
    return RosterEntry(raw=raw, name=name, tag=tag, puuid=puuid)


def test_load_returns_empty_when_file_missing(tmp_path: Path) -> None:
    history = load_roster_history(tmp_path / "nope.json")
    assert isinstance(history, RosterHistory)
    assert history.teams == {}


def test_load_tolerates_corrupt_json(tmp_path: Path) -> None:
    path = tmp_path / "broken.json"
    path.write_text("{ not json", encoding="utf-8")
    history = load_roster_history(path)
    assert history.teams == {}


def test_save_then_load_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "rh.json"
    history = RosterHistory(
        teams={
            "MyTeam#MTM": TeamHistory(
                last_synced_at="2025-01-01T00:00:00+00:00",
                members=[
                    MemberRecord(
                        puuid="p-alice",
                        name="Alice",
                        tag="JP1",
                        first_seen_at="2025-01-01T00:00:00+00:00",
                        last_seen_at="2025-01-01T00:00:00+00:00",
                        is_current=True,
                        source="api",
                    )
                ],
            )
        }
    )
    save_roster_history(history, path)

    raw = json.loads(path.read_text(encoding="utf-8"))
    assert "teams" in raw
    assert "MyTeam#MTM" in raw["teams"]

    reloaded = load_roster_history(path)
    records = member_records(reloaded, TEAM_NAME, TEAM_TAG)
    assert len(records) == 1
    assert records[0].puuid == "p-alice"
    assert records[0].is_current is True


def test_merge_inserts_new_members_with_first_seen(tmp_path: Path) -> None:
    history = RosterHistory()
    report = merge_team_members(
        history,
        TEAM_NAME,
        TEAM_TAG,
        [_entry("Alice", puuid="p-a"), _entry("Bob", puuid="p-b")],
        source="api",
        now_iso="2025-01-01T00:00:00+00:00",
    )
    assert len(report.added) == 2
    records = member_records(history, TEAM_NAME, TEAM_TAG)
    assert {r.puuid for r in records} == {"p-a", "p-b"}
    for r in records:
        assert r.first_seen_at == "2025-01-01T00:00:00+00:00"
        assert r.last_seen_at == "2025-01-01T00:00:00+00:00"
        assert r.is_current
        assert r.source == "api"


def test_merge_existing_member_updates_last_seen(tmp_path: Path) -> None:
    history = RosterHistory()
    merge_team_members(
        history,
        TEAM_NAME,
        TEAM_TAG,
        [_entry("Alice", puuid="p-a")],
        source="api",
        now_iso="2025-01-01T00:00:00+00:00",
    )
    report = merge_team_members(
        history,
        TEAM_NAME,
        TEAM_TAG,
        [_entry("Alice", puuid="p-a")],
        source="api",
        now_iso="2025-02-01T00:00:00+00:00",
    )
    assert len(report.added) == 0
    assert len(report.updated) == 1
    rec = member_records(history, TEAM_NAME, TEAM_TAG)[0]
    assert rec.first_seen_at == "2025-01-01T00:00:00+00:00"
    assert rec.last_seen_at == "2025-02-01T00:00:00+00:00"


def test_merge_marks_missing_member_as_departed(tmp_path: Path) -> None:
    history = RosterHistory()
    merge_team_members(
        history,
        TEAM_NAME,
        TEAM_TAG,
        [_entry("Alice", puuid="p-a"), _entry("Bob", puuid="p-b")],
        source="api",
        now_iso="2025-01-01T00:00:00+00:00",
    )
    # Bob no longer on the team
    report = merge_team_members(
        history,
        TEAM_NAME,
        TEAM_TAG,
        [_entry("Alice", puuid="p-a")],
        source="api",
        now_iso="2025-02-01T00:00:00+00:00",
    )
    assert [r.puuid for r in report.departed] == ["p-b"]
    records = {r.puuid: r for r in member_records(history, TEAM_NAME, TEAM_TAG)}
    assert records["p-a"].is_current is True
    assert records["p-b"].is_current is False
    # Departed members are kept (not deleted)
    assert "Bob" in {r.name for r in records.values()}


def test_merge_rejoin_flips_is_current_back(tmp_path: Path) -> None:
    history = RosterHistory()
    merge_team_members(
        history,
        TEAM_NAME,
        TEAM_TAG,
        [_entry("Alice", puuid="p-a"), _entry("Bob", puuid="p-b")],
        source="api",
        now_iso="2025-01-01T00:00:00+00:00",
    )
    merge_team_members(
        history,
        TEAM_NAME,
        TEAM_TAG,
        [_entry("Alice", puuid="p-a")],
        source="api",
        now_iso="2025-02-01T00:00:00+00:00",
    )
    report = merge_team_members(
        history,
        TEAM_NAME,
        TEAM_TAG,
        [_entry("Alice", puuid="p-a"), _entry("Bob", puuid="p-b")],
        source="api",
        now_iso="2025-03-01T00:00:00+00:00",
    )
    assert [r.puuid for r in report.rejoined] == ["p-b"]
    records = {r.puuid: r for r in member_records(history, TEAM_NAME, TEAM_TAG)}
    assert records["p-b"].is_current is True
    assert records["p-b"].first_seen_at == "2025-01-01T00:00:00+00:00"
    assert records["p-b"].last_seen_at == "2025-03-01T00:00:00+00:00"


def test_merge_with_mark_missing_inactive_false_is_additive(tmp_path: Path) -> None:
    history = RosterHistory()
    merge_team_members(
        history,
        TEAM_NAME,
        TEAM_TAG,
        [_entry("Alice", puuid="p-a"), _entry("Bob", puuid="p-b")],
        source="api",
        now_iso="2025-01-01T00:00:00+00:00",
    )
    # DB scan only sees Alice but should NOT mark Bob as departed.
    merge_team_members(
        history,
        TEAM_NAME,
        TEAM_TAG,
        [_entry("Alice", puuid="p-a")],
        source="match_players",
        mark_missing_inactive=False,
        now_iso="2025-01-15T00:00:00+00:00",
    )
    bob = next(
        r for r in member_records(history, TEAM_NAME, TEAM_TAG) if r.puuid == "p-b"
    )
    assert bob.is_current is True


def test_merge_matches_by_riot_id_when_puuid_missing(tmp_path: Path) -> None:
    history = RosterHistory()
    # First insert with puuid only.
    merge_team_members(
        history,
        TEAM_NAME,
        TEAM_TAG,
        [_entry("Alice", puuid="p-a")],
        source="api",
        now_iso="2025-01-01T00:00:00+00:00",
    )
    # Second insert with same Riot ID but no puuid (e.g. PREMIER_ROSTER entry).
    report = merge_team_members(
        history,
        TEAM_NAME,
        TEAM_TAG,
        [RosterEntry(raw="Alice#JP1", name="Alice", tag="JP1", puuid=None)],
        source="manual",
        now_iso="2025-02-01T00:00:00+00:00",
    )
    assert len(report.added) == 0
    assert len(report.updated) == 1
    rec = member_records(history, TEAM_NAME, TEAM_TAG)[0]
    assert rec.puuid == "p-a"  # not lost


def test_merge_backfills_missing_identity_fields(tmp_path: Path) -> None:
    history = RosterHistory()
    # Seed with a riot-id-only record (e.g. from PREMIER_ROSTER).
    merge_team_members(
        history,
        TEAM_NAME,
        TEAM_TAG,
        [RosterEntry(raw="Alice#JP1", name="Alice", tag="JP1", puuid=None)],
        source="manual",
        now_iso="2025-01-01T00:00:00+00:00",
    )
    # API later returns the puuid for the same Riot ID.
    merge_team_members(
        history,
        TEAM_NAME,
        TEAM_TAG,
        [_entry("Alice", puuid="p-a")],
        source="api",
        now_iso="2025-02-01T00:00:00+00:00",
    )
    rec = member_records(history, TEAM_NAME, TEAM_TAG)[0]
    assert rec.puuid == "p-a"
    assert rec.name == "Alice"
    assert rec.tag == "JP1"


def test_current_and_all_members_views(tmp_path: Path) -> None:
    history = RosterHistory()
    merge_team_members(
        history,
        TEAM_NAME,
        TEAM_TAG,
        [_entry("Alice", puuid="p-a"), _entry("Bob", puuid="p-b")],
        source="api",
        now_iso="2025-01-01T00:00:00+00:00",
    )
    merge_team_members(
        history,
        TEAM_NAME,
        TEAM_TAG,
        [_entry("Alice", puuid="p-a")],
        source="api",
        now_iso="2025-02-01T00:00:00+00:00",
    )

    current = current_members(history, TEAM_NAME, TEAM_TAG)
    assert [e.puuid for e in current] == ["p-a"]

    everyone = all_members(history, TEAM_NAME, TEAM_TAG)
    assert {e.puuid for e in everyone} == {"p-a", "p-b"}


def test_unknown_team_returns_empty_lists(tmp_path: Path) -> None:
    history = RosterHistory()
    assert current_members(history, "Nope", "X") == []
    assert all_members(history, "Nope", "X") == []
    assert member_records(history, "Nope", "X") == []
