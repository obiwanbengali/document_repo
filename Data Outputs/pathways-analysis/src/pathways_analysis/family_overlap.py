"""Phase 2: overlap between candidate families, and hypothetical merges.

Sections 7, 8 and 13 of the Phase 2 brief.

How overlap is computed
-----------------------
For each candidate family set, a boolean ``families x pathways`` matrix ``M`` is built
from the membership frame, and a boolean ``pathways x features`` matrix ``P`` from each
feature map. ``(M @ P) > 0`` is then the family's feature set, and the family-by-family
intersection of any feature class is a single matrix product. Family-to-family
transitions are ``M @ A @ M.T`` for the pathway adjacency matrix ``A``.

This matters for correctness as well as speed: an overlapping family set (clinical
areas, trauma tags) would make a loop-based implementation easy to get wrong about
pathways counted in two families at once, whereas the matrix form has one definition.

What overlap does and does not mean
-----------------------------------
High overlap is **evidence**, not a merge instruction. Two families sharing a large
symptom-discriminator vocabulary may be one clinical area split by routing, or two
genuinely distinct areas that share a screening vocabulary. Section 8 therefore
reports *why* each high-overlap pair overlaps and leaves the decision open.
"""

from __future__ import annotations

import logging
from typing import Final, Mapping, Sequence

import numpy as np
import pandas as pd

from .family_config import FamilyDiscoveryConfig
from .family_features import (
    FEATURE_DIMENSIONS,
    CandidateFamilySet,
    PairwiseSimilarity,
    PathwayFeatureModel,
    adjacency_matrices,
    indicator_matrix,
)

LOGGER: Final = logging.getLogger(__name__)

#: Feature classes reported in the overlap matrix. Clinical area is included because it
#: is itself an NHS grouping, so shared clinical areas are a distinct kind of overlap
#: from shared questions.
OVERLAP_DIMENSIONS: Final[tuple[str, ...]] = FEATURE_DIMENSIONS

#: Column names used for the per-dimension overlap columns, keyed by dimension.
_COLUMN_NAMES: Final[dict[str, tuple[str, str]]] = {
    "question": ("shared_questions", "question_jaccard"),
    "symptom_discriminator": ("shared_sds", "sd_jaccard"),
    "snomed": ("shared_snomed", "snomed_jaccard"),
    "disposition": ("shared_dispositions", "disposition_jaccard"),
    "clinical_area": ("shared_clinical_areas", "clinical_area_jaccard"),
}


class FamilyMatrices:
    """Matrix view of one candidate family set, shared by every metric that needs it.

    Attributes:
        family_ids: Row order of the family matrix.
        pathways: Column order of the family matrix and row order of every feature and
            adjacency matrix.
        membership_matrix: ``families x pathways`` 0/1 matrix.
        feature_matrices: ``{dimension: (pathways x features) matrix}``.
        feature_names: ``{dimension: [feature_id, ...]}``.
        adjacency: ``pathways x pathways`` 0/1 edge matrix.
        adjacency_weighted: ``pathways x pathways`` transition-count matrix.
    """

    def __init__(
        self,
        candidate: CandidateFamilySet,
        model: PathwayFeatureModel,
    ) -> None:
        self.candidate = candidate
        self.family_ids: list[str] = candidate.family_ids
        self.pathways: list[str] = list(model.scope)
        self.labels = candidate.labels()

        pathway_index = {value: position for position, value in enumerate(self.pathways)}
        family_index = {value: position for position, value in enumerate(self.family_ids)}
        self.membership_matrix = np.zeros(
            (len(self.family_ids), len(self.pathways)), dtype=np.float32
        )
        in_scope = candidate.membership.loc[
            candidate.membership["pathway_key"].isin(pathway_index)
        ]
        if not in_scope.empty:
            self.membership_matrix[
                in_scope["family_id"].map(family_index).to_numpy(dtype=np.int64),
                in_scope["pathway_key"].map(pathway_index).to_numpy(dtype=np.int64),
            ] = 1.0

        self.feature_matrices: dict[str, np.ndarray] = {}
        self.feature_names: dict[str, list[str]] = {}
        for dimension, frame in model.maps.as_mapping().items():
            matrix, names = indicator_matrix(frame, self.pathways)
            self.feature_matrices[dimension] = matrix
            self.feature_names[dimension] = names

        self.adjacency, self.adjacency_weighted = adjacency_matrices(
            model.pathway_graph, self.pathways
        )
        # Edges whose far end is outside the membership scope (an archived pathway
        # taking part in a transfer) are counted as external, so they are kept in a
        # separate vector rather than discarded.
        self._external_out, self._external_in = _out_of_scope_degrees(model, self.pathways)

    def family_feature_matrix(self, dimension: str) -> np.ndarray:
        """Return the ``families x features`` 0/1 matrix for one dimension."""
        return (self.membership_matrix @ self.feature_matrices[dimension] > 0).astype(
            np.float32
        )

    def family_sizes(self) -> np.ndarray:
        """Return the pathway count per family."""
        return self.membership_matrix.sum(axis=1)

    def out_of_scope_degrees(self) -> tuple[np.ndarray, np.ndarray]:
        """Return per-pathway out/in edge counts to pathways outside the family scope."""
        return self._external_out, self._external_in


