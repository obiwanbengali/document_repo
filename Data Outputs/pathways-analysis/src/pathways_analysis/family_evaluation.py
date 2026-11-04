"""Phase 2: family cohesion, split testing, quality scorecard and strategy comparison.

Sections 6, 12, 17 and 18 of the Phase 2 brief.

Metric definitions
------------------
Every metric produced here is a **derived metric under a stated definition**, not a
measurement. The definitions are given once, in :data:`METRIC_DEFINITIONS`, and are
written into ``outputs/phase2/reports/metric_definitions.csv`` so that no number in the
Phase 2 evidence base is quoted without its definition.

The internal-edge percentage keeps the Phase 1 definition -- ``internal / (internal +
outgoing) * 100`` -- so cohesion figures are comparable across the two phases. Where
Phase 2 adds a metric Phase 1 did not have, the definition says what it counts and what
it deliberately does not.

Scoring
-------
The scorecard keeps every component metric visible. A composite score is available but
disabled by default, because a single number invites exactly the kind of automatic
"winner" selection the Phase 2 brief rules out.
"""

from __future__ import annotations

import logging
from typing import Final, Iterable, Mapping, Sequence

import networkx as nx
import numpy as np
import pandas as pd

from . import graph as graph_tools
from .family_config import FamilyDiscoveryConfig
from .family_features import (
    CandidateFamilySet,
    PairwiseSimilarity,
    PathwayFeatureModel,
)

LOGGER: Final = logging.getLogger(__name__)

#: Definition of every derived metric Phase 2 emits for a family. Written out as a
#: table so a reader of any Phase 2 CSV can look up what a column counts.
METRIC_DEFINITIONS: Final[tuple[tuple[str, str, str], ...]] = (
    (
        "PathwayCount",
        "measured",
        "Distinct pathways assigned to the family. A pathway may be counted in several "
        "families of the same strategy where that strategy is overlapping.",
    ),
    (
        "UniqueQuestionCount",
        "derived",
        "Distinct Tx triage questions referenced by the triage logic of the family's "
        "pathways. Cx care-advice and Dx disposition node references are excluded, "
        "because only Tx nodes are answerable questions.",
    ),
    (
        "UniqueSymptomDiscriminatorCount",
        "derived",
        "Distinct SdId values reachable through an answer that one of the family's "
        "pathways offers.",
    ),
    (
        "UniqueSnomedCount",
        "derived",
        "Distinct SNOMED concept ids assigned to an answer that one of the family's "
        "pathways offers.",
    ),
    (
        "UniqueDispositionCount",
        "derived",
        "Distinct disposition codes the family can reach, unioned over both routes: a "
        "T1-T4 transfer resolving to a DispositionCode, and a Dx disposition node in "
        "the pathway's own triage logic.",
    ),
    (
        "InternalEdges",
        "derived",
        "Directed pathway-transfer edges whose source and target are both family "
        "members. Self loops count as internal.",
    ),
    (
        "ExternalEdges",
        "derived",
        "Directed edges leaving the family: source is a member, target is not. Targets "
        "outside the family-membership scope (an archived pathway taking part in a "
        "resolved transfer) count as external rather than being dropped.",
    ),
    (
        "ExternalEdgesIncoming",
        "derived",
        "Directed edges entering the family from a non-member.",
    ),
    (
        "InternalEdgePercentage",
        "derived",
        "internal / (internal + external outgoing) * 100. The share of edges leaving "
        "the family's pathways that stay inside the family. NaN when the family's "
        "pathways have no outgoing or internal edges at all, rather than a misleading "
        "0 or 100. Same definition as Phase 1.",
    ),
    (
        "ExternalEdgePercentage",
        "derived",
        "100 - InternalEdgePercentage.",
    ),
    (
        "AverageInternalDegree",
        "derived",
        "Mean over the family's pathways of the number of distinct family members the "
        "pathway is adjacent to in either direction. Self loops excluded, since a "
        "pathway is not its own neighbour.",
    ),
    (
        "AverageExternalDegree",
        "derived",
        "Mean over the family's pathways of the number of distinct non-member pathways "
        "the pathway is adjacent to in either direction.",
    ),
    (
        "NumberOfBoundaryPathways",
        "derived",
        "Family members with at least one edge, in either direction, to a non-member.",
    ),
    (
        "PercentageBoundaryPathways",
        "derived",
        "NumberOfBoundaryPathways / PathwayCount * 100.",
    ),
    (
        "SharedQuestionPercentage",
        "derived",
        "Share of the family's unique Tx questions that are used by at least two of "
        "the family's pathways. Measures internal re-use, i.e. how much of the "
        "family's question vocabulary is genuinely shared rather than pathway-specific. "
        "It is NOT a measure of sharing with other families -- that is the overlap "
        "matrix.",
    ),
    (
        "SharedSdPercentage",
        "derived",
        "Share of the family's unique symptom discriminators used by at least two of "
        "its pathways.",
    ),
    (
        "SharedSnomedPercentage",
        "derived",
        "Share of the family's unique SNOMED concepts used by at least two of its "
        "pathways.",
    ),
    (
        "MeanPairwiseQuestionJaccard",
        "derived",
        "Mean question-set Jaccard similarity over all pairs of the family's pathways. "
        "Pairs sharing nothing contribute 0, so a family of unrelated pathways with one "
        "similar pair does not look cohesive.",
    ),
    (
        "MeanPairwiseSdJaccard",
        "derived",
        "As above, over symptom-discriminator sets.",
    ),
    (
        "MeanPairwiseSnomedJaccard",
        "derived",
        "As above, over SNOMED concept sets.",
    ),
    (
        "DominantSymptomGroupShare",
        "derived",
        "Share of the family's pathways carrying the family's most common "
        "SymptomGroupId. Pathways with no symptom group are counted in the "
        "denominator, so a family of mostly-unclassified pathways cannot score highly.",
    ),
    (
        "DominantClinicalAreaShare",
        "derived",
        "Share of the family's pathways mapped to the family's most common clinical "
        "area. Clinical areas overlap, so these shares do not sum to 1 across areas.",
    ),
    (
        "AmbiguityScore",
        "derived",
        "Per pathway: second-best family affinity divided by best family affinity, "
        "under the weights in routing.weights. 0 means an unambiguous single-family "
        "association; 1 means two families are equally plausible.",
    ),
    (
        "MaxFeatureJaccard",
        "derived",
        "Per family pair: the largest of the question, symptom-discriminator, SNOMED "
        "and disposition Jaccard values.",
    ),
    (
        "MaxDiscriminatingJaccard",
        "derived",
        "The same maximum with dispositions excluded. Under 200 disposition codes "
        "exist and most families reach a similar subset, so disposition Jaccard has the "
        "highest median of any dimension and cannot distinguish family pairs. This is "
        "the measure the overlap band is read from by default "
        "(overlap_thresholds.band_measure), and the one the scorecard's overlap "
        "columns aggregate.",
    ),
    (
        "MaxOverlapWithAnotherFamily",
        "derived",
        "Per family: the largest overlap with any other family of the same strategy, "
        "measured on whichever of the two maxima above configuration selects. Reported "
        "alongside MeanOverlapWithOtherFamilies because one very similar neighbour and "
        "many slightly similar ones are different problems.",
    ),
    (
        "SizeBalanceVsStrategyMedian",
        "derived",
        "PathwayCount divided by the median family size of the same strategy. Above 1 "
        "means the family is larger than typical for its strategy.",
    ),
    (
        "DuplicationIfFederated",
        "derived",
        "Per shared-core candidate feature: FamilyCount - 1, i.e. how many extra copies "
        "the feature would need if every family using it held its own. A structural "
        "count, not a sizing estimate; sizing is Phase 3.",
    ),
)


