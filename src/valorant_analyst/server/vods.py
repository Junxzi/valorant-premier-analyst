"""Optional VOD URLs keyed by match_id (Henrik UUID), stored as ``data/vods.json``.

Format: ``{"<match_uuid>": "https://..." , ... }``
"""

from __future__ import annotations

import json

from ..config import DEFAULT_VODS_PATH

VODS_PATH = DEFAULT_VODS_PATH


def load_vods() -> dict[str, str]:
    """Return match_id → URL. Empty dict if file missing or invalid.

    Reads from disk each call so edits to ``vods.json`` apply without restarting
    the server (file is tiny).
    """
    if not VODS_PATH.is_file():
        return {}
    try:
        raw = json.loads(VODS_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(raw, dict):
        return {}
    out: dict[str, str] = {}
    for k, v in raw.items():
        if isinstance(k, str) and isinstance(v, str) and v.strip():
            out[k] = v.strip()
    return out


def vod_url_for(match_id: str) -> str | None:
    return load_vods().get(match_id)


def _normalize_incoming(raw: dict[str, str]) -> dict[str, str]:
    """Strip keys/values; keep only non-empty http(s) URLs."""
    out: dict[str, str] = {}
    for k, v in raw.items():
        if not isinstance(k, str):
            continue
        kk = k.strip()
        if not kk:
            continue
        if not isinstance(v, str):
            continue
        vv = v.strip()
        if not vv:
            continue
        if not (vv.startswith("http://") or vv.startswith("https://")):
            msg = f"URL must start with http:// or https:// (key {kk[:12]}…)"
            raise ValueError(msg)
        out[kk] = vv
    return out


def save_vods(raw: dict[str, str]) -> dict[str, str]:
    """Validate, write atomically, return persisted mapping."""
    urls = _normalize_incoming(raw)
    VODS_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = VODS_PATH.with_suffix(".json.tmp")
    payload = json.dumps(urls, ensure_ascii=False, indent=2) + "\n"
    tmp.write_text(payload, encoding="utf-8")
    tmp.replace(VODS_PATH)
    return urls
