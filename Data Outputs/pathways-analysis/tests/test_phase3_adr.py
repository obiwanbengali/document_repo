from __future__ import annotations

from pathways_analysis.phase3_adr import runtime_tradeoffs


def test_runtime_tradeoffs_do_not_score_or_select_a_winner():
    tradeoffs = runtime_tradeoffs()
    assert "Score" not in tradeoffs.columns
    assert "Winner" not in tradeoffs.columns
    assert set(tradeoffs.columns) == {
        "Representation",
        "Strength",
        "Tradeoff",
        "EvidenceClass",
    }
