"""Tests for the sync route + scheduler config helpers."""

from __future__ import annotations

import subprocess
import threading
import time
from typing import Any

import pytest

from valorant_analyst.server import scheduler
from valorant_analyst.server.routes import sync as sync_route


@pytest.fixture(autouse=True)
def _reset_state(monkeypatch: pytest.MonkeyPatch):
    """Reset module-level sync state and restore default runner between tests."""
    sync_route._state.update(
        running=False,
        last_started_at=None,
        last_finished_at=None,
        last_status=None,
        last_log="",
        last_trigger=None,
    )
    monkeypatch.setattr(sync_route, "_runner_factory", sync_route._default_runner)
    yield
    sync_route._state.update(
        running=False,
        last_started_at=None,
        last_finished_at=None,
        last_status=None,
        last_log="",
        last_trigger=None,
    )


class _FakeCompleted:
    def __init__(self, *, returncode: int = 0, stdout: str = "", stderr: str = "") -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def _wait_for_idle(timeout: float = 2.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        with sync_route._lock:
            if not sync_route._state["running"]:
                return
        time.sleep(0.01)
    raise AssertionError("sync did not finish in time")


# ---------------------------------------------------------------------------
# start_sync — locking and trigger plumbing
# ---------------------------------------------------------------------------


def test_start_sync_runs_runner_and_records_trigger() -> None:
    captured: list[bool] = []

    def fake() -> _FakeCompleted:
        captured.append(True)
        return _FakeCompleted(stdout="hello")

    sync_route.set_runner_factory(fake)
    started, snapshot = sync_route.start_sync(trigger="manual")
    assert started is True
    assert snapshot.last_trigger == "manual"
    _wait_for_idle()

    final = sync_route.get_sync_status()
    assert final.running is False
    assert final.last_status == "ok"
    assert final.last_log == "hello"
    assert final.last_trigger == "manual"
    assert captured == [True]


def test_start_sync_second_call_is_skipped_when_running() -> None:
    gate = threading.Event()

    def fake() -> _FakeCompleted:
        gate.wait(timeout=2.0)
        return _FakeCompleted()

    sync_route.set_runner_factory(fake)
    started1, _ = sync_route.start_sync(trigger="manual")
    assert started1 is True

    started2, snap2 = sync_route.start_sync(trigger="scheduled")
    assert started2 is False
    # last_trigger must reflect the *currently running* job, not the
    # rejected scheduled call.
    assert snap2.last_trigger == "manual"
    assert snap2.running is True

    gate.set()
    _wait_for_idle()


def test_start_sync_records_error_on_nonzero_exit() -> None:
    sync_route.set_runner_factory(
        lambda: _FakeCompleted(returncode=1, stderr="boom")
    )
    started, _ = sync_route.start_sync(trigger="scheduled")
    assert started is True
    _wait_for_idle()

    final = sync_route.get_sync_status()
    assert final.last_status == "error"
    assert "boom" in final.last_log
    assert final.last_trigger == "scheduled"


def test_start_sync_handles_subprocess_timeout() -> None:
    def fake() -> _FakeCompleted:
        raise subprocess.TimeoutExpired(cmd="x", timeout=1)

    sync_route.set_runner_factory(fake)
    started, _ = sync_route.start_sync(trigger="manual")
    assert started is True
    _wait_for_idle()

    final = sync_route.get_sync_status()
    assert final.last_status == "error"
    assert "Timeout" in final.last_log


def test_default_runner_targets_team_sync() -> None:
    """Sanity check: the production subprocess command is `team-sync`."""
    captured: list[list[str]] = []

    def fake_run(cmd: list[str], **kwargs: Any) -> _FakeCompleted:
        captured.append(cmd)
        return _FakeCompleted()

    import valorant_analyst.server.routes.sync as mod

    original_run = subprocess.run
    subprocess.run = fake_run  # type: ignore[assignment]
    try:
        mod._default_runner()
    finally:
        subprocess.run = original_run  # type: ignore[assignment]

    assert captured, "subprocess.run was not called"
    assert captured[0][-1] == "team-sync"


# ---------------------------------------------------------------------------
# load_scheduler_config — env parsing + auto-disable
# ---------------------------------------------------------------------------


def _set_required_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HENRIK_API_KEY", "key")
    monkeypatch.setenv("PREMIER_TEAM_NAME", "MyTeam")
    monkeypatch.setenv("PREMIER_TEAM_TAG", "MTM")


def test_scheduler_enabled_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_required_env(monkeypatch)
    monkeypatch.delenv("SYNC_AUTO_ENABLED", raising=False)
    monkeypatch.delenv("SYNC_AUTO_INTERVAL_MINUTES", raising=False)
    monkeypatch.delenv("SYNC_AUTO_INITIAL_DELAY_SECONDS", raising=False)

    cfg = scheduler.load_scheduler_config()
    assert cfg.enabled is True
    assert cfg.interval_seconds == 15 * 60
    assert cfg.initial_delay_seconds == 30
    assert cfg.disabled_reason is None


def test_scheduler_disabled_via_env(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_required_env(monkeypatch)
    monkeypatch.setenv("SYNC_AUTO_ENABLED", "0")
    cfg = scheduler.load_scheduler_config()
    assert cfg.enabled is False
    assert cfg.disabled_reason == "SYNC_AUTO_ENABLED=0"


def test_scheduler_disabled_when_env_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SYNC_AUTO_ENABLED", "1")
    monkeypatch.delenv("HENRIK_API_KEY", raising=False)
    monkeypatch.setenv("PREMIER_TEAM_NAME", "MyTeam")
    monkeypatch.setenv("PREMIER_TEAM_TAG", "MTM")
    cfg = scheduler.load_scheduler_config()
    assert cfg.enabled is False
    assert cfg.disabled_reason is not None
    assert "HENRIK_API_KEY" in cfg.disabled_reason


def test_scheduler_zero_interval_disables(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_required_env(monkeypatch)
    monkeypatch.setenv("SYNC_AUTO_INTERVAL_MINUTES", "0")
    cfg = scheduler.load_scheduler_config()
    assert cfg.enabled is False
    assert cfg.disabled_reason is not None
    assert "INTERVAL" in cfg.disabled_reason


def test_scheduler_invalid_int_falls_back_to_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_required_env(monkeypatch)
    monkeypatch.setenv("SYNC_AUTO_INTERVAL_MINUTES", "not-an-int")
    cfg = scheduler.load_scheduler_config()
    assert cfg.enabled is True
    assert cfg.interval_seconds == 15 * 60


def test_scheduler_env_bool_truthy_variants(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_required_env(monkeypatch)
    for truthy in ("1", "true", "TRUE", "yes", "On"):
        monkeypatch.setenv("SYNC_AUTO_ENABLED", truthy)
        cfg = scheduler.load_scheduler_config()
        assert cfg.enabled is True, f"expected enabled for {truthy!r}"
    for falsy in ("0", "false", "no", "off", "  "):
        monkeypatch.setenv("SYNC_AUTO_ENABLED", falsy)
        cfg = scheduler.load_scheduler_config()
        # Empty/whitespace falls back to default True; explicit false disables.
        if falsy.strip():
            assert cfg.enabled is False, f"expected disabled for {falsy!r}"
        else:
            assert cfg.enabled is True
