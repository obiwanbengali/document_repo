-- 05_jump_analysis.sql
-- Profile and classify every JumpID value. Nothing is assumed to be a graph edge.
--
-- Read-only.
--
-- Observed classification in this dataset (measured, not assumed):
--   JumpID  > 0  intra-pathway jump to that OrderNumber in the SAME pathway.
--   JumpID  = 0  present (2 rows) and NOT documented in the Pathways spec supplied.
--                Carries no T-field payload. Reported as unexpected.
--   JumpID = -1  T1..T4 carry EITHER a disposition code OR a dotted
--                '<PathwayID>.<OrderNumber>' pathway transfer. Both occur.
--   JumpID = -3  T1..T4 carry dotted pathway transfers (all rows populated).
--   JumpID = -6  T1..T4 carry dotted pathway transfers (all rows populated).
--   JumpID in (-2,-4,-5,-9)  control behaviour with NO T-field payload, therefore
--                not resolvable to any target from this table alone.

-- name: jump_distribution
SELECT
    t.JumpID AS jump_id,
    CASE
        WHEN t.JumpID > 0  THEN 'positive_intra_pathway_jump'
        WHEN t.JumpID = 0  THEN 'zero_unexpected'
        WHEN t.JumpID = -1 THEN 'transfer_or_disposition'
        ELSE 'special_negative_control'
    END AS jump_class,
    COUNT(*)                          AS row_count,
    COUNT(DISTINCT UPPER(t.PathwayID)) AS pathway_count,
    SUM(CASE WHEN t.T1 IS NOT NULL AND LTRIM(RTRIM(t.T1)) <> '' THEN 1 ELSE 0 END) AS t1_populated,
    SUM(CASE WHEN t.T2 IS NOT NULL AND LTRIM(RTRIM(t.T2)) <> '' THEN 1 ELSE 0 END) AS t2_populated,
    SUM(CASE WHEN t.T3 IS NOT NULL AND LTRIM(RTRIM(t.T3)) <> '' THEN 1 ELSE 0 END) AS t3_populated,
    SUM(CASE WHEN t.T4 IS NOT NULL AND LTRIM(RTRIM(t.T4)) <> '' THEN 1 ELSE 0 END) AS t4_populated
FROM dbo.tblTriageLogic AS t
GROUP BY t.JumpID;

-- name: positive_jumps
-- Source/target order positions for every intra-pathway jump, with resolvability
-- against the set of order positions that actually exist in the same pathway.
WITH existing_positions AS (
    SELECT DISTINCT UPPER(PathwayID) AS pathway_key, OrderNumber
    FROM dbo.tblTriageLogic
)
SELECT
    t.TriageLogicID          AS triage_logic_id,
    UPPER(t.PathwayID)       AS pathway_key,
    t.OrderNumber            AS source_order,
    UPPER(t.QuestionID)      AS question_key,
    CAST(t.AnswerNumber AS int) AS answer_number,
    t.JumpID                 AS target_order,
    t.JumpID - t.OrderNumber AS jump_distance,
    CASE WHEN t.JumpID > t.OrderNumber THEN 'forward'
         WHEN t.JumpID < t.OrderNumber THEN 'backward'
         ELSE 'self' END     AS jump_direction,
    CAST(CASE WHEN ep.OrderNumber IS NULL THEN 0 ELSE 1 END AS bit) AS target_resolved
FROM dbo.tblTriageLogic AS t
LEFT JOIN existing_positions AS ep
       ON ep.pathway_key = UPPER(t.PathwayID)
      AND ep.OrderNumber = t.JumpID
WHERE t.JumpID > 0;