# ======================================================================================
# Cohesion
# ======================================================================================
def cohesion_for_group(
    members: Iterable[str],
    model: PathwayFeatureModel,
    *,
    similarity: PairwiseSimilarity | None = None,
) -> dict[str, float]:
    """Compute the Phase 2 section 6 cohesion metrics for one set of pathways.

    Used for candidate families, and again for hypothetical merges and splits, so that
    a before/after comparison is guaranteed to use an identical definition.

    Args:
        members: Pathway keys in the group.
        model: The feature model.
        similarity: Optional pre-computed pairwise similarity. When supplied, the mean
            pairwise Jaccard columns are populated; otherwise they are NaN.

    Returns:
        Mapping of metric name to value. See :data:`METRIC_DEFINITIONS`.
    """
    member_set = {key for key in members}
    graph = model.pathway_graph
    scope = set(model.scope)

    internal = outgoing = incoming = 0
    internal_weight = outgoing_weight = 0
    internal_degrees: list[int] = []
    external_degrees: list[int] = []
    boundary_pathways = 0

    for node in sorted(member_set):
        if node not in graph:
            internal_degrees.append(0)
            external_degrees.append(0)
            continue
        internal_neighbours: set[str] = set()
        external_neighbours: set[str] = set()
        for _, target, data in graph.out_edges(node, data=True):
            weight = int(data.get(graph_tools.WEIGHT_ATTRIBUTE, 0) or 0)
            if target in member_set:
                internal += 1
                internal_weight += weight
                if target != node:
                    internal_neighbours.add(target)
            else:
                outgoing += 1
                outgoing_weight += weight
                external_neighbours.add(target)
        for source, _, _ in graph.in_edges(node, data=True):
            if source in member_set:
                if source != node:
                    internal_neighbours.add(source)
            else:
                incoming += 1
                external_neighbours.add(source)
        internal_degrees.append(len(internal_neighbours))
        external_degrees.append(len(external_neighbours))
        if external_neighbours:
            boundary_pathways += 1

    boundary_total = internal + outgoing
    internal_percentage = (
        round(100.0 * internal / boundary_total, 3) if boundary_total else float("nan")
    )

    result: dict[str, float] = {
        "PathwayCount": len(member_set),
        "PathwaysInScope": len(member_set & scope),
        "InternalEdges": internal,
        "ExternalEdges": outgoing,
        "ExternalEdgesIncoming": incoming,
        "InternalTransitionCount": internal_weight,
        "ExternalTransitionCount": outgoing_weight,
        "InternalEdgePercentage": internal_percentage,
        "ExternalEdgePercentage": (
            round(100.0 - internal_percentage, 3)
            if pd.notna(internal_percentage)
            else float("nan")
        ),
        "AverageInternalDegree": (
            round(float(np.mean(internal_degrees)), 3) if internal_degrees else 0.0
        ),
        "AverageExternalDegree": (
            round(float(np.mean(external_degrees)), 3) if external_degrees else 0.0
        ),
        "NumberOfBoundaryPathways": boundary_pathways,
        "PercentageBoundaryPathways": (
            round(100.0 * boundary_pathways / len(member_set), 3)
            if member_set
            else float("nan")
        ),
    }

    for dimension, count_name, shared_name in (
        ("question", "UniqueQuestionCount", "SharedQuestionPercentage"),
        ("symptom_discriminator", "UniqueSymptomDiscriminatorCount", "SharedSdPercentage"),
        ("snomed", "UniqueSnomedCount", "SharedSnomedPercentage"),
        ("disposition", "UniqueDispositionCount", "SharedDispositionPercentage"),
    ):
        frame = getattr(model.maps, dimension)
        if frame.empty:
            result[count_name] = 0
            result[shared_name] = float("nan")
            continue
        subset = frame.loc[frame["pathway_key"].isin(member_set)]
        if subset.empty:
            result[count_name] = 0
            result[shared_name] = float("nan")
            continue
        per_feature = subset.groupby("feature_id")["pathway_key"].nunique()
        result[count_name] = int(len(per_feature))
        result[shared_name] = round(
            100.0 * float((per_feature >= 2).sum()) / len(per_feature), 3
        )

    for dimension, column in (
        ("question", "MeanPairwiseQuestionJaccard"),
        ("symptom_discriminator", "MeanPairwiseSdJaccard"),
        ("snomed", "MeanPairwiseSnomedJaccard"),
        ("disposition", "MeanPairwiseDispositionJaccard"),
    ):
        if similarity is None:
            result[column] = float("nan")
        else:
            result[column] = similarity.mean_within(dimension, member_set)

    return result


def _metadata_shares(
    members: Iterable[str],
    model: PathwayFeatureModel,
) -> dict[str, object]:
    """Return dominant metadata values and their shares for a set of pathways.

    Dominance is reported as a share of the family's pathways, including pathways with
    no value, so a family of mostly-unclassified pathways cannot appear well-labelled.
    """
    member_set = set(members)
    features = model.features.loc[model.features["PathwayKey"].isin(member_set)]
    total = max(len(features), 1)

    result: dict[str, object] = {}

    sg_counts = features["SymptomGroupDescription"].dropna().value_counts()
    sg_ids = features["SymptomGroupId"].dropna().value_counts()
    result["DominantSymptomGroup"] = sg_counts.index[0] if len(sg_counts) else ""
    result["DominantSymptomGroupId"] = int(sg_ids.index[0]) if len(sg_ids) else -1
    result["DominantSymptomGroupShare"] = (
        round(float(sg_counts.iloc[0]) / total, 4) if len(sg_counts) else 0.0
    )
    result["DistinctSymptomGroups"] = int(features["SymptomGroupId"].nunique(dropna=True))
    result["PrimarySymptomGroups"] = " | ".join(str(value) for value in sg_counts.index[:3])

    area_counts = _exploded_counts(features, "ClinicalAreas")
    result["DominantClinicalArea"] = area_counts.index[0] if len(area_counts) else ""
    result["DominantClinicalAreaShare"] = (
        round(float(area_counts.iloc[0]) / total, 4) if len(area_counts) else 0.0
    )
    result["DistinctClinicalAreas"] = int(len(area_counts))
    result["PrimaryClinicalAreas"] = " | ".join(str(value) for value in area_counts.index[:3])

    group_counts = _exploded_counts(features, "AreaGroups")
    result["DominantAreaGroup"] = group_counts.index[0] if len(group_counts) else ""
    result["DominantAreaGroupShare"] = (
        round(float(group_counts.iloc[0]) / total, 4) if len(group_counts) else 0.0
    )

    trauma_counts = features["TraumaClassification"].value_counts()
    result["DominantTraumaClassification"] = (
        trauma_counts.index[0] if len(trauma_counts) else ""
    )
    result["TraumaTaggedPathways"] = int(
        (~features["TraumaClassification"].isin(["unspecified"])).sum()
    )
    age_counts = features["AgeClassification"].value_counts()
    result["DominantAgeClassification"] = age_counts.index[0] if len(age_counts) else ""
    result["PaediatricOnlyPathways"] = int(
        (features["AgeClassification"] == "paediatric_only").sum()
    )
    result["AdultOnlyPathways"] = int((features["AgeClassification"] == "adult_only").sum())
    return result


