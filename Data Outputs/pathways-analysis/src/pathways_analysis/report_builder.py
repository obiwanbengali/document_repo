"""Presentation-layer transformation: analytical CSVs to scoped report JSON.

Usage::

    python -m pathways_analysis.report_builder
    python -m pathways_analysis.report_builder --phase 1
    python -m pathways_analysis.report_builder --phase 2

Reads the Phase 1 and Phase 2 output tables and writes two deliberately narrow JSON
files for the static report in ``reports/``:

* ``reports/data/phase1-report.json``
* ``reports/data/phase2-report.json``

What this module is for
-----------------------
The analytical estate is ~80 CSV files aimed at people doing the analysis. A browser
must not ingest it, for two reasons: most of it is irrelevant to a briefing, and much
of it is confidential clinical content that has no business being loaded into a page.
This module decides, explicitly and reviewably, what the presentation is allowed to
see.

Rules it follows
----------------
1. **Read-only over the evidence.** It opens files under ``outputs/`` and writes only
   under ``reports/data/``. It never modifies, moves or regenerates an analytical
   artefact, and it needs no database connection at all.
2. **Aggregate by default.** Distributions are banded into plain-English buckets rather
   than shipped per pathway. The only per-pathway data that reaches the browser is a
   ten-row most-connected list carrying identifiers and degree counts, with no titles.
3. **No clinical free text.** No question text, no symptom-discriminator descriptions,
   no SNOMED preferred terms, no pathway titles. Symptom-group and clinical-area
   *names* are included, because the candidate-family explorer is unusable without
   them and they are reference metadata rather than patient-facing content.
4. **Lineage travels with the data.** Every block carries the artefact path it came
   from, so a figure in the browser can always be traced back to the CSV behind it.
5. **Evidence class travels with the data.** Every block is tagged ``measured``,
   ``derived`` or ``candidate``. The fourth class in the programme's scheme,
   architectural interpretation, is deliberately absent: it is Phase 3 work, and
   nothing here may imply it.
6. **Fail loudly.** A missing artefact or a missing column is an error, not a silently
   empty section. A report that quietly omits a section would misrepresent the
   evidence.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Final, Iterable, Mapping, Sequence

import pandas as pd

from .config import Paths

LOGGER: Final = logging.getLogger("pathways_analysis.report_builder")

#: Bumped when the JSON shape changes, so a stale file cannot be mistaken for a current
#: one by a page expecting different keys.
SCHEMA_VERSION: Final = "1.2"

#: Shown on every page of the report.
CONFIDENTIALITY_NOTICE: Final = (
    "Contains derived NHS Pathways analysis. Handle according to programme "
    "information governance requirements."
)

#: The three evidence classes the presentation may use, and what each means to a reader.
#: "architectural interpretation" is intentionally not here.
EVIDENCE_CLASSES: Final[dict[str, str]] = {
    "measured": "Counted directly in the NHS Pathways dataset.",
    "derived": (
        "Calculated from measured values using a stated definition. The definition is "
        "given with the figure."
    ),
    "candidate": (
        "A possible grouping, boundary or shared structure suggested by the evidence. "
        "Requires clinical review and architectural judgement before it means anything."
    ),
}

#: Number of most-connected pathways shown. Identifiers and counts only.
TOP_CONNECTED_LIMIT: Final = 10

#: Families shown on the overlap heatmaps. Beyond roughly this many the axis labels stop
#: being legible, and single-pathway families produce all-zero rows either way.
HEATMAP_FAMILY_LIMIT: Final = 20

#: Merge and split candidates shown. The brief asks for "a small number of strongest".
MERGE_SPLIT_LIMIT: Final = 6

#: Plain-English bands for the pathway-size distribution. An executive reader is served
#: better by "26-50 questions" than by an arbitrary bin width.
QUESTION_COUNT_BANDS: Final[tuple[tuple[str, int, int | None], ...]] = (
    ("No questions", 0, 0),
    ("1-10", 1, 10),
    ("11-25", 11, 25),
    ("26-50", 26, 50),
    ("51-75", 51, 75),
    ("76-100", 76, 100),
    ("101-150", 101, 150),
    ("151+", 151, None),
)

#: Bands for how many other pathways a pathway connects to.
DEGREE_BANDS: Final[tuple[tuple[str, int, int | None], ...]] = (
    ("None", 0, 0),
    ("1", 1, 1),
    ("2", 2, 2),
    ("3-5", 3, 5),
    ("6-10", 6, 10),
    ("11-20", 11, 20),
    ("21+", 21, None),
)

#: Bands for how many pathways reuse a symptom discriminator.
REUSE_BANDS: Final[tuple[tuple[str, int, int | None], ...]] = (
    ("1 pathway", 1, 1),
    ("2-5", 2, 5),
    ("6-10", 6, 10),
    ("11-25", 11, 25),
    ("26-50", 26, 50),
    ("51+", 51, None),
)


class ReportBuildError(RuntimeError):
    """Raised when the report cannot be built from the available evidence.

    Always names the artefact and what was expected, so the fix is obvious: usually
    "run Phase 1" or "run Phase 2".
    """


@dataclass(frozen=True)
class Artefact:
    """One analytical output the report depends on.

    Attributes:
        relative_path: Path under the project root, used verbatim as the lineage string
            shown in the browser.
        columns: Columns the presentation reads. Checked on load, so a renamed column
            in the analysis fails here rather than producing a blank chart.
        produced_by: The command that creates it, quoted in the error message.
    """

    relative_path: str
    columns: tuple[str, ...]
    produced_by: str

    def path(self, paths: Paths) -> Path:
        return paths.project_root / self.relative_path


PHASE1_RUNNER: Final = "python -m pathways_analysis.profiling"
PHASE2_RUNNER: Final = "python -m pathways_analysis.family_discovery"

PHASE1_ARTEFACTS: Final[dict[str, Artefact]] = {
    "inventory": Artefact(
        "outputs/tables/dataset_inventory.csv", ("metric", "value"), PHASE1_RUNNER
    ),
    "complexity": Artefact(
        "outputs/tables/pathway_complexity.csv",
        ("pathway_id", "is_active", "question_count", "logic_row_count"),
        PHASE1_RUNNER,
    ),
    "complexity_summary": Artefact(
        "outputs/tables/pathway_complexity_summary.csv",
        ("metric", "count", "min", "mean", "median", "p90", "p95", "p99", "max"),
        PHASE1_RUNNER,
    ),
    "question_reuse_bands": Artefact(
        "outputs/tables/question_reuse_bands.csv",
        ("band", "question_count", "percentage_of_questions"),
        PHASE1_RUNNER,
    ),
    "discriminator_reuse": Artefact(
        "outputs/tables/discriminator_reuse_distribution.csv",
        ("pathway_count", "number_of_discriminators"),
        PHASE1_RUNNER,
    ),
    "graph_metrics": Artefact(
        "outputs/tables/pathway_graph_metrics.csv",
        ("scope", "metric", "value"),
        PHASE1_RUNNER,
    ),
    "graph_nodes": Artefact(
        "outputs/tables/pathway_graph_nodes.csv",
        ("pathway_id", "is_active", "in_degree", "out_degree", "total_degree"),
        PHASE1_RUNNER,
    ),
    "clinical_areas": Artefact(
        "outputs/tables/clinical_area_analysis.csv",
        (
            "clinical_area_description",
            "area_group",
            "pathway_count",
            "internal_edge_percentage",
        ),
        PHASE1_RUNNER,
    ),
    "symptom_groups": Artefact(
        "outputs/tables/symptom_group_analysis.csv",
        ("sg_id", "sg_desc", "pathway_count", "internal_edge_percentage"),
        PHASE1_RUNNER,
    ),
    "answer_cardinality": Artefact(
        "outputs/tables/answer_cardinality_summary.csv",
        ("metric", "count", "min", "median", "mean", "max"),
        PHASE1_RUNNER,
    ),
    # Age and trauma metadata is extracted by Phase 2, not Phase 1. The Phase 1 report
    # shows it because it is part of "how Pathways is already grouped", and the lineage
    # string names the Phase 2 artefact so the provenance is not misrepresented.
    "age_analysis": Artefact(
        "outputs/phase2/tables/age_family_analysis.csv",
        ("AnalysisScope", "GroupOrFamily", "PathwayCount"),
        PHASE2_RUNNER,
    ),
    "trauma_analysis": Artefact(
        "outputs/phase2/tables/trauma_family_analysis.csv",
        ("AnalysisScope", "GroupOrFamily", "PathwayCount"),
        PHASE2_RUNNER,
    ),
    "metadata_coverage": Artefact(
        "outputs/phase2/tables/pathway_metadata_coverage.csv",
        (
            "field",
            "pathways_populated",
            "pathways_missing",
            "coverage_percentage",
            "distinct_values",
            "usable_as_grouping",
        ),
        PHASE2_RUNNER,
    ),
}

PHASE2_ARTEFACTS: Final[dict[str, Artefact]] = {
    "configuration": Artefact(
        "outputs/phase2/reports/configuration_used.csv",
        ("setting", "value"),
        PHASE2_RUNNER,
    ),
    "strategy_comparison": Artefact(
        "outputs/phase2/tables/family_strategy_comparison.csv",
        (
            "strategy",
            "FamilyBasis",
            "FamilyCount",
            "MedianFamilySize",
            "MaxFamilySize",
            "MedianInternalEdgePercentage",
            "MedianExternalEdgePercentage",
            "MedianBoundaryPathwayPercentage",
            "IsOverlapping",
        ),
        PHASE2_RUNNER,
    ),
    "community_methods": Artefact(
        "outputs/phase2/tables/community_method_comparison.csv",
        (
            "method",
            "available",
            "community_count",
            "modularity",
            "largest_community_size",
            "adjusted_rand_index_vs_primary",
            "is_primary_method",
        ),
        PHASE2_RUNNER,
    ),
    "similarity_summary": Artefact(
        "outputs/phase2/tables/pathway_similarity_summary.csv",
        (
            "dimension",
            "pathways_with_any_feature",
            "overlapping_pairs",
            "possible_pairs",
            "percentage_of_pairs_overlapping",
            "median_jaccard",
        ),
        PHASE2_RUNNER,
    ),
    "families": Artefact(
        "outputs/phase2/tables/candidate_bayesian_families.csv",
        (
            "FamilyId",
            "FamilyName",
            "FamilyNameBasis",
            "FamilyBasis",
            "Strategy",
            "PathwayCount",
            "PrimaryClinicalAreas",
            "PrimarySymptomGroups",
            "InternalEdgePercentage",
            "ExternalEdgePercentage",
            "UniqueQuestions",
            "UniqueSDs",
            "UniqueSnomed",
            "UniqueDispositions",
            "BoundaryPathwayCount",
            "CrossFamilyHubCount",
            "StrongOverlapFamilies",
            "SharedCoreDependencyCount",
            "ConfidenceInStructuralCohesion",
            "ClinicalReviewRequired",
            "Notes",
        ),
        PHASE2_RUNNER,
    ),
    "overlap": Artefact(
        "outputs/phase2/tables/family_overlap_matrix.csv",
        (
            "strategy",
            "FamilyA",
            "FamilyB",
            "TransitionsAtoB",
            "TransitionsBtoA",
            "SdJaccard",
            "QuestionJaccard",
            "SnomedJaccard",
            "OverlapBand",
        ),
        PHASE2_RUNNER,
    ),
    "boundary_summary": Artefact(
        "outputs/phase2/tables/boundary_pathway_summary.csv",
        (
            "strategy",
            "PathwaysClassified",
            "count_internal_pathway",
            "count_weak_boundary_pathway",
            "count_strong_boundary_pathway",
            "count_cross_family_hub",
            "BoundaryPathwayCount",
            "BoundaryPathwayPercentage",
        ),
        PHASE2_RUNNER,
    ),
    "shared_feature_summary": Artefact(
        "outputs/phase2/tables/shared_feature_summary.csv",
        (
            "FeatureType",
            "FeatureTypeLabel",
            "FeaturesTotal",
            "FamilySpecific",
            "SharedBy2Families",
            "SharedBy3To5Families",
            "BroadlyShared",
            "SharedCoreCandidates",
            "TotalDuplicationIfFederated",
            "MaxFamilyCount",
        ),
        PHASE2_RUNNER,
    ),
    "routing_summary": Artefact(
        "outputs/phase2/tables/pathway_family_routing_summary.csv",
        (
            "strategy",
            "PathwaysScored",
            "PercentageStrongSingleFamilyAssociation",
            "PercentageModerateAmbiguity",
            "PercentageHighAmbiguity",
            "PercentageOnePlausibleFamily",
            "PercentageTwoPlausibleFamilies",
            "PercentageThreeOrMorePlausibleFamilies",
        ),
        PHASE2_RUNNER,
    ),
    "merge_candidates": Artefact(
        "outputs/phase2/tables/family_merge_candidates.csv",
        (
            "strategy",
            "FamilyA",
            "FamilyB",
            "OverlapDriver",
            "SmallerFamilyPathwayCount",
            "PathwayCountBeforeA",
            "PathwayCountBeforeB",
            "PathwayCountAfterMerge",
            "InternalEdgePercentageBeforeWeighted",
            "InternalEdgePercentageAfterMerge",
            "MeanPairwiseSdJaccardBeforeWeighted",
            "MeanPairwiseSdJaccardAfterMerge",
            "MeanPairwiseSdJaccardDelta",
            "StructuralVerdict",
        ),
        PHASE2_RUNNER,
    ),
    "split_candidates": Artefact(
        "outputs/phase2/tables/family_split_candidates.csv",
        (
            "strategy",
            "FamilyId",
            "SplitMethod",
            "SplitTriggers",
            "PathwayCountBefore",
            "PartCount",
            "PartSizes",
            "InternalEdgePercentageBefore",
            "InternalEdgePercentageAfterWeighted",
            "MeanPairwiseSdJaccardBefore",
            "MeanPairwiseSdJaccardAfterWeighted",
            "MeanPairwiseSdJaccardDelta",
            "StructuralVerdict",
        ),
        PHASE2_RUNNER,
    ),
    "high_overlap": Artefact(
        "outputs/phase2/tables/high_overlap_family_pairs.csv",
        ("strategy", "FamilyA", "FamilyB", "OverlapDriver", "SmallerFamilyPathwayCount"),
        PHASE2_RUNNER,
    ),
}


# ======================================================================================
# Loading and validation
# ======================================================================================
def load_artefact(artefact: Artefact, paths: Paths) -> pd.DataFrame:
    """Load one analytical table, failing clearly if it is missing or has changed shape.

    Raises:
        ReportBuildError: If the file does not exist, is empty, or lacks a column the
            presentation reads.
    """
    path = artefact.path(paths)
    if not path.is_file():
        raise ReportBuildError(
            f"Required evidence is missing: {artefact.relative_path}\n"
            f"  Produce it with: {artefact.produced_by}"
        )
    try:
        frame = pd.read_csv(path)
    except Exception as exc:  # noqa: BLE001 - surfaced with the path, whatever the cause
        raise ReportBuildError(
            f"Could not read {artefact.relative_path}: {type(exc).__name__}: {exc}"
        ) from exc

    missing = [column for column in artefact.columns if column not in frame.columns]
    if missing:
        raise ReportBuildError(
            f"{artefact.relative_path} is missing column(s) {missing}.\n"
            f"  The analysis output has changed shape since the report was written. "
            f"Re-run {artefact.produced_by}, or update report_builder.py to match."
        )
    if frame.empty:
        raise ReportBuildError(
            f"{artefact.relative_path} has no rows. Re-run {artefact.produced_by}."
        )
    LOGGER.debug("Loaded %-58s %6d rows", artefact.relative_path, len(frame))
    return frame


def load_all(artefacts: Mapping[str, Artefact], paths: Paths) -> dict[str, pd.DataFrame]:
    """Load every artefact, reporting *all* missing ones rather than only the first.

    A reader whose Phase 2 run never happened should be told that once, with the whole
    list, not made to discover it one file at a time.
    """
    frames: dict[str, pd.DataFrame] = {}
    errors: list[str] = []
    for name, artefact in artefacts.items():
        try:
            frames[name] = load_artefact(artefact, paths)
        except ReportBuildError as exc:
            errors.append(str(exc))
    if errors:
        raise ReportBuildError(
            f"{len(errors)} required artefact(s) could not be used:\n\n"
            + "\n\n".join(errors)
        )
    return frames


def validate_payload(
    payload: Mapping[str, Any], expected: Sequence[str], label: str
) -> None:
    """Check that a built payload has every top-level key the page reads.

    Raises:
        ReportBuildError: If a key is missing or holds an empty value. Catching this
            here means a page never has to defend against a half-built payload.
    """
    missing = [key for key in expected if key not in payload]
    if missing:
        raise ReportBuildError(f"{label} payload is missing key(s) {missing}.")
    empty = [
        key
        for key in expected
        if key not in {"meta"} and not payload[key] and payload[key] != 0
    ]
    if empty:
        raise ReportBuildError(
            f"{label} payload has empty value(s) for {empty}. The underlying evidence "
            "produced nothing for these sections, which would render as blank panels."
        )


# ======================================================================================
# Small shared helpers
# ======================================================================================
def _band(value: float, bands: Sequence[tuple[str, int, int | None]]) -> str:
    """Return the band label a value falls into."""
    for label, lower, upper in bands:
        if value >= lower and (upper is None or value <= upper):
            return label
    return bands[-1][0]


def _banded_counts(
    values: Iterable[float],
    bands: Sequence[tuple[str, int, int | None]],
) -> list[dict[str, Any]]:
    """Band a set of values into plain-English buckets.

    Banding rather than shipping the raw series is what keeps the payload small and the
    chart readable, and it means no per-pathway value reaches the browser.
    """
    counts = {label: 0 for label, _, _ in bands}
    total = 0
    for value in values:
        if pd.isna(value):
            continue
        counts[_band(float(value), bands)] += 1
        total += 1
    return [
        {
            "band": label,
            "count": counts[label],
            "percentage": round(100.0 * counts[label] / total, 1) if total else 0.0,
        }
        for label, _, _ in bands
    ]


def _weighted_banded_counts(
    frame: pd.DataFrame,
    *,
    value_column: str,
    weight_column: str,
    bands: Sequence[tuple[str, int, int | None]],
) -> list[dict[str, Any]]:
    """Band an already-aggregated distribution (value plus how many items have it)."""
    counts = {label: 0 for label, _, _ in bands}
    total = 0
    for row in frame.itertuples():
        value = getattr(row, value_column)
        weight = int(getattr(row, weight_column))
        if pd.isna(value):
            continue
        counts[_band(float(value), bands)] += weight
        total += weight
    return [
        {
            "band": label,
            "count": counts[label],
            "percentage": round(100.0 * counts[label] / total, 1) if total else 0.0,
        }
        for label, _, _ in bands
    ]


def _number(value: Any, default: float = 0.0) -> float:
    """Coerce to float, mapping missing values to a default."""
    if value is None or (not isinstance(value, str) and pd.isna(value)):
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _optional_number(value: Any) -> float | None:
    """Coerce to float, mapping missing values to None so JSON carries null."""
    if value is None or (not isinstance(value, str) and pd.isna(value)):
        return None
    try:
        return round(float(value), 4)
    except (TypeError, ValueError):
        return None


def _text(value: Any) -> str:
    """Coerce to a trimmed string, mapping missing values to an empty string."""
    if value is None or (not isinstance(value, str) and pd.isna(value)):
        return ""
    return str(value).strip()


def _lookup(frame: pd.DataFrame, key_column: str, value_column: str) -> dict[str, float]:
    """Turn a two-column long-format table into a mapping."""
    return {
        _text(row[key_column]): _number(row[value_column])
        for _, row in frame.iterrows()
    }


def _pipe_first(value: Any, limit: int = 3) -> list[str]:
    """Split a pipe-joined field into at most ``limit`` trimmed values."""
    parts = [part.strip() for part in _text(value).split("|") if part.strip()]
    return parts[:limit]


def _meta(phase: str, title: str, question: str) -> dict[str, Any]:
    """Build the shared meta block every payload carries."""
    return {
        "schema_version": SCHEMA_VERSION,
        "phase": phase,
        "title": title,
        "question": question,
        "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "confidentiality": CONFIDENTIALITY_NOTICE,
        "evidence_classes": EVIDENCE_CLASSES,
        "scope_note": (
            "This report presents measured and derived evidence only. It makes no "
            "architectural recommendation: comparing monolithic against federated "
            "designs is Phase 3 work."
        ),
    }


# ======================================================================================
# Phase 1 payload
# ======================================================================================
PHASE1_KEYS: Final[tuple[str, ...]] = (
    "meta",
    "executive_summary",
    "estate",
    "pathway_size",
    "reuse",
    "connectivity",
    "groupings",
    "tells_us",
    "conclusion",
    "does_not_tell_us",
    "methodology",
)


def build_phase1(paths: Paths) -> dict[str, Any]:
    """Build the Phase 1 presentation payload."""
    LOGGER.info("--- Building Phase 1 report data ---")
    frames = load_all(PHASE1_ARTEFACTS, paths)
    source = {name: artefact.relative_path for name, artefact in PHASE1_ARTEFACTS.items()}

    inventory = _lookup(frames["inventory"], "metric", "value")
    graph_metrics = frames["graph_metrics"]
    graph = {
        _text(row.metric): _number(row.value)
        for row in graph_metrics.loc[graph_metrics["scope"] == "all_participating"].itertuples()
    }
    graph_active = {
        _text(row.metric): _number(row.value)
        for row in graph_metrics.loc[graph_metrics["scope"] == "active_only"].itertuples()
    }

    payload: dict[str, Any] = {
        "meta": _meta(
            "1",
            "Understanding NHS Pathways",
            "What does NHS Pathways actually look like?",
        ),
        "executive_summary": _phase1_executive_summary(inventory, graph, frames),
        "estate": _phase1_estate(inventory, graph, source),
        "pathway_size": _phase1_pathway_size(frames, source),
        "reuse": _phase1_reuse(frames, inventory, source),
        "connectivity": _phase1_connectivity(frames, graph, graph_active, source),
        "groupings": _phase1_groupings(frames, inventory, source),
        "tells_us": _phase1_tells_us(inventory, graph, frames),
        "conclusion": _phase1_conclusion(inventory, graph, frames),
        "does_not_tell_us": [
            "Whether one large Bayesian Network or several smaller ones is the better "
            "design — in technical terms, monolithic against federated. Phase 1 "
            "measures the estate; it does not compare architectures.",
            "Which Bayesian families should exist. Phase 2 proposes candidates; none is "
            "confirmed.",
            "How large a Bayesian model built from this data would be, in nodes, edges "
            "or probability tables.",
            "How much memory or compute a model would need, or how fast it would "
            "answer.",
            "What infrastructure would be required, or what it would cost to run, "
            "including any cloud infrastructure cost.",
            "How often each pathway is actually used. The dataset carries structure, "
            "not traffic, so a rarely-used pathway counts the same as a busy one.",
        ],
        "methodology": _phase1_methodology(),
    }
    validate_payload(payload, PHASE1_KEYS, "phase1")
    return payload


def _phase1_executive_summary(
    inventory: Mapping[str, float],
    graph: Mapping[str, float],
    frames: Mapping[str, pd.DataFrame],
) -> dict[str, Any]:
    """Short non-technical summary for senior readers."""
    bands = frames["question_reuse_bands"]
    total = int(bands["question_count"].sum())
    single = int(
        bands.loc[bands["band"].astype(str).str.startswith("1 pathway"), "question_count"].sum()
    )
    shared_pct = round(100.0 * (total - single) / total, 0) if total else 0

    summary = frames["complexity_summary"]
    question_row = summary.loc[summary["metric"] == "QuestionCount"]
    median = int(_number(question_row.iloc[0]["median"])) if not question_row.empty else 0
    largest = int(_number(question_row.iloc[0]["max"])) if not question_row.empty else 0

    active = int(inventory.get("pathways_active", 0))
    edges = int(graph.get("edge_count", 0))
    connected = int(graph.get("largest_weakly_connected_component", 0))

    return {
        "evidence_class": "derived",
        "headline": "NHS Pathways is one connected clinical decision estate, not hundreds of "
        "isolated pathways.",
        "summary": (
            f"Phase 1 examined the structure of {active:,} active pathways and found extensive "
            "connectivity, reuse and variation in size. The evidence is strong enough to move "
            "from"
            "describing the estate to testing where meaningful Bayesian family boundaries "
            "might sit."
        ),
        "key_points": [
            (
                f"{connected:,} active pathways sit in the largest connected group, with "
                f"{edges:,} distinct pathway-to-pathway relationships."
            ),
            (
                f"About {shared_pct:.0f}% of referenced questions are reused across "
                "more than one "
                "pathway, so the estate contains substantial shared clinical structure."
            ),
            (
                "Pathway size varies materially: the typical pathway contains "
                f"{median} questions "
                f"while the largest contains {largest}."
            ),
            (
                "Existing classifications such as Symptom Groups, Clinical Areas, age and "
                "trauma"
                "provide useful signals, but overlap and do not cleanly divide the estate."
            ),
        ],
        "bottom_line": (
            "Phase 1 supports proceeding to family discovery. It does not decide whether the "
            "final"
            "Bayesian architecture should be monolithic or federated."
        ),
    }


def _phase1_estate(
    inventory: Mapping[str, float],
    graph: Mapping[str, float],
    source: Mapping[str, str],
) -> dict[str, Any]:
    """Headline counts for the estate, all measured."""
    def card(key: str, label: str, metric: str, explanation: str) -> dict[str, Any]:
        return {
            "key": key,
            "label": label,
            "value": int(inventory.get(metric, 0)),
            "evidence_class": "measured",
            "explanation": explanation,
        }

    return {
        "evidence_class": "measured",
        "source": [source["inventory"], source["graph_metrics"]],
        "cards": [
            card(
                "pathways",
                "Active pathways",
                "pathways_active",
                "A pathway is one clinical assessment flow, such as the assessment for "
                "a particular symptom. Active means in use rather than archived.",
            ),
            card(
                "questions",
                "Questions",
                "questions_active",
                "Distinct questions available to ask across the whole estate. Many are "
                "used by more than one pathway.",
            ),
            card(
                "answers",
                "Answers",
                "answers_total",
                "The possible responses to those questions. Each answer can lead "
                "somewhere different.",
            ),
            {
                "key": "triage_logic",
                "label": "Triage logic relationships",
                "value": int(inventory.get("triage_logic_rows", 0)),
                "evidence_class": "measured",
                "explanation": (
                    "Each row records what happens after a specific answer to a "
                    "specific question in a specific pathway. This is the wiring of "
                    "the whole estate."
                ),
            },
            card(
                "dispositions",
                "Dispositions",
                "dispositions_active",
                "The possible outcomes of an assessment, such as an ambulance response "
                "or a primary-care referral within a stated time.",
            ),
            card(
                "symptom_groups",
                "Symptom groups",
                "symptom_groups_total",
                "An existing NHS classification that groups pathways by presenting "
                "symptom.",
            ),
            card(
                "symptom_discriminators",
                "Symptom discriminators",
                "symptom_discriminators_total",
                "Clinical factors that distinguish more urgent presentations from less "
                "urgent ones.",
            ),
            card(
                "clinical_areas",
                "Clinical areas",
                "clinical_areas_total",
                "A broad anatomical or clinical grouping, such as chest or head. A "
                "pathway can belong to more than one.",
            ),
            {
                "key": "pathway_links",
                "label": "Pathway-to-pathway links",
                "value": int(graph.get("edge_count", 0)),
                "evidence_class": "derived",
                "explanation": (
                    "Distinct ways one pathway can hand over to another. Derived by "
                    "resolving every recorded transfer instruction to its target "
                    "pathway."
                ),
            },
        ],
    }


def _phase1_pathway_size(
    frames: Mapping[str, pd.DataFrame], source: Mapping[str, str]
) -> dict[str, Any]:
    """Distribution of questions per pathway, banded."""
    summary = frames["complexity_summary"]
    row = summary.loc[summary["metric"] == "QuestionCount"]
    if row.empty:
        raise ReportBuildError(
            "pathway_complexity_summary.csv has no 'QuestionCount' row, which the "
            "pathway-size section needs."
        )
    stats = row.iloc[0]

    complexity = frames["complexity"]
    active = complexity.loc[complexity["is_active"].astype(str).str.lower().isin(
        {"true", "1", "yes"}
    )]
    if active.empty:
        raise ReportBuildError(
            "pathway_complexity.csv contains no active pathways, so the pathway-size "
            "distribution cannot be built."
        )

    return {
        "evidence_class": "derived",
        "source": [source["complexity_summary"], source["complexity"]],
        "definition": (
            "Questions counted per pathway are the answerable triage questions only. "
            "Care-advice and disposition steps are counted separately and excluded here."
        ),
        "stats": {
            "pathways": int(_number(stats["count"])),
            "min": int(_number(stats["min"])),
            "median": int(_number(stats["median"])),
            "mean": round(_number(stats["mean"]), 1),
            "p90": int(_number(stats["p90"])),
            "p95": int(_number(stats["p95"])),
            "max": int(_number(stats["max"])),
        },
        "distribution": _banded_counts(active["question_count"], QUESTION_COUNT_BANDS),
        "logic_rows": {
            "median": int(
                _number(
                    summary.loc[summary["metric"] == "LogicRowCount", "median"].iloc[0]
                    if not summary.loc[summary["metric"] == "LogicRowCount"].empty
                    else 0
                )
            ),
            "max": int(
                _number(
                    summary.loc[summary["metric"] == "LogicRowCount", "max"].iloc[0]
                    if not summary.loc[summary["metric"] == "LogicRowCount"].empty
                    else 0
                )
            ),
        },
    }


def _phase1_reuse(
    frames: Mapping[str, pd.DataFrame],
    inventory: Mapping[str, float],
    source: Mapping[str, str],
) -> dict[str, Any]:
    """How much question and discriminator content is shared between pathways."""
    bands = frames["question_reuse_bands"]
    question_bands = [
        {
            "band": _text(row.band),
            "count": int(_number(row.question_count)),
            "percentage": round(_number(row.percentage_of_questions), 1),
        }
        for row in bands.itertuples()
    ]
    total_questions = sum(item["count"] for item in question_bands)
    single_use = next(
        (item["count"] for item in question_bands if item["band"].startswith("1 pathway")),
        0,
    )

    discriminators = _weighted_banded_counts(
        frames["discriminator_reuse"],
        value_column="pathway_count",
        weight_column="number_of_discriminators",
        bands=REUSE_BANDS,
    )
    answers = frames["answer_cardinality"]
    answer_row = answers.loc[
        answers["metric"] == "catalogue_answer_count_active_questions"
    ]

    return {
        "evidence_class": "derived",
        "source": [
            source["question_reuse_bands"],
            source["discriminator_reuse"],
            source["answer_cardinality"],
        ],
        "definition": (
            "A question is counted as reused when more than one pathway references it. "
            "Reuse is counted from the recorded wiring, not from how often a question "
            "is actually asked."
        ),
        "question_bands": question_bands,
        "discriminator_bands": discriminators,
        "headline": {
            "questions_referenced": total_questions,
            "single_pathway_questions": single_use,
            "single_pathway_percentage": (
                round(100.0 * single_use / total_questions, 1) if total_questions else 0.0
            ),
            "shared_percentage": (
                round(100.0 * (total_questions - single_use) / total_questions, 1)
                if total_questions
                else 0.0
            ),
            "answers_per_question_median": (
                int(_number(answer_row.iloc[0]["median"])) if not answer_row.empty else 0
            ),
            "answers_per_question_max": (
                int(_number(answer_row.iloc[0]["max"])) if not answer_row.empty else 0
            ),
            "discriminators_reachable": int(
                inventory.get("symptom_discriminators_total", 0)
            ),
        },
    }


def _phase1_connectivity(
    frames: Mapping[str, pd.DataFrame],
    graph: Mapping[str, float],
    graph_active: Mapping[str, float],
    source: Mapping[str, str],
) -> dict[str, Any]:
    """Pathway-to-pathway connectedness, banded, plus a short most-connected list."""
    nodes = frames["graph_nodes"]
    active = nodes.loc[nodes["is_active"].astype(str).str.lower().isin(
        {"true", "1", "yes"}
    )]
    if active.empty:
        active = nodes

    # Identifiers and counts only: no pathway titles reach the browser. The titles are
    # in the detailed evidence files for anyone who needs them.
    top = active.nlargest(TOP_CONNECTED_LIMIT, "total_degree")
    top_connected = [
        {
            "pathway_id": _text(row.pathway_id),
            "outgoing": int(_number(row.out_degree)),
            "incoming": int(_number(row.in_degree)),
            "total": int(_number(row.total_degree)),
        }
        for row in top.itertuples()
    ]

    return {
        "evidence_class": "derived",
        "source": [source["graph_metrics"], source["graph_nodes"]],
        "definition": (
            "A link exists between two pathways when an answer in the first can hand "
            "the assessment over to the second. Links are counted once per pair and "
            "direction, however many answers create them."
        ),
        "cards": [
            {
                "key": "links",
                "label": "Pathway-to-pathway links",
                "value": int(graph.get("edge_count", 0)),
                "explanation": "Distinct directed handovers between pathways.",
            },
            {
                "key": "transitions",
                "label": "Recorded handover instructions",
                "value": int(graph.get("total_transition_count", 0)),
                "explanation": (
                    "Individual transfer instructions in the data. Several can create "
                    "the same link."
                ),
            },
            {
                "key": "connected",
                "label": "Pathways in the largest connected group",
                "value": int(graph.get("largest_weakly_connected_component", 0)),
                "explanation": (
                    "The largest set of pathways reachable from one another by "
                    "following handovers in any direction."
                ),
            },
            {
                "key": "isolated",
                "label": "Pathways with no handovers",
                "value": int(graph.get("isolated_node_count", 0)),
                "explanation": "Pathways that neither hand over nor receive handovers.",
            },
        ],
        "outgoing_distribution": _banded_counts(active["out_degree"], DEGREE_BANDS),
        "incoming_distribution": _banded_counts(active["in_degree"], DEGREE_BANDS),
        "top_connected": top_connected,
        "components": {
            "separate_groups": int(graph.get("weakly_connected_components", 0)),
            "largest_group": int(graph.get("largest_weakly_connected_component", 0)),
            "nodes": int(graph.get("node_count", 0)),
            "active_only_nodes": int(graph_active.get("node_count", 0)),
            "active_only_edges": int(graph_active.get("edge_count", 0)),
        },
        "presentation_note": (
            "The full network is not drawn. At this size a single node-link diagram is "
            "unreadable and would not support any conclusion. The distributions and the "
            "family-level view in Phase 2 carry the same information legibly."
        ),
    }


def _phase1_groupings(
    frames: Mapping[str, pd.DataFrame],
    inventory: Mapping[str, float],
    source: Mapping[str, str],
) -> dict[str, Any]:
    """The groupings that already exist in the Pathways data."""
    areas = frames["clinical_areas"]
    clinical_areas = [
        {
            "name": _text(row.clinical_area_description),
            "area_group": _text(row.area_group),
            "pathway_count": int(_number(row.pathway_count)),
            "internal_link_percentage": _optional_number(row.internal_edge_percentage),
        }
        for row in areas.sort_values("pathway_count", ascending=False).itertuples()
    ]

    groups = frames["symptom_groups"]
    populated = groups.loc[groups["pathway_count"] > 0]
    symptom_groups = {
        "total_catalogued": int(len(groups)),
        "with_active_pathways": int(len(populated)),
        "median_pathways": (
            int(populated["pathway_count"].median()) if not populated.empty else 0
        ),
        "largest": [
            {
                "name": _text(row.sg_desc),
                "pathway_count": int(_number(row.pathway_count)),
            }
            for row in populated.nlargest(12, "pathway_count").itertuples()
        ],
        "size_distribution": _banded_counts(
            populated["pathway_count"],
            (
                ("1 pathway", 1, 1),
                ("2-5", 2, 5),
                ("6-10", 6, 10),
                ("11-25", 11, 25),
                ("26+", 26, None),
            ),
        ),
    }

    def tag_counts(frame: pd.DataFrame) -> list[dict[str, Any]]:
        rows = frame.loc[frame["AnalysisScope"] == "individual_tag_as_grouping"]
        return [
            {
                "label": _text(row.GroupOrFamily),
                "pathway_count": int(_number(row.PathwayCount)),
            }
            for row in rows.sort_values("PathwayCount", ascending=False).itertuples()
        ]

    coverage = frames["metadata_coverage"]
    coverage_rows = [
        {
            "field": _text(row.field),
            "populated": int(_number(row.pathways_populated)),
            "missing": int(_number(row.pathways_missing)),
            "coverage_percentage": round(_number(row.coverage_percentage), 1),
            "distinct_values": int(_number(row.distinct_values)),
            "can_separate": bool(row.usable_as_grouping),
        }
        for row in coverage.itertuples()
    ]

    return {
        "evidence_class": "measured",
        "source": [
            source["clinical_areas"],
            source["symptom_groups"],
            source["age_analysis"],
            source["trauma_analysis"],
            source["metadata_coverage"],
        ],
        "caveat": (
            "These are existing NHS classifications and possible grouping signals. "
            "None of them is automatically a Bayesian family: Phase 2 tests how well "
            "each one actually holds together."
        ),
        "clinical_areas": clinical_areas,
        "clinical_area_overlap": {
            "total_links": int(inventory.get("pathway_clinical_area_links", 0)),
            "note": (
                "A pathway can be listed under several clinical areas, so the area "
                "counts add up to more than the number of pathways. Clinical areas "
                "overlap; they are not a clean division of the estate."
            ),
        },
        "symptom_groups": symptom_groups,
        "age_bands": tag_counts(frames["age_analysis"]),
        "trauma": tag_counts(frames["trauma_analysis"]),
        "metadata_coverage": coverage_rows,
    }


def _phase1_tells_us(
    inventory: Mapping[str, float],
    graph: Mapping[str, float],
    frames: Mapping[str, pd.DataFrame],
) -> list[dict[str, str]]:
    """Plain-language summary cards, each tied to a figure elsewhere on the page."""
    bands = frames["question_reuse_bands"]
    total = int(bands["question_count"].sum())
    single = int(
        bands.loc[bands["band"].astype(str).str.startswith("1 pathway"), "question_count"].sum()
    )
    shared_pct = round(100.0 * (total - single) / total, 0) if total else 0

    summary = frames["complexity_summary"]
    question_row = summary.loc[summary["metric"] == "QuestionCount"]
    median = int(_number(question_row.iloc[0]["median"])) if not question_row.empty else 0
    largest = int(_number(question_row.iloc[0]["max"])) if not question_row.empty else 0

    return [
        {
            "title": "The estate is connected, not a set of independent pathways",
            "text": (
                f"There are {int(graph.get('edge_count', 0)):,} distinct ways one "
                f"pathway can hand over to another, and "
                f"{int(graph.get('largest_weakly_connected_component', 0)):,} of the "
                f"{int(inventory.get('pathways_active', 0)):,} active pathways sit in a "
                "single connected group. Any design has to account for that."
            ),
        },
        {
            "title": "Pathways vary widely in size",
            "text": (
                f"The typical pathway asks {median} questions, but the largest asks "
                f"{largest}. A design sized for the typical case would not fit the "
                "largest."
            ),
        },
        {
            "title": "Most question content is shared between pathways",
            "text": (
                f"About {shared_pct:.0f}% of the questions referenced by triage logic "
                "are used by more than one pathway. The same clinical question appears "
                "in many places."
            ),
        },
        {
            "title": "Several grouping systems already exist, and they overlap",
            "text": (
                f"{int(inventory.get('clinical_areas_total', 0))} clinical areas and "
                f"{int(inventory.get('symptom_groups_total', 0))} symptom groups are "
                "already recorded, alongside age and trauma tags. A pathway can belong "
                "to several at once, so none of them divides the estate cleanly."
            ),
        },
        {
            "title": "The data is good enough to build evidence on",
            "text": (
                "Every recorded handover instruction resolved to a real target except "
                "four, and all internal navigation steps resolved. Known gaps are "
                "reported rather than filled in."
            ),
        },
    ]


def _phase1_conclusion(
    inventory: Mapping[str, float],
    graph: Mapping[str, float],
    frames: Mapping[str, pd.DataFrame],
) -> dict[str, Any]:
    """Synthesis of the Phase 1 evidence, without choosing an architecture."""
    bands = frames["question_reuse_bands"]
    total = int(bands["question_count"].sum())
    single = int(
        bands.loc[bands["band"].astype(str).str.startswith("1 pathway"), "question_count"].sum()
    )
    shared_pct = round(100.0 * (total - single) / total, 0) if total else 0

    summary = frames["complexity_summary"]
    question_row = summary.loc[summary["metric"] == "QuestionCount"]
    median = int(_number(question_row.iloc[0]["median"])) if not question_row.empty else 0
    largest = int(_number(question_row.iloc[0]["max"])) if not question_row.empty else 0

    return {
        "evidence_class": "derived",
        "title": "NHS Pathways is a connected, shared clinical decision estate",
        "paragraphs": [
            (
                "The evidence does not support treating the "
                f"{int(inventory.get('pathways_active', 0)):,} "
                "active pathways as independent units. Most sit within one connected "
                "structure,"
                f"there are {int(graph.get('edge_count', 0)):,} distinct "
                "pathway-to-pathway links, "
                f"and about {shared_pct:.0f}% of referenced questions are reused "
                "across more than one pathway."
            ),
            (
                "Pathway size also varies materially: the typical pathway contains "
                f"{median} questions "
                f"while the largest contains {largest}. Existing classifications "
                "such as Symptom Groups, "
                "Clinical Areas, age and trauma provide useful structure, but overlap and do "
                "not by"
                "themselves create clean computational boundaries."
            ),
            (
                "Phase 1 therefore provides a reliable structural basis for the next "
                "question: whether"
                "coherent candidate Bayesian families can be derived from this connected "
                "estate. It does"
                "not determine whether a federated architecture is preferable."
            ),
        ],
        "next_question": "If the architecture were federated, where should the model "
        "boundaries sit?",
    }


def _phase1_methodology() -> list[dict[str, str]]:
    """Technical definitions, shown behind progressive disclosure."""
    return [
        {
            "term": "Active",
            "definition": (
                "A pathway, question or disposition not archived and not flagged for "
                "deletion. Applied only to the tables that record both flags."
            ),
        },
        {
            "term": "Question count",
            "definition": (
                "Distinct answerable triage questions referenced by a pathway's logic. "
                "The same column in the source data also references care-advice and "
                "disposition steps; those are counted separately, because only "
                "answerable questions could become variables in a model."
            ),
        },
        {
            "term": "Pathway-to-pathway link",
            "definition": (
                "A transfer instruction of the form <pathway>.<step> whose pathway part "
                "matches a real pathway, aggregated to one link per source, target and "
                "direction."
            ),
        },
        {
            "term": "Handover instruction",
            "definition": (
                "One transfer value in the source data. A single answer can carry up to "
                "four, one per skillset branch, so instructions outnumber links."
            ),
        },
        {
            "term": "Connected group",
            "definition": (
                "A set of pathways reachable from one another by following handovers in "
                "either direction. Formally a weakly connected component."
            ),
        },
        {
            "term": "Internal link percentage",
            "definition": (
                "For a group of pathways: handovers that stay inside the group as a "
                "share of all handovers leaving the group's pathways. 100% means the "
                "group is self-contained."
            ),
        },
        {
            "term": "Excluded from the link count",
            "definition": (
                "Navigation codes that carry no destination in the data are treated as "
                "control behaviour, not handovers. If any of them does imply a "
                "relationship recorded elsewhere, the connectivity figures understate "
                "it."
            ),
        },
    ]


# ======================================================================================
# Phase 2 payload
# ======================================================================================
PHASE2_KEYS: Final[tuple[str, ...]] = (
    "meta",
    "executive_summary",
    "configuration",
    "evidence_sources",
    "strategy_comparison",
    "families",
    "overlap",
    "boundaries",
    "shared_core",
    "routing",
    "merge_candidates",
    "split_candidates",
    "clinical_review",
    "tells_us",
    "conclusion",
    "does_not_tell_us",
    "next_phase",
    "methodology",
)


def build_phase2(paths: Paths) -> dict[str, Any]:
    """Build the Phase 2 presentation payload."""
    LOGGER.info("--- Building Phase 2 report data ---")
    frames = load_all(PHASE2_ARTEFACTS, paths)
    source = {name: artefact.relative_path for name, artefact in PHASE2_ARTEFACTS.items()}

    configuration = _lookup_text(frames["configuration"], "setting", "value")
    primary_strategy = configuration.get(
        "presentation.primary_candidate_strategy", "hybrid_a"
    )

    families = frames["families"]
    payload: dict[str, Any] = {
        "meta": _meta(
            "2",
            "Discovering Candidate Bayesian Families",
            "If federation were chosen, what candidate Bayesian families might exist?",
        ),
        "executive_summary": _phase2_executive_summary(frames, primary_strategy),
        "configuration": {
            "evidence_class": "derived",
            "source": [source["configuration"]],
            "primary_strategy": primary_strategy,
            "settings": [
                {"setting": key, "value": value}
                for key, value in sorted(configuration.items())
            ],
            "note": (
                "Every threshold and weight used by Phase 2 is configurable and is "
                "listed here. None is clinically validated; they are stated so the "
                "evidence can be reproduced or re-run differently."
            ),
        },
        "evidence_sources": _phase2_evidence_sources(frames, primary_strategy, source),
        "strategy_comparison": _phase2_strategy_comparison(frames, primary_strategy, source),
        "families": _phase2_families(families, source),
        "overlap": _phase2_overlap(frames, families, primary_strategy, source),
        "boundaries": _phase2_boundaries(frames, primary_strategy, source),
        "shared_core": _phase2_shared_core(frames, configuration, source),
        "routing": _phase2_routing(frames, primary_strategy, source),
        "merge_candidates": _phase2_merge(frames, families, primary_strategy, source),
        "split_candidates": _phase2_split(frames, families, primary_strategy, source),
        "clinical_review": _phase2_clinical_review(frames, primary_strategy, source),
        "tells_us": _phase2_tells_us(frames, primary_strategy),
        "conclusion": _phase2_conclusion(frames, primary_strategy),
        "does_not_tell_us": [
            "Whether a federated design is preferable to a single model. Phase 2 shows "
            "where boundaries could be drawn, not whether they should be.",
            "How many variables or relationships a model would contain.",
            "How large the probability tables would be, or how they would grow.",
            "How much memory a model would need.",
            "How quickly it would answer a question.",
            "What infrastructure would be required to run it.",
            "What it would cost, in total or per assessment.",
            "Which candidate families are clinically correct. Every one of them needs "
            "clinical review, without exception.",
        ],
        "next_phase": _phase2_next_phase(),
        "methodology": _phase2_methodology(configuration),
    }
    validate_payload(payload, PHASE2_KEYS, "phase2")
    return payload


def _phase2_executive_summary(
    frames: Mapping[str, pd.DataFrame], primary_strategy: str
) -> dict[str, Any]:
    """Short non-technical summary for senior readers."""
    families = frames["families"]
    boundary = frames["boundary_summary"]
    boundary_row = boundary.loc[boundary["strategy"] == primary_strategy]
    routing = frames["routing_summary"]
    routing_row = routing.loc[routing["strategy"] == primary_strategy]
    shared = frames["shared_feature_summary"]

    family_count = int(len(families))
    largest = int(families["PathwayCount"].max()) if family_count else 0
    median = int(families["PathwayCount"].median()) if family_count else 0
    boundary_pct = (
        _number(boundary_row.iloc[0]["BoundaryPathwayPercentage"])
        if not boundary_row.empty
        else 0.0
    )
    ambiguous_pct = (
        _number(routing_row.iloc[0]["PercentageHighAmbiguity"])
        if not routing_row.empty
        else 0.0
    )
    shared_candidates = int(shared["SharedCoreCandidates"].sum())

    return {
        "evidence_class": "candidate",
        "headline": "Repeatable candidate families emerge, but they are not independent "
        "islands.",
        "summary": (
            "Phase 2 tested existing NHS groupings, graph structure and shared clinical "
            "features"
            "independently and in combination. The results provide enough evidence to carry a "
            "federated or hierarchical option into Phase 3, but not enough to treat the "
            "proposed"
            "families as final clinical boundaries."
        ),
        "key_points": [
            (
                f"The presented candidate set contains {family_count} families; the "
                "typical family "
                f"contains {median} pathways and the largest contains {largest}."
            ),
            (
                f"About {boundary_pct:.0f}% of pathways cross a proposed family "
                "boundary, showing "
                "that the families remain strongly connected to one another."
            ),
            (
                f"{shared_candidates:,} features are shared broadly across candidate "
                "families, so "
                "a separated design would need to decide what is shared and what is duplicated."
            ),
            (
                f"{ambiguous_pct:.0f}% of pathways remain highly ambiguous on "
                "structural evidence "
                "alone, and all proposed family boundaries still require clinical review."
            ),
        ],
        "bottom_line": (
            "Federation is credible enough to compare in Phase 3, but any viable federated "
            "design"
            "must account for cross-family reasoning, shared evidence and clinical validation."
        ),
    }


def _lookup_text(frame: pd.DataFrame, key_column: str, value_column: str) -> dict[str, str]:
    """Turn a two-column long-format table into a string mapping."""
    return {
        _text(row[key_column]): _text(row[value_column])
        for _, row in frame.iterrows()
    }


#: Plain-English labels for the discovery strategies. Keeping this mapping here rather
#: than in the page means the label and the underlying strategy name cannot drift apart.
STRATEGY_LABELS: Final[dict[str, str]] = {
    "native_symptom_group": "NHS symptom groups",
    "native_clinical_area": "NHS clinical areas",
    "native_area_group": "NHS area groups",
    "native_trauma": "Trauma tags",
    "native_age_group": "Age bands",
    "native_gender": "Gender tags",
    "native_module": "Module (empty in this dataset)",
    "graph_louvain": "Connection clusters (Louvain)",
    "graph_networkx_louvain": "Connection clusters (Louvain, second implementation)",
    "graph_leiden": "Connection clusters (Leiden)",
    "graph_greedy_modularity": "Connection clusters (greedy)",
    "graph_label_propagation": "Connection clusters (label propagation)",
    "graph_strongly_connected": "Mutually reachable groups",
    "hybrid_a": "Hybrid A — connections checked against clinical features",
    "hybrid_b": "Hybrid B — NHS groups split where connections are weak",
    "hybrid_c": "Hybrid C — combined similarity clustering",
}

BASIS_LABELS: Final[dict[str, str]] = {
    "nhs_native": "NHS classification",
    "graph_derived": "Connection structure",
    "hybrid": "Combined evidence",
}


def _strategy_label(strategy: str) -> str:
    """Return a plain-English label for a strategy name."""
    return STRATEGY_LABELS.get(strategy, strategy.replace("_", " "))


def _phase2_evidence_sources(
    frames: Mapping[str, pd.DataFrame],
    primary_strategy: str,
    source: Mapping[str, str],
) -> dict[str, Any]:
    """The three independent evidence sources, summarised."""
    comparison = frames["strategy_comparison"]
    native = comparison.loc[comparison["FamilyBasis"] == "nhs_native"]

    methods = frames["community_methods"]
    available = methods.loc[methods["available"].astype(str).str.lower().isin(
        {"true", "1", "yes"}
    )]

    similarity = frames["similarity_summary"]
    dimension_labels = {
        "question": "Shared questions",
        "symptom_discriminator": "Shared symptom discriminators",
        "snomed": "Shared SNOMED concepts",
        "disposition": "Shared outcomes",
        "clinical_area": "Shared clinical areas",
        "graph_relationship": "Direct connections",
    }

    return {
        "evidence_class": "derived",
        "source": [
            source["strategy_comparison"],
            source["community_methods"],
            source["similarity_summary"],
        ],
        "warning": "A graph community is a data cluster, not a clinically approved family.",
        "native": {
            "label": "NHS classification",
            "description": (
                "Groupings that already exist in the Pathways data: symptom groups, "
                "clinical areas, area groups, age bands and trauma tags."
            ),
            "groupings": [
                {
                    "strategy": _text(row.strategy),
                    "label": _strategy_label(_text(row.strategy)),
                    "family_count": int(_number(row.FamilyCount)),
                    "median_size": _optional_number(row.MedianFamilySize),
                    "max_size": int(_number(row.MaxFamilySize)),
                    "internal_link_percentage": _optional_number(
                        row.MedianInternalEdgePercentage
                    ),
                }
                for row in native.sort_values("FamilyCount", ascending=False).itertuples()
            ],
        },
        "structural": {
            "label": "Connection structure",
            "description": (
                "Which pathways hand over to each other most. Several clustering "
                "methods were run independently, so agreement between them is itself "
                "evidence rather than one algorithm's opinion."
            ),
            "methods": [
                {
                    "method": _text(row.method),
                    "label": _strategy_label(f"graph_{_text(row.method)}"),
                    "clusters_found": int(_number(row.community_count)),
                    "largest_cluster": int(_number(row.largest_community_size)),
                    "agreement_with_primary": _optional_number(
                        row.adjusted_rand_index_vs_primary
                    ),
                    "is_primary": bool(row.is_primary_method),
                }
                for row in available.itertuples()
            ],
            "agreement_note": (
                "Agreement is measured on a scale where 1.0 means the two methods "
                "produced the same grouping and 0.0 means no more agreement than "
                "chance."
            ),
        },
        "features": {
            "label": "Shared clinical features",
            "description": (
                "Whether two pathways ask the same questions, use the same symptom "
                "discriminators or SNOMED concepts, or lead to the same outcomes."
            ),
            "dimensions": [
                {
                    "dimension": _text(row.dimension),
                    "label": dimension_labels.get(
                        _text(row.dimension), _text(row.dimension)
                    ),
                    "pathways": int(_number(row.pathways_with_any_feature)),
                    "pairs_with_overlap": int(_number(row.overlapping_pairs)),
                    "possible_pairs": int(_number(row.possible_pairs)),
                    "percentage_of_pairs": round(
                        _number(row.percentage_of_pairs_overlapping), 1
                    ),
                    "median_similarity": _optional_number(row.median_jaccard),
                }
                for row in similarity.itertuples()
            ],
        },
        "primary_strategy": primary_strategy,
        "primary_strategy_label": _strategy_label(primary_strategy),
    }


def _phase2_strategy_comparison(
    frames: Mapping[str, pd.DataFrame],
    primary_strategy: str,
    source: Mapping[str, str],
) -> dict[str, Any]:
    """Every discovery strategy side by side. No strategy is marked as best."""
    comparison = frames["strategy_comparison"]
    rows = [
        {
            "strategy": _text(row.strategy),
            "label": _strategy_label(_text(row.strategy)),
            "basis": _text(row.FamilyBasis),
            "basis_label": BASIS_LABELS.get(_text(row.FamilyBasis), _text(row.FamilyBasis)),
            "is_primary": _text(row.strategy) == primary_strategy,
            "overlapping": bool(row.IsOverlapping),
            "family_count": int(_number(row.FamilyCount)),
            "median_size": _optional_number(row.MedianFamilySize),
            "max_size": int(_number(row.MaxFamilySize)),
            "internal_link_percentage": _optional_number(row.MedianInternalEdgePercentage),
            "external_link_percentage": _optional_number(row.MedianExternalEdgePercentage),
            "boundary_pathway_percentage": _optional_number(
                row.MedianBoundaryPathwayPercentage
            ),
        }
        for row in comparison.sort_values(
            ["FamilyBasis", "FamilyCount"], ascending=[True, False]
        ).itertuples()
    ]
    return {
        "evidence_class": "candidate",
        "source": [source["strategy_comparison"]],
        "rows": rows,
        "no_winner_note": (
            "No strategy is preferred here. NHS classifications are immediately "
            "recognisable to clinicians but often hold together poorly in terms of "
            "connections; connection clusters hold together well by construction but "
            "may not match anything clinically meaningful. The hybrids sit between the "
            "two and inherit both caveats."
        ),
        "definitions": {
            "internal_link_percentage": (
                "Of all the handovers leaving a family's pathways, the share that stay "
                "inside that family. Higher means the family is more self-contained."
            ),
            "boundary_pathway_percentage": (
                "The share of a family's pathways that hand over to, or receive "
                "handovers from, a pathway in another family."
            ),
        },
    }


#: Tooltip text for every metric the family explorer shows. Held next to the payload
#: builder rather than in the page so that a metric cannot appear in the explorer
#: without an explanation attached to it.
FAMILY_METRIC_TOOLTIPS: Final[dict[str, str]] = {
    "pathway_count": (
        "How many pathways this candidate family contains. A pathway is one clinical "
        "assessment flow."
    ),
    "clinical_areas": (
        "The clinical areas most of this family's pathways are listed under. Pathways "
        "can belong to several areas, so these are the most common rather than the only "
        "ones."
    ),
    "symptom_groups": (
        "The NHS symptom groups most common among this family's pathways."
    ),
    "unique_questions": (
        "Distinct questions the family's pathways can ask between them. The same "
        "question can be used by several pathways and is counted once."
    ),
    "unique_discriminators": (
        "Distinct symptom discriminators reachable from this family. Discriminators are "
        "the clinical factors that separate more urgent presentations from less urgent "
        "ones."
    ),
    "unique_snomed": (
        "Distinct SNOMED clinical concepts recorded against answers in this family. "
        "SNOMED coverage in this dataset is sparse, so this is a partial view."
    ),
    "unique_dispositions": (
        "Distinct outcomes this family can reach, such as an ambulance response or a "
        "referral within a stated time."
    ),
    "internal_link_percentage": (
        "Of all the handovers leaving this family's pathways, the share that stay inside "
        "the family. Higher means the family is more self-contained. Shown as 'not "
        "measurable' where the family's pathways have no handovers at all."
    ),
    "external_link_percentage": (
        "The remainder: handovers that cross into another family."
    ),
    "boundary_pathway_count": (
        "Pathways in this family that hand over to, or receive handovers from, a pathway "
        "in a different family."
    ),
    "cross_family_hub_count": (
        "Pathways that connect several other families at once and sit on many of the "
        "routes through the estate. A structural description, not a clinical judgement."
    ),
    "overlapping_families": (
        "Other candidate families this one shares a substantial amount of clinical "
        "vocabulary with. Overlap is a prompt for review, not a reason to combine them."
    ),
    "shared_core_dependencies": (
        "How many of this family's features are also used by several other families. "
        "These are the things that would need either sharing or duplicating if the "
        "families were separated."
    ),
    "cohesion": (
        "A plain summary of how well the family holds together on two independent "
        "measures: how much its pathways hand over to each other, and how much clinical "
        "vocabulary they share. 'High' means both agree; 'low' means neither is strong. "
        "It says nothing about whether the family is clinically correct."
    ),
    "name_basis": (
        "Where the family's name came from. A family is only named after an NHS "
        "classification when one value covers at least half its pathways; otherwise it "
        "keeps a neutral name, because inventing a clinical-sounding name would imply a "
        "claim the evidence does not support."
    ),
}


def _phase2_families(
    families: pd.DataFrame, source: Mapping[str, str]
) -> dict[str, Any]:
    """The candidate families presented for review.

    Symptom-group and clinical-area names are included because the explorer is
    unusable without them. No pathway titles, question text or feature descriptions
    are included.
    """
    rows = [
        {
            "family_id": _text(row.FamilyId),
            "name": _text(row.FamilyName),
            "name_basis": _text(row.FamilyNameBasis),
            "is_named_from_metadata": _text(row.FamilyNameBasis) != "neutral",
            "basis": _text(row.FamilyBasis),
            "basis_label": BASIS_LABELS.get(_text(row.FamilyBasis), _text(row.FamilyBasis)),
            "strategy": _text(row.Strategy),
            "strategy_label": _strategy_label(_text(row.Strategy)),
            "pathway_count": int(_number(row.PathwayCount)),
            "clinical_areas": _pipe_first(row.PrimaryClinicalAreas),
            "symptom_groups": _pipe_first(row.PrimarySymptomGroups),
            "unique_questions": int(_number(row.UniqueQuestions)),
            "unique_discriminators": int(_number(row.UniqueSDs)),
            "unique_snomed": int(_number(row.UniqueSnomed)),
            "unique_dispositions": int(_number(row.UniqueDispositions)),
            "internal_link_percentage": _optional_number(row.InternalEdgePercentage),
            "external_link_percentage": _optional_number(row.ExternalEdgePercentage),
            "boundary_pathway_count": int(_number(row.BoundaryPathwayCount)),
            "cross_family_hub_count": int(_number(row.CrossFamilyHubCount)),
            "overlapping_families": _pipe_first(row.StrongOverlapFamilies, limit=4),
            "shared_core_dependencies": int(_number(row.SharedCoreDependencyCount)),
            "cohesion": _text(row.ConfidenceInStructuralCohesion),
            "cohesion_band": _text(row.ConfidenceInStructuralCohesion).split(" ")[0],
            "clinical_review_required": bool(row.ClinicalReviewRequired),
            "notes": _text(row.Notes),
        }
        for row in families.itertuples()
    ]
    return {
        "evidence_class": "candidate",
        "source": [source["families"]],
        "rows": rows,
        "metric_tooltips": FAMILY_METRIC_TOOLTIPS,
        "review_note": (
            "Every family here requires clinical review. None is confirmed, and the "
            "order they appear in carries no ranking."
        ),
    }


def _phase2_overlap(
    frames: Mapping[str, pd.DataFrame],
    families: pd.DataFrame,
    primary_strategy: str,
    source: Mapping[str, str],
) -> dict[str, Any]:
    """Family-by-family overlap matrices for the four presentable measures.

    Restricted to the largest families with more than one pathway: single-pathway
    families produce all-zero rows, and a pair of them scores a perfect similarity from
    three shared questions, which is arithmetically true and analytically meaningless.
    """
    overlap = frames["overlap"]
    subset = overlap.loc[overlap["strategy"] == primary_strategy]
    if subset.empty:
        raise ReportBuildError(
            f"family_overlap_matrix.csv has no rows for the primary strategy "
            f"{primary_strategy!r}, so the overlap heatmaps cannot be built."
        )

    eligible = families.loc[families["PathwayCount"] >= 2].nlargest(
        HEATMAP_FAMILY_LIMIT, "PathwayCount"
    )
    if eligible.empty:
        eligible = families.nlargest(HEATMAP_FAMILY_LIMIT, "PathwayCount")
    order = [_text(value) for value in eligible["FamilyId"]]
    index = {family_id: position for position, family_id in enumerate(order)}
    size = len(order)

    measures = {
        "transitions": ("TransitionsAtoB", "TransitionsBtoA"),
        "discriminators": ("SdJaccard", None),
        "questions": ("QuestionJaccard", None),
        "snomed": ("SnomedJaccard", None),
    }
    matrices = {name: [[0.0] * size for _ in range(size)] for name in measures}

    for row in subset.itertuples():
        left = index.get(_text(row.FamilyA))
        right = index.get(_text(row.FamilyB))
        if left is None or right is None:
            continue
        for name, (forward, reverse) in measures.items():
            value = _number(getattr(row, forward))
            if reverse is not None:
                value += _number(getattr(row, reverse))
            value = round(value, 4)
            matrices[name][left][right] = value
            matrices[name][right][left] = value

    label_lookup = dict(zip(families["FamilyId"].map(_text), families["FamilyName"].map(_text)))
    count_lookup = dict(
        zip(families["FamilyId"].map(_text), families["PathwayCount"].map(int))
    )

    return {
        "evidence_class": "candidate",
        "source": [source["overlap"]],
        "family_ids": order,
        "family_labels": [label_lookup.get(family_id, family_id) for family_id in order],
        "family_pathway_counts": [count_lookup.get(family_id, 0) for family_id in order],
        "matrices": matrices,
        # Explicit order: the JSON writer sorts keys, so the dict order cannot be
        # relied on to put the default measure first in the page's control row.
        "measure_order": ["transitions", "discriminators", "questions", "snomed"],
        "default_measure": "transitions",
        "measure_labels": {
            "transitions": "Handovers between the two families",
            "discriminators": "Shared symptom discriminators",
            "questions": "Shared questions",
            "snomed": "Shared SNOMED concepts",
        },
        "measure_descriptions": {
            "transitions": (
                "How many recorded handover instructions run between the two families, "
                "in either direction. The most directly understandable measure: it "
                "counts something the data records rather than a calculated similarity."
            ),
            "discriminators": (
                "How much of the two families' symptom-discriminator vocabulary is the "
                "same, on a 0 to 1 scale. 0 means nothing in common, 1 means identical."
            ),
            "questions": (
                "How much of the two families' question sets is the same, on a 0 to 1 "
                "scale."
            ),
            "snomed": (
                "How much of the two families' SNOMED concept sets is the same, on a 0 "
                "to 1 scale. SNOMED coverage in this dataset is sparse, so this is the "
                "thinnest of the three similarity measures."
            ),
        },
        "families_shown": size,
        "families_total": int(len(families)),
        "excluded_single_pathway": int((families["PathwayCount"] < 2).sum()),
        "interpretation_note": (
            "High overlap does not automatically mean two families should be merged. It "
            "identifies an area requiring further clinical and architectural "
            "consideration."
        ),
    }


def _phase2_boundaries(
    frames: Mapping[str, pd.DataFrame],
    primary_strategy: str,
    source: Mapping[str, str],
) -> dict[str, Any]:
    """Aggregate counts of how pathways sit relative to their family boundary."""
    summary = frames["boundary_summary"]
    subset = summary.loc[summary["strategy"] == primary_strategy]
    if subset.empty:
        raise ReportBuildError(
            f"boundary_pathway_summary.csv has no rows for {primary_strategy!r}."
        )
    row = subset.iloc[0]
    total = int(_number(row["PathwaysClassified"]))

    def bucket(key: str, label: str, explanation: str) -> dict[str, Any]:
        count = int(_number(row.get(f"count_{key}", 0)))
        return {
            "key": key,
            "label": label,
            "count": count,
            "percentage": round(100.0 * count / total, 1) if total else 0.0,
            "explanation": explanation,
        }

    return {
        "evidence_class": "candidate",
        "source": [source["boundary_summary"]],
        "pathways_classified": total,
        "boundary_pathway_count": int(_number(row["BoundaryPathwayCount"])),
        "boundary_pathway_percentage": round(
            _number(row["BoundaryPathwayPercentage"]), 1
        ),
        "buckets": [
            bucket(
                "internal_pathway",
                "Sits inside one family",
                "Every pathway it hands over to, and receives handovers from, is in the "
                "same family.",
            ),
            bucket(
                "weak_boundary_pathway",
                "Touches one other family",
                "Has a small number of handovers reaching outside its family.",
            ),
            bucket(
                "strong_boundary_pathway",
                "Sits on a boundary",
                "Has several handovers reaching outside its family, or reaches several "
                "other families.",
            ),
            bucket(
                "cross_family_hub",
                "Connects several families",
                "Reaches several other families and sits on many of the routes through "
                "the estate.",
            ),
        ],
        "classification_note": (
            "This classification is structural only. It describes how a pathway is "
            "wired, and makes no claim that a pathway is clinically central, "
            "safety-critical or wrongly placed."
        ),
    }


def _phase2_shared_core(
    frames: Mapping[str, pd.DataFrame],
    configuration: Mapping[str, str],
    source: Mapping[str, str],
) -> dict[str, Any]:
    """Features used across many candidate families."""
    summary = frames["shared_feature_summary"]
    by_type = [
        {
            "feature_type": _text(row.FeatureType),
            "label": _text(row.FeatureTypeLabel),
            "total": int(_number(row.FeaturesTotal)),
            "bands": [
                {"band": "Used by 1 family", "count": int(_number(row.FamilySpecific))},
                {"band": "2 families", "count": int(_number(row.SharedBy2Families))},
                {"band": "3-5 families", "count": int(_number(row.SharedBy3To5Families))},
                {"band": "6 or more", "count": int(_number(row.BroadlyShared))},
            ],
            "shared_core_candidates": int(_number(row.SharedCoreCandidates)),
            "max_families": int(_number(row.MaxFamilyCount)),
            "duplication_if_separated": int(_number(row.TotalDuplicationIfFederated)),
        }
        for row in summary.itertuples()
    ]
    return {
        "evidence_class": "candidate",
        "source": [source["shared_feature_summary"]],
        "by_type": by_type,
        "totals": {
            "shared_core_candidates": sum(
                item["shared_core_candidates"] for item in by_type
            ),
            "duplication_if_separated": sum(
                item["duplication_if_separated"] for item in by_type
            ),
            "threshold_families": int(
                _number(configuration.get("shared_core.minimum_family_count", 5))
            ),
        },
        "definitions": {
            "duplication_if_separated": (
                "If every family held its own copy of each shared feature, this is how "
                "many extra copies would exist. It is a count of duplication in the "
                "structure, not an estimate of size, memory or cost."
            )
        },
        "interpretation_note": (
            "This does not conclude that a separate shared model is required. A feature "
            "used everywhere might be one clinical concept genuinely used everywhere, "
            "several different concepts that happen to share wording, or a by-product of "
            "how the pathways were written. Structure alone cannot tell those apart."
        ),
    }


def _phase2_routing(
    frames: Mapping[str, pd.DataFrame],
    primary_strategy: str,
    source: Mapping[str, str],
) -> dict[str, Any]:
    """How cleanly each pathway associates with a single candidate family."""
    summary = frames["routing_summary"]
    subset = summary.loc[summary["strategy"] == primary_strategy]
    if subset.empty:
        raise ReportBuildError(
            f"pathway_family_routing_summary.csv has no rows for {primary_strategy!r}."
        )
    row = subset.iloc[0]

    return {
        "evidence_class": "candidate",
        "source": [source["routing_summary"]],
        "pathways_scored": int(_number(row["PathwaysScored"])),
        "association": [
            {
                "key": "strong",
                "label": "Clearly belongs to one family",
                "percentage": round(
                    _number(row["PercentageStrongSingleFamilyAssociation"]), 1
                ),
                "explanation": (
                    "The best-matching family is well ahead of the next best, so the "
                    "pathway's placement is clear from its structure."
                ),
            },
            {
                "key": "moderate",
                "label": "Somewhat ambiguous",
                "percentage": round(_number(row["PercentageModerateAmbiguity"]), 1),
                "explanation": (
                    "A second family is a reasonable match, so the placement depends on "
                    "judgement."
                ),
            },
            {
                "key": "high",
                "label": "Highly ambiguous",
                "percentage": round(_number(row["PercentageHighAmbiguity"]), 1),
                "explanation": (
                    "Two or more families match almost equally well. Structure alone "
                    "cannot place these pathways."
                ),
            },
        ],
        "plausible_families": [
            {
                "label": "One plausible family",
                "percentage": round(_number(row["PercentageOnePlausibleFamily"]), 1),
            },
            {
                "label": "Two plausible families",
                "percentage": round(_number(row["PercentageTwoPlausibleFamilies"]), 1),
            },
            {
                "label": "Three or more",
                "percentage": round(
                    _number(row["PercentageThreeOrMorePlausibleFamilies"]), 1
                ),
            },
        ],
        "why_it_matters": (
            "If separate models were used, something would have to decide which model "
            "handles an incoming case. This measures how far that decision can be made "
            "from structure alone. It does not design that mechanism, which is Phase 3 "
            "work."
        ),
        "optimistic_bound_note": (
            "These figures are measured with the whole pathway known. A live system "
            "would have to decide from partial answers, which is harder, so treat this "
            "as the best case rather than the expected case."
        ),
    }


def _phase2_merge(
    frames: Mapping[str, pd.DataFrame],
    families: pd.DataFrame,
    primary_strategy: str,
    source: Mapping[str, str],
) -> dict[str, Any]:
    """The strongest merge candidates, with before and after evidence."""
    merges = frames["merge_candidates"]
    subset = merges.loc[merges["strategy"] == primary_strategy]
    names = dict(zip(families["FamilyId"].map(_text), families["FamilyName"].map(_text)))

    # Ordered by the smaller family's size: a pair of one-pathway families is
    # arithmetically a strong overlap and analytically uninteresting.
    top = subset.nlargest(MERGE_SPLIT_LIMIT, "SmallerFamilyPathwayCount")
    rows = [
        {
            "family_a": _text(row.FamilyA),
            "family_b": _text(row.FamilyB),
            "family_a_name": names.get(_text(row.FamilyA), _text(row.FamilyA)),
            "family_b_name": names.get(_text(row.FamilyB), _text(row.FamilyB)),
            "why_flagged": _text(row.OverlapDriver),
            "pathways_a": int(_number(row.PathwayCountBeforeA)),
            "pathways_b": int(_number(row.PathwayCountBeforeB)),
            "pathways_after": int(_number(row.PathwayCountAfterMerge)),
            "internal_link_before": _optional_number(
                row.InternalEdgePercentageBeforeWeighted
            ),
            "internal_link_after": _optional_number(row.InternalEdgePercentageAfterMerge),
            "clinical_similarity_before": _optional_number(
                row.MeanPairwiseSdJaccardBeforeWeighted
            ),
            "clinical_similarity_after": _optional_number(
                row.MeanPairwiseSdJaccardAfterMerge
            ),
            "clinical_similarity_change": _optional_number(row.MeanPairwiseSdJaccardDelta),
            "verdict": _text(row.StructuralVerdict),
        }
        for row in top.itertuples()
    ]
    improving = int((subset["MeanPairwiseSdJaccardDelta"] > 0).sum())
    return {
        "evidence_class": "candidate",
        "source": [source["merge_candidates"]],
        "tested": int(len(subset)),
        "improving_clinical_similarity": improving,
        "rows": rows,
        "no_recommendation_note": (
            "No merge is proposed. These are before-and-after measurements for review."
        ),
        "mechanical_caveat": (
            "Combining two families always increases the share of handovers that stay "
            "inside the result, because handovers that used to cross the boundary now "
            "sit within it. That measure therefore cannot tell a good merge from a "
            "pointless one. The measure that can is clinical similarity, which falls "
            "when a merge combines pathways that connect to each other without being "
            "clinically alike."
        ),
    }


def _phase2_split(
    frames: Mapping[str, pd.DataFrame],
    families: pd.DataFrame,
    primary_strategy: str,
    source: Mapping[str, str],
) -> dict[str, Any]:
    """The strongest split candidates, with before and after evidence."""
    splits = frames["split_candidates"]
    subset = splits.loc[splits["strategy"] == primary_strategy]
    names = dict(zip(families["FamilyId"].map(_text), families["FamilyName"].map(_text)))
    top = subset.nlargest(MERGE_SPLIT_LIMIT, "PathwayCountBefore")

    method_labels = {
        "graph_subcommunity": "By how the pathways connect to each other",
        "dominant_symptom_group": "By NHS symptom group",
    }
    rows = [
        {
            "family_id": _text(row.FamilyId),
            "family_name": names.get(_text(row.FamilyId), _text(row.FamilyId)),
            "method": _text(row.SplitMethod),
            "method_label": method_labels.get(
                _text(row.SplitMethod), _text(row.SplitMethod).replace("_", " ")
            ),
            "why_flagged": _text(row.SplitTriggers),
            "pathways_before": int(_number(row.PathwayCountBefore)),
            "parts": int(_number(row.PartCount)),
            "part_sizes": _text(row.PartSizes),
            "internal_link_before": _optional_number(row.InternalEdgePercentageBefore),
            "internal_link_after": _optional_number(row.InternalEdgePercentageAfterWeighted),
            "clinical_similarity_before": _optional_number(row.MeanPairwiseSdJaccardBefore),
            "clinical_similarity_after": _optional_number(
                row.MeanPairwiseSdJaccardAfterWeighted
            ),
            "clinical_similarity_change": _optional_number(row.MeanPairwiseSdJaccardDelta),
            "verdict": _text(row.StructuralVerdict),
        }
        for row in top.itertuples()
    ]
    return {
        "evidence_class": "candidate",
        "source": [source["split_candidates"]],
        "families_triggered": int(subset["FamilyId"].nunique()),
        "proposals_tested": int(len(subset)),
        "rows": rows,
        "no_recommendation_note": (
            "No split is proposed. These are before-and-after measurements for review."
        ),
        "mechanical_caveat": (
            "Dividing a family always reduces the share of handovers that stay inside "
            "each part, because handovers that used to be internal now cross a "
            "boundary. As with merges, the measure that carries real information is "
            "clinical similarity."
        ),
    }


def _phase2_clinical_review(
    frames: Mapping[str, pd.DataFrame],
    primary_strategy: str,
    source: Mapping[str, str],
) -> dict[str, Any]:
    """What clinical review is being asked to look at."""
    families = frames["families"]
    high_overlap = frames["high_overlap"]
    overlap_subset = high_overlap.loc[high_overlap["strategy"] == primary_strategy]
    substantial = overlap_subset.loc[overlap_subset["SmallerFamilyPathwayCount"] >= 5]
    boundary = frames["boundary_summary"]
    boundary_subset = boundary.loc[boundary["strategy"] == primary_strategy]
    shared = frames["shared_feature_summary"]

    neutral = int((families["FamilyNameBasis"] == "neutral").sum())
    return {
        "evidence_class": "candidate",
        "source": [
            source["families"],
            source["high_overlap"],
            source["boundary_summary"],
            source["shared_feature_summary"],
        ],
        "items": [
            {
                "label": "Candidate families needing review",
                "value": int(len(families)),
                "detail": (
                    f"{neutral} of them could not be given a name from existing NHS "
                    "classifications, which is where clinical judgement is most needed."
                ),
            },
            {
                "label": "Family pairs with substantial overlap",
                "value": int(len(substantial)),
                "detail": (
                    "Pairs where both families hold at least five pathways. For each: "
                    "one clinical area split by routing, or two areas sharing a "
                    "vocabulary?"
                ),
            },
            {
                "label": "Pathways sitting on a boundary",
                "value": (
                    int(_number(boundary_subset.iloc[0]["BoundaryPathwayCount"]))
                    if not boundary_subset.empty
                    else 0
                ),
                "detail": (
                    "Including "
                    + (
                        str(int(_number(boundary_subset.iloc[0]["count_cross_family_hub"])))
                        if not boundary_subset.empty
                        else "0"
                    )
                    + " that connect several families at once."
                ),
            },
            {
                "label": "Features used across many families",
                "value": int(shared["SharedCoreCandidates"].sum()),
                "detail": (
                    "Questions, discriminators, SNOMED concepts and outcomes that "
                    "appear in many candidate families at once."
                ),
            },
        ],
        "review_pack": "outputs/phase2/clinical_review_pack.md",
        "review_pack_note": (
            "A per-family review document is generated alongside this report. It lists "
            "representative pathways, dominant classifications and the specific "
            "questions being asked about each family."
        ),
        "questions": [
            "Is each candidate family recognisable as one clinical area?",
            "Where a family has no dominant NHS classification, is there a real "
            "clinical grouping the metadata does not capture?",
            "Where two families overlap strongly, are they one area or two?",
            "For the most widely shared features: one clinical concept, several "
            "concepts sharing wording, or an artefact of how pathways were written?",
            "Should paediatric pathways be separate families, variants within "
            "families, or handled by every family?",
            "Is trauma one family, several anatomical families, or a dimension that "
            "cuts across families?",
            "Is there any pair of families that must not be separated, because a "
            "clinically critical route runs between them?",
        ],
    }


def _phase2_tells_us(
    frames: Mapping[str, pd.DataFrame], primary_strategy: str
) -> list[dict[str, str]]:
    """Plain-language summary of what Phase 2 established."""
    families = frames["families"]
    comparison = frames["strategy_comparison"]
    routing = frames["routing_summary"]
    routing_row = routing.loc[routing["strategy"] == primary_strategy]
    boundary = frames["boundary_summary"]
    boundary_row = boundary.loc[boundary["strategy"] == primary_strategy]
    shared = frames["shared_feature_summary"]
    methods = frames["community_methods"]
    available = methods.loc[
        methods["available"].astype(str).str.lower().isin({"true", "1", "yes"})
        & ~methods["is_primary_method"].astype(bool)
    ]
    neutral = int((families["FamilyNameBasis"] == "neutral").sum())

    cards = [
        {
            "title": "Repeatable candidate groupings emerge from the data",
            "text": (
                f"{int(len(comparison))} different ways of grouping the estate were "
                f"tested. The set presented here holds {int(len(families))} candidate "
                f"families, the largest containing "
                f"{int(families['PathwayCount'].max())} pathways and the typical one "
                f"{int(families['PathwayCount'].median())}."
            ),
        },
        {
            "title": "Independent methods broadly agree on the structure",
            "text": (
                "Several clustering methods were run separately. Their agreement "
                + (
                    f"ranges from {available['adjusted_rand_index_vs_primary'].min():.2f} "
                    f"to {available['adjusted_rand_index_vs_primary'].max():.2f} "
                    if not available.empty
                    else ""
                )
                + "on a 0 to 1 scale, which means the grouping reflects the data rather "
                "than one algorithm's assumptions."
            ),
        },
        {
            "title": "Most candidate families do not match an existing NHS grouping",
            "text": (
                f"{neutral} of {int(len(families))} families had no dominant symptom "
                "group or clinical area, so they were deliberately left unnamed rather "
                "than given a clinical-sounding label the evidence does not support."
            ),
        },
        {
            "title": "Boundaries between families are real but busy",
            "text": (
                (
                    f"{_number(boundary_row.iloc[0]['BoundaryPathwayPercentage']):.0f}% of "
                    "pathways hand over to a pathway outside their own family, and "
                    f"{int(_number(boundary_row.iloc[0]['count_cross_family_hub']))} "
                    "connect several families at once."
                )
                if not boundary_row.empty
                else "Boundary figures were not available."
            ),
        },
        {
            "title": "Some content would have to be shared or duplicated",
            "text": (
                f"{int(shared['SharedCoreCandidates'].sum()):,} features appear across "
                "many candidate families. Separating the families entirely would mean "
                f"{int(shared['TotalDuplicationIfFederated'].sum()):,} duplicate copies "
                "of that content."
            ),
        },
        {
            "title": "Placement is clear for some pathways and not others",
            "text": (
                (
                    f"{_number(routing_row.iloc[0]['PercentageStrongSingleFamilyAssociation']):.0f}"
                    "% "
                    "of pathways clearly belong to one family on structural evidence; "
                    f"{_number(routing_row.iloc[0]['PercentageHighAmbiguity']):.0f}% could "
                    "sit in two or more equally well."
                )
                if not routing_row.empty
                else "Routing figures were not available."
            ),
        },
    ]
    return cards


def _phase2_conclusion(
    frames: Mapping[str, pd.DataFrame], primary_strategy: str
) -> dict[str, Any]:
    """Synthesis of the Phase 2 evidence, without selecting an architecture."""
    families = frames["families"]
    boundary = frames["boundary_summary"]
    boundary_row = boundary.loc[boundary["strategy"] == primary_strategy]
    routing = frames["routing_summary"]
    routing_row = routing.loc[routing["strategy"] == primary_strategy]
    shared = frames["shared_feature_summary"]

    boundary_pct = (
        _number(boundary_row.iloc[0]["BoundaryPathwayPercentage"])
        if not boundary_row.empty
        else 0.0
    )
    ambiguous_pct = (
        _number(routing_row.iloc[0]["PercentageHighAmbiguity"])
        if not routing_row.empty
        else 0.0
    )
    shared_candidates = int(shared["SharedCoreCandidates"].sum())

    return {
        "evidence_class": "candidate",
        "title": "Federated families are credible candidates, but their boundaries are porous",
        "paragraphs": [
            (
                "Multiple independent methods produce repeatable candidate "
                "groupings, and the presented "
                f"set contains {int(len(families))} candidate families. That is "
                "sufficient evidence to carry "
                "a federated or hierarchical architecture forward into Phase 3 for comparison "
                "with a"
                "monolithic alternative."
            ),
            (
                "The families are not independent clinical islands. About "
                f"{boundary_pct:.0f}% of pathways "
                f"cross a proposed family boundary, {shared_candidates:,} features "
                "are shared broadly across "
                f"families, and {ambiguous_pct:.0f}% of pathways remain highly "
                "ambiguous on structural "
                "evidence alone."
            ),
            (
                "Any viable federated design would therefore need to handle cross-family "
                "reasoning and"
                "shared evidence, potentially through shared or hierarchical structures, "
                "rather than simply"
                "running completely isolated Bayesian Networks. The proposed family "
                "boundaries still require"
                "clinical review before they can be treated as model boundaries."
            ),
        ],
        "next_question": (
            "Do the benefits of these smaller networks justify the runtime, governance and "
            "coordination"
            "complexity compared with a monolithic model?"
        ),
    }


def _phase2_next_phase() -> dict[str, Any]:
    """What Phase 3 will compare, and what it needs from Phase 2."""
    return {
        "description": (
            "Phase 3 will take the candidate structures from this phase and compare "
            "three ways of building a Bayesian model, measuring each against the same "
            "criteria."
        ),
        "options": [
            {
                "label": "Single model, as the data is written",
                "detail": (
                    "One Bayesian Network covering the whole estate, following the "
                    "existing Pathways structure directly."
                ),
            },
            {
                "label": "Single model, clinically normalised",
                "detail": (
                    "One Bayesian Network where questions meaning the same thing are "
                    "represented once rather than repeated."
                ),
            },
            {
                "label": "Federated or hierarchical models",
                "detail": (
                    "Several smaller Bayesian Networks based on the candidate families "
                    "from this phase, with shared structure where needed."
                ),
            },
        ],
        "criteria": [
            "Number of variables and relationships",
            "Growth of the probability tables",
            "Memory required",
            "Time to answer a question",
            "Behaviour as load increases",
            "Infrastructure needed",
            "Cost to run, including cost per assessment",
        ],
        "inputs_needed": [
            "The candidate family set, after clinical review",
            "Which pathways belong to which family, including overlaps",
            "The variable counts per family",
            "The shared features and how much duplication they imply",
            "The boundary pathways and features that would need coordinating",
            "The placement ambiguity figures",
            "The merge and split alternatives, to size a range rather than one option",
        ],
    }


def _phase2_methodology(configuration: Mapping[str, str]) -> list[dict[str, str]]:
    """Technical definitions, shown behind progressive disclosure."""
    return [
        {
            "term": "Candidate family",
            "definition": (
                "A group of pathways that the evidence suggests could form one Bayesian "
                "model. Produced by an algorithm or an existing classification, and not "
                "clinically confirmed."
            ),
        },
        {
            "term": "Discovery strategy",
            "definition": (
                "One method of proposing families. NHS classifications, connection "
                "clustering and combined-similarity clustering were run independently, "
                "so that agreement between them is evidence in itself."
            ),
        },
        {
            "term": "Internal and external links",
            "definition": (
                "A handover between two pathways in the same family is internal; one "
                "crossing into another family is external. The internal percentage is "
                "internal divided by internal plus external, counted over the handovers "
                "leaving a family's pathways."
            ),
        },
        {
            "term": "Similarity scale",
            "definition": (
                "Feature similarity is the proportion of the combined feature set that "
                "both sides share, from 0 (nothing in common) to 1 (identical). It takes "
                "no account of set size, so two very small families can score 1.0 from a "
                "handful of shared items; the tables therefore carry the family sizes "
                "alongside."
            ),
        },
        {
            "term": "Why outcomes are excluded from the overlap banding",
            "definition": (
                "Fewer than 200 distinct outcomes exist and most families can reach a "
                "similar subset, so outcome similarity is high for almost every pair and "
                "cannot distinguish them. It is measured and reported, but the "
                "low/moderate/high banding uses questions, discriminators and SNOMED "
                "concepts only."
            ),
        },
        {
            "term": "Agreement between clustering methods",
            "definition": (
                "Measured as the adjusted Rand index: 1.0 means two methods produced the "
                "same grouping, 0.0 means agreement no better than chance. It ignores "
                "how the groups are labelled or how many there are."
            ),
        },
        {
            "term": "Presented candidate set",
            "definition": (
                "The family set shown in the explorer is "
                "'"
                + configuration.get("presentation.primary_candidate_strategy", "hybrid_a")
                + "', "
                "chosen in configuration because it requires both connection evidence "
                "and clinical-feature support before keeping a group. That is a "
                "modelling choice, not a finding that it is the right family set; all "
                "strategies are compared."
            ),
        },
        {
            "term": "Family naming",
            "definition": (
                "A family is named after an NHS classification only when one value "
                "covers at least "
                f"{configuration.get('presentation.naming_dominance_threshold', '0.5')} "
                "of its pathways. Otherwise it keeps a neutral name, because inventing a "
                "clinical-sounding name would imply a clinical claim the evidence does "
                "not support."
            ),
        },
    ]


# ======================================================================================
# Phase 3 payload
# ======================================================================================
PHASE3_RUNNERS: Final[dict[str, str]] = {
    "a": "python -m pathways_analysis.phase3_sizing",
    "b": "python -m pathways_analysis.phase3_cpt_sizing",
    "c": "python -m pathways_analysis.phase3_benchmark",
    "d": "python -m pathways_analysis.phase3_runtime",
    "e": "python -m pathways_analysis.phase3_cost",
    "f": "python -m pathways_analysis.phase3_adr",
}

PHASE3_ARTEFACTS: Final[dict[str, Artefact]] = {
    "representations": Artefact(
        "outputs/phase3/tables/representation_summary.csv",
        (
            "Representation",
            "Label",
            "CandidateVariableCount",
            "VariableIdentity",
            "EvidenceClass",
            "Interpretation",
            "ComparedWithDeduplicatedMonolith",
        ),
        PHASE3_RUNNERS["a"],
    ),
    "state_cardinality": Artefact(
        "outputs/phase3/tables/state_cardinality_summary.csv",
        ("Scope", "count", "min", "median", "p90", "p95", "max"),
        PHASE3_RUNNERS["a"],
    ),
    "assumptions": Artefact(
        "outputs/phase3/tables/evidence_and_assumptions.csv",
        ("Item", "Class", "Value", "Limitation"),
        PHASE3_RUNNERS["a"],
    ),
    "cpt_sizing": Artefact(
        "outputs/phase3/tables/cpt_sizing_by_representation.csv",
        (
            "Representation",
            "ParentCount",
            "ParentStateCase",
            "AssumedParentStatesEach",
            "VariableCountSized",
            "TotalCptEntries",
            "TotalFreeParameters",
            "LargestVariableCptEntries",
            "RawProbabilityMiBFloat32",
        ),
        PHASE3_RUNNERS["b"],
    ),
    "cpt_growth": Artefact(
        "outputs/phase3/tables/cpt_growth_curve.csv",
        (
            "Representation",
            "ParentStateCase",
            "ParentCount",
            "TotalCptEntries",
            "GrowthVsPreviousParentCount",
        ),
        PHASE3_RUNNERS["b"],
    ),
    "cpt_method_notes": Artefact(
        "outputs/phase3/tables/phase3b_method_notes.csv",
        ("Item", "EvidenceClass", "Statement"),
        PHASE3_RUNNERS["b"],
    ),
    "benchmark_envelope": Artefact(
        "outputs/phase3/tables/benchmark_runtime_envelope.csv",
        (
            "Representation",
            "ModelScope",
            "MaxBenchmarkNodes",
            "MaxFractionOfActualModel",
            "ObservedQueryP95MinMs",
            "ObservedQueryP95MaxMs",
            "EvidenceClass",
            "Caveat",
        ),
        PHASE3_RUNNERS["c"],
    ),
    "runtime_patterns": Artefact(
        "outputs/phase3/tables/runtime_patterns.csv",
        (
            "PatternId",
            "LogicalModel",
            "DeploymentShape",
            "ModelResidency",
            "Routing",
            "CrossModelCoordination",
        ),
        PHASE3_RUNNERS["d"],
    ),
    "runtime_coordination": Artefact(
        "outputs/phase3/tables/runtime_coordination_evidence.csv",
        ("Evidence", "Value", "Unit", "RuntimeMeaning", "EvidenceClass"),
        PHASE3_RUNNERS["d"],
    ),
    "runtime_failure_modes": Artefact(
        "outputs/phase3/tables/runtime_failure_modes.csv",
        ("PatternId", "FailureMode", "LikelyScope", "RequiredControl", "EvidenceClass"),
        PHASE3_RUNNERS["d"],
    ),
    "runtime_blast_radius": Artefact(
        "outputs/phase3/tables/runtime_change_blast_radius.csv",
        (
            "PatternId",
            "LocalChangeUnit",
            "ModelReleaseBlastRadius",
            "RegressionScope",
            "EvidenceClass",
        ),
        PHASE3_RUNNERS["d"],
    ),
    "cost_scenarios": Artefact(
        "outputs/phase3/tables/infrastructure_cost_scenarios.csv",
        (
            "PatternId",
            "AssessmentsPerMonth",
            "RequiredTasks",
            "TotalIllustrativeMonthlyUsd",
            "IllustrativeCostPer1000AssessmentsUsd",
            "PricingTargetRegion",
            "PricingBasisRegion",
            "PricingStatus",
            "EvidenceClass",
        ),
        PHASE3_RUNNERS["e"],
    ),
    "cost_method_notes": Artefact(
        "outputs/phase3/tables/phase3e_method_notes.csv",
        ("Item", "EvidenceClass", "Statement"),
        PHASE3_RUNNERS["e"],
    ),
    "adr_evidence_matrix": Artefact(
        "outputs/phase3/tables/adr_evidence_matrix.csv",
        (
            "Representation",
            "Label",
            "CandidateVariableCount",
            "ReferenceCptEntries",
            "BenchmarkCoverage",
            "BenchmarkP95MsRange",
            "IllustrativeMonthlyCost1mUsd",
            "EvidenceStatus",
        ),
        PHASE3_RUNNERS["f"],
    ),
    "adr_gates": Artefact(
        "outputs/phase3/tables/adr_decision_gates.csv",
        ("Gate", "Passed", "Detail"),
        PHASE3_RUNNERS["f"],
    ),
    "adr_tradeoffs": Artefact(
        "outputs/phase3/tables/adr_runtime_tradeoffs.csv",
        ("Representation", "Strength", "Tradeoff", "EvidenceClass"),
        PHASE3_RUNNERS["f"],
    ),
}

PHASE3_KEYS: Final[tuple[str, ...]] = (
    "meta",
    "executive_summary",
    "status",
    "representations",
    "cpt_growth",
    "benchmark",
    "runtime",
    "cost",
    "decision",
    "tells_us",
    "does_not_tell_us",
    "methodology",
    "conclusion",
)

#: Plain-English labels for the three representations. Held here so the wording is
#: identical everywhere it appears rather than retyped per section.
REPRESENTATION_LABELS: Final[dict[str, str]] = {
    "literal_monolith": "One model, as the content is written",
    "deduplicated_monolith": "One model, questions deduplicated",
    "provisional_federated": "Several models, one per candidate family",
}

#: Plain-English labels for the four runtime patterns.
RUNTIME_PATTERN_LABELS: Final[dict[str, str]] = {
    "monolith_always_resident": "One model, always loaded",
    "federated_all_resident": "All family models, always loaded",
    "federated_lazy_loaded": "Family models loaded on demand",
    "hierarchical_shared_core": "Family models plus a shared core",
}


def _representation_label(key: str) -> str:
    """Return a plain-English label for a representation identifier."""
    return REPRESENTATION_LABELS.get(key, key.replace("_", " "))


def _pattern_label(key: str) -> str:
    """Return a plain-English label for a runtime pattern identifier."""
    return RUNTIME_PATTERN_LABELS.get(key, key.replace("_", " "))


def build_phase3(paths: Paths) -> dict[str, Any]:
    """Build the Phase 3 presentation payload.

    Phase 3 is the first phase whose outputs bear on the architecture decision, so the
    presentation has one extra obligation the earlier phases did not: it must make
    unmistakable which figures are measured, which are modelled under assumptions, and
    which are placeholders awaiting a decision that has not been taken. The decision
    gates are surfaced for exactly that reason.
    """
    LOGGER.info("--- Building Phase 3 report data ---")
    frames = load_all(PHASE3_ARTEFACTS, paths)
    source = {name: artefact.relative_path for name, artefact in PHASE3_ARTEFACTS.items()}

    payload: dict[str, Any] = {
        "meta": _meta(
            "3",
            "Comparing Architectures",
            "How large, fast, scalable and costly would the candidate architectures be?",
        ),
        "executive_summary": _phase3_executive_summary(frames),
        "status": _phase3_status(frames, source),
        "representations": _phase3_representations(frames, source),
        "cpt_growth": _phase3_cpt_growth(frames, source),
        "benchmark": _phase3_benchmark(frames, source),
        "runtime": _phase3_runtime(frames, source),
        "cost": _phase3_cost(frames, source),
        "decision": _phase3_decision(frames, source),
        "tells_us": _phase3_tells_us(frames),
        "does_not_tell_us": [
            "Which architecture should be built. The draft ADR records open decision "
            "gates, not a recommendation.",
            "What the system would actually cost. The cost figures are illustrative "
            "scenarios built on stated assumptions and non-target-region pricing, not "
            "a quotation.",
            "How fast the real system would respond — its production latency. The "
            "benchmark runs models a fraction of the size of the real ones; it bounds "
            "the shape of the problem, not the answer.",
            "Whether the candidate families are the right ones. They remain a "
            "provisional analytical baseline pending clinical review, and every "
            "federated figure inherits that caveat.",
            "What the clinically correct Bayesian structure is. The parent counts are "
            "a sensitivity range, not a proposed model; a real network would be "
            "designed clinically, not derived from the current question ordering.",
        ],
        "methodology": _phase3_methodology(frames),
        "conclusion": _phase3_conclusion(frames),
    }
    validate_payload(payload, PHASE3_KEYS, "phase3")
    return payload


def _phase3_status(
    frames: Mapping[str, pd.DataFrame], source: Mapping[str, str]
) -> dict[str, Any]:
    """Which Phase 3 stages have produced evidence, and whether the ADR is open."""
    gates = frames["adr_gates"]
    rows = [
        {
            "gate": _text(row.Gate),
            "passed": bool(row.Passed),
            "detail": _text(row.Detail),
        }
        for row in gates.itertuples()
    ]
    open_gates = [row for row in rows if not row["passed"]]
    return {
        "evidence_class": "derived",
        "source": [source["adr_gates"]],
        "gates": rows,
        "gates_total": len(rows),
        "gates_passed": len(rows) - len(open_gates),
        "gates_open": len(open_gates),
        "decision_status": "DRAFT — decision gates open" if open_gates else "gates closed",
        "note": (
            "A gate marked as passed means the evidence for that stage exists and was "
            "produced by this pipeline. It does not mean the evidence has been "
            "accepted, reviewed or agreed."
        ),
    }


def _phase3_representations(
    frames: Mapping[str, pd.DataFrame], source: Mapping[str, str]
) -> dict[str, Any]:
    """The three candidate representations and how many variables each implies."""
    summary = frames["representations"]
    cardinality = frames["state_cardinality"]
    rows = [
        {
            "representation": _text(row.Representation),
            "label": _representation_label(_text(row.Representation)),
            "technical_label": _text(row.Label),
            "variable_count": int(_number(row.CandidateVariableCount)),
            "variable_identity": _text(row.VariableIdentity),
            "evidence_class": _text(row.EvidenceClass),
            "interpretation": _text(row.Interpretation),
            "difference_vs_deduplicated": int(
                _number(row.ComparedWithDeduplicatedMonolith)
            ),
        }
        for row in summary.itertuples()
    ]
    rows.sort(key=lambda item: -item["variable_count"])

    return {
        "evidence_class": "derived",
        "source": [source["representations"], source["state_cardinality"]],
        "rows": rows,
        "state_cardinality": [
            {
                "scope": _text(row.Scope),
                "variables": int(_number(row.count)),
                "min": int(_number(row.min)),
                "median": _optional_number(row.median),
                "p90": _optional_number(row.p90),
                "max": int(_number(row.max)),
            }
            for row in cardinality.itertuples()
        ],
        "definition": (
            "A variable is one thing the model reasons about. The three options differ "
            "only in what counts as the same variable: every question occurrence in "
            "every pathway, each distinct question once, or each distinct question once "
            "per family that uses it."
        ),
        "caveat": (
            "None of these is a proposed Bayesian network. They are three ways of "
            "counting what the current content would become, which is what makes them "
            "comparable."
        ),
    }


def _phase3_cpt_growth(
    frames: Mapping[str, pd.DataFrame], source: Mapping[str, str]
) -> dict[str, Any]:
    """How the probability tables grow as variables gain parents."""
    sizing = frames["cpt_sizing"]
    growth = frames["cpt_growth"]

    rows = [
        {
            "representation": _text(row.Representation),
            "label": _representation_label(_text(row.Representation)),
            "parent_count": int(_number(row.ParentCount)),
            "parent_state_case": _text(row.ParentStateCase),
            "parent_states_each": int(_number(row.AssumedParentStatesEach)),
            "variables": int(_number(row.VariableCountSized)),
            "cpt_entries": int(_number(row.TotalCptEntries)),
            "free_parameters": int(_number(row.TotalFreeParameters)),
            "largest_variable_entries": int(_number(row.LargestVariableCptEntries)),
            "raw_mib_float32": _optional_number(row.RawProbabilityMiBFloat32),
        }
        for row in sizing.itertuples()
    ]

    growth_rows = [
        {
            "representation": _text(row.Representation),
            "label": _representation_label(_text(row.Representation)),
            "parent_state_case": _text(row.ParentStateCase),
            "parent_count": int(_number(row.ParentCount)),
            "cpt_entries": int(_number(row.TotalCptEntries)),
            "growth_multiple": _optional_number(row.GrowthVsPreviousParentCount),
        }
        for row in growth.itertuples()
    ]

    parent_counts = sorted({item["parent_count"] for item in rows})
    cases = sorted({item["parent_state_case"] for item in rows})
    return {
        "evidence_class": "derived",
        "source": [source["cpt_sizing"], source["cpt_growth"]],
        "rows": rows,
        "growth": growth_rows,
        "parent_counts": parent_counts,
        "parent_state_cases": cases,
        "default_case": "median_parent_states" if "median_parent_states" in cases else cases[0],
        "case_labels": {
            "median_parent_states": "Typical case",
            "p90_parent_states": "Demanding case",
        },
        "method_notes": [
            {
                "item": _text(row.Item),
                "evidence_class": _text(row.EvidenceClass),
                "statement": _text(row.Statement),
            }
            for row in frames["cpt_method_notes"].itertuples()
        ],
        "definition": (
            "A probability table holds one number for every combination of a variable's "
            "own answers and the answers of the variables it depends on. Add one more "
            "dependency and the table multiplies in size rather than adding to it."
        ),
        "caveat": (
            "The number of dependencies per variable is a stated range, not a finding. "
            "The real structure would be designed clinically. These figures show how "
            "sensitive the size is to that choice, which is the point."
        ),
    }


def _phase3_benchmark(
    frames: Mapping[str, pd.DataFrame], source: Mapping[str, str]
) -> dict[str, Any]:
    """Measured inference timings, with their coverage stated plainly."""
    envelope = frames["benchmark_envelope"]
    rows = [
        {
            "representation": _text(row.Representation),
            "label": _representation_label(_text(row.Representation)),
            "model_scope": _text(row.ModelScope).replace("_", " "),
            "benchmark_nodes": int(_number(row.MaxBenchmarkNodes)),
            "fraction_of_real_model": _optional_number(row.MaxFractionOfActualModel),
            "coverage_percentage": round(
                100.0 * _number(row.MaxFractionOfActualModel), 2
            ),
            "p95_min_ms": _optional_number(row.ObservedQueryP95MinMs),
            "p95_max_ms": _optional_number(row.ObservedQueryP95MaxMs),
            "evidence_class": _text(row.EvidenceClass),
        }
        for row in envelope.itertuples()
    ]
    caveat = _text(envelope.iloc[0]["Caveat"]) if not envelope.empty else ""
    smallest = min((item["coverage_percentage"] for item in rows), default=0.0)
    largest = max((item["coverage_percentage"] for item in rows), default=0.0)
    return {
        "evidence_class": "measured",
        "source": [source["benchmark_envelope"]],
        "rows": rows,
        "coverage_min_percentage": smallest,
        "coverage_max_percentage": largest,
        "caveat": caveat,
        "coverage_warning": (
            "These timings come from models built at a fraction of the real size — "
            f"between {smallest:.1f}% and {largest:.0f}% of the variables the real "
            "models would contain. They establish how timing responds to size and "
            "structure. They are not a prediction of production latency, and they must "
            "not be quoted as one."
        ),
    }


def _phase3_runtime(
    frames: Mapping[str, pd.DataFrame], source: Mapping[str, str]
) -> dict[str, Any]:
    """The four deployment patterns and what distinguishes them."""
    patterns = frames["runtime_patterns"]
    rows = [
        {
            "pattern_id": _text(row.PatternId),
            "label": _pattern_label(_text(row.PatternId)),
            "logical_model": _text(row.LogicalModel),
            "deployment_shape": _text(row.DeploymentShape),
            "model_residency": _text(row.ModelResidency),
            "routing": _text(row.Routing),
            "coordination": _text(row.CrossModelCoordination),
        }
        for row in patterns.itertuples()
    ]
    return {
        "evidence_class": "candidate",
        "source": [
            source["runtime_patterns"],
            source["runtime_coordination"],
            source["runtime_failure_modes"],
            source["runtime_blast_radius"],
        ],
        "patterns": rows,
        "coordination_evidence": [
            {
                "evidence": _text(row.Evidence),
                "value": _optional_number(row.Value),
                "unit": _text(row.Unit),
                "meaning": _text(row.RuntimeMeaning),
                "evidence_class": _text(row.EvidenceClass),
            }
            for row in frames["runtime_coordination"].itertuples()
        ],
        "failure_modes": [
            {
                "pattern_id": _text(row.PatternId),
                "label": _pattern_label(_text(row.PatternId)),
                "failure_mode": _text(row.FailureMode),
                "scope": _text(row.LikelyScope),
                "control": _text(row.RequiredControl),
            }
            for row in frames["runtime_failure_modes"].itertuples()
        ],
        "blast_radius": [
            {
                "pattern_id": _text(row.PatternId),
                "label": _pattern_label(_text(row.PatternId)),
                "change_unit": _text(row.LocalChangeUnit),
                "release_blast_radius": _text(row.ModelReleaseBlastRadius),
                "regression_scope": _text(row.RegressionScope),
            }
            for row in frames["runtime_blast_radius"].itertuples()
        ],
        "key_point": (
            "How the model is divided and how it is deployed are separate decisions. "
            "Several smaller models does not have to mean several services: they can "
            "sit inside one. The patterns exist so that cost is attached to a "
            "deployment shape rather than to the word 'federated'."
        ),
    }


def _phase3_cost(
    frames: Mapping[str, pd.DataFrame], source: Mapping[str, str]
) -> dict[str, Any]:
    """Illustrative running-cost scenarios, with their basis stated."""
    scenarios = frames["cost_scenarios"]
    rows = [
        {
            "pattern_id": _text(row.PatternId),
            "label": _pattern_label(_text(row.PatternId)),
            "assessments_per_month": int(_number(row.AssessmentsPerMonth)),
            "tasks": int(_number(row.RequiredTasks)),
            "monthly_usd": _optional_number(row.TotalIllustrativeMonthlyUsd),
            "cost_per_1000_usd": _optional_number(
                row.IllustrativeCostPer1000AssessmentsUsd
            ),
        }
        for row in scenarios.itertuples()
    ]
    volumes = sorted({item["assessments_per_month"] for item in rows})
    first = scenarios.iloc[0]

    # Whether the patterns differ in cost depends entirely on volume: below a certain
    # throughput the minimum capacity floor dominates and every pattern costs the same.
    # The spread is computed per volume so the page can say which regime it is showing
    # instead of asserting one.
    spread = []
    for volume in volumes:
        at_volume = [
            item["monthly_usd"]
            for item in rows
            if item["assessments_per_month"] == volume
        ]
        low, high = min(at_volume), max(at_volume)
        spread.append(
            {
                "assessments_per_month": volume,
                "min_monthly_usd": low,
                "max_monthly_usd": high,
                "ratio": round(high / low, 2) if low else None,
                "patterns_differ": high > low,
            }
        )
    differentiating = [
        item["assessments_per_month"] for item in spread if item["patterns_differ"]
    ]

    return {
        "evidence_class": "candidate",
        "source": [source["cost_scenarios"], source["cost_method_notes"]],
        "rows": rows,
        "volumes": volumes,
        "spread_by_volume": spread,
        "volumes_where_patterns_differ": differentiating,
        # Default to the highest volume: it is the only regime in which the patterns
        # separate at all, so defaulting lower would show four identical bars and hide
        # the finding.
        "default_volume": (
            max(differentiating)
            if differentiating
            else (volumes[-1] if volumes else 0)
        ),
        "floor_note": (
            "Below roughly "
            + (f"{min(differentiating):,} assessments a month, " if differentiating else "")
            + "the patterns cost the same because a minimum amount of capacity has to "
            "run regardless of how much work reaches it. The differences only appear "
            "once volume is high enough to need more than that minimum."
        ),
        "pricing_target_region": _text(first["PricingTargetRegion"]),
        "pricing_basis_region": _text(first["PricingBasisRegion"]),
        "pricing_status": _text(first["PricingStatus"]),
        "method_notes": [
            {
                "item": _text(row.Item),
                "evidence_class": _text(row.EvidenceClass),
                "statement": _text(row.Statement),
            }
            for row in frames["cost_method_notes"].itertuples()
        ],
        "caveat": (
            "These are illustrative scenarios, not a quotation. They are modelled on "
            f"{_text(first['PricingBasisRegion'])} pricing as a stand-in for "
            f"{_text(first['PricingTargetRegion'])}, and they price compute for "
            "inference only. Treat the gap between the patterns as the finding, not the "
            "absolute figures."
        ),
    }


def _phase3_decision(
    frames: Mapping[str, pd.DataFrame], source: Mapping[str, str]
) -> dict[str, Any]:
    """The evidence assembled per representation, and the trade-offs, with no winner."""
    matrix = frames["adr_evidence_matrix"]
    rows = [
        {
            "representation": _text(row.Representation),
            "label": _representation_label(_text(row.Representation)),
            "technical_label": _text(row.Label),
            "variable_count": int(_number(row.CandidateVariableCount)),
            "reference_cpt_entries": int(_number(row.ReferenceCptEntries)),
            "benchmark_coverage": _text(row.BenchmarkCoverage),
            "benchmark_range": _text(row.BenchmarkP95MsRange),
            "illustrative_monthly_usd": _optional_number(
                row.IllustrativeMonthlyCost1mUsd
            ),
            "evidence_status": _text(row.EvidenceStatus),
        }
        for row in matrix.itertuples()
    ]
    tradeoffs = [
        {
            "representation": _text(row.Representation),
            "label": _representation_label(_text(row.Representation)),
            "strength": _text(row.Strength),
            "tradeoff": _text(row.Tradeoff),
            "evidence_class": _text(row.EvidenceClass),
        }
        for row in frames["adr_tradeoffs"].itertuples()
    ]
    return {
        "evidence_class": "candidate",
        "source": [source["adr_evidence_matrix"], source["adr_tradeoffs"]],
        "rows": rows,
        "tradeoffs": tradeoffs,
        "no_recommendation": (
            "No architecture is recommended. Each option is shown with its strength and "
            "the cost of that strength, so the choice can be made deliberately rather "
            "than inherited from an analysis."
        ),
        "outstanding": (
            "The decision cannot be closed while the candidate families remain a "
            "provisional analytical baseline. Clinical review of the Phase 2 families "
            "changes the federated figures and must come first."
        ),
    }


def _phase3_cost_spread_sentence(frames: Mapping[str, pd.DataFrame]) -> str:
    """Describe how far the deployment patterns separate on cost, from the data.

    Asserting "the patterns cost about the same" is only true below the volume at
    which more than the minimum capacity is needed. Computing it keeps the summary
    honest when the scenario assumptions change.
    """
    scenarios = frames["cost_scenarios"]
    widest_ratio, widest_volume = 1.0, None
    for volume, group in scenarios.groupby("AssessmentsPerMonth"):
        low = float(group["TotalIllustrativeMonthlyUsd"].min())
        high = float(group["TotalIllustrativeMonthlyUsd"].max())
        if low > 0 and high / low > widest_ratio:
            widest_ratio, widest_volume = high / low, int(volume)
    if widest_volume is None:
        return (
            "Illustrative running costs are identical across the deployment patterns "
            "at every volume modelled, so cost alone does not separate them."
        )
    return (
        f"Illustrative running costs are identical across the deployment patterns "
        f"until volume is high enough to need more than minimum capacity; at "
        f"{widest_volume:,} assessments a month they spread to about "
        f"{widest_ratio:.1f}x between cheapest and dearest, though the absolute sums "
        "remain small."
    )


def _phase3_executive_summary(frames: Mapping[str, pd.DataFrame]) -> dict[str, Any]:
    """The one-screen summary for a reader who will not scroll."""
    summary = frames["representations"].set_index("Representation")
    literal = int(_number(summary.loc["literal_monolith", "CandidateVariableCount"]))
    dedup = int(_number(summary.loc["deduplicated_monolith", "CandidateVariableCount"]))
    federated = int(_number(summary.loc["provisional_federated", "CandidateVariableCount"]))
    gates = frames["adr_gates"]
    open_gates = int((~gates["Passed"].astype(bool)).sum())

    return {
        "evidence_class": "derived",
        "headline": (
            "All three architectures are technically feasible at this scale. The "
            "decision is not about whether they fit, but about which trade-off is "
            "acceptable."
        ),
        "key_points": [
            f"Representing the content literally needs about {literal:,} variables; "
            f"treating each distinct question once needs {dedup:,}, roughly "
            f"{literal / max(dedup, 1):.0f} times fewer.",
            f"Splitting into the candidate families needs about {federated:,} variable "
            f"copies, because a question used by several families is held in each of "
            "them.",
            "Probability-table size is driven far more by how many other variables each "
            "one depends on than by how many variables there are. That structural "
            "choice is clinical, and has not been made.",
            "Measured inference timings are in the low milliseconds, but on models a "
            "fraction of real size, so they bound the shape of the problem rather than "
            "predicting production performance.",
            _phase3_cost_spread_sentence(frames),
        ],
        "bottom_line": (
            f"Phase 3 has assembled the comparison evidence but does not close the "
            f"decision: {open_gates} gate(s) remain open, and the candidate families "
            "are still a provisional baseline awaiting clinical review."
            if open_gates
            else "Phase 3 has assembled the comparison evidence. The decision remains "
            "with the programme."
        ),
    }


def _phase3_tells_us(frames: Mapping[str, pd.DataFrame]) -> list[dict[str, str]]:
    """Plain-language findings."""
    summary = frames["representations"].set_index("Representation")
    literal = int(_number(summary.loc["literal_monolith", "CandidateVariableCount"]))
    dedup = int(_number(summary.loc["deduplicated_monolith", "CandidateVariableCount"]))
    federated = int(_number(summary.loc["provisional_federated", "CandidateVariableCount"]))
    growth = frames["cpt_growth"]
    largest_growth = growth["GrowthVsPreviousParentCount"].max()

    return [
        {
            "title": "Deduplication is the single largest lever on size",
            "text": (
                f"Treating each distinct question once rather than once per pathway "
                f"takes the variable count from {literal:,} to {dedup:,}. No other "
                "choice in this analysis changes the size by as much."
            ),
        },
        {
            "title": "Splitting into families duplicates shared content",
            "text": (
                f"The candidate families need {federated:,} variable copies against "
                f"{dedup:,} for a single deduplicated model. The difference is the "
                "questions used by more than one family, which each family would hold "
                "its own copy of."
            ),
        },
        {
            "title": "Structure matters more than scale",
            "text": (
                "Adding one more dependency to each variable multiplies the probability "
                f"tables by up to {largest_growth:.0f} times. The number of variables is "
                "a much weaker driver of size than how they are connected."
            ),
        },
        {
            "title": "Nothing here is close to a technical limit",
            "text": (
                "Under the assumptions tested, the probability tables are measured in "
                "megabytes and the inference timings in milliseconds. Size is not what "
                "distinguishes these options."
            ),
        },
        {
            "title": "Cost separates the patterns only at high volume",
            "text": (
                _phase3_cost_spread_sentence(frames)
                + " Below that, what distinguishes the patterns is release blast "
                "radius, failure scope and version coordination — operational "
                "qualities rather than a price."
            ),
        },
    ]


def _phase3_methodology(frames: Mapping[str, pd.DataFrame]) -> list[dict[str, str]]:
    """Technical definitions, shown behind progressive disclosure."""
    definitions = [
        {
            "term": "Variable",
            "definition": (
                "One thing the model reasons about, usually corresponding to a question "
                "and its possible answers. The three representations differ only in what "
                "they treat as the same variable."
            ),
        },
        {
            "term": "Probability table",
            "definition": (
                "For each variable, one number for every combination of its own answers "
                "and the answers of the variables it depends on. Size is the product of "
                "those, not the sum, which is why dependency count dominates."
            ),
        },
        {
            "term": "Free parameters",
            "definition": (
                "The numbers that would actually have to be estimated. Each column of a "
                "probability table must sum to one, so one value per column follows from "
                "the others and is not independently estimated."
            ),
        },
        {
            "term": "Parent count",
            "definition": (
                "How many other variables a variable depends on. Varied deliberately "
                "across a range here because the real structure would be a clinical "
                "design decision, not something derivable from the current content."
            ),
        },
        {
            "term": "Benchmark coverage",
            "definition": (
                "The share of a real model's variables that the benchmarked model "
                "actually contained. Coverage well below 100% means the timings describe "
                "the trend, not the destination."
            ),
        },
        {
            "term": "Runtime pattern",
            "definition": (
                "A deployment shape: how many services, which models are held in memory, "
                "and how requests are routed between them. Deliberately separate from the "
                "logical question of how the model is divided."
            ),
        },
        {
            "term": "Release blast radius",
            "definition": (
                "How much of the system has to be re-tested and re-released when one part "
                "changes. A primary operational difference between the patterns."
            ),
        },
        {
            "term": "Illustrative cost",
            "definition": (
                "A scenario built from stated assumptions about volume, compute and "
                "pricing. Useful for comparing patterns against each other; not a budget "
                "figure and not a quotation."
            ),
        },
    ]
    for row in frames["assumptions"].itertuples():
        definitions.append(
            {
                "term": f"{_text(row.Item)} ({_text(row.Class)})",
                "definition": f"{_text(row.Value)}. Limitation: {_text(row.Limitation)}",
            }
        )
    return definitions


def _phase3_conclusion(frames: Mapping[str, pd.DataFrame]) -> dict[str, Any]:
    """The explicit closing statement, matching the Phase 1 and Phase 2 shape."""
    gates = frames["adr_gates"]
    open_gates = int((~gates["Passed"].astype(bool)).sum())
    return {
        "evidence_class": "derived",
        "paragraphs": [
            "Phase 3 set out to establish whether the three candidate architectures "
            "differ enough in size, speed, operability and cost for the choice to be "
            "made on technical grounds. On the evidence assembled, they do not. All "
            "three fit comfortably within ordinary infrastructure under the assumptions "
            "tested, and the illustrative costs sit close together.",
            "What does separate them is operational: how much has to be re-tested when "
            "one part changes, how far a failure spreads, and how much content would be "
            "duplicated across models. Those are the terms in which the decision should "
            "be argued.",
            "The largest single influence on model size is not the architecture at all. "
            "It is how many other variables each variable depends on, and that is a "
            "clinical modelling decision that has not been taken.",
        ],
        "next_question": (
            "Which trade-off does the programme want to own: the simplicity of one "
            "model, or the smaller blast radius of several?"
        ),
        "open_gates": open_gates,
        "status_note": (
            "The draft ADR remains open. The candidate families are a provisional "
            "analytical baseline, and the federated figures will change once clinical "
            "review settles the family boundaries."
        ),
    }


# ======================================================================================
# CLI
# ======================================================================================
def write_payload(payload: Mapping[str, Any], path: Path) -> Path:
    """Write a payload as formatted JSON.

    Sorted keys and a trailing newline keep the diff stable between runs, which matters
    because these files are reviewed for confidentiality before being shared.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    LOGGER.info("Wrote %-34s %8.1f KB", path.name, path.stat().st_size / 1024)
    return path