def _out_of_scope_degrees(
    model: PathwayFeatureModel, pathways: Sequence[str]
) -> tuple[np.ndarray, np.ndarray]:
    """Count each in-scope pathway's edges to pathways outside the scope.

    The pathway graph spans every active pathway plus any pathway taking part in a
    resolved transfer, whereas family membership is restricted to the configured scope.
    An edge from an in-scope pathway to an out-of-scope one is a real external edge and
    must be counted as such; dropping it would inflate every internal-edge percentage.
    """
    scope = set(pathways)
    index = {value: position for position, value in enumerate(pathways)}
    out_counts = np.zeros(len(pathways), dtype=np.float32)
    in_counts = np.zeros(len(pathways), dtype=np.float32)
    graph = model.pathway_graph
    for node in pathways:
        if node not in graph:
            continue
        position = index[node]
        out_counts[position] = sum(
            1 for _, target in graph.out_edges(node) if target not in scope
        )
        in_counts[position] = sum(
            1 for source, _ in graph.in_edges(node) if source not in scope
        )
    return out_counts, in_counts


def _jaccard_from_counts(
    intersection: np.ndarray, sizes: np.ndarray
) -> np.ndarray:
    """Return the pairwise Jaccard matrix given intersection counts and set sizes."""
    union = sizes[:, None] + sizes[None, :] - intersection
    with np.errstate(divide="ignore", invalid="ignore"):
        result = np.where(union > 0, intersection / union, 0.0)
    return result


