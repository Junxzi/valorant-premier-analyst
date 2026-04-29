"""Tests for processing.normalize."""

from __future__ import annotations

import pandas as pd

from valorant_analyst.processing.normalize import (
    MATCH_COLUMNS,
    PLAYER_COLUMNS,
    ROUND_COLUMNS,
    TEAM_COLUMNS,
    extract_match_ids_from_stored,
    filter_premier,
    normalize_match_players,
    normalize_match_teams,
    normalize_matches,
    normalize_rounds,
    wrap_single_match,
)


def test_normalize_handles_empty_payload() -> None:
    empty_df = normalize_matches({})
    assert isinstance(empty_df, pd.DataFrame)
    assert empty_df.empty
    assert list(empty_df.columns) == MATCH_COLUMNS

    empty_players = normalize_match_players({})
    assert isinstance(empty_players, pd.DataFrame)
    assert empty_players.empty
    assert list(empty_players.columns) == PLAYER_COLUMNS


def test_normalize_handles_missing_data_key() -> None:
    payload: dict = {"status": 200}
    assert normalize_matches(payload).empty
    assert normalize_match_players(payload).empty


def test_normalize_handles_garbage_input() -> None:
    assert normalize_matches({"data": "oops"}).empty  # type: ignore[arg-type]
    assert normalize_match_players({"data": None}).empty


def _sample_payload() -> dict:
    return {
        "status": 200,
        "data": [
            {
                "metadata": {
                    "matchid": "abc-123",
                    "map": "Ascent",
                    "mode": "Competitive",
                    "queue": "competitive",
                    "game_start": 1700000000,
                    "game_length": 1800,
                },
                "players": {
                    "all_players": [
                        {
                            "puuid": "p1",
                            "name": "Alice",
                            "tag": "JP1",
                            "team": "Red",
                            "character": "Jett",
                            "stats": {
                                "kills": 20,
                                "deaths": 12,
                                "assists": 4,
                                "score": 4500,
                            },
                            "damage_made": 3000,
                            "damage_received": 2400,
                        },
                        {
                            "puuid": "p2",
                            "name": "Bob",
                            "tag": "JP1",
                            "team": "Blue",
                            "character": "Sage",
                            "stats": {
                                "kills": 10,
                                "deaths": 14,
                                "assists": 8,
                                "score": 3000,
                            },
                        },
                    ]
                },
            }
        ],
    }


def test_normalize_matches_sample() -> None:
    df = normalize_matches(_sample_payload())
    assert len(df) == 1
    row = df.iloc[0]
    assert row["match_id"] == "abc-123"
    assert row["map_name"] == "Ascent"
    assert row["mode"] == "Competitive"
    assert row["game_length"] == 1800


def test_filter_premier_keeps_only_premier_matches() -> None:
    payload = {
        "status": 200,
        "data": [
            {"metadata": {"matchid": "p1", "queue": "premier", "mode": "Premier"}},
            {"metadata": {"matchid": "c1", "queue": "competitive",
                          "mode": "Competitive"}},
            {"metadata": {"matchid": "p2", "mode": "Premier"}},
            {"metadata": {"matchid": "u1", "queue": "unrated"}},
        ],
    }
    filtered = filter_premier(payload)
    ids = sorted(
        m["metadata"]["matchid"]
        for m in filtered["data"]
    )
    assert ids == ["p1", "p2"]


def test_filter_premier_handles_empty_payload() -> None:
    assert filter_premier({}) == {"status": 200, "data": []}
    assert filter_premier({"data": []}) == {"status": 200, "data": []}


def test_filter_premier_uses_premier_info() -> None:
    payload = {
        "data": [
            {
                "metadata": {
                    "matchid": "x1",
                    "queue": "competitive",
                    "premier_info": {"tournament_id": "t1", "matchup_id": "m1"},
                }
            }
        ]
    }
    filtered = filter_premier(payload)
    assert len(filtered["data"]) == 1


def test_extract_match_ids_from_stored_premier_only() -> None:
    payload = {
        "status": 200,
        "results": {"total": 4, "returned": 4},
        "data": [
            {"meta": {"id": "p1", "mode": "Premier",
                      "map": {"name": "Ascent"}}},
            {"meta": {"id": "c1", "mode": "Competitive",
                      "map": {"name": "Bind"}}},
            {"meta": {"id": "p2", "mode": "Premier",
                      "map": {"name": "Lotus"}}},
            {"meta": {"id": "p1", "mode": "Premier",
                      "map": {"name": "Ascent"}}},  # duplicate
        ],
    }
    ids = extract_match_ids_from_stored(payload)
    assert ids == ["p1", "p2"]


