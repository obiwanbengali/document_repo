-- 08_snomed_analysis.sql
-- SNOMED concept reach per pathway.
--
-- Read-only.
--
-- Chain: tblTriageLogic -> tblTxAnswers (QuestionID + AnswerNumber) -> tblTxAnswerSnomeds
-- (AnswerID). Only the stored assignment is used; no clinical meaning is inferred from
-- the concept, its preferred term or its semantic tag.

-- name: pathway_snomed
SELECT
    UPPER(t.PathwayID)                  AS pathway_key,
    s.SnomedConceptId                   AS snomed_concept_id,
    -- Case-sensitive MIN for determinism under the CI collation (see 03_question_reuse).
    MIN(s.SnomedPreferredTerm COLLATE Latin1_General_CS_AS) AS snomed_preferred_term,
    MIN(s.SnomedSemanticTag COLLATE Latin1_General_CS_AS)   AS snomed_semantic_tag,
    COUNT(*)                            AS logic_row_count,
    COUNT(DISTINCT UPPER(t.QuestionID)) AS question_count,
    COUNT(DISTINCT s.AnswerID)          AS answer_count
FROM dbo.tblTriageLogic AS t
JOIN dbo.tblTxAnswers AS a
      ON UPPER(a.QuestionID) = UPPER(t.QuestionID)
     AND a.AnswerNumber      = CAST(t.AnswerNumber AS int)
JOIN dbo.tblTxAnswerSnomeds AS s
      ON s.AnswerID = a.AnswerID
GROUP BY UPPER(t.PathwayID), s.SnomedConceptId;

-- name: snomed_catalogue
SELECT
    s.SnomedConceptId          AS snomed_concept_id,
    MIN(s.SnomedPreferredTerm COLLATE Latin1_General_CS_AS) AS snomed_preferred_term,
    MIN(s.SnomedSemanticTag COLLATE Latin1_General_CS_AS)   AS snomed_semantic_tag,
    COUNT(*)                   AS assignment_count,
    COUNT(DISTINCT s.AnswerID) AS answer_count
FROM dbo.tblTxAnswerSnomeds AS s
GROUP BY s.SnomedConceptId;
