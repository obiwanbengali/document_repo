-- 06_transfer_analysis.sql
-- Unpivot T1..T4 into a normalised transfer structure and resolve each value against
-- the pathway and disposition catalogues.
--
-- Read-only.
--
-- Deliberately NOT filtered to JumpID = -1. Every row carrying a non-empty T value is
-- unpivoted so that which JumpID values actually carry a payload is a measured
-- result rather than an input assumption. (In this dataset that is -1, -3 and -6.)
--
-- Value grammar, established by profiling rather than assumed:
--   '<PathwayID>.<OrderNumber>'  pathway transfer, e.g. 'PA25.3900'
--   '<DispositionCode>'          disposition,      e.g. 'Dx02'
-- No PathwayID and no DispositionCode in this database contains a '.', so splitting on
-- the first '.' is unambiguous. Values are upper-cased before resolution because both
-- tblTriageLogic and the T fields use inconsistent prefix case ('PA25', 'pa25', 'Pw1').
--
-- resolution is left as separate boolean columns rather than a single verdict so that
-- the "both" and "neither" cases stay visible to the caller.

-- name: transfer_values
WITH unpivoted AS (
    SELECT
        t.TriageLogicID             AS triage_logic_id,
        t.PathwayID                 AS source_pathway_id,
        UPPER(t.PathwayID)          AS source_pathway_key,
        t.OrderNumber               AS source_order,
        t.QuestionID                AS question_id,
        UPPER(t.QuestionID)         AS question_key,
        CAST(t.AnswerNumber AS int) AS answer_number,
        t.JumpID                    AS jump_id,
        t.Rank                      AS rank_value,
        x.branch,
        LTRIM(RTRIM(x.transfer_value)) AS transfer_value
    FROM dbo.tblTriageLogic AS t
    CROSS APPLY (VALUES ('T1', t.T1), ('T2', t.T2), ('T3', t.T3), ('T4', t.T4))
        AS x(branch, transfer_value)
    WHERE x.transfer_value IS NOT NULL
      AND LTRIM(RTRIM(x.transfer_value)) <> ''
),
split AS (
    SELECT
        u.triage_logic_id,
        u.source_pathway_id,
        u.source_pathway_key,
        u.source_order,
        u.question_id,
        u.question_key,
        u.answer_number,
        u.jump_id,
        u.rank_value,
        u.branch,
        u.transfer_value,
        UPPER(u.transfer_value) AS transfer_value_key,
        CASE WHEN CHARINDEX('.', u.transfer_value) > 0 THEN 1 ELSE 0 END AS has_dot,
        CASE WHEN CHARINDEX('.', u.transfer_value) > 0
             THEN UPPER(LEFT(u.transfer_value, CHARINDEX('.', u.transfer_value) - 1))
             ELSE UPPER(u.transfer_value)
        END AS candidate_pathway_key,
        CASE WHEN CHARINDEX('.', u.transfer_value) > 0
             THEN SUBSTRING(u.transfer_value,
                            CHARINDEX('.', u.transfer_value) + 1,
                            LEN(u.transfer_value))
        END AS candidate_order_text
    FROM unpivoted AS u
),
existing_positions AS (
    SELECT DISTINCT UPPER(PathwayID) AS pathway_key, OrderNumber
    FROM dbo.tblTriageLogic
)
SELECT
    s.triage_logic_id,
    s.source_pathway_id,
    s.source_pathway_key,
    s.source_order,
    s.question_id,
    s.question_key,
    s.answer_number,
    s.jump_id,
    s.rank_value,
    s.branch,
    s.transfer_value,
    s.transfer_value_key,
    s.has_dot,
    s.candidate_pathway_key,
    s.candidate_order_text,
    TRY_CONVERT(int, s.candidate_order_text)                      AS candidate_order_number,
    p.PathwayID                                                   AS resolved_pathway_id,
    CAST(CASE WHEN p.PathwayID IS NULL THEN 0 ELSE 1 END AS bit)  AS resolves_pathway,
    p.IsArchived                                                  AS target_pathway_is_archived,
    p.FlagForDeletion                                             AS target_pathway_flag_for_deletion,
    dc.DispositionCode                                            AS resolved_disposition_code,
    dc.DispositionID                                              AS resolved_disposition_id_via_code,
    CAST(CASE WHEN dc.DispositionCode IS NULL THEN 0 ELSE 1 END AS bit) AS resolves_disposition_code,
    di.DispositionID                                              AS resolved_disposition_id,
    CAST(CASE WHEN di.DispositionID IS NULL THEN 0 ELSE 1 END AS bit)   AS resolves_disposition_id,
    CAST(CASE WHEN ep.OrderNumber IS NULL THEN 0 ELSE 1 END AS bit)     AS target_order_resolved
