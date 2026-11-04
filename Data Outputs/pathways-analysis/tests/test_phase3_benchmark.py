from __future__ import annotations

from pathways_analysis.phase3_benchmark import (
    planned_model_sizes,
    rolling_window_edges,
)


def test_rolling_window_edges_is_acyclic_by_construction():
    edges = rolling_window_edges(5, 2)
    assert ("X00000", "X00001") in edges
    assert ("X00000", "X00002") in edges
    assert ("X00001", "X00002") in edges
    assert all(source < target for source, target in edges)


def test_parent_count_is_bounded_for_early_nodes():
    edges = rolling_window_edges(4, 3)
    incoming = {}
    for _source, target in edges:
        incoming[target] = incoming.get(target, 0) + 1
    assert incoming["X00001"] == 1
    assert incoming["X00002"] == 2
    assert incoming["X00003"] == 3


def test_planned_model_sizes_includes_real_target_when_below_cap():
    assert planned_model_sizes(72, [25, 50, 100, 250], 250) == [25, 50, 72]


def test_planned_model_sizes_caps_large_model():
    assert planned_model_sizes(1000, [25, 50, 100, 250], 250) == [25, 50, 100, 250]
