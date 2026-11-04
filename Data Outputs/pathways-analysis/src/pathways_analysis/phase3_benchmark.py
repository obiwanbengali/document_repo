"""Phase 3C controlled computational benchmark.

Builds valid synthetic Bayesian Networks whose sizes are derived from Phase 3A/3B,
but whose probabilities and dependency topology are deliberately synthetic.

Pathways does not contain a clinically approved Bayesian DAG or CPTs. Benchmarking a
controlled DAG lets us measure model construction, serialisation, Python allocation
and exact-inference latency without pretending synthetic posteriors are clinical
evidence.

Every result records node count, state cardinality, parent count and topology. Exact
inference performance is topology/treewidth-sensitive; a latency without that context
is not meaningful.
"""

from __future__ import annotations

import argparse
import gc
import logging
import pickle
import statistics
import time
import tracemalloc
from pathlib import Path
from typing import Any, Final

import pandas as pd
import yaml

from .config import ConfigurationError, Paths
from .profiling import configure_logging

LOGGER: Final = logging.getLogger("pathways_analysis.phase3_benchmark")


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ConfigurationError(f"Configuration not found: {path}")
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def _require_file(path: Path, description: str) -> pd.DataFrame:
    if not path.is_file():
        raise ConfigurationError(
            f"{description} not found: {path}. Run Phase 3A and Phase 3B first."
        )
    return pd.read_csv(path)


def rolling_window_edges(node_count: int, parent_count: int) -> list[tuple[str, str]]:
    """Return an acyclic rolling-window DAG with bounded in-degree."""
    if node_count < 1:
        raise ValueError("node_count must be >= 1")
    if parent_count < 0:
        raise ValueError("parent_count must be >= 0")

    nodes = [f"X{i:05d}" for i in range(node_count)]
    edges: list[tuple[str, str]] = []
    for index, child in enumerate(nodes):
        start = max(0, index - parent_count)
        for parent_index in range(start, index):
            edges.append((nodes[parent_index], child))
    return edges


def planned_model_sizes(actual: int, steps: list[int], cap: int) -> list[int]:
    """Return deterministic benchmark sizes up to the real/capped model size."""
    target = min(max(int(actual), 1), int(cap))
    return sorted({int(step) for step in steps if 0 < int(step) <= target} | {target})


def _state_values(state_summary: pd.DataFrame) -> dict[str, int]:
    row = state_summary.loc[state_summary["Scope"] == "deduplicated_questions"]
    if row.empty:
        raise ConfigurationError(
            "state_cardinality_summary.csv has no deduplicated_questions row."
        )
    source = row.iloc[0]
    return {
        "median": max(int(round(float(source["median"]))), 2),
        "p90": max(int(round(float(source["p90"]))), 2),
    }


def build_benchmark_plan(paths: Paths, config: dict[str, Any]) -> pd.DataFrame:
    """Build the benchmark matrix from measured representation and family sizes."""
    representation = _require_file(
        paths.phase3_tables / "representation_summary.csv",
        "Phase 3A representation summary",
    )
    families = _require_file(
        paths.phase3_tables / "family_sizing_baseline.csv",
        "Phase 3A family sizing baseline",
    )
    states = _require_file(
        paths.phase3_tables / "state_cardinality_summary.csv",
        "Phase 3A state-cardinality summary",
    )

    counts = dict(
        zip(
            representation["Representation"].astype(str),
            representation["CandidateVariableCount"].astype(int),
        )
    )
    if families.empty:
        raise ConfigurationError("family_sizing_baseline.csv is empty.")

    largest_family = int(families["VariableCount"].max())
    median_family = max(int(round(float(families["VariableCount"].median()))), 1)

    benchmark = config["benchmarking"]
    steps = [int(value) for value in benchmark["variable_count_steps"]]
    cap = int(benchmark["max_benchmark_variables"])
    parent_cases = [int(value) for value in benchmark["parent_count_cases"]]
    state_cases = _state_values(states)

    model_targets = [
        ("literal_monolith", "whole_model", int(counts["literal_monolith"])),
        ("deduplicated_monolith", "whole_model", int(counts["deduplicated_monolith"])),
        ("provisional_federated", "largest_family", largest_family),
        ("provisional_federated", "median_family", median_family),
    ]

    rows: list[dict[str, Any]] = []
    for representation_name, model_scope, actual_variables in model_targets:
        for node_count in planned_model_sizes(actual_variables, steps, cap):
            for state_case, state_cardinality in state_cases.items():
                for parent_count in parent_cases:
                    max_parents = min(parent_count, max(node_count - 1, 0))
                    largest_cpt_entries = int(
                        state_cardinality * (state_cardinality ** max_parents)
                    )
                    approx_total_cpt_entries = 0
                    for index in range(node_count):
                        parents = min(parent_count, index)
                        approx_total_cpt_entries += int(
                            state_cardinality * (state_cardinality ** parents)
                        )

                    runnable = (
                        largest_cpt_entries
                        <= int(benchmark["max_cpt_entries_per_variable"])
                        and approx_total_cpt_entries
                        <= int(benchmark["max_total_cpt_entries"])
                    )
                    reason = ""
                    if not runnable:
                        reason = (
                            "safety cap: synthetic CPT allocation would exceed configured "
                            "per-variable or total-cell limit"
                        )

                    rows.append(
                        {
                            "Representation": representation_name,
                            "ModelScope": model_scope,
                            "ActualCandidateVariables": actual_variables,
                            "BenchmarkNodeCount": node_count,
                            "FractionOfActualModel": round(
                                node_count / max(actual_variables, 1), 6
                            ),
                            "Topology": benchmark["topology"],
                            "ParentCount": parent_count,
                            "StateCase": state_case,
                            "StateCardinality": state_cardinality,
                            "ApproxTotalCptEntries": approx_total_cpt_entries,
                            "LargestCptEntries": largest_cpt_entries,
                            "Runnable": runnable,
                            "SkipReason": reason,
                            "EvidenceClass": "benchmark_configuration",
                        }
                    )
    return pd.DataFrame(rows)


