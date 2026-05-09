"""One-shot migration of the legacy ``data/`` tree into ``PERSIST_ROOT``.

Older builds wrote strategy / notes / bios / vods / roster history under
``data/`` (project root). That directory was *ephemeral* on Railway because
no Volume was mounted there — every redeploy reset everything. The fix is to
keep all persistent files under ``db/`` (the directory the Volume mounts).

This helper runs on FastAPI startup and copies any legacy file/folder into
the new location only when the destination is empty. It's idempotent: once
the migration has happened, repeated calls are no-ops, so it's safe to leave
the hook in forever.
"""

from __future__ import annotations

import logging
import shutil
from dataclasses import dataclass
from pathlib import Path

from ..config import (
    DEFAULT_ARCHIVE_DIR,
    DEFAULT_BIOS_DIR,
    DEFAULT_NOTES_DIR,
    DEFAULT_ROSTER_HISTORY_PATH,
    DEFAULT_STRATEGY_DIR,
    DEFAULT_VODS_PATH,
    LEGACY_ARCHIVE_DIR,
    LEGACY_BIOS_DIR,
    LEGACY_NOTES_DIR,
    LEGACY_ROSTER_HISTORY_PATH,
    LEGACY_STRATEGY_DIR,
    LEGACY_VODS_PATH,
)

logger = logging.getLogger("valorant_analyst.server.persist_migrate")


@dataclass(frozen=True)
class _Target:
    label: str
    legacy: Path
    destination: Path
    is_dir: bool


_TARGETS: tuple[_Target, ...] = (
    _Target("strategy", LEGACY_STRATEGY_DIR, DEFAULT_STRATEGY_DIR, is_dir=True),
    _Target("notes", LEGACY_NOTES_DIR, DEFAULT_NOTES_DIR, is_dir=True),
    _Target("bios", LEGACY_BIOS_DIR, DEFAULT_BIOS_DIR, is_dir=True),
    _Target("vods", LEGACY_VODS_PATH, DEFAULT_VODS_PATH, is_dir=False),
    _Target(
        "roster_history",
        LEGACY_ROSTER_HISTORY_PATH,
        DEFAULT_ROSTER_HISTORY_PATH,
        is_dir=False,
    ),
    _Target("raw_archive", LEGACY_ARCHIVE_DIR, DEFAULT_ARCHIVE_DIR, is_dir=True),
)


def _dir_has_files(directory: Path) -> bool:
    if not directory.is_dir():
        return False
    return any(directory.iterdir())


def _migrate_one(target: _Target) -> int:
    """Migrate a single (legacy → destination) pair. Returns files copied.

    For directories we copy each *file* missing from the destination so a
    half-populated destination doesn't prevent us from picking up extra
    legacy files. For single-file targets we copy only when the destination
    doesn't exist yet (never overwrite live data).
    """
    if target.is_dir:
        if not target.legacy.is_dir():
            return 0
        target.destination.mkdir(parents=True, exist_ok=True)
        copied = 0
        for src in target.legacy.rglob("*"):
            if not src.is_file():
                continue
            rel = src.relative_to(target.legacy)
            dst = target.destination / rel
            if dst.exists():
                continue
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            copied += 1
        return copied

    if not target.legacy.is_file():
        return 0
    if target.destination.exists():
        return 0
    target.destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(target.legacy, target.destination)
    return 1


def migrate_legacy_data() -> dict[str, int]:
    """Migrate every known legacy path. Returns ``{label: files_copied}``.

    Always tries to migrate every target; failures on one don't block the
    others. Errors are logged but never raised — startup must not block on
    a bad migration.
    """
    report: dict[str, int] = {}
    for target in _TARGETS:
        try:
            n = _migrate_one(target)
        except Exception as exc:  # noqa: BLE001 - migration is best-effort
            logger.warning(
                "persist-migrate: %s failed (%s -> %s): %s",
                target.label,
                target.legacy,
                target.destination,
                exc,
            )
            continue
        report[target.label] = n
        if n > 0:
            logger.info(
                "persist-migrate: %s copied %d file(s) from %s to %s",
                target.label,
                n,
                target.legacy,
                target.destination,
            )
        elif target.is_dir and _dir_has_files(target.destination):
            logger.debug(
                "persist-migrate: %s already populated at %s — skipping",
                target.label,
                target.destination,
            )
    return report
