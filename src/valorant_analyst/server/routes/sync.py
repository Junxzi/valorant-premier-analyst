"""Sync endpoint — runs `valorant-analyst team-sync` (team-backfill + ingest).

Both the manual ``POST /api/sync`` HTTP trigger and the background scheduler
in :mod:`valorant_analyst.server.scheduler` go through :func:`start_sync` so a
single in-process lock prevents concurrent runs and the same status/log is
visible to ``GET /api/sync`` regardless of who started the job.
"""

from __future__ import annotations

import subprocess
import sys
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/sync", tags=["sync"])

Trigger = Literal["manual", "scheduled"]

# ---------------------------------------------------------------------------
# In-process state (single-server; sufficient for a local tool)
# ---------------------------------------------------------------------------

_lock = threading.Lock()

_state: dict = {
    "running": False,
    "last_started_at": None,   # ISO string
    "last_finished_at": None,  # ISO string
    "last_status": None,       # "ok" | "error"
    "last_log": "",            # last run's stdout+stderr tail
    "last_trigger": None,      # "manual" | "scheduled"
}

_PROJECT_ROOT = Path(__file__).resolve().parents[4]


def _default_runner() -> subprocess.CompletedProcess[str]:
    """Real subprocess runner used outside tests."""
    return subprocess.run(
        [sys.executable, "-m", "valorant_analyst.cli", "team-sync"],
        cwd=str(_PROJECT_ROOT),
        capture_output=True,
        text=True,
        timeout=600,  # 10 min ceiling for a full team-backfill + ingest
    )


_runner_factory = _default_runner


def set_runner_factory(factory) -> None:
    """Replace the subprocess runner used by the worker thread (for tests)."""
    global _runner_factory
    _runner_factory = factory


def _run_sync_job() -> None:
    """Execute team-sync; ``running`` / start fields are set before the thread starts."""
    log = ""
    status = "error"
    try:
        result = _runner_factory()
        log = (result.stdout + result.stderr).strip()
        status = "ok" if result.returncode == 0 else "error"
    except subprocess.TimeoutExpired:
        log = "Timeout: team-sync took longer than 10 minutes."
        status = "error"
    except Exception as exc:  # noqa: BLE001
        log = str(exc)
        status = "error"
    finally:
        finished = datetime.now(UTC).isoformat()
        with _lock:
            _state["running"] = False
            _state["last_finished_at"] = finished
            _state["last_status"] = status
            _state["last_log"] = log[-4096:] if len(log) > 4096 else log


class SyncStatus(BaseModel):
    running: bool
    last_started_at: str | None
    last_finished_at: str | None
    last_status: str | None  # "ok" | "error" | None
    last_log: str
    last_trigger: Trigger | None = None


def _snapshot() -> SyncStatus:
    """Return a SyncStatus copy of the current state. Caller holds the lock."""
    return SyncStatus(**_state)


def start_sync(trigger: Trigger = "manual") -> tuple[bool, SyncStatus]:
    """Kick off a team-sync run in a background thread.

    Returns ``(started, snapshot)`` — ``started`` is False when a sync is
    already running and this call was a no-op. The same lock serializes
    manual HTTP triggers and the scheduled background loop, so the two
    callers can't double-spawn the worker.
    """
    with _lock:
        if _state["running"]:
            return False, _snapshot()
        started = datetime.now(UTC).isoformat()
        _state["running"] = True
        _state["last_started_at"] = started
        _state["last_log"] = ""
        _state["last_trigger"] = trigger
        snapshot = _snapshot()

    thread = threading.Thread(target=_run_sync_job, daemon=True)
    thread.start()
    return True, snapshot


@router.get("", response_model=SyncStatus)
def get_sync_status() -> SyncStatus:
    """Return the current sync state."""
    with _lock:
        return _snapshot()


@router.post("", response_model=SyncStatus)
def trigger_sync() -> SyncStatus:
    """Kick off a sync run in the background. Ignored if already running."""
    _, snapshot = start_sync(trigger="manual")
    return snapshot
