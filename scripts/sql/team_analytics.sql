-- Team analytics for DuckDB (valorant-premier-analyst)
-- Usage:
--   duckdb path/to/valorant.duckdb < scripts/sql/team_analytics.sql
--   or run sections in DuckDB CLI / DBeaver.

-- ---------------------------------------------------------------------------
-- 1) Premier identityごとの通算成績（name + tag で一意）
-- ---------------------------------------------------------------------------
SELECT
    premier_team_name,
    premier_team_tag,
    COUNT(*) AS games,
    SUM(CASE WHEN has_won THEN 1 ELSE 0 END) AS wins,
    SUM(CASE WHEN NOT has_won THEN 1 ELSE 0 END) AS losses,
    ROUND(
        100.0 * SUM(CASE WHEN has_won THEN 1 ELSE 0 END) / COUNT(*),
        1
    ) AS winrate_pct,
    ROUND(
        AVG(rounds_won * 1.0 / NULLIF(rounds_won + rounds_lost, 0)),
        3
    ) AS avg_round_share
FROM match_teams
WHERE premier_team_name IS NOT NULL
  AND premier_team_tag IS NOT NULL
  AND premier_team_name <> ''
GROUP BY premier_team_name, premier_team_tag
HAVING COUNT(*) >= 1
ORDER BY games DESC, winrate_pct DESC;

-- ---------------------------------------------------------------------------
-- 2) マップ別の勝率（試合単位）
-- ---------------------------------------------------------------------------
SELECT
    mt.premier_team_name,
    mt.premier_team_tag,
    m.map_name,
    COUNT(*) AS games,
    SUM(CASE WHEN mt.has_won THEN 1 ELSE 0 END) AS wins,
    ROUND(
        100.0 * SUM(CASE WHEN mt.has_won THEN 1 ELSE 0 END) / COUNT(*),
        1
    ) AS winrate_pct
FROM match_teams mt
JOIN matches m ON m.match_id = mt.match_id
WHERE mt.premier_team_name IS NOT NULL
  AND mt.premier_team_tag IS NOT NULL
GROUP BY
    mt.premier_team_name,
    mt.premier_team_tag,
    m.map_name
ORDER BY mt.premier_team_name, mt.premier_team_tag, games DESC;

-- ---------------------------------------------------------------------------
-- 3) チーム側の平均 K-D、ACS（ラウンドあたりスコア合計÷試合総ラウンド）
--    APIの /api/teams/.../stats と同系のロジック
-- ---------------------------------------------------------------------------
WITH side AS (
    SELECT
        match_id,
        team,
        premier_team_name,
        premier_team_tag
    FROM match_teams
    WHERE premier_team_name IS NOT NULL
),
match_rounds AS (
    SELECT match_id, SUM(rounds_won) AS total_rounds
    FROM match_teams
    GROUP BY match_id
)
SELECT
    s.premier_team_name,
    s.premier_team_tag,
    COUNT(DISTINCT mp.match_id) AS games,
    ROUND(AVG(mp.kills - mp.deaths), 2) AS avg_plus_minus,
    ROUND(AVG(mp.kills * 1.0 / NULLIF(mp.deaths, 0)), 2) AS avg_kd,
    ROUND(
        SUM(mp.score) * 1.0 / NULLIF(SUM(mr.total_rounds), 0),
        1
    ) AS team_avg_acs_per_round
FROM match_players mp
JOIN side s
    ON mp.match_id = s.match_id
   AND mp.team = s.team
JOIN match_rounds mr ON mr.match_id = mp.match_id
GROUP BY s.premier_team_name, s.premier_team_tag
ORDER BY games DESC;

-- ---------------------------------------------------------------------------
-- 4) 対戦相手の頭取り（特定チーム向け: リテラルを差し替え）
-- ---------------------------------------------------------------------------
-- WITH ours AS (
--     SELECT match_id, team
--     FROM match_teams
--     WHERE premier_team_name = 'YourTeamName'
--       AND premier_team_tag = 'TAG'
-- ),
-- opp AS (
--     SELECT mt.match_id, mt.premier_team_name, mt.premier_team_tag, mt.has_won
--     FROM match_teams mt
--     JOIN ours o ON o.match_id = mt.match_id AND mt.team <> o.team
-- )
-- SELECT
--     premier_team_name,
--     premier_team_tag,
--     COUNT(*) AS games,
--     SUM(CASE WHEN has_won THEN 1 ELSE 0 END) AS their_wins,
--     SUM(CASE WHEN NOT has_won THEN 1 ELSE 0 END) AS our_wins
-- FROM opp
-- WHERE premier_team_name IS NOT NULL
-- GROUP BY 1, 2
-- ORDER BY games DESC;
