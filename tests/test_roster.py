"""Tests for analysis.roster (parsing, discovery, filters, premier helpers)."""

from __future__ import annotations

import pandas as pd

from valorant_analyst.analysis.roster import (
    DISCOVER_COLUMNS,
    ROSTER_MATCH_COLUMNS,
    RosterEntry,
    discover_teammates,
    filter_payload_by_roster,
    find_user_puuid,
    league_match_ids,
    matches_with_roster,
    members_from_premier_team,
    parse_roster_entries,
    resolve_roster_puuids,
)


def _players_df() -> pd.DataFrame:
    rows = [
        # match m1, team Red: Alice, Bob, Charlie
        {"match_id": "m1", "team": "Red", "puuid": "p-alice",
         "name": "Alice", "tag": "JP1", "agent": "Jett", "kills": 20,
         "deaths": 10, "assists": 5, "score": 4500, "damage_made": 3000,
         "damage_received": 2000},
        {"match_id": "m1", "team": "Red", "puuid": "p-bob",
         "name": "Bob", "tag": "JP1", "agent": "Sage", "kills": 12,
         "deaths": 11, "assists": 8, "score": 3000, "damage_made": 2200,
         "damage_received": 2100},
        {"match_id": "m1", "team": "Red", "puuid": "p-charlie",
         "name": "Charlie", "tag": "JP1", "agent": "Omen", "kills": 14,
         "deaths": 9, "assists": 6, "score": 3400, "damage_made": 2400,
         "damage_received": 1900},
        {"match_id": "m1", "team": "Blue", "puuid": "p-enemy1",
         "name": "Enemy1", "tag": "AAA", "agent": "Reyna", "kills": 18,
         "deaths": 15, "assists": 2, "score": 4000, "damage_made": 2800,
         "damage_received": 2700},
        # match m2, team Blue: Alice, Bob (only 2 → not enough for min=3)
        {"match_id": "m2", "team": "Blue", "puuid": "p-alice",
         "name": "Alice", "tag": "JP1", "agent": "Jett", "kills": 22,
         "deaths": 13, "assists": 4, "score": 4800, "damage_made": 3100,
         "damage_received": 2300},
        {"match_id": "m2", "team": "Blue", "puuid": "p-bob",
         "name": "Bob", "tag": "JP1", "agent": "Sage", "kills": 9,
         "deaths": 12, "assists": 11, "score": 2700, "damage_made": 1800,
         "damage_received": 2100},
        {"match_id": "m2", "team": "Red", "puuid": "p-randomA",
         "name": "RandomA", "tag": "X", "agent": "Phoenix", "kills": 5,
         "deaths": 8, "assists": 3, "score": 1500, "damage_made": 700,
         "damage_received": 1100},
    ]
    return pd.DataFrame(rows)


def test_parse_roster_entries_distinguishes_riot_id_and_puuid() -> None:
    parsed = parse_roster_entries(
        ["Alice#JP1", "  Bob#JP1  ", "abcdef-puuid", "", "  ", "no-tag#"]
    )
    assert len(parsed) == 3
    assert parsed[0] == RosterEntry(
        raw="Alice#JP1", name="Alice", tag="JP1", puuid=None
    )
    assert parsed[1] == RosterEntry(
        raw="Bob#JP1", name="Bob", tag="JP1", puuid=None
    )
    assert parsed[2].puuid == "abcdef-puuid"
    assert parsed[2].is_puuid_only


def test_resolve_roster_puuids_uses_match_players() -> None:
    entries = parse_roster_entries(["Alice#JP1", "p-charlie", "Ghost#JP1"])
    resolved, unresolved = resolve_roster_puuids(entries, _players_df())

    assert "p-alice" in resolved
    assert "p-charlie" in resolved
    assert len(unresolved) == 1
    assert unresolved[0].raw == "Ghost#JP1"


def test_resolve_roster_puuids_handles_empty_dataframe() -> None:
    entries = parse_roster_entries(["Alice#JP1", "p-x"])
    resolved, unresolved = resolve_roster_puuids(entries, pd.DataFrame())

    assert resolved == {"p-x"}
    assert [e.raw for e in unresolved] == ["Alice#JP1"]


def test_find_user_puuid() -> None:
    assert find_user_puuid(_players_df(), "Alice", "JP1") == "p-alice"
    assert find_user_puuid(_players_df(), "Nope", "Z") is None
    assert find_user_puuid(pd.DataFrame(), "Alice", "JP1") is None


def test_discover_teammates_ranks_by_games_together() -> None:
    df = discover_teammates(_players_df(), user_puuid="p-alice")
    assert list(df.columns) == DISCOVER_COLUMNS
    # Bob shares a team with Alice in m1 AND m2 (2 games)
    bob = df[df["puuid"] == "p-bob"].iloc[0]
    assert bob["games_together"] == 2
    # Charlie is on the same team as Alice once (m1)
    charlie = df[df["puuid"] == "p-charlie"].iloc[0]
    assert charlie["games_together"] == 1
    # Enemy1 was on the opposite team → must not appear
    assert "p-enemy1" not in set(df["puuid"])
    # Sorted by games_together desc
    assert df.iloc[0]["games_together"] >= df.iloc[-1]["games_together"]


