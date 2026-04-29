"""Tests for storage.duckdb_store (upsert behavior is critical for the
incremental data pipeline)."""

from __future__ import annotations

from pathlib import Path

import duckdb
import pandas as pd
import pytest

from valorant_analyst.storage.duckdb_store import (
    table_row_count,
    upsert_dataframe,
)


def _matches_df(ids: list[str]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "match_id": ids,
            "map_name": ["Ascent"] * len(ids),
            "mode": ["Premier"] * len(ids),
            "queue": ["premier"] * len(ids),
            "game_start": list(range(len(ids))),
            "game_length": [1800] * len(ids),
        }
    )


def test_upsert_creates_table_and_inserts(tmp_path: Path) -> None:
    db = tmp_path / "test.duckdb"
    df = _matches_df(["a", "b", "c"])

    result = upsert_dataframe(df, db, "matches", ["match_id"])

    assert result.inserted == 3
    assert result.skipped == 0
    assert table_row_count(db, "matches") == 3


def test_upsert_skips_existing_keys(tmp_path: Path) -> None:
    db = tmp_path / "test.duckdb"
    upsert_dataframe(_matches_df(["a", "b"]), db, "matches", ["match_id"])

    second = upsert_dataframe(
        _matches_df(["b", "c", "d"]),
        db,
        "matches",
        ["match_id"],
    )

    assert second.inserted == 2
    assert second.skipped == 1
    assert table_row_count(db, "matches") == 4

    con = duckdb.connect(str(db), read_only=True)
    try:
        ids = sorted(
            row[0]
            for row in con.execute("SELECT match_id FROM matches").fetchall()
        )
    finally:
        con.close()
    assert ids == ["a", "b", "c", "d"]


def test_upsert_handles_empty_dataframe(tmp_path: Path) -> None:
    db = tmp_path / "test.duckdb"
    df = _matches_df([]).iloc[0:0]
    result = upsert_dataframe(df, db, "matches", ["match_id"])

    assert result.inserted == 0
    assert result.skipped == 0
    assert table_row_count(db, "matches") == 0


def test_upsert_drops_duplicate_keys_within_input(tmp_path: Path) -> None:
    db = tmp_path / "test.duckdb"
    df = _matches_df(["a", "a", "b"])
    result = upsert_dataframe(df, db, "matches", ["match_id"])

    assert result.inserted == 2
    assert table_row_count(db, "matches") == 2


def test_upsert_supports_composite_key(tmp_path: Path) -> None:
    db = tmp_path / "test.duckdb"
    df = pd.DataFrame(
        {
            "match_id": ["m1", "m1", "m2"],
            "puuid": ["p1", "p2", "p1"],
            "kills": [10, 12, 8],
        }
    )
    first = upsert_dataframe(df, db, "match_players", ["match_id", "puuid"])
    assert first.inserted == 3

    overlap = pd.DataFrame(
        {
            "match_id": ["m1", "m3"],
            "puuid": ["p1", "p1"],
            "kills": [99, 5],
        }
    )
    second = upsert_dataframe(
        overlap, db, "match_players", ["match_id", "puuid"]
    )
    assert second.inserted == 1
    assert second.skipped == 1
    assert table_row_count(db, "match_players") == 4


def test_upsert_rejects_invalid_table_name(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        upsert_dataframe(
            _matches_df(["a"]),
            tmp_path / "x.duckdb",
            "bad name",
            ["match_id"],
        )
