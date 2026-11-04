-- 13_phase3_sizing.sql
-- Read-only inputs for Phase 3A representation sizing.
--
-- These queries do not create a Bayesian DAG. They expose the structural units needed
-- to size the three declared representations.

-- name: phase3_active_tx_occurrences
SELECT DISTINCT
    UPPER(t.PathwayID) AS pathway_key,
    t.OrderNumber      AS order_number,
    UPPER(t.QuestionID) AS question_key,
    COALESCE(ac.catalogue_answer_count, 0) AS state_cardinality
FROM dbo.tblTriageLogic AS t
JOIN dbo.tblPathways AS p
  ON UPPER(p.PathwayID) = UPPER(t.PathwayID)
LEFT JOIN (
    SELECT UPPER(a.QuestionID) AS question_key,
           COUNT(*) AS catalogue_answer_count
    FROM dbo.tblTxAnswers AS a
    GROUP BY UPPER(a.QuestionID)
) AS ac
  ON ac.question_key = UPPER(t.QuestionID)
WHERE p.IsArchived = 0
  AND p.FlagForDeletion = 0
  AND UPPER(LEFT(t.QuestionID, 2)) = 'TX';

-- name: phase3_active_question_catalogue
SELECT
    UPPER(t.QuestionID) AS question_key,
    COUNT(DISTINCT UPPER(t.PathwayID)) AS pathway_count,
    COUNT(DISTINCT CAST(UPPER(t.PathwayID) AS nvarchar(50))
          + '#' + CAST(t.OrderNumber AS nvarchar(20))) AS occurrence_count,
    COALESCE(ac.catalogue_answer_count, 0) AS state_cardinality
FROM dbo.tblTriageLogic AS t
JOIN dbo.tblPathways AS p
  ON UPPER(p.PathwayID) = UPPER(t.PathwayID)
LEFT JOIN (
    SELECT UPPER(a.QuestionID) AS question_key,
           COUNT(*) AS catalogue_answer_count
    FROM dbo.tblTxAnswers AS a
    GROUP BY UPPER(a.QuestionID)
) AS ac
  ON ac.question_key = UPPER(t.QuestionID)
WHERE p.IsArchived = 0
  AND p.FlagForDeletion = 0
  AND UPPER(LEFT(t.QuestionID, 2)) = 'TX'
GROUP BY UPPER(t.QuestionID), ac.catalogue_answer_count;