def _exploded_counts(features: pd.DataFrame, column: str) -> pd.Series:
    """Count pipe-joined multi-values in a column, one count per distinct value."""
    if column not in features.columns or features.empty:
        return pd.Series(dtype="int64")
    exploded = (
        features[column]
        .fillna("")
        .astype(str)
        .str.split("|")
        .explode()
        .str.strip()
    )
    exploded = exploded.loc[exploded != ""]
    return exploded.value_counts()


def family_cohesion(
    candidate_sets: Sequence[CandidateFamilySet],
    model: PathwayFeatureModel,
    *,
    similarity: PairwiseSimilarity,
) -> pd.DataFrame:
    """Compute cohesion for every family of every candidate strategy (section 6)."""
    records = []
    for candidate in candidate_sets:
        families = candidate.families()
        labels = candidate.labels()
        for family_id in sorted(families):
            members = families[family_id]
            metrics = cohesion_for_group(members, model, similarity=similarity)
            metadata = _metadata_shares(members, model)
            records.append(
                {
                    "strategy": candidate.strategy,
                    "FamilyBasis": candidate.basis,
                    "FamilyId": family_id,
                    "FamilyLabel": labels.get(family_id, family_id),
                    "StrategyIsOverlapping": candidate.overlapping,
                    **metrics,
                    **metadata,
                }
            )
    if not records:
        return pd.DataFrame()
    frame = pd.DataFrame(records)
    return frame.sort_values(
        ["strategy", "PathwayCount", "FamilyId"],
        ascending=[True, False, True],
        ignore_index=True,
    )


def metric_definition_table() -> pd.DataFrame:
    """Return :data:`METRIC_DEFINITIONS` as a table for export."""
    return pd.DataFrame(
        [
            {"metric": metric, "category": category, "definition": definition}
            for metric, category, definition in METRIC_DEFINITIONS
        ]
    )


# ======================================================================================
# Split analysis (section 12)
# ======================================================================================
def split_candidates(
    candidate_sets: Sequence[CandidateFamilySet],
    model: PathwayFeatureModel,
    cohesion: pd.DataFrame,
    *,
    config: FamilyDiscoveryConfig,
    similarity: PairwiseSimilarity,
) -> pd.DataFrame:
    """Test whether large or internally weak families split naturally (section 12).

    Trigger conditions, any one of which puts a family under test:

    * ``PathwayCount >= family_size.split_review_size`` -- large enough that a split is
      worth measuring.
    * ``InternalEdgePercentage < hybrid_b.weak_cohesion_internal_edge_pct`` -- the
      family's pathways mostly transfer outside it.
    * ``MeanPairwiseSdJaccard < hybrid_a.clinical_cohesion_threshold`` -- weak shared
      symptom-discriminator vocabulary.
    * ``PercentageBoundaryPathways >= 75`` -- most members sit on a boundary.
    * bimodal clinical-area composition: the dominant clinical area covers less than
      half the family and the family spans three or more areas.

    Two split methods are tested for each triggered family and reported side by side:

    * ``graph_subcommunity`` -- community detection on the family's induced subgraph.
    * ``dominant_symptom_group`` -- partition by the pathway's SymptomGroupId.

    Cohesion is recomputed for every resulting part, so before/after is measured.

    **No split is recommended.** A split that improves internal-edge percentage may
    still separate pathways a clinician would keep together.
    """
    if cohesion.empty:
        return pd.DataFrame()

    records = []
    cohesion_indexed = cohesion.set_index(["strategy", "FamilyId"])

    for candidate in candidate_sets:
        families = candidate.families()
        labels = candidate.labels()
        for family_id in sorted(families):
            members = families[family_id]
            key = (candidate.strategy, family_id)
            if key not in cohesion_indexed.index:
                continue
            row = cohesion_indexed.loc[key]
            triggers = _split_triggers(row, config)
            if not triggers or len(members) < 2 * config.minimum_split_part_size:
                continue

            for method, parts in _split_methods(members, model, candidate.strategy).items():
                usable = {
                    name: part
                    for name, part in parts.items()
                    if len(part) >= config.minimum_split_part_size
                }
                if len(usable) < 2:
                    continue
                part_metrics = [
                    cohesion_for_group(part, model, similarity=similarity)
                    for part in usable.values()
                ]
                sizes = [len(part) for part in usable.values()]
                weighted_internal = _weighted_mean(
                    [metrics["InternalEdgePercentage"] for metrics in part_metrics], sizes
                )
                weighted_boundary = _weighted_mean(
                    [metrics["PercentageBoundaryPathways"] for metrics in part_metrics], sizes
                )
                weighted_sd = _weighted_mean(
                    [metrics["MeanPairwiseSdJaccard"] for metrics in part_metrics], sizes
                )
                covered = set().union(*usable.values()) if usable else set()
                records.append(
                    {
                        "strategy": candidate.strategy,
                        "FamilyId": family_id,
                        "FamilyLabel": labels.get(family_id, family_id),
                        "SplitMethod": method,
                        "SplitTriggers": "; ".join(triggers),
                        "PathwayCountBefore": len(members),
                        "PartCount": len(usable),
                        "PartSizes": " | ".join(
                            str(size) for size in sorted(sizes, reverse=True)
                        ),
                        "PathwaysRetainedInParts": len(covered),
                        "PathwaysBelowMinimumPartSize": len(members) - len(covered),
                        "InternalEdgePercentageBefore": _as_float(
                            row["InternalEdgePercentage"]
                        ),
                        "InternalEdgePercentageAfterWeighted": weighted_internal,
                        "InternalEdgePercentageDelta": _delta(
                            weighted_internal, _as_float(row["InternalEdgePercentage"])
                        ),
                        "PercentageBoundaryPathwaysBefore": _as_float(
                            row["PercentageBoundaryPathways"]
                        ),
                        "PercentageBoundaryPathwaysAfterWeighted": weighted_boundary,
                        "PercentageBoundaryPathwaysDelta": _delta(
                            weighted_boundary, _as_float(row["PercentageBoundaryPathways"])
                        ),
                        "MeanPairwiseSdJaccardBefore": _as_float(row["MeanPairwiseSdJaccard"]),
                        "MeanPairwiseSdJaccardAfterWeighted": weighted_sd,
                        "MeanPairwiseSdJaccardDelta": _delta(
                            weighted_sd, _as_float(row["MeanPairwiseSdJaccard"])
                        ),
                        "PartLabels": " | ".join(str(name) for name in usable),
                        "StructuralVerdict": _split_verdict(
                            _delta(weighted_internal, _as_float(row["InternalEdgePercentage"])),
                            _delta(weighted_sd, _as_float(row["MeanPairwiseSdJaccard"])),
                        ),
                        "Recommendation": "not made -- split decisions require clinical review",
                    }
                )
    if not records:
        return pd.DataFrame()
    return pd.DataFrame(records).sort_values(
        ["strategy", "PathwayCountBefore", "FamilyId", "SplitMethod"],
        ascending=[True, False, True, True],
        ignore_index=True,
    )