def family_overlap_matrix(
    candidate: CandidateFamilySet,
    model: PathwayFeatureModel,
    *,
    matrices: FamilyMatrices | None = None,
    include_zero_overlap: bool = False,
) -> pd.DataFrame:
    """Compute the long-form family-pair overlap matrix (Phase 2 section 7).

    Args:
        candidate: The candidate family set.
        model: The feature model supplying features and the pathway graph.
        matrices: Pre-built matrices, to avoid rebuilding them per section.
        include_zero_overlap: Emit pairs with no shared feature, pathway or transition.
            Off by default: for a 224-family native grouping that is 25k rows of zeros.

    Returns:
        One row per unordered family pair with shared counts, per-class Jaccard
        similarity and directed transition counts in both directions.
    """
    matrices = matrices or FamilyMatrices(candidate, model)
    family_ids = matrices.family_ids
    if len(family_ids) < 2:
        return pd.DataFrame(
            columns=[
                "strategy", "FamilyA", "FamilyB", "FamilyALabel", "FamilyBLabel",
                "PathwayCountA", "PathwayCountB", "SharedPathways", "SharedQuestions",
                "SharedSDs", "SharedSnomed", "SharedDispositions", "SharedClinicalAreas",
                "TransitionsAtoB", "TransitionsBtoA", "EdgesAtoB", "EdgesBtoA",
                "QuestionJaccard", "SdJaccard", "SnomedJaccard", "DispositionJaccard",
                "ClinicalAreaJaccard", "PathwayJaccard", "MaxFeatureJaccard",
                "MaxDiscriminatingJaccard",
            ]
        )

    membership = matrices.membership_matrix
    sizes = matrices.family_sizes()
    shared_pathways = membership @ membership.T
    pathway_jaccard = _jaccard_from_counts(shared_pathways, sizes)

    dimension_data: dict[str, tuple[np.ndarray, np.ndarray]] = {}
    for dimension in OVERLAP_DIMENSIONS:
        family_features = matrices.family_feature_matrix(dimension)
        intersection = family_features @ family_features.T
        dimension_sizes = family_features.sum(axis=1)
        dimension_data[dimension] = (
            intersection,
            _jaccard_from_counts(intersection, dimension_sizes),
        )

    edges_between = membership @ matrices.adjacency @ membership.T
    transitions_between = membership @ matrices.adjacency_weighted @ membership.T

    rows, columns = np.triu_indices(len(family_ids), k=1)
    frame = pd.DataFrame(
        {
            "strategy": candidate.strategy,
            "FamilyA": [family_ids[index] for index in rows],
            "FamilyB": [family_ids[index] for index in columns],
            "FamilyALabel": [matrices.labels.get(family_ids[index], "") for index in rows],
            "FamilyBLabel": [matrices.labels.get(family_ids[index], "") for index in columns],
            "PathwayCountA": sizes[rows].astype(np.int64),
            "PathwayCountB": sizes[columns].astype(np.int64),
            "SharedPathways": shared_pathways[rows, columns].astype(np.int64),
            "PathwayJaccard": pathway_jaccard[rows, columns].round(6),
            "TransitionsAtoB": transitions_between[rows, columns].astype(np.int64),
            "TransitionsBtoA": transitions_between[columns, rows].astype(np.int64),
            "EdgesAtoB": edges_between[rows, columns].astype(np.int64),
            "EdgesBtoA": edges_between[columns, rows].astype(np.int64),
        }
    )
    for dimension in OVERLAP_DIMENSIONS:
        shared_column, jaccard_column = _COLUMN_NAMES[dimension]
        intersection, jaccard = dimension_data[dimension]
        frame[_pascal(shared_column)] = intersection[rows, columns].astype(np.int64)
        frame[_pascal(jaccard_column)] = jaccard[rows, columns].round(6)

    frame["MaxFeatureJaccard"] = frame[
        ["QuestionJaccard", "SdJaccard", "SnomedJaccard", "DispositionJaccard"]
    ].max(axis=1).round(6)
    # The same maximum with dispositions excluded. Disposition sets are small and
    # largely shared -- most families can reach an ambulance and a primary-care
    # referral -- so including them makes the maximum near-constant across pairs and
    # unable to distinguish them. Both measures are exported; configuration decides
    # which one the overlap band is read from.
    frame["MaxDiscriminatingJaccard"] = frame[
        ["QuestionJaccard", "SdJaccard", "SnomedJaccard"]
    ].max(axis=1).round(6)

    if not include_zero_overlap:
        keep = (
            (frame["SharedPathways"] > 0)
            | (frame["MaxFeatureJaccard"] > 0)
            | (frame["TransitionsAtoB"] > 0)
            | (frame["TransitionsBtoA"] > 0)
        )
        frame = frame.loc[keep]

    return frame.sort_values(
        ["strategy", "MaxFeatureJaccard", "SharedPathways", "FamilyA", "FamilyB"],
        ascending=[True, False, False, True, True],
        ignore_index=True,
    )


def _pascal(column: str) -> str:
    """Map a snake_case overlap column name to the PascalCase deliverable name."""
    mapping = {
        "shared_questions": "SharedQuestions",
        "question_jaccard": "QuestionJaccard",
        "shared_sds": "SharedSDs",
        "sd_jaccard": "SdJaccard",
        "shared_snomed": "SharedSnomed",
        "snomed_jaccard": "SnomedJaccard",
        "shared_dispositions": "SharedDispositions",
        "disposition_jaccard": "DispositionJaccard",
        "shared_clinical_areas": "SharedClinicalAreas",
        "clinical_area_jaccard": "ClinicalAreaJaccard",
    }
    return mapping[column]


