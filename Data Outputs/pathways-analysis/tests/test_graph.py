"""Unit tests for graph transformation and cohesion metrics.

These use small hand-built fixtures whose expected values can be checked by hand, so a
regression in the aggregation or cohesion rules is caught without a database.
"""

from __future__ import annotations

import networkx as nx
import pandas as pd
import pytest

from pathways_analysis import graph as gt


def make_transfers(rows: list[dict]) -> pd.DataFrame:
    """Build a transfer frame with the columns aggregate_pathway_edges requires."""
    return pd.DataFrame(
        rows,
        columns=[
            "source_pathway_key", "resolved_pathway_key", "question_key",
            "answer_number", "source_order", "branch",
        ],
    )


class TestAggregatePathwayEdges:
    def test_counts_branch_slots_separately_from_answer_branches(self):
        # One answer offering the same target on all four skillset branches is four
        # transfer records but a single answer branch.
        transfers = make_transfers(
            [
                {"source_pathway_key": "PA1", "resolved_pathway_key": "PA2",
                 "question_key": "TX1", "answer_number": 1, "source_order": 100,
                 "branch": branch}
                for branch in ("T1", "T2", "T3", "T4")
            ]
        )
        edges = gt.aggregate_pathway_edges(transfers)

        assert len(edges) == 1
        row = edges.iloc[0]
        assert row["transition_count"] == 4
        assert row["branches"] == 4
        assert row["answer_branches"] == 1
        assert row["source_question_count"] == 1
        assert row["source_order_count"] == 1

    def test_distinct_questions_and_orders_are_counted(self):
        transfers = make_transfers(
            [
                {"source_pathway_key": "PA1", "resolved_pathway_key": "PA2",
                 "question_key": "TX1", "answer_number": 1, "source_order": 100,
                 "branch": "T1"},
                {"source_pathway_key": "PA1", "resolved_pathway_key": "PA2",
                 "question_key": "TX2", "answer_number": 2, "source_order": 200,
                 "branch": "T1"},
            ]
        )
        row = gt.aggregate_pathway_edges(transfers).iloc[0]
        assert row["transition_count"] == 2
        assert row["source_question_count"] == 2
        assert row["source_order_count"] == 2
        assert row["answer_branches"] == 2

    def test_separate_targets_produce_separate_edges_sorted(self):
        transfers = make_transfers(
            [
                {"source_pathway_key": "PA1", "resolved_pathway_key": "PZ9",
                 "question_key": "TX1", "answer_number": 1, "source_order": 100,
                 "branch": "T1"},
                {"source_pathway_key": "PA1", "resolved_pathway_key": "PA2",
                 "question_key": "TX1", "answer_number": 2, "source_order": 100,
                 "branch": "T1"},
            ]
        )
        edges = gt.aggregate_pathway_edges(transfers)
        assert list(edges["target_pathway_key"]) == ["PA2", "PZ9"]

    def test_empty_input_returns_empty_frame_with_schema(self):
        edges = gt.aggregate_pathway_edges(make_transfers([]))
        assert edges.empty
        assert "transition_count" in edges.columns

    def test_missing_column_raises(self):
        with pytest.raises(ValueError, match="missing required columns"):
            gt.aggregate_pathway_edges(pd.DataFrame({"source_pathway_key": ["PA1"]}))


class TestBuildPathwayGraph:
    def test_edge_attributes_are_attached(self):
        edges = pd.DataFrame(
            [
                {"source_pathway_key": "A", "target_pathway_key": "B",
                 "transition_count": 3, "branches": 2, "answer_branches": 2,
                 "source_question_count": 1, "source_order_count": 1},
            ]
        )
        graph = gt.build_pathway_graph(edges)
        assert graph.number_of_nodes() == 2
        assert graph["A"]["B"]["transition_count"] == 3
        assert graph["A"]["B"]["source_question_count"] == 1

    def test_isolated_nodes_from_attributes_are_retained(self):
        edges = pd.DataFrame(
            [{"source_pathway_key": "A", "target_pathway_key": "B",
              "transition_count": 1}]
        )
        attributes = pd.DataFrame(
            [
                {"pathway_key": "A", "is_active": True},
                {"pathway_key": "B", "is_active": True},
                {"pathway_key": "LONELY", "is_active": True},
            ]
        )
        graph = gt.build_pathway_graph(edges, attributes)
        assert graph.number_of_nodes() == 3
        assert graph.degree("LONELY") == 0
        assert graph.nodes["A"]["is_active"] is True

    def test_self_loops_are_preserved(self):
        edges = pd.DataFrame(
            [{"source_pathway_key": "A", "target_pathway_key": "A",
              "transition_count": 2}]
        )
        graph = gt.build_pathway_graph(edges)
        assert list(nx.selfloop_edges(graph)) == [("A", "A")]


