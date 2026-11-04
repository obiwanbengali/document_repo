-- 01_inventory.sql
-- Dataset inventory: authoritative counts computed server-side.
--
-- Read-only. Returns one row per metric (long format) so that new metrics can be
-- added without changing the consuming schema.
--
-- "Active" means IsArchived = 0 AND FlagForDeletion = 0, applied only to tables that
-- actually carry both columns (tblPathways, tblTxQuestions, tblDxDispositions).
-- tblSymptomGroups and tblSymptomDiscriminators carry Active and IsArchived but no
-- FlagForDeletion, so they are reported on their own terms.
-- tblTxAnswers, tblTriageLogic, tblClinicalAreas carry no archive columns at all.

-- name: inventory
SELECT 'pathways_total'                AS metric, COUNT(*) AS value FROM dbo.tblPathways
UNION ALL
SELECT 'pathways_active',              COUNT(*) FROM dbo.tblPathways
    WHERE IsArchived = 0 AND FlagForDeletion = 0
UNION ALL
SELECT 'pathways_archived',            COUNT(*) FROM dbo.tblPathways WHERE IsArchived = 1
UNION ALL
SELECT 'pathways_flagged_for_deletion', COUNT(*) FROM dbo.tblPathways WHERE FlagForDeletion = 1
UNION ALL
SELECT 'questions_total',              COUNT(*) FROM dbo.tblTxQuestions
UNION ALL
SELECT 'questions_active',             COUNT(*) FROM dbo.tblTxQuestions
    WHERE IsArchived = 0 AND FlagForDeletion = 0
UNION ALL
SELECT 'answers_total',                COUNT(*) FROM dbo.tblTxAnswers
UNION ALL
SELECT 'triage_logic_rows',            COUNT(*) FROM dbo.tblTriageLogic
UNION ALL
SELECT 'dispositions_total',           COUNT(*) FROM dbo.tblDxDispositions
UNION ALL
SELECT 'dispositions_active',          COUNT(*) FROM dbo.tblDxDispositions
    WHERE IsArchived = 0 AND FlagForDeletion = 0
UNION ALL
SELECT 'disposition_items_total',      COUNT(*) FROM dbo.tblDXDispositionItems
UNION ALL
SELECT 'dx_rank_total',                COUNT(*) FROM dbo.tblDxRank
UNION ALL
SELECT 'symptom_groups_total',         COUNT(*) FROM dbo.tblSymptomGroups
UNION ALL
SELECT 'symptom_groups_active',        COUNT(*) FROM dbo.tblSymptomGroups WHERE Active = 1
UNION ALL
SELECT 'symptom_groups_not_archived',  COUNT(*) FROM dbo.tblSymptomGroups WHERE IsArchived = 0
UNION ALL
SELECT 'symptom_discriminators_total', COUNT(*) FROM dbo.tblSymptomDiscriminators
UNION ALL
SELECT 'symptom_discriminators_active', COUNT(*) FROM dbo.tblSymptomDiscriminators WHERE Active = 1
UNION ALL
SELECT 'symptom_group_disc_combinations_total', COUNT(*) FROM dbo.tblSymptomGroupDiscCombinations
UNION ALL
SELECT 'clinical_areas_total',         COUNT(*) FROM dbo.tblClinicalAreas
UNION ALL
SELECT 'pathway_clinical_area_links',  COUNT(*) FROM dbo.tblPathway2ClinicalAreas
UNION ALL
SELECT 'answer_snomed_assignments',    COUNT(*) FROM dbo.tblTxAnswerSnomeds
UNION ALL
SELECT 'distinct_snomed_concepts',     COUNT(DISTINCT SnomedConceptId) FROM dbo.tblTxAnswerSnomeds
UNION ALL
SELECT 'distinct_pathways_in_triage_logic', COUNT(DISTINCT PathwayID) FROM dbo.tblTriageLogic
UNION ALL
SELECT 'distinct_order_positions_in_triage_logic',
       COUNT(*) FROM (SELECT DISTINCT PathwayID, OrderNumber FROM dbo.tblTriageLogic) AS z;
