"""Unit tests for pairwise set-similarity calculations.

The Jaccard implementation uses a matrix product for speed, so these tests pin the
result against hand-computed values to prove the optimisation stays faithful to the
set definition.
"""

from __future__ import annotations

import pandas as pd
import pytest

from pathways_analysis import graph as gt


def membership(pairs: list[tuple[str, str]]) -> pd.DataFrame:
    return pd.DataFrame(pairs, columns=["pathway_key", "question_key"])


class TestJaccardSimilarity:
    def test_hand_computed_values(self):
        # A = {Q1, Q2, Q3}; B = {Q2, Q3, Q4}
        # intersection = 2, union = 4, Jaccard = 0.5
        frame = membership(
            [("A", "Q1"), ("A", "Q2"), ("A", "Q3"),
             ("B", "Q2"), ("B", "Q3"), ("B", "Q4")]
        )
        result = gt.jaccard_similarity(
            frame, entity_column="pathway_key", feature_column="question_key"
        )
        assert len(result) == 1
        row = result.iloc[0]
        assert row["pathway_key_a"] == "A"
        assert row["pathway_key_b"] == "B"
        assert row["set_size_a"] == 3
        assert row["set_size_b"] == 3
        assert row["intersection_count"] == 2
        assert row["union_count"] == 4
        assert row["jaccard_similarity"] == pytest.approx(0.5)

    def test_identical_sets_score_one(self):
        frame = membership([("A", "Q1"), ("A", "Q2"), ("B", "Q1"), ("B", "Q2")])
        result = gt.jaccard_similarity(
            frame, entity_column="pathway_key", feature_column="question_key"
        )
        assert result.iloc[0]["jaccard_similarity"] == pytest.approx(1.0)

    def test_disjoint_sets_are_omitted_by_default(self):
        frame = membership([("A", "Q1"), ("B", "Q2")])
        result = gt.jaccard_similarity(
            frame, entity_column="pathway_key", feature_column="question_key"
        )
        assert result.empty

    def test_min_intersection_zero_returns_full_upper_triangle(self):
        frame = membership([("A", "Q1"), ("B", "Q2"), ("C", "Q3")])
        result = gt.jaccard_similarity(
            frame,
            entity_column="pathway_key",
            feature_column="question_key",
            min_intersection=0,
        )
        assert len(result) == gt.pair_count(3)
        assert (result["intersection_count"] == 0).all()
        assert (result["jaccard_similarity"] == 0.0).all()

    def test_duplicate_pairs_are_deduplicated(self):
        # A repeated (pathway, question) pair must not inflate the set size: the same
        # question used at several order positions is still one question.
        frame = membership(
            [("A", "Q1"), ("A", "Q1"), ("A", "Q1"), ("B", "Q1"), ("B", "Q2")]
        )
        row = gt.jaccard_similarity(
            frame, entity_column="pathway_key", feature_column="question_key"
        ).iloc[0]
        assert row["set_size_a"] == 1
        assert row["intersection_count"] == 1
        assert row["union_count"] == 2
        assert row["jaccard_similarity"] == pytest.approx(0.5)

    def test_only_upper_triangle_is_emitted(self):
        frame = membership(
            [("A", "Q1"), ("B", "Q1"), ("C", "Q1")]
        )
        result = gt.jaccard_similarity(
            frame, entity_column="pathway_key", feature_column="question_key"
        )
        pairs = set(zip(result["pathway_key_a"], result["pathway_key_b"]))
        assert pairs == {("A", "B"), ("A", "C"), ("B", "C")}
        assert all(a < b for a, b in pairs)

    def test_sorted_by_descending_similarity(self):
        frame = membership(
            [
                ("A", "Q1"), ("A", "Q2"),
                ("B", "Q1"), ("B", "Q2"),   # identical to A -> 1.0
                ("C", "Q2"), ("C", "Q3"), ("C", "Q4"),  # partial overlap -> lower
            ]
        )
        result = gt.jaccard_similarity(
            frame, entity_column="pathway_key", feature_column="question_key"
        )
        assert list(result["jaccard_similarity"]) == sorted(
            result["jaccard_similarity"], reverse=True
        )
        assert result.iloc[0]["jaccard_similarity"] == pytest.approx(1.0)

    def test_nulls_are_dropped(self):
        frame = pd.DataFrame(
            {
                "pathway_key": ["A", "A", "B", "B"],
                "question_key": ["Q1", None, "Q1", "Q2"],
            }
        )
        row = gt.jaccard_similarity(
            frame, entity_column="pathway_key", feature_column="question_key"
        ).iloc[0]
        assert row["set_size_a"] == 1

    def test_single_entity_returns_empty(self):
        frame = membership([("A", "Q1"), ("A", "Q2")])
        assert gt.jaccard_similarity(
            frame, entity_column="pathway_key", feature_column="question_key"
        ).empty

    def test_numeric_feature_column(self):
        frame = pd.DataFrame(
            {"pathway_key": ["A", "A", "B"], "sd_id": [10, 20, 20]}
        )
        row = gt.jaccard_similarity(
            frame, entity_column="pathway_key", feature_column="sd_id"
        ).iloc[0]
        assert row["intersection_count"] == 1
        assert row["union_count"] == 2

    def test_missing_column_raises(self):
        with pytest.raises(ValueError, match="missing required column"):
            gt.jaccard_similarity(
                membership([("A", "Q1")]),
                entity_column="pathway_key",
                feature_column="nope",
            )

    def test_symmetry_against_brute_force(self):
        # Cross-check the matrix implementation against a naive set computation.
        pairs = [
            ("P1", "Q1"), ("P1", "Q2"), ("P1", "Q3"),
            ("P2", "Q2"), ("P2", "Q3"), ("P2", "Q5"),
            ("P3", "Q5"), ("P3", "Q6"),
            ("P4", "Q1"), ("P4", "Q6"), ("P4", "Q7"), ("P4", "Q8"),
        ]
        frame = membership(pairs)
        result = gt.jaccard_similarity(
            frame, entity_column="pathway_key", feature_column="question_key"
        )

        sets: dict[str, set[str]] = {}
        for entity, feature in pairs:
            sets.setdefault(entity, set()).add(feature)

        for row in result.itertuples():
            left = sets[row.pathway_key_a]
            right = sets[row.pathway_key_b]
            assert row.intersection_count == len(left & right)
            assert row.union_count == len(left | right)
            assert row.jaccard_similarity == pytest.approx(
                len(left & right) / len(left | right), abs=1e-6
            )


class TestDescribeDistribution:
    def test_percentiles_and_basics(self):
        stats = gt.describe_distribution(range(1, 101), percentiles=(75, 90, 95, 99))
        assert stats["count"] == 100
        assert stats["min"] == 1.0
        assert stats["max"] == 100.0
        assert stats["median"] == pytest.approx(50.5)
        assert stats["p75"] == pytest.approx(75.25)
        assert stats["p95"] == pytest.approx(95.05)

    def test_empty_input_returns_nan_not_exception(self):
        stats = gt.describe_distribution([], percentiles=(90,))
        assert stats["count"] == 0
        assert pd.isna(stats["mean"])
        assert pd.isna(stats["p90"])

    def test_nulls_are_ignored(self):
        stats = gt.describe_distribution(pd.Series([1.0, None, 3.0]), percentiles=(90,))
        assert stats["count"] == 2
        assert stats["mean"] == pytest.approx(2.0)


class TestPairCount:
    @pytest.mark.parametrize(
        ("n", "expected"), [(0, 0), (1, 0), (2, 1), (3, 3), (4, 6), (815, 331705)]
    )
    def test_known_values(self, n, expected):
        assert gt.pair_count(n) == expected
