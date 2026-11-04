from __future__ import annotations

import pandas as pd

from pathways_analysis.phase3_cpt_sizing import (
    build_sensitivity,
    cpt_entries,
    free_parameters,
)


def test_cpt_entries_binary_child_two_binary_parents():
    assert cpt_entries(2, 2, 2) == 8


def test_free_parameters_respects_sum_to_one_constraint():
    assert free_parameters(3, 2, 2) == 8


def test_build_sensitivity_sums_variable_specific_child_states():
    variables = pd.DataFrame(
        [
            {
                "Representation": "deduplicated_monolith",
                "FamilyId": "",
                "VariableKey": "Q1",
                "state_cardinality": 2,
            },
            {
                "Representation": "deduplicated_monolith",
                "FamilyId": "",
                "VariableKey": "Q2",
                "state_cardinality": 4,
            },
        ]
    )

    summary, families = build_sensitivity(
        variables,
        parent_counts=[1],
        parent_state_cases={"median_parent_states": 3},
        storage_bytes=[4, 8],
    )

    row = summary.iloc[0]
    # Q1: 2*3 = 6; Q2: 4*3 = 12.
    assert row["TotalCptEntries"] == 18
    assert row["TotalFreeParameters"] == 12
    assert row["LargestVariableCptEntries"] == 12
    assert families.empty


def test_federated_family_totals_are_kept_separate():
    variables = pd.DataFrame(
        [
            {
                "Representation": "provisional_federated",
                "FamilyId": "F1",
                "VariableKey": "F1::Q1",
                "state_cardinality": 2,
            },
            {
                "Representation": "provisional_federated",
                "FamilyId": "F2",
                "VariableKey": "F2::Q1",
                "state_cardinality": 2,
            },
        ]
    )

    summary, families = build_sensitivity(
        variables,
        parent_counts=[0],
        parent_state_cases={"median_parent_states": 2},
        storage_bytes=[4],
    )

    assert summary.iloc[0]["TotalCptEntries"] == 4
    assert set(families["FamilyId"]) == {"F1", "F2"}
    assert set(families["TotalCptEntries"]) == {2}
