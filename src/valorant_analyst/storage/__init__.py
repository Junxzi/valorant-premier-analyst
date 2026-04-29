"""Persistence helpers (raw files and DuckDB)."""

from .duckdb_store import (
    UpsertResult,
    save_dataframe_to_duckdb,
    table_row_count,
    upsert_dataframe,
)
from .raw_store import (
    archive_matches,
    archived_match_ids,
    iter_archived_matches,
    load_archive_as_payload,
    load_raw_json,
    save_match_archive,
    save_raw_json,
)

__all__ = [
    "UpsertResult",
    "archive_matches",
    "archived_match_ids",
    "iter_archived_matches",
    "load_archive_as_payload",
    "load_raw_json",
    "save_dataframe_to_duckdb",
    "save_match_archive",
    "save_raw_json",
    "table_row_count",
    "upsert_dataframe",
]