class TestGraphSummary:
    def test_reciprocity_and_self_loops(self):
        graph = nx.DiGraph()
        graph.add_edge("A", "B", transition_count=1)
        graph.add_edge("B", "A", transition_count=2)
        graph.add_edge("C", "C", transition_count=5)
        graph.add_node("D")

        summary = gt.graph_summary(graph)
        assert summary["node_count"] == 4
        assert summary["edge_count"] == 3
        assert summary["self_loop_count"] == 1
        # A<->B is one reciprocal pair; the C self loop must not be counted as one.
        assert summary["reciprocal_pair_count"] == 1
        assert summary["reciprocal_edge_count"] == 2
        assert summary["isolated_node_count"] == 1
        assert summary["total_transition_count"] == 8

    def test_components(self):
        graph = nx.DiGraph()
        graph.add_edge("A", "B")
        graph.add_edge("B", "A")
        graph.add_edge("X", "Y")
        summary = gt.graph_summary(graph)
        assert summary["weakly_connected_components"] == 2
        assert summary["non_trivial_strongly_connected_components"] == 1
        assert summary["largest_strongly_connected_component"] == 2

    def test_empty_graph_does_not_raise(self):
        summary = gt.graph_summary(nx.DiGraph())
        assert summary["node_count"] == 0
        assert summary["density"] == 0.0


class TestNodeMetrics:
    def test_degrees_and_weights(self):
        graph = nx.DiGraph()
        graph.add_edge("A", "B", transition_count=4)
        graph.add_edge("C", "B", transition_count=6)

        metrics = gt.node_metrics(graph).set_index("pathway_key")
        assert metrics.loc["B", "in_degree"] == 2
        assert metrics.loc["B", "weighted_in_degree"] == 10
        assert metrics.loc["A", "out_degree"] == 1
        assert metrics.loc["A", "weighted_out_degree"] == 4
        assert metrics["pagerank"].sum() == pytest.approx(1.0, abs=1e-6)

    def test_self_loop_excluded_from_successor_count(self):
        graph = nx.DiGraph()
        graph.add_edge("A", "A", transition_count=1)
        graph.add_edge("A", "B", transition_count=1)
        metrics = gt.node_metrics(graph).set_index("pathway_key")
        assert metrics.loc["A", "successor_count"] == 1
        assert bool(metrics.loc["A", "self_loop"]) is True

    def test_empty_graph_returns_schema(self):
        metrics = gt.node_metrics(nx.DiGraph())
        assert metrics.empty
        assert "betweenness_centrality" in metrics.columns


class TestUndirectedProjection:
    def test_reciprocal_weights_are_summed_and_self_loops_dropped(self):
        graph = nx.DiGraph()
        graph.add_edge("A", "B", transition_count=3)
        graph.add_edge("B", "A", transition_count=4)
        graph.add_edge("A", "A", transition_count=9)

        projection = gt.undirected_projection(graph)
        assert projection.number_of_edges() == 1
        assert projection["A"]["B"]["weight"] == 7
        assert not list(nx.selfloop_edges(projection))


