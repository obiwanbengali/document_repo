"""Phase 3E infrastructure and cost scenarios.

Maps the Phase 3D runtime patterns to an illustrative ECS/Fargate capacity model.

The cost model is deliberately scenario-based. It does not claim to predict production
traffic and it does not silently use a non-London rate as a final NHS England cost.
The checked-in rate is the current AWS public Linux/x86 Fargate example for us-east-1,
used to exercise and compare the model until the agreed eu-west-2 Commercial/FinOps
rate card is supplied.
"""

from __future__ import annotations

import argparse
import logging
import math
from pathlib import Path
from typing import Any, Final

import pandas as pd
import yaml
from pandas.errors import EmptyDataError

from .config import ConfigurationError, Paths
from .profiling import configure_logging

LOGGER: Final = logging.getLogger("pathways_analysis.phase3_cost")


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ConfigurationError(f"Configuration not found: {path}")
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def _read(path: Path, *, required: bool = True) -> pd.DataFrame:
    if not path.is_file():
        if required:
            raise ConfigurationError(
                f"Required evidence not found: {path}. Run the preceding phase first."
            )
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except EmptyDataError as exc:
        if required:
            raise ConfigurationError(
                f"Required evidence file is empty: {path}"
            ) from exc
        return pd.DataFrame()


def _primary_routing_row(paths: Paths) -> pd.Series | None:
    routing = _read(
        paths.phase2_tables / "pathway_family_routing_summary.csv",
        required=False,
    )
    if routing.empty:
        return None

    primary = "hybrid_a"
    config_path = paths.config_dir / "family_discovery.yaml"
    if config_path.is_file():
        cfg = _load_yaml(config_path)
        primary = cfg.get("presentation", {}).get("primary_candidate_strategy", primary)

    subset = routing.loc[routing["strategy"].astype(str) == str(primary)]
    return subset.iloc[0] if not subset.empty else routing.iloc[0]


def structural_minimum_fanout(paths: Paths) -> float:
    """Return a lower-bound family fan-out from Phase 2 routing evidence.

    One plausible family counts as 1, two as 2, and three-or-more as 3. This is
    intentionally a lower bound because the third bucket may contain more than three.
    It is structural evidence, not a production case-frequency prediction.
    """
    row = _primary_routing_row(paths)
    if row is None:
        return 1.0

    one = float(row.get("PercentageOnePlausibleFamily", 0.0)) / 100.0
    two = float(row.get("PercentageTwoPlausibleFamilies", 0.0)) / 100.0
    three = float(row.get("PercentageThreeOrMorePlausibleFamilies", 0.0)) / 100.0
    covered = one + two + three
    if covered <= 0:
        return 1.0

    weighted = one + 2.0 * two + 3.0 * three
    # Any structurally scored pathways outside the plausible-family buckets contribute
    # one inference as a conservative floor rather than disappearing from capacity.
    return max(weighted + max(0.0, 1.0 - covered), 1.0)


def _pattern_multipliers(paths: Paths) -> pd.DataFrame:
    """Derive explicit workload multipliers for the four Phase 3D patterns."""
    fanout = structural_minimum_fanout(paths)
    return pd.DataFrame(
        [
            {
                "PatternId": "monolith_always_resident",
                "InferenceOperationsPerAssessment": 1.0,
                "CoordinationCpuMultiplier": 1.0,
                "Basis": "single whole-model inference",
                "EvidenceClass": "architectural_interpretation",
            },
            {
                "PatternId": "federated_all_resident",
                "InferenceOperationsPerAssessment": fanout,
                "CoordinationCpuMultiplier": 1.0,
                "Basis": "Phase 2 structural minimum plausible-family fan-out",
                "EvidenceClass": "derived+architectural_interpretation",
            },
            {
                "PatternId": "federated_lazy_loaded",
                "InferenceOperationsPerAssessment": fanout,
                "CoordinationCpuMultiplier": 1.10,
                "Basis": (
                    "same structural fan-out plus 10% explicit cache/load coordination "
                    "sensitivity assumption"
                ),
                "EvidenceClass": "derived+assumption",
            },
            {
                "PatternId": "hierarchical_shared_core",
                "InferenceOperationsPerAssessment": fanout + 1.0,
                "CoordinationCpuMultiplier": 1.0,
                "Basis": (
                    "one shared/core inference plus Phase 2 structural minimum family fan-out"
                ),
                "EvidenceClass": "derived+architectural_interpretation",
            },
        ]
    )


