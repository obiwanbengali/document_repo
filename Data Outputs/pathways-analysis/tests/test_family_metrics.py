"""Unit tests for the Phase 2 family metrics.

Every fixture here is synthetic. **No real NHS Pathways data appears in any test**:
the pathway ids, question ids, symptom-discriminator ids and titles are invented, and
the expected values are small enough to verify by hand. A test that needed real data to
pass would be pinning a snapshot, not a definition.

The tests are organised around the definitions that are contestable -- Jaccard, the
internal-edge percentage, the shared-feature percentage, the boundary classification,
the merge/split before/after comparison and the ambiguity score -- because those are
where a regression would silently change the evidence rather than break the run.
"""

from __future__ import annotations

import networkx as nx
import pandas as pd
import pytest

from pathways_analysis import (
    family_boundaries,
    family_core,
    family_discovery,
    family_evaluation,
    family_overlap,
    family_routing,
)
from pathways_analysis import graph as gt
from pathways_analysis.family_config import FamilyDiscoveryConfig
from pathways_analysis.family_features import (
    CandidateFamilySet,
    FeatureMaps,
    PairwiseSimilarity,
    PathwayFeatureModel,
    build_membership_frame,
    classify_age,
    classify_gender,
    classify_trauma,
    indicator_matrix,
)


# ======================================================================================
# Synthetic fixtures
# ======================================================================================
def _map(pairs: list[tuple[str, str]]) -> pd.DataFrame:
    """Build a two-column pathway -> feature map."""
    return pd.DataFrame(pairs, columns=["pathway_key", "feature_id"])


@pytest.fixture
def synthetic_model() -> PathwayFeatureModel:
    """A six-pathway model with two obvious clusters and one bridge.

    Layout, hand-drawn so every expected value below can be checked::

        PA1 <-> PA2 -> PA3        PA4 -> PA5        PA6 (isolated)
                        |           ^
                        +-----------+   (PA3 -> PA4 is the only cross-cluster edge)

    Features:
      * PA1, PA2, PA3 share questions Q1/Q2 (PA3 also has Q3).
      * PA4, PA5 share Q4.
      * PA6 has Q9 and nothing else.
    """
    edges = pd.DataFrame(
        [
            {"source_pathway_key": "PA1", "target_pathway_key": "PA2", "transition_count": 3},
            {"source_pathway_key": "PA2", "target_pathway_key": "PA1", "transition_count": 1},
            {"source_pathway_key": "PA2", "target_pathway_key": "PA3", "transition_count": 2},
            {"source_pathway_key": "PA3", "target_pathway_key": "PA4", "transition_count": 5},
            {"source_pathway_key": "PA4", "target_pathway_key": "PA5", "transition_count": 4},
        ]
    )
    scope = ["PA1", "PA2", "PA3", "PA4", "PA5", "PA6"]
    node_attributes = pd.DataFrame({"pathway_key": scope})
    pathway_graph = gt.build_pathway_graph(edges, node_attributes)

    maps = FeatureMaps(
        question=_map(
            [
                ("PA1", "Q1"), ("PA1", "Q2"),
                ("PA2", "Q1"), ("PA2", "Q2"),
                ("PA3", "Q1"), ("PA3", "Q2"), ("PA3", "Q3"),
                ("PA4", "Q4"), ("PA5", "Q4"),
                ("PA6", "Q9"),
            ]
        ),
        symptom_discriminator=_map(
            [("PA1", "1"), ("PA2", "1"), ("PA3", "1"), ("PA4", "2"), ("PA5", "2")]
        ),
        snomed=_map([("PA1", "100"), ("PA2", "100"), ("PA4", "200")]),
        disposition=_map([("PA1", "DX01"), ("PA2", "DX01"), ("PA4", "DX02")]),
        clinical_area=_map([("PA1", "1"), ("PA2", "1"), ("PA4", "2"), ("PA5", "2")]),
    )

    features = pd.DataFrame(
        [
            {
                "PathwayID": key.lower(),
                "PathwayKey": key,
                "PathwayTitle": f"Synthetic pathway {key}",
                "SymptomGroupId": symptom_group,
                "SymptomGroupDescription": f"SG{symptom_group}" if symptom_group else None,
                "ClinicalAreas": area,
                "AreaGroups": area_group,
                "ClinicalAreaCount": 1 if area else 0,
                "AgeClassification": age,
                "TraumaClassification": trauma,
                "AgeDescriptions": age_description,
                "TraumaDescriptions": trauma_description,
                "BetweennessCentrality": betweenness,
            }
            for key, symptom_group, area, area_group, age, trauma, age_description,
                trauma_description, betweenness in (
                ("PA1", 10, "Area A", "upper", "adult_only", "non_trauma",
                 "Adult", "Non Trauma", 0.0),
                ("PA2", 10, "Area A", "upper", "adult_only", "non_trauma",
                 "Adult", "Non Trauma", 0.10),
                ("PA3", 10, "Area A", "upper", "paediatric_only", "trauma",
                 "Child", "Trauma", 0.60),
                ("PA4", 20, "Area B", "lower", "paediatric_only", "trauma",
                 "Child", "Trauma", 0.20),
                ("PA5", 20, "Area B", "lower", "adult_only", "non_trauma",
                 "Adult", "Non Trauma", 0.0),
                ("PA6", None, "", "", "unspecified", "unspecified", "", "", 0.0),
            )
        ]
    )

    return PathwayFeatureModel(
        features=features,
        maps=maps,
        pathway_graph=pathway_graph,
        edges=edges,
        node_metrics=gt.node_metrics(pathway_graph),
        scope=scope,
        metadata_coverage=pd.DataFrame(),
        adult_age_id=1,
    )