class TestGroupCohesion:
    def test_internal_and_outgoing_edges(self):
        graph = nx.DiGraph()
        graph.add_edge("A", "B", transition_count=2)  # internal to G1
        graph.add_edge("A", "X", transition_count=5)  # leaves G1
        graph.add_edge("X", "B", transition_count=1)  # enters G1

        cohesion = gt.group_cohesion(
            graph, {"A": "G1", "B": "G1", "X": "G2"}
        ).set_index("group_id")

        assert cohesion.loc["G1", "internal_edges"] == 1
        assert cohesion.loc["G1", "outgoing_edges"] == 1
        assert cohesion.loc["G1", "incoming_edges"] == 1
        assert cohesion.loc["G1", "internal_transition_count"] == 2
        assert cohesion.loc["G1", "outgoing_transition_count"] == 5
        assert cohesion.loc["G1", "internal_edge_percentage"] == 50.0

    def test_self_loop_counts_as_internal(self):
        graph = nx.DiGraph()
        graph.add_edge("A", "A", transition_count=1)
        cohesion = gt.group_cohesion(graph, {"A": "G1"}).set_index("group_id")
        assert cohesion.loc["G1", "internal_edges"] == 1
        assert cohesion.loc["G1", "internal_edge_percentage"] == 100.0

    def test_group_with_no_boundary_edges_is_nan_not_zero(self):
        graph = nx.DiGraph()
        graph.add_node("A")
        cohesion = gt.group_cohesion(graph, {"A": "G1"}).set_index("group_id")
        assert pd.isna(cohesion.loc["G1", "internal_edge_percentage"])

    def test_overlapping_membership_counts_pathway_in_every_group(self):
        graph = nx.DiGraph()
        graph.add_edge("A", "B", transition_count=1)
        cohesion = gt.group_cohesion(
            graph, {"A": {"G1", "G2"}, "B": {"G1"}}, group_label="area"
        ).set_index("area")

        # A belongs to both areas, so G1 sees the edge as internal while G2 sees it
        # leaving.
        assert cohesion.loc["G1", "internal_edges"] == 1
        assert cohesion.loc["G2", "outgoing_edges"] == 1
        assert cohesion.loc["G2", "internal_edges"] == 0

    def test_none_membership_is_skipped(self):
        graph = nx.DiGraph()
        graph.add_edge("A", "B", transition_count=1)
        cohesion = gt.group_cohesion(graph, {"A": "G1", "B": None})
        assert list(cohesion["group_id"]) == ["G1"]

    def test_members_absent_from_graph_are_reported_separately(self):
        graph = nx.DiGraph()
        graph.add_node("A")
        cohesion = gt.group_cohesion(graph, {"A": "G1", "GHOST": "G1"}).set_index(
            "group_id"
        )
        assert cohesion.loc["G1", "pathway_count"] == 2
        assert cohesion.loc["G1", "pathways_in_graph"] == 1


class TestCommunities:
    def test_two_cliques_are_separated(self):
        graph = nx.DiGraph()
        for left, right in [("A", "B"), ("B", "C"), ("C", "A")]:
            graph.add_edge(left, right, transition_count=10)
        for left, right in [("X", "Y"), ("Y", "Z"), ("Z", "X")]:
            graph.add_edge(left, right, transition_count=10)
        graph.add_edge("C", "X", transition_count=1)

        partitions = gt.detect_communities(graph)
        assert partitions, "expected at least one algorithm to produce a partition"
        for algorithm, membership in partitions.items():
            assert membership["A"] == membership["B"] == membership["C"], algorithm
            assert membership["X"] == membership["Y"] == membership["Z"], algorithm
            assert membership["A"] != membership["X"], algorithm

    def test_community_ids_are_renumbered_largest_first(self):
        graph = nx.DiGraph()
        for left, right in [("A", "B"), ("B", "C"), ("C", "D"), ("D", "A")]:
            graph.add_edge(left, right, transition_count=10)
        graph.add_edge("Y", "Z", transition_count=10)

        partitions = gt.detect_communities(graph)
        for membership in partitions.values():
            sizes = pd.Series(list(membership.values())).value_counts().sort_index()
            assert sizes.iloc[0] >= sizes.iloc[-1]
            assert membership["A"] == 0

    def test_detection_is_deterministic(self):
        graph = nx.DiGraph()
        for index in range(12):
            graph.add_edge(f"N{index}", f"N{(index + 1) % 12}", transition_count=3)
        first = gt.detect_communities(graph)
        second = gt.detect_communities(graph)
        assert first == second

    def test_community_summary_shape(self):
        graph = nx.DiGraph()
        graph.add_edge("A", "B", transition_count=1)
        summary = gt.community_summary(graph, {"A": 0, "B": 0}, algorithm="test")
        assert summary.loc[0, "algorithm"] == "test"
        assert "external_edges" in summary.columns
        assert summary.loc[0, "internal_edges"] == 1

    def test_empty_graph_yields_no_partitions(self):
        assert gt.detect_communities(nx.DiGraph()) == {}
