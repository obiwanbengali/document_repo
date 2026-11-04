-- 09_data_quality.sql
-- Referential integrity and duplicate checks. Nothing here is filtered to hide a
-- problem; counts are reported as found.
--
-- Read-only.
--
-- Checks 'positive_jump_target_missing' and 'transfer_value_resolves_to_neither' are
-- NOT computed here. They are derived in Python from the 05/06 extracts so the jump
-- and transfer resolution rules live in exactly one place.
--
-- Note on 'triage_logic_question_id_not_in_tblTxQuestions': a large non-zero count is
-- EXPECTED and is not corruption. tblTriageLogic.QuestionID is a polymorphic node
-- reference which also addresses care advice (Cx) and disposition (Dx) nodes. The
-- check is therefore split by node prefix so the genuinely orphaned Tx references are
-- separable from the by-design non-Tx references.

-- name: data_quality
SELECT 'triage_logic_tx_question_not_catalogued' AS check_name,
       COUNT(*) AS affected_rows
FROM dbo.tblTriageLogic AS t
WHERE UPPER(LEFT(t.QuestionID, 2)) = 'TX'
  AND NOT EXISTS (SELECT 1 FROM dbo.tblTxQuestions AS q
                  WHERE UPPER(q.QuestionID) = UPPER(t.QuestionID))
UNION ALL
SELECT 'triage_logic_non_tx_node_reference',
       COUNT(*)
FROM dbo.tblTriageLogic AS t
WHERE UPPER(LEFT(t.QuestionID, 2)) <> 'TX'
UNION ALL
SELECT 'triage_logic_node_reference_unknown_prefix',
       COUNT(*)
FROM dbo.tblTriageLogic AS t
WHERE UPPER(LEFT(t.QuestionID, 2)) NOT IN ('TX', 'CX', 'DX')
UNION ALL
SELECT 'triage_logic_answer_not_catalogued_for_tx_question',
       COUNT(*)
FROM dbo.tblTriageLogic AS t
WHERE UPPER(LEFT(t.QuestionID, 2)) = 'TX'
  AND NOT EXISTS (SELECT 1 FROM dbo.tblTxAnswers AS a
                  WHERE UPPER(a.QuestionID) = UPPER(t.QuestionID)
                    AND a.AnswerNumber = CAST(t.AnswerNumber AS int))
UNION ALL
SELECT 'triage_logic_pathway_not_catalogued',
       COUNT(*)
FROM dbo.tblTriageLogic AS t
WHERE NOT EXISTS (SELECT 1 FROM dbo.tblPathways AS p
                  WHERE UPPER(p.PathwayID) = UPPER(t.PathwayID))
UNION ALL
SELECT 'duplicate_pathway_id',
       COALESCE(SUM(c), 0)
FROM (SELECT COUNT(*) AS c FROM dbo.tblPathways
      GROUP BY UPPER(PathwayID) HAVING COUNT(*) > 1) AS z
UNION ALL
SELECT 'duplicate_question_id',
       COALESCE(SUM(c), 0)
FROM (SELECT COUNT(*) AS c FROM dbo.tblTxQuestions
      GROUP BY UPPER(QuestionID) HAVING COUNT(*) > 1) AS z
UNION ALL
SELECT 'duplicate_question_answer_pair',
       COALESCE(SUM(c), 0)
FROM (SELECT COUNT(*) AS c FROM dbo.tblTxAnswers
      GROUP BY UPPER(QuestionID), AnswerNumber HAVING COUNT(*) > 1) AS z
UNION ALL
SELECT 'active_pathway_with_no_triage_logic',
       COUNT(*)
FROM dbo.tblPathways AS p
WHERE p.IsArchived = 0 AND p.FlagForDeletion = 0
  AND NOT EXISTS (SELECT 1 FROM dbo.tblTriageLogic AS t
                  WHERE UPPER(t.PathwayID) = UPPER(p.PathwayID))
UNION ALL
SELECT 'inactive_pathway_with_triage_logic',
       COUNT(*)
FROM dbo.tblPathways AS p
WHERE (p.IsArchived = 1 OR p.FlagForDeletion = 1)
  AND EXISTS (SELECT 1 FROM dbo.tblTriageLogic AS t
              WHERE UPPER(t.PathwayID) = UPPER(p.PathwayID))
UNION ALL
SELECT 'question_never_referenced',
       COUNT(*)
FROM dbo.tblTxQuestions AS q
WHERE NOT EXISTS (SELECT 1 FROM dbo.tblTriageLogic AS t
                  WHERE UPPER(t.QuestionID) = UPPER(q.QuestionID))
UNION ALL
SELECT 'active_question_never_referenced',
       COUNT(*)
FROM dbo.tblTxQuestions AS q
WHERE q.IsArchived = 0 AND q.FlagForDeletion = 0
  AND NOT EXISTS (SELECT 1 FROM dbo.tblTriageLogic AS t
                  WHERE UPPER(t.QuestionID) = UPPER(q.QuestionID))