@pytest.fixture
def synthetic_candidate() -> CandidateFamilySet:
    """Two families matching the two clusters, plus a singleton for PA6."""
    return CandidateFamilySet(
        strategy="test",
        basis="hybrid",
        description="synthetic",
        membership=build_membership_frame(
            {
                "F1": {"PA1", "PA2", "PA3"},
                "F2": {"PA4", "PA5"},
                "F3": {"PA6"},
            },
            strategy="test",
            membership_basis="synthetic",
        ),
    )


@pytest.fixture
def config() -> FamilyDiscoveryConfig:
    """Default configuration, used so tests pin the shipped thresholds."""
    return FamilyDiscoveryConfig()


# ======================================================================================
# Jaccard and indicator matrices
# ======================================================================================
class TestJaccard:
    def test_hand_computed_pairwise_jaccard(self, synthetic_model):
        # PA1 = {Q1,Q2}; PA3 = {Q1,Q2,Q3} -> intersection 2, union 3, Jaccard 2/3.
        similarity = PairwiseSimilarity.build(synthetic_model)
        matrix = similarity.matrix("question")
        index = {key: position for position, key in enumerate(similarity.pathways)}
        assert matrix[index["PA1"], index["PA3"]] == pytest.approx(2 / 3)
        assert matrix[index["PA1"], index["PA2"]] == pytest.approx(1.0)
        assert matrix[index["PA1"], index["PA4"]] == pytest.approx(0.0)

    def test_mean_within_counts_non_overlapping_pairs_as_zero(self, synthetic_model):
        # F1 = {PA1,PA2,PA3}: pairs are (PA1,PA2)=1.0, (PA1,PA3)=2/3, (PA2,PA3)=2/3.
        similarity = PairwiseSimilarity.build(synthetic_model)
        assert similarity.mean_within("question", {"PA1", "PA2", "PA3"}) == pytest.approx(
            (1.0 + 2 / 3 + 2 / 3) / 3, abs=1e-5
        )
        # Adding an unrelated pathway must dilute the mean, not be skipped: PA6 shares
        # nothing, so three extra pairs contribute 0 out of six pairs total.
        diluted = similarity.mean_within("question", {"PA1", "PA2", "PA3", "PA6"})
        assert diluted == pytest.approx((1.0 + 2 / 3 + 2 / 3) / 6, abs=1e-5)

    def test_mean_within_is_nan_below_two_members(self, synthetic_model):
        similarity = PairwiseSimilarity.build(synthetic_model)
        assert pd.isna(similarity.mean_within("question", {"PA1"}))
        assert pd.isna(similarity.mean_within("question", set()))

    def test_mean_between_excludes_self_pairs(self, synthetic_model):
        similarity = PairwiseSimilarity.build(synthetic_model)
        # PA1 appears in both groups; its self-similarity of 1.0 must not inflate the
        # between-group mean. Remaining pair is (PA1,PA2) = 1.0 and (PA2,PA2) excluded.
        value = similarity.mean_between("question", {"PA1", "PA2"}, {"PA1"})
        assert value == pytest.approx(1.0)

    def test_indicator_matrix_gives_zero_rows_to_absent_entities(self):
        matrix, features = indicator_matrix(_map([("PA1", "Q1")]), ["PA1", "PA2"])
        assert features == ["Q1"]
        assert matrix.shape == (2, 1)
        assert matrix[0, 0] == 1.0
        assert matrix[1, 0] == 0.0

    def test_indicator_matrix_handles_an_empty_map(self):
        matrix, features = indicator_matrix(_map([]), ["PA1", "PA2"])
        assert features == []
        assert matrix.shape == (2, 0)


# ======================================================================================
# Adjusted Rand index
# ======================================================================================
class TestAdjustedRandIndex:
    def test_identical_partitions_score_one(self):
        partition = {"A": 0, "B": 0, "C": 1, "D": 1}
        assert gt.adjusted_rand_index(partition, partition) == pytest.approx(1.0)

    def test_relabelling_does_not_change_the_score(self):
        left = {"A": 0, "B": 0, "C": 1, "D": 1}
        right = {"A": 9, "B": 9, "C": 7, "D": 7}
        assert gt.adjusted_rand_index(left, right) == pytest.approx(1.0)

    def test_one_moved_member_scores_below_one(self):
        left = {"A": 0, "B": 0, "C": 1, "D": 1}
        right = {"A": 0, "B": 1, "C": 1, "D": 1}
        score = gt.adjusted_rand_index(left, right)
        assert -1.0 <= score < 1.0

    def test_only_shared_nodes_are_compared(self):
        left = {"A": 0, "B": 0, "C": 1}
        right = {"A": 0, "B": 0, "Z": 5}
        # A and B agree; C and Z are not shared and cannot agree or disagree.
        assert gt.adjusted_rand_index(left, right) == pytest.approx(1.0)

    def test_fewer_than_two_shared_nodes_is_nan(self):
        assert pd.isna(gt.adjusted_rand_index({"A": 0}, {"A": 1}))


