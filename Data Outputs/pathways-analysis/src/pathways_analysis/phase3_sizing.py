"""Phase 3A representation sizing.

Produces the first quantitative Phase 3 evidence from measured Pathways structure and
the provisional Phase 2 family set.

This module deliberately does not transform the deterministic graph into a Bayesian DAG.
It sizes candidate variable representations only. CPT growth and Bayesian edge structure
remain sensitivity analysis until an explicit DAG transformation is agreed.
"""

from __future__ import annotations

import argparse
import logging
from typing import Final

import pandas as pd
import yaml

from .config import ConfigurationError, DatabaseSettings, Paths
from .db import DatabaseConnectionError, PathwaysDatabase
from .profiling import configure_logging, load_dotenv_if_present

LOGGER: Final = logging.getLogger("pathways_analysis.phase3_sizing")


def _load_config(paths: Paths) -> dict:
    path = paths.config_dir / "phase3.yaml"
    if not path.is_file():
        raise ConfigurationError(f"Phase 3 configuration not found: {path}")
    with path.open("r", encoding="utf-8") as handle:
        loaded = yaml.safe_load(handle) or {}
    return loaded


def _load_family_membership(paths: Paths) -> pd.DataFrame:
    path = paths.phase2_tables / "candidate_family_membership.csv"
    if not path.is_file():
        raise ConfigurationError(
            f"Phase 2 family membership not found: {path}. "
            "Run python -m pathways_analysis.family_discovery first."
        )
    frame = pd.read_csv(path)
    required = {"FamilyId", "PathwayKey"}
    missing = required - set(frame.columns)
    if missing:
        raise ConfigurationError(
            f"{path} is missing required column(s): {sorted(missing)}"
        )
    frame = frame[["FamilyId", "PathwayKey"]].dropna().copy()
    frame["PathwayKey"] = frame["PathwayKey"].astype(str).str.strip().str.upper()
    frame["FamilyId"] = frame["FamilyId"].astype(str).str.strip()
    return frame.drop_duplicates()


def _state_summary(values: pd.Series) -> dict[str, float]:
    usable = pd.to_numeric(values, errors="coerce").dropna()
    usable = usable.loc[usable > 0]
    if usable.empty:
        return {
            "count": 0,
            "min": 0,
            "median": 0,
            "p90": 0,
            "p95": 0,
            "max": 0,
            "mean": 0,
        }
    return {
        "count": int(len(usable)),
        "min": int(usable.min()),
        "median": float(usable.median()),
        "p90": float(usable.quantile(0.90)),
        "p95": float(usable.quantile(0.95)),
        "max": int(usable.max()),
        "mean": float(usable.mean()),
    }