def classify_overlap(
    overlap: pd.DataFrame,
    config: FamilyDiscoveryConfig,
) -> pd.DataFrame:
    """Band every family pair as low / moderate / high overlap (Phase 2 section 8).

    Classification is on ``MaxFeatureJaccard`` -- the largest of the question, symptom
    discriminator, SNOMED and disposition Jaccard values -- with an escalation to
    ``high`` for any pair that shares at least
    ``overlap_thresholds.shared_pathway_escalation`` pathways. Shared membership is
    treated as the stronger signal because it means the two families are not disjoint
    at all, whereas shared vocabulary may only mean shared screening questions.

    Thresholds come from configuration and are echoed into the output so a reader never
    has to guess which cut produced a band.
    """
    if overlap.empty:
        return overlap.assign(
            OverlapBand=pd.Series(dtype="object"),
            OverlapDriver=pd.Series(dtype="object"),
        )

    result = overlap.copy()
    band_column = (
        "MaxDiscriminatingJaccard"
        if config.overlap_band_measure == "discriminating"
        and "MaxDiscriminatingJaccard" in result.columns
        else "MaxFeatureJaccard"
    )
    result["OverlapBandMeasure"] = band_column
    max_jaccard = result[band_column]
    band = np.where(
        max_jaccard >= config.overlap_high,
        "high",
        np.where(max_jaccard >= config.overlap_moderate, "moderate", "low"),
    )
    escalated = result["SharedPathways"] >= max(config.shared_pathway_escalation, 1)
    band = np.where(escalated, "high", band)
    result["OverlapBand"] = band
    result["OverlapEscalatedBySharedPathways"] = escalated

    # The dominant driver is the feature class with the highest Jaccard, which is what a
    # reviewer needs in order to judge whether the overlap is clinically meaningful.
    driver_columns = {
        "QuestionJaccard": "shared questions",
        "SdJaccard": "shared symptom discriminators",
        "SnomedJaccard": "shared SNOMED concepts",
    }
    if band_column == "MaxFeatureJaccard":
        driver_columns["DispositionJaccard"] = "shared dispositions"
    driver_frame = result[list(driver_columns)]
    result["OverlapDriver"] = [
        driver_columns[column] if value > 0 else "no shared features"
        for column, value in zip(driver_frame.idxmax(axis=1), driver_frame.max(axis=1))
    ]
    result.loc[escalated, "OverlapDriver"] = (
        "shared pathways (" + result.loc[escalated, "SharedPathways"].astype(str) + ")"
    )
    result["OverlapModerateThreshold"] = config.overlap_moderate
    result["OverlapHighThreshold"] = config.overlap_high
    return result


