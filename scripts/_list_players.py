import sys
import duckdb

sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
con = duckdb.connect(r"d:\dev\valorant-premier-analyst\db\valorant.duckdb", read_only=True)
rows = con.execute(
    "SELECT puuid, "
    "ANY_VALUE(name) FILTER (WHERE name IS NOT NULL AND name <> '') AS name, "
    "ANY_VALUE(tag)  FILTER (WHERE tag  IS NOT NULL AND tag  <> '') AS tag "
    "FROM match_players GROUP BY puuid ORDER BY name"
).fetchall()
for r in rows:
    print(r[0], repr(r[1]), repr(r[2]))