def build_cost_scenarios(
    paths: Paths, config: dict[str, Any]
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Build capacity and monthly cost scenarios for every runtime pattern."""
    runtime = _read(paths.phase3_tables / "runtime_patterns.csv")
    infra = config["infrastructure_cost"]
    rate = infra["fargate_linux_x86"]

    hours = float(infra["hours_per_month"])
    min_tasks = int(infra["high_availability_min_tasks"])
    task_vcpu = float(infra["task_cpu_vcpu"])
    task_memory = float(infra["task_memory_gb"])
    utilisation = float(infra["target_utilisation"])
    inference_seconds = float(infra["average_inference_seconds_assumption"])
    peak_multiplier = float(infra["peak_multiplier"])

    vcpu_price = float(rate["vcpu_per_hour_usd"])
    memory_price = float(rate["memory_gb_per_hour_usd"])
    fixed_monthly = (
        float(infra["load_balancer_monthly_allowance_usd"])
        + float(infra["observability_monthly_allowance_usd"])
        + float(infra["artefact_storage_monthly_allowance_usd"])
    )

    multipliers = _pattern_multipliers(paths)
    patterns = runtime[["PatternId", "LogicalModel", "ModelResidency", "ScalingUnit"]].merge(
        multipliers, on="PatternId", how="left"
    )

    capacity_rows: list[dict[str, Any]] = []
    cost_rows: list[dict[str, Any]] = []

    for monthly_assessments in infra["assessments_per_month_scenarios"]:
        monthly_assessments = int(monthly_assessments)
        avg_rps = monthly_assessments / (hours * 3600.0)
        peak_rps = avg_rps * peak_multiplier

        for row in patterns.itertuples():
            operations = float(row.InferenceOperationsPerAssessment)
            coordination = float(row.CoordinationCpuMultiplier)
            effective_seconds = inference_seconds * operations * coordination

            # Approximation: one vCPU-second of requested capacity supplies one
            # CPU-second of inference work. This is a capacity assumption, not a
            # benchmark-derived throughput claim.
            task_capacity_rps = (
                task_vcpu * utilisation / max(effective_seconds, 1e-9)
            )
            load_tasks = int(math.ceil(peak_rps / max(task_capacity_rps, 1e-9)))
            required_tasks = max(min_tasks, load_tasks)

            compute_monthly = required_tasks * hours * (
                task_vcpu * vcpu_price + task_memory * memory_price
            )
            total_monthly = compute_monthly + fixed_monthly
            cost_per_1000 = (
                total_monthly / monthly_assessments * 1000.0
                if monthly_assessments > 0
                else float("nan")
            )

            capacity_rows.append(
                {
                    "PatternId": row.PatternId,
                    "AssessmentsPerMonth": monthly_assessments,
                    "AverageRequestsPerSecond": round(avg_rps, 6),
                    "PeakRequestsPerSecondAssumption": round(peak_rps, 6),
                    "InferenceOperationsPerAssessment": round(operations, 4),
                    "EffectiveCpuSecondsPerAssessment": round(effective_seconds, 6),
                    "TaskVcpu": task_vcpu,
                    "TaskMemoryGb": task_memory,
                    "TargetUtilisation": utilisation,
                    "EstimatedTaskCapacityRps": round(task_capacity_rps, 4),
                    "LoadDrivenTasks": load_tasks,
                    "HighAvailabilityMinimumTasks": min_tasks,
                    "RequiredTasks": required_tasks,
                    "EvidenceClass": "assumption+derived",
                }
            )

            cost_rows.append(
                {
                    "PatternId": row.PatternId,
                    "AssessmentsPerMonth": monthly_assessments,
                    "RequiredTasks": required_tasks,
                    "FargateComputeMonthlyUsd": round(compute_monthly, 2),
                    "FixedPlatformAllowancesMonthlyUsd": round(fixed_monthly, 2),
                    "TotalIllustrativeMonthlyUsd": round(total_monthly, 2),
                    "IllustrativeCostPer1000AssessmentsUsd": round(cost_per_1000, 4),
                    "PricingTargetRegion": infra["target_region"],
                    "PricingBasisRegion": infra["pricing_basis_region"],
                    "PricingStatus": infra["pricing_status"],
                    "EvidenceClass": "assumption+derived",
                }
            )

    return pd.DataFrame(capacity_rows), pd.DataFrame(cost_rows)


def run_phase3e(paths: Paths) -> None:
    """Generate Phase 3E infrastructure and cost evidence."""
    paths.ensure_phase3_directories()
    config = _load_yaml(paths.config_dir / "phase3.yaml")

    capacity, costs = build_cost_scenarios(paths, config)
    multipliers = _pattern_multipliers(paths)

    notes = pd.DataFrame(
        [
            {
                "Item": "Production traffic",
                "EvidenceClass": "assumption",
                "Statement": (
                    "Monthly assessment volumes and peak multiplier are scenarios, not "
                    "measured 111/999 production traffic."
                ),
            },
            {
                "Item": "Inference duration",
                "EvidenceClass": "assumption",
                "Statement": (
                    "average_inference_seconds_assumption is used for capacity until the "
                    "repaired Phase 3C benchmark can provide an observed throughput basis."
                ),
            },
            {
                "Item": "Federated fan-out",
                "EvidenceClass": "derived",
                "Statement": (
                    "Family fan-out is a lower bound derived from Phase 2 plausible-family "
                    "percentages. It is structural evidence, not case-frequency evidence."
                ),
            },
            {
                "Item": "AWS rate",
                "EvidenceClass": "external+assumption",
                "Statement": (
                    "The checked-in Fargate rate is the AWS public Linux/x86 us-east-1 "
                    "example rate. Absolute costs remain illustrative until the agreed "
                    "eu-west-2 rate card is refreshed."
                ),
            },
            {
                "Item": "Excluded services",
                "EvidenceClass": "assumption",
                "Statement": (
                    "ALB, observability and artefact storage use explicit monthly allowances. "
                    "NAT/data transfer, WAF, KMS, ECR, backup and organisational "
                    "shared-service "
                    "charges are not yet itemised."
                ),
            },
        ]
    )

    for name, frame in {
        "infrastructure_capacity_scenarios.csv": capacity,
        "infrastructure_cost_scenarios.csv": costs,
        "runtime_workload_multipliers.csv": multipliers,
        "phase3e_method_notes.csv": notes,
    }.items():
        path = paths.phase3_tables / name
        frame.to_csv(path, index=False)
        LOGGER.info("Wrote %-48s %6d rows", path, len(frame))

    report = [
        "# Phase 3E — Infrastructure and Cost",
        "",
        "## Status",
        "",
        (
            "Infrastructure sizing is scenario-based. Absolute AWS costs are illustrative "
            "because the checked-in public Fargate rate is an AWS us-east-1 example while "
            "the target deployment region is eu-west-2. Refresh the rate card before the "
            "ADR is finalised."
        ),
        "",
        "## Runtime patterns",
        "",
    ]
    for pattern_id in multipliers["PatternId"]:
        row = multipliers.loc[multipliers["PatternId"] == pattern_id].iloc[0]
        report.append(
            f"- **{pattern_id}** — {row['InferenceOperationsPerAssessment']:.2f} "
            f"inference operations/assessment; basis: {row['Basis']}."
        )
    report.extend(
        [
            "",
            "## Cost scenarios",
            "",
            (
                "The generated CSV contains monthly and per-1,000-assessment values for "
                "100k, 1m and 5m assessments/month. These figures should be used for "
                "relative sensitivity only until production traffic and eu-west-2 pricing "
                "are supplied."
            ),
            "",
            "## Phase 3E conclusion",
            "",
            (
                "The cost model is now explicit and reproducible. The largest uncertainties "
                "are production traffic, observed inference duration, family fan-out under "
                "real cases, and the final eu-west-2 commercial rate card. Those uncertainties "
                "are carried into Phase 3F rather than hidden."
            ),
            "",
        ]
    )
    report_path = paths.phase3_reports / "phase3e_infrastructure_cost.md"
    report_path.write_text("\n".join(report), encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Phase 3E infrastructure and cost scenario model."
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
        run_phase3e(paths)
        return 0
    except ConfigurationError as exc:
        LOGGER.error("Configuration error: %s", exc)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
