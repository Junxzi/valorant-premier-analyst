import sys
import duckdb

sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
con = duckdb.connect(r"d:\dev\valorant-premier-analyst\db\valorant.duckdb", read_only=True)

print("=== DESCRIBE match_teams ===")
for row in con.execute("DESCRIBE match_teams").fetchall():
    print(row)

print("\n=== sample match_teams (premier_team cols) ===")
for row in con.execute(
    "SELECT match_id, team, premier_team_id, premier_team_name, premier_team_tag "
    "FROM match_teams LIMIT 10"
).fetchall():
    print(row)