def _split_triggers(row: pd.Series, config: FamilyDiscoveryConfig) -> list[str]:
    """Return the trigger reasons that put a family under split review."""
    triggers = []
    if row["PathwayCount"] >= config.split_review_size:
        triggers.append(f"size {int(row['PathwayCount'])} >= {config.split_review_size}")
    internal = _as_float(row["InternalEdgePercentage"])
    if pd.notna(internal) and internal < config.hybrid_b_weak_cohesion_internal_edge_pct:
        triggers.append(
            f"internal-edge {internal:.1f}% < "
            f"{config.hybrid_b_weak_cohesion_internal_edge_pct:.0f}%"
        )
    sd_cohesion = _as_float(row["MeanPairwiseSdJaccard"])
    if pd.notna(sd_cohesion) and sd_cohesion < config.hybrid_a_clinical_cohesion_threshold:
        triggers.append(
            f"mean SD Jaccard {sd_cohesion:.3f} < "
            f"{config.hybrid_a_clinical_cohesion_threshold:.2f}"
        )
    boundary = _as_float(row["PercentageBoundaryPathways"])
    if pd.notna(boundary) and boundary >= 75.0:
        triggers.append(f"boundary pathways {boundary:.0f}% >= 75%")
    if (
        _as_float(row["DominantClinicalAreaShare"]) < 0.5
        and int(row["DistinctClinicalAreas"]) >= 3
    ):
        triggers.append(
            f"clinical-area composition spread over {int(row['DistinctClinicalAreas'])} "
            "areas with no majority"
        )
    return triggers


def _split_methods(
    members: set[str],
    model: PathwayFeatureModel,
    strategy: str,
) -> dict[str, dict[str, set[str]]]:
    """Return candidate partitions of a family, keyed by split method."""
    methods: dict[str, dict[str, set[str]]] = {}

    subgraph = model.pathway_graph.subgraph(members)
    if subgraph.number_of_nodes() >= 2:
        projection = graph_tools.undirected_projection(nx.DiGraph(subgraph))
        try:
            membership = graph_tools.partition_undirected(projection, "louvain")
        except Exception as exc:  # noqa: BLE001 - a failed split test must not stop the run
            LOGGER.debug("Subcommunity split failed for %s: %s", strategy, exc)
            membership = {}
        if membership:
            parts: dict[str, set[str]] = {}
            for node, community_id in membership.items():
                parts.setdefault(f"subcommunity_{community_id}", set()).add(node)
            # Members absent from the projection (isolated inside the family) form
            # their own part rather than being silently lost.
            missing = members - set(membership)
            if missing:
                parts["subcommunity_isolated"] = missing
            methods["graph_subcommunity"] = parts

    features = model.features.loc[model.features["PathwayKey"].isin(members)]
    sg_parts: dict[str, set[str]] = {}
    for row in features.itertuples():
        key = (
            f"sg_{int(row.SymptomGroupId)}"
            if pd.notna(row.SymptomGroupId)
            else "sg_unassigned"
        )
        sg_parts.setdefault(key, set()).add(row.PathwayKey)
    if len(sg_parts) >= 2:
        methods["dominant_symptom_group"] = sg_parts

    return methods


def _split_verdict(internal_delta: float, sd_delta: float) -> str:
    """Describe the structural effect of a split without recommending it."""
    if pd.isna(internal_delta):
        return "not measurable"
    improves_graph = internal_delta > 0
    improves_features = pd.notna(sd_delta) and sd_delta > 0
    if improves_graph and improves_features:
        return "split improves both graph cohesion and shared-SD cohesion"
    if improves_graph:
        return "split improves graph cohesion only"
    if improves_features:
        return "split improves shared-SD cohesion only"
    return "split improves neither measure"


def _weighted_mean(values: Sequence[float], weights: Sequence[int]) -> float:
    """Return the weight-weighted mean, ignoring NaN values."""
    usable = [
        (float(value), float(weight))
        for value, weight in zip(values, weights)
        if pd.notna(value) and weight > 0
    ]
    if not usable:
        return float("nan")
    total = sum(weight for _, weight in usable)
    return round(sum(value * weight for value, weight in usable) / total, 3)


def _delta(after: float, before: float) -> float:
    """Return ``after - before``, propagating NaN."""
    if pd.isna(after) or pd.isna(before):
        return float("nan")
    return round(float(after) - float(before), 3)


def _as_float(value: object) -> float:
    """Coerce a cell to float, mapping missing values to NaN."""
    if value is None or (not isinstance(value, str) and pd.isna(value)):
        return float("nan")
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return float("nan")


