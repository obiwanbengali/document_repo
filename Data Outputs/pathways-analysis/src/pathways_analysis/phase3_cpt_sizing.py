"""Phase 3B CPT-growth and raw storage sensitivity.

Uses the Phase 3A variable/cardinality baseline and declared parent-count assumptions.
It does not claim that deterministic Pathways relationships are Bayesian dependencies.

The output is a sensitivity model: for each representation, assume every variable has
N parents and that each parent has either the measured median or measured p90 state
cardinality. This isolates the combinatorial effect of parent count and state space.

Runtime memory and serialised artefact size are intentionally deferred to Phase 3C,
where they can be measured against a concrete BN library rather than guessed.
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path
from typing import Final

import pandas as pd
import yaml

from .config import ConfigurationError, Paths
from .profiling import configure_logging

LOGGER: Final = logging.getLogger("pathways_analysis.phase3_cpt_sizing")


def _load_yaml(path: Path) -> dict:
    if not path.is_file():
        raise ConfigurationError(f"Configuration not found: {path}")
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def cpt_entries(child_states: int, parent_states: int, parent_count: int) -> int:
    """Return CPT probability cells for one variable under a homogeneous parent case."""
    if child_states < 1 or parent_states < 1 or parent_count < 0:
        raise ValueError("State counts must be >=1 and parent_count must be >=0.")
    return int(child_states * (parent_states ** parent_count))


def free_parameters(child_states: int, parent_states: int, parent_count: int) -> int:
    """Return independent CPT parameters after the sum-to-one constraint."""
    if child_states < 1 or parent_states < 1 or parent_count < 0:
        raise ValueError("State counts must be >=1 and parent_count must be >=0.")
    return int((child_states - 1) * (parent_states ** parent_count))


def _read_phase3a(paths: Paths) -> tuple[pd.DataFrame, pd.DataFrame]:
    variables_path = paths.phase3_tables / "variable_cardinality_baseline.csv"
    state_path = paths.phase3_tables / "state_cardinality_summary.csv"
    missing = [str(p) for p in (variables_path, state_path) if not p.is_file()]
    if missing:
        raise ConfigurationError(
            "Phase 3A outputs are missing: "
            + ", ".join(missing)
            + ". Run python -m pathways_analysis.phase3_sizing first."
        )

    variables = pd.read_csv(variables_path)
    states = pd.read_csv(state_path)

    required_variables = {
        "Representation",
        "FamilyId",
        "VariableKey",
        "state_cardinality",
    }
    missing_columns = required_variables - set(variables.columns)
    if missing_columns:
        raise ConfigurationError(
            f"{variables_path} is missing columns {sorted(missing_columns)}."
        )

    return variables, states


def _state_cases(states: pd.DataFrame) -> dict[str, int]:
    row = states.loc[states["Scope"] == "deduplicated_questions"]
    if row.empty:
        raise ConfigurationError(
            "state_cardinality_summary.csv has no deduplicated_questions row."
        )
    median = max(int(round(float(row.iloc[0]["median"]))), 1)
    p90 = max(int(round(float(row.iloc[0]["p90"]))), 1)
    return {
        "median_parent_states": median,
        "p90_parent_states": p90,
    }


def _usable_variables(variables: pd.DataFrame) -> pd.DataFrame:
    frame = variables.copy()
    frame["state_cardinality"] = pd.to_numeric(
        frame["state_cardinality"], errors="coerce"
    )
    missing = int(frame["state_cardinality"].isna().sum())
    zero = int((frame["state_cardinality"].fillna(0) < 1).sum())
    if missing or zero:
        LOGGER.warning(
            "%d variables have missing cardinality and %d have cardinality <1; "
            "they are excluded from CPT sizing and reported separately.",
            missing,
            zero,
        )
    return frame.loc[frame["state_cardinality"].fillna(0) >= 1].copy()


def build_sensitivity(
    variables: pd.DataFrame,
    *,
    parent_counts: list[int],
    parent_state_cases: dict[str, int],
    storage_bytes: list[int],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Build representation-level and family-level CPT sensitivity tables."""
    usable = _usable_variables(variables)
    rows: list[dict] = []
    family_rows: list[dict] = []

    for representation, rep in usable.groupby("Representation", dropna=False):
        for state_case, parent_states in parent_state_cases.items():
            for parent_count in parent_counts:
                entries = rep["state_cardinality"].map(
                    lambda child, states=parent_states, parents=parent_count: (
                        cpt_entries(int(child), int(states), int(parents))
                    )
                )
                params = rep["state_cardinality"].map(
                    lambda child, states=parent_states, parents=parent_count: (
                        free_parameters(int(child), int(states), int(parents))
                    )
                )
                base = {
                    "Representation": representation,
                    "ParentCount": int(parent_count),
                    "ParentStateCase": state_case,
                    "AssumedParentStatesEach": int(parent_states),
                    "VariableCountSized": int(len(rep)),
                    "TotalCptEntries": int(entries.sum()),
                    "TotalFreeParameters": int(params.sum()),
                    "LargestVariableCptEntries": int(entries.max()),
                    "MedianVariableCptEntries": float(entries.median()),
                    "EvidenceClass": "assumption+derived",
                }
                for byte_width in storage_bytes:
                    base[f"RawProbabilityBytesFloat{byte_width * 8}"] = int(
                        entries.sum() * int(byte_width)
                    )
                    base[f"RawProbabilityMiBFloat{byte_width * 8}"] = round(
                        entries.sum() * int(byte_width) / (1024 ** 2), 3
                    )
                    base[f"RawProbabilityGiBFloat{byte_width * 8}"] = round(
                        entries.sum() * int(byte_width) / (1024 ** 3), 6
                    )
                rows.append(base)

                if representation == "provisional_federated":
                    for family_id, family in rep.groupby("FamilyId", dropna=False):
                        family_entries = family["state_cardinality"].map(
                            lambda child, states=parent_states, parents=parent_count: (
                                cpt_entries(int(child), int(states), int(parents))
                            )
                        )
                        family_params = family["state_cardinality"].map(
                            lambda child, states=parent_states, parents=parent_count: (
                                free_parameters(int(child), int(states), int(parents))
                            )
                        )
                        family_row = {
                            "FamilyId": family_id,
                            "ParentCount": int(parent_count),
                            "ParentStateCase": state_case,
                            "AssumedParentStatesEach": int(parent_states),
                            "VariableCountSized": int(len(family)),
                            "TotalCptEntries": int(family_entries.sum()),
                            "TotalFreeParameters": int(family_params.sum()),
                            "LargestVariableCptEntries": int(family_entries.max()),
                            "EvidenceClass": "candidate+assumption+derived",
                        }
                        for byte_width in storage_bytes:
                            family_row[f"RawProbabilityMiBFloat{byte_width * 8}"] = round(
                                family_entries.sum() * int(byte_width) / (1024 ** 2),
                                3,
                            )
                        family_rows.append(family_row)

    summary = pd.DataFrame(rows).sort_values(
        ["ParentCount", "ParentStateCase", "Representation"],
        ignore_index=True,
    )
    families = pd.DataFrame(family_rows)
    if not families.empty:
        families = families.sort_values(
            ["ParentCount", "ParentStateCase", "TotalCptEntries", "FamilyId"],
            ascending=[True, True, False, True],
            ignore_index=True,
        )
    return summary, families