def test_discover_teammates_empty_inputs() -> None:
    assert discover_teammates(pd.DataFrame(), "p-x").empty
    assert discover_teammates(_players_df(), "missing").empty


def test_matches_with_roster_min_present_threshold() -> None:
    roster = {"p-alice", "p-bob", "p-charlie"}

    # min=3 → only m1/Red qualifies
    out_3 = matches_with_roster(_players_df(), roster, min_present=3)
    assert list(out_3.columns) == ROSTER_MATCH_COLUMNS
    assert len(out_3) == 1
    row = out_3.iloc[0]
    assert row["match_id"] == "m1"
    assert row["team"] == "Red"
    assert row["roster_present"] == 3
    assert sorted(row["members"]) == ["Alice", "Bob", "Charlie"]

    # min=2 → m1/Red AND m2/Blue qualify
    out_2 = matches_with_roster(_players_df(), roster, min_present=2)
    assert len(out_2) == 2


def test_matches_with_roster_handles_empty() -> None:
    assert matches_with_roster(pd.DataFrame(), {"p"}, 1).empty
    assert matches_with_roster(_players_df(), set(), 3).empty


def test_filter_payload_by_roster_keeps_only_qualifying_matches() -> None:
    payload = {
        "status": 200,
        "data": [
            {
                "metadata": {"matchid": "good"},
                "players": {
                    "all_players": [
                        {"puuid": "p-alice", "name": "Alice", "tag": "JP1",
                         "team": "Red"},
                        {"puuid": "p-bob", "name": "Bob", "tag": "JP1",
                         "team": "Red"},
                        {"puuid": "p-charlie", "name": "Charlie", "tag": "JP1",
                         "team": "Red"},
                        {"puuid": "p-enemy", "name": "Enemy", "tag": "JP1",
                         "team": "Blue"},
                    ]
                },
            },
            {
                "metadata": {"matchid": "bad"},
                "players": {
                    "all_players": [
                        {"puuid": "p-alice", "name": "Alice", "tag": "JP1",
                         "team": "Red"},
                        {"puuid": "p-rando1", "name": "R1", "tag": "X",
                         "team": "Red"},
                        {"puuid": "p-rando2", "name": "R2", "tag": "X",
                         "team": "Red"},
                    ]
                },
            },
        ],
    }
    entries = parse_roster_entries(["Alice#JP1", "Bob#JP1", "Charlie#JP1"])
    filtered = filter_payload_by_roster(payload, entries, min_present=3)
    assert [m["metadata"]["matchid"] for m in filtered["data"]] == ["good"]


def test_filter_payload_by_roster_matches_via_puuid() -> None:
    payload = {
        "data": [
            {
                "metadata": {"matchid": "via-puuid"},
                "players": {
                    "all_players": [
                        {"puuid": "PA", "name": "X", "tag": "Y", "team": "Red"},
                        {"puuid": "PB", "name": "X", "tag": "Y", "team": "Red"},
                    ]
                },
            }
        ]
    }
    entries = parse_roster_entries(["PA", "PB"])
    filtered = filter_payload_by_roster(payload, entries, min_present=2)
    assert len(filtered["data"]) == 1


def test_members_from_premier_team_extracts_all_members() -> None:
    payload = {
        "status": 1,
        "data": {
            "id": "team-uuid",
            "name": "MyTeam",
            "tag": "MTM",
            "member": [
                {"puuid": "p1", "name": "Alice", "tag": "JP1"},
                {"puuid": "p2", "name": "Bob", "tag": "JP1"},
                {"puuid": None, "name": "Carol", "tag": "JP1"},
                {"puuid": "p4", "name": "Alice", "tag": "JP1"},  # duplicate raw
                "garbage",
            ],
        },
    }
    members = members_from_premier_team(payload)
    raws = [m.raw for m in members]
    assert raws == ["Alice#JP1", "Bob#JP1", "Carol#JP1"]
    alice = next(m for m in members if m.raw == "Alice#JP1")
    assert alice.puuid == "p1"
    assert alice.name == "Alice"
    assert alice.tag == "JP1"


def test_members_from_premier_team_handles_garbage() -> None:
    assert members_from_premier_team({}) == []
    assert members_from_premier_team({"data": "oops"}) == []  # type: ignore[arg-type]
    assert members_from_premier_team({"data": {"member": "no"}}) == []


def test_league_match_ids_pulls_history_ids_in_order() -> None:
    payload = {
        "data": {
            "league_matches": [
                {"id": "m-A", "started_at": "..."},
                {"id": "m-B"},
                {"id": "m-A"},  # duplicate
                {"id": ""},
                {"no_id": True},
                "garbage",
            ]
        }
    }
    assert league_match_ids(payload) == ["m-A", "m-B"]


def test_league_match_ids_handles_garbage() -> None:
    assert league_match_ids({}) == []
    assert league_match_ids({"data": {"league_matches": "no"}}) == []
    assert league_match_ids({"data": "oops"}) == []  # type: ignore[arg-type]