# ======================================================================================
# Quality scorecard (section 17)
# ======================================================================================
def family_quality_scorecard(
    cohesion: pd.DataFrame,
    overlap: pd.DataFrame,
    routing: pd.DataFrame,
    boundary: pd.DataFrame,
    *,
    config: FamilyDiscoveryConfig,
) -> pd.DataFrame:
    """Build the per-family quality scorecard (section 17).

    Every dimension stays a separate, named column. A composite score is appended only
    when ``composite_score.enabled`` is true in configuration, and even then all
    components remain present, because a single number hides which dimension is weak.

    Dimensions, each in its own raw units:

    * graph cohesion -- ``InternalEdgePercentage``
    * semantic cohesion -- ``MeanPairwiseQuestionJaccard``
    * symptom-discriminator cohesion -- ``MeanPairwiseSdJaccard``
    * SNOMED cohesion -- ``MeanPairwiseSnomedJaccard``
    * disposition cohesion -- ``SharedDispositionPercentage``
    * boundary complexity -- ``PercentageBoundaryPathways``
    * overlap with other families -- max and mean ``MaxFeatureJaccard`` for the family
    * routing ambiguity -- mean ``AmbiguityScore`` over the family's pathways
    * size balance -- ``PathwayCount`` divided by the strategy's median family size
    """
    if cohesion.empty:
        return pd.DataFrame()

    scorecard = cohesion[
        [
            "strategy", "FamilyBasis", "FamilyId", "FamilyLabel", "PathwayCount",
            "InternalEdgePercentage", "ExternalEdgePercentage",
            "MeanPairwiseQuestionJaccard", "MeanPairwiseSdJaccard",
            "MeanPairwiseSnomedJaccard", "SharedDispositionPercentage",
            "SharedQuestionPercentage", "SharedSdPercentage", "SharedSnomedPercentage",
            "PercentageBoundaryPathways", "NumberOfBoundaryPathways",
            "DominantSymptomGroupShare", "DominantClinicalAreaShare",
            "DistinctSymptomGroups", "DistinctClinicalAreas",
        ]
    ].copy()

    # Overlap: a family's strongest and average overlap with any other family in the
    # same strategy. Both are reported because one very similar neighbour and many
    # slightly similar neighbours are different problems.
    if not overlap.empty:
        # Read from the same measure the overlap band was computed on, so the scorecard
        # and high_overlap_family_pairs.csv never quote different numbers for the same
        # family pair. See family_overlap.classify_overlap.
        measure = (
            "MaxDiscriminatingJaccard"
            if "MaxDiscriminatingJaccard" in overlap.columns
            else "MaxFeatureJaccard"
        )
        long_overlap = pd.concat(
            [
                overlap[["strategy", "FamilyA", measure, "SharedPathways"]].rename(
                    columns={"FamilyA": "FamilyId"}
                ),
                overlap[["strategy", "FamilyB", measure, "SharedPathways"]].rename(
                    columns={"FamilyB": "FamilyId"}
                ),
            ],
            ignore_index=True,
        )
        aggregated = (
            long_overlap.groupby(["strategy", "FamilyId"])
            .agg(
                MaxOverlapWithAnotherFamily=(measure, "max"),
                MeanOverlapWithOtherFamilies=(measure, "mean"),
                FamiliesWithAnyOverlap=(measure, "size"),
                FamiliesSharingPathways=(
                    "SharedPathways",
                    lambda values: int((values > 0).sum()),
                ),
            )
            .reset_index()
        )
        aggregated["OverlapMeasureUsed"] = measure
        scorecard = scorecard.merge(aggregated, on=["strategy", "FamilyId"], how="left")
    else:
        for column in (
            "MaxOverlapWithAnotherFamily",
            "MeanOverlapWithOtherFamilies",
            "FamiliesWithAnyOverlap",
            "FamiliesSharingPathways",
        ):
            scorecard[column] = np.nan

    if not routing.empty:
        routing_aggregated = (
            routing.groupby(["strategy", "DominantFamilyId"])
            .agg(
                MeanRoutingAmbiguity=("AmbiguityScore", "mean"),
                PathwaysWithHighAmbiguity=(
                    "AmbiguityClassification",
                    lambda values: int((values == "high ambiguity").sum()),
                ),
            )
            .reset_index()
            .rename(columns={"DominantFamilyId": "FamilyId"})
        )
        scorecard = scorecard.merge(routing_aggregated, on=["strategy", "FamilyId"], how="left")
    else:
        scorecard["MeanRoutingAmbiguity"] = np.nan
        scorecard["PathwaysWithHighAmbiguity"] = np.nan

    if not boundary.empty:
        boundary_aggregated = (
            boundary.groupby(["strategy", "FamilyId"])
            .agg(
                CrossFamilyHubs=(
                    "BoundaryClassification",
                    lambda values: int((values == "cross-family hub").sum()),
                ),
                StrongBoundaryPathways=(
                    "BoundaryClassification",
                    lambda values: int((values == "strong boundary pathway").sum()),
                ),
            )
            .reset_index()
        )
        scorecard = scorecard.merge(
            boundary_aggregated, on=["strategy", "FamilyId"], how="left"
        )
    else:
        scorecard["CrossFamilyHubs"] = np.nan
        scorecard["StrongBoundaryPathways"] = np.nan

    median_sizes = scorecard.groupby("strategy")["PathwayCount"].transform("median")
    scorecard["SizeBalanceVsStrategyMedian"] = (
        scorecard["PathwayCount"] / median_sizes.replace(0, np.nan)
    ).round(3)

    scorecard["CompositeScoreEnabled"] = config.composite_score_enabled
    if config.composite_score_enabled:
        scorecard["CompositeScore"] = _composite_score(scorecard, config)
        scorecard["CompositeScoreWeights"] = ", ".join(
            f"{key}={value:g}" for key, value in sorted(config.composite_score_weights.items())
        )
    else:
        scorecard["CompositeScore"] = np.nan
        scorecard["CompositeScoreWeights"] = (
            "disabled -- set composite_score.enabled to compute one"
        )

    return scorecard.sort_values(
        ["strategy", "PathwayCount", "FamilyId"],
        ascending=[True, False, True],
        ignore_index=True,
    )


def _composite_score(
    scorecard: pd.DataFrame, config: FamilyDiscoveryConfig
) -> pd.Series:
    """Compute the optional composite score.

    Each component is min-max normalised **within its strategy**, because comparing an
    internal-edge percentage across a 224-family grouping and a 20-family grouping on a
    shared absolute scale would be meaningless. Components where higher is worse
    (boundary share, routing ambiguity) are inverted before weighting.

    The result is deliberately unitless and is documented as such: it ranks families
    within one strategy and carries no meaning across strategies.
    """
    weights = config.composite_score_weights
    components = {
        "graph_cohesion": ("InternalEdgePercentage", False),
        "symptom_discriminator_cohesion": ("MeanPairwiseSdJaccard", False),
        "snomed_cohesion": ("MeanPairwiseSnomedJaccard", False),
        "disposition_cohesion": ("SharedDispositionPercentage", False),
        "boundary_simplicity": ("PercentageBoundaryPathways", True),
        "routing_clarity": ("MeanRoutingAmbiguity", True),
    }
    total = pd.Series(0.0, index=scorecard.index)
    weight_total = 0.0
    for name, (column, invert) in components.items():
        weight = float(weights.get(name, 0.0))
        if weight <= 0 or column not in scorecard.columns:
            continue
        values = pd.to_numeric(scorecard[column], errors="coerce")
        normalised = values.groupby(scorecard["strategy"]).transform(_min_max)
        if invert:
            normalised = 1.0 - normalised
        total = total.add(normalised.fillna(0.0) * weight, fill_value=0.0)
        weight_total += weight
    if weight_total <= 0:
        return pd.Series(np.nan, index=scorecard.index)
    return (total / weight_total).round(4)


def _min_max(series: pd.Series) -> pd.Series:
    """Scale a series to 0..1, returning 0.5 where every value is identical."""
    low = series.min()
    high = series.max()
    if pd.isna(low) or pd.isna(high) or high == low:
        return pd.Series(0.5, index=series.index)
    return (series - low) / (high - low)


