"""Verify the name backfill SQL the matches route uses."""

from __future__ import annotations

from pathlib import Path

import duckdb

DB = Path(__file__).resolve().parents[1] / "db" / "valorant.duckdb"
con = duckdb.connect(str(DB), read_only=True)
match_id = "5bf67597-831d-41a9-a92e-f3b2e69bf172"

print("--- raw players in anonymized match ---")
for r in con.execute(
    'SELECT puuid, name, tag, team, agent FROM "match_players" '
    'WHERE match_id = ? ORDER BY score DESC',
    [match_id],
).fetchall():
    print(f"  puuid={r[0][:8]} name={r[1]!r} tag={r[2]!r} team={r[3]} agent={r[4]}")

print("\n--- known names from other matches for the same puuids ---")
for r in con.execute(
    """
    SELECT puuid,
           ANY_VALUE(name) FILTER (WHERE name IS NOT NULL AND name <> '') AS name,
           ANY_VALUE(tag)  FILTER (WHERE tag  IS NOT NULL AND tag  <> '') AS tag,
           COUNT(*)        AS rows,
           SUM(CASE WHEN name IS NOT NULL AND name <> '' THEN 1 ELSE 0 END) AS named_rows
    FROM "match_players"
    GROUP BY puuid
    HAVING puuid IN (
        SELECT puuid FROM "match_players" WHERE match_id = ?
    )
    """,
    [match_id],
).fetchall():
    print(f"  puuid={r[0][:8]} name={r[1]!r} tag={r[2]!r} rows={r[3]} named={r[4]}")

print("\n--- combined backfill query result ---")
for r in con.execute(
    """
    WITH known AS (
        SELECT puuid,
               ANY_VALUE(name) FILTER (
                   WHERE name IS NOT NULL AND name <> ''
               ) AS name,
               ANY_VALUE(tag) FILTER (
                   WHERE tag IS NOT NULL AND tag <> ''
               ) AS tag
        FROM "match_players"
        GROUP BY puuid
    )
    SELECT mp.puuid,
           COALESCE(NULLIF(mp.name, ''), k.name) AS name,
           COALESCE(NULLIF(mp.tag,  ''), k.tag)  AS tag,
           mp.team, mp.agent
    FROM "match_players" mp
    LEFT JOIN known k ON k.puuid = mp.puuid
    WHERE mp.match_id = ?
    ORDER BY mp.score DESC NULLS LAST
    """,
    [match_id],
).fetchall():
    print(f"  puuid={r[0][:8]} name={r[1]!r} tag={r[2]!r}")
