"""Tests for the legacy `data/` -> `db/` migration helper."""

from __future__ import annotations

from pathlib import Path

import pytest

from valorant_analyst.server import persist_migrate


def _redirect_targets(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> dict[str, Path]:
    """Point all migration source/destination paths at *tmp_path* sandboxes."""
    legacy_root = tmp_path / "legacy"
    persist_root = tmp_path / "persist"
    paths: dict[str, Path] = {}

    targets = (
        ("strategy", legacy_root / "strategy", persist_root / "strategy", True),
        ("notes", legacy_root / "notes", persist_root / "notes", True),
        ("bios", legacy_root / "bios", persist_root / "bios", True),
        ("vods", legacy_root / "vods.json", persist_root / "vods.json", False),
        (
            "roster_history",
            legacy_root / "roster_history.json",
            persist_root / "roster_history.json",
            False,
        ),
        (
            "raw_archive",
            legacy_root / "raw" / "matches",
            persist_root / "raw" / "matches",
            True,
        ),
    )
    new_targets = tuple(
        persist_migrate._Target(label=label, legacy=legacy, destination=dest, is_dir=is_dir)
        for label, legacy, dest, is_dir in targets
    )
    monkeypatch.setattr(persist_migrate, "_TARGETS", new_targets)

    for label, legacy, dest, _ in targets:
        paths[f"legacy_{label}"] = legacy
        paths[f"dest_{label}"] = dest
    paths["legacy_root"] = legacy_root
    paths["persist_root"] = persist_root
    return paths


def test_migrate_copies_files_when_destination_missing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    paths = _redirect_targets(monkeypatch, tmp_path)
    paths["legacy_strategy"].mkdir(parents=True)
    (paths["legacy_strategy"] / "MyTeam__MTM.json").write_text(
        '{"Ascent": {"Alice": "Jett"}}', encoding="utf-8"
    )
    paths["legacy_vods"].parent.mkdir(parents=True, exist_ok=True)
    paths["legacy_vods"].write_text('{"m1": "https://x"}', encoding="utf-8")

    report = persist_migrate.migrate_legacy_data()

    assert report["strategy"] == 1
    assert report["vods"] == 1
    assert (paths["dest_strategy"] / "MyTeam__MTM.json").read_text(encoding="utf-8") == (
        '{"Ascent": {"Alice": "Jett"}}'
    )
    assert paths["dest_vods"].read_text(encoding="utf-8") == '{"m1": "https://x"}'


def test_migrate_is_idempotent(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    paths = _redirect_targets(monkeypatch, tmp_path)
    paths["legacy_strategy"].mkdir(parents=True)
    (paths["legacy_strategy"] / "MyTeam__MTM.json").write_text(
        '{"Ascent": {}}', encoding="utf-8"
    )

    first = persist_migrate.migrate_legacy_data()
    second = persist_migrate.migrate_legacy_data()
    assert first["strategy"] == 1
    assert second["strategy"] == 0


def test_migrate_does_not_overwrite_existing_destination_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    paths = _redirect_targets(monkeypatch, tmp_path)
    paths["legacy_vods"].parent.mkdir(parents=True, exist_ok=True)
    paths["legacy_vods"].write_text('{"legacy": "x"}', encoding="utf-8")
    paths["dest_vods"].parent.mkdir(parents=True, exist_ok=True)
    paths["dest_vods"].write_text('{"live": "y"}', encoding="utf-8")

    report = persist_migrate.migrate_legacy_data()

    assert report["vods"] == 0
    assert paths["dest_vods"].read_text(encoding="utf-8") == '{"live": "y"}'


def test_migrate_directory_picks_up_only_missing_files(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    paths = _redirect_targets(monkeypatch, tmp_path)
    paths["legacy_strategy"].mkdir(parents=True)
    (paths["legacy_strategy"] / "Old__OLD.json").write_text("legacy", encoding="utf-8")
    (paths["legacy_strategy"] / "New__NEW.json").write_text("legacy", encoding="utf-8")

    paths["dest_strategy"].mkdir(parents=True, exist_ok=True)
    (paths["dest_strategy"] / "Old__OLD.json").write_text("live", encoding="utf-8")

    report = persist_migrate.migrate_legacy_data()

    assert report["strategy"] == 1
    # Pre-existing destination file is preserved.
    assert (paths["dest_strategy"] / "Old__OLD.json").read_text(encoding="utf-8") == "live"
    # Missing destination file copied across.
    assert (paths["dest_strategy"] / "New__NEW.json").read_text(encoding="utf-8") == "legacy"


def test_migrate_handles_missing_legacy(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Running on a fresh deploy where data/ doesn't exist must be a no-op."""
    _redirect_targets(monkeypatch, tmp_path)
    report = persist_migrate.migrate_legacy_data()
    assert all(count == 0 for count in report.values())


def test_migrate_continues_after_individual_failure(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    paths = _redirect_targets(monkeypatch, tmp_path)
    paths["legacy_strategy"].mkdir(parents=True)
    (paths["legacy_strategy"] / "MyTeam__MTM.json").write_text(
        '{"Ascent": {}}', encoding="utf-8"
    )

    original = persist_migrate._migrate_one
    seen: list[str] = []

    def flaky(target):
        seen.append(target.label)
        if target.label == "notes":
            raise OSError("simulated disk error")
        return original(target)

    monkeypatch.setattr(persist_migrate, "_migrate_one", flaky)
    report = persist_migrate.migrate_legacy_data()

    # Other targets still ran, the failing one is omitted from the report.
    assert "strategy" in report
    assert "notes" not in report
    assert report["strategy"] == 1
