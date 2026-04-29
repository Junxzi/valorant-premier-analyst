"""DuckDB persistence helpers."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import duckdb
import pandas as pd


def _validate_identifier(name: str, label: str) -> None:
    if not isinstance(name, str) or not name.isidentifier():
        raise ValueError(
            f"{label} must be a valid SQL identifier, got: {name!r}"
        )


def save_dataframe_to_duckdb(
    df: pd.DataFrame,
    db_path: Path,
    table_name: str,
) -> None:
    """Replace *table_name* in the DuckDB file at *db_path* with *df*.

    Kept for one-shot exports; the incremental ingestion path uses
    :func:`upsert_dataframe` instead.
    """
    _validate_identifier(table_name, "table_name")

    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    con = duckdb.connect(str(db_path))
    try:
        con.register("__df", df)
        con.execute(f'CREATE OR REPLACE TABLE "{table_name}" AS SELECT * FROM __df')
        con.unregister("__df")
    finally:
        con.close()


@dataclass(frozen=True)
class UpsertResult:
    """Outcome of an :func:`upsert_dataframe` call."""

    table: str
    inserted: int
    skipped: int

    @property
    def total(self) -> int:
        return self.inserted + self.skipped


def upsert_dataframe(
    df: pd.DataFrame,
    db_path: Path,
    table_name: str,
    key_columns: Sequence[str],
) -> UpsertResult:
    """Insert rows from *df* into *table_name*, skipping existing keys.

    The table is created on first use using *df*'s schema. Subsequent calls
    only insert rows whose ``key_columns`` tuple is not already present in
    the table — this is the building block of the incremental data pipeline.

    Returns counts so the CLI can report ``inserted`` / ``skipped`` numbers.
    """
    _validate_identifier(table_name, "table_name")
    if not key_columns:
        raise ValueError("key_columns must contain at least one column.")
    for col in key_columns:
        _validate_identifier(col, "key column")

    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    if df is None or df.empty:
        return UpsertResult(table=table_name, inserted=0, skipped=0)

    missing = [c for c in key_columns if c not in df.columns]
    if missing:
        raise ValueError(
            f"DataFrame is missing key column(s) for upsert into "
            f"{table_name!r}: {missing}"
        )

    df_in = df.copy()
    df_in = df_in.dropna(subset=list(key_columns))
    if df_in.empty:
        return UpsertResult(table=table_name, inserted=0, skipped=int(len(df)))

    df_in = df_in.drop_duplicates(subset=list(key_columns), keep="last")
    incoming_total = int(len(df_in))

    con = duckdb.connect(str(db_path))
    try:
        con.register("__incoming", df_in)
        con.execute(
            f'CREATE TABLE IF NOT EXISTS "{table_name}" AS '
            f"SELECT * FROM __incoming WHERE 1=0"
        )

        join_cond = " AND ".join(
            f't."{c}" = n."{c}"' for c in key_columns
        )
        before = con.execute(
            f'SELECT COUNT(*) FROM "{table_name}"'
        ).fetchone()[0]
        con.execute(
            f'INSERT INTO "{table_name}" '
            f"SELECT n.* FROM __incoming n "
            f'WHERE NOT EXISTS (SELECT 1 FROM "{table_name}" t WHERE {join_cond})'
        )
        after = con.execute(
            f'SELECT COUNT(*) FROM "{table_name}"'
        ).fetchone()[0]
        con.unregister("__incoming")
    finally:
        con.close()

    inserted = int(after - before)
    skipped = incoming_total - inserted
    return UpsertResult(table=table_name, inserted=inserted, skipped=skipped)


def drop_table_if_exists(db_path: Path, table_name: str) -> None:
    """Drop *table_name* from the DuckDB file if it exists."""
    _validate_identifier(table_name, "table_name")
    db_path = Path(db_path)
    if not db_path.exists():
        return
    con = duckdb.connect(str(db_path))
    try:
        con.execute(f'DROP TABLE IF EXISTS "{table_name}"')
    finally:
        con.close()


def table_row_count(db_path: Path, table_name: str) -> int:
    """Return the number of rows in *table_name*, or 0 if the table is absent."""
    _validate_identifier(table_name, "table_name")
    db_path = Path(db_path)
    if not db_path.exists():
        return 0

    con = duckdb.connect(str(db_path), read_only=True)
    try:
        exists = con.execute(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_name = ? LIMIT 1",
            [table_name],
        ).fetchone()
        if not exists:
            return 0
        return int(
            con.execute(f'SELECT COUNT(*) FROM "{table_name}"').fetchone()[0]
        )
    finally:
        con.close()