# ======================================================================================
# Strategy comparison (section 18)
# ======================================================================================
def strategy_comparison(
    candidate_sets: Sequence[CandidateFamilySet],
    cohesion: pd.DataFrame,
    overlap: pd.DataFrame,
    routing: pd.DataFrame,
    boundary: pd.DataFrame,
    model: PathwayFeatureModel,
) -> pd.DataFrame:
    """Compare NHS-native, graph-derived and hybrid strategies side by side (section 18).

    No strategy is selected. The comparison exists so a reviewer can see the trade
    each one makes: NHS-native groupings are clinically recognisable but may be weakly
    cohesive in the transfer graph; graph-derived communities are cohesive by
    construction but may not map onto anything a clinician recognises; hybrids sit in
    between and inherit both sets of caveats.

    "Clinically recognisable metadata composition" is reported as the mean dominant
    symptom-group share and the mean dominant clinical-area share across the strategy's
    families: a strategy whose families each sit largely inside one NHS grouping is
    easier to review than one whose families each span many.
    """
    if cohesion.empty:
        return pd.DataFrame()

    by_strategy = {candidate.strategy: candidate for candidate in candidate_sets}
    records = []
    for strategy, group in cohesion.groupby("strategy"):
        candidate = by_strategy.get(strategy)
        sizes = group["PathwayCount"]
        overlap_subset = (
            overlap.loc[overlap["strategy"] == strategy]
            if not overlap.empty
            else pd.DataFrame()
        )
        routing_subset = (
            routing.loc[routing["strategy"] == strategy]
            if not routing.empty
            else pd.DataFrame()
        )
        boundary_subset = (
            boundary.loc[boundary["strategy"] == strategy]
            if not boundary.empty
            else pd.DataFrame()
        )

        records.append(
            {
                "strategy": strategy,
                "FamilyBasis": group["FamilyBasis"].iloc[0],
                "Description": candidate.description if candidate else "",
                "IsOverlapping": bool(candidate.overlapping) if candidate else False,
                "FamilyCount": int(group["FamilyId"].nunique()),
                "PathwaysAssigned": int(candidate.pathway_count) if candidate else 0,
                "PathwaysInScope": len(model.scope),
                "MedianFamilySize": float(sizes.median()),
                "MeanFamilySize": round(float(sizes.mean()), 2),
                "MaxFamilySize": int(sizes.max()),
                "MinFamilySize": int(sizes.min()),
                "SingletonFamilies": int((sizes == 1).sum()),
                "FamiliesBelowFive": int((sizes < 5).sum()),
                "MedianInternalEdgePercentage": round(
                    float(group["InternalEdgePercentage"].median()), 2
                ),
                "MeanInternalEdgePercentage": round(
                    float(group["InternalEdgePercentage"].mean()), 2
                ),
                "MedianExternalEdgePercentage": round(
                    float(group["ExternalEdgePercentage"].median()), 2
                ),
                "MedianBoundaryPathwayPercentage": round(
                    float(group["PercentageBoundaryPathways"].median()), 2
                ),
                "MeanBoundaryPathwayPercentage": round(
                    float(group["PercentageBoundaryPathways"].mean()), 2
                ),
                "MeanPairwiseSdJaccard": round(
                    float(group["MeanPairwiseSdJaccard"].mean()), 4
                ),
                "MeanPairwiseQuestionJaccard": round(
                    float(group["MeanPairwiseQuestionJaccard"].mean()), 4
                ),
                "FamilyPairsWithAnyOverlap": int(len(overlap_subset)),
                "MeanFamilyPairOverlap": (
                    round(float(overlap_subset["MaxFeatureJaccard"].mean()), 4)
                    if not overlap_subset.empty else float("nan")
                ),
                "HighOverlapFamilyPairs": (
                    int((overlap_subset["OverlapBand"] == "high").sum())
                    if not overlap_subset.empty and "OverlapBand" in overlap_subset
                    else 0
                ),
                "MeanRoutingAmbiguity": (
                    round(float(routing_subset["AmbiguityScore"].mean()), 4)
                    if not routing_subset.empty else float("nan")
                ),
                "PercentageStrongSingleFamily": (
                    round(
                        100.0
                        * float(
                            (
                                routing_subset["AmbiguityClassification"]
                                == "strong single-family association"
                            ).sum()
                        )
                        / max(len(routing_subset), 1),
                        2,
                    )
                    if not routing_subset.empty else float("nan")
                ),
                "PercentageHighAmbiguity": (
                    round(
                        100.0
                        * float(
                            (
                                routing_subset["AmbiguityClassification"]
                                == "high ambiguity"
                            ).sum()
                        )
                        / max(len(routing_subset), 1),
                        2,
                    )
                    if not routing_subset.empty else float("nan")
                ),
                "CrossFamilyHubs": (
                    int((boundary_subset["BoundaryClassification"] == "cross-family hub").sum())
                    if not boundary_subset.empty else 0
                ),
                "MeanDominantSymptomGroupShare": round(
                    float(group["DominantSymptomGroupShare"].mean()), 4
                ),
                "MeanDominantClinicalAreaShare": round(
                    float(group["DominantClinicalAreaShare"].mean()), 4
                ),
                "MeanDistinctSymptomGroupsPerFamily": round(
                    float(group["DistinctSymptomGroups"].mean()), 2
                ),
                "ClinicallyRecognisableMetadataNote": _recognisability_note(group),
            }
        )
    return pd.DataFrame(records).sort_values(
        ["FamilyBasis", "strategy"], ignore_index=True
    )


def _recognisability_note(group: pd.DataFrame) -> str:
    """Summarise, factually, how closely a strategy's families track NHS metadata."""
    sg_share = float(group["DominantSymptomGroupShare"].mean())
    area_share = float(group["DominantClinicalAreaShare"].mean())
    return (
        f"mean dominant symptom-group share {sg_share:.2f}, "
        f"mean dominant clinical-area share {area_share:.2f} "
        f"over {int(group['FamilyId'].nunique())} families"
    )


# ======================================================================================
# Age and trauma analysis (sections 15 and 16)
# ======================================================================================
def _group_rows(
    groups: Mapping[str, set[str]],
    model: PathwayFeatureModel,
    similarity: PairwiseSimilarity,
    *,
    dimension_name: str,
    scope_label: str,
) -> list[dict[str, object]]:
    """Return cohesion rows for a set of metadata-defined groups."""
    rows = []
    for group_name in sorted(groups):
        members = groups[group_name]
        if not members:
            continue
        metrics = cohesion_for_group(members, model, similarity=similarity)
        metadata = _metadata_shares(members, model)
        rows.append(
            {
                "AnalysisScope": scope_label,
                "Dimension": dimension_name,
                "GroupOrFamily": group_name,
                "PathwayCount": metrics["PathwayCount"],
                "InternalEdgePercentage": metrics["InternalEdgePercentage"],
                "ExternalEdgePercentage": metrics["ExternalEdgePercentage"],
                "PercentageBoundaryPathways": metrics["PercentageBoundaryPathways"],
                "UniqueSymptomDiscriminatorCount": metrics["UniqueSymptomDiscriminatorCount"],
                "UniqueSnomedCount": metrics["UniqueSnomedCount"],
                "UniqueDispositionCount": metrics["UniqueDispositionCount"],
                "MeanPairwiseSdJaccard": metrics["MeanPairwiseSdJaccard"],
                "MeanPairwiseSnomedJaccard": metrics["MeanPairwiseSnomedJaccard"],
                "MeanPairwiseQuestionJaccard": metrics["MeanPairwiseQuestionJaccard"],
                "SharedSdPercentage": metrics["SharedSdPercentage"],
                "DominantSymptomGroup": metadata["DominantSymptomGroup"],
                "DominantClinicalArea": metadata["DominantClinicalArea"],
                "DistinctClinicalAreas": metadata["DistinctClinicalAreas"],
            }
        )
    return rows


