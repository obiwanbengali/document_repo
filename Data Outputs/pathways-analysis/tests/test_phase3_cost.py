from __future__ import annotations

from pathways_analysis.phase3_cost import structural_minimum_fanout


def test_structural_minimum_fanout_falls_back_without_outputs(tmp_path, monkeypatch):
    from pathways_analysis.config import Paths

    paths = Paths(project_root=tmp_path)
    assert structural_minimum_fanout(paths) == 1.0
