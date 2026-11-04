from __future__ import annotations

from pathways_analysis.phase3_runtime import (
    change_blast_radius,
    failure_modes,
    runtime_patterns,
)


def test_runtime_patterns_keep_logical_and_deployment_architecture_separate():
    patterns = runtime_patterns().set_index("PatternId")
    assert patterns.loc["federated_all_resident", "LogicalModel"] == "federated"
    assert "one central inference service" in patterns.loc[
        "federated_all_resident", "DeploymentShape"
    ]


def test_runtime_patterns_cover_four_declared_shapes():
    patterns = runtime_patterns()
    assert set(patterns["PatternId"]) == {
        "monolith_always_resident",
        "federated_all_resident",
        "federated_lazy_loaded",
        "hierarchical_shared_core",
    }


def test_failure_modes_include_shared_core_blast_radius():
    failures = failure_modes()
    rows = failures.loc[
        failures["PatternId"] == "hierarchical_shared_core", "LikelyScope"
    ].astype(str)
    assert any("multiple or all families" in value for value in rows)


def test_change_blast_radius_distinguishes_local_and_shared_changes():
    blast = change_blast_radius().set_index("PatternId")
    value = blast.loc["hierarchical_shared_core", "ModelReleaseBlastRadius"]
    assert "family-local" in value
    assert "broad" in value
