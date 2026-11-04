-- 00_reference_data.sql
-- Reference/dimension extracts for the Pathways structural analysis workbench.
--
-- Read-only. No DDL, no DML.
--
-- Named query blocks are separated by lines of the form:
--   -- name: <query_name>
-- The loader in src/pathways_analysis/db.py splits on these markers.
--
-- ID case normalisation
-- --------------------
-- TriageDB uses collation Latin1_General_CI_AS, so SQL joins on PathwayID /
-- QuestionID are case-insensitive. tblTriageLogic stores the same logical
-- QuestionID with inconsistent prefix case ('TX100001' and 'Tx100001').
-- pandas joins are case-sensitive, so every extract exposes an explicit
-- upper-cased join key (*_key) alongside the canonical stored value.

-- name: pathways
SELECT
    p.PathwayID                              AS pathway_id,
    UPPER(p.PathwayID)                       AS pathway_key,
    p.PathwayTitle                           AS pathway_title,
    p.PathwayVersionNo                       AS pathway_version_no,
    p.PathwayStatusId                        AS pathway_status_id,
    p.SymptomGroupId                         AS symptom_group_id,
    p.Party                                  AS party,
    p.Module                                 AS module,
    p.IsArchived                             AS is_archived,
    p.FlagForDeletion                        AS flag_for_deletion,
    CAST(CASE WHEN p.IsArchived = 0 AND p.FlagForDeletion = 0
              THEN 1 ELSE 0 END AS bit)      AS is_active
FROM dbo.tblPathways AS p;

-- name: questions
SELECT
    q.QuestionID                             AS question_id,
    UPPER(q.QuestionID)                      AS question_key,
    q.ControlType                            AS control_type,
    q.IsArchived                             AS is_archived,
    q.FlagForDeletion                        AS flag_for_deletion,
    CAST(CASE WHEN q.IsArchived = 0 AND q.FlagForDeletion = 0
              THEN 1 ELSE 0 END AS bit)      AS is_active
FROM dbo.tblTxQuestions AS q;

-- name: answers
SELECT
    a.AnswerID                               AS answer_id,
    a.QuestionID                             AS question_id,
    UPPER(a.QuestionID)                      AS question_key,
    a.AnswerNumber                           AS answer_number,
    a.Positive                               AS positive,
    a.SystemFlag                             AS system_flag,
    a.SdId                                   AS sd_id
FROM dbo.tblTxAnswers AS a;

-- name: dispositions
SELECT
    d.DispositionID                          AS disposition_id,
    UPPER(d.DispositionID)                   AS disposition_id_key,
    d.DispositionCode                        AS disposition_code,
    UPPER(d.DispositionCode)                 AS disposition_code_key,
    d.DispositionText                        AS disposition_text,
    d.DxRank                                 AS dx_rank,
    d.IsArchived                             AS is_archived,
    d.FlagForDeletion                        AS flag_for_deletion,
    CAST(CASE WHEN d.IsArchived = 0 AND d.FlagForDeletion = 0
              THEN 1 ELSE 0 END AS bit)      AS is_active
FROM dbo.tblDxDispositions AS d;

-- name: symptom_groups
SELECT
    sg.SgId                                  AS sg_id,
    sg.SgDesc                                AS sg_desc,
    sg.Active                                AS active,
    sg.IsArchived                            AS is_archived
FROM dbo.tblSymptomGroups AS sg;

-- name: symptom_discriminators
SELECT
    sd.SdId                                  AS sd_id,
    sd.SdDesc                                AS sd_desc,
    sd.Active                                AS active,
    sd.IsArchived                            AS is_archived
FROM dbo.tblSymptomDiscriminators AS sd;

-- name: symptom_group_disc_combinations
SELECT
    c.SgId                                   AS sg_id,
    c.SdId                                   AS sd_id,
    c.Active                                 AS active
FROM dbo.tblSymptomGroupDiscCombinations AS c;

-- name: clinical_areas
SELECT
    ca.ClinicalAreaID                        AS clinical_area_id,
    ca.ClinicalAreaDescription               AS clinical_area_description,
    ca.AreaGroup                             AS area_group
FROM dbo.tblClinicalAreas AS ca;

-- name: pathway_clinical_areas
SELECT
    pca.PathwayID                            AS pathway_id,
    UPPER(pca.PathwayID)                     AS pathway_key,
    pca.ClinicalAreaID                       AS clinical_area_id
FROM dbo.tblPathway2ClinicalAreas AS pca;

-- name: answer_snomeds
SELECT
    s.AnswerID                               AS answer_id,
    s.SnomedConceptId                        AS snomed_concept_id,
    s.SnomedPreferredTerm                    AS snomed_preferred_term,
    s.AssignmentType                         AS assignment_type,
    s.SnomedSemanticTag                      AS snomed_semantic_tag
FROM dbo.tblTxAnswerSnomeds AS s;

-- name: dx_rank
SELECT
    r.DxRank                                 AS dx_rank,
    r.DxText                                 AS dx_text
FROM dbo.tblDxRank AS r;

-- name: triage_logic
-- Full triage logic fact table (140,669 rows).
--
-- node_kind classifies the polymorphic QuestionID reference. tblTriageLogic.QuestionID
-- does NOT always point at tblTxQuestions: it addresses whichever node type sits at
-- that order position. Observed prefixes are Tx (triage question), Cx (care advice)
-- and Dx (disposition). Classification is by stored prefix only; no clinical meaning
-- is inferred.
SELECT
    t.TriageLogicID                          AS triage_logic_id,
    t.PathwayID                              AS pathway_id,
    UPPER(t.PathwayID)                       AS pathway_key,
    t.OrderNumber                            AS order_number,
    t.QuestionID                             AS question_id,
    UPPER(t.QuestionID)                      AS question_key,
    CAST(t.AnswerNumber AS int)              AS answer_number,
    t.JumpID                                 AS jump_id,
    t.T1                                     AS t1,
    t.T2                                     AS t2,
    t.T3                                     AS t3,
    t.T4                                     AS t4,
    t.Rank                                   AS rank_value,
    CASE UPPER(LEFT(t.QuestionID, 2))
         WHEN 'TX' THEN 'question'
         WHEN 'CX' THEN 'care_advice'
         WHEN 'DX' THEN 'disposition'
         ELSE 'other'
    END                                      AS node_kind
FROM dbo.tblTriageLogic AS t;