# ======================================================================================
# Community membership transforms
# ======================================================================================
class TestCommunityTransforms:
    def test_partition_ids_are_renumbered_largest_first(self):
        graph = nx.Graph()
        graph.add_edges_from([("A", "B"), ("B", "C"), ("X", "Y")])
        membership = gt.partition_undirected(graph, "greedy_modularity")
        sizes = pd.Series(list(membership.values())).value_counts()
        assert sizes.loc[0] >= sizes.max()
        assert set(membership) == {"A", "B", "C", "X", "Y"}

    def test_strongly_connected_communities_group_a_cycle(self):
        graph = nx.DiGraph()
        graph.add_edges_from([("A", "B"), ("B", "A"), ("C", "D")])
        membership = gt.strongly_connected_communities(graph)
        assert membership["A"] == membership["B"]
        assert membership["C"] != membership["D"]

    def test_unknown_method_raises(self):
        with pytest.raises(ValueError, match="Unknown undirected community method"):
            gt.partition_undirected(nx.Graph([("A", "B")]), "not_a_method")

    def test_detect_community_methods_records_rather_than_drops_a_bad_method(self):
        graph = nx.DiGraph([("A", "B")])
        partitions, unavailable = gt.detect_community_methods(graph, ["louvain"])
        assert "louvain" in partitions
        assert unavailable == {}

    def test_membership_frame_is_long_format_and_allows_overlap(self):
        frame = build_membership_frame(
            {"F1": {"PA1", "PA2"}, "F2": {"PA2"}},
            strategy="test",
            membership_basis="synthetic",
        )
        assert len(frame) == 3
        assert (frame.loc[frame["pathway_key"] == "PA2"]).shape[0] == 2

    def test_candidate_set_detects_overlap_rather_than_asserting_it(self):
        partition = CandidateFamilySet(
            strategy="p", basis="hybrid", description="",
            membership=build_membership_frame(
                {"F1": {"PA1"}, "F2": {"PA2"}}, strategy="p"
            ),
        )
        overlapping = CandidateFamilySet(
            strategy="o", basis="hybrid", description="",
            membership=build_membership_frame(
                {"F1": {"PA1"}, "F2": {"PA1"}}, strategy="o"
            ),
        )
        assert partition.overlapping is False
        assert overlapping.overlapping is True


# ======================================================================================
# Cohesion
# ======================================================================================
class TestCohesion:
    def test_internal_edge_percentage_matches_the_phase_1_definition(self, synthetic_model):
        # F1 = {PA1,PA2,PA3}. Internal out-edges: PA1->PA2, PA2->PA1, PA2->PA3 = 3.
        # Outgoing: PA3->PA4 = 1. So internal share = 3/4 = 75%.
        metrics = family_evaluation.cohesion_for_group({"PA1", "PA2", "PA3"}, synthetic_model)
        assert metrics["InternalEdges"] == 3
        assert metrics["ExternalEdges"] == 1
        assert metrics["InternalEdgePercentage"] == pytest.approx(75.0)
        assert metrics["ExternalEdgePercentage"] == pytest.approx(25.0)

    def test_incoming_external_edges_are_counted_separately(self, synthetic_model):
        # F2 = {PA4,PA5}: PA3->PA4 is an incoming external edge; PA4->PA5 is internal.
        metrics = family_evaluation.cohesion_for_group({"PA4", "PA5"}, synthetic_model)
        assert metrics["InternalEdges"] == 1
        assert metrics["ExternalEdges"] == 0
        assert metrics["ExternalEdgesIncoming"] == 1
        assert metrics["InternalEdgePercentage"] == pytest.approx(100.0)

    def test_group_with_no_edges_gets_nan_not_zero_or_hundred(self, synthetic_model):
        metrics = family_evaluation.cohesion_for_group({"PA6"}, synthetic_model)
        assert metrics["InternalEdges"] == 0
        assert pd.isna(metrics["InternalEdgePercentage"])

    def test_average_degrees_exclude_self_and_count_distinct_neighbours(self, synthetic_model):
        # F1: PA1 has 1 internal neighbour (PA2), PA2 has 2 (PA1, PA3),
        # PA3 has 1 (PA2) internal and 1 external (PA4).
        metrics = family_evaluation.cohesion_for_group({"PA1", "PA2", "PA3"}, synthetic_model)
        assert metrics["AverageInternalDegree"] == pytest.approx((1 + 2 + 1) / 3, abs=1e-3)
        assert metrics["AverageExternalDegree"] == pytest.approx(1 / 3, abs=1e-3)

    def test_boundary_pathway_count_and_percentage(self, synthetic_model):
        metrics = family_evaluation.cohesion_for_group({"PA1", "PA2", "PA3"}, synthetic_model)
        assert metrics["NumberOfBoundaryPathways"] == 1  # only PA3 reaches outside
        assert metrics["PercentageBoundaryPathways"] == pytest.approx(100 / 3, abs=1e-2)

    def test_shared_feature_percentage_counts_features_used_twice_or_more(
        self, synthetic_model
    ):
        # F1 questions: Q1 (3 pathways), Q2 (3), Q3 (1) -> 2 of 3 shared = 66.667%.
        metrics = family_evaluation.cohesion_for_group({"PA1", "PA2", "PA3"}, synthetic_model)
        assert metrics["UniqueQuestionCount"] == 3
        assert metrics["SharedQuestionPercentage"] == pytest.approx(66.667, abs=1e-2)

    def test_unique_counts_cover_every_dimension(self, synthetic_model):
        metrics = family_evaluation.cohesion_for_group({"PA1", "PA2"}, synthetic_model)
        assert metrics["UniqueQuestionCount"] == 2
        assert metrics["UniqueSymptomDiscriminatorCount"] == 1
        assert metrics["UniqueSnomedCount"] == 1
        assert metrics["UniqueDispositionCount"] == 1

    def test_cohesion_table_covers_every_family_of_every_strategy(
        self, synthetic_model, synthetic_candidate
    ):
        similarity = PairwiseSimilarity.build(synthetic_model)
        table = family_evaluation.family_cohesion(
            [synthetic_candidate], synthetic_model, similarity=similarity
        )
        assert set(table["FamilyId"]) == {"F1", "F2", "F3"}
        assert set(table["strategy"]) == {"test"}

    def test_every_emitted_metric_has_a_documented_definition(
        self, synthetic_model, synthetic_candidate
    ):
        similarity = PairwiseSimilarity.build(synthetic_model)
        table = family_evaluation.family_cohesion(
            [synthetic_candidate], synthetic_model, similarity=similarity
        )
        documented = set(family_evaluation.metric_definition_table()["metric"])
        # Guard the metrics the brief names explicitly: a renamed column without a
        # matching definition would put an undefined number in the evidence base.
        required = {
            "PathwayCount", "UniqueQuestionCount", "UniqueSymptomDiscriminatorCount",
            "UniqueSnomedCount", "UniqueDispositionCount", "InternalEdges",
            "ExternalEdges", "InternalEdgePercentage", "ExternalEdgePercentage",
            "AverageInternalDegree", "AverageExternalDegree",
            "NumberOfBoundaryPathways", "PercentageBoundaryPathways",
            "SharedQuestionPercentage", "SharedSdPercentage", "SharedSnomedPercentage",
        }
        assert required <= set(table.columns)
        assert required <= documented