def configure_logging(level: str) -> None:
    """Configure stdout logging."""
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s  %(levelname)-7s %(message)s",
        datefmt="%H:%M:%S",
        stream=sys.stdout,
    )


def build_argument_parser() -> argparse.ArgumentParser:
    """Build the report-builder CLI parser."""
    parser = argparse.ArgumentParser(
        prog="python -m pathways_analysis.report_builder",
        description=(
            "Convert the Phase 1, Phase 2 and Phase 3 analytical outputs into scoped "
            "JSON for the static report in reports/. Reads files only: no database "
            "connection and no credentials are required, and no analytical artefact is "
            "modified."
        ),
    )
    parser.add_argument(
        "--phase",
        default="all",
        choices=["1", "2", "3", "all"],
        help="Which report data to build (default: all).",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Override the output directory (default: reports/data).",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging verbosity (default: INFO).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Entry point for ``python -m pathways_analysis.report_builder``."""
    args = build_argument_parser().parse_args(argv)
    configure_logging(args.log_level)

    paths = Paths.discover()
    output_dir = args.output_dir or paths.reports_data

    builders = {
        "1": ("phase1-report.json", build_phase1),
        "2": ("phase2-report.json", build_phase2),
        "3": ("phase3-report.json", build_phase3),
    }
    selected = ["1", "2", "3"] if args.phase == "all" else [args.phase]

    written: list[Path] = []
    skipped: list[tuple[str, str]] = []
    for phase in selected:
        filename, builder = builders[phase]
        try:
            payload = builder(paths)
        except ReportBuildError as exc:
            # An explicitly requested phase is a hard failure: the caller asked for it.
            # Under `--phase all` a phase whose analysis has not been run yet is
            # skipped with a named reason instead, so that not having run Phase 3 does
            # not block rebuilding the Phase 1 and 2 data. The skip is reported, never
            # silent, and the corresponding page shows its own missing-data panel.
            if args.phase != "all":
                LOGGER.error("REPORT BUILD FAILED")
                LOGGER.error("%s", exc)
                return 2
            LOGGER.warning("Skipping phase %s: its analysis outputs are not present.", phase)
            skipped.append((phase, str(exc)))
            continue
        written.append(write_payload(payload, output_dir / filename))

    if not written:
        LOGGER.error("REPORT BUILD FAILED: no phase had usable evidence.")
        for _, reason in skipped:
            LOGGER.error("%s", reason)
        return 2

    print()
    print("=" * 78)
    print("PATHWAYS REPORT DATA BUILT")
    print("=" * 78)
    for path in written:
        print(f"  {path.name:<28} {path.stat().st_size / 1024:>8.1f} KB  -> {path.parent}")
    for phase, _ in skipped:
        runner = {
            "1": "python -m pathways_analysis.profiling",
            "2": "python -m pathways_analysis.family_discovery",
            "3": "python -m pathways_analysis.phase3_sizing (and the other phase3_* stages)",
        }[phase]
        print(f"  phase{phase}-report.json          SKIPPED -- run: {runner}")
    print("-" * 78)
    print("  " + CONFIDENTIALITY_NOTICE)
    print("  These files carry derived Pathways content and are gitignored.")
    print("-" * 78)
    print("  Serve the report locally with:")
    print(f"    cd {paths.reports}  &&  python -m http.server 8000")
    print("    then open http://localhost:8000/")
    print("=" * 78)
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