def _subset_comparison(
    members: set[str],
    subset_a: set[str],
    subset_b: set[str],
    model: PathwayFeatureModel,
    similarity: PairwiseSimilarity,
) -> dict[str, object]:
    """Compare two subsets of a family on features, transitions and dispositions.

    The question this answers is structural: does subset A look like a variant of
    subset B inside one family, or like a separate structure that happens to share a
    family? The evidence is the within-subset similarity against the between-subset
    similarity, plus whether transfers cross between them.

    A between-subset similarity at or above the within-subset similarities means the
    two subsets are not structurally distinguishable on that dimension. That is
    *consistent with* a variant relationship; it does not establish one.
    """
    graph = model.pathway_graph
    transitions_a_to_b = sum(
        1
        for node in subset_a
        if node in graph
        for _, target in graph.out_edges(node)
        if target in subset_b
    )
    transitions_b_to_a = sum(
        1
        for node in subset_b
        if node in graph
        for _, target in graph.out_edges(node)
        if target in subset_a
    )

    disposition_sets = model.maps.feature_sets("disposition")
    dispositions_a: set[str] = set()
    dispositions_b: set[str] = set()
    for node in subset_a:
        dispositions_a |= disposition_sets.get(node, set())
    for node in subset_b:
        dispositions_b |= disposition_sets.get(node, set())
    union = dispositions_a | dispositions_b
    disposition_jaccard = (
        round(len(dispositions_a & dispositions_b) / len(union), 6) if union else float("nan")
    )

    within_a = similarity.mean_within("symptom_discriminator", subset_a)
    within_b = similarity.mean_within("symptom_discriminator", subset_b)
    between = similarity.mean_between("symptom_discriminator", subset_a, subset_b)

    return {
        "SubsetACount": len(subset_a),
        "SubsetBCount": len(subset_b),
        "WithinSubsetASdJaccard": within_a,
        "WithinSubsetBSdJaccard": within_b,
        "BetweenSubsetSdJaccard": between,
        "WithinSubsetASnomedJaccard": similarity.mean_within("snomed", subset_a),
        "WithinSubsetBSnomedJaccard": similarity.mean_within("snomed", subset_b),
        "BetweenSubsetSnomedJaccard": similarity.mean_between("snomed", subset_a, subset_b),
        "TransitionsAToB": transitions_a_to_b,
        "TransitionsBToA": transitions_b_to_a,
        "SharedDispositionJaccard": disposition_jaccard,
        "StructuralReading": _subset_reading(within_a, within_b, between),
    }


def _subset_reading(within_a: float, within_b: float, between: float) -> str:
    """Describe the within/between similarity relationship without a clinical claim."""
    values = [value for value in (within_a, within_b) if pd.notna(value)]
    if pd.isna(between) or not values:
        return "not measurable (one subset has fewer than two pathways)"
    reference = float(np.mean(values))
    if between >= reference:
        return (
            "subsets are not structurally distinguishable on shared symptom "
            "discriminators (between >= within)"
        )
    if between >= 0.5 * reference:
        return "subsets partially distinguishable (between is 50-100% of within)"
    return "subsets are structurally distinct on shared symptom discriminators"


def metadata_dimension_analysis(
    candidate: CandidateFamilySet,
    model: PathwayFeatureModel,
    similarity: PairwiseSimilarity,
    *,
    dimension_name: str,
    classification_column: str,
    tag_column: str,
    subset_a: tuple[str, Sequence[str]],
    subset_b: tuple[str, Sequence[str]],
) -> pd.DataFrame:
    """Analyse whether a metadata dimension forms families, variants or a cross-cut.

    Shared engine behind the age analysis (section 15) and the trauma analysis
    (section 16), so both use identical definitions and can be read side by side.

    Three scopes are produced, distinguished by the ``AnalysisScope`` column:

    * ``classification_as_grouping`` -- the classification values treated as candidate
      families in their own right, with full cohesion metrics. Answers "would this
      dimension make a coherent top-level family set?"
    * ``individual_tag_as_grouping`` -- each raw tag value treated as an overlapping
      group. Answers "is any single tag value coherent on its own?"
    * ``family_composition`` -- for each family of the supplied candidate set, the
      dimension's composition plus a within/between comparison of the two named
      subsets. Answers "is this dimension a variant inside families, or a separator
      between them?"

    Args:
        candidate: Candidate family set whose families are decomposed.
        model: The feature model.
        similarity: Pre-computed pairwise similarity.
        dimension_name: Label for the dimension, e.g. ``age`` or ``trauma``.
        classification_column: Feature-model column holding the derived classification.
        tag_column: Feature-model column holding the pipe-joined raw tag descriptions.
        subset_a: ``(name, classification values)`` defining the first subset.
        subset_b: ``(name, classification values)`` defining the second subset.

    Returns:
        A long-format frame covering all three scopes.
    """
    features = model.features
    rows: list[dict[str, object]] = []

    classification_groups: dict[str, set[str]] = {}
    for row in features.itertuples():
        value = str(getattr(row, classification_column))
        classification_groups.setdefault(value, set()).add(row.PathwayKey)
    rows.extend(
        _group_rows(
            classification_groups,
            model,
            similarity,
            dimension_name=dimension_name,
            scope_label="classification_as_grouping",
        )
    )

    tag_groups: dict[str, set[str]] = {}
    for row in features.itertuples():
        raw = getattr(row, tag_column)
        if raw is None or (not isinstance(raw, str) and pd.isna(raw)):
            continue
        for part in str(raw).split("|"):
            tag = part.strip()
            if tag:
                tag_groups.setdefault(tag, set()).add(row.PathwayKey)
    rows.extend(
        _group_rows(
            tag_groups,
            model,
            similarity,
            dimension_name=dimension_name,
            scope_label="individual_tag_as_grouping",
        )
    )

    subset_a_name, subset_a_values = subset_a
    subset_b_name, subset_b_values = subset_b
    classification_by_pathway = dict(
        zip(features["PathwayKey"], features[classification_column].astype(str))
    )
    families = candidate.families()
    labels = candidate.labels()
    for family_id in sorted(families):
        members = families[family_id]
        members_a = {
            key for key in members
            if classification_by_pathway.get(key, "") in set(subset_a_values)
        }
        members_b = {
            key for key in members
            if classification_by_pathway.get(key, "") in set(subset_b_values)
        }
        composition = {
            value: sum(
                1 for key in members if classification_by_pathway.get(key, "") == value
            )
            for value in sorted(set(classification_by_pathway.values()))
        }
        comparison = _subset_comparison(members, members_a, members_b, model, similarity)
        rows.append(
            {
                "AnalysisScope": "family_composition",
                "Dimension": dimension_name,
                "GroupOrFamily": family_id,
                "FamilyLabel": labels.get(family_id, family_id),
                "strategy": candidate.strategy,
                "PathwayCount": len(members),
                "SubsetAName": subset_a_name,
                "SubsetBName": subset_b_name,
                "CompositionCounts": " | ".join(
                    f"{value}:{count}" for value, count in composition.items() if count
                ),
                "SubsetAShare": round(len(members_a) / max(len(members), 1), 4),
                "SubsetBShare": round(len(members_b) / max(len(members), 1), 4),
                "FamilyIsSingleSubset": bool(members_a) != bool(members_b),
                **comparison,
            }
        )

    frame = pd.DataFrame(rows)
    if frame.empty:
        return frame
    return frame.sort_values(
        ["AnalysisScope", "PathwayCount", "GroupOrFamily"],
        ascending=[True, False, True],
        ignore_index=True,
    )


