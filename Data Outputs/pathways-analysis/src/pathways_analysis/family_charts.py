"""Phase 2 visualisations.

Section 19 of the Phase 2 brief.

Each function renders one figure from tables already written by the runner, so a chart
can never disagree with the evidence table behind it. Every chart is rendered through
:func:`~pathways_analysis.exports.safe_chart`, which converts a failure into a warning:
an optional visualisation must not lose a completed analysis.

Readability over completeness
-----------------------------
The brief rules out hairball diagrams, so:

* heatmaps are capped at the largest families of the strategy, with the cut stated in
  the subtitle rather than left implicit;
* the network view is aggregated to one node per candidate family, keeping only the
  strongest inter-family edges;
* per-pathway rankings show a top-N slice, with the full population named in the
  subtitle.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Final, Mapping, Sequence

import numpy as np
import pandas as pd

from . import exports
from .family_features import CandidateFamilySet, PathwayFeatureModel

LOGGER: Final = logging.getLogger(__name__)

SOURCE_NOTE: Final = (
    "Source: TriageDB (NHS Pathways current-state tables), read-only extract. "
    "Phase 2 candidate families are structural groupings, not clinically endorsed."
)

#: Largest number of families shown on a heatmap axis. Above this the axis labels stop
#: being legible and the figure stops being evidence.
HEATMAP_LIMIT: Final = 26


def _short(text: object, limit: int = 30) -> str:
    """Shorten a label for a dense axis."""
    value = "" if text is None else str(text)
    return value if len(value) <= limit else value[: limit - 1].rstrip() + "…"


def _family_axis_labels(
    cohesion: pd.DataFrame,
    names: Mapping[str, str],
    *,
    limit: int = HEATMAP_LIMIT,
    minimum_size: int = 2,
) -> tuple[list[str], list[str]]:
    """Return the largest families of a strategy and their short display labels.

    Single-pathway families are excluded by default. They produce all-zero rows and
    columns that consume a third of the canvas while carrying no information a reader
    cannot get from the family table; the exclusion is stated in each subtitle.
    """
    eligible = cohesion.loc[cohesion["PathwayCount"] >= minimum_size]
    if eligible.empty:
        eligible = cohesion
    top = eligible.nlargest(limit, "PathwayCount")
    ids = top["FamilyId"].tolist()
    labels = [
        _short(f"{names.get(family_id, family_id)} ({int(count)})")
        for family_id, count in zip(ids, top["PathwayCount"])
    ]
    return ids, labels


def _pair_matrix(
    overlap: pd.DataFrame,
    family_ids: Sequence[str],
    value_column: str,
) -> np.ndarray:
    """Build a symmetric matrix of one overlap column over the given families."""
    index = {family_id: position for position, family_id in enumerate(family_ids)}
    matrix = np.zeros((len(family_ids), len(family_ids)), dtype=float)
    for row in overlap.itertuples():
        left = index.get(row.FamilyA)
        right = index.get(row.FamilyB)
        if left is None or right is None:
            continue
        value = float(getattr(row, value_column))
        matrix[left, right] = value
        matrix[right, left] = value
    return matrix


def render_all(
    *,
    charts_dir: Path,
    graphs_dir: Path,
    primary: CandidateFamilySet,
    primary_names: Mapping[str, str],
    model: PathwayFeatureModel,
    cohesion: pd.DataFrame,
    overlap: pd.DataFrame,
    boundary: pd.DataFrame,
    shared_core: pd.DataFrame,
    strategy_comparison: pd.DataFrame,
    community_comparison: pd.DataFrame,
    native_candidates: pd.DataFrame,
) -> list[Path]:
    """Render every Phase 2 figure and return the paths written.

    Args:
        charts_dir: Directory for statistical charts.
        graphs_dir: Directory for network views.
        primary: The candidate family set presented for review.
        primary_names: ``{family_id: display name}`` for the primary set.
        model: The feature model.
        cohesion: Family cohesion for all strategies.
        overlap: Classified family overlap for all strategies.
        boundary: Boundary pathway classification for all strategies.
        shared_core: Shared-core candidate features.
        strategy_comparison: Strategy-level comparison.
        community_comparison: Community-detection method comparison.
        native_candidates: NHS-native grouping metrics.

    Returns:
        Paths of the figures that rendered successfully.
    """
    exports.apply_chart_theme()
    charts_dir.mkdir(parents=True, exist_ok=True)
    graphs_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    primary_cohesion = cohesion.loc[cohesion["strategy"] == primary.strategy].copy()
    primary_overlap = overlap.loc[overlap["strategy"] == primary.strategy].copy()
    primary_boundary = boundary.loc[boundary["strategy"] == primary.strategy].copy()

    def add(name: str, renderer) -> None:  # noqa: ANN001 - renderer is a local closure
        path = exports.safe_chart(name, renderer)
        if path is not None:
            written.append(path)

    # 1. Candidate family size distribution -------------------------------------------
    if not primary_cohesion.empty:
        sizes = primary_cohesion.sort_values("PathwayCount", ascending=False)
        add(
            "candidate_family_size_distribution",
            lambda: exports.bar_distribution(
                [
                    _short(primary_names.get(row.FamilyId, row.FamilyId), 22)
                    for row in sizes.itertuples()
                ],
                sizes["PathwayCount"].tolist(),
                title=f"Candidate family sizes ({primary.strategy})",
                subtitle=(
                    f"{len(sizes):,} candidate families over "
                    f"{primary.pathway_count:,} in-scope pathways. Structural "
                    f"grouping only -- not clinically endorsed"
                ),
                source=SOURCE_NOTE,
                path=charts_dir / "candidate_family_size_distribution.png",
                xlabel="Candidate family",
                ylabel="Pathways",
                annotate=len(sizes) <= 30,
                rotate_labels=90 if len(sizes) > 12 else 0,
                figsize=(12.5, 6.4),
            ),
        )

    # 2-5. Overlap and transition heatmaps --------------------------------------------
    if not primary_cohesion.empty and not primary_overlap.empty:
        family_ids, labels = _family_axis_labels(primary_cohesion, primary_names)
        shown = len(family_ids)
        total_families = int(primary_cohesion["FamilyId"].nunique())
        singletons = int((primary_cohesion["PathwayCount"] < 2).sum())
        cut_note = (
            f"largest {shown} of {total_families} candidate families"
            if shown < total_families
            else f"all {total_families} candidate families"
        )
        if singletons:
            cut_note += f", excluding {singletons} single-pathway families"

        transitions = _pair_matrix(primary_overlap, family_ids, "TransitionsAtoB")
        transitions_reverse = _pair_matrix(primary_overlap, family_ids, "TransitionsBtoA")
        add(
            "family_transition_heatmap",
            lambda: exports.heatmap(
                transitions + transitions_reverse,
                row_labels=labels,
                column_labels=labels,
                title=(
                    "Transfer transitions between candidate families "
                    f"({primary.strategy})"
                ),
                subtitle=(
                    f"{cut_note}. Both directions summed, so the matrix is symmetric; "
                    "the diagonal (within-family transitions) is not shown"
                ),
                source=SOURCE_NOTE,
                path=charts_dir / "family_transition_heatmap.png",
                value_label="Transfer transitions between the pair",
                annotate=shown <= 16,
                value_format="{:.0f}",
            ),
        )

        for column, stem, label, human in (
            ("SdJaccard", "family_sd_overlap_heatmap", "Symptom-discriminator Jaccard",
             "symptom discriminators"),
            ("SnomedJaccard", "family_snomed_overlap_heatmap", "SNOMED concept Jaccard",
             "SNOMED concepts"),
            ("QuestionJaccard", "family_question_overlap_heatmap", "Question Jaccard",
             "Tx triage questions"),
        ):
            matrix = _pair_matrix(primary_overlap, family_ids, column)
            add(
                stem,
                lambda matrix=matrix, label=label, human=human, stem=stem: exports.heatmap(
                    matrix,
                    row_labels=labels,
                    column_labels=labels,
                    title=f"Candidate family overlap: shared {human}",
                    subtitle=(
                        f"{cut_note}. Jaccard similarity of the families' {human} "
                        "sets; the diagonal is not shown. High overlap is evidence "
                        "for review, not a merge instruction"
                    ),
                    source=SOURCE_NOTE,
                    path=charts_dir / f"{stem}.png",
                    value_label=label,
                    annotate=shown <= 16,
                ),
            )

    # 6. Internal vs external edge percentage -----------------------------------------
    if not primary_cohesion.empty:
        eligible = primary_cohesion.loc[
            primary_cohesion["InternalEdgePercentage"].notna()
        ].copy()
        eligible["label"] = [
            _short(primary_names.get(row.FamilyId, row.FamilyId), 40)
            + f" (n={int(row.PathwayCount)})"
            for row in eligible.itertuples()
        ]
        add(
            "family_internal_vs_external_edges",
            lambda: exports.stacked_share_barh(
                eligible,
                label_column="label",
                primary_column="InternalEdgePercentage",
                primary_label="Internal to the candidate family",
                secondary_label="Leaving the candidate family",
                title=(
                    "Candidate family cohesion: internal vs external edges "
                    f"({primary.strategy})"
                ),
                subtitle=(
                    f"Top 30 of {len(eligible):,} families with measurable edges. "
                    f"Internal share = internal / (internal + outgoing) edges"
                ),
                source=SOURCE_NOTE,
                path=charts_dir / "family_internal_vs_external_edges.png",
                top_n=30,
            ),
        )

    # 7. Boundary pathway ranking -------------------------------------------------------
    if not primary_boundary.empty:
        ranking = primary_boundary.loc[
            primary_boundary["BoundaryClassification"] != "internal pathway"
        ].copy()
        if not ranking.empty:
            ranking["label"] = [
                _short(f"{row.PathwayID} {row.PathwayTitle}", 52)
                + f" [{row.BoundaryClassification.split()[0]}]"
                for row in ranking.itertuples()
            ]
            hub_count = int(
                (ranking["BoundaryClassification"] == "cross-family hub").sum()
            )
            add(
                "boundary_pathway_ranking",
                lambda: exports.barh_top_n(
                    ranking,
                    label_column="label",
                    value_column="ExternalDegree",
                    top_n=30,
                    title="Boundary pathways ranked by external degree",
                    subtitle=(
                        f"Top 30 of {len(ranking):,} boundary pathways "
                        f"({hub_count} classified as cross-family hubs). External degree "
                        f"counts distinct non-member pathways adjacent in either direction"
                    ),
                    source=SOURCE_NOTE + " Classification is structural, not clinical.",
                    path=charts_dir / "boundary_pathway_ranking.png",
                    xlabel="Distinct non-member pathways adjacent (external degree)",
                ),
            )

    # 8. Community-level network view --------------------------------------------------
    if not primary_cohesion.empty and not primary_overlap.empty:
        nodes = primary_cohesion[["FamilyId", "PathwayCount"]].rename(
            columns={"FamilyId": "family_id"}
        )
        nodes["label"] = [
            _short(primary_names.get(row.family_id, row.family_id), 24)
            for row in nodes.itertuples()
        ]
        edges = primary_overlap[
            ["FamilyA", "FamilyB", "TransitionsAtoB", "TransitionsBtoA"]
        ].copy()
        edges["weight"] = edges["TransitionsAtoB"] + edges["TransitionsBtoA"]
        edges = edges.loc[edges["weight"] > 0].rename(
            columns={"FamilyA": "source", "FamilyB": "target"}
        )
        add(
            "candidate_family_network",
            lambda: exports.community_graph(
                nodes,
                edges,
                node_label_column="label",
                node_size_column="PathwayCount",
                edge_weight_column="weight",
                title=(
                    "Candidate families and the transfers between them "
                    f"({primary.strategy})"
                ),
                subtitle=(
                    "One node per candidate family, sized by pathway count; edge "
                    "width is transfer transitions. Aggregated deliberately: the "
                    "pathway-level graph is not readable as a single diagram"
                ),
                source=SOURCE_NOTE,
                path=graphs_dir / "candidate_family_network.png",
            ),
        )

    # 9. Shared-core feature frequency --------------------------------------------------
    if not shared_core.empty:
        by_type = (
            shared_core.groupby("FeatureTypeLabel")
            .agg(features=("FeatureId", "nunique"), max_families=("FamilyCount", "max"))
            .reset_index()
            .sort_values("features", ascending=False)
        )
        add(
            "shared_core_feature_frequency",
            lambda: exports.bar_distribution(
                by_type["FeatureTypeLabel"].tolist(),
                by_type["features"].tolist(),
                title="Shared-core candidate features by feature type",
                subtitle=(
                    f"Features used by {int(shared_core['FamilyCount'].min())}+ candidate "
                    f"families. Evidence only: this does not conclude that any feature "
                    f"belongs in a shared network"
                ),
                source=SOURCE_NOTE,
                path=charts_dir / "shared_core_feature_frequency.png",
                xlabel="Feature type",
                ylabel="Shared-core candidate features",
            ),
        )
        top_features = shared_core.nlargest(25, ["FamilyCount", "PathwayCount"]).copy()
        top_features["label"] = [
            _short(f"{row.FeatureId} {row.Description}".strip(), 48)
            for row in top_features.itertuples()
        ]
        add(
            "shared_core_top_features",
            lambda: exports.barh_top_n(
                top_features,
                label_column="label",
                value_column="FamilyCount",
                top_n=25,
                title="Most broadly shared features across candidate families",
                subtitle=(
                    "Candidate families using each feature. A feature here would need "
                    "duplicating across every family that uses it, or a shared structure"
                ),
                source=SOURCE_NOTE,
                path=charts_dir / "shared_core_top_features.png",
                xlabel="Candidate families using the feature",
            ),
        )

    # 10. NHS-native vs graph-derived vs hybrid comparison -------------------------------
    if not strategy_comparison.empty:
        usable = strategy_comparison.loc[strategy_comparison["FamilyCount"] > 1].copy()
        usable["basis_label"] = usable["FamilyBasis"].map(
            {
                "nhs_native": "NHS-native",
                "graph_derived": "Graph-derived",
                "hybrid": "Hybrid",
            }
        ).fillna(usable["FamilyBasis"])
        usable["label"] = usable["strategy"].str.replace("_", " ", regex=False)
        add(
            "strategy_cohesion_vs_family_count",
            lambda: exports.scatter_by_category(
                usable,
                x_column="MedianInternalEdgePercentage",
                y_column="FamilyCount",
                category_column="basis_label",
                label_column="label",
                title="Candidate family strategies: cohesion against family count",
                subtitle=(
                    "Each point is one strategy. Further right is more self-contained in "
                    "the transfer graph; higher is more families. No strategy is selected"
                ),
                source=SOURCE_NOTE,
                path=charts_dir / "strategy_cohesion_vs_family_count.png",
                xlabel="Median internal-edge percentage across the strategy's families",
                ylabel="Number of candidate families",
            ),
        )

        comparison_subset = usable.loc[
            usable["FamilyBasis"].isin(["nhs_native", "graph_derived"])
        ].copy()
        if not comparison_subset.empty:
            comparison_subset = comparison_subset.sort_values(
                "MedianInternalEdgePercentage", ascending=False
            )
            comparison_subset["label"] = comparison_subset["strategy"].str.replace(
                "_", " ", regex=False
            )
            add(
                "native_vs_graph_comparison",
                lambda: exports.grouped_barh(
                    comparison_subset,
                    label_column="label",
                    value_columns=[
                        "MedianInternalEdgePercentage",
                        "MedianBoundaryPathwayPercentage",
                    ],
                    series_labels=[
                        "Median internal-edge %",
                        "Median boundary-pathway %",
                    ],
                    title="NHS-native groupings vs graph-derived communities",
                    subtitle=(
                        "Graph-derived communities are cohesive by construction; NHS "
                        "groupings are clinically recognisable. Neither is preferred here"
                    ),
                    source=SOURCE_NOTE,
                    path=charts_dir / "native_vs_graph_comparison.png",
                    xlabel="Percentage",
                ),
            )

    # 11. Community-detection method agreement -------------------------------------------
    if not community_comparison.empty:
        available = community_comparison.loc[
            community_comparison["available"] & (community_comparison["community_count"] > 0)
        ].copy()
        if not available.empty:
            available = available.sort_values("modularity", ascending=False)
            available["label"] = available["method"].str.replace("_", " ", regex=False)
            add(
                "community_method_comparison",
                lambda: exports.barh_top_n(
                    available,
                    label_column="label",
                    value_column="community_count",
                    top_n=len(available),
                    title="Communities found per detection method",
                    subtitle=(
                        "Several algorithms are run deliberately: no single community "
                        "algorithm is treated as ground truth"
                    ),
                    source=SOURCE_NOTE,
                    path=charts_dir / "community_method_comparison.png",
                    xlabel="Communities found",
                ),
            )

    # 12. Native grouping sizes -----------------------------------------------------------
    if not native_candidates.empty:
        sg = native_candidates.loc[
            native_candidates["strategy"] == "native_symptom_group"
        ].nlargest(25, "pathway_count").copy()
        if not sg.empty:
            sg["label"] = [_short(row.family_label, 44) for row in sg.itertuples()]
            add(
                "native_symptom_group_sizes",
                lambda: exports.barh_top_n(
                    sg,
                    label_column="label",
                    value_column="pathway_count",
                    top_n=25,
                    title="Largest NHS symptom groups as candidate families",
                    subtitle=(
                        "Baseline NHS-native grouping. Symptom group is NULL for 150 "
                        "active pathways, which are held in an explicit UNASSIGNED family"
                    ),
                    source=SOURCE_NOTE,
                    path=charts_dir / "native_symptom_group_sizes.png",
                    xlabel="Active pathways",
                ),
            )

    LOGGER.info("Rendered %d of the Phase 2 figures", len(written))
    return written