# ======================================================================================
# Overlap matrix
# ======================================================================================
class TestOverlapMatrix:
    def test_shared_counts_and_jaccard_are_hand_computable(
        self, synthetic_model, synthetic_candidate
    ):
        overlap = family_overlap.family_overlap_matrix(
            synthetic_candidate, synthetic_model, include_zero_overlap=True
        )
        row = overlap.loc[
            (overlap["FamilyA"] == "F1") & (overlap["FamilyB"] == "F2")
        ].iloc[0]
        # F1 questions {Q1,Q2,Q3}; F2 {Q4} -> no overlap.
        assert row["SharedQuestions"] == 0
        assert row["QuestionJaccard"] == pytest.approx(0.0)
        # F1 -> F2 has one edge (PA3->PA4) carrying 5 transitions; nothing comes back.
        assert row["EdgesAtoB"] == 1
        assert row["TransitionsAtoB"] == 5
        assert row["TransitionsBtoA"] == 0

    def test_overlapping_membership_is_reported_as_shared_pathways(self, synthetic_model):
        candidate = CandidateFamilySet(
            strategy="overlap", basis="nhs_native", description="",
            membership=build_membership_frame(
                {"F1": {"PA1", "PA2"}, "F2": {"PA2", "PA4"}}, strategy="overlap"
            ),
        )
        overlap = family_overlap.family_overlap_matrix(candidate, synthetic_model)
        row = overlap.iloc[0]
        assert row["SharedPathways"] == 1
        # |F1 ∪ F2| = 3, |F1 ∩ F2| = 1 -> 1/3.
        assert row["PathwayJaccard"] == pytest.approx(1 / 3, abs=1e-4)

    def test_zero_overlap_pairs_are_omitted_by_default(
        self, synthetic_model, synthetic_candidate
    ):
        filtered = family_overlap.family_overlap_matrix(synthetic_candidate, synthetic_model)
        full = family_overlap.family_overlap_matrix(
            synthetic_candidate, synthetic_model, include_zero_overlap=True
        )
        assert len(full) == 3  # three unordered pairs of three families
        assert len(filtered) < len(full)

    def test_single_family_set_returns_an_empty_typed_frame(self, synthetic_model):
        candidate = CandidateFamilySet(
            strategy="one", basis="hybrid", description="",
            membership=build_membership_frame({"F1": {"PA1"}}, strategy="one"),
        )
        overlap = family_overlap.family_overlap_matrix(candidate, synthetic_model)
        assert overlap.empty
        assert "MaxFeatureJaccard" in overlap.columns

    def test_classification_uses_the_configured_thresholds(self, config):
        overlap = pd.DataFrame(
            [
                {"strategy": "s", "FamilyA": "A", "FamilyB": "B", "SharedPathways": 0,
                 "QuestionJaccard": 0.05, "SdJaccard": 0.02, "SnomedJaccard": 0.0,
                 "DispositionJaccard": 0.0, "MaxFeatureJaccard": 0.05},
                {"strategy": "s", "FamilyA": "A", "FamilyB": "C", "SharedPathways": 0,
                 "QuestionJaccard": 0.20, "SdJaccard": 0.02, "SnomedJaccard": 0.0,
                 "DispositionJaccard": 0.0, "MaxFeatureJaccard": 0.20},
                {"strategy": "s", "FamilyA": "B", "FamilyB": "C", "SharedPathways": 0,
                 "QuestionJaccard": 0.40, "SdJaccard": 0.02, "SnomedJaccard": 0.0,
                 "DispositionJaccard": 0.0, "MaxFeatureJaccard": 0.40},
            ]
        )
        overlap["MaxDiscriminatingJaccard"] = overlap["MaxFeatureJaccard"]
        classified = family_overlap.classify_overlap(overlap, config)
        assert list(classified["OverlapBand"]) == ["low", "moderate", "high"]
        assert list(classified["OverlapDriver"]) == ["shared questions"] * 3

    def test_dispositions_are_excluded_from_the_band_by_default(self, config):
        # A pair whose only strong overlap is its disposition set must not be banded
        # high: nearly every family can reach an ambulance or a primary-care referral,
        # so disposition Jaccard does not distinguish clinical areas.
        overlap = pd.DataFrame(
            [
                {"strategy": "s", "FamilyA": "A", "FamilyB": "B", "SharedPathways": 0,
                 "QuestionJaccard": 0.02, "SdJaccard": 0.01, "SnomedJaccard": 0.0,
                 "DispositionJaccard": 0.90, "MaxFeatureJaccard": 0.90,
                 "MaxDiscriminatingJaccard": 0.02},
            ]
        )
        assert config.overlap_band_measure == "discriminating"
        classified = family_overlap.classify_overlap(overlap, config)
        assert classified.iloc[0]["OverlapBand"] == "low"
        assert classified.iloc[0]["OverlapBandMeasure"] == "MaxDiscriminatingJaccard"

        including = FamilyDiscoveryConfig(overlap_band_measure="all_features")
        classified = family_overlap.classify_overlap(overlap, including)
        assert classified.iloc[0]["OverlapBand"] == "high"
        assert classified.iloc[0]["OverlapDriver"] == "shared dispositions"

    def test_shared_pathways_escalate_to_high_regardless_of_jaccard(self, config):
        overlap = pd.DataFrame(
            [
                {"strategy": "s", "FamilyA": "A", "FamilyB": "B", "SharedPathways": 2,
                 "QuestionJaccard": 0.0, "SdJaccard": 0.0, "SnomedJaccard": 0.0,
                 "DispositionJaccard": 0.0, "MaxFeatureJaccard": 0.0},
            ]
        )
        classified = family_overlap.classify_overlap(overlap, config)
        assert classified.iloc[0]["OverlapBand"] == "high"
        assert classified.iloc[0]["OverlapEscalatedBySharedPathways"]
        assert "shared pathways" in classified.iloc[0]["OverlapDriver"]


