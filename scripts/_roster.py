import sys, duckdb
sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
con = duckdb.connect(r"d:\dev\valorant-premier-analyst\db\valorant.duckdb", read_only=True)
rows = con.execute(
    "WITH om AS (SELECT match_id, team FROM match_teams "
    "WHERE premier_team_name = '120pingがIGL' AND premier_team_tag = '120') "
    "SELECT mp.puuid, "
    "ANY_VALUE(mp.name) FILTER (WHERE mp.name IS NOT NULL AND mp.name <> '') AS name, "
    "COUNT(DISTINCT mp.match_id) AS games "
    "FROM match_players mp JOIN om ON mp.match_id = om.match_id AND mp.team = om.team "
    "GROUP BY mp.puuid ORDER BY games DESC"
).fetchall()
for r in rows:
    print(r)
