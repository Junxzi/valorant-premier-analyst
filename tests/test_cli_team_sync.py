"""Tests for cmd_team_sync — composes team-backfill + ingest --from-archive."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from valorant_analyst.cli import cmd_team_sync
from valorant_analyst.config import AppConfig


def _config() -> AppConfig:
    return AppConfig(
        henrik_api_key="key",
        region="ap",
        name="Me",
        tag="JP1",
        match_size=10,
        roster_entries=(),
        roster_min_present=4,
        premier_team_name="MyTeam",
        premier_team_tag="MTM",
    )


def test_cmd_team_sync_calls_backfill_then_ingest(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    calls: list[str] = []

    def fake_team_backfill(*args: Any, **kwargs: Any) -> None:
        calls.append("team-backfill")

    def fake_ingest(*args: Any, **kwargs: Any) -> tuple:
        calls.append("ingest")
        # Verify ingest was invoked with the archive flow.
        assert kwargs["use_archive"] is True
        assert kwargs["premier_only"] is True
        return (None, None)

    monkeypatch.setattr("valorant_analyst.cli.cmd_team_backfill", fake_team_backfill)
    monkeypatch.setattr("valorant_analyst.cli.cmd_ingest", fake_ingest)

    cmd_team_sync(
        _config(),
        tmp_path / "archive",
        tmp_path / "db.duckdb",
        tmp_path / "rh.json",
        sleep_seconds=0.0,
        max_matches=None,
    )

    assert calls == ["team-backfill", "ingest"]


def test_cmd_team_sync_propagates_backfill_errors(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """If team-backfill fails, ingest must not run and the error must surface."""
    ingest_called = False

    def fake_team_backfill(*args: Any, **kwargs: Any) -> None:
        raise RuntimeError("backfill exploded")

    def fake_ingest(*args: Any, **kwargs: Any) -> tuple:
        nonlocal ingest_called
        ingest_called = True
        return (None, None)

    monkeypatch.setattr("valorant_analyst.cli.cmd_team_backfill", fake_team_backfill)
    monkeypatch.setattr("valorant_analyst.cli.cmd_ingest", fake_ingest)

    with pytest.raises(RuntimeError, match="backfill exploded"):
        cmd_team_sync(
            _config(),
            tmp_path / "archive",
            tmp_path / "db.duckdb",
            tmp_path / "rh.json",
            sleep_seconds=0.0,
            max_matches=None,
        )
    assert ingest_called is False


def test_cmd_team_sync_propagates_ingest_errors(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def fake_team_backfill(*args: Any, **kwargs: Any) -> None:
        return None

    def fake_ingest(*args: Any, **kwargs: Any) -> tuple:
        raise RuntimeError("ingest exploded")

    monkeypatch.setattr("valorant_analyst.cli.cmd_team_backfill", fake_team_backfill)
    monkeypatch.setattr("valorant_analyst.cli.cmd_ingest", fake_ingest)

    with pytest.raises(RuntimeError, match="ingest exploded"):
        cmd_team_sync(
            _config(),
            tmp_path / "archive",
            tmp_path / "db.duckdb",
            tmp_path / "rh.json",
            sleep_seconds=0.0,
            max_matches=None,
        )


def test_cmd_team_sync_passes_max_matches_and_rebuild_flags(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    backfill_kwargs: dict[str, Any] = {}
    ingest_kwargs: dict[str, Any] = {}

    def fake_team_backfill(*args: Any, **kwargs: Any) -> None:
        backfill_kwargs.update(kwargs)

    def fake_ingest(*args: Any, **kwargs: Any) -> tuple:
        ingest_kwargs.update(kwargs)
        return (None, None)

    monkeypatch.setattr("valorant_analyst.cli.cmd_team_backfill", fake_team_backfill)
    monkeypatch.setattr("valorant_analyst.cli.cmd_ingest", fake_ingest)

    cmd_team_sync(
        _config(),
        tmp_path / "archive",
        tmp_path / "db.duckdb",
        tmp_path / "rh.json",
        sleep_seconds=1.5,
        max_matches=3,
        rebuild_players=True,
    )

    assert backfill_kwargs["sleep_seconds"] == 1.5
    assert backfill_kwargs["max_matches"] == 3
    assert ingest_kwargs["rebuild_players"] is True
