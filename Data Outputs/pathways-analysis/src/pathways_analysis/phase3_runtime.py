"""Phase 3D runtime architecture assessment.

Translates Phase 2 family evidence and Phase 3 sizing/benchmark evidence into runtime
deployment patterns. This module does not select a winner. It makes the operational
consequences of each logical model shape explicit.

A key rule is enforced throughout: logical BN architecture and service deployment
architecture are separate decisions. Federated networks do not imply one service per
family, and a monolithic network may still be horizontally replicated.
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

LOGGER: Final = logging.getLogger("pathways_analysis.phase3_runtime")


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
                f"Required evidence file is empty: {path}. Re-run the preceding phase."
            ) from exc
        LOGGER.warning(
            "Optional evidence file is empty and will be treated as pending: %s", path
        )
        return pd.DataFrame()


def _primary_routing_row(paths: Paths) -> pd.Series | None:
    routing = _read(
        paths.phase2_tables / "pathway_family_routing_summary.csv",
        required=False,
    )
    if routing.empty:
        return None

    config_path = paths.config_dir / "family_discovery.yaml"
    primary = "hybrid_a"
    if config_path.is_file():
        with config_path.open("r", encoding="utf-8") as handle:
            config = yaml.safe_load(handle) or {}
        primary = (
            config.get("presentation", {})
            .get("primary_candidate_strategy", primary)
        )

    subset = routing.loc[routing["strategy"].astype(str) == str(primary)]
    if subset.empty:
        return routing.iloc[0]
    return subset.iloc[0]


def runtime_patterns() -> pd.DataFrame:
    """Return the deployment patterns carried into Phase 3E costing."""
    rows = [
        {
            "PatternId": "monolith_always_resident",
            "LogicalModel": "monolithic",
            "DeploymentShape": "one central inference service; model replicated per worker",
            "ModelResidency": "whole model loaded on every active worker",
            "Routing": "no family routing after request enters inference service",
            "CrossModelCoordination": "none",
            "ScalingUnit": "whole-model worker",
            "FailureScope": (
                "worker failure; model-level issue affects all triage handled by that "
                "version"
            ),
            "Versioning": "single model artefact/version plus service version",
            "OperationalImplication": (
                "Simple routing and version coordination, but every worker carries the "
                "full model and every model release has estate-wide blast radius."
            ),
            "EvidenceClass": "architectural_interpretation",
        },
        {
            "PatternId": "federated_all_resident",
            "LogicalModel": "federated",
            "DeploymentShape": (
                "one central inference service; all family models resident in each worker"
            ),
            "ModelResidency": "all family models loaded on every worker",
            "Routing": "select one or more candidate families inside inference service",
            "CrossModelCoordination": (
                "required when evidence or pathway membership spans family boundaries"
            ),
            "ScalingUnit": "worker containing complete family set",
            "FailureScope": (
                "worker failure; individual family artefact defect can be isolated logically"
            ),
            "Versioning": "family-set manifest plus per-family versions",
            "OperationalImplication": (
                "Keeps deployment simple while preserving smaller inference units, but "
                "memory may approach the aggregate size of all family models and duplicate "
                "shared features."
            ),
            "EvidenceClass": "architectural_interpretation",
        },
        {
            "PatternId": "federated_lazy_loaded",
            "LogicalModel": "federated",
            "DeploymentShape": (
                "one central inference service with model cache; families loaded on demand"
            ),
            "ModelResidency": "hot families cached; cold families loaded from artefact store",
            "Routing": "family routing occurs before model acquisition",
            "CrossModelCoordination": (
                "fan-out may load or query several family models for ambiguous cases"
            ),
            "ScalingUnit": "inference worker plus family-model cache capacity",
            "FailureScope": (
                "cache/load failure may affect a family or request; service can "
                "remain available"
            ),
            "Versioning": "immutable family artefacts referenced by manifest",
            "OperationalImplication": (
                "Can reduce resident memory, but introduces cold-load latency, cache policy, "
                "artefact availability and more observable runtime states."
            ),
            "EvidenceClass": "architectural_interpretation",
        },
        {
            "PatternId": "hierarchical_shared_core",
            "LogicalModel": "federated_hierarchical",
            "DeploymentShape": (
                "central inference service with shared/common model layer plus family models"
            ),
            "ModelResidency": (
                "shared layer resident; family models resident or cached according to policy"
            ),
            "Routing": (
                "shared evidence evaluated first or alongside family routing; one or more "
                "families then engaged"
            ),
            "CrossModelCoordination": (
                "explicit contract between shared layer and family models"
            ),
            "ScalingUnit": "shared-layer worker capacity plus family inference capacity",
            "FailureScope": (
                "shared-layer defect has broad blast radius; family defect can remain localised"
            ),
            "Versioning": (
                "shared-core version plus compatible family versions in a release manifest"
            ),
            "OperationalImplication": (
                "Reduces uncontrolled duplication of common evidence, but creates the most "
                "explicit compatibility and coordination requirements."
            ),
            "EvidenceClass": "architectural_interpretation",
        },
    ]
    return pd.DataFrame(rows)


def coordination_evidence(paths: Paths) -> pd.DataFrame:
    """Convert Phase 2 evidence into runtime coordination pressure, without inventing load."""
    rows: list[dict[str, Any]] = []
    routing = _primary_routing_row(paths)
    if routing is not None:
        for column, label in (
            ("PercentageOnePlausibleFamily", "one plausible family"),
            ("PercentageTwoPlausibleFamilies", "two plausible families"),
            (
                "PercentageThreeOrMorePlausibleFamilies",
                "three or more plausible families",
            ),
            ("PercentageHighAmbiguity", "high structural ambiguity"),
            (
                "PercentageStrongSingleFamilyAssociation",
                "strong single-family association",
            ),
        ):
            if column in routing.index:
                rows.append(
                    {
                        "Evidence": label,
                        "Value": float(routing[column]),
                        "Unit": "percent of structurally scored pathways",
                        "RuntimeMeaning": (
                            "Structural routing evidence only. It indicates where a runtime "
                            "router may need one versus several candidate families, but it is "
                            "not a production traffic distribution."
                        ),
                        "EvidenceClass": "candidate+derived",
                    }
                )

    shared = _read(
        paths.phase2_tables / "shared_feature_summary.csv",
        required=False,
    )
    if not shared.empty:
        for row in shared.itertuples():
            feature_type = getattr(row, "FeatureType", "")
            total = getattr(row, "FeaturesTotal", None)
            family_specific = getattr(row, "FamilySpecific", None)
            broadly_shared = getattr(row, "BroadlyShared", None)
            rows.append(
                {
                    "Evidence": f"shared features: {feature_type}",
                    "Value": (
                        int(broadly_shared)
                        if broadly_shared is not None and not pd.isna(broadly_shared)
                        else 0
                    ),
                    "Unit": "broadly shared features",
                    "RuntimeMeaning": (
                        f"Out of {int(total) if total is not None else 'unknown'} measured "
                        "features, "
                        f"{int(family_specific) if family_specific is not None else 'unknown'} "
                        "are family-specific. Broad sharing creates a design choice between "
                        "duplication, shared model structure or evidence propagation."
                    ),
                    "EvidenceClass": "candidate+derived",
                }
            )

    return pd.DataFrame(rows)


def benchmark_envelope(paths: Paths) -> pd.DataFrame:
    """Summarise observed Phase 3C benchmark ranges without collapsing topology context."""
    results = _read(
        paths.phase3_tables / "benchmark_results.csv",
        required=False,
    )
    if results.empty:
        return pd.DataFrame(
            [
                {
                    "Representation": "not yet available",
                    "ModelScope": "",
                    "MaxBenchmarkNodes": 0,
                    "MaxFractionOfActualModel": 0.0,
                    "ObservedQueryP95MinMs": pd.NA,
                    "ObservedQueryP95MaxMs": pd.NA,
                    "ObservedSerializedModelMaxMiB": pd.NA,
                    "ObservedPythonPeakMaxMiB": pd.NA,
                    "EvidenceClass": "benchmark_pending",
                    "Caveat": (
                        "Run python -m pathways_analysis.phase3_benchmark before using "
                        "benchmark evidence in runtime architecture decisions."
                    ),
                }
            ]
        )

    rows = []
    group_columns = ["Representation", "ModelScope"]
    for keys, group in results.groupby(group_columns, dropna=False):
        representation, model_scope = keys
        rows.append(
            {
                "Representation": representation,
                "ModelScope": model_scope,
                "MaxBenchmarkNodes": int(group["BenchmarkNodeCount"].max()),
                "MaxFractionOfActualModel": round(
                    float(group["FractionOfActualModel"].max()), 6
                ),
                "ObservedQueryP95MinMs": round(float(group["QueryP95Ms"].min()), 3),
                "ObservedQueryP95MaxMs": round(float(group["QueryP95Ms"].max()), 3),
                "ObservedSerializedModelMaxMiB": round(
                    float(group["SerializedModelMiB"].max()), 3
                ),
                "ObservedPythonPeakMaxMiB": round(
                    float(group["PythonPeakAllocatedMiB"].max()), 3
                ),
                "EvidenceClass": "benchmark",
                "Caveat": (
                    "Envelope spans different parent/state cases. It is not a single "
                    "latency estimate and must be read with benchmark_results.csv."
                ),
            }
        )
    return pd.DataFrame(rows)


def failure_modes() -> pd.DataFrame:
    """Document runtime failure behaviour for each pattern."""
    rows = [
        (
            "monolith_always_resident",
            "model artefact fails validation or load",
            "worker cannot serve that model version",
            "roll back whole model version; keep previous immutable artefact available",
        ),
        (
            "monolith_always_resident",
            "clinical/model defect in one area",
            "potential estate-wide release impact",
            "versioned rollback; regression suite must cover whole model",
        ),
        (
            "federated_all_resident",
            "one family artefact fails validation",
            "that family can be withheld while other validated family artefacts remain usable",
            "family-level rollback under a validated family-set manifest",
        ),
        (
            "federated_lazy_loaded",
            "family artefact store/cache miss or load failure",
            "request may be delayed or family unavailable",
            "bounded load timeout, previous-version cache, explicit fail-safe handling",
        ),
        (
            "hierarchical_shared_core",
            "shared-core failure or incompatible version",
            "multiple or all families may be affected",
            "atomic compatibility manifest and rollback of shared-core/family set",
        ),
        (
            "hierarchical_shared_core",
            "single family model failure",
            "local family capability affected",
            "family-level rollback if compatible with current shared core",
        ),
    ]
    return pd.DataFrame(
        rows,
        columns=[
            "PatternId",
            "FailureMode",
            "LikelyScope",
            "RequiredControl",
        ],
    ).assign(EvidenceClass="architectural_interpretation")


def change_blast_radius() -> pd.DataFrame:
    """Express the expected release/test blast radius qualitatively."""
    return pd.DataFrame(
        [
            {
                "PatternId": "monolith_always_resident",
                "LocalChangeUnit": "single monolithic artefact",
                "ModelReleaseBlastRadius": "whole model",
                "RegressionScope": "whole-model structural and clinical regression",
                "CompatibilityManagement": "low structural complexity; one model version",
            },
            {
                "PatternId": "federated_all_resident",
                "LocalChangeUnit": "family artefact",
                "ModelReleaseBlastRadius": "family plus boundary/shared evidence dependencies",
                "RegressionScope": "changed family, neighbouring families and shared contracts",
                "CompatibilityManagement": "family-set manifest",
            },
            {
                "PatternId": "federated_lazy_loaded",
                "LocalChangeUnit": "family artefact",
                "ModelReleaseBlastRadius": "family plus cache/version interactions",
                "RegressionScope": "same as federation plus load/cache behaviour",
                "CompatibilityManagement": "family-set manifest plus cache invalidation",
            },
            {
                "PatternId": "hierarchical_shared_core",
                "LocalChangeUnit": "family or shared-core artefact",
                "ModelReleaseBlastRadius": (
                    "family-local for isolated change; broad for shared-core change"
                ),
                "RegressionScope": (
                    "family-level for local changes; all dependent families for core changes"
                ),
                "CompatibilityManagement": (
                    "explicit shared-core/family compatibility matrix or manifest"
                ),
            },
        ]
    ).assign(EvidenceClass="architectural_interpretation")


def write_summary(
    paths: Paths,
    patterns: pd.DataFrame,
    coordination: pd.DataFrame,
    benchmarks: pd.DataFrame,
) -> None:
    """Write a concise Phase 3D evidence report."""
    lines = [
        "# Phase 3D — Runtime Architecture",
        "",
        "## Scope",
        "",
        (
            "This phase maps the logical model options to runtime deployment patterns. "
            "It does not choose a final architecture and it does not assume that a "
            "federated Bayesian design requires one microservice per family."
        ),
        "",
        "## Runtime patterns carried into costing",
        "",
    ]
    for row in patterns.itertuples():
        lines.extend(
            [
                f"### {row.PatternId}",
                "",
                f"- Logical model: {row.LogicalModel}",
                f"- Deployment: {row.DeploymentShape}",
                f"- Residency: {row.ModelResidency}",
                f"- Scaling unit: {row.ScalingUnit}",
                f"- Versioning: {row.Versioning}",
                f"- Implication: {row.OperationalImplication}",
                "",
            ]
        )

    lines.extend(
        [
            "## Cross-family coordination evidence",
            "",
            (
                "Phase 2 routing ambiguity and shared-feature evidence are used only as "
                "structural indicators. They do not describe production case volumes."
            ),
            "",
        ]
    )
    if coordination.empty:
        lines.append("_No coordination evidence available._")
    else:
        for row in coordination.itertuples():
            lines.append(f"- {row.Evidence}: {row.Value} {row.Unit}. {row.RuntimeMeaning}")

    lines.extend(
        [
            "",
            "## Benchmark coverage",
            "",
            (
                "Phase 3C benchmark evidence is summarised as an envelope rather than "
                "collapsed into one latency figure because parent count, state cardinality "
                "and topology materially affect exact inference."
            ),
            "",
        ]
    )
    for row in benchmarks.itertuples():
        lines.append(
            f"- {row.Representation}/{row.ModelScope}: max benchmark nodes "
            f"{row.MaxBenchmarkNodes}, coverage {row.MaxFractionOfActualModel:.1%}. "
            f"{row.Caveat}"
        )

    lines.extend(
        [
            "",
            "## Phase 3D conclusion",
            "",
            (
                "The runtime comparison should carry four deployment patterns into Phase "
                "3E rather than equating logical federation with microservices. The key "
                "operational differences are model residency, cross-family fan-out, version "
                "coordination, failure scope and release blast radius. Phase 3E can now map "
                "these patterns to concrete AWS infrastructure and cost scenarios."
            ),
            "",
        ]
    )

    path = paths.phase3_reports / "phase3d_runtime_architecture.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    LOGGER.info("Wrote %s", path)


def run_phase3d(paths: Paths) -> None:
    """Generate Phase 3D runtime architecture evidence."""
    paths.ensure_phase3_directories()
    _load_yaml(paths.config_dir / "phase3.yaml")

    patterns = runtime_patterns()
    coordination = coordination_evidence(paths)
    benchmarks = benchmark_envelope(paths)
    failures = failure_modes()
    blast = change_blast_radius()

    outputs = {
        "runtime_patterns.csv": patterns,
        "runtime_coordination_evidence.csv": coordination,
        "benchmark_runtime_envelope.csv": benchmarks,
        "runtime_failure_modes.csv": failures,
        "runtime_change_blast_radius.csv": blast,
    }
    for name, frame in outputs.items():
        path = paths.phase3_tables / name
        frame.to_csv(path, index=False)
        LOGGER.info("Wrote %-42s %6d rows", path, len(frame))

    write_summary(paths, patterns, coordination, benchmarks)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Phase 3D runtime architecture assessment."
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
        run_phase3d(paths)
        return 0
    except ConfigurationError as exc:
        LOGGER.error("Configuration error: %s", exc)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
