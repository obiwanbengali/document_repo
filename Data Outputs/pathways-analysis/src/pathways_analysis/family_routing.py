"""Phase 2: how strongly each pathway associates with each candidate family.

Section 14 of the Phase 2 brief.

Why this matters for a federated runtime
----------------------------------------
If families were to become separate Bayesian Networks, something would have to decide
which network handles an incoming case. This module measures how *decidable* that is
from structure alone: a pathway whose best and second-best family affinities are nearly
equal cannot be routed on structural evidence, whatever the runtime does.

Phase 2 deliberately stops at measurement. **No router is designed here.**

How affinity is computed
------------------------
A pathway's affinity to a family is a weighted sum of five transparent components, each
in 0..1 and each reported individually alongside the total:

* ``graph`` -- the share of the pathway's distinct graph neighbours (either direction)
  that are members of the family. Neighbours outside the family-membership scope are
  kept in the denominator, so a pathway that mostly transfers to archived pathways
  cannot look strongly associated with anything.
* ``question`` / ``symptom_discriminator`` / ``snomed`` / ``disposition`` -- the mean
  Jaccard similarity between the pathway's feature set and those of the family's
  members, excluding the pathway itself where it is a member. Self-similarity is
  excluded because a family of one would otherwise score 1.0 by construction.

The weights come from ``routing.weights`` in configuration and are not clinically
validated. The component columns are exported so a reviewer can re-weight without
re-running, and so a total is never quoted without its parts.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Final, Iterable, Mapping, Sequence

import numpy as np
import pandas as pd

from .family_config import WEIGHT_DIMENSIONS, FamilyDiscoveryConfig
from .family_features import (
    CandidateFamilySet,
    PairwiseSimilarity,
    PathwayFeatureModel,
)

LOGGER: Final = logging.getLogger(__name__)

#: Feature dimensions that carry a routing weight. Clinical area is excluded: it is an
#: NHS grouping used to *define* candidate families, so scoring affinity with it would
#: let a native strategy score itself.
ROUTING_FEATURE_DIMENSIONS: Final[tuple[str, ...]] = (
    "question",
    "symptom_discriminator",
    "snomed",
    "disposition",
)


@dataclass
class AffinityContext:
    """Pre-computed pairwise similarity and neighbourhood data shared by all strategies.

    Building this once and reusing it across every candidate strategy is what makes
    running the full routing analysis for 15 strategies practical: the expensive part
    (pairwise Jaccard over ~800 pathways in four dimensions) does not depend on the
    family set.

    Attributes:
        pathways: Row/column order of every matrix.
        similarity: The shared pairwise Jaccard matrices.
        neighbour_matrix: ``pathways x pathways`` 0/1 symmetric adjacency, self loops
            removed.
        neighbour_totals: Per pathway, its count of distinct neighbours in the **full**
            pathway graph, including neighbours outside the membership scope.
    """

    pathways: list[str]
    similarity: PairwiseSimilarity
    neighbour_matrix: np.ndarray
    neighbour_totals: np.ndarray

    @property
    def jaccard(self) -> dict[str, np.ndarray]:
        """Return the per-dimension Jaccard matrices."""
        return self.similarity.matrices

    @classmethod
    def build(
        cls,
        model: PathwayFeatureModel,
        similarity: PairwiseSimilarity | None = None,
    ) -> "AffinityContext":
        """Compute the neighbourhood data for a feature model.

        Args:
            model: The feature model.
            similarity: Pre-built pairwise similarity. Supplied by the runner so the
                matrices are computed once for the whole of Phase 2.
        """
        pathways = list(model.scope)
        size = len(pathways)
        index = {value: position for position, value in enumerate(pathways)}
        similarity = similarity or PairwiseSimilarity.build(model)

        neighbour_matrix = np.zeros((size, size), dtype=np.float32)
        neighbour_totals = np.zeros(size, dtype=np.float32)
        graph = model.pathway_graph
        for pathway in pathways:
            if pathway not in graph:
                continue
            position = index[pathway]
            neighbours = (set(graph.successors(pathway)) | set(graph.predecessors(pathway))) - {
                pathway
            }
            neighbour_totals[position] = len(neighbours)
            for neighbour in neighbours:
                other = index.get(neighbour)
                if other is not None:
                    neighbour_matrix[position, other] = 1.0
        return cls(
            pathways=pathways,
            similarity=similarity,
            neighbour_matrix=neighbour_matrix,
            neighbour_totals=neighbour_totals,
        )

    def graph_pairwise_similarity(self) -> np.ndarray:
        """Return a pairwise graph similarity matrix for Hybrid C clustering.

        Defined as the mean of two transparent components:

        1. a 0/1 indicator that the pair is directly connected in either direction --
           a routing relationship authored into Pathways;
        2. the Jaccard similarity of their neighbour sets -- structural equivalence,
           which relates two pathways referred to by the same set of pathways even
           where no direct transfer exists between them.

        Both are needed: (1) alone would make a family a chain of referrals with no
        notion of similar-but-unconnected pathways, and (2) alone would ignore direct
        routing entirely. The 50/50 split between them is a modelling assumption.
        """
        adjacency = ((self.neighbour_matrix + self.neighbour_matrix.T) > 0).astype(np.float32)
        np.fill_diagonal(adjacency, 0.0)
        shared = adjacency @ adjacency.T
        degrees = adjacency.sum(axis=1)
        union = degrees[:, None] + degrees[None, :] - shared
        with np.errstate(divide="ignore", invalid="ignore"):
            neighbour_jaccard = np.where(union > 0, shared / union, 0.0)
        np.fill_diagonal(neighbour_jaccard, 0.0)
        return (0.5 * adjacency + 0.5 * neighbour_jaccard).astype(np.float32)


def affinity_matrix(
    context: AffinityContext,
    families: Mapping[str, Iterable[str]],
    *,
    weights: Mapping[str, float],
) -> tuple[np.ndarray, dict[str, np.ndarray], list[str]]:
    """Compute the pathway-by-family affinity matrix from a plain family mapping.

    Exposed separately from :func:`family_affinity` so that the hybrid builders can
    score pathways against a family set that is still being constructed and does not
    yet exist as a :class:`~pathways_analysis.family_features.CandidateFamilySet`.

    Args:
        context: Pre-computed similarity data.
        families: ``{family_id: member pathway keys}``.
        weights: Weight per dimension in :data:`WEIGHT_DIMENSIONS`. Expected to sum
            to 1; the configuration loader guarantees this.

    Returns:
        ``(affinity, components, family_ids)`` where ``affinity`` is
        ``pathways x families`` and ``components`` holds the same shape per dimension.
    """
    family_ids = sorted(families)
    pathway_index = {value: position for position, value in enumerate(context.pathways)}

    membership = np.zeros((len(family_ids), len(context.pathways)), dtype=np.float32)
    for family_position, family_id in enumerate(family_ids):
        for pathway_key in families[family_id]:
            position = pathway_index.get(pathway_key)
            if position is not None:
                membership[family_position, position] = 1.0
    family_sizes = membership.sum(axis=1)

    components: dict[str, np.ndarray] = {}

    # Feature components: mean similarity to the family's members, excluding self.
    for dimension in ROUTING_FEATURE_DIMENSIONS:
        similarity = context.jaccard[dimension]
        totals = similarity @ membership.T  # pathways x families
        # Remove the pathway's own contribution where it is a member. Self-similarity
        # is 1 for any pathway with at least one feature and 0 otherwise, so the
        # diagonal is used rather than assuming 1.
        self_similarity = np.diag(similarity)[:, None] * membership.T
        counts = np.tile(family_sizes, (len(context.pathways), 1)) - membership.T
        with np.errstate(divide="ignore", invalid="ignore"):
            components[dimension] = np.where(
                counts > 0, (totals - self_similarity) / counts, 0.0
            ).astype(np.float32)

    # Graph component: share of the pathway's distinct neighbours inside the family.
    neighbours_in_family = context.neighbour_matrix @ membership.T
    denominator = context.neighbour_totals[:, None]
    with np.errstate(divide="ignore", invalid="ignore"):
        components["graph"] = np.where(
            denominator > 0, neighbours_in_family / denominator, 0.0
        ).astype(np.float32)

    affinity = np.zeros((len(context.pathways), len(family_ids)), dtype=np.float32)
    for dimension in WEIGHT_DIMENSIONS:
        weight = float(weights.get(dimension, 0.0))
        if weight <= 0 or dimension not in components:
            continue
        affinity += weight * components[dimension]
    return affinity, components, family_ids


def family_affinity(
    candidate: CandidateFamilySet,
    context: AffinityContext,
    *,
    weights: Mapping[str, float],
) -> tuple[np.ndarray, dict[str, np.ndarray], list[str]]:
    """Compute the pathway-by-family affinity matrix for a candidate family set.

    Thin wrapper over :func:`affinity_matrix`, kept so callers holding a
    :class:`~pathways_analysis.family_features.CandidateFamilySet` do not have to
    unpack it.
    """
    return affinity_matrix(context, candidate.families(), weights=weights)


def routing_ambiguity(
    candidate: CandidateFamilySet,
    model: PathwayFeatureModel,
    context: AffinityContext,
    *,
    config: FamilyDiscoveryConfig,
) -> pd.DataFrame:
    """Score every pathway against every candidate family (section 14).

    Returns:
        One row per pathway with its dominant and second-best family, the ambiguity
        score, the number of plausible families, the component breakdown for the
        dominant family, and its actual assigned membership. Classification thresholds
        come from configuration and are echoed onto each row.
    """
    if not candidate.family_ids:
        return pd.DataFrame()

    affinity, components, family_ids = family_affinity(
        candidate, context, weights=config.routing_weights
    )
    labels = candidate.labels()
    assigned = (
        candidate.membership.groupby("pathway_key")["family_id"]
        .apply(lambda values: sorted(set(values)))
        .to_dict()
    )
    titles = model.features.set_index("PathwayKey")[["PathwayID", "PathwayTitle"]]

    order = np.argsort(-affinity, axis=1, kind="stable")
    records = []
    for position, pathway_key in enumerate(context.pathways):
        scores = affinity[position]
        ranked = order[position]
        best_index = int(ranked[0])
        best = float(scores[best_index])
        second_index = int(ranked[1]) if len(ranked) > 1 else None
        second = float(scores[second_index]) if second_index is not None else 0.0

        if best <= 0:
            ambiguity = float("nan")
            classification = "no structural association"
            plausible_ids: list[str] = []
        else:
            ambiguity = round(second / best, 6)
            plausible_mask = scores >= config.routing_plausible_affinity_ratio * best
            plausible_ids = [
                family_ids[index]
                for index in np.flatnonzero(plausible_mask & (scores > 0))
            ]
            if ambiguity >= config.routing_high_ambiguity:
                classification = "high ambiguity"
            elif ambiguity >= config.routing_moderate_ambiguity:
                classification = "moderate ambiguity"
            else:
                classification = "strong single-family association"

        assigned_ids = assigned.get(pathway_key, [])
        title_row = (
            titles.loc[pathway_key] if pathway_key in titles.index else None
        )
        records.append(
            {
                "strategy": candidate.strategy,
                "PathwayID": title_row["PathwayID"] if title_row is not None else pathway_key,
                "PathwayKey": pathway_key,
                "PathwayTitle": title_row["PathwayTitle"] if title_row is not None else "",
                "AssignedFamilyIds": " | ".join(assigned_ids),
                "AssignedFamilyCount": len(assigned_ids),
                "DominantFamilyId": family_ids[best_index],
                "DominantFamilyLabel": labels.get(family_ids[best_index], ""),
                "DominantAffinity": round(best, 6),
                "SecondFamilyId": family_ids[second_index] if second_index is not None else "",
                "SecondFamilyLabel": (
                    labels.get(family_ids[second_index], "") if second_index is not None else ""
                ),
                "SecondAffinity": round(second, 6),
                "AmbiguityScore": ambiguity,
                "PlausibleFamilyCount": len(plausible_ids),
                "PlausibleFamilyIds": " | ".join(plausible_ids),
                "AmbiguityClassification": classification,
                "DominantMatchesAssignedFamily": family_ids[best_index] in assigned_ids,
                "AffinityGraphComponent": round(
                    float(components["graph"][position, best_index]), 6
                ),
                "AffinityQuestionComponent": round(
                    float(components["question"][position, best_index]), 6
                ),
                "AffinitySdComponent": round(
                    float(components["symptom_discriminator"][position, best_index]), 6
                ),
                "AffinitySnomedComponent": round(
                    float(components["snomed"][position, best_index]), 6
                ),
                "AffinityDispositionComponent": round(
                    float(components["disposition"][position, best_index]), 6
                ),
                "ModerateAmbiguityThreshold": config.routing_moderate_ambiguity,
                "HighAmbiguityThreshold": config.routing_high_ambiguity,
                "PlausibleAffinityRatio": config.routing_plausible_affinity_ratio,
            }
        )
    return pd.DataFrame(records).sort_values(
        ["strategy", "AmbiguityScore", "PathwayKey"],
        ascending=[True, False, True],
        ignore_index=True,
    )


def routing_summary(routing: pd.DataFrame) -> pd.DataFrame:
    """Summarise routing ambiguity per strategy (section 14 summary).

    Reports the share of pathways associated with one, two, and three or more plausible
    families, where "plausible" is the configured affinity ratio relative to the best
    family.
    """
    if routing.empty:
        return pd.DataFrame()
    records = []
    for strategy, group in routing.groupby("strategy"):
        total = max(len(group), 1)
        counts = group["PlausibleFamilyCount"]
        records.append(
            {
                "strategy": strategy,
                "PathwaysScored": len(group),
                "PathwaysWithOnePlausibleFamily": int((counts == 1).sum()),
                "PercentageOnePlausibleFamily": round(
                    100.0 * float((counts == 1).sum()) / total, 2
                ),
                "PathwaysWithTwoPlausibleFamilies": int((counts == 2).sum()),
                "PercentageTwoPlausibleFamilies": round(
                    100.0 * float((counts == 2).sum()) / total, 2
                ),
                "PathwaysWithThreeOrMorePlausibleFamilies": int((counts >= 3).sum()),
                "PercentageThreeOrMorePlausibleFamilies": round(
                    100.0 * float((counts >= 3).sum()) / total, 2
                ),
                "PathwaysWithNoStructuralAssociation": int(
                    (group["AmbiguityClassification"] == "no structural association").sum()
                ),
                "PercentageStrongSingleFamilyAssociation": round(
                    100.0
                    * float(
                        (
                            group["AmbiguityClassification"]
                            == "strong single-family association"
                        ).sum()
                    )
                    / total,
                    2,
                ),
                "PercentageModerateAmbiguity": round(
                    100.0
                    * float((group["AmbiguityClassification"] == "moderate ambiguity").sum())
                    / total,
                    2,
                ),
                "PercentageHighAmbiguity": round(
                    100.0 * float((group["AmbiguityClassification"] == "high ambiguity").sum())
                    / total,
                    2,
                ),
                "MeanAmbiguityScore": round(float(group["AmbiguityScore"].mean()), 4),
                "MedianAmbiguityScore": round(float(group["AmbiguityScore"].median()), 4),
                "PercentageDominantMatchesAssigned": round(
                    100.0 * float(group["DominantMatchesAssignedFamily"].sum()) / total, 2
                ),
            }
        )
    return pd.DataFrame(records).sort_values("strategy", ignore_index=True)


def secondary_family_candidates(
    routing: pd.DataFrame,
    *,
    strategy: str,
    max_secondary: int = 3,
) -> dict[str, list[str]]:
    """Return plausible non-assigned families per pathway, for the membership output.

    Used to populate ``SecondaryFamilyCandidates`` in
    ``candidate_family_membership.csv``: a pathway with a second family above the
    plausibility ratio is evidence of overlapping membership, not noise.
    """
    if routing.empty:
        return {}
    subset = routing.loc[routing["strategy"] == strategy]
    result: dict[str, list[str]] = {}
    for row in subset.itertuples():
        assigned = {value for value in str(row.AssignedFamilyIds).split(" | ") if value}
        plausible = [
            value
            for value in str(row.PlausibleFamilyIds).split(" | ")
            if value and value not in assigned
        ]
        result[row.PathwayKey] = plausible[:max_secondary]
    return result


def pathway_family_edge_counts(
    candidate: CandidateFamilySet,
    model: PathwayFeatureModel,
) -> pd.DataFrame:
    """Count each pathway's graph edges to each family (input to boundary analysis).

    Direction is preserved so an outbound-only relationship is distinguishable from a
    mutual one.

    Returns:
        Long-format frame with ``pathway_key``, ``family_id``, ``edges_out``,
        ``edges_in`` and ``transitions``, restricted to non-zero rows.
    """
    families = candidate.families()
    membership_by_pathway: dict[str, set[str]] = {}
    for family_id, members in families.items():
        for member in members:
            membership_by_pathway.setdefault(member, set()).add(family_id)

    graph = model.pathway_graph
    counts: dict[tuple[str, str], dict[str, int]] = {}
    for pathway in model.scope:
        if pathway not in graph:
            continue
        for _, target, data in graph.out_edges(pathway, data=True):
            for family_id in membership_by_pathway.get(target, set()):
                entry = counts.setdefault(
                    (pathway, family_id), {"edges_out": 0, "edges_in": 0, "transitions": 0}
                )
                entry["edges_out"] += 1
                entry["transitions"] += int(data.get("transition_count", 0) or 0)
        for source, _, data in graph.in_edges(pathway, data=True):
            for family_id in membership_by_pathway.get(source, set()):
                entry = counts.setdefault(
                    (pathway, family_id), {"edges_out": 0, "edges_in": 0, "transitions": 0}
                )
                entry["edges_in"] += 1
                entry["transitions"] += int(data.get("transition_count", 0) or 0)

    if not counts:
        return pd.DataFrame(
            columns=["pathway_key", "family_id", "edges_out", "edges_in", "transitions"]
        )
    records = [
        {"pathway_key": pathway, "family_id": family_id, **values}
        for (pathway, family_id), values in counts.items()
    ]
    return pd.DataFrame(records).sort_values(
        ["pathway_key", "family_id"], ignore_index=True
    )


def plausible_family_counts(routing: pd.DataFrame) -> dict[str, int]:
    """Return ``{pathway_key: plausible family count}`` for one strategy's routing rows."""
    if routing.empty:
        return {}
    return dict(zip(routing["PathwayKey"], routing["PlausibleFamilyCount"].astype(int)))


