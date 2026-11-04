-- 11_family_transitions.sql
-- Phase 2: pathway-to-pathway transitions, computed server-side.
--
-- Read-only. No DDL, no DML.
--
-- Relationship to Phase 1
-- -----------------------
-- Phase 1 derives the pathway graph in Python from the row-level transfer_values
-- extract (sql/06_transfer_analysis.sql) via graph.aggregate_pathway_edges. Phase 2
-- depends on that graph for every cohesion, boundary and routing metric, so the edge
-- list is re-computed here independently in SQL and the runner asserts the two agree.
-- A silent divergence between the two would invalidate every family metric downstream.
--
-- The value grammar is the one established in Phase 1 (see 06_transfer_analysis.sql):
-- a T1..T4 value containing '.' is '<PathwayID>.<OrderNumber>' and denotes a pathway
-- transfer. Values with no '.' are disposition codes and are not pathway edges.
--
-- transition_count counts branch slots, matching Phase 1: one answer offering the same
-- target on all four T slots contributes 4.

-- name: pathway_transition_edges
WITH unpivoted AS (
    SELECT
        UPPER(t.PathwayID)          AS source_pathway_key,
        t.OrderNumber               AS source_order,
        UPPER(t.QuestionID)         AS question_key,
        CAST(t.AnswerNumber AS int) AS answer_number,
        x.branch,
        LTRIM(RTRIM(x.transfer_value)) AS transfer_value
    FROM dbo.tblTriageLogic AS t
    CROSS APPLY (VALUES ('T1', t.T1), ('T2', t.T2), ('T3', t.T3), ('T4', t.T4))
        AS x(branch, transfer_value)
    WHERE x.transfer_value IS NOT NULL
      AND LTRIM(RTRIM(x.transfer_value)) <> ''
      AND CHARINDEX('.', x.transfer_value) > 0
),
candidates AS (
    SELECT
        u.source_pathway_key,
        u.source_order,
        u.question_key,
        u.answer_number,
        u.branch,
        UPPER(LEFT(u.transfer_value, CHARINDEX('.', u.transfer_value) - 1))
            AS candidate_pathway_key
    FROM unpivoted AS u
)
SELECT
    c.source_pathway_key,
    c.candidate_pathway_key                                AS target_pathway_key,
    COUNT(*)                                               AS transition_count,
    COUNT(DISTINCT c.question_key + '|'
                   + CAST(c.answer_number AS varchar(12)) + '|' + c.branch) AS branches,
    COUNT(DISTINCT c.question_key + '|'
                   + CAST(c.answer_number AS varchar(12)))  AS answer_branches,
    COUNT(DISTINCT c.question_key)                         AS source_question_count,
    COUNT(DISTINCT c.source_order)                         AS source_order_count
FROM candidates AS c
JOIN dbo.tblPathways AS p
      ON UPPER(p.PathwayID) = c.candidate_pathway_key
GROUP BY c.source_pathway_key, c.candidate_pathway_key;

-- name: symptom_group_transition_matrix
-- Transitions aggregated to the NHS-native symptom-group grouping, over active
-- pathways at both ends. Pathways with a NULL SymptomGroupId (150 active ones in this
-- snapshot) cannot be placed in this matrix and are excluded rather than bucketed,
-- so the row totals here are deliberately smaller than the pathway-level totals.
WITH unpivoted AS (
    SELECT
        UPPER(t.PathwayID)             AS source_pathway_key,
        LTRIM(RTRIM(x.transfer_value)) AS transfer_value
    FROM dbo.tblTriageLogic AS t
    CROSS APPLY (VALUES ('T1', t.T1), ('T2', t.T2), ('T3', t.T3), ('T4', t.T4))
        AS x(branch, transfer_value)
    WHERE x.transfer_value IS NOT NULL
      AND LTRIM(RTRIM(x.transfer_value)) <> ''
      AND CHARINDEX('.', x.transfer_value) > 0
),
edges AS (
    SELECT
        u.source_pathway_key,
        UPPER(LEFT(u.transfer_value, CHARINDEX('.', u.transfer_value) - 1))
            AS target_pathway_key
    FROM unpivoted AS u
)
SELECT
    sp.SymptomGroupId                          AS source_sg_id,
    tp.SymptomGroupId                          AS target_sg_id,
    COUNT(*)                                   AS transition_count,
    COUNT(DISTINCT e.source_pathway_key)       AS source_pathway_count,
    COUNT(DISTINCT e.target_pathway_key)       AS target_pathway_count,
    CAST(CASE WHEN sp.SymptomGroupId = tp.SymptomGroupId THEN 1 ELSE 0 END AS bit)
                                               AS is_internal
FROM edges AS e
JOIN dbo.tblPathways AS sp
      ON UPPER(sp.PathwayID) = e.source_pathway_key
JOIN dbo.tblPathways AS tp
      ON UPPER(tp.PathwayID) = e.target_pathway_key
WHERE sp.IsArchived = 0 AND sp.FlagForDeletion = 0
  AND tp.IsArchived = 0 AND tp.FlagForDeletion = 0
  AND sp.SymptomGroupId IS NOT NULL
  AND tp.SymptomGroupId IS NOT NULL
GROUP BY sp.SymptomGroupId, tp.SymptomGroupId;