FROM split AS s
LEFT JOIN dbo.tblPathways AS p
       ON UPPER(p.PathwayID) = s.candidate_pathway_key
LEFT JOIN dbo.tblDxDispositions AS dc
       ON UPPER(dc.DispositionCode) = s.transfer_value_key
LEFT JOIN dbo.tblDxDispositions AS di
       ON UPPER(di.DispositionID) = s.transfer_value_key
LEFT JOIN existing_positions AS ep
       ON ep.pathway_key = s.candidate_pathway_key
      AND ep.OrderNumber = TRY_CONVERT(int, s.candidate_order_text);


-- name: transfer_values_for_source_pathway
-- Same resolution semantics as transfer_values, but scoped to one source pathway.
-- Used by focused family reports so they do not materialise the whole transfer estate.
WITH unpivoted AS (
    SELECT
        t.TriageLogicID             AS triage_logic_id,
        t.PathwayID                 AS source_pathway_id,
        UPPER(t.PathwayID)          AS source_pathway_key,
        t.OrderNumber               AS source_order,
        t.QuestionID                AS question_id,
        UPPER(t.QuestionID)         AS question_key,
        CAST(t.AnswerNumber AS int) AS answer_number,
        t.JumpID                    AS jump_id,
        t.Rank                      AS rank_value,
        x.branch,
        LTRIM(RTRIM(x.transfer_value)) AS transfer_value
    FROM dbo.tblTriageLogic AS t
    CROSS APPLY (VALUES ('T1', t.T1), ('T2', t.T2), ('T3', t.T3), ('T4', t.T4))
        AS x(branch, transfer_value)
    WHERE UPPER(t.PathwayID) = :source_pathway_key
      AND x.transfer_value IS NOT NULL
      AND LTRIM(RTRIM(x.transfer_value)) <> ''
),
split AS (
    SELECT
        u.triage_logic_id,
        u.source_pathway_id,
        u.source_pathway_key,
        u.source_order,
        u.question_id,
        u.question_key,
        u.answer_number,
        u.jump_id,
        u.rank_value,
        u.branch,
        u.transfer_value,
        UPPER(u.transfer_value) AS transfer_value_key,
        CASE WHEN CHARINDEX('.', u.transfer_value) > 0 THEN 1 ELSE 0 END AS has_dot,
        CASE WHEN CHARINDEX('.', u.transfer_value) > 0
             THEN UPPER(LEFT(u.transfer_value, CHARINDEX('.', u.transfer_value) - 1))
             ELSE UPPER(u.transfer_value)
        END AS candidate_pathway_key,
        CASE WHEN CHARINDEX('.', u.transfer_value) > 0
             THEN SUBSTRING(u.transfer_value,
                            CHARINDEX('.', u.transfer_value) + 1,
                            LEN(u.transfer_value))
        END AS candidate_order_text
    FROM unpivoted AS u
),
existing_positions AS (
    SELECT DISTINCT UPPER(PathwayID) AS pathway_key, OrderNumber
    FROM dbo.tblTriageLogic
)
SELECT
    s.triage_logic_id,
    s.source_pathway_id,
    s.source_pathway_key,
    s.source_order,
    s.question_id,
    s.question_key,
    s.answer_number,
    s.jump_id,
    s.rank_value,
    s.branch,
    s.transfer_value,
    s.transfer_value_key,
    s.has_dot,
    s.candidate_pathway_key,
    s.candidate_order_text,
    TRY_CONVERT(int, s.candidate_order_text)                      AS candidate_order_number,
    p.PathwayID                                                   AS resolved_pathway_id,
    CAST(CASE WHEN p.PathwayID IS NULL THEN 0 ELSE 1 END AS bit)  AS resolves_pathway,
    p.IsArchived                                                  AS target_pathway_is_archived,
    p.FlagForDeletion                                             AS target_pathway_flag_for_deletion,
    dc.DispositionCode                                            AS resolved_disposition_code,
    dc.DispositionID                                              AS resolved_disposition_id_via_code,
    CAST(CASE WHEN dc.DispositionCode IS NULL THEN 0 ELSE 1 END AS bit) AS resolves_disposition_code,
    di.DispositionID                                              AS resolved_disposition_id,
    CAST(CASE WHEN di.DispositionID IS NULL THEN 0 ELSE 1 END AS bit)   AS resolves_disposition_id,
    CAST(CASE WHEN ep.OrderNumber IS NULL THEN 0 ELSE 1 END AS bit)     AS target_order_resolved
