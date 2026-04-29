"""Tests for storage.raw_store archive helpers."""

from __future__ import annotations

import json
from pathlib import Path

from valorant_analyst.storage.raw_store import (
    archive_matches,
    archived_match_ids,
    iter_archived_matches,
    load_archive_as_payload,
    save_match_archive,
)


def _payload() -> dict:
    return {
        "status": 200,
        "data": [
            {"metadata": {"matchid": "abc-1"}, "players": {"all_players": []}},
            {"metadata": {"matchid": "abc-2"}, "players": {"all_players": []}},
            {"metadata": {}, "players": {}},  # missing match_id → skipped
        ],
    }


def test_archive_matches_writes_one_file_per_match(tmp_path: Path) -> None:
    written = archive_matches(_payload(), tmp_path)

    assert len(written) == 2
    files = sorted(p.name for p in tmp_path.glob("*.json"))
    assert files == ["abc-1.json", "abc-2.json"]

    with (tmp_path / "abc-1.json").open(encoding="utf-8") as fh:
        match = json.load(fh)
    assert match["metadata"]["matchid"] == "abc-1"


def test_archive_matches_is_idempotent(tmp_path: Path) -> None:
    archive_matches(_payload(), tmp_path)
    archive_matches(_payload(), tmp_path)
    assert len(list(tmp_path.glob("*.json"))) == 2


def test_archive_matches_handles_empty_payload(tmp_path: Path) -> None:
    assert archive_matches({}, tmp_path) == []
    assert archive_matches({"data": None}, tmp_path) == []


def test_load_archive_as_payload_round_trip(tmp_path: Path) -> None:
    archive_matches(_payload(), tmp_path)
    rebuilt = load_archive_as_payload(tmp_path)

    ids = sorted(m["metadata"]["matchid"] for m in rebuilt["data"])
    assert ids == ["abc-1", "abc-2"]


def test_archived_match_ids_returns_filenames(tmp_path: Path) -> None:
    assert archived_match_ids(tmp_path) == set()
    archive_matches(_payload(), tmp_path)
    assert archived_match_ids(tmp_path) == {"abc-1", "abc-2"}


def test_archived_match_ids_handles_missing_dir(tmp_path: Path) -> None:
    assert archived_match_ids(tmp_path / "does-not-exist") == set()


def test_save_match_archive_single_match(tmp_path: Path) -> None:
    match = {"metadata": {"matchid": "single-1"}, "players": {"all_players": []}}
    path = save_match_archive(match, tmp_path)
    assert path is not None
    assert path.name == "single-1.json"
    assert archived_match_ids(tmp_path) == {"single-1"}


def test_save_match_archive_returns_none_for_unidentifiable(tmp_path: Path) -> None:
    assert save_match_archive({"metadata": {}}, tmp_path) is None
    assert save_match_archive({}, tmp_path) is None
    assert save_match_archive("not a dict", tmp_path) is None  # type: ignore[arg-type]


def test_iter_archived_matches_skips_invalid_files(tmp_path: Path) -> None:
    (tmp_path / "broken.json").write_text("{ not json", encoding="utf-8")
    (tmp_path / "ok.json").write_text(
        json.dumps({"metadata": {"matchid": "ok"}}), encoding="utf-8"
    )
    matches = list(iter_archived_matches(tmp_path))
    assert len(matches) == 1
    assert matches[0]["metadata"]["matchid"] == "ok"
