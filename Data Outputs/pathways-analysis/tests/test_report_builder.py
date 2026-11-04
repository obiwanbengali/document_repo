"""Unit tests for the presentation-layer transformation.

Every fixture is synthetic. **No real NHS Pathways data appears in any test.** The
pathway references, clinical-area names and symptom-group names below are invented, and
the numbers are small enough to verify by hand.

The tests concentrate on the three things that would actually cause harm if they broke:

1. **Confidentiality.** The builder must not pass clinical free text into the browser
   payload. ``TestConfidentiality`` puts deliberately recognisable marker strings into
   columns the builder reads and asserts they do not appear in the output.
2. **Failing loudly.** A missing artefact, a renamed column or an empty table must stop
   the build with a message naming the file, not produce a report with a blank section.
3. **Aggregation.** The banding helpers are what keep per-pathway data out of the
   payload, so their boundaries are pinned.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from pathways_analysis import report_builder as rb
from pathways_analysis.config import Paths


# ======================================================================================
# Synthetic project tree
# ======================================================================================
def _write(path: Path, rows: list[dict]) -> None:
    """Write a synthetic CSV, creating parent directories."""
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(path, index=False)


#: A marker that must never reach the browser payload. Used to prove that the builder
#: selects columns rather than copying frames wholesale.
CLINICAL_MARKER = "CONFIDENTIAL_CLINICAL_FREE_TEXT_MARKER"


def build_synthetic_outputs(root: Path) -> None:
    """Create the minimum Phase 1 and Phase 2 outputs the builder reads.

    Deliberately includes extra columns carrying :data:`CLINICAL_MARKER`, mimicking the
    real tables, which hold pathway titles and feature descriptions alongside the
    columns the report needs.
    """
    tables = root / "outputs" / "tables"
    phase2 = root / "outputs" / "phase2" / "tables"
    phase2_reports = root / "outputs" / "phase2" / "reports"

    # -- Phase 1 --------------------------------------------------------------------
    _write(
        tables / "dataset_inventory.csv",
        [
            {"metric": "pathways_active", "value": 6},
            {"metric": "questions_active", "value": 40},
            {"metric": "answers_total", "value": 90},
            {"metric": "triage_logic_rows", "value": 500},
            {"metric": "dispositions_active", "value": 7},
            {"metric": "symptom_groups_total", "value": 4},
            {"metric": "symptom_discriminators_total", "value": 9},
            {"metric": "clinical_areas_total", "value": 3},
            {"metric": "pathway_clinical_area_links", "value": 8},
        ],
    )
    _write(
        tables / "pathway_complexity.csv",
        [
            {
                "pathway_id": f"XX{index}",
                "pathway_title": f"{CLINICAL_MARKER} title {index}",
                "is_active": True,
                "question_count": count,
                "logic_row_count": count * 4,
            }
            for index, count in enumerate([0, 5, 20, 30, 60, 120], start=1)
        ],
    )
    _write(
        tables / "pathway_complexity_summary.csv",
        [
            {
                "metric": "QuestionCount",
                "count": 6, "min": 0, "mean": 39.2, "median": 25,
                "p75": 45, "p90": 90, "p95": 110, "p99": 118, "max": 120,
            },
            {
                "metric": "LogicRowCount",
                "count": 6, "min": 0, "mean": 156, "median": 100,
                "p75": 180, "p90": 360, "p95": 440, "p99": 470, "max": 480,
            },
        ],
    )
    _write(
        tables / "question_reuse_bands.csv",
        [
            {"band": "1 pathway", "question_count": 12, "total_logic_rows": 40,
             "mean_pathways_per_question": 1.0, "percentage_of_questions": 40.0},
            {"band": "2-5 pathways", "question_count": 15, "total_logic_rows": 90,
             "mean_pathways_per_question": 3.0, "percentage_of_questions": 50.0},
            {"band": "6-10 pathways", "question_count": 3, "total_logic_rows": 30,
             "mean_pathways_per_question": 7.0, "percentage_of_questions": 10.0},
        ],
    )
    _write(
        tables / "discriminator_reuse_distribution.csv",
        [
            {"pathway_count": 1, "number_of_discriminators": 4},
            {"pathway_count": 3, "number_of_discriminators": 3},
            {"pathway_count": 12, "number_of_discriminators": 2},
        ],
    )
    _write(
        tables / "pathway_graph_metrics.csv",
        [
            {"scope": "all_participating", "metric": "node_count", "value": 6},
            {"scope": "all_participating", "metric": "edge_count", "value": 9},
            {"scope": "all_participating", "metric": "total_transition_count", "value": 40},
            {"scope": "all_participating", "metric": "weakly_connected_components", "value": 2},
            {"scope": "all_participating",
             "metric": "largest_weakly_connected_component", "value": 5},
            {"scope": "all_participating", "metric": "isolated_node_count", "value": 1},
            {"scope": "active_only", "metric": "node_count", "value": 6},
            {"scope": "active_only", "metric": "edge_count", "value": 9},
        ],
    )
    _write(
        tables / "pathway_graph_nodes.csv",
        [
            {
                "pathway_id": f"XX{index}",
                "pathway_title": f"{CLINICAL_MARKER} title {index}",
                "is_active": True,
                "in_degree": index,
                "out_degree": 6 - index,
                "total_degree": 6,
            }
            for index in range(1, 7)
        ],
    )
    _write(
        tables / "clinical_area_analysis.csv",
        [
            {"clinical_area_description": "synthetic area one", "area_group": "group a",
             "pathway_count": 4, "internal_edge_percentage": 40.0},
            {"clinical_area_description": "synthetic area two", "area_group": "group b",
             "pathway_count": 3, "internal_edge_percentage": 10.0},
            {"clinical_area_description": "synthetic area three", "area_group": "group b",
             "pathway_count": 1, "internal_edge_percentage": None},
        ],
    )
    _write(
        tables / "symptom_group_analysis.csv",
        [
            {"sg_id": 1, "sg_desc": "synthetic group one", "pathway_count": 3,
             "internal_edge_percentage": 50.0},
            {"sg_id": 2, "sg_desc": "synthetic group two", "pathway_count": 2,
             "internal_edge_percentage": 0.0},
            {"sg_id": 3, "sg_desc": "synthetic group three", "pathway_count": 1,
             "internal_edge_percentage": None},
            {"sg_id": 4, "sg_desc": "synthetic group four", "pathway_count": 0,
             "internal_edge_percentage": None},
        ],
    )
    _write(
        tables / "answer_cardinality_summary.csv",
        [
            {"metric": "catalogue_answer_count_active_questions", "count": 40,
             "min": 1, "median": 3, "mean": 2.7, "max": 7},
        ],
    )

    # -- Phase 2 --------------------------------------------------------------------
    _write(
        phase2 / "age_family_analysis.csv",
        [
            {"AnalysisScope": "individual_tag_as_grouping", "GroupOrFamily": "BandA",
             "PathwayCount": 5},
            {"AnalysisScope": "individual_tag_as_grouping", "GroupOrFamily": "BandB",
             "PathwayCount": 3},
            {"AnalysisScope": "family_composition", "GroupOrFamily": "F1", "PathwayCount": 4},
        ],
    )
    _write(
        phase2 / "trauma_family_analysis.csv",
        [
            {"AnalysisScope": "individual_tag_as_grouping", "GroupOrFamily": "TagA",
             "PathwayCount": 4},
            {"AnalysisScope": "individual_tag_as_grouping", "GroupOrFamily": "TagB",
             "PathwayCount": 2},
        ],
    )
    _write(
        phase2 / "pathway_metadata_coverage.csv",
        [
            {"field": "SymptomGroupId", "pathways_in_scope": 6, "pathways_populated": 5,
             "pathways_missing": 1, "coverage_percentage": 83.3, "distinct_values": 3,
             "usable_as_grouping": True},
            {"field": "Module", "pathways_in_scope": 6, "pathways_populated": 0,
             "pathways_missing": 6, "coverage_percentage": 0.0, "distinct_values": 0,
             "usable_as_grouping": False},
        ],
    )
    _write(
        phase2_reports / "configuration_used.csv",
        [
            {"setting": "presentation.primary_candidate_strategy", "value": "hybrid_a"},
            {"setting": "presentation.naming_dominance_threshold", "value": "0.5"},
            {"setting": "shared_core.minimum_family_count", "value": "5"},
        ],
    )
    _write(
        phase2 / "family_strategy_comparison.csv",
        [
            {"strategy": "hybrid_a", "FamilyBasis": "hybrid", "Description": "synthetic",
             "IsOverlapping": False, "FamilyCount": 3, "MedianFamilySize": 2.0,
             "MaxFamilySize": 3, "MedianInternalEdgePercentage": 70.0,
             "MedianExternalEdgePercentage": 30.0, "MedianBoundaryPathwayPercentage": 25.0},
            {"strategy": "native_clinical_area", "FamilyBasis": "nhs_native",
             "Description": "synthetic", "IsOverlapping": True, "FamilyCount": 3,
             "MedianFamilySize": 3.0, "MaxFamilySize": 4,
             "MedianInternalEdgePercentage": 20.0, "MedianExternalEdgePercentage": 80.0,
             "MedianBoundaryPathwayPercentage": 90.0},
            {"strategy": "graph_louvain", "FamilyBasis": "graph_derived",
             "Description": "synthetic", "IsOverlapping": False, "FamilyCount": 4,
             "MedianFamilySize": 1.0, "MaxFamilySize": 3,
             "MedianInternalEdgePercentage": 100.0, "MedianExternalEdgePercentage": 0.0,
             "MedianBoundaryPathwayPercentage": 0.0},
        ],
    )
    _write(
        phase2 / "community_method_comparison.csv",
        [
            {"method": "louvain", "available": True, "community_count": 4,
             "modularity": 0.6, "largest_community_size": 3,
             "adjusted_rand_index_vs_primary": 1.0, "is_primary_method": True},
            {"method": "leiden", "available": True, "community_count": 4,
             "modularity": 0.61, "largest_community_size": 3,
             "adjusted_rand_index_vs_primary": 0.8, "is_primary_method": False},
            {"method": "unavailable_method", "available": False, "community_count": 0,
             "modularity": None, "largest_community_size": 0,
             "adjusted_rand_index_vs_primary": None, "is_primary_method": False},
        ],
    )
    _write(
        phase2 / "pathway_similarity_summary.csv",
        [
            {"dimension": "question", "pathways_with_any_feature": 6,
             "overlapping_pairs": 10, "possible_pairs": 15,
             "percentage_of_pairs_overlapping": 66.7, "median_jaccard": 0.1},
            {"dimension": "symptom_discriminator", "pathways_with_any_feature": 5,
             "overlapping_pairs": 8, "possible_pairs": 10,
             "percentage_of_pairs_overlapping": 80.0, "median_jaccard": 0.2},
        ],
    )
    _write(
        phase2 / "candidate_bayesian_families.csv",
        [
            {
                "FamilyId": f"F{index}",
                "FamilyName": f"synthetic family {index}",
                "FamilyNameBasis": "neutral" if index == 2 else "dominant symptom group (60%)",
                "FamilyBasis": "hybrid",
                "Strategy": "hybrid_a",
                "PathwayCount": 4 - index,
                "PrimaryClinicalAreas": "synthetic area one | synthetic area two",
                "PrimarySymptomGroups": "synthetic group one",
                "DominantSymptomGroupShare": 0.6,
                "DominantClinicalAreaShare": 0.5,
                "InternalEdgePercentage": 70.0,
                "ExternalEdgePercentage": 30.0,
                "UniqueQuestions": 20,
                "UniqueSDs": 5,
                "UniqueSnomed": 3,
                "UniqueDispositions": 4,
                "MeanPairwiseSdJaccard": 0.3,
                "SharedQuestionPercentage": 50.0,
                "BoundaryPathwayCount": 1,
                "CrossFamilyHubCount": 0,
                "StrongOverlapFamilies": "F2" if index == 1 else "",
                "StrongOverlapFamilyCount": 1 if index == 1 else 0,
                "SharedCoreDependencyCount": 6,
                "ConfidenceInStructuralCohesion": "moderate (one measure is strong)",
                "ClinicalReviewRequired": True,
                "Notes": "synthetic note",
                # A column the report must not copy through.
                "ExtraClinicalDetail": CLINICAL_MARKER,
            }
            for index in (1, 2, 3)
        ],
    )
    _write(
        phase2 / "family_overlap_matrix.csv",
        [
            {"strategy": "hybrid_a", "FamilyA": "F1", "FamilyB": "F2",
             "TransitionsAtoB": 5, "TransitionsBtoA": 2, "SdJaccard": 0.4,
             "QuestionJaccard": 0.2, "SnomedJaccard": 0.1, "OverlapBand": "high"},
            {"strategy": "hybrid_a", "FamilyA": "F1", "FamilyB": "F3",
             "TransitionsAtoB": 1, "TransitionsBtoA": 0, "SdJaccard": 0.1,
             "QuestionJaccard": 0.05, "SnomedJaccard": 0.0, "OverlapBand": "low"},
            {"strategy": "other_strategy", "FamilyA": "X1", "FamilyB": "X2",
             "TransitionsAtoB": 99, "TransitionsBtoA": 99, "SdJaccard": 0.9,
             "QuestionJaccard": 0.9, "SnomedJaccard": 0.9, "OverlapBand": "high"},
        ],
    )
    _write(
        phase2 / "boundary_pathway_summary.csv",
        [
            {"strategy": "hybrid_a", "PathwaysClassified": 6,
             "count_internal_pathway": 3, "percentage_internal_pathway": 50.0,
             "count_weak_boundary_pathway": 1, "percentage_weak_boundary_pathway": 16.7,
             "count_strong_boundary_pathway": 1, "percentage_strong_boundary_pathway": 16.7,
             "count_cross_family_hub": 1, "percentage_cross_family_hub": 16.7,
             "BoundaryPathwayCount": 3, "BoundaryPathwayPercentage": 50.0},
        ],
    )
    _write(
        phase2 / "shared_feature_summary.csv",
        [
            {"FeatureType": "question", "FeatureTypeLabel": "Tx triage question",
             "OutputTable": "shared_questions.csv", "FeaturesTotal": 30,
             "FamilySpecific": 18, "SharedBy2Families": 7, "SharedBy3To5Families": 4,
             "BroadlyShared": 1, "PercentageFamilySpecific": 60.0,
             "PercentageBroadlyShared": 3.3, "MedianFamilyCount": 1.0,
             "MaxFamilyCount": 3, "SharedCoreCandidates": 2,
             "SharedCoreThresholdFamilies": 5, "TotalDuplicationIfFederated": 4},
            {"FeatureType": "sd", "FeatureTypeLabel": "symptom discriminator",
             "OutputTable": "shared_symptom_discriminators.csv", "FeaturesTotal": 9,
             "FamilySpecific": 4, "SharedBy2Families": 3, "SharedBy3To5Families": 2,
             "BroadlyShared": 0, "PercentageFamilySpecific": 44.4,
             "PercentageBroadlyShared": 0.0, "MedianFamilyCount": 2.0,
             "MaxFamilyCount": 3, "SharedCoreCandidates": 1,
             "SharedCoreThresholdFamilies": 5, "TotalDuplicationIfFederated": 2},
        ],
    )
    _write(
        phase2 / "pathway_family_routing_summary.csv",
        [
            {"strategy": "hybrid_a", "PathwaysScored": 6,
             "PathwaysWithOnePlausibleFamily": 4, "PercentageOnePlausibleFamily": 66.7,
             "PathwaysWithTwoPlausibleFamilies": 1, "PercentageTwoPlausibleFamilies": 16.7,
             "PathwaysWithThreeOrMorePlausibleFamilies": 1,
             "PercentageThreeOrMorePlausibleFamilies": 16.7,
             "PathwaysWithNoStructuralAssociation": 0,
             "PercentageStrongSingleFamilyAssociation": 50.0,
             "PercentageModerateAmbiguity": 33.3, "PercentageHighAmbiguity": 16.7},
        ],
    )
    _write(
        phase2 / "family_merge_candidates.csv",
        [
            {"strategy": "hybrid_a", "FamilyA": "F1", "FamilyB": "F2",
             "FamilyALabel": "F1", "FamilyBLabel": "F2",
             "OverlapDriver": "shared symptom discriminators",
             "MaxFeatureJaccard": 0.4, "SmallerFamilyPathwayCount": 2,
             "PathwayCountBeforeA": 3, "PathwayCountBeforeB": 2,
             "PathwayCountAfterMerge": 5, "SharedPathways": 0,
             "InternalEdgePercentageBeforeWeighted": 60.0,
             "InternalEdgePercentageAfterMerge": 80.0,
             "MeanPairwiseSdJaccardBeforeWeighted": 0.30,
             "MeanPairwiseSdJaccardAfterMerge": 0.24,
             "MeanPairwiseSdJaccardDelta": -0.06,
             "StructuralVerdict": "shared-SD cohesion falls"},
        ],
    )
    _write(
        phase2 / "family_split_candidates.csv",
        [
            {"strategy": "hybrid_a", "FamilyId": "F1", "FamilyLabel": "F1",
             "SplitMethod": "graph_subcommunity", "SplitTriggers": "size 3 >= 3",
             "PathwayCountBefore": 3, "PartCount": 2, "PartSizes": "2 | 1",
             "InternalEdgePercentageBefore": 70.0,
             "InternalEdgePercentageAfterWeighted": 55.0,
             "MeanPairwiseSdJaccardBefore": 0.30,
             "MeanPairwiseSdJaccardAfterWeighted": 0.42,
             "MeanPairwiseSdJaccardDelta": 0.12,
             "StructuralVerdict": "split improves shared-SD cohesion only"},
        ],
    )
    _write(
        phase2 / "high_overlap_family_pairs.csv",
        [
            {"strategy": "hybrid_a", "FamilyA": "F1", "FamilyB": "F2",
             "OverlapDriver": "shared symptom discriminators",
             "SmallerFamilyPathwayCount": 2},
        ],
    )


@pytest.fixture
def synthetic_paths(tmp_path: Path) -> Paths:
    """A project root containing only synthetic analytical outputs."""
    build_synthetic_outputs(tmp_path)
    return Paths(project_root=tmp_path)


# ======================================================================================
# Loading and failure behaviour
# ======================================================================================
class TestArtefactLoading:
    def test_missing_file_names_the_file_and_the_command(self, tmp_path):
        artefact = rb.Artefact("outputs/tables/nope.csv", ("a",), "run the thing")
        with pytest.raises(rb.ReportBuildError) as error:
            rb.load_artefact(artefact, Paths(project_root=tmp_path))
        assert "outputs/tables/nope.csv" in str(error.value)
        assert "run the thing" in str(error.value)

    def test_missing_column_is_an_error_not_a_blank_section(self, tmp_path):
        _write(tmp_path / "outputs" / "t.csv", [{"a": 1}])
        artefact = rb.Artefact("outputs/t.csv", ("a", "b"), "run it")
        with pytest.raises(rb.ReportBuildError, match=r"missing column\(s\) \['b'\]"):
            rb.load_artefact(artefact, Paths(project_root=tmp_path))

    def test_empty_table_is_an_error(self, tmp_path):
        path = tmp_path / "outputs" / "empty.csv"
        path.parent.mkdir(parents=True)
        path.write_text("a,b\n")
        artefact = rb.Artefact("outputs/empty.csv", ("a", "b"), "run it")
        with pytest.raises(rb.ReportBuildError, match="has no rows"):
            rb.load_artefact(artefact, Paths(project_root=tmp_path))

    def test_all_missing_artefacts_are_reported_together(self, tmp_path):
        # A reader whose Phase 2 run never happened should be told once, with the whole
        # list, not made to discover it one file at a time.
        with pytest.raises(rb.ReportBuildError) as error:
            rb.load_all(rb.PHASE2_ARTEFACTS, Paths(project_root=tmp_path))
        message = str(error.value)
        assert "required artefact(s) could not be used" in message
        assert message.count("Produce it with") >= 5

    def test_a_real_phase1_build_fails_clearly_without_phase2_outputs(self, tmp_path):
        # Phase 1's report needs the age and trauma tables, which Phase 2 produces.
        # The error must say so rather than silently omitting the section.
        build_synthetic_outputs(tmp_path)
        (tmp_path / "outputs" / "phase2" / "tables" / "age_family_analysis.csv").unlink()
        with pytest.raises(rb.ReportBuildError) as error:
            rb.build_phase1(Paths(project_root=tmp_path))
        assert "age_family_analysis.csv" in str(error.value)
        assert "family_discovery" in str(error.value)


class TestPayloadValidation:
    def test_missing_key_is_rejected(self):
        with pytest.raises(rb.ReportBuildError, match=r"missing key\(s\) \['b'\]"):
            rb.validate_payload({"a": 1}, ["a", "b"], "test")

    def test_empty_value_is_rejected(self):
        with pytest.raises(rb.ReportBuildError, match="empty value"):
            rb.validate_payload({"a": 1, "b": []}, ["a", "b"], "test")

    def test_zero_is_a_legitimate_value(self):
        rb.validate_payload({"a": 0}, ["a"], "test")


# ======================================================================================
# Aggregation helpers
# ======================================================================================
class TestBanding:
    @pytest.mark.parametrize(
        ("value", "expected"),
        [(0, "No questions"), (1, "1-10"), (10, "1-10"), (11, "11-25"),
         (25, "11-25"), (26, "26-50"), (150, "101-150"), (151, "151+"), (900, "151+")],
    )
    def test_question_band_boundaries(self, value, expected):
        assert rb._band(value, rb.QUESTION_COUNT_BANDS) == expected

    def test_banded_counts_total_and_percentages(self):
        bands = rb._banded_counts([0, 5, 5, 20, 200], rb.QUESTION_COUNT_BANDS)
        by_band = {band["band"]: band for band in bands}
        assert by_band["No questions"]["count"] == 1
        assert by_band["1-10"]["count"] == 2
        assert by_band["11-25"]["count"] == 1
        assert by_band["151+"]["count"] == 1
        assert sum(band["count"] for band in bands) == 5
        assert by_band["1-10"]["percentage"] == pytest.approx(40.0)

    def test_banded_counts_keeps_every_band_even_when_empty(self):
        # A missing band would silently shorten the chart's x-axis.
        bands = rb._banded_counts([5], rb.QUESTION_COUNT_BANDS)
        assert len(bands) == len(rb.QUESTION_COUNT_BANDS)
        assert all("count" in band for band in bands)

    def test_nulls_are_skipped_not_counted(self):
        bands = rb._banded_counts([5, None, float("nan")], rb.QUESTION_COUNT_BANDS)
        assert sum(band["count"] for band in bands) == 1

    def test_weighted_banding_uses_the_weight_column(self):
        frame = pd.DataFrame(
            [
                {"pathway_count": 1, "number_of_discriminators": 4},
                {"pathway_count": 3, "number_of_discriminators": 3},
                {"pathway_count": 60, "number_of_discriminators": 1},
            ]
        )
        bands = rb._weighted_banded_counts(
            frame,
            value_column="pathway_count",
            weight_column="number_of_discriminators",
            bands=rb.REUSE_BANDS,
        )
        by_band = {band["band"]: band["count"] for band in bands}
        assert by_band["1 pathway"] == 4
        assert by_band["2-5"] == 3
        assert by_band["51+"] == 1

    def test_optional_number_maps_missing_to_none_for_json_null(self):
        # The page shows "not measurable" for null, which is different from zero.
        assert rb._optional_number(None) is None
        assert rb._optional_number(float("nan")) is None
        assert rb._optional_number(1.23456789) == pytest.approx(1.2346)


# ======================================================================================
# Phase 1 payload
# ======================================================================================
class TestPhase1Payload:
    def test_builds_every_section(self, synthetic_paths):
        payload = rb.build_phase1(synthetic_paths)
        assert set(rb.PHASE1_KEYS) <= set(payload)

    def test_headline_counts_come_from_the_inventory(self, synthetic_paths):
        payload = rb.build_phase1(synthetic_paths)
        cards = {card["key"]: card["value"] for card in payload["estate"]["cards"]}
        assert cards["pathways"] == 6
        assert cards["questions"] == 40
        assert cards["pathway_links"] == 9

    def test_every_card_declares_its_evidence_class(self, synthetic_paths):
        payload = rb.build_phase1(synthetic_paths)
        for card in payload["estate"]["cards"]:
            assert card["evidence_class"] in rb.EVIDENCE_CLASSES

    def test_pathway_size_is_banded_not_per_pathway(self, synthetic_paths):
        payload = rb.build_phase1(synthetic_paths)
        size = payload["pathway_size"]
        assert size["stats"]["median"] == 25
        assert size["stats"]["max"] == 120
        assert sum(band["count"] for band in size["distribution"]) == 6

    def test_top_connected_list_is_capped_and_carries_no_titles(self, synthetic_paths):
        payload = rb.build_phase1(synthetic_paths)
        top = payload["connectivity"]["top_connected"]
        assert len(top) <= rb.TOP_CONNECTED_LIMIT
        for item in top:
            assert set(item) == {"pathway_id", "outgoing", "incoming", "total"}

    def test_groupings_include_age_and_trauma_tags(self, synthetic_paths):
        payload = rb.build_phase1(synthetic_paths)
        groupings = payload["groupings"]
        assert [band["label"] for band in groupings["age_bands"]] == ["BandA", "BandB"]
        assert [item["label"] for item in groupings["trauma"]] == ["TagA", "TagB"]

    def test_family_composition_rows_are_excluded_from_tag_counts(self, synthetic_paths):
        # The age table holds several analysis scopes; only the per-tag rows belong here.
        payload = rb.build_phase1(synthetic_paths)
        labels = [band["label"] for band in payload["groupings"]["age_bands"]]
        assert "F1" not in labels

    def test_symptom_groups_with_no_pathways_are_excluded_from_the_distribution(
        self, synthetic_paths
    ):
        payload = rb.build_phase1(synthetic_paths)
        groups = payload["groupings"]["symptom_groups"]
        assert groups["total_catalogued"] == 4
        assert groups["with_active_pathways"] == 3
        assert sum(band["count"] for band in groups["size_distribution"]) == 3

    def test_every_block_carries_its_lineage(self, synthetic_paths):
        payload = rb.build_phase1(synthetic_paths)
        for section in ("estate", "pathway_size", "reuse", "connectivity", "groupings"):
            assert payload[section]["source"], f"{section} has no source lineage"

    def test_limitations_are_stated_explicitly(self, synthetic_paths):
        payload = rb.build_phase1(synthetic_paths)
        joined = " ".join(payload["does_not_tell_us"]).lower()
        for topic in ("federated", "cost", "memory", "infrastructure"):
            assert topic in joined


# ======================================================================================
# Phase 2 payload
# ======================================================================================
class TestPhase2Payload:
    def test_builds_every_section(self, synthetic_paths):
        payload = rb.build_phase2(synthetic_paths)
        assert set(rb.PHASE2_KEYS) <= set(payload)

    def test_primary_strategy_is_read_from_configuration(self, synthetic_paths):
        payload = rb.build_phase2(synthetic_paths)
        assert payload["configuration"]["primary_strategy"] == "hybrid_a"

    def test_the_graph_cluster_warning_is_present_verbatim(self, synthetic_paths):
        # The brief requires this sentence prominently; it must not be paraphrased away.
        payload = rb.build_phase2(synthetic_paths)
        assert payload["evidence_sources"]["warning"] == (
            "A graph community is a data cluster, not a clinically approved family."
        )

    def test_no_strategy_is_marked_as_best(self, synthetic_paths):
        payload = rb.build_phase2(synthetic_paths)
        rows = payload["strategy_comparison"]["rows"]
        assert sum(1 for row in rows if row["is_primary"]) == 1
        # "is_primary" means "presented for review", and the note must say so.
        assert "No strategy is preferred" in payload["strategy_comparison"]["no_winner_note"]

    def test_every_family_requires_clinical_review(self, synthetic_paths):
        payload = rb.build_phase2(synthetic_paths)
        assert all(row["clinical_review_required"] for row in payload["families"]["rows"])

    def test_every_family_metric_has_a_tooltip(self, synthetic_paths):
        payload = rb.build_phase2(synthetic_paths)
        tooltips = payload["families"]["metric_tooltips"]
        for key in (
            "pathway_count", "unique_questions", "unique_discriminators", "unique_snomed",
            "unique_dispositions", "internal_link_percentage", "external_link_percentage",
            "boundary_pathway_count", "cross_family_hub_count", "shared_core_dependencies",
            "cohesion", "clinical_areas", "symptom_groups", "overlapping_families",
            "name_basis",
        ):
            assert tooltips.get(key), f"metric {key} has no explanation"

    def test_neutral_named_families_are_flagged(self, synthetic_paths):
        payload = rb.build_phase2(synthetic_paths)
        by_id = {row["family_id"]: row for row in payload["families"]["rows"]}
        assert by_id["F2"]["is_named_from_metadata"] is False
        assert by_id["F1"]["is_named_from_metadata"] is True

    def test_overlap_matrices_are_square_symmetric_and_strategy_scoped(
        self, synthetic_paths
    ):
        payload = rb.build_phase2(synthetic_paths)
        overlap = payload["overlap"]
        size = len(overlap["family_ids"])
        for name, matrix in overlap["matrices"].items():
            assert len(matrix) == size, name
            assert all(len(row) == size for row in matrix), name
            for i in range(size):
                for j in range(size):
                    assert matrix[i][j] == matrix[j][i], f"{name} not symmetric"
        # The other strategy's much larger values must not leak in.
        assert max(max(row) for row in overlap["matrices"]["transitions"]) == 7

    def test_overlap_measure_order_puts_the_default_first(self, synthetic_paths):
        payload = rb.build_phase2(synthetic_paths)
        overlap = payload["overlap"]
        assert overlap["measure_order"][0] == overlap["default_measure"]
        assert set(overlap["measure_order"]) == set(overlap["matrices"])

    def test_boundary_buckets_sum_to_the_classified_total(self, synthetic_paths):
        payload = rb.build_phase2(synthetic_paths)
        boundaries = payload["boundaries"]
        assert sum(bucket["count"] for bucket in boundaries["buckets"]) == (
            boundaries["pathways_classified"]
        )

    def test_routing_association_bands_are_present_and_ordered(self, synthetic_paths):
        payload = rb.build_phase2(synthetic_paths)
        keys = [item["key"] for item in payload["routing"]["association"]]
        assert keys == ["strong", "moderate", "high"]

    def test_merge_and_split_never_recommend(self, synthetic_paths):
        payload = rb.build_phase2(synthetic_paths)
        for section in ("merge_candidates", "split_candidates"):
            note = payload[section]["no_recommendation_note"].lower()
            assert "no merge is proposed" in note or "no split is proposed" in note
            assert payload[section]["mechanical_caveat"]

    def test_merge_evidence_keeps_the_unbiased_measure(self, synthetic_paths):
        # The internal-edge change is mechanically favourable to any merge, so the
        # clinical-similarity change has to reach the presentation.
        payload = rb.build_phase2(synthetic_paths)
        row = payload["merge_candidates"]["rows"][0]
        assert row["clinical_similarity_before"] == pytest.approx(0.30)
        assert row["clinical_similarity_after"] == pytest.approx(0.24)
        assert row["clinical_similarity_change"] == pytest.approx(-0.06)

    def test_limitations_name_the_phase3_questions(self, synthetic_paths):
        payload = rb.build_phase2(synthetic_paths)
        joined = " ".join(payload["does_not_tell_us"]).lower()
        for topic in ("federated", "memory", "cost", "probability tables"):
            assert topic in joined

    def test_next_phase_lists_three_options_and_its_inputs(self, synthetic_paths):
        payload = rb.build_phase2(synthetic_paths)
        assert len(payload["next_phase"]["options"]) == 3
        assert payload["next_phase"]["criteria"]
        assert payload["next_phase"]["inputs_needed"]

    def test_missing_primary_strategy_rows_fail_loudly(self, tmp_path):
        build_synthetic_outputs(tmp_path)
        boundary = tmp_path / "outputs" / "phase2" / "tables" / "boundary_pathway_summary.csv"
        frame = pd.read_csv(boundary)
        frame["strategy"] = "some_other_strategy"
        frame.to_csv(boundary, index=False)
        with pytest.raises(rb.ReportBuildError, match="boundary_pathway_summary"):
            rb.build_phase2(Paths(project_root=tmp_path))


# ======================================================================================
# Confidentiality
# ======================================================================================
class TestConfidentiality:
    """The payload is loaded into a browser, so what it contains is a control, not a
    detail. These tests fail if the builder starts copying frames wholesale."""

    def test_phase1_payload_contains_no_clinical_free_text(self, synthetic_paths):
        payload = rb.build_phase1(synthetic_paths)
        assert CLINICAL_MARKER not in json.dumps(payload)

    def test_phase2_payload_contains_no_clinical_free_text(self, synthetic_paths):
        payload = rb.build_phase2(synthetic_paths)
        assert CLINICAL_MARKER not in json.dumps(payload)

    def test_pathway_titles_never_reach_either_payload(self, synthetic_paths):
        # The fixture's titles all carry the marker, so this is the same assertion made
        # explicit: titles are available to the builder and deliberately not used.
        for payload in (rb.build_phase1(synthetic_paths), rb.build_phase2(synthetic_paths)):
            serialised = json.dumps(payload)
            assert "title" not in serialised.replace('"title"', "")
            assert CLINICAL_MARKER not in serialised

    def test_every_payload_carries_the_confidentiality_notice(self, synthetic_paths):
        for builder in (rb.build_phase1, rb.build_phase2):
            payload = builder(synthetic_paths)
            assert payload["meta"]["confidentiality"] == rb.CONFIDENTIALITY_NOTICE

    def test_architectural_interpretation_is_not_an_available_evidence_class(self):
        # The fourth class in the programme's scheme is out of scope until Phase 3, so
        # the presentation must not have a way of labelling something with it.
        assert "architectural" not in " ".join(rb.EVIDENCE_CLASSES).lower()
        assert set(rb.EVIDENCE_CLASSES) == {"measured", "derived", "candidate"}

    def test_scope_note_denies_an_architectural_recommendation(self, synthetic_paths):
        payload = rb.build_phase2(synthetic_paths)
        assert "no architectural recommendation" in payload["meta"]["scope_note"].lower()


# ======================================================================================
# Writing
# ======================================================================================
class TestWriting:
    def test_payload_round_trips_as_json(self, synthetic_paths, tmp_path):
        payload = rb.build_phase1(synthetic_paths)
        path = rb.write_payload(payload, tmp_path / "out" / "phase1-report.json")
        assert json.loads(path.read_text(encoding="utf-8")) == payload

    def test_output_is_stable_between_identical_builds(self, synthetic_paths, tmp_path):
        # Sorted keys and fixed indentation: these files are reviewed for
        # confidentiality before being shared, so the diff has to be meaningful.
        payload = rb.build_phase1(synthetic_paths)
        first = rb.write_payload(payload, tmp_path / "a.json").read_text()
        second = rb.write_payload(payload, tmp_path / "b.json").read_text()
        assert first == second

    def test_cli_reports_missing_evidence_with_exit_code_two(self, tmp_path, monkeypatch):
        monkeypatch.setenv("PATHWAYS_PROJECT_ROOT", str(tmp_path))
        assert rb.main(["--phase", "1", "--output-dir", str(tmp_path / "data")]) == 2

    def test_cli_all_skips_a_phase_whose_analysis_has_not_been_run(
        self, tmp_path, monkeypatch
    ):
        # Not having run Phase 3 must not block rebuilding the Phase 1 and 2 data.
        # The skip is reported, and the Phase 3 page shows its own missing-data panel.
        build_synthetic_outputs(tmp_path)
        monkeypatch.setenv("PATHWAYS_PROJECT_ROOT", str(tmp_path))
        output = tmp_path / "reports" / "data"
        assert rb.main(["--phase", "all", "--output-dir", str(output)]) == 0
        assert (output / "phase1-report.json").is_file()
        assert (output / "phase2-report.json").is_file()
        assert not (output / "phase3-report.json").exists()

    def test_cli_explicit_phase_still_fails_hard_when_evidence_is_missing(
        self, tmp_path, monkeypatch
    ):
        build_synthetic_outputs(tmp_path)
        monkeypatch.setenv("PATHWAYS_PROJECT_ROOT", str(tmp_path))
        assert rb.main(["--phase", "3", "--output-dir", str(tmp_path / "d")]) == 2

    def test_cli_fails_when_no_phase_has_evidence(self, tmp_path, monkeypatch):
        monkeypatch.setenv("PATHWAYS_PROJECT_ROOT", str(tmp_path))
        assert rb.main(["--phase", "all", "--output-dir", str(tmp_path / "d")]) == 2


# ======================================================================================
# Phase 3 synthetic outputs
# ======================================================================================
def build_synthetic_phase3(root: Path) -> None:
    """Create the minimum Phase 3 outputs the report builder reads.

    As with the Phase 1 and 2 fixtures, extra columns carrying
    :data:`CLINICAL_MARKER` are included so the confidentiality tests can prove the
    builder selects columns rather than copying frames.
    """
    tables = root / "outputs" / "phase3" / "tables"

    _write(
        tables / "representation_summary.csv",
        [
            {"Representation": "literal_monolith", "Label": "Literal monolith",
             "CandidateVariableCount": 900, "VariableIdentity": "pathway_order_occurrence",
             "EvidenceClass": "derived", "Interpretation": "Structural upper bound.",
             "ComparedWithDeduplicatedMonolith": 800, "Extra": CLINICAL_MARKER},
            {"Representation": "deduplicated_monolith", "Label": "Deduplicated monolith",
             "CandidateVariableCount": 100, "VariableIdentity": "question_id",
             "EvidenceClass": "derived", "Interpretation": "Technical dedup only.",
             "ComparedWithDeduplicatedMonolith": 0, "Extra": CLINICAL_MARKER},
            {"Representation": "provisional_federated", "Label": "Provisional federated",
             "CandidateVariableCount": 150,
             "VariableIdentity": "question_id_per_candidate_family",
             "EvidenceClass": "candidate", "Interpretation": "Counted once per family.",
             "ComparedWithDeduplicatedMonolith": 50, "Extra": CLINICAL_MARKER},
        ],
    )
    _write(
        tables / "state_cardinality_summary.csv",
        [
            {"Scope": "literal_occurrences", "count": 900, "min": 1, "median": 3.0,
             "p90": 4.0, "p95": 5.0, "max": 7, "mean": 2.4},
            {"Scope": "deduplicated_questions", "count": 100, "min": 1, "median": 3.0,
             "p90": 4.0, "p95": 5.0, "max": 7, "mean": 2.7},
        ],
    )
    _write(
        tables / "evidence_and_assumptions.csv",
        [
            {"Item": "Candidate family boundaries", "Class": "assumption",
             "Value": "Provisional Phase 2 set", "Limitation": "Pending clinical review."},
        ],
    )

    sizing_rows, growth_rows = [], []
    for representation in (
        "literal_monolith", "deduplicated_monolith", "provisional_federated"
    ):
        variables = {"literal_monolith": 900, "deduplicated_monolith": 100,
                     "provisional_federated": 150}[representation]
        for case, states in (("median_parent_states", 3), ("p90_parent_states", 4)):
            previous = None
            for parents in (1, 2, 3):
                entries = variables * 3 * states**parents
                sizing_rows.append({
                    "Representation": representation, "ParentCount": parents,
                    "ParentStateCase": case, "AssumedParentStatesEach": states,
                    "VariableCountSized": variables, "TotalCptEntries": entries,
                    "TotalFreeParameters": int(entries * 0.6),
                    "LargestVariableCptEntries": 7 * states**parents,
                    "MedianVariableCptEntries": 3 * states**parents,
                    "EvidenceClass": "assumption+derived",
                    "RawProbabilityMiBFloat32": round(entries * 4 / 1048576, 4),
                })
                growth_rows.append({
                    "Representation": representation, "ParentStateCase": case,
                    "ParentCount": parents, "TotalCptEntries": entries,
                    "GrowthVsPreviousParentCount": (
                        None if previous is None else round(entries / previous, 2)
                    ),
                })
                previous = entries
    _write(tables / "cpt_sizing_by_representation.csv", sizing_rows)
    _write(tables / "cpt_growth_curve.csv", growth_rows)
    _write(
        tables / "phase3b_method_notes.csv",
        [{"Item": "Parent count", "EvidenceClass": "assumption",
          "Statement": "Varied deliberately; not a proposed structure."}],
    )
    _write(
        tables / "benchmark_runtime_envelope.csv",
        [
            {"Representation": "deduplicated_monolith", "ModelScope": "whole_model",
             "MaxBenchmarkNodes": 50, "MaxFractionOfActualModel": 0.5,
             "ObservedQueryP95MinMs": 1.5, "ObservedQueryP95MaxMs": 12.0,
             "EvidenceClass": "benchmark", "Caveat": "Envelope spans several cases."},
            {"Representation": "literal_monolith", "ModelScope": "whole_model",
             "MaxBenchmarkNodes": 50, "MaxFractionOfActualModel": 0.055,
             "ObservedQueryP95MinMs": 1.4, "ObservedQueryP95MaxMs": 15.0,
             "EvidenceClass": "benchmark", "Caveat": "Envelope spans several cases."},
        ],
    )
    _write(
        tables / "runtime_patterns.csv",
        [
            {"PatternId": pattern, "LogicalModel": "synthetic",
             "DeploymentShape": "synthetic shape", "ModelResidency": "resident",
             "Routing": "internal", "CrossModelCoordination": "none",
             "Extra": CLINICAL_MARKER}
            for pattern in ("monolith_always_resident", "federated_all_resident",
                            "federated_lazy_loaded", "hierarchical_shared_core")
        ],
    )
    _write(
        tables / "runtime_coordination_evidence.csv",
        [{"Evidence": "one plausible family", "Value": 70.9,
          "Unit": "percent of scored pathways", "RuntimeMeaning": "structural only",
          "EvidenceClass": "candidate+derived"}],
    )
    _write(
        tables / "runtime_failure_modes.csv",
        [{"PatternId": "monolith_always_resident", "FailureMode": "synthetic",
          "LikelyScope": "whole service", "RequiredControl": "synthetic control",
          "EvidenceClass": "architectural_interpretation"}],
    )
    _write(
        tables / "runtime_change_blast_radius.csv",
        [{"PatternId": "monolith_always_resident", "LocalChangeUnit": "whole model",
          "ModelReleaseBlastRadius": "everything", "RegressionScope": "full",
          "CompatibilityManagement": "single version",
          "EvidenceClass": "architectural_interpretation"}],
    )

    cost_rows = []
    for volume, tasks in ((100_000, 2), (1_000_000, 2), (5_000_000, 4)):
        for index, pattern in enumerate(
            ("monolith_always_resident", "federated_all_resident",
             "federated_lazy_loaded", "hierarchical_shared_core")
        ):
            # Only the largest volume separates the patterns, mirroring the real model's
            # minimum-capacity floor.
            pattern_tasks = tasks if volume < 5_000_000 else tasks + index
            cost_rows.append({
                "PatternId": pattern, "AssessmentsPerMonth": volume,
                "RequiredTasks": pattern_tasks,
                "FargateComputeMonthlyUsd": pattern_tasks * 85.0,
                "FixedPlatformAllowancesMonthlyUsd": 80.0,
                "TotalIllustrativeMonthlyUsd": pattern_tasks * 85.0 + 80.0,
                "IllustrativeCostPer1000AssessmentsUsd": round(
                    (pattern_tasks * 85.0 + 80.0) / (volume / 1000), 4
                ),
                "PricingTargetRegion": "eu-west-2", "PricingBasisRegion": "us-east-1",
                "PricingStatus": "illustrative_only", "EvidenceClass": "assumption+derived",
            })
    _write(tables / "infrastructure_cost_scenarios.csv", cost_rows)
    _write(
        tables / "phase3e_method_notes.csv",
        [{"Item": "Pricing", "EvidenceClass": "assumption",
          "Statement": "Illustrative only."}],
    )
    _write(
        tables / "adr_evidence_matrix.csv",
        [
            {"Representation": representation, "Label": "synthetic",
             "CandidateVariableCount": 100, "ReferenceCptEntries": 2700,
             "ReferenceCptCase": "3 parents", "BenchmarkCoverage": "50% max coverage",
             "BenchmarkP95MsRange": "1.5-12.0 ms", "IllustrativeMonthlyCost1mUsd": 250.0,
             "CostBasis": "scenario", "EvidenceStatus": "complete_for_draft"}
            for representation in ("literal_monolith", "deduplicated_monolith",
                                   "provisional_federated")
        ],
    )
    _write(
        tables / "adr_decision_gates.csv",
        [
            {"Gate": "Phase 3A representation evidence", "Passed": True,
             "Detail": "exists"},
            {"Gate": "Clinical review of candidate families", "Passed": False,
             "Detail": "outstanding"},
        ],
    )
    _write(
        tables / "adr_runtime_tradeoffs.csv",
        [
            {"Representation": representation, "Strength": "synthetic strength",
             "Tradeoff": "synthetic tradeoff", "EvidenceClass": "architectural_interpretation"}
            for representation in ("literal_monolith", "deduplicated_monolith",
                                   "provisional_federated")
        ],
    )


@pytest.fixture
def synthetic_phase3_paths(tmp_path: Path) -> Paths:
    """A project root containing synthetic Phase 1, 2 and 3 outputs."""
    build_synthetic_outputs(tmp_path)
    build_synthetic_phase3(tmp_path)
    return Paths(project_root=tmp_path)


class TestPhase3Payload:
    def test_builds_every_section(self, synthetic_phase3_paths):
        payload = rb.build_phase3(synthetic_phase3_paths)
        assert set(rb.PHASE3_KEYS) <= set(payload)

    def test_missing_phase3_outputs_fail_with_the_producing_command(self, tmp_path):
        build_synthetic_outputs(tmp_path)
        with pytest.raises(rb.ReportBuildError) as error:
            rb.build_phase3(Paths(project_root=tmp_path))
        message = str(error.value)
        assert "representation_summary.csv" in message
        assert "phase3_sizing" in message

    def test_representations_are_ordered_largest_first(self, synthetic_phase3_paths):
        payload = rb.build_phase3(synthetic_phase3_paths)
        counts = [row["variable_count"] for row in payload["representations"]["rows"]]
        assert counts == sorted(counts, reverse=True)

    def test_every_representation_has_a_plain_english_label(self, synthetic_phase3_paths):
        payload = rb.build_phase3(synthetic_phase3_paths)
        for row in payload["representations"]["rows"]:
            assert row["label"] != row["representation"]
            assert "_" not in row["label"]

    def test_every_runtime_pattern_has_a_plain_english_label(self, synthetic_phase3_paths):
        # A missing mapping silently shows a raw identifier to a non-technical reader.
        payload = rb.build_phase3(synthetic_phase3_paths)
        for row in payload["runtime"]["patterns"]:
            assert "_" not in row["label"], row["pattern_id"]

    def test_open_decision_gates_are_surfaced(self, synthetic_phase3_paths):
        payload = rb.build_phase3(synthetic_phase3_paths)
        status = payload["status"]
        assert status["gates_total"] == 2
        assert status["gates_open"] == 1
        assert "DRAFT" in status["decision_status"]

    def test_benchmark_coverage_warning_quotes_the_real_coverage(
        self, synthetic_phase3_paths
    ):
        # The timings are meaningless without the coverage, so it must travel with them.
        payload = rb.build_phase3(synthetic_phase3_paths)
        benchmark = payload["benchmark"]
        assert benchmark["coverage_min_percentage"] == pytest.approx(5.5)
        assert benchmark["coverage_max_percentage"] == pytest.approx(50.0)
        assert "5.5%" in benchmark["coverage_warning"]
        assert "not a prediction" in benchmark["coverage_warning"]

    def test_cost_spread_identifies_where_patterns_actually_differ(
        self, synthetic_phase3_paths
    ):
        # Below a volume threshold every pattern costs the same because of a minimum
        # capacity floor. Defaulting to such a volume would show identical bars and
        # hide the finding.
        payload = rb.build_phase3(synthetic_phase3_paths)
        cost = payload["cost"]
        assert cost["volumes_where_patterns_differ"] == [5_000_000]
        assert cost["default_volume"] == 5_000_000
        flat = [item for item in cost["spread_by_volume"] if not item["patterns_differ"]]
        assert {item["assessments_per_month"] for item in flat} == {100_000, 1_000_000}

    def test_cost_carries_its_pricing_basis(self, synthetic_phase3_paths):
        payload = rb.build_phase3(synthetic_phase3_paths)
        cost = payload["cost"]
        assert cost["pricing_basis_region"] != cost["pricing_target_region"]
        assert "not a quotation" in cost["caveat"]

    def test_decision_section_recommends_nothing(self, synthetic_phase3_paths):
        payload = rb.build_phase3(synthetic_phase3_paths)
        decision = payload["decision"]
        assert "No architecture is recommended" in decision["no_recommendation"]
        for row in decision["tradeoffs"]:
            assert row["strength"] and row["tradeoff"]
        serialised = json.dumps(decision).lower()
        for banned in ("recommended option", "we recommend", "preferred architecture"):
            assert banned not in serialised

    def test_limitations_name_the_things_phase3_cannot_settle(self, synthetic_phase3_paths):
        payload = rb.build_phase3(synthetic_phase3_paths)
        joined = " ".join(payload["does_not_tell_us"]).lower()
        for topic in ("cost", "clinical review", "latency", "decision gates"):
            assert topic in joined

    def test_provisional_family_caveat_is_unavoidable(self, synthetic_phase3_paths):
        # Every federated figure depends on unreviewed families; a reader must not be
        # able to reach the numbers without meeting that caveat.
        payload = rb.build_phase3(synthetic_phase3_paths)
        serialised = json.dumps(payload).lower()
        assert "provisional" in serialised
        assert "clinical review" in serialised

    def test_conclusion_matches_the_phase1_and_phase2_shape(self, synthetic_phase3_paths):
        payload = rb.build_phase3(synthetic_phase3_paths)
        conclusion = payload["conclusion"]
        assert conclusion["paragraphs"]
        assert conclusion["next_question"]
        assert conclusion["evidence_class"] in rb.EVIDENCE_CLASSES

    def test_executive_summary_matches_the_phase1_and_phase2_shape(
        self, synthetic_phase3_paths
    ):
        payload = rb.build_phase3(synthetic_phase3_paths)
        summary = payload["executive_summary"]
        assert summary["headline"] and summary["bottom_line"]
        assert len(summary["key_points"]) >= 3

    def test_every_section_carries_its_lineage(self, synthetic_phase3_paths):
        payload = rb.build_phase3(synthetic_phase3_paths)
        for section in (
            "status", "representations", "cpt_growth", "benchmark", "runtime", "cost",
            "decision",
        ):
            assert payload[section]["source"], f"{section} has no source lineage"

    def test_payload_contains_no_clinical_free_text(self, synthetic_phase3_paths):
        payload = rb.build_phase3(synthetic_phase3_paths)
        assert CLINICAL_MARKER not in json.dumps(payload)

    def test_cli_builds_phase3(self, tmp_path, monkeypatch):
        build_synthetic_outputs(tmp_path)
        build_synthetic_phase3(tmp_path)
        monkeypatch.setenv("PATHWAYS_PROJECT_ROOT", str(tmp_path))
        output = tmp_path / "reports" / "data"
        assert rb.main(["--phase", "3", "--output-dir", str(output)]) == 0
        assert (output / "phase3-report.json").is_file()

    def test_cli_all_builds_three_payloads(self, tmp_path, monkeypatch):
        build_synthetic_outputs(tmp_path)
        build_synthetic_phase3(tmp_path)
        monkeypatch.setenv("PATHWAYS_PROJECT_ROOT", str(tmp_path))
        output = tmp_path / "reports" / "data"
        assert rb.main(["--phase", "all", "--output-dir", str(output)]) == 0
        for phase in (1, 2, 3):
            assert (output / f"phase{phase}-report.json").is_file()