def high_overlap_evidence(
    classified: pd.DataFrame,
    candidate_sets: Mapping[str, CandidateFamilySet],
    model: PathwayFeatureModel,
    *,
    top_n_drivers: int = 8,
) -> pd.DataFrame:
    """Build the per-pair evidence table for high-overlap family pairs (section 8).

    For each high-overlap pair this records which pathways, symptom discriminators,
    SNOMED concepts and graph transitions drive the overlap, so a reviewer can judge
    the pair on its content rather than on a similarity number.

    Args:
        classified: Output of :func:`classify_overlap` across all strategies.
        candidate_sets: The candidate sets, keyed by strategy.
        model: The feature model.
        top_n_drivers: How many driving features to name per pair.

    Returns:
        One row per high-overlap pair with the driving evidence.
    """
    if classified.empty:
        return pd.DataFrame()
    high = classified.loc[classified["OverlapBand"] == "high"]
    if high.empty:
        return pd.DataFrame()

    feature_sets: dict[str, dict[str, set[str]]] = {
        dimension: model.maps.feature_sets(dimension)
        for dimension in ("symptom_discriminator", "snomed", "question", "disposition")
    }
    titles = model.title_lookup()
    edge_lookup: dict[tuple[str, str], int] = {}
    if not model.edges.empty:
        for row in model.edges.itertuples():
            edge_lookup[(row.source_pathway_key, row.target_pathway_key)] = int(
                row.transition_count
            )

    records = []
    for row in high.itertuples():
        candidate = candidate_sets.get(row.strategy)
        if candidate is None:
            continue
        families = candidate.families()
        members_a = families.get(row.FamilyA, set())
        members_b = families.get(row.FamilyB, set())
        shared_members = sorted(members_a & members_b)

        def shared_features(
            dimension: str,
            members_a: set[str] = members_a,
            members_b: set[str] = members_b,
        ) -> list[str]:
            """Return the features both families reach, for one dimension.

            The member sets are bound as defaults rather than captured from the
            enclosing loop, so the closure cannot read a later iteration's values.
            """
            sets_by_pathway = feature_sets[dimension]
            set_a: set[str] = set()
            set_b: set[str] = set()
            for pathway in members_a:
                set_a |= sets_by_pathway.get(pathway, set())
            for pathway in members_b:
                set_b |= sets_by_pathway.get(pathway, set())
            return sorted(set_a & set_b)

        shared_sd = shared_features("symptom_discriminator")
        shared_snomed = shared_features("snomed")
        shared_questions = shared_features("question")

        transitions = []
        for source in sorted(members_a):
            for target in sorted(members_b):
                count = edge_lookup.get((source, target))
                if count:
                    transitions.append((source, target, count))
        for source in sorted(members_b):
            for target in sorted(members_a):
                count = edge_lookup.get((source, target))
                if count:
                    transitions.append((source, target, count))
        transitions.sort(key=lambda item: (-item[2], item[0], item[1]))

        reasons = []
        if shared_members:
            reasons.append(
                f"{len(shared_members)} pathway(s) belong to both families"
            )
        if row.SdJaccard > 0:
            reasons.append(
                f"symptom-discriminator Jaccard {row.SdJaccard:.3f} "
                f"({row.SharedSDs} shared)"
            )
        if row.QuestionJaccard > 0:
            reasons.append(
                f"question Jaccard {row.QuestionJaccard:.3f} ({row.SharedQuestions} shared)"
            )
        if row.SnomedJaccard > 0:
            reasons.append(
                f"SNOMED Jaccard {row.SnomedJaccard:.3f} ({row.SharedSnomed} shared)"
            )
        if row.TransitionsAtoB or row.TransitionsBtoA:
            reasons.append(
                f"{row.TransitionsAtoB + row.TransitionsBtoA} transfer transitions between them"
            )

        records.append(
            {
                "strategy": row.strategy,
                "FamilyA": row.FamilyA,
                "FamilyB": row.FamilyB,
                "FamilyALabel": row.FamilyALabel,
                "FamilyBLabel": row.FamilyBLabel,
                "PathwayCountA": row.PathwayCountA,
                "PathwayCountB": row.PathwayCountB,
                # Jaccard is scale-free, so two one-pathway families sharing all three
                # of their questions score 1.0. That is arithmetically correct and
                # analytically trivial, so the smaller family's size is carried
                # alongside it and drives the sort order.
                "SmallerFamilyPathwayCount": int(
                    min(row.PathwayCountA, row.PathwayCountB)
                ),
                "OverlapBand": row.OverlapBand,
                "OverlapDriver": row.OverlapDriver,
                # The value the band was read from, so the band and the number quoted
                # beside it always refer to the same measure.
                "OverlapBandMeasure": getattr(row, "OverlapBandMeasure", ""),
                "BandMeasureJaccard": getattr(
                    row, "MaxDiscriminatingJaccard", row.MaxFeatureJaccard
                )
                if getattr(row, "OverlapBandMeasure", "") == "MaxDiscriminatingJaccard"
                else row.MaxFeatureJaccard,
                "MaxFeatureJaccard": row.MaxFeatureJaccard,
                "MaxDiscriminatingJaccard": getattr(
                    row, "MaxDiscriminatingJaccard", float("nan")
                ),
                "SharedPathways": row.SharedPathways,
                "WhyTheyOverlap": "; ".join(reasons) if reasons else "no measurable overlap",
                "SharedPathwayExamples": " | ".join(
                    titles.get(key, key) for key in shared_members[:top_n_drivers]
                ),
                "DrivingSymptomDiscriminators": " | ".join(shared_sd[:top_n_drivers]),
                "DrivingSymptomDiscriminatorCount": len(shared_sd),
                "DrivingSnomedConcepts": " | ".join(shared_snomed[:top_n_drivers]),
                "DrivingSnomedConceptCount": len(shared_snomed),
                "DrivingQuestionCount": len(shared_questions),
                "DrivingTransitions": " | ".join(
                    f"{source}->{target} ({count})"
                    for source, target, count in transitions[:top_n_drivers]
                ),
                "DrivingTransitionCount": len(transitions),
            }
        )
    if not records:
        return pd.DataFrame()
    # Sorted by the smaller family's size first, so the pairs a reviewer should look at
    # -- two substantial families that overlap -- come before pairs of singletons whose
    # Jaccard is 1.0 by construction.
    return pd.DataFrame(records).sort_values(
        [
            "strategy",
            "SmallerFamilyPathwayCount",
            "BandMeasureJaccard",
            "SharedPathways",
        ],
        ascending=[True, False, False, False],
        ignore_index=True,
    )


