"""Read/write helpers for raw JSON payloads."""

from __future__ import annotations

import json
import re
from collections.abc import Iterator
from pathlib import Path
from typing import Any

_SAFE_ID = re.compile(r"[^A-Za-z0-9._-]+")


def save_raw_json(data: dict[str, Any], output_path: Path) -> None:
    """Persist *data* as pretty-printed UTF-8 JSON.

    Creates parent directories as needed. Non-ASCII characters are preserved.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)


def load_raw_json(input_path: Path) -> dict[str, Any]:
    """Load a JSON file previously produced by :func:`save_raw_json`."""
    input_path = Path(input_path)
    if not input_path.exists():
        raise FileNotFoundError(
            f"Raw JSON not found: {input_path}. "
            "Run the `fetch` command first to download match data."
        )
    with input_path.open("r", encoding="utf-8") as fh:
        payload = json.load(fh)
    if not isinstance(payload, dict):
        raise ValueError(
            f"Expected a JSON object at {input_path}, got {type(payload).__name__}."
        )
    return payload


def _safe_filename_part(value: str) -> str:
    cleaned = _SAFE_ID.sub("_", value).strip("._-")
    return cleaned or "unknown"


def _extract_match_id(match: dict[str, Any]) -> str | None:
    metadata = match.get("metadata") or {}
    if not isinstance(metadata, dict):
        return None
    for key in ("matchid", "match_id", "id"):
        value = metadata.get(key)
        if value:
            return str(value)
    return None


def archive_matches(payload: dict[str, Any], archive_dir: Path) -> list[Path]:
    """Write each match in *payload* to ``{archive_dir}/{match_id}.json``.

    The per-match archive is the durable source of truth for the data pipeline:
    even if DuckDB is rebuilt or wiped, every historical match can be replayed
    by walking this directory. Existing files are overwritten so re-fetching
    the same match is idempotent.

    Matches without a usable id are skipped. Returns the list of files that
    were (re)written this call.
    """
    archive_dir = Path(archive_dir)
    archive_dir.mkdir(parents=True, exist_ok=True)

    written: list[Path] = []
    data = payload.get("data") if isinstance(payload, dict) else None
    if isinstance(data, dict):
        data = [data]
    if not isinstance(data, list):
        return written

    for match in data:
        if not isinstance(match, dict):
            continue
        match_id = _extract_match_id(match)
        if not match_id:
            continue
        filename = f"{_safe_filename_part(match_id)}.json"
        path = archive_dir / filename
        with path.open("w", encoding="utf-8") as fh:
            json.dump(match, fh, ensure_ascii=False, indent=2)
        written.append(path)

    return written


def iter_archived_matches(archive_dir: Path) -> Iterator[dict[str, Any]]:
    """Yield each match dict stored under *archive_dir* (sorted by filename)."""
    archive_dir = Path(archive_dir)
    if not archive_dir.exists():
        return
    for path in sorted(archive_dir.glob("*.json")):
        try:
            with path.open("r", encoding="utf-8") as fh:
                match = json.load(fh)
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(match, dict):
            yield match


def archived_match_ids(archive_dir: Path) -> set[str]:
    """Return the set of match ids already on disk under *archive_dir*.

    The CLI uses this to skip matches that have already been pulled, so a
    ``backfill`` command can be re-run safely without re-downloading.
    """
    archive_dir = Path(archive_dir)
    if not archive_dir.exists():
        return set()
    return {p.stem for p in archive_dir.glob("*.json")}


def save_match_archive(match: dict[str, Any], archive_dir: Path) -> Path | None:
    """Write a single match dict to ``{archive_dir}/{match_id}.json``.

    Returns the path written, or ``None`` if the dict has no usable id.
    """
    if not isinstance(match, dict):
        return None
    match_id = _extract_match_id(match)
    if not match_id:
        return None
    archive_dir = Path(archive_dir)
    archive_dir.mkdir(parents=True, exist_ok=True)
    path = archive_dir / f"{_safe_filename_part(match_id)}.json"
    with path.open("w", encoding="utf-8") as fh:
        json.dump(match, fh, ensure_ascii=False, indent=2)
    return path


def load_archive_as_payload(archive_dir: Path) -> dict[str, Any]:
    """Load every archived match into a single ``{"data": [...]}`` payload.

    This lets the rest of the pipeline (normalize, ingest) consume the archive
    using the exact same shape as a live HenrikDev API response.
    """
    matches = list(iter_archived_matches(archive_dir))
    return {"status": 200, "data": matches}
