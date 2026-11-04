-- 09_family_features.sql
-- Phase 2: per-pathway feature-model extracts that Phase 1 did not need.
--
-- Read-only. No DDL, no DML.
--
-- File numbering note: sql/09_data_quality.sql is the Phase 1 file with the same
-- numeric prefix. The prefix orders files for readability only; the loader keys
-- queries by name, and query names are unique across every file.
--
-- Phase 1 already extracts pathways, clinical areas (including AreaGroup), symptom
-- groups, symptom discriminators, SNOMED assignments and the full triage logic table.
-- Those queries are reused rather than duplicated here. What Phase 2 adds is the
-- pathway-level age / gender / trauma metadata and the two independent routes from a
-- pathway to a disposition.
--
-- Age / gender / trauma are MANY-TO-MANY with pathways
-- ----------------------------------------------------
-- tblPathway2Ages, tblPathway2Genders and tblPathway2Trauma are link tables, so a
-- pathway carries a SET of age bands, a SET of genders and possibly BOTH trauma
-- values. They are therefore extracted long-format and must never be treated as a
-- single categorical column per pathway.

-- name: pathway_ages
SELECT
    pa.PathwayID                    AS pathway_id,
    UPPER(pa.PathwayID)             AS pathway_key,
    pa.AgeID                        AS age_id,
    a.AgeDescription                AS age_description,
    a.MinHours                      AS age_min_hours,
    a.MaxHours                      AS age_max_hours
FROM dbo.tblPathway2Ages AS pa
LEFT JOIN dbo.tblAges AS a
       ON a.AgeID = pa.AgeID;

-- name: pathway_genders
SELECT
    pg.PathwayID                    AS pathway_id,
    UPPER(pg.PathwayID)             AS pathway_key,
    pg.GenderID                     AS gender_id,
    g.GenderDescription             AS gender_description
FROM dbo.tblPathway2Genders AS pg
LEFT JOIN dbo.tblGenders AS g
       ON g.GenderID = pg.GenderID;

-- name: pathway_trauma
SELECT
    pt.PathwayID                    AS pathway_id,
    UPPER(pt.PathwayID)             AS pathway_key,
    pt.TraumaID                     AS trauma_id,
    t.TraumaDescription             AS trauma_description
FROM dbo.tblPathway2Trauma AS pt
LEFT JOIN dbo.tblTrauma AS t
       ON t.TraumaID = pt.TraumaID;

-- name: age_reference
-- MinHours / MaxHours are the stored band boundaries. They are exported so that the
-- ordering of age bands is taken from the data rather than from the description text.
SELECT
    a.AgeID                         AS age_id,
    a.AgeDescription                AS age_description,
    a.MinHours                      AS age_min_hours,
    a.MaxHours                      AS age_max_hours,
    a.OtherDescription              AS age_other_description
FROM dbo.tblAges AS a;

-- name: gender_reference
SELECT
    g.GenderID                      AS gender_id,
    g.GenderDescription             AS gender_description
FROM dbo.tblGenders AS g;

-- name: trauma_reference
SELECT
    t.TraumaID                      AS trauma_id,
    t.TraumaDescription             AS trauma_description
FROM dbo.tblTrauma AS t;

-- name: pathway_disposition_nodes
-- Route 1 from a pathway to a disposition: a Dx-prefixed node sitting at an order
-- position in the pathway's own triage logic.
--
-- tblTriageLogic.QuestionID is polymorphic (Tx / Cx / Dx). A 'Dx' value here is a
-- disposition node reference, not a question. It is matched to the disposition
-- catalogue on DispositionID, which is the identifier those references use.
SELECT
    UPPER(t.PathwayID)              AS pathway_key,
    UPPER(t.QuestionID)             AS disposition_node_key,
    d.DispositionID                 AS disposition_id,
    d.DispositionCode               AS disposition_code,
    UPPER(d.DispositionCode)        AS disposition_code_key,
    d.DxRank                        AS dx_rank,
    COUNT(*)                        AS logic_row_count,
    COUNT(DISTINCT t.OrderNumber)   AS order_position_count
FROM dbo.tblTriageLogic AS t
LEFT JOIN dbo.tblDxDispositions AS d
       ON UPPER(d.DispositionID) = UPPER(t.QuestionID)
WHERE UPPER(LEFT(t.QuestionID, 2)) = 'DX'
GROUP BY
    UPPER(t.PathwayID), UPPER(t.QuestionID),
    d.DispositionID, d.DispositionCode, d.DxRank;

-- name: pathway_disposition_transfers
-- Route 2 from a pathway to a disposition: a T1..T4 transfer value that resolves to a
-- DispositionCode (a value with no '.'; see 06_transfer_analysis.sql for the grammar).
--
-- This is the same resolution Phase 1 performs in Python for
-- pathway_to_disposition_edges.csv, computed server-side so the Phase 2 feature model
-- can be built without re-deriving it, and so the two can be cross-checked.
WITH unpivoted AS (
    SELECT
        UPPER(t.PathwayID)             AS pathway_key,
        UPPER(t.QuestionID)            AS question_key,
        CAST(t.AnswerNumber AS int)    AS answer_number,
        t.OrderNumber                  AS source_order,
        x.branch,
        UPPER(LTRIM(RTRIM(x.transfer_value))) AS transfer_value_key
    FROM dbo.tblTriageLogic AS t
    CROSS APPLY (VALUES ('T1', t.T1), ('T2', t.T2), ('T3', t.T3), ('T4', t.T4))
        AS x(branch, transfer_value)
    WHERE x.transfer_value IS NOT NULL
      AND LTRIM(RTRIM(x.transfer_value)) <> ''
      AND CHARINDEX('.', x.transfer_value) = 0
)
SELECT
    u.pathway_key,
    d.DispositionID                    AS disposition_id,
    d.DispositionCode                  AS disposition_code,
    UPPER(d.DispositionCode)           AS disposition_code_key,
    d.DxRank                           AS dx_rank,
    COUNT(*)                           AS transfer_row_count,
    COUNT(DISTINCT u.question_key)     AS source_question_count,
    COUNT(DISTINCT u.source_order)     AS source_order_count
FROM unpivoted AS u
JOIN dbo.tblDxDispositions AS d
      ON UPPER(d.DispositionCode) = u.transfer_value_key
GROUP BY
    u.pathway_key, d.DispositionID, d.DispositionCode, d.DxRank;
