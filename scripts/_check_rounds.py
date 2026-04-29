import sys, duckdb
sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
con = duckdb.connect(r"d:\dev\valorant-premier-analyst\db\valorant.duckdb", read_only=True)

print("=== sample rounds (5 rows) ===")
for r in con.execute(
    "SELECT match_id, round_num, winning_team, end_type, bomb_planted, bomb_defused "
    "FROM rounds LIMIT 5"
).fetchall():
    print(r)

print("\n=== rounds count ===")
print(con.execute("SELECT COUNT(*) FROM rounds").fetchone())

# Check if we can derive ATK/DEF side from round data
# In Valorant, rounds 1-12 are typically the first half (one team attacks, other defends)
# After halftime, sides swap. Overtime rounds also alternate.
print("\n=== match rounds for 120pingがIGL ===")
rows = con.execute(
    "WITH om AS (SELECT mt.match_id, mt.team FROM match_teams mt "
    "WHERE mt.premier_team_name = '120pingがIGL' AND mt.premier_team_tag = '120') "
    "SELECT r.match_id, r.round_num, r.winning_team, om.team "
    "FROM rounds r JOIN om ON r.match_id = om.match_id "
    "LIMIT 20"
).fetchall()
for r in rows:
    print(r)