# ======================================================================================
# Boundary classification
# ======================================================================================
class TestBoundaryClassification:
    def test_no_external_edge_is_internal(self, config):
        assert (
            family_boundaries._classify_boundary(
                external_degree=0, external_family_count=0,
                betweenness_percentile=99.0, config=config,
            )
            == "internal pathway"
        )

    def test_one_external_edge_is_a_weak_boundary(self, config):
        assert (
            family_boundaries._classify_boundary(
                external_degree=1, external_family_count=1,
                betweenness_percentile=10.0, config=config,
            )
            == "weak boundary pathway"
        )

    def test_high_external_degree_is_a_strong_boundary(self, config):
        assert (
            family_boundaries._classify_boundary(
                external_degree=config.boundary_strong_external_degree,
                external_family_count=1, betweenness_percentile=10.0, config=config,
            )
            == "strong boundary pathway"
        )

    def test_many_families_without_betweenness_is_not_promoted_to_a_hub(self, config):
        # Both conditions are required, so a locally chatty pathway stays a boundary.
        assert (
            family_boundaries._classify_boundary(
                external_degree=1,
                external_family_count=config.boundary_hub_external_family_count,
                betweenness_percentile=10.0,
                config=config,
            )
            == "strong boundary pathway"
        )

    def test_many_families_with_high_betweenness_is_a_cross_family_hub(self, config):
        assert (
            family_boundaries._classify_boundary(
                external_degree=5,
                external_family_count=config.boundary_hub_external_family_count,
                betweenness_percentile=config.boundary_hub_betweenness_percentile,
                config=config,
            )
            == "cross-family hub"
        )

    def test_boundary_table_identifies_the_bridge_pathway(
        self, synthetic_model, synthetic_candidate, config
    ):
        boundary = family_boundaries.boundary_pathways(
            synthetic_candidate, synthetic_model, pd.DataFrame(), config=config
        )
        by_pathway = boundary.set_index("PathwayKey")["BoundaryClassification"].to_dict()
        # PA3 is the only F1 member with an edge outside F1; PA4 receives it.
        assert by_pathway["PA3"] != "internal pathway"
        assert by_pathway["PA4"] != "internal pathway"
        assert by_pathway["PA1"] == "internal pathway"
        assert by_pathway["PA6"] == "internal pathway"

    def test_boundary_summary_percentages_sum_to_one_hundred(
        self, synthetic_model, synthetic_candidate, config
    ):
        boundary = family_boundaries.boundary_pathways(
            synthetic_candidate, synthetic_model, pd.DataFrame(), config=config
        )
        summary = family_boundaries.boundary_summary(boundary)
        row = summary.iloc[0]
        total = sum(
            row[f"percentage_{name.replace(' ', '_').replace('-', '_')}"]
            for name in family_boundaries.BOUNDARY_CLASSES
        )
        assert total == pytest.approx(100.0, abs=0.05)