def test_extract_match_ids_from_stored_all_modes() -> None:
    payload = {
        "data": [
            {"meta": {"id": "a", "mode": "Premier"}},
            {"meta": {"id": "b", "mode": "Competitive"}},
            {"meta": {}},  # missing id → skipped
            {"not_meta": True},  # malformed → skipped
        ]
    }
    ids = extract_match_ids_from_stored(payload, premier_only=False)
    assert ids == ["a", "b"]


def test_extract_match_ids_from_stored_handles_garbage() -> None:
    assert extract_match_ids_from_stored({}) == []
    assert extract_match_ids_from_stored({"data": "oops"}) == []  # type: ignore[arg-type]
    assert extract_match_ids_from_stored({"data": None}) == []


def test_wrap_single_match_object() -> None:
    inner = {"metadata": {"matchid": "abc"}, "players": {}}
    wrapped = wrap_single_match({"status": 200, "data": inner})
    assert wrapped == {"status": 200, "data": [inner]}


def test_normalize_match_teams_extracts_premier_roster() -> None:
    payload = {
        "data": [
            {
                "metadata": {"matchid": "m1"},
                "teams": {
                    "red": {
                        "has_won": True,
                        "rounds_won": 13,
                        "rounds_lost": 7,
                        "roster": {
                            "id": "tr-1",
                            "name": "Red Team",
                            "tag": "RED",
                        },
                    },
                    "blue": {
                        "has_won": False,
                        "rounds_won": 7,
                        "rounds_lost": 13,
                        "roster": {
                            "id": "tb-1",
                            "name": "Blue Team",
                            "tag": "BLU",
                        },
                    },
                },
            }
        ]
    }
    df = normalize_match_teams(payload)
    assert list(df.columns) == TEAM_COLUMNS
    assert len(df) == 2

    red = df[df["team"] == "Red"].iloc[0]
    assert bool(red["has_won"]) is True
    assert red["rounds_won"] == 13
    assert red["premier_team_tag"] == "RED"

    blue = df[df["team"] == "Blue"].iloc[0]
    assert bool(blue["has_won"]) is False
    assert blue["premier_team_id"] == "tb-1"


def test_normalize_match_teams_handles_no_roster() -> None:
    payload = {
        "data": [
            {
                "metadata": {"matchid": "m1"},
                "teams": {
                    "red": {"has_won": True, "rounds_won": 13, "rounds_lost": 11},
                    "blue": {"has_won": False, "rounds_won": 11, "rounds_lost": 13},
                },
            }
        ]
    }
    df = normalize_match_teams(payload)
    assert len(df) == 2
    assert df["premier_team_id"].isna().all()


def test_normalize_match_teams_empty_payload() -> None:
    assert normalize_match_teams({}).empty
    assert normalize_match_teams({"data": []}).empty
    assert normalize_match_teams({"data": [{"metadata": {"matchid": "x"}}]}).empty


def test_normalize_rounds_basic() -> None:
    payload = {
        "data": [
            {
                "metadata": {"matchid": "m1"},
                "rounds": [
                    {
                        "winning_team": "Red",
                        "end_type": "Eliminated",
                        "bomb_planted": False,
                    },
                    {
                        "winning_team": "Blue",
                        "end_type": "Bomb detonated",
                        "bomb_planted": True,
                        "bomb_defused": False,
                    },
                    "garbage",
                ],
            }
        ]
    }
    df = normalize_rounds(payload)
    assert list(df.columns) == ROUND_COLUMNS
    assert len(df) == 2
    assert df.iloc[0]["round_num"] == 1
    assert df.iloc[0]["winning_team"] == "Red"
    assert bool(df.iloc[1]["bomb_planted"]) is True
    assert df.iloc[1]["winning_team"] == "Blue"


def test_normalize_rounds_empty() -> None:
    assert normalize_rounds({}).empty
    assert normalize_rounds({"data": [{"metadata": {"matchid": "x"}}]}).empty
    assert normalize_rounds(
        {"data": [{"metadata": {"matchid": "x"}, "rounds": "no"}]}
    ).empty


def test_wrap_single_match_handles_list_or_missing() -> None:
    assert wrap_single_match({"data": [{"metadata": {"matchid": "z"}}]})["data"] == [
        {"metadata": {"matchid": "z"}}
    ]
    assert wrap_single_match({})["data"] == []
    assert wrap_single_match({"status": 500, "data": "boom"})["data"] == []


def test_normalize_match_players_sample() -> None:
    df = normalize_match_players(_sample_payload())
    assert list(df.columns) == PLAYER_COLUMNS
    assert len(df) == 2

    alice = df[df["name"] == "Alice"].iloc[0]
    assert alice["match_id"] == "abc-123"
    assert alice["agent"] == "Jett"
    assert alice["kills"] == 20
    assert alice["deaths"] == 12
    assert alice["damage_made"] == 3000
    assert alice["damage_received"] == 2400

    bob = df[df["name"] == "Bob"].iloc[0]
    assert bob["damage_made"] is None or pd.isna(bob["damage_made"])
