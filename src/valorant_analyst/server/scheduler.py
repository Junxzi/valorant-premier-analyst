"""Background scheduler that periodically triggers ``team-sync``.

A single :func:`asyncio.Task` is spawned from the FastAPI ``lifespan`` context
manager (see :mod:`valorant_analyst.server.app`). The loop is intentionally
trivial — it just nudges :func:`valorant_analyst.server.routes.sync.start_sync`
on a fixed cadence and lets the existing in-process lock + worker thread do
the actual work, so the manual button and the scheduler share one execution
queue and one status object.
"""

from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass

from .routes.sync import start_sync

logger = logging.getLogger("valorant_analyst.server.scheduler")

DEFAULT_INTERVAL_MINUTES = 15
DEFAULT_INITIAL_DELAY_SECONDS = 30


@dataclass(frozen=True)
class SchedulerConfig:
    enabled: bool
    interval_seconds: int
    initial_delay_seconds: int
    disabled_reason: str | None = None


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    cleaned = raw.strip().lower()
    if not cleaned:
        return default
    return cleaned in ("1", "true", "yes", "on")


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    cleaned = raw.strip()
    if not cleaned:
        return default
    try:
        value = int(cleaned)
    except ValueError:
        logger.warning(
            "Invalid integer for %s=%r; falling back to default %d", name, raw, default
        )
        return default
    return max(0, value)


def load_scheduler_config() -> SchedulerConfig:
    """Read scheduler settings from the environment.

    The scheduler is auto-disabled (with a logged reason) when the required
    HenrikDev / Premier env vars are missing, so a half-configured local
    server doesn't keep hammering the API for nothing.
    """
    enabled = _env_bool("SYNC_AUTO_ENABLED", True)
    interval_minutes = _env_int(
        "SYNC_AUTO_INTERVAL_MINUTES", DEFAULT_INTERVAL_MINUTES
    )
    initial_delay = _env_int(
        "SYNC_AUTO_INITIAL_DELAY_SECONDS", DEFAULT_INITIAL_DELAY_SECONDS
    )

    disabled_reason: str | None = None
    if not enabled:
        disabled_reason = "SYNC_AUTO_ENABLED=0"
    elif interval_minutes <= 0:
        disabled_reason = f"SYNC_AUTO_INTERVAL_MINUTES={interval_minutes}"
    else:
        missing = [
            key
            for key in ("HENRIK_API_KEY", "PREMIER_TEAM_NAME", "PREMIER_TEAM_TAG")
            if not (os.getenv(key) or "").strip()
        ]
        if missing:
            disabled_reason = (
                "missing env: " + ", ".join(missing)
            )

    return SchedulerConfig(
        enabled=disabled_reason is None,
        interval_seconds=interval_minutes * 60,
        initial_delay_seconds=initial_delay,
        disabled_reason=disabled_reason,
    )


async def periodic_sync_loop(
    interval_seconds: int,
    initial_delay_seconds: int,
) -> None:
    """Run ``start_sync('scheduled')`` every *interval_seconds* until cancelled.

    The first tick is delayed by *initial_delay_seconds* so the server has a
    moment to finish booting before we hammer the HenrikDev API.
    """
    logger.info(
        "Scheduler started: interval=%ds initial_delay=%ds",
        interval_seconds,
        initial_delay_seconds,
    )
    try:
        if initial_delay_seconds > 0:
            await asyncio.sleep(initial_delay_seconds)
        while True:
            try:
                started, snapshot = start_sync(trigger="scheduled")
                if started:
                    logger.info("Scheduled sync started")
                else:
                    logger.info(
                        "Scheduled sync skipped (already running, last_trigger=%s)",
                        snapshot.last_trigger,
                    )
            except Exception:  # noqa: BLE001 - keep loop alive across errors
                logger.exception("Scheduled sync trigger failed")

            await asyncio.sleep(interval_seconds)
    except asyncio.CancelledError:
        logger.info("Scheduler loop cancelled — exiting cleanly")
        raise
