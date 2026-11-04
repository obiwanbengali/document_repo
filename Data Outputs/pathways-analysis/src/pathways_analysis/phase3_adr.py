"""Phase 3F ADR evidence synthesis.

Combines Phase 3A-E into a draft Architecture Decision Record evidence pack.

The generator does not manufacture a winner. If benchmark evidence, clinical family
review, or target-region pricing is incomplete, the ADR remains explicitly draft and
records the blocking decision gates. That keeps the final decision human and evidence-led.
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path
from typing import Any, Final

import pandas as pd
import yaml
from pandas.errors import EmptyDataError

from .config import ConfigurationError, Paths
from .profiling import configure_logging

LOGGER: Final = logging.getLogger("pathways_analysis.phase3_adr")


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ConfigurationError(f"Configuration not found: {path}")
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def _read(path: Path) -> pd.DataFrame:
    if not path.is_file():
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except EmptyDataError:
        return pd.DataFrame()


def _gate(name: str, present: bool, detail: str) -> dict[str, Any]:
    return {
        "Gate": name,
        "Passed": bool(present),
        "Detail": detail,
    }


def decision_gates(paths: Paths, config: dict[str, Any]) -> pd.DataFrame:
    """Return the evidence/commercial/clinical gates for final ADR approval."""
    phase3a = not _read(paths.phase3_tables / "representation_summary.csv").empty
    phase3b = not _read(paths.phase3_tables / "cpt_sizing_by_representation.csv").empty
    phase3c = not _read(paths.phase3_tables / "benchmark_results.csv").empty
    phase3d = not _read(paths.phase3_tables / "runtime_patterns.csv").empty
    phase3e = not _read(paths.phase3_tables / "infrastructure_cost_scenarios.csv").empty

    infra = config["infrastructure_cost"]
    pricing_final = (
        str(infra.get("target_region")) == str(infra.get("pricing_basis_region"))
        and "illustrative" not in str(infra.get("pricing_status", "")).lower()
        and "pending" not in str(infra.get("pricing_status", "")).lower()
    )
    clinical_final = not bool(
        config.get("adr", {}).get("clinical_family_review_required_before_final", True)
    )

    return pd.DataFrame(
        [
            _gate("Phase 3A representation evidence", phase3a, "representation summary exists"),
            _gate("Phase 3B CPT sizing evidence", phase3b, "CPT sizing output exists"),
            _gate(
                "Phase 3C benchmark evidence",
                phase3c,
                "benchmark results exist and are non-empty",
            ),
            _gate("Phase 3D runtime evidence", phase3d, "runtime pattern output exists"),
            _gate("Phase 3E cost evidence", phase3e, "cost scenario output exists"),
            _gate(
                "Target-region pricing refreshed",
                pricing_final,
                (
                    f"target={infra.get('target_region')}, "
                    f"basis={infra.get('pricing_basis_region')}, "
                    f"status={infra.get('pricing_status')}"
                ),
            ),
            _gate(
                "Clinician-led family review complete",
                clinical_final,
                (
                    "Phase 2 family refinement is still required before the federated "
                    "family boundaries can be treated as clinically agreed."
                ),
            ),
        ]
    )


def evidence_matrix(paths: Paths) -> pd.DataFrame:
    """Create the side-by-side logical architecture evidence matrix."""
    reps = _read(paths.phase3_tables / "representation_summary.csv")
    cpt = _read(paths.phase3_tables / "cpt_sizing_by_representation.csv")
    bench = _read(paths.phase3_tables / "benchmark_results.csv")
    costs = _read(paths.phase3_tables / "infrastructure_cost_scenarios.csv")

    options = [
        ("literal_monolith", "Literal monolith"),
        ("deduplicated_monolith", "Question-ID deduplicated monolith"),
        ("provisional_federated", "Provisional federated / hierarchical"),
    ]
    rows: list[dict[str, Any]] = []

    for representation, label in options:
        row: dict[str, Any] = {
            "Representation": representation,
            "Label": label,
            "CandidateVariableCount": pd.NA,
            "ReferenceCptEntries": pd.NA,
            "ReferenceCptCase": "3 parents, median parent-state cardinality",
            "BenchmarkCoverage": "pending",
            "BenchmarkP95MsRange": "pending",
            "IllustrativeMonthlyCost1mUsd": "pending",
            "CostBasis": "Phase 3E scenario model",
            "EvidenceStatus": "partial",
        }

        rep = reps.loc[reps["Representation"].astype(str) == representation]
        if not rep.empty:
            row["CandidateVariableCount"] = int(rep.iloc[0]["CandidateVariableCount"])

        if not cpt.empty:
            subset = cpt.loc[
                (cpt["Representation"].astype(str) == representation)
                & (cpt["ParentCount"].astype(int) == 3)
                & (cpt["ParentStateCase"].astype(str) == "median_parent_states")
            ]
            if not subset.empty:
                row["ReferenceCptEntries"] = int(subset.iloc[0]["TotalCptEntries"])

        if not bench.empty:
            b = bench.loc[bench["Representation"].astype(str) == representation]
            if not b.empty:
                row["BenchmarkCoverage"] = (
                    f"{float(b['FractionOfActualModel'].max()):.1%} max model coverage"
                )
                row["BenchmarkP95MsRange"] = (
                    f"{float(b['QueryP95Ms'].min()):.3f}-"
                    f"{float(b['QueryP95Ms'].max()):.3f} ms"
                )

        if not costs.empty:
            scenario = costs.loc[costs["AssessmentsPerMonth"].astype(int) == 1000000]
            if representation in {"literal_monolith", "deduplicated_monolith"}:
                c = scenario.loc[
                    scenario["PatternId"].astype(str) == "monolith_always_resident"
                ]
                if not c.empty:
                    row["IllustrativeMonthlyCost1mUsd"] = float(
                        c.iloc[0]["TotalIllustrativeMonthlyUsd"]
                    )
            else:
                c = scenario.loc[
                    scenario["PatternId"].astype(str).isin(
                        [
                            "federated_all_resident",
                            "federated_lazy_loaded",
                            "hierarchical_shared_core",
                        ]
                    )
                ]
                if not c.empty:
                    row["IllustrativeMonthlyCost1mUsd"] = (
                        f"{float(c['TotalIllustrativeMonthlyUsd'].min()):.2f}-"
                        f"{float(c['TotalIllustrativeMonthlyUsd'].max()):.2f}"
                    )

        evidence_items = [
            row["CandidateVariableCount"],
            row["ReferenceCptEntries"],
            row["BenchmarkCoverage"],
            row["IllustrativeMonthlyCost1mUsd"],
        ]
        pending = sum(
            value is pd.NA or str(value).lower() == "pending"
            for value in evidence_items
        )
        row["EvidenceStatus"] = "complete_for_draft" if pending == 0 else "partial"
        rows.append(row)

    return pd.DataFrame(rows)


def runtime_tradeoffs() -> pd.DataFrame:
    """Return qualitative trade-offs without scoring or selecting a winner."""
    return pd.DataFrame(
        [
            {
                "Representation": "literal_monolith",
                "Strength": "single model boundary and simple runtime routing",
                "Tradeoff": (
                    "largest structural representation; whole-model release and regression "
                    "blast radius"
                ),
            },
            {
                "Representation": "deduplicated_monolith",
                "Strength": (
                    "retains one runtime model while removing repeated QuestionID occurrences"
                ),
                "Tradeoff": (
                    "still one global dependency structure and whole-model release boundary; "
                    "QuestionID identity is not clinical semantic normalisation"
                ),
            },
            {
                "Representation": "provisional_federated",
                "Strength": (
                    "smaller family inference units and potentially more localised "
                    "model changes"
                ),
                "Tradeoff": (
                    "cross-family routing, shared evidence, compatibility/version management "
                    "and family-boundary clinical governance"
                ),
            },
            {
                "Representation": "hierarchical_shared_core",
                "Strength": (
                    "makes broadly shared evidence explicit rather than duplicating it silently"
                ),
                "Tradeoff": (
                    "shared-core changes regain a broad blast radius and require explicit "
                    "compatibility contracts with family models"
                ),
            },
        ]
    ).assign(EvidenceClass="architectural_interpretation")


def run_phase3f(paths: Paths) -> None:
    """Generate the Phase 3F draft ADR evidence pack."""
    paths.ensure_phase3_directories()
    config = _load_yaml(paths.config_dir / "phase3.yaml")

    gates = decision_gates(paths, config)
    matrix = evidence_matrix(paths)
    tradeoffs = runtime_tradeoffs()
    final_ready = bool(gates["Passed"].all())

    gates.to_csv(paths.phase3_tables / "adr_decision_gates.csv", index=False)
    matrix.to_csv(paths.phase3_tables / "adr_evidence_matrix.csv", index=False)
    tradeoffs.to_csv(paths.phase3_tables / "adr_runtime_tradeoffs.csv", index=False)

    status = "READY FOR FINAL DECISION" if final_ready else "DRAFT — DECISION GATES OPEN"

    lines = [
        "# ADR-AI — Bayesian Network Topology for Probabilistic Triage",
        "",
        f"**Status:** {status}",
        "",
        "## Context",
        "",
        (
            "Probabilistic Triage needs a Bayesian model topology that can represent the "
            "NHS Pathways-derived clinical estate while remaining operable, testable and "
            "governable. The service deployment boundary is already treated as a central "
            "inference capability; this ADR compares the logical Bayesian model topology "
            "inside that boundary."
        ),
        "",
        "## Options under comparison",
        "",
        "1. Literal monolithic Bayesian representation.",
        "2. Question-ID deduplicated monolithic representation.",
        "3. Federated / hierarchical representation using provisional Phase 2 families.",
        "",
        "## Evidence summary",
        "",
    ]

    for row in matrix.itertuples():
        lines.extend(
            [
                f"### {row.Label}",
                "",
                f"- Candidate variables: {row.CandidateVariableCount}",
                f"- Reference CPT case: {row.ReferenceCptEntries} entries "
                f"({row.ReferenceCptCase})",
                f"- Benchmark coverage: {row.BenchmarkCoverage}",
                f"- Observed benchmark p95 range: {row.BenchmarkP95MsRange}",
                "- Illustrative 1m-assessment monthly cost: "
                f"{row.IllustrativeMonthlyCost1mUsd}",
                "",
            ]
        )

    lines.extend(
        [
            "## Decision gates",
            "",
        ]
    )
    for row in gates.itertuples():
        marker = "PASS" if row.Passed else "OPEN"
        lines.append(f"- **{marker} — {row.Gate}:** {row.Detail}")

    lines.extend(
        [
            "",
            "## Decision",
            "",
        ]
    )
    if final_ready:
        lines.append(
            (
                "All configured evidence gates are closed. The architecture review can now "
                "make the final topology decision using the evidence matrix and recorded "
                "trade-offs. This generator deliberately does not select the architecture "
                "algorithmically."
            )
        )
    else:
        lines.append(
            (
                "No final topology decision is recorded yet. The remaining open gates are "
                "visible above. In particular, the federated family set remains provisional "
                "until clinician-led refinement, and absolute AWS cost remains illustrative "
                "until the eu-west-2 rate card is refreshed. If Phase 3C is still open, "
                "runtime performance evidence is also incomplete."
            )
        )

    lines.extend(
        [
            "",
            "## Existing architectural constraint",
            "",
            (
                "Whichever logical topology is selected, it is evaluated inside the same "
                "centralised inference-service boundary. Federation does not imply a "
                "microservice per family."
            ),
            "",
            "## Next actions before finalising",
            "",
            "1. Close any remaining Phase 3C benchmark issues and regenerate the evidence.",
            "2. Refresh eu-west-2 pricing with the agreed Commercial / FinOps rate card.",
            "3. Revisit Phase 2 with clinician-led family definition.",
            "4. Re-run affected Phase 3 sizing, benchmark and cost calculations.",
            "5. Record the human architecture decision and consequences in this ADR.",
            "",
        ]
    )

    report_path = paths.phase3_reports / "phase3f_draft_adr.md"
    report_path.write_text("\n".join(lines), encoding="utf-8")
    LOGGER.info("Wrote %s", report_path)
    LOGGER.info("Phase 3F status: %s", status)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Phase 3F draft ADR evidence synthesis.")
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
        run_phase3f(paths)
        return 0
    except ConfigurationError as exc:
        LOGGER.error("Configuration error: %s", exc)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
