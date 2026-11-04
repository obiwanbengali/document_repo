-- 10_family_overlap.sql
-- Phase 2: server-side overlap precursors for the NHS-native groupings.
--
-- Read-only. No DDL, no DML.
--
-- Why these exist alongside the Python overlap matrix
-- ---------------------------------------------------
-- family_overlap.py computes overlap for every candidate family set using boolean
-- matrix products, which is the only practical way to cover 15 candidate strategies.
-- These queries compute the same quantity for two NHS-native groupings directly in
-- SQL. The runner compares the two results and reports any divergence, so the matrix
-- implementation is checked against the database rather than trusted.
--
-- Scope: active pathways only (IsArchived = 0 AND FlagForDeletion = 0), matching the
-- Phase 2 family-membership scope.

-- name: symptom_group_pair_shared_discriminators
-- Symptom-group pairs that share at least one symptom discriminator, where a
-- discriminator belongs to a symptom group because one of that group's active
-- pathways offers an answer carrying it (the Phase 1 pathway -> SD derivation).
WITH sg_sd AS (
    SELECT DISTINCT
        p.SymptomGroupId AS sg_id,
        a.SdId           AS sd_id
    FROM dbo.tblPathways AS p
    JOIN dbo.tblTriageLogic AS t
          ON UPPER(t.PathwayID) = UPPER(p.PathwayID)
    JOIN dbo.tblTxAnswers AS a
          ON UPPER(a.QuestionID) = UPPER(t.QuestionID)
         AND a.AnswerNumber      = CAST(t.AnswerNumber AS int)
    WHERE p.IsArchived = 0
      AND p.FlagForDeletion = 0
      AND p.SymptomGroupId IS NOT NULL
      AND a.SdId IS NOT NULL
),
sizes AS (
    SELECT sg_id, COUNT(*) AS sd_count FROM sg_sd GROUP BY sg_id
)
SELECT
    l.sg_id                                   AS sg_id_a,
    r.sg_id                                   AS sg_id_b,
    sa.sd_count                               AS sd_count_a,
    sb.sd_count                               AS sd_count_b,
    COUNT(*)                                  AS shared_sd_count,
    sa.sd_count + sb.sd_count - COUNT(*)      AS union_sd_count
FROM sg_sd AS l
JOIN sg_sd AS r
      ON r.sd_id = l.sd_id
     AND r.sg_id > l.sg_id
JOIN sizes AS sa ON sa.sg_id = l.sg_id
JOIN sizes AS sb ON sb.sg_id = r.sg_id
GROUP BY l.sg_id, r.sg_id, sa.sd_count, sb.sd_count;

-- name: clinical_area_pair_shared_pathways
-- Clinical areas are an OVERLAPPING grouping: 126 active pathways map to more than
-- one (Phase 1 finding). Shared pathway counts between area pairs quantify that
-- overlap directly, which is the one overlap signal the Python matrix cannot be
-- cross-checked against by feature sets alone.
WITH links AS (
    SELECT DISTINCT
        pca.ClinicalAreaID   AS clinical_area_id,
        UPPER(pca.PathwayID) AS pathway_key
    FROM dbo.tblPathway2ClinicalAreas AS pca
    JOIN dbo.tblPathways AS p
          ON UPPER(p.PathwayID) = UPPER(pca.PathwayID)
    WHERE p.IsArchived = 0
      AND p.FlagForDeletion = 0
),
sizes AS (
    SELECT clinical_area_id, COUNT(*) AS pathway_count FROM links GROUP BY clinical_area_id
)
SELECT
    l.clinical_area_id                                       AS clinical_area_id_a,
    r.clinical_area_id                                       AS clinical_area_id_b,
    sa.pathway_count                                         AS pathway_count_a,
    sb.pathway_count                                         AS pathway_count_b,
    COUNT(*)                                                 AS shared_pathway_count,
    sa.pathway_count + sb.pathway_count - COUNT(*)           AS union_pathway_count
FROM links AS l
JOIN links AS r
      ON r.pathway_key = l.pathway_key
     AND r.clinical_area_id > l.clinical_area_id
JOIN sizes AS sa ON sa.clinical_area_id = l.clinical_area_id
JOIN sizes AS sb ON sb.clinical_area_id = r.clinical_area_id
GROUP BY l.clinical_area_id, r.clinical_area_id, sa.pathway_count, sb.pathway_count;

-- name: symptom_group_pair_shared_questions
-- Symptom-group pairs sharing at least one Tx triage question. Cx care-advice and Dx
-- disposition node references are excluded: only Tx nodes are answerable questions
-- and therefore candidate Bayesian variables.
WITH sg_question AS (
    SELECT DISTINCT
        p.SymptomGroupId    AS sg_id,
        UPPER(t.QuestionID) AS question_key
    FROM dbo.tblPathways AS p
    JOIN dbo.tblTriageLogic AS t
          ON UPPER(t.PathwayID) = UPPER(p.PathwayID)
    WHERE p.IsArchived = 0
      AND p.FlagForDeletion = 0
      AND p.SymptomGroupId IS NOT NULL
      AND UPPER(LEFT(t.QuestionID, 2)) = 'TX'
),
sizes AS (
    SELECT sg_id, COUNT(*) AS question_count FROM sg_question GROUP BY sg_id
)
SELECT
    l.sg_id                                              AS sg_id_a,
    r.sg_id                                              AS sg_id_b,
    sa.question_count                                    AS question_count_a,
    sb.question_count                                    AS question_count_b,
    COUNT(*)                                             AS shared_question_count,
    sa.question_count + sb.question_count - COUNT(*)     AS union_question_count
FROM sg_question AS l
JOIN sg_question AS r
      ON r.question_key = l.question_key
     AND r.sg_id > l.sg_id
JOIN sizes AS sa ON sa.sg_id = l.sg_id
JOIN sizes AS sb ON sb.sg_id = r.sg_id
GROUP BY l.sg_id, r.sg_id, sa.question_count, sb.question_count;
