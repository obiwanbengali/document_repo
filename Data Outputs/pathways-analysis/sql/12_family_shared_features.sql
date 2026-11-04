-- 12_family_shared_features.sql
-- Phase 2: how widely each feature is shared across pathways.
--
-- Read-only. No DDL, no DML.
--
-- Section 10 of Phase 2 asks how many candidate FAMILIES use each question, symptom
-- discriminator, SNOMED concept and disposition. Family membership is a Python-side
-- construct, so the family counts cannot be computed here. What SQL can supply
-- authoritatively is the pathway count per feature, which is both the denominator for
-- those family counts and an independent check on the Python feature maps.
--
-- Scope: active pathways only, matching the Phase 2 family-membership scope. This is
-- narrower than the Phase 1 reuse tables (question_reuse.csv, discriminator_reuse.csv,
-- snomed_reuse.csv), which count over every pathway present in triage logic. The two
-- are therefore expected to differ, and the runner reports the difference rather than
-- treating either as wrong.

-- name: feature_pathway_counts
-- Long format so a new feature type can be added without changing the consumer.
--
-- feature_type values:
--   question    -- Tx triage question referenced by the pathway's triage logic
--   sd          -- symptom discriminator reachable through an answer the pathway offers
--   snomed      -- SNOMED concept assigned to an answer the pathway offers
--   disposition -- disposition code reachable by a T1..T4 transfer, or present as a
--                  Dx node in the pathway's own logic (the two routes are unioned,
--                  because both make the disposition part of the pathway's outcome set)
WITH active_pathways AS (
    SELECT UPPER(p.PathwayID) AS pathway_key
    FROM dbo.tblPathways AS p
    WHERE p.IsArchived = 0 AND p.FlagForDeletion = 0
),
question_map AS (
    SELECT DISTINCT UPPER(t.PathwayID) AS pathway_key, UPPER(t.QuestionID) AS feature_id
    FROM dbo.tblTriageLogic AS t
    WHERE UPPER(LEFT(t.QuestionID, 2)) = 'TX'
),
sd_map AS (
    SELECT DISTINCT UPPER(t.PathwayID) AS pathway_key, CAST(a.SdId AS varchar(32)) AS feature_id
    FROM dbo.tblTriageLogic AS t
    JOIN dbo.tblTxAnswers AS a
          ON UPPER(a.QuestionID) = UPPER(t.QuestionID)
         AND a.AnswerNumber      = CAST(t.AnswerNumber AS int)
    WHERE a.SdId IS NOT NULL
),
snomed_map AS (
    SELECT DISTINCT UPPER(t.PathwayID) AS pathway_key,
                    CAST(s.SnomedConceptId AS varchar(32)) AS feature_id
    FROM dbo.tblTriageLogic AS t
    JOIN dbo.tblTxAnswers AS a
          ON UPPER(a.QuestionID) = UPPER(t.QuestionID)
         AND a.AnswerNumber      = CAST(t.AnswerNumber AS int)
    JOIN dbo.tblTxAnswerSnomeds AS s
          ON s.AnswerID = a.AnswerID
),
disposition_transfer_map AS (
    SELECT DISTINCT
        UPPER(t.PathwayID)       AS pathway_key,
        UPPER(d.DispositionCode) AS feature_id
    FROM dbo.tblTriageLogic AS t
    CROSS APPLY (VALUES (t.T1), (t.T2), (t.T3), (t.T4)) AS x(transfer_value)
    JOIN dbo.tblDxDispositions AS d
          ON UPPER(d.DispositionCode) = UPPER(LTRIM(RTRIM(x.transfer_value)))
    WHERE x.transfer_value IS NOT NULL
      AND LTRIM(RTRIM(x.transfer_value)) <> ''
      AND CHARINDEX('.', x.transfer_value) = 0
),
disposition_node_map AS (
    SELECT DISTINCT
        UPPER(t.PathwayID)       AS pathway_key,
        UPPER(d.DispositionCode) AS feature_id
    FROM dbo.tblTriageLogic AS t
    JOIN dbo.tblDxDispositions AS d
          ON UPPER(d.DispositionID) = UPPER(t.QuestionID)
    WHERE UPPER(LEFT(t.QuestionID, 2)) = 'DX'
),
disposition_map AS (
    SELECT pathway_key, feature_id FROM disposition_transfer_map
    UNION
    SELECT pathway_key, feature_id FROM disposition_node_map
),
combined AS (
    SELECT 'question'    AS feature_type, pathway_key, feature_id FROM question_map
    UNION ALL
    SELECT 'sd',                          pathway_key, feature_id FROM sd_map
    UNION ALL
    SELECT 'snomed',                      pathway_key, feature_id FROM snomed_map
    UNION ALL
    SELECT 'disposition',                 pathway_key, feature_id FROM disposition_map
)
SELECT
    c.feature_type,
    c.feature_id,
    COUNT(DISTINCT c.pathway_key) AS pathway_count
FROM combined AS c
JOIN active_pathways AS ap
      ON ap.pathway_key = c.pathway_key
GROUP BY c.feature_type, c.feature_id;

-- name: disposition_catalogue
-- Disposition reference data for labelling the shared-feature and shared-core tables.
-- DxRank is exported because disposition rank is the Pathways notion of clinical
-- acuity ordering; no clinical meaning is inferred from it here.
SELECT
    d.DispositionID            AS disposition_id,
    UPPER(d.DispositionID)     AS disposition_id_key,
    d.DispositionCode          AS disposition_code,
    UPPER(d.DispositionCode)   AS disposition_code_key,
    d.DispositionText          AS disposition_text,
    d.DxRank                   AS dx_rank,
    r.DxText                   AS dx_rank_text,
    d.IsArchived               AS is_archived,
    d.FlagForDeletion          AS flag_for_deletion,
    CAST(CASE WHEN d.IsArchived = 0 AND d.FlagForDeletion = 0
              THEN 1 ELSE 0 END AS bit) AS is_active
FROM dbo.tblDxDispositions AS d
LEFT JOIN dbo.tblDxRank AS r
       ON r.DxRank = d.DxRank;
