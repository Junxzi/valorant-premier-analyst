"""Shared FastAPI dependencies (DuckDB connection management)."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import duckdb
from fastapi import HTTPException

from ..config import DEFAULT_DB_PATH


def db_path() -> Path:
    """Override target via dependency_overrides in tests."""
    return DEFAULT_DB_PATH


@contextmanager
def open_duckdb(path: Path) -> Iterator[duckdb.DuckDBPyConnection]:
    """Open a read-only DuckDB connection with friendly errors for the API."""
    if not path.exists():
        raise HTTPException(
            status_code=503,
            detail=(
                f"DuckDB not built yet at {path}. "
                "Run `valorant-analyst ingest --from-archive` first."
            ),
        )
    con = duckdb.connect(str(path), read_only=True)
    try:
        yield con
    finally:
        con.close()
