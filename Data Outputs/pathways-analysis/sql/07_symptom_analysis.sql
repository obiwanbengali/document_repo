-- 07_symptom_analysis.sql
-- Symptom group and symptom discriminator structure.
--
-- Read-only.
--
-- Pathway -> symptom discriminator is derived by joining triage logic to the answer
-- catalogue on (QuestionID, AnswerNumber) and taking the answer's SdId, as specified.
-- Note the join is on the answer the pathway can actually select, so a discriminator
-- counts towards a pathway only where that pathway offers an answer carrying it.
--
-- The join upper-cases QuestionID on both sides: tblTriageLogic stores 'TX...' and
-- 'Tx...' for the same question while tblTxAnswers stores only 'Tx...'.

-- name: pathway_discriminators
SELECT
    UPPER(t.PathwayID)             AS pathway_key,
    a.SdId                         AS sd_id,
    COUNT(*)                       AS logic_row_count,
    COUNT(DISTINCT UPPER(t.QuestionID)) AS question_count
FROM dbo.tblTriageLogic AS t
JOIN dbo.tblTxAnswers AS a
      ON UPPER(a.QuestionID) = UPPER(t.QuestionID)
     AND a.AnswerNumber      = CAST(t.AnswerNumber AS int)
WHERE a.SdId IS NOT NULL
GROUP BY UPPER(t.PathwayID), a.SdId;

-- name: symptom_group_discriminator_counts
SELECT
    c.SgId                  AS sg_id,
    COUNT(*)                AS combination_count,
    SUM(CASE WHEN c.Active = 1 THEN 1 ELSE 0 END) AS active_combination_count,
    COUNT(DISTINCT c.SdId)  AS discriminator_count
FROM dbo.tblSymptomGroupDiscCombinations AS c
GROUP BY c.SgId;

-- name: answers_with_discriminators
-- Coverage of SdId across the answer catalogue, to show how much of the discriminator
-- catalogue is reachable through answers at all.
SELECT
    COUNT(*)                                                   AS answers_total,
    SUM(CASE WHEN SdId IS NULL THEN 0 ELSE 1 END)              AS answers_with_sd_id,
    COUNT(DISTINCT SdId)                                       AS distinct_sd_ids_on_answers
FROM dbo.tblTxAnswers;