def merge_candidates(
    classified: pd.DataFrame,
    candidate_sets: Mapping[str, CandidateFamilySet],
    model: PathwayFeatureModel,
    cohesion: pd.DataFrame,
    *,
    config: FamilyDiscoveryConfig,
    similarity: PairwiseSimilarity,
) -> pd.DataFrame:
    """Test hypothetical merges of high-overlap family pairs (Phase 2 section 13).

    For each high-overlap pair the two families are notionally unioned and the cohesion
    metrics are recomputed, so the effect of a merge is measured rather than assumed.

    The internal-edge percentage is a **mechanically favourable** measure of a merge
    -------------------------------------------------------------------------------
    Every edge that ran between the two families becomes internal to the union, so
    merging can only raise the combined internal-edge percentage (or leave it
    unchanged). "This merge improves cohesion" is therefore close to a tautology and is
    **not** evidence for merging. It is reported because the *size* of the gain
    distinguishes a pair that genuinely belongs together from one that barely
    interacts, but it cannot be read as a verdict.

    The discriminating signal is the **mean pairwise symptom-discriminator Jaccard**,
    which has no such bias: merging two families whose pathways share little clinical
    vocabulary lowers it, because the union contains many dissimilar pairs. A merge
    that raises internal-edge percentage while lowering shared-SD cohesion is combining
    things that route together but are not clinically alike -- exactly the case that
    needs a clinician, not a metric.

    ``StructuralVerdict`` is therefore driven by the symptom-discriminator change, with
    the graph change reported alongside it.

    **No merge is recommended.** The output is a before/after comparison for review.

    Args:
        classified: Output of :func:`classify_overlap`.
        candidate_sets: The candidate sets, keyed by strategy.
        model: The feature model.
        cohesion: Per-family cohesion, supplying the "before" values.
        config: Supplies the split-review size used for the size flag.
        similarity: Pre-computed pairwise similarity. Required: without it every mean
            pairwise Jaccard would be NaN and no merge would be measurable.

    Returns:
        One row per tested pair with before and after metrics and the deltas.
    """
    from .family_evaluation import cohesion_for_group  # local import avoids a cycle

    if classified.empty:
        return pd.DataFrame()
    high = classified.loc[classified["OverlapBand"] == "high"]
    if high.empty:
        return pd.DataFrame()

    cohesion_indexed = (
        cohesion.set_index(["strategy", "FamilyId"]) if not cohesion.empty else pd.DataFrame()
    )

    def before(strategy: str, family_id: str, column: str) -> float:
        if cohesion_indexed.empty:
            return float("nan")
        key = (strategy, family_id)
        if key not in cohesion_indexed.index:
            return float("nan")
        value = cohesion_indexed.at[key, column]
        return float(value) if pd.notna(value) else float("nan")

    records = []
    for row in high.itertuples():
        candidate = candidate_sets.get(row.strategy)
        if candidate is None:
            continue
        families = candidate.families()
        members_a = families.get(row.FamilyA, set())
        members_b = families.get(row.FamilyB, set())
        merged = members_a | members_b
        if not merged:
            continue
        # The similarity matrices must be passed through: without them
        # cohesion_for_group returns NaN for every mean pairwise Jaccard, which would
        # silently make the merge verdict unmeasurable for every pair.
        after = cohesion_for_group(merged, model, similarity=similarity)

        internal_before_a = before(row.strategy, row.FamilyA, "InternalEdgePercentage")
        internal_before_b = before(row.strategy, row.FamilyB, "InternalEdgePercentage")
        boundary_before_a = before(row.strategy, row.FamilyA, "PercentageBoundaryPathways")
        boundary_before_b = before(row.strategy, row.FamilyB, "PercentageBoundaryPathways")
        sd_before_a = before(row.strategy, row.FamilyA, "SharedSdPercentage")
        sd_before_b = before(row.strategy, row.FamilyB, "SharedSdPercentage")
        sd_jaccard_before_a = before(row.strategy, row.FamilyA, "MeanPairwiseSdJaccard")
        sd_jaccard_before_b = before(row.strategy, row.FamilyB, "MeanPairwiseSdJaccard")
        snomed_before_a = before(row.strategy, row.FamilyA, "SharedSnomedPercentage")
        snomed_before_b = before(row.strategy, row.FamilyB, "SharedSnomedPercentage")

        weighted_internal_before = _size_weighted(
            (internal_before_a, len(members_a)), (internal_before_b, len(members_b))
        )
        weighted_boundary_before = _size_weighted(
            (boundary_before_a, len(members_a)), (boundary_before_b, len(members_b))
        )
        weighted_sd_before = _size_weighted(
            (sd_before_a, len(members_a)), (sd_before_b, len(members_b))
        )
        weighted_snomed_before = _size_weighted(
            (snomed_before_a, len(members_a)), (snomed_before_b, len(members_b))
        )
        weighted_sd_jaccard_before = _size_weighted(
            (sd_jaccard_before_a, len(members_a)), (sd_jaccard_before_b, len(members_b))
        )

        records.append(
            {
                "strategy": row.strategy,
                "FamilyA": row.FamilyA,
                "FamilyB": row.FamilyB,
                "FamilyALabel": row.FamilyALabel,
                "FamilyBLabel": row.FamilyBLabel,
                "OverlapDriver": row.OverlapDriver,
                "MaxFeatureJaccard": row.MaxFeatureJaccard,
                "PathwayCountBeforeA": len(members_a),
                "PathwayCountBeforeB": len(members_b),
                "SmallerFamilyPathwayCount": min(len(members_a), len(members_b)),
                "PathwayCountAfterMerge": len(merged),
                "SharedPathways": len(members_a & members_b),
                "InternalEdgePercentageBeforeA": internal_before_a,
                "InternalEdgePercentageBeforeB": internal_before_b,
                "InternalEdgePercentageBeforeWeighted": weighted_internal_before,
                "InternalEdgePercentageAfterMerge": after["InternalEdgePercentage"],
                "InternalEdgePercentageDelta": _delta(
                    after["InternalEdgePercentage"], weighted_internal_before
                ),
                "ExternalEdgePercentageAfterMerge": after["ExternalEdgePercentage"],
                "BoundaryPathwayPercentageBeforeWeighted": weighted_boundary_before,
                "BoundaryPathwayPercentageAfterMerge": after["PercentageBoundaryPathways"],
                "BoundaryPathwayPercentageDelta": _delta(
                    after["PercentageBoundaryPathways"], weighted_boundary_before
                ),
                "SharedSdPercentageBeforeWeighted": weighted_sd_before,
                "SharedSdPercentageAfterMerge": after["SharedSdPercentage"],
                "SharedSdPercentageDelta": _delta(
                    after["SharedSdPercentage"], weighted_sd_before
                ),
                "SharedSnomedPercentageBeforeWeighted": weighted_snomed_before,
                "SharedSnomedPercentageAfterMerge": after["SharedSnomedPercentage"],
                "SharedSnomedPercentageDelta": _delta(
                    after["SharedSnomedPercentage"], weighted_snomed_before
                ),
                "MeanPairwiseSdJaccardBeforeWeighted": weighted_sd_jaccard_before,
                "MeanPairwiseSdJaccardAfterMerge": after["MeanPairwiseSdJaccard"],
                "MeanPairwiseSdJaccardDelta": _delta(
                    after["MeanPairwiseSdJaccard"], weighted_sd_jaccard_before
                ),
                "UniqueQuestionsAfterMerge": after["UniqueQuestionCount"],
                "UniqueSdsAfterMerge": after["UniqueSymptomDiscriminatorCount"],
                "MergeWouldExceedSplitReviewSize": len(merged) >= config.split_review_size,
                "InternalEdgeGainIsMechanical": True,
                "StructuralVerdict": _merge_verdict(
                    _delta(after["InternalEdgePercentage"], weighted_internal_before),
                    _delta(
                        after["MeanPairwiseSdJaccard"], weighted_sd_jaccard_before
                    ),
                ),
                "Recommendation": "not made -- merge decisions require clinical review",
            }
        )
    if not records:
        return pd.DataFrame()
    # Sorted by the smaller family's size first, so merges of two substantial families
    # lead the table rather than pairs of singletons whose every delta is zero; then by
    # the unbiased signal, since a merge that raises shared-SD cohesion is more
    # interesting than one that only converts cross-family edges into internal ones,
    # which every merge does.
    return pd.DataFrame(records).sort_values(
        [
            "strategy",
            "SmallerFamilyPathwayCount",
            "MeanPairwiseSdJaccardDelta",
            "InternalEdgePercentageDelta",
        ],
        ascending=[True, False, False, False],
        ignore_index=True,
    )


