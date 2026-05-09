"""Sync endpoint — triggers `valorant-analyst run` (fetch + ingest) in the background."""

from __future__ import annotations

import subprocess
import sys
import threading
from datetime import UTC, datetime
from pathlib import Path

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/sync", tags=["sync"])

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
}

_PROJECT_ROOT = Path(__file__).resolve().parents[4]


def _run_sync_job() -> None:
    """Execute fetch+ingest; ``running`` / start fields are set before the thread starts."""
    log = ""
    status = "error"
    try:
        result = subprocess.run(
            [sys.executable, "-m", "valorant_analyst.cli", "run"],
            cwd=str(_PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=300,  # 5 min max
        )
        log = (result.stdout + result.stderr).strip()
        status = "ok" if result.returncode == 0 else "error"
    except subprocess.TimeoutExpired:
        log = "Timeout: sync took longer than 5 minutes."
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


@router.get("", response_model=SyncStatus)
def get_sync_status() -> SyncStatus:
    """Return the current sync state."""
    with _lock:
        return SyncStatus(**_state)


@router.post("", response_model=SyncStatus)
def start_sync() -> SyncStatus:
    """Kick off a fetch+ingest run in the background. Ignored if already running."""
    with _lock:
        if _state["running"]:
            return SyncStatus(**_state)
        started = datetime.now(UTC).isoformat()
        _state["running"] = True
        _state["last_started_at"] = started
        _state["last_log"] = ""
        out = SyncStatus(**_state)

    thread = threading.Thread(target=_run_sync_job, daemon=True)
    thread.start()
    return out