# ======================================================================================
# Shared features and shared core
# ======================================================================================
class TestSharedFeatures:
    def test_family_counts_and_bands(self, synthetic_model, synthetic_candidate, config):
        tables = family_boundaries.shared_feature_tables(
            synthetic_candidate,
            synthetic_model,
            occurrences={},
            config=config,
        )
        questions = tables["shared_questions"].set_index("FeatureId")
        # Q1 is used only by F1's pathways, so it is family-specific.
        assert questions.loc["Q1", "FamilyCount"] == 1
        assert questions.loc["Q1", "SharingBand"] == "family-specific"
        assert questions.loc["Q1", "PathwayCount"] == 3

    def test_a_feature_spanning_two_families_is_banded_as_such(
        self, synthetic_model, config
    ):
        candidate = CandidateFamilySet(
            strategy="t", basis="hybrid", description="",
            membership=build_membership_frame(
                {"F1": {"PA1"}, "F2": {"PA2"}}, strategy="t"
            ),
        )
        tables = family_boundaries.shared_feature_tables(
            candidate, synthetic_model, occurrences={}, config=config
        )
        questions = tables["shared_questions"].set_index("FeatureId")
        assert questions.loc["Q1", "FamilyCount"] == 2
        assert questions.loc["Q1", "SharingBand"] == "shared by 2 families"

    def test_occurrence_counts_are_carried_through(
        self, synthetic_model, synthetic_candidate, config
    ):
        occurrences = {
            "question": pd.DataFrame(
                [{"feature_id": "Q1", "total_occurrences": 42}]
            )
        }
        tables = family_boundaries.shared_feature_tables(
            synthetic_candidate, synthetic_model, occurrences=occurrences, config=config
        )
        questions = tables["shared_questions"].set_index("FeatureId")
        assert questions.loc["Q1", "TotalOccurrences"] == 42
        assert questions.loc["Q2", "TotalOccurrences"] == 0

    def test_shared_core_threshold_is_respected(
        self, synthetic_model, synthetic_candidate, config
    ):
        tables = family_boundaries.shared_feature_tables(
            synthetic_candidate, synthetic_model, occurrences={}, config=config
        )
        # Default threshold is 5 families; the fixture has 3, so nothing qualifies.
        assert family_core.shared_core_candidates(
            tables, synthetic_candidate, synthetic_model, config=config
        ).empty

        relaxed = FamilyDiscoveryConfig(shared_core_minimum_family_count=1)
        core = family_core.shared_core_candidates(
            tables, synthetic_candidate, synthetic_model, config=relaxed
        )
        assert not core.empty
        assert (core["DuplicationIfFederated"] == core["FamilyCount"] - 1).all()
        assert core["Conclusion"].str.contains("evidence only").all()


# ======================================================================================
# Routing ambiguity
# ======================================================================================
class TestRoutingAmbiguity:
    def test_a_pathway_inside_a_tight_family_is_unambiguous(
        self, synthetic_model, synthetic_candidate, config
    ):
        context = family_routing.AffinityContext.build(synthetic_model)
        routing = family_routing.routing_ambiguity(
            synthetic_candidate, synthetic_model, context, config=config
        ).set_index("PathwayKey")
        # PA1 shares every feature with PA2 and nothing with F2, so F1 must dominate.
        assert routing.loc["PA1", "DominantFamilyId"] == "F1"
        assert routing.loc["PA1", "AmbiguityScore"] < config.routing_moderate_ambiguity
        assert (
            routing.loc["PA1", "AmbiguityClassification"]
            == "strong single-family association"
        )

    def test_ambiguity_score_is_second_over_best(
        self, synthetic_model, synthetic_candidate, config
    ):
        context = family_routing.AffinityContext.build(synthetic_model)
        routing = family_routing.routing_ambiguity(
            synthetic_candidate, synthetic_model, context, config=config
        )
        for row in routing.itertuples():
            if pd.isna(row.AmbiguityScore):
                continue
            assert 0.0 <= row.AmbiguityScore <= 1.0
            assert row.SecondAffinity <= row.DominantAffinity
            assert row.AmbiguityScore == pytest.approx(
                row.SecondAffinity / row.DominantAffinity, abs=1e-5
            )

    def test_a_pathway_with_no_features_or_edges_has_no_association(
        self, synthetic_model, config
    ):
        candidate = CandidateFamilySet(
            strategy="t", basis="hybrid", description="",
            membership=build_membership_frame(
                {"F1": {"PA1", "PA2"}, "F2": {"PA4", "PA5"}}, strategy="t"
            ),
        )
        model = synthetic_model
        # Strip PA6's only feature so it is genuinely unrelated to everything.
        model.maps.question.drop(
            model.maps.question.index[model.maps.question["pathway_key"] == "PA6"],
            inplace=True,
        )
        context = family_routing.AffinityContext.build(model)
        routing = family_routing.routing_ambiguity(
            candidate, model, context, config=config
        ).set_index("PathwayKey")
        assert routing.loc["PA6", "AmbiguityClassification"] == "no structural association"
        assert pd.isna(routing.loc["PA6", "AmbiguityScore"])

    def test_affinity_components_are_reported_individually(
        self, synthetic_model, synthetic_candidate, config
    ):
        context = family_routing.AffinityContext.build(synthetic_model)
        routing = family_routing.routing_ambiguity(
            synthetic_candidate, synthetic_model, context, config=config
        )
        for column in (
            "AffinityGraphComponent", "AffinityQuestionComponent", "AffinitySdComponent",
            "AffinitySnomedComponent", "AffinityDispositionComponent",
        ):
            assert column in routing.columns
            assert (routing[column].fillna(0) >= 0).all()

    def test_self_similarity_is_excluded_from_a_pathways_own_family(
        self, synthetic_model, config
    ):
        # A single-member family would otherwise score 1.0 for its own member.
        candidate = CandidateFamilySet(
            strategy="t", basis="hybrid", description="",
            membership=build_membership_frame(
                {"F1": {"PA1"}, "F2": {"PA2", "PA3"}}, strategy="t"
            ),
        )
        context = family_routing.AffinityContext.build(synthetic_model)
        affinity, components, family_ids = family_routing.family_affinity(
            candidate, context, weights=config.routing_weights
        )
        position = context.pathways.index("PA1")
        own = family_ids.index("F1")
        assert components["question"][position, own] == pytest.approx(0.0)

    def test_routing_summary_percentages_are_consistent(
        self, synthetic_model, synthetic_candidate, config
    ):
        context = family_routing.AffinityContext.build(synthetic_model)
        routing = family_routing.routing_ambiguity(
            synthetic_candidate, synthetic_model, context, config=config
        )
        summary = family_routing.routing_summary(routing)
        row = summary.iloc[0]
        assert row["PathwaysScored"] == len(routing)
        assert (
            row["PathwaysWithOnePlausibleFamily"]
            + row["PathwaysWithTwoPlausibleFamilies"]
            + row["PathwaysWithThreeOrMorePlausibleFamilies"]
            <= len(routing)
        )