def _size_weighted(*pairs: tuple[float, int]) -> float:
    """Return the size-weighted mean of (value, weight) pairs, ignoring NaN values."""
    usable = [(value, weight) for value, weight in pairs if pd.notna(value) and weight > 0]
    if not usable:
        return float("nan")
    total_weight = sum(weight for _, weight in usable)
    return round(sum(value * weight for value, weight in usable) / total_weight, 3)


def _delta(after: float, before: float) -> float:
    """Return ``after - before``, propagating NaN."""
    if pd.isna(after) or pd.isna(before):
        return float("nan")
    return round(float(after) - float(before), 3)


def _merge_verdict(internal_delta: float, sd_jaccard_delta: float) -> str:
    """Describe the structural effect of a merge without recommending it.

    The verdict is driven by the shared-symptom-discriminator change, because the
    internal-edge change is mechanically non-negative under any merge and therefore
    cannot distinguish a good merge from a pointless one. See
    :func:`merge_candidates`.
    """
    if pd.isna(sd_jaccard_delta):
        return "not measurable"
    graph_note = (
        f"graph cohesion {internal_delta:+.1f}pp (mechanical)"
        if pd.notna(internal_delta)
        else "graph cohesion not measurable"
    )
    if sd_jaccard_delta > 0.01:
        return f"shared-SD cohesion rises ({sd_jaccard_delta:+.3f}); {graph_note}"
    if sd_jaccard_delta >= -0.01:
        return f"shared-SD cohesion unchanged ({sd_jaccard_delta:+.3f}); {graph_note}"
    return (
        f"shared-SD cohesion falls ({sd_jaccard_delta:+.3f}): the union is less "
        f"clinically alike than its parts; {graph_note}"
    )