def age_family_analysis(
    candidate: CandidateFamilySet,
    model: PathwayFeatureModel,
    similarity: PairwiseSimilarity,
) -> pd.DataFrame:
    """Analyse whether age forms families, variants within families, or a cross-cut.

    Age metadata exists in this dataset: ``tblPathway2Ages`` links pathways to the five
    bands in ``tblAges``, and 796 of the 815 active pathways carry at least one band.
    Most carry several, so age is an overlapping dimension and cannot be a partition.

    The analysis makes no assumption that paediatrics must be a separate top-level
    family. It reports the three readings side by side and leaves the choice to
    clinical review.
    """
    return metadata_dimension_analysis(
        candidate,
        model,
        similarity,
        dimension_name="age",
        classification_column="AgeClassification",
        tag_column="AgeDescriptions",
        subset_a=("paediatric_only", ("paediatric_only",)),
        subset_b=("adult_only", ("adult_only",)),
    )


def trauma_family_analysis(
    candidate: CandidateFamilySet,
    model: PathwayFeatureModel,
    similarity: PairwiseSimilarity,
) -> pd.DataFrame:
    """Analyse whether trauma is one family, several, a cross-cut, or a gateway.

    Trauma metadata exists: ``tblPathway2Trauma`` links pathways to the two values in
    ``tblTrauma``. 449 of the 815 active pathways carry a trauma tag and 24 carry both,
    so trauma is not a clean binary partition either.

    The four readings the brief asks about map onto measurable quantities:

    * one coherent family -> high internal-edge percentage and high shared-SD cohesion
      for the trauma group taken as a whole;
    * multiple anatomical families -> trauma pathways concentrated in a few area
      groups, with the whole-trauma group weakly cohesive;
    * a cross-cutting dimension -> trauma pathways spread thinly across many candidate
      families;
    * a shared gateway -> trauma pathways with high betweenness and high external
      degree, i.e. sitting on routes into other families.

    All four sets of numbers are emitted; the reading is left to clinical review.
    """
    return metadata_dimension_analysis(
        candidate,
        model,
        similarity,
        dimension_name="trauma",
        classification_column="TraumaClassification",
        tag_column="TraumaDescriptions",
        subset_a=("trauma", ("trauma", "trauma_and_non_trauma")),
        subset_b=("non_trauma", ("non_trauma",)),
    )


def metadata_spread_summary(
    candidate: CandidateFamilySet,
    model: PathwayFeatureModel,
    *,
    classification_column: str,
    values: Sequence[str],
    dimension_name: str,
) -> pd.DataFrame:
    """Measure how a metadata value spreads across a candidate family set.

    A dimension concentrated in a few families behaves like a family; one spread across
    many behaves like a cross-cutting attribute. This quantifies which, using the share
    of tagged pathways held by the largest family and the number of families needed to
    cover 80% of them.
    """
    families = candidate.families()
    classification_by_pathway = dict(
        zip(model.features["PathwayKey"], model.features[classification_column].astype(str))
    )
    records = []
    for value in values:
        tagged = {
            key for key, classification in classification_by_pathway.items()
            if classification == value
        }
        if not tagged:
            continue
        per_family = sorted(
            ((family_id, len(tagged & members)) for family_id, members in families.items()),
            key=lambda item: (-item[1], item[0]),
        )
        populated = [(family_id, count) for family_id, count in per_family if count]
        cumulative = 0
        families_for_80 = 0
        for _, count in populated:
            cumulative += count
            families_for_80 += 1
            if cumulative >= 0.8 * len(tagged):
                break
        area_groups = _exploded_counts(
            model.features.loc[model.features["PathwayKey"].isin(tagged)], "AreaGroups"
        )
        centrality = model.features.loc[
            model.features["PathwayKey"].isin(tagged), "BetweennessCentrality"
        ].astype(float)
        all_centrality = model.features["BetweennessCentrality"].astype(float)
        records.append(
            {
                "Dimension": dimension_name,
                "ClassificationValue": value,
                "strategy": candidate.strategy,
                "TaggedPathways": len(tagged),
                "FamiliesContainingValue": len(populated),
                "FamilyCountTotal": len(families),
                "LargestFamilyShare": round(
                    populated[0][1] / len(tagged), 4
                ) if populated else float("nan"),
                "LargestFamilyId": populated[0][0] if populated else "",
                "FamiliesCovering80Percent": families_for_80,
                "DistinctAreaGroups": int(len(area_groups)),
                "TopAreaGroups": " | ".join(
                    f"{name}:{count}" for name, count in area_groups.head(4).items()
                ),
                "MeanBetweennessOfTagged": (
                    round(float(centrality.mean()), 8)
                    if len(centrality)
                    else float("nan")
                ),
                "MeanBetweennessOfAllInScope": round(float(all_centrality.mean()), 8),
                "SpreadReading": _spread_reading(
                    populated[0][1] / len(tagged) if populated else float("nan"),
                    families_for_80,
                    len(families),
                ),
            }
        )
    if not records:
        return pd.DataFrame()
    return pd.DataFrame(records).sort_values(
        ["Dimension", "TaggedPathways"], ascending=[True, False], ignore_index=True
    )


def _spread_reading(largest_share: float, families_for_80: int, family_count: int) -> str:
    """Describe concentration versus spread, factually."""
    if pd.isna(largest_share):
        return "not measurable"
    if largest_share >= 0.5:
        return "concentrated: one family holds at least half the tagged pathways"
    if families_for_80 <= max(3, int(0.15 * family_count)):
        return "concentrated: 80% of tagged pathways sit in a small number of families"
    return (
        "spread: tagged pathways are distributed across many families, consistent "
        "with a cross-cutting dimension"
    )
