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
from .roster_history import (
    ROSTER_HISTORY_FILENAME,
    MemberRecord,
    MergeReport,
    RosterHistory,
    TeamHistory,
    all_members,
    current_members,
    load_roster_history,
    member_records,
    merge_team_members,
    save_roster_history,
)

__all__ = [
    "ROSTER_HISTORY_FILENAME",
    "MemberRecord",
    "MergeReport",
    "RosterHistory",
    "TeamHistory",
    "UpsertResult",
    "all_members",
    "archive_matches",
    "archived_match_ids",
    "current_members",
    "iter_archived_matches",
    "load_archive_as_payload",
    "load_raw_json",
    "load_roster_history",
    "member_records",
    "merge_team_members",
    "save_dataframe_to_duckdb",
    "save_match_archive",
    "save_raw_json",
    "save_roster_history",
    "table_row_count",
    "upsert_dataframe",
]