# ======================================================================================
# Merge and split
# ======================================================================================
class TestMergeAndSplit:
    def test_merge_recomputes_cohesion_and_never_recommends(
        self, synthetic_model, synthetic_candidate, config
    ):
        similarity = PairwiseSimilarity.build(synthetic_model)
        cohesion = family_evaluation.family_cohesion(
            [synthetic_candidate], synthetic_model, similarity=similarity
        )
        classified = pd.DataFrame(
            [
                {
                    "strategy": "test", "FamilyA": "F1", "FamilyB": "F2",
                    "FamilyALabel": "F1", "FamilyBLabel": "F2",
                    "OverlapBand": "high", "OverlapDriver": "shared questions",
                    "MaxFeatureJaccard": 0.5, "SharedPathways": 0,
                    "SharedSDs": 0, "SharedQuestions": 0, "SharedSnomed": 0,
                    "SdJaccard": 0.0, "QuestionJaccard": 0.5, "SnomedJaccard": 0.0,
                    "TransitionsAtoB": 5, "TransitionsBtoA": 0,
                    "PathwayCountA": 3, "PathwayCountB": 2,
                }
            ]
        )
        merges = family_overlap.merge_candidates(
            classified, {"test": synthetic_candidate}, synthetic_model, cohesion,
            config=config, similarity=similarity,
        )
        row = merges.iloc[0]
        # Regression guard: without the similarity matrices every mean pairwise
        # Jaccard is NaN and the verdict silently becomes "not measurable" for every
        # pair, which reads as "no merge helps" rather than as a missing input.
        assert pd.notna(row["MeanPairwiseSdJaccardAfterMerge"])
        assert row["StructuralVerdict"] != "not measurable"
        # Merging F1 and F2 absorbs the only cross-family edge, so every edge from the
        # merged family's pathways stays inside it.
        assert row["PathwayCountAfterMerge"] == 5
        assert row["InternalEdgePercentageAfterMerge"] == pytest.approx(100.0)
        assert row["InternalEdgePercentageDelta"] > 0
        assert "not made" in row["Recommendation"]

    def test_merge_verdict_is_driven_by_the_unbiased_signal(self):
        # Internal-edge percentage can only rise under a merge, so a large positive
        # graph delta must not by itself produce a favourable verdict; a falling
        # shared-SD cohesion has to show through.
        verdict = family_overlap._merge_verdict(40.0, -0.15)
        assert "falls" in verdict
        assert "mechanical" in verdict

        verdict = family_overlap._merge_verdict(40.0, 0.12)
        assert "rises" in verdict

        assert family_overlap._merge_verdict(40.0, float("nan")) == "not measurable"

    def test_merge_output_carries_the_mechanical_warning_flag(
        self, synthetic_model, synthetic_candidate, config
    ):
        similarity = PairwiseSimilarity.build(synthetic_model)
        cohesion = family_evaluation.family_cohesion(
            [synthetic_candidate], synthetic_model, similarity=similarity
        )
        classified = pd.DataFrame(
            [
                {
                    "strategy": "test", "FamilyA": "F1", "FamilyB": "F2",
                    "FamilyALabel": "F1", "FamilyBLabel": "F2",
                    "OverlapBand": "high", "OverlapDriver": "shared questions",
                    "MaxFeatureJaccard": 0.5, "SharedPathways": 0,
                    "SharedSDs": 0, "SharedQuestions": 0, "SharedSnomed": 0,
                    "SdJaccard": 0.0, "QuestionJaccard": 0.5, "SnomedJaccard": 0.0,
                    "TransitionsAtoB": 5, "TransitionsBtoA": 0,
                    "PathwayCountA": 3, "PathwayCountB": 2,
                }
            ]
        )
        merges = family_overlap.merge_candidates(
            classified, {"test": synthetic_candidate}, synthetic_model, cohesion,
            config=config, similarity=similarity,
        )
        assert merges.iloc[0]["InternalEdgeGainIsMechanical"]
        assert "MeanPairwiseSdJaccardDelta" in merges.columns

    def test_split_is_only_proposed_when_two_parts_are_viable(self, synthetic_model, config):
        candidate = CandidateFamilySet(
            strategy="big", basis="hybrid", description="",
            membership=build_membership_frame(
                {"F1": {"PA1", "PA2", "PA3", "PA4", "PA5"}}, strategy="big"
            ),
        )
        similarity = PairwiseSimilarity.build(synthetic_model)
        cohesion = family_evaluation.family_cohesion(
            [candidate], synthetic_model, similarity=similarity
        )
        # Default minimum_split_part_size is 8, so a 5-pathway family cannot split.
        assert family_evaluation.split_candidates(
            [candidate], synthetic_model, cohesion, config=config, similarity=similarity
        ).empty

        permissive = FamilyDiscoveryConfig(
            minimum_split_part_size=2, split_review_size=4,
            hybrid_a_clinical_cohesion_threshold=0.9,
        )
        splits = family_evaluation.split_candidates(
            [candidate], synthetic_model, cohesion, config=permissive,
            similarity=similarity,
        )
        assert not splits.empty
        assert (splits["PartCount"] >= 2).all()
        assert splits["Recommendation"].str.contains("not made").all()

    def test_split_parts_never_lose_pathways_silently(self, synthetic_model):
        candidate = CandidateFamilySet(
            strategy="big", basis="hybrid", description="",
            membership=build_membership_frame(
                {"F1": {"PA1", "PA2", "PA3", "PA4", "PA5"}}, strategy="big"
            ),
        )
        similarity = PairwiseSimilarity.build(synthetic_model)
        permissive = FamilyDiscoveryConfig(
            minimum_split_part_size=2, split_review_size=4,
            hybrid_a_clinical_cohesion_threshold=0.9,
        )
        cohesion = family_evaluation.family_cohesion(
            [candidate], synthetic_model, similarity=similarity
        )
        splits = family_evaluation.split_candidates(
            [candidate], synthetic_model, cohesion, config=permissive,
            similarity=similarity,
        )
        for row in splits.itertuples():
            assert (
                row.PathwaysRetainedInParts + row.PathwaysBelowMinimumPartSize
                == row.PathwayCountBefore
            )

    def test_membership_change_percentage_is_label_invariant(self):
        default = {"A": 0, "B": 0, "C": 1, "D": 1}
        relabelled = {"A": 7, "B": 7, "C": 3, "D": 3}
        assert family_discovery._membership_change_percentage(default, relabelled) == 0.0

        moved = {"A": 0, "B": 0, "C": 0, "D": 1}
        # C moves into the family matched to default 0; one of four pathways moved.
        assert family_discovery._membership_change_percentage(default, moved) == pytest.approx(
            25.0
        )