FROM split AS s
LEFT JOIN dbo.tblPathways AS p
       ON UPPER(p.PathwayID) = s.candidate_pathway_key
LEFT JOIN dbo.tblDxDispositions AS dc
       ON UPPER(dc.DispositionCode) = s.transfer_value_key
LEFT JOIN dbo.tblDxDispositions AS di
       ON UPPER(di.DispositionID) = s.transfer_value_key
LEFT JOIN existing_positions AS ep
       ON ep.pathway_key = s.candidate_pathway_key
      AND ep.OrderNumber = TRY_CONVERT(int, s.candidate_order_text);


-- name: transfer_values_to_target_pathway
-- Resolve all transfers whose target is one selected pathway. This supports
-- focused ingress analysis without materialising the full transfer estate.
WITH unpivoted AS (
    SELECT
        t.TriageLogicID             AS triage_logic_id,
        t.PathwayID                 AS source_pathway_id,
        UPPER(t.PathwayID)          AS source_pathway_key,
        t.OrderNumber               AS source_order,
        t.QuestionID                AS question_id,
        UPPER(t.QuestionID)         AS question_key,
        CAST(t.AnswerNumber AS int) AS answer_number,
        t.JumpID                    AS jump_id,
        t.Rank                      AS rank_value,
        x.branch,
        LTRIM(RTRIM(x.transfer_value)) AS transfer_value
    FROM dbo.tblTriageLogic AS t
    CROSS APPLY (VALUES ('T1', t.T1), ('T2', t.T2), ('T3', t.T3), ('T4', t.T4))
        AS x(branch, transfer_value)
    WHERE x.transfer_value IS NOT NULL
      AND LTRIM(RTRIM(x.transfer_value)) <> ''
      AND UPPER(LTRIM(RTRIM(x.transfer_value))) LIKE :target_pathway_prefix
),
split AS (
    SELECT
        u.triage_logic_id,
        u.source_pathway_id,
        u.source_pathway_key,
        u.source_order,
        u.question_id,
        u.question_key,
        u.answer_number,
        u.jump_id,
        u.rank_value,
        u.branch,
        u.transfer_value,
        UPPER(u.transfer_value) AS transfer_value_key,
        UPPER(LEFT(u.transfer_value, CHARINDEX('.', u.transfer_value) - 1))
            AS candidate_pathway_key,
        SUBSTRING(
            u.transfer_value,
            CHARINDEX('.', u.transfer_value) + 1,
            LEN(u.transfer_value)
        ) AS candidate_order_text
    FROM unpivoted AS u
    WHERE CHARINDEX('.', u.transfer_value) > 0
),
existing_positions AS (
    SELECT DISTINCT UPPER(PathwayID) AS pathway_key, OrderNumber
    FROM dbo.tblTriageLogic
)
SELECT
    s.triage_logic_id,
    s.source_pathway_id,
    s.source_pathway_key,
    s.source_order,
    s.question_id,
    s.question_key,
    s.answer_number,
    s.jump_id,
    s.rank_value,
    s.branch,
    s.transfer_value,
    s.transfer_value_key,
    CAST(1 AS bit) AS has_dot,
    s.candidate_pathway_key,
    s.candidate_order_text,
    TRY_CONVERT(int, s.candidate_order_text) AS candidate_order_number,
    p.PathwayID AS resolved_pathway_id,
    CAST(CASE WHEN p.PathwayID IS NULL THEN 0 ELSE 1 END AS bit) AS resolves_pathway,
    p.IsArchived AS target_pathway_is_archived,
    p.FlagForDeletion AS target_pathway_flag_for_deletion,
    CAST(NULL AS varchar(50)) AS resolved_disposition_code,
    CAST(NULL AS varchar(50)) AS resolved_disposition_id_via_code,
    CAST(0 AS bit) AS resolves_disposition_code,
    CAST(NULL AS varchar(50)) AS resolved_disposition_id,
    CAST(0 AS bit) AS resolves_disposition_id,
    CAST(CASE WHEN ep.OrderNumber IS NULL THEN 0 ELSE 1 END AS bit) AS target_order_resolved
FROM split AS s
LEFT JOIN dbo.tblPathways AS p
       ON UPPER(p.PathwayID) = s.candidate_pathway_key
LEFT JOIN existing_positions AS ep
       ON ep.pathway_key = s.candidate_pathway_key
      AND ep.OrderNumber = TRY_CONVERT(int, s.candidate_order_text);