def affinity_to_families(
    candidate: CandidateFamilySet,
    context: AffinityContext,
    *,
    weights: Mapping[str, float],
    pathways: Sequence[str] | None = None,
) -> pd.DataFrame:
    """Return the full pathway-by-family affinity matrix in long format.

    Exported for the primary candidate strategy only: at 815 pathways it is one row per
    pathway-family pair, which is informative for the primary set and noise for all 15
    strategies at once.
    """
    affinity, components, family_ids = family_affinity(candidate, context, weights=weights)
    selected = list(pathways) if pathways is not None else context.pathways
    index = {value: position for position, value in enumerate(context.pathways)}
    records = []
    for pathway in selected:
        position = index.get(pathway)
        if position is None:
            continue
        for family_position, family_id in enumerate(family_ids):
            score = float(affinity[position, family_position])
            if score <= 0:
                continue
            records.append(
                {
                    "strategy": candidate.strategy,
                    "pathway_key": pathway,
                    "family_id": family_id,
                    "affinity": round(score, 6),
                    "graph_component": round(
                        float(components["graph"][position, family_position]), 6
                    ),
                    "question_component": round(
                        float(components["question"][position, family_position]), 6
                    ),
                    "sd_component": round(
                        float(components["symptom_discriminator"][position, family_position]), 6
                    ),
                    "snomed_component": round(
                        float(components["snomed"][position, family_position]), 6
                    ),
                    "disposition_component": round(
                        float(components["disposition"][position, family_position]), 6
                    ),
                }
            )
    if not records:
        return pd.DataFrame()
    return pd.DataFrame(records).sort_values(
        ["pathway_key", "affinity"], ascending=[True, False], ignore_index=True
    )