# ======================================================================================
# Metadata classification
# ======================================================================================
class TestMetadataClassification:
    def test_age_classification_uses_the_supplied_adult_band(self):
        assert classify_age({1}, 1) == "adult_only"
        assert classify_age({2, 3}, 1) == "paediatric_only"
        assert classify_age({1, 2}, 1) == "adult_and_paediatric"
        assert classify_age(set(), 1) == "unspecified"
        assert classify_age({1}, None) == "unclassified"

    def test_trauma_classification_allows_both_values(self):
        labels = {0: "Non Trauma", 1: "Trauma"}
        assert classify_trauma({0}, labels) == "non_trauma"
        assert classify_trauma({1}, labels) == "trauma"
        assert classify_trauma({0, 1}, labels) == "trauma_and_non_trauma"
        assert classify_trauma(set(), labels) == "unspecified"

    def test_gender_classification_is_stable_and_order_independent(self):
        labels = {1: "Male", 2: "Female"}
        assert classify_gender({1}, labels) == "male_only"
        assert classify_gender({1, 2}, labels) == classify_gender({2, 1}, labels)
        assert classify_gender(set(), labels) == "unspecified"


# ======================================================================================
# Naming
# ======================================================================================
class TestFamilyNaming:
    def _cohesion(self, rows: list[dict]) -> pd.DataFrame:
        return pd.DataFrame(rows)

    def test_a_dominant_symptom_group_supplies_the_name(self, config):
        cohesion = self._cohesion(
            [
                {
                    "strategy": "test", "FamilyId": "F1", "PathwayCount": 10,
                    "DominantSymptomGroupShare": 0.8,
                    "DominantSymptomGroup": "Synthetic Group A",
                    "DominantClinicalAreaShare": 0.2, "DominantClinicalArea": "chest",
                    "DominantAreaGroupShare": 0.2, "DominantAreaGroup": "chest",
                }
            ]
        )
        candidate = CandidateFamilySet(
            strategy="test", basis="hybrid", description="",
            membership=build_membership_frame({"F1": {"PA1"}}, strategy="test"),
        )
        names = family_discovery.derive_family_names(candidate, cohesion, config=config)
        assert names.iloc[0]["FamilyName"] == "Synthetic Group A"
        assert "dominant symptom group" in names.iloc[0]["FamilyNameBasis"]

    def test_no_dominant_metadata_yields_a_neutral_name(self, config):
        cohesion = self._cohesion(
            [
                {
                    "strategy": "graph_louvain", "FamilyId": "F1", "PathwayCount": 10,
                    "DominantSymptomGroupShare": 0.2,
                    "DominantSymptomGroup": "Synthetic Group A",
                    "DominantClinicalAreaShare": 0.3, "DominantClinicalArea": "chest",
                    "DominantAreaGroupShare": 0.1, "DominantAreaGroup": "chest",
                }
            ]
        )
        candidate = CandidateFamilySet(
            strategy="graph_louvain", basis="graph_derived", description="",
            membership=build_membership_frame({"F1": {"PA1"}}, strategy="graph_louvain"),
        )
        names = family_discovery.derive_family_names(candidate, cohesion, config=config)
        assert names.iloc[0]["FamilyName"] == "Community_00"
        assert names.iloc[0]["FamilyNameBasis"] == "neutral"
