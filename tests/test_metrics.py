"""Tests for analysis.metrics."""

from __future__ import annotations

import pandas as pd

from valorant_analyst.analysis.metrics import (
    PLAYER_SUMMARY_COLUMNS,
    map_summary,
    player_summary,
)


def _players_df() -> pd.DataFrame:
    rows = [
        {
            "match_id": "m1",
            "puuid": "p1",
            "name": "Alice",
            "tag": "JP1",
            "team": "Red",
            "agent": "Jett",
            "kills": 20,
            "deaths": 10,
            "assists": 5,
            "score": 4500,
            "damage_made": 3000,
            "damage_received": 2200,
        },
        {
            "match_id": "m2",
            "puuid": "p1",
            "name": "Alice",
            "tag": "JP1",
            "team": "Blue",
            "agent": "Jett",
            "kills": 10,
            "deaths": 10,
            "assists": 7,
            "score": 3500,
            "damage_made": 2500,
            "damage_received": 2300,
        },
        {
            "match_id": "m1",
            "puuid": "p2",
            "name": "Bob",
            "tag": "JP1",
            "team": "Blue",
            "agent": "Sage",
            "kills": 5,
            "deaths": 0,
            "assists": 12,
            "score": 2500,
            "damage_made": 800,
            "damage_received": 1500,
        },
    ]
    return pd.DataFrame(rows)


def test_player_summary_empty_input() -> None:
    df = player_summary(pd.DataFrame())
    assert df.empty
    assert list(df.columns) == PLAYER_SUMMARY_COLUMNS


def test_player_summary_basic_aggregation() -> None:
    summary = player_summary(_players_df())
    assert list(summary.columns) == PLAYER_SUMMARY_COLUMNS

    alice = summary[summary["name"] == "Alice"].iloc[0]
    assert alice["games"] == 2
    assert alice["avg_kills"] == 15.0
    assert alice["avg_deaths"] == 10.0
    assert alice["avg_assists"] == 6.0
    # 30 kills / 20 deaths = 1.5
    assert alice["kd_ratio"] == 1.5

    bob = summary[summary["name"] == "Bob"].iloc[0]
    assert bob["games"] == 1
    assert bob["avg_kills"] == 5.0
    # zero deaths → KD undefined, expressed as NaN
    assert pd.isna(bob["kd_ratio"])


def test_player_summary_sorted_by_games_desc() -> None:
    summary = player_summary(_players_df())
    assert summary.iloc[0]["name"] == "Alice"
    assert summary.iloc[-1]["name"] == "Bob"


def test_map_summary_basic() -> None:
    matches = pd.DataFrame(
        [
            {"match_id": "m1", "map_name": "Ascent", "mode": "Competitive",
             "queue": "competitive", "game_start": 0, "game_length": 1800},
            {"match_id": "m2", "map_name": "Ascent", "mode": "Competitive",
             "queue": "competitive", "game_start": 0, "game_length": 2400},
            {"match_id": "m3", "map_name": "Bind", "mode": "Competitive",
             "queue": "competitive", "game_start": 0, "game_length": 1500},
        ]
    )
    summary = map_summary(matches, _players_df())
    assert len(summary) == 2
    ascent = summary[summary["map_name"] == "Ascent"].iloc[0]
    assert ascent["games"] == 2
    # avg(1800, 2400) = 2100s = 35.0min
    assert ascent["avg_match_length_min"] == 35.0