def _growth_table(summary: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (state_case, representation), group in summary.groupby(
        ["ParentStateCase", "Representation"]
    ):
        ordered = group.sort_values("ParentCount")
        previous = None
        for row in ordered.itertuples():
            growth = None if previous is None else row.TotalCptEntries / previous
            rows.append(
                {
                    "Representation": representation,
                    "ParentStateCase": state_case,
                    "ParentCount": int(row.ParentCount),
                    "TotalCptEntries": int(row.TotalCptEntries),
                    "GrowthVsPreviousParentCount": (
                        round(float(growth), 4) if growth is not None else None
                    ),
                }
            )
            previous = row.TotalCptEntries
    return pd.DataFrame(rows)


def run_phase3b(paths: Paths) -> None:
    """Generate Phase 3B structural sizing outputs."""
    paths.ensure_phase3_directories()
    config = _load_yaml(paths.config_dir / "phase3.yaml")
    variables, states = _read_phase3a(paths)

    parent_counts = [
        int(value) for value in config["cpt_sizing"]["parent_count_scenarios"]
    ]
    storage_bytes = [
        int(value) for value in config["cpt_sizing"]["probability_storage_bytes"]
    ]
    parent_state_cases = _state_cases(states)

    summary, families = build_sensitivity(
        variables,
        parent_counts=parent_counts,
        parent_state_cases=parent_state_cases,
        storage_bytes=storage_bytes,
    )
    growth = _growth_table(summary)

    exclusions = (
        variables.assign(
            state_cardinality=pd.to_numeric(
                variables["state_cardinality"], errors="coerce"
            )
        )
        .loc[lambda x: x["state_cardinality"].fillna(0) < 1]
        .groupby("Representation")
        .size()
        .rename("ExcludedVariableCount")
        .reset_index()
    )

    notes = pd.DataFrame(
        [
            {
                "Item": "Bayesian dependencies",
                "EvidenceClass": "assumption",
                "Statement": (
                    "Parent counts are sensitivity cases only. Phase 3B does not map "
                    "deterministic Pathways edges directly into Bayesian dependencies."
                ),
            },
            {
                "Item": "Parent state cardinality",
                "EvidenceClass": "measured+assumption",
                "Statement": (
                    "Parent state cases use measured median and p90 authored answer "
                    "cardinality, applied homogeneously to isolate CPT growth."
                ),
            },
            {
                "Item": "Raw storage",
                "EvidenceClass": "derived",
                "Statement": (
                    "Storage figures count probability arrays only. They exclude node "
                    "objects, factor metadata, indexes, evidence caches and interpreter "
                    "overhead."
                ),
            },
            {
                "Item": "Runtime memory",
                "EvidenceClass": "deferred",
                "Statement": (
                    "Runtime memory and serialised artefact size will be measured in "
                    "Phase 3C against a concrete BN implementation rather than estimated "
                    "from an arbitrary multiplier."
                ),
            },
        ]
    )

    outputs = {
        "cpt_sizing_by_representation.csv": summary,
        "cpt_growth_curve.csv": growth,
        "family_cpt_sizing.csv": families,
        "cpt_sizing_exclusions.csv": exclusions,
        "phase3b_method_notes.csv": notes,
    }
    for name, frame in outputs.items():
        path = paths.phase3_tables / name
        frame.to_csv(path, index=False)
        LOGGER.info("Wrote %-42s %6d rows", path, len(frame))

    LOGGER.info(
        "Phase 3B complete: %d representation sensitivity rows, %d family rows.",
        len(summary),
        len(families),
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Phase 3B CPT growth and raw probability storage sensitivity."
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    configure_logging(args.log_level)
    paths = Paths.discover()
    try:
        run_phase3b(paths)
        return 0
    except ConfigurationError as exc:
        LOGGER.error("Configuration error: %s", exc)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