UNION ALL
SELECT 'answer_never_referenced',
       COUNT(*)
FROM dbo.tblTxAnswers AS a
WHERE NOT EXISTS (SELECT 1 FROM dbo.tblTriageLogic AS t
                  WHERE UPPER(t.QuestionID) = UPPER(a.QuestionID)
                    AND CAST(t.AnswerNumber AS int) = a.AnswerNumber)
UNION ALL
SELECT 'active_pathway_referencing_archived_question',
       COUNT(*)
FROM dbo.tblTriageLogic AS t
JOIN dbo.tblPathways AS p    ON UPPER(p.PathwayID) = UPPER(t.PathwayID)
JOIN dbo.tblTxQuestions AS q ON UPPER(q.QuestionID) = UPPER(t.QuestionID)
WHERE p.IsArchived = 0 AND p.FlagForDeletion = 0
  AND (q.IsArchived = 1 OR q.FlagForDeletion = 1)
UNION ALL
SELECT 'pathway_with_null_symptom_group',
       COUNT(*)
FROM dbo.tblPathways AS p
WHERE p.SymptomGroupId IS NULL
UNION ALL
SELECT 'active_pathway_with_null_symptom_group',
       COUNT(*)
FROM dbo.tblPathways AS p
WHERE p.SymptomGroupId IS NULL AND p.IsArchived = 0 AND p.FlagForDeletion = 0
UNION ALL
SELECT 'pathway_symptom_group_not_catalogued',
       COUNT(*)
FROM dbo.tblPathways AS p
WHERE p.SymptomGroupId IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM dbo.tblSymptomGroups AS sg WHERE sg.SgId = p.SymptomGroupId)
UNION ALL
SELECT 'pathway_with_null_module',
       COUNT(*)
FROM dbo.tblPathways AS p WHERE p.Module IS NULL
UNION ALL
SELECT 'pathway_with_null_party',
       COUNT(*)
FROM dbo.tblPathways AS p WHERE p.Party IS NULL
UNION ALL
SELECT 'active_pathway_with_no_clinical_area',
       COUNT(*)
FROM dbo.tblPathways AS p
WHERE p.IsArchived = 0 AND p.FlagForDeletion = 0
  AND NOT EXISTS (SELECT 1 FROM dbo.tblPathway2ClinicalAreas AS pca
                  WHERE UPPER(pca.PathwayID) = UPPER(p.PathwayID))
UNION ALL
SELECT 'clinical_area_link_pathway_not_catalogued',
       COUNT(*)
FROM dbo.tblPathway2ClinicalAreas AS pca
WHERE NOT EXISTS (SELECT 1 FROM dbo.tblPathways AS p
                  WHERE UPPER(p.PathwayID) = UPPER(pca.PathwayID))
UNION ALL
SELECT 'answer_sd_id_not_catalogued',
       COUNT(*)
FROM dbo.tblTxAnswers AS a
WHERE a.SdId IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM dbo.tblSymptomDiscriminators AS sd WHERE sd.SdId = a.SdId)
UNION ALL
SELECT 'answer_snomed_answer_id_not_catalogued',
       COUNT(*)
FROM dbo.tblTxAnswerSnomeds AS s
WHERE NOT EXISTS (SELECT 1 FROM dbo.tblTxAnswers AS a WHERE a.AnswerID = s.AnswerID)
UNION ALL
SELECT 'disposition_dx_rank_not_catalogued',
       COUNT(*)
FROM dbo.tblDxDispositions AS d
WHERE NOT EXISTS (SELECT 1 FROM dbo.tblDxRank AS r WHERE r.DxRank = d.DxRank);

-- name: orphan_tx_question_detail
-- Detail rows for any Tx reference in triage logic with no catalogue entry.
SELECT
    UPPER(t.QuestionID)                AS question_key,
    COUNT(*)                           AS logic_row_count,
    COUNT(DISTINCT UPPER(t.PathwayID)) AS pathway_count
FROM dbo.tblTriageLogic AS t
WHERE UPPER(LEFT(t.QuestionID, 2)) = 'TX'
  AND NOT EXISTS (SELECT 1 FROM dbo.tblTxQuestions AS q
                  WHERE UPPER(q.QuestionID) = UPPER(t.QuestionID))
GROUP BY UPPER(t.QuestionID)
ORDER BY question_key;

-- name: node_prefix_distribution
-- Measured distribution of node-reference prefixes, case preserved, so the case
-- inconsistency in tblTriageLogic.QuestionID stays visible.
SELECT
    LEFT(t.QuestionID, 2) COLLATE Latin1_General_CS_AS AS node_prefix_case_sensitive,
    COUNT(*)                                           AS logic_row_count,
    COUNT(DISTINCT t.QuestionID)                       AS distinct_references
FROM dbo.tblTriageLogic AS t
GROUP BY LEFT(t.QuestionID, 2) COLLATE Latin1_General_CS_AS
ORDER BY node_prefix_case_sensitive;