def _pgmpy_types():
    """Import pgmpy lazily so ordinary Phase 1-3B installs stay lightweight."""
    try:
        import numpy as np
        from pgmpy.factors.discrete import TabularCPD
        from pgmpy.inference import VariableElimination
        try:
            from pgmpy.models import DiscreteBayesianNetwork as BayesianModel
        except ImportError:
            from pgmpy.models import BayesianNetwork as BayesianModel
    except (ImportError, TypeError) as exc:
        raise ConfigurationError(
            "Phase 3C could not import a Python-3.9-compatible pgmpy stack. "
            "This workbench supports Python 3.9, but pgmpy 1.x requires Python >=3.10 "
            "and older PyTorch wheels are incompatible with NumPy 2.x. "
            "Reinstall the pinned benchmark extra with: "
            "pip uninstall -y pgmpy numpy && pip install -e '.[benchmark]'"
        ) from exc
    return np, TabularCPD, VariableElimination, BayesianModel


def _make_model(node_count: int, parent_count: int, states: int):
    np, TabularCPD, _, BayesianModel = _pgmpy_types()
    nodes = [f"X{i:05d}" for i in range(node_count)]
    edges = rolling_window_edges(node_count, parent_count)
    model = BayesianModel(edges)
    model.add_nodes_from(nodes)

    for index, node in enumerate(nodes):
        parent_start = max(0, index - parent_count)
        parents = nodes[parent_start:index]
        parent_configs = states ** len(parents)
        values = np.full((states, parent_configs), 1.0 / states, dtype=float)
        if parents:
            cpd = TabularCPD(
                variable=node,
                variable_card=states,
                values=values,
                evidence=parents,
                evidence_card=[states] * len(parents),
            )
        else:
            cpd = TabularCPD(variable=node, variable_card=states, values=values)
        model.add_cpds(cpd)

    if not model.check_model():
        raise RuntimeError("Synthetic benchmark model failed pgmpy validation.")
    return model


def _query(engine: Any, target: str, evidence: dict[str, int]) -> None:
    try:
        engine.query([target], evidence=evidence, show_progress=False)
    except TypeError:
        engine.query([target], evidence=evidence)


def benchmark_case(
    *,
    node_count: int,
    parent_count: int,
    states: int,
    repetitions: int,
    warmups: int,
    evidence_count: int,
) -> dict[str, Any]:
    """Run one controlled benchmark case and return observed timings and memory."""
    _, _, VariableElimination, _ = _pgmpy_types()

    gc.collect()
    tracemalloc.start()
    build_started = time.perf_counter()
    model = _make_model(node_count, parent_count, states)
    engine = VariableElimination(model)
    build_ms = (time.perf_counter() - build_started) * 1000.0
    _, peak_bytes = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    serialise_started = time.perf_counter()
    payload = pickle.dumps(model, protocol=pickle.HIGHEST_PROTOCOL)
    serialise_ms = (time.perf_counter() - serialise_started) * 1000.0

    nodes = [f"X{i:05d}" for i in range(node_count)]
    target = nodes[-1]
    usable_evidence_nodes = nodes[: min(evidence_count, max(node_count - 1, 0))]
    evidence = {node: 0 for node in usable_evidence_nodes if node != target}

    for _ in range(warmups):
        _query(engine, target, evidence)

    timings: list[float] = []
    for _ in range(repetitions):
        started = time.perf_counter()
        _query(engine, target, evidence)
        timings.append((time.perf_counter() - started) * 1000.0)

    ordered = sorted(timings)
    p95_index = min(max(int(round(0.95 * (len(ordered) - 1))), 0), len(ordered) - 1)

    return {
        "BuildAndInferenceInitMs": round(build_ms, 3),
        "PythonPeakAllocatedMiB": round(peak_bytes / (1024 ** 2), 3),
        "SerializedModelMiB": round(len(payload) / (1024 ** 2), 3),
        "SerializeMs": round(serialise_ms, 3),
        "QueryMedianMs": round(statistics.median(timings), 3),
        "QueryMeanMs": round(statistics.mean(timings), 3),
        "QueryP95Ms": round(ordered[p95_index], 3),
        "QueryMaxMs": round(max(timings), 3),
        "EvidenceVariables": len(evidence),
    }


