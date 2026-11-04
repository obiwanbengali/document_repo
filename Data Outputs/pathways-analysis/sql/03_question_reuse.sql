-- 03_question_reuse.sql
-- Reuse of node references across pathways.
--
-- Read-only.
--
-- One row per distinct upper-cased node reference appearing in dbo.tblTriageLogic,
-- plus (via the second query) any catalogued question that never appears in triage
-- logic at all. node_kind distinguishes Tx questions from Cx care advice and Dx
-- disposition references, which share the same column.
--
-- answer_cardinality is the number of rows in dbo.tblTxAnswers for the question and
-- is NULL for non-Tx references, which have no answer catalogue.

-- name: question_reuse
WITH usage AS (
    SELECT
        UPPER(t.QuestionID)                          AS question_key,
        -- Case-sensitive MIN: under the database's CI collation 'TX1' and 'Tx1' compare
        -- equal, so a plain MIN() picks between them arbitrarily and the exported value
        -- changes between runs. Forcing CS makes the choice deterministic.
        MIN(t.QuestionID COLLATE Latin1_General_CS_AS) AS question_id_sample,
        CASE UPPER(LEFT(MIN(t.QuestionID COLLATE Latin1_General_CS_AS), 2))
             WHEN 'TX' THEN 'question'
             WHEN 'CX' THEN 'care_advice'
             WHEN 'DX' THEN 'disposition'
             ELSE 'other'
        END                                          AS node_kind,
        COUNT(DISTINCT UPPER(t.PathwayID))           AS pathway_count,
        COUNT(*)                                     AS logic_row_count,
        COUNT(DISTINCT CAST(UPPER(t.PathwayID) AS nvarchar(50))
              + '#' + CAST(t.OrderNumber AS nvarchar(20)))
                                                     AS position_count,
        COUNT(DISTINCT t.AnswerNumber)               AS distinct_answer_numbers_used
    FROM dbo.tblTriageLogic AS t
    GROUP BY UPPER(t.QuestionID)
),
answer_counts AS (
    SELECT UPPER(a.QuestionID) AS question_key, COUNT(*) AS answer_cardinality
    FROM dbo.tblTxAnswers AS a
    GROUP BY UPPER(a.QuestionID)
)
SELECT
    u.question_key,
    u.question_id_sample,
    u.node_kind,
    q.QuestionID            AS catalogued_question_id,
    q.ControlType           AS control_type,
    q.IsArchived            AS question_is_archived,
    q.FlagForDeletion       AS question_flag_for_deletion,
    ac.answer_cardinality,
    u.pathway_count,
    u.logic_row_count,
    u.position_count,
    u.distinct_answer_numbers_used
FROM usage AS u
LEFT JOIN dbo.tblTxQuestions AS q  ON UPPER(q.QuestionID) = u.question_key
LEFT JOIN answer_counts      AS ac ON ac.question_key     = u.question_key;

-- name: unreferenced_questions
-- Catalogued Tx questions with no row anywhere in dbo.tblTriageLogic.
SELECT
    q.QuestionID        AS question_id,
    UPPER(q.QuestionID) AS question_key,
    q.ControlType       AS control_type,
    q.IsArchived        AS is_archived,
    q.FlagForDeletion   AS flag_for_deletion
FROM dbo.tblTxQuestions AS q
WHERE NOT EXISTS (
    SELECT 1 FROM dbo.tblTriageLogic AS t
    WHERE UPPER(t.QuestionID) = UPPER(q.QuestionID)
)
ORDER BY question_key;

-- name: unreferenced_answers
-- Catalogued answers whose (QuestionID, AnswerNumber) pair is never used in triage logic.
SELECT
    a.AnswerID          AS answer_id,
    a.QuestionID        AS question_id,
    UPPER(a.QuestionID) AS question_key,
    a.AnswerNumber      AS answer_number,
    a.SdId              AS sd_id
FROM dbo.tblTxAnswers AS a
WHERE NOT EXISTS (
    SELECT 1 FROM dbo.tblTriageLogic AS t
    WHERE UPPER(t.QuestionID) = UPPER(a.QuestionID)
      AND CAST(t.AnswerNumber AS int) = a.AnswerNumber
)
ORDER BY question_key, answer_number;
