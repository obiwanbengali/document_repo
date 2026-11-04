-- 02_pathway_complexity.sql
-- Per-pathway structural complexity measured directly from dbo.tblTriageLogic.
--
-- Read-only.
--
-- Branching factor
-- ----------------
-- Each (PathwayID, OrderNumber) pair was verified to carry exactly one distinct
-- QuestionID, so an order position is a single decision node. The branching factor of
-- a position is therefore its number of distinct AnswerNumber values. avg/max are
-- taken over the positions of the pathway.
--
-- Node kinds
-- ----------
-- QuestionID is a polymorphic node reference (Tx = triage question, Cx = care advice,
-- Dx = disposition). Counts are reported per kind rather than collapsed, because only
-- Tx nodes are answerable triage questions.

-- name: pathway_complexity
WITH positions AS (
    SELECT
        UPPER(t.PathwayID)                AS pathway_key,
        t.OrderNumber                     AS order_number,
        MIN(UPPER(t.QuestionID))          AS question_key,
        MIN(UPPER(LEFT(t.QuestionID, 2))) AS node_prefix,
        COUNT(DISTINCT t.AnswerNumber)    AS branch_count,
        COUNT(*)                          AS row_count
    FROM dbo.tblTriageLogic AS t
    GROUP BY UPPER(t.PathwayID), t.OrderNumber
),
position_rollup AS (
    SELECT
        pathway_key,
        COUNT(*)                                          AS logic_position_count,
        SUM(row_count)                                    AS logic_row_count,
        SUM(branch_count)                                 AS answer_transition_count,
        CAST(AVG(CAST(branch_count AS float)) AS float)   AS avg_branches_per_position,
        MAX(branch_count)                                 AS max_branches_per_position,
        MIN(branch_count)                                 AS min_branches_per_position,
        COUNT(DISTINCT CASE WHEN node_prefix = 'TX' THEN question_key END)
                                                          AS question_count,
        COUNT(DISTINCT CASE WHEN node_prefix = 'CX' THEN question_key END)
                                                          AS care_advice_node_count,
        COUNT(DISTINCT CASE WHEN node_prefix = 'DX' THEN question_key END)
                                                          AS disposition_node_count,
        COUNT(DISTINCT question_key)                      AS distinct_node_count,
        MIN(order_number)                                 AS min_order_number,
        MAX(order_number)                                 AS max_order_number
    FROM positions
    GROUP BY pathway_key
),
jump_rollup AS (
    SELECT
        UPPER(t.PathwayID) AS pathway_key,
        SUM(CASE WHEN t.JumpID  > 0 THEN 1 ELSE 0 END) AS positive_jump_count,
        SUM(CASE WHEN t.JumpID  = 0 THEN 1 ELSE 0 END) AS zero_jump_count,
        SUM(CASE WHEN t.JumpID = -1 THEN 1 ELSE 0 END) AS jump_minus_one_count,
        SUM(CASE WHEN t.JumpID  < -1 THEN 1 ELSE 0 END) AS special_negative_jump_count
    FROM dbo.tblTriageLogic AS t
    GROUP BY UPPER(t.PathwayID)
)
SELECT
    r.pathway_key,
    r.question_count,
    r.care_advice_node_count,
    r.disposition_node_count,
    r.distinct_node_count,
    r.logic_position_count,
    r.logic_row_count,
    r.answer_transition_count,
    r.avg_branches_per_position,
    r.max_branches_per_position,
    r.min_branches_per_position,
    r.min_order_number,
    r.max_order_number,
    j.positive_jump_count,
    j.zero_jump_count,
    j.jump_minus_one_count,
    j.special_negative_jump_count
FROM position_rollup AS r
JOIN jump_rollup     AS j ON j.pathway_key = r.pathway_key;