def run_phase3c(paths: Paths) -> None:
    """Generate the Phase 3C benchmark plan and execute runnable cases."""
    paths.ensure_phase3_directories()
    config = _load_yaml(paths.config_dir / "phase3.yaml")
    plan = build_benchmark_plan(paths, config)
    plan_path = paths.phase3_tables / "benchmark_plan.csv"
    plan.to_csv(plan_path, index=False)
    LOGGER.info("Wrote benchmark plan: %s (%d rows)", plan_path, len(plan))

    _pgmpy_types()

    benchmark = config["benchmarking"]
    results: list[dict[str, Any]] = []
    runnable = plan.loc[plan["Runnable"].astype(bool)].copy()

    for index, row in enumerate(runnable.itertuples(), start=1):
        LOGGER.info(
            "Benchmark %d/%d: %s/%s nodes=%d parents=%d states=%d",
            index,
            len(runnable),
            row.Representation,
            row.ModelScope,
            row.BenchmarkNodeCount,
            row.ParentCount,
            row.StateCardinality,
        )
        observed = benchmark_case(
            node_count=int(row.BenchmarkNodeCount),
            parent_count=int(row.ParentCount),
            states=int(row.StateCardinality),
            repetitions=int(benchmark["repetitions"]),
            warmups=int(benchmark["warmup_runs"]),
            evidence_count=int(benchmark["query_evidence_count"]),
        )
        results.append(
            {
                "Representation": row.Representation,
                "ModelScope": row.ModelScope,
                "ActualCandidateVariables": int(row.ActualCandidateVariables),
                "BenchmarkNodeCount": int(row.BenchmarkNodeCount),
                "FractionOfActualModel": float(row.FractionOfActualModel),
                "Topology": row.Topology,
                "ParentCount": int(row.ParentCount),
                "StateCase": row.StateCase,
                "StateCardinality": int(row.StateCardinality),
                "ApproxTotalCptEntries": int(row.ApproxTotalCptEntries),
                **observed,
                "EvidenceClass": "benchmark",
                "ClinicalMeaning": "none -- synthetic computational benchmark",
            }
        )

    results_frame = pd.DataFrame(results)
    results_path = paths.phase3_tables / "benchmark_results.csv"
    results_frame.to_csv(results_path, index=False)
    LOGGER.info("Wrote benchmark results: %s (%d rows)", results_path, len(results_frame))

    skipped = plan.loc[~plan["Runnable"].astype(bool)].copy()
    skipped.to_csv(paths.phase3_tables / "benchmark_skipped_cases.csv", index=False)

    methodology = pd.DataFrame(
        [
            {
                "Item": "Topology",
                "EvidenceClass": "assumption",
                "Statement": (
                    "rolling_window_dag gives each node up to N immediately preceding "
                    "nodes as parents. It is a benchmark shape, not a clinical DAG."
                ),
            },
            {
                "Item": "Probabilities",
                "EvidenceClass": "assumption",
                "Statement": (
                    "Uniform synthetic CPT values are used. They have no clinical "
                    "interpretation; only computational behaviour is measured."
                ),
            },
            {
                "Item": "Memory",
                "EvidenceClass": "benchmark",
                "Statement": (
                    "PythonPeakAllocatedMiB is tracemalloc peak allocation during model "
                    "construction and inference initialisation, not total container RSS."
                ),
            },
            {
                "Item": "Serialised size",
                "EvidenceClass": "benchmark",
                "Statement": (
                    "SerializedModelMiB is a Python pickle size for the pgmpy model, "
                    "not a storage-format recommendation."
                ),
            },
            {
                "Item": "Exact inference",
                "EvidenceClass": "benchmark",
                "Statement": (
                    "VariableElimination latency is meaningful only with the recorded "
                    "topology, parent count and state cardinality."
                ),
            },
        ]
    )
    methodology.to_csv(paths.phase3_tables / "phase3c_method_notes.csv", index=False)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Phase 3C controlled pgmpy exact-inference benchmark."
    )
    parser.add_argument(
        "--plan-only",
        action="store_true",
        help="Write benchmark_plan.csv without importing pgmpy or executing cases.",
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
        config = _load_yaml(paths.config_dir / "phase3.yaml")
        paths.ensure_phase3_directories()
        if args.plan_only:
            plan = build_benchmark_plan(paths, config)
            plan.to_csv(paths.phase3_tables / "benchmark_plan.csv", index=False)
            LOGGER.info("Wrote Phase 3C benchmark plan only (%d rows).", len(plan))
        else:
            run_phase3c(paths)
        return 0
    except ConfigurationError as exc:
        LOGGER.error("Configuration error: %s", exc)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