def run_phase3a(database: PathwaysDatabase, paths: Paths) -> None:
    """Generate Phase 3A sizing evidence."""
    config = _load_config(paths)
    paths.ensure_phase3_directories()

    occurrences = database.read_query("phase3_active_tx_occurrences")
    questions = database.read_query("phase3_active_question_catalogue")
    membership = _load_family_membership(paths)

    occurrences["pathway_key"] = occurrences["pathway_key"].astype(str).str.upper()
    occurrences["question_key"] = occurrences["question_key"].astype(str).str.upper()
    questions["question_key"] = questions["question_key"].astype(str).str.upper()

    literal_variables = int(len(occurrences))
    deduplicated_variables = int(questions["question_key"].nunique())

    family_occurrences = membership.merge(
        occurrences[["pathway_key", "question_key", "state_cardinality"]],
        left_on="PathwayKey",
        right_on="pathway_key",
        how="left",
    )
    family_occurrences = family_occurrences.dropna(subset=["question_key"])

    family_table = (
        family_occurrences.groupby("FamilyId")
        .agg(
            PathwayCount=("PathwayKey", "nunique"),
            VariableCount=("question_key", "nunique"),
            VariableOccurrences=("question_key", "size"),
            MedianStateCardinality=("state_cardinality", "median"),
            MaxStateCardinality=("state_cardinality", "max"),
        )
        .reset_index()
        .sort_values(["VariableCount", "FamilyId"], ascending=[False, True])
    )

    federated_variable_copies = int(family_table["VariableCount"].sum())
    shared_copy_overhead = federated_variable_copies - deduplicated_variables

    representation_summary = pd.DataFrame(
        [
            {
                "Representation": "literal_monolith",
                "Label": config["representations"]["literal_monolith"]["label"],
                "CandidateVariableCount": literal_variables,
                "VariableIdentity": "pathway_order_occurrence",
                "EvidenceClass": "derived",
                "Interpretation": "Structural upper bound; not a proposed Bayesian DAG.",
            },
            {
                "Representation": "deduplicated_monolith",
                "Label": config["representations"]["deduplicated_monolith"]["label"],
                "CandidateVariableCount": deduplicated_variables,
                "VariableIdentity": "question_id",
                "EvidenceClass": "derived",
                "Interpretation": (
                    "Technical QuestionID deduplication only; no clinical semantic "
                    "merge."
                ),
            },
            {
                "Representation": "provisional_federated",
                "Label": config["representations"]["provisional_federated"]["label"],
                "CandidateVariableCount": federated_variable_copies,
                "VariableIdentity": "question_id_per_candidate_family",
                "EvidenceClass": "candidate",
                "Interpretation": (
                    "Sum of distinct QuestionIDs per provisional family; shared questions are "
                    "counted once in every family that uses them."
                ),
            },
        ]
    )
    representation_summary["ComparedWithDeduplicatedMonolith"] = (
        representation_summary["CandidateVariableCount"] - deduplicated_variables
    )

    # Keep a detailed, gitignored variable/cardinality table for Phase 3B. It contains
    # identifiers but no clinical free text. This is the reproducible bridge from the
    # measured Pathways structure to CPT-growth sensitivity.
    literal_variable_cardinality = occurrences[
        ["pathway_key", "order_number", "question_key", "state_cardinality"]
    ].copy()
    literal_variable_cardinality["Representation"] = "literal_monolith"
    literal_variable_cardinality["FamilyId"] = ""
    literal_variable_cardinality["VariableKey"] = (
        literal_variable_cardinality["pathway_key"].astype(str)
        + "#"
        + literal_variable_cardinality["order_number"].astype(str)
    )

    deduplicated_variable_cardinality = questions[
        ["question_key", "state_cardinality"]
    ].drop_duplicates("question_key").copy()
    deduplicated_variable_cardinality["Representation"] = "deduplicated_monolith"
    deduplicated_variable_cardinality["FamilyId"] = ""
    deduplicated_variable_cardinality["VariableKey"] = (
        deduplicated_variable_cardinality["question_key"].astype(str)
    )
    deduplicated_variable_cardinality["pathway_key"] = ""
    deduplicated_variable_cardinality["order_number"] = pd.NA

    federated_variable_cardinality = (
        family_occurrences[
            ["FamilyId", "question_key", "state_cardinality"]
        ]
        .drop_duplicates(["FamilyId", "question_key"])
        .copy()
    )
    federated_variable_cardinality["Representation"] = "provisional_federated"
    federated_variable_cardinality["VariableKey"] = (
        federated_variable_cardinality["FamilyId"].astype(str)
        + "::"
        + federated_variable_cardinality["question_key"].astype(str)
    )
    federated_variable_cardinality["pathway_key"] = ""
    federated_variable_cardinality["order_number"] = pd.NA

    variable_cardinality = pd.concat(
        [
            literal_variable_cardinality,
            deduplicated_variable_cardinality,
            federated_variable_cardinality,
        ],
        ignore_index=True,
        sort=False,
    )[
        [
            "Representation",
            "FamilyId",
            "VariableKey",
            "question_key",
            "pathway_key",
            "order_number",
            "state_cardinality",
        ]
    ]

    cardinality_rows = []
    for label, series in (
        ("literal_occurrences", occurrences["state_cardinality"]),
        ("deduplicated_questions", questions["state_cardinality"]),
    ):
        stats = _state_summary(series)
        cardinality_rows.append({"Scope": label, **stats})
    state_cardinality = pd.DataFrame(cardinality_rows)

    median_states = max(int(round(state_cardinality.loc[
        state_cardinality["Scope"] == "deduplicated_questions", "median"
    ].iloc[0])), 1)
    p90_states = max(int(round(state_cardinality.loc[
        state_cardinality["Scope"] == "deduplicated_questions", "p90"
    ].iloc[0])), 1)

    sensitivity_rows = []
    parent_counts = config["cpt_sizing"]["parent_count_scenarios"]
    for parent_count in parent_counts:
        for state_case, states in (("median_state_cardinality", median_states),
                                   ("p90_state_cardinality", p90_states)):
            sensitivity_rows.append(
                {
                    "ParentCount": int(parent_count),
                    "StateCase": state_case,
                    "AssumedChildStates": states,
                    "AssumedParentStatesEach": states,
                    "CptEntriesPerVariable": int(states * (states ** int(parent_count))),
                    "EvidenceClass": "assumption",
                }
            )
    cpt_parent_sensitivity = pd.DataFrame(sensitivity_rows)

    assumptions = pd.DataFrame(
        [
            {
                "Item": "Candidate family boundaries",
                "Class": "assumption",
                "Value": "Current Phase 2 analytical candidate set",
                "Limitation": "Pending clinician-led refinement.",
            },
            {
                "Item": "Literal variable identity",
                "Class": "assumption",
                "Value": "Pathway/order Tx occurrence",
                "Limitation": "Upper-bound representation, not a clinical BN design.",
            },
            {
                "Item": "Deduplicated variable identity",
                "Class": "assumption",
                "Value": "Distinct QuestionID",
                "Limitation": "Does not merge clinically equivalent different QuestionIDs.",
            },
            {
                "Item": "Variable state cardinality",
                "Class": "measured",
                "Value": "Catalogue answer count",
                "Limitation": "A future clinical BN may encode states differently.",
            },
            {
                "Item": "Bayesian parent count",
                "Class": "assumption",
                "Value": str(parent_counts),
                "Limitation": "Sensitivity only until a BN DAG transformation is agreed.",
            },
            {
                "Item": "Federated shared-variable overhead",
                "Class": "derived",
                "Value": str(shared_copy_overhead),
                "Limitation": (
                    "Counts variable copies, not memory or runtime coordination cost."
                ),
            },
        ]
    )

    outputs = {
        "representation_summary.csv": representation_summary,
        "state_cardinality_summary.csv": state_cardinality,
        "family_sizing_baseline.csv": family_table,
        "cpt_parent_sensitivity.csv": cpt_parent_sensitivity,
        "evidence_and_assumptions.csv": assumptions,
        "variable_cardinality_baseline.csv": variable_cardinality,
    }
    for name, frame in outputs.items():
        path = paths.phase3_tables / name
        frame.to_csv(path, index=False)
        LOGGER.info("Wrote %-42s %6d rows", path, len(frame))

    LOGGER.info(
        "Phase 3A baseline complete: literal=%d variables, deduplicated=%d variables, "
        "federated copies=%d across %d provisional families.",
        literal_variables,
        deduplicated_variables,
        federated_variable_copies,
        len(family_table),
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Phase 3A Bayesian representation sizing baseline."
    )
    parser.add_argument(
        "--check-connection",
        action="store_true",
        help="Validate database connectivity and exit.",
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
    load_dotenv_if_present(paths)

    try:
        settings = DatabaseSettings.from_env()
        database = PathwaysDatabase(settings, paths)
        info = database.validate_connectivity()
        if args.check_connection:
            LOGGER.info(
                "Connectivity OK: database=%s server_time=%s",
                info["database_name"],
                info["server_utc_time"],
            )
            return 0
        run_phase3a(database, paths)
        return 0
    except ConfigurationError as exc:
        LOGGER.error("Configuration error: %s", exc)
        return 2
    except DatabaseConnectionError as exc:
        LOGGER.error("Database failure: %s", exc)
        return 3
    finally:
        if "database" in locals():
            database.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
