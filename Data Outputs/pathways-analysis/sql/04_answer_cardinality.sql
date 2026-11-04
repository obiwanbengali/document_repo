-- 04_answer_cardinality.sql
-- Answer cardinality per question. Feeds Bayesian CPT sizing in Phase 2.
--
-- Read-only.
--
-- Two different cardinalities matter and are both returned:
--   catalogue_answer_count -- rows in dbo.tblTxAnswers for the question. This is the
--                             state space of the variable as authored.
--   used_answer_count      -- distinct AnswerNumber values the question actually
--                             exercises anywhere in dbo.tblTriageLogic.
-- They diverge when a pathway uses only part of a question's answer set, which changes
-- CPT sizing materially, so neither is collapsed into the other.

-- name: answer_cardinality
WITH catalogue AS (
    SELECT UPPER(a.QuestionID) AS question_key, COUNT(*) AS catalogue_answer_count
    FROM dbo.tblTxAnswers AS a
    GROUP BY UPPER(a.QuestionID)
),
used AS (
    SELECT UPPER(t.QuestionID) AS question_key,
           COUNT(DISTINCT t.AnswerNumber) AS used_answer_count
    FROM dbo.tblTriageLogic AS t
    GROUP BY UPPER(t.QuestionID)
)
SELECT
    q.QuestionID                          AS question_id,
    UPPER(q.QuestionID)                   AS question_key,
    q.ControlType                         AS control_type,
    q.IsArchived                          AS is_archived,
    q.FlagForDeletion                     AS flag_for_deletion,
    CAST(CASE WHEN q.IsArchived = 0 AND q.FlagForDeletion = 0
              THEN 1 ELSE 0 END AS bit)   AS is_active,
    COALESCE(c.catalogue_answer_count, 0) AS catalogue_answer_count,
    COALESCE(u.used_answer_count, 0)      AS used_answer_count
FROM dbo.tblTxQuestions AS q
LEFT JOIN catalogue AS c ON c.question_key = UPPER(q.QuestionID)
LEFT JOIN used      AS u ON u.question_key = UPPER(q.QuestionID);

-- name: control_types
SELECT
    ct.ControlType AS control_type,
    ct.Description AS control_type_desc
FROM dbo.tblTxQuestionControlTypes AS ct;
