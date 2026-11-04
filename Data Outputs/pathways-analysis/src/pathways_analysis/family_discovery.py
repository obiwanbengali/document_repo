"""Phase 2 runner: candidate Bayesian Network family discovery.

Usage::

    python -m pathways_analysis.family_discovery
    python -m pathways_analysis.family_discovery --strategy graph
    python -m pathways_analysis.family_discovery --no-charts
    python -m pathways_analysis.family_discovery --config config/family_discovery.yaml

The run validates connectivity, extracts read-only from SQL Server, generates candidate
family sets three independent ways, measures cohesion, overlap, boundaries, shared-core
features and routing ambiguity, and writes the evidence base under
``outputs/phase2/``.

Scope boundary
--------------
Phase 2 answers *what families could exist, how much they overlap, and what shared
structure they need*. It deliberately produces **no** Bayesian sizing, CPT estimate,
memory figure, infrastructure sizing, cost model, or monolithic-vs-federated
recommendation. Those are Phase 3.

Phase 1 outputs under ``outputs/tables/`` and ``outputs/charts/`` are never written by
this module.
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Final, Mapping, Sequence

import networkx as nx
import numpy as np
import pandas as pd

from . import (
    exports,
    family_boundaries,
    family_charts,
    family_core,
    family_evaluation,
    family_overlap,
    family_report,
    family_routing,
)
from . import graph as graph_tools
from .config import (
    ConfigurationError,
    DatabaseSettings,
    Paths,
    load_dotenv_if_present,
)
from .db import DatabaseConnectionError, PathwaysDatabase, normalise_id
from .family_config import (
    FamilyDiscoveryConfig,
    default_config_path,
    load_family_config,
)
from .family_features import (
    FAMILY_BASIS_GRAPH,
    FAMILY_BASIS_HYBRID,
    UNASSIGNED,
    CandidateFamilySet,
    PairwiseSimilarity,
    PathwayFeatureModel,
    build_feature_maps,
    build_membership_frame,
    build_pathway_feature_model,
    graph_similarity_table,
    native_candidate_sets,
    native_group_metrics,
    similarity_tables,
)

LOGGER: Final = logging.getLogger("pathways_analysis.phase2")

#: Phase 1 queries Phase 2 reuses rather than duplicating.
PHASE1_QUERIES: Final[tuple[str, ...]] = (
    "inventory",
    "pathways",
    "symptom_groups",
    "symptom_discriminators",
    "clinical_areas",
    "pathway_clinical_areas",
    "triage_logic",
    "pathway_complexity",
    "pathway_discriminators",
    "pathway_snomed",
    "transfer_values",
)

#: Queries added by Phase 2.
PHASE2_QUERIES: Final[tuple[str, ...]] = (
    "pathway_ages",
    "pathway_genders",
    "pathway_trauma",
    "age_reference",
    "gender_reference",
    "trauma_reference",
    "pathway_disposition_nodes",
    "pathway_disposition_transfers",
    "pathway_transition_edges",
    "symptom_group_transition_matrix",
    "symptom_group_pair_shared_discriminators",
    "clinical_area_pair_shared_pathways",
    "symptom_group_pair_shared_questions",
    "feature_pathway_counts",
    "disposition_catalogue",
)

#: Strategies excluded from the full metric battery, with the reason. Recorded rather
#: than silently skipped, because "excluded by judgement" and "not produced" are
#: different findings.
BATTERY_EXCLUSIONS: Final[dict[str, str]] = {
    "graph_strongly_connected": (
        "strongly connected components are a connectivity diagnostic, not a candidate "
        "family set: almost every component is a singleton, so overlap and routing "
        "metrics over them would measure the partition's triviality rather than any "
        "family structure. The component counts are still reported in "
        "community_method_comparison.csv and graph_community_summary.csv"
    ),
    "native_module": (
        "tblPathways.Module carries no value in this snapshot, so the grouping has one "
        "family and cannot separate pathways"
    ),
}


@dataclass
class Phase2Result:
    """Outcome of a Phase 2 run, used for the terminal summary."""

    tables_written: list[Path] = field(default_factory=list)
    charts_written: list[Path] = field(default_factory=list)
    reports_written: list[Path] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    strategies_tested: int = 0
    community_methods_run: int = 0
    graph_communities: int = 0
    hybrid_families: int = 0
    median_family_size: float = float("nan")
    largest_family_size: int = 0
    strong_overlap_pairs: int = 0
    strong_overlap_pairs_presented: int = 0
    presented_family_count: int = 0
    boundary_pathways: int = 0
    shared_core_features: int = 0
    percentage_single_family: float = float("nan")
    percentage_ambiguous: float = float("nan")
    elapsed_seconds: float = 0.0


# ======================================================================================
# Hybrid strategies (section 5)
# ======================================================================================
def _absorb_small_families(
    families: dict[str, set[str]],
    context: family_routing.AffinityContext,
    *,
    config: FamilyDiscoveryConfig,
) -> tuple[dict[str, set[str]], dict[str, str], list[str]]:
    """Merge families below the minimum size into their highest-affinity neighbour.

    Absorption is decided at the level of the whole small family rather than per
    pathway: a small graph community is a coherent unit, and splitting it across
    several destinations would discard the evidence that put its members together.

    A small family is only absorbed when its mean affinity to the destination reaches
    ``hybrid_a.absorption_affinity_floor``. Below that there is no structural reason to
    attach it anywhere, so it is retained and flagged.

    Returns:
        ``(families, basis_by_family, notes)``.
    """
    large = {
        family_id: members
        for family_id, members in families.items()
        if len(members) >= config.minimum_family_size
    }
    small = {
        family_id: members
        for family_id, members in families.items()
        if len(members) < config.minimum_family_size
    }
    basis: dict[str, str] = {}
    notes: list[str] = []

    if not small:
        return dict(families), basis, notes
    if not large:
        notes.append(
            f"No family reached the minimum size of {config.minimum_family_size}, so "
            "no absorption was attempted."
        )
        return dict(families), basis, notes

    affinity, _, family_ids = family_routing.affinity_matrix(
        context, large, weights=config.routing_weights
    )
    pathway_index = {value: position for position, value in enumerate(context.pathways)}
    result = {family_id: set(members) for family_id, members in large.items()}
    absorbed = retained = 0

    for family_id in sorted(small):
        members = small[family_id]
        positions = [
            pathway_index[member] for member in members if member in pathway_index
        ]
        if not positions or not family_ids:
            result[family_id] = set(members)
            basis[family_id] = "small family retained: not present in the pathway graph scope"
            retained += 1
            continue
        mean_affinity = affinity[positions, :].mean(axis=0)
        best = int(np.argmax(mean_affinity))
        if float(mean_affinity[best]) >= config.hybrid_a_absorption_affinity_floor:
            result[family_ids[best]] |= set(members)
            absorbed += 1
        else:
            result[family_id] = set(members)
            basis[family_id] = (
                f"small family retained: best affinity "
                f"{float(mean_affinity[best]):.3f} below the absorption floor "
                f"{config.hybrid_a_absorption_affinity_floor}"
            )
            retained += 1

    notes.append(
        f"{absorbed} families below the minimum size of {config.minimum_family_size} "
        f"were absorbed into their highest-affinity neighbour; {retained} were retained "
        "because no destination reached the affinity floor."
    )
    return result, basis, notes


def build_hybrid_a(
    community_membership: Mapping[str, int],
    model: PathwayFeatureModel,
    similarity: PairwiseSimilarity,
    context: family_routing.AffinityContext,
    *,
    config: FamilyDiscoveryConfig,
) -> CandidateFamilySet:
    """HYBRID A: graph communities as the primary grouping, refined by clinical features.

    This is the only strategy that requires *both* kinds of evidence before a family is
    kept, which is why it is the default candidate set presented for review: the Phase 2
    brief rules out calling a graph cluster a clinical family unless clinical features
    support it.

    Rules, all thresholds from configuration:

    1. Start from the primary community partition over the in-scope pathways.
    2. For each community large enough to split, measure the mean pairwise
       symptom-discriminator Jaccard. Where it falls below
       ``hybrid_a.clinical_cohesion_threshold`` the community is not coherent on
       clinical vocabulary, so it is split by ``hybrid_a.split_feature``. Parts below
       ``family_size.minimum_split_part_size`` are returned to the community's largest
       part rather than left as fragments.
    3. Communities below ``family_size.minimum_family_size`` are absorbed into their
       highest-affinity neighbour, or retained and flagged where no neighbour reaches
       the affinity floor.

    A community that is already clinically coherent is left alone: refinement only ever
    fires where the clinical evidence says the graph grouping is mixed.
    """
    communities: dict[int, set[str]] = {}
    for pathway_key in model.scope:
        community_id = community_membership.get(pathway_key)
        if community_id is None:
            continue
        communities.setdefault(int(community_id), set()).add(pathway_key)

    unplaced = {
        pathway_key for pathway_key in model.scope if pathway_key not in community_membership
    }

    features = model.features.set_index("PathwayKey")
    split_column = (
        "SymptomGroupId"
        if config.hybrid_a_split_feature == "symptom_group"
        else "ClinicalAreas"
    )

    families: dict[str, set[str]] = {}
    basis: dict[str, str] = {}
    notes: list[str] = []
    split_count = 0

    for community_id in sorted(communities):
        members = communities[community_id]
        base_id = f"HA_C{community_id:02d}"
        cohesion = similarity.mean_within("symptom_discriminator", members)
        splittable = len(members) >= 2 * config.minimum_split_part_size
        incoherent = (
            pd.notna(cohesion)
            and cohesion < config.hybrid_a_clinical_cohesion_threshold
        )

        if not (splittable and incoherent):
            families[base_id] = set(members)
            basis[base_id] = (
                f"graph community {community_id} retained: mean SD Jaccard "
                f"{cohesion:.3f} at or above the clinical cohesion threshold "
                f"{config.hybrid_a_clinical_cohesion_threshold}"
                if pd.notna(cohesion) and not incoherent
                else f"graph community {community_id} retained: too small to split"
            )
            continue

        parts: dict[str, set[str]] = {}
        for pathway_key in sorted(members):
            if pathway_key not in features.index:
                continue
            value = features.at[pathway_key, split_column]
            if value is None or (not isinstance(value, str) and pd.isna(value)) or value == "":
                label = "unassigned"
            elif split_column == "ClinicalAreas":
                # A pathway may map to several clinical areas; the first alphabetically
                # is used so the split is deterministic, and the choice is recorded.
                label = str(value).split("|")[0].strip()
            else:
                label = f"sg{int(value)}"
            parts.setdefault(label, set()).add(pathway_key)

        viable = {
            label: part
            for label, part in parts.items()
            if len(part) >= config.minimum_split_part_size
        }
        if len(viable) < 2:
            families[base_id] = set(members)
            basis[base_id] = (
                f"graph community {community_id} retained: mean SD Jaccard "
                f"{cohesion:.3f} is below the clinical cohesion threshold but no "
                f"{config.hybrid_a_split_feature} split yields two viable parts"
            )
            continue

        split_count += 1
        largest_label = max(viable, key=lambda label: (len(viable[label]), label))
        remainder = members - set().union(*viable.values())
        for index, label in enumerate(sorted(viable)):
            part = set(viable[label])
            if label == largest_label:
                part |= remainder
            family_id = f"{base_id}_{index:02d}"
            families[family_id] = part
            basis[family_id] = (
                f"graph community {community_id} split on "
                f"{config.hybrid_a_split_feature} ({label}) because its mean SD "
                f"Jaccard {cohesion:.3f} was below "
                f"{config.hybrid_a_clinical_cohesion_threshold}"
            )

    if split_count:
        notes.append(
            f"{split_count} graph communities were split on "
            f"{config.hybrid_a_split_feature} because their mean pairwise "
            f"symptom-discriminator Jaccard fell below "
            f"{config.hybrid_a_clinical_cohesion_threshold}."
        )

    absorbed, absorption_basis, absorption_notes = _absorb_small_families(
        families, context, config=config
    )
    basis.update(absorption_basis)
    notes.extend(absorption_notes)

    if unplaced:
        absorbed["HA_UNPLACED"] = set(unplaced)
        basis["HA_UNPLACED"] = (
            "pathways absent from the community partition, retained as an explicit "
            "group rather than dropped"
        )
        notes.append(
            f"{len(unplaced)} in-scope pathways were not placed by the community "
            "partition and are held in HA_UNPLACED."
        )

    membership = build_membership_frame(
        absorbed,
        strategy="hybrid_a",
        labels={family_id: family_id for family_id in absorbed},
        membership_basis="hybrid_a",
    )
    membership["membership_basis"] = membership["family_id"].map(
        lambda family_id: basis.get(family_id, "graph community retained")
    )
    return CandidateFamilySet(
        strategy="hybrid_a",
        basis=FAMILY_BASIS_HYBRID,
        description=(
            f"Graph communities ({config.primary_community_method}) as the primary "
            "grouping, split on "
            f"{config.hybrid_a_split_feature} where mean pairwise symptom-discriminator "
            f"Jaccard < {config.hybrid_a_clinical_cohesion_threshold}, with communities "
            f"below {config.minimum_family_size} pathways absorbed by affinity."
        ),
        membership=membership,
        notes=notes,
    )


def build_hybrid_b(
    model: PathwayFeatureModel,
    similarity: PairwiseSimilarity,
    *,
    config: FamilyDiscoveryConfig,
) -> CandidateFamilySet:
    """HYBRID B: NHS-native grouping as primary, split where graph evidence is weak.

    The primary key is the pathway's ``SymptomGroupId`` where it has one, otherwise its
    **most specific** clinical area -- the one covering the fewest in-scope pathways.
    "Most specific" is used rather than "first" because clinical areas overlap and a
    pathway mapped to 21 of them would otherwise be assigned essentially at random;
    the narrowest area is the most informative of the ones available.

    A group is split when its internal-edge percentage falls below
    ``hybrid_b.weak_cohesion_internal_edge_pct``, meaning its pathways mostly transfer
    outside the group. The split uses community detection on the group's induced
    subgraph, so the split follows measured routing rather than another metadata field.

    Unlike Hybrid A, small families are **not** absorbed: an NHS grouping with three
    pathways is still a clinically meaningful unit, and absorbing it would discard the
    native structure this strategy exists to test.
    """
    features = model.features
    area_sizes: dict[str, int] = {}
    for row in features.itertuples():
        for part in str(row.ClinicalAreas or "").split("|"):
            area = part.strip()
            if area:
                area_sizes[area] = area_sizes.get(area, 0) + 1

    groups: dict[str, set[str]] = {}
    labels: dict[str, str] = {}
    key_basis: dict[str, str] = {}
    for row in features.itertuples():
        if pd.notna(row.SymptomGroupId):
            key = f"sg{int(row.SymptomGroupId)}"
            labels.setdefault(
                key, f"{row.SymptomGroupDescription} [SymptomGroupId={int(row.SymptomGroupId)}]"
            )
            key_basis.setdefault(key, "nhs_native:SymptomGroupId")
        else:
            areas = [
                part.strip()
                for part in str(row.ClinicalAreas or "").split("|")
                if part.strip()
            ]
            if areas:
                narrowest = min(areas, key=lambda area: (area_sizes.get(area, 0), area))
                key = f"ca:{narrowest}"
                labels.setdefault(key, f"{narrowest} [most specific clinical area]")
                key_basis.setdefault(
                    key, "nhs_native:ClinicalArea (no SymptomGroupId; most specific area used)"
                )
            else:
                key = UNASSIGNED
                labels.setdefault(key, UNASSIGNED)
                key_basis.setdefault(
                    key, "no SymptomGroupId and no clinical area; retained explicitly"
                )
        groups.setdefault(key, set()).add(row.PathwayKey)

    families: dict[str, set[str]] = {}
    family_labels: dict[str, str] = {}
    basis: dict[str, str] = {}
    notes: list[str] = []
    split_count = 0

    ordered = sorted(groups.items(), key=lambda item: (-len(item[1]), item[0]))
    for index, (key, members) in enumerate(ordered):
        base_id = f"HB_{index:03d}"
        metrics = family_evaluation.cohesion_for_group(members, model, similarity=similarity)
        internal = metrics["InternalEdgePercentage"]
        weak = (
            pd.notna(internal)
            and internal < config.hybrid_b_weak_cohesion_internal_edge_pct
        )
        splittable = len(members) >= 2 * config.minimum_split_part_size

        if not (weak and splittable):
            families[base_id] = set(members)
            family_labels[base_id] = labels.get(key, key)
            basis[base_id] = (
                f"{key_basis.get(key, 'nhs_native')} retained: internal-edge "
                + (
                    f"{internal:.1f}% at or above "
                    f"{config.hybrid_b_weak_cohesion_internal_edge_pct}%"
                    if pd.notna(internal) and not weak
                    else "percentage not measurable or group too small to split"
                )
            )
            continue

        subgraph = nx.DiGraph(model.pathway_graph.subgraph(members))
        projection = graph_tools.undirected_projection(subgraph)
        try:
            partition = graph_tools.partition_undirected(projection, "louvain")
        except Exception as exc:  # noqa: BLE001 - one failed split must not stop the run
            LOGGER.debug("Hybrid B split failed for %s: %s", key, exc)
            partition = {}

        parts: dict[int, set[str]] = {}
        for pathway_key, community_id in partition.items():
            parts.setdefault(int(community_id), set()).add(pathway_key)
        viable = {
            community_id: part
            for community_id, part in parts.items()
            if len(part) >= config.minimum_split_part_size
        }
        if len(viable) < 2:
            families[base_id] = set(members)
            family_labels[base_id] = labels.get(key, key)
            basis[base_id] = (
                f"{key_basis.get(key, 'nhs_native')} retained: internal-edge "
                f"{internal:.1f}% is weak but the group has no two viable graph "
                "subcommunities"
            )
            continue

        split_count += 1
        largest = max(
            viable, key=lambda community_id: (len(viable[community_id]), community_id)
        )
        remainder = members - set().union(*viable.values())
        for part_index, community_id in enumerate(sorted(viable)):
            part = set(viable[community_id])
            if community_id == largest:
                part |= remainder
            family_id = f"{base_id}_{part_index:02d}"
            families[family_id] = part
            family_labels[family_id] = f"{labels.get(key, key)} — graph part {part_index}"
            basis[family_id] = (
                f"{key_basis.get(key, 'nhs_native')} split on graph subcommunity "
                f"because its internal-edge percentage {internal:.1f}% was below "
                f"{config.hybrid_b_weak_cohesion_internal_edge_pct}%"
            )

    if split_count:
        notes.append(
            f"{split_count} NHS-native groups were split on graph subcommunities "
            f"because their internal-edge percentage fell below "
            f"{config.hybrid_b_weak_cohesion_internal_edge_pct}%."
        )
    notes.append(
        "Small families are retained rather than absorbed: an NHS grouping with few "
        "pathways is still a native unit, and absorbing it would discard the structure "
        "this strategy exists to test."
    )

    membership = build_membership_frame(
        families,
        strategy="hybrid_b",
        labels=family_labels,
        membership_basis="hybrid_b",
    )
    membership["membership_basis"] = membership["family_id"].map(
        lambda family_id: basis.get(family_id, "nhs_native retained")
    )
    return CandidateFamilySet(
        strategy="hybrid_b",
        basis=FAMILY_BASIS_HYBRID,
        description=(
            "NHS-native grouping as primary (SymptomGroupId, else the most specific "
            "clinical area), split on graph subcommunities where the group's "
            f"internal-edge percentage < {config.hybrid_b_weak_cohesion_internal_edge_pct}%."
        ),
        membership=membership,
        notes=notes,
    )


def hybrid_c_partition(
    context: family_routing.AffinityContext,
    *,
    weights: Mapping[str, float],
    similarity_threshold: float,
    clustering_method: str,
    leiden_resolution: float = 1.0,
) -> dict[str, int]:
    """Cluster pathways on a weighted combination of every evidence dimension.

    The weighted similarity matrix is thresholded before clustering: below the
    threshold a pair is not treated as related at all. Without a threshold the graph is
    almost complete -- 59% of pathway pairs share at least one question -- and community
    detection on a near-complete graph returns the graph.

    Returns:
        ``{pathway_key: community_id}``, renumbered so id 0 is the largest cluster.
    """
    pathways = context.pathways
    combined = np.zeros((len(pathways), len(pathways)), dtype=np.float32)
    for dimension in ("question", "symptom_discriminator", "snomed", "disposition"):
        weight = float(weights.get(dimension, 0.0))
        if weight > 0:
            combined += weight * context.jaccard[dimension]
    graph_weight = float(weights.get("graph", 0.0))
    if graph_weight > 0:
        combined += graph_weight * context.graph_pairwise_similarity()
    np.fill_diagonal(combined, 0.0)

    similarity_graph = nx.Graph()
    similarity_graph.add_nodes_from(pathways)
    rows, columns = np.triu_indices(len(pathways), k=1)
    values = combined[rows, columns]
    keep = values >= similarity_threshold
    for row, column, value in zip(rows[keep], columns[keep], values[keep]):
        similarity_graph.add_edge(pathways[row], pathways[column], weight=float(value))

    if similarity_graph.number_of_edges() == 0:
        return {pathway: index for index, pathway in enumerate(pathways)}
    return graph_tools._renumber_by_size(  # noqa: SLF001 - same package, shared helper
        graph_tools.partition_undirected(
            similarity_graph, clustering_method, resolution=leiden_resolution
        )
    )


def build_hybrid_c(
    context: family_routing.AffinityContext,
    *,
    config: FamilyDiscoveryConfig,
) -> tuple[CandidateFamilySet, dict[str, int]]:
    """HYBRID C: clustering on a transparent weighted combination of all dimensions.

    Every weight is exposed in ``hybrid_c_weights`` and the defaults are an
    **experimental baseline only**. The accompanying sensitivity analysis measures
    whether family membership changes materially when the weights change; if it does,
    Hybrid C's families cannot be treated as a settled result.

    Returns:
        ``(candidate set, membership)`` -- the membership is returned so the sensitivity
        analysis can compare variants against it without recomputing.
    """
    membership = hybrid_c_partition(
        context,
        weights=config.hybrid_c_weights,
        similarity_threshold=config.hybrid_c_similarity_threshold,
        clustering_method=config.hybrid_c_clustering_method,
        leiden_resolution=config.leiden_resolution,
    )
    families: dict[str, set[str]] = {}
    for pathway_key, cluster_id in membership.items():
        families.setdefault(f"HC_{int(cluster_id):03d}", set()).add(pathway_key)

    weight_text = ", ".join(
        f"{key}={value:.2f}" for key, value in sorted(config.hybrid_c_weights.items())
    )
    frame = build_membership_frame(
        families,
        strategy="hybrid_c",
        labels={family_id: family_id for family_id in families},
        membership_basis=(
            f"hybrid_c weighted similarity clustering ({weight_text}), threshold "
            f"{config.hybrid_c_similarity_threshold}"
        ),
    )
    return (
        CandidateFamilySet(
            strategy="hybrid_c",
            basis=FAMILY_BASIS_HYBRID,
            description=(
                f"{config.hybrid_c_clustering_method} clustering of a weighted "
                f"similarity graph ({weight_text}) thresholded at "
                f"{config.hybrid_c_similarity_threshold}. The weighting is an "
                "experimental baseline and is not clinically validated."
            ),
            membership=frame,
            notes=[
                "The default weighting is not clinically validated. See "
                "hybrid_family_sensitivity.csv for what changes when it changes.",
            ],
        ),
        membership,
    )


def hybrid_c_sensitivity(
    context: family_routing.AffinityContext,
    default_membership: Mapping[str, int],
    *,
    config: FamilyDiscoveryConfig,
) -> pd.DataFrame:
    """Re-run Hybrid C under each configured weight variant and measure the change.

    Two agreement measures are reported because they answer different questions:

    * **adjusted Rand index** -- whether the variant groups the same *pairs* of
      pathways together, independent of how families are labelled or how many there are.
    * **membership changed percentage** -- after greedily matching each variant family
      to the default family it overlaps most, the share of pathways that land somewhere
      different. This is the figure a reviewer cares about: how many pathways would move.
    """
    records = []
    default_families: dict[int, set[str]] = {}
    for pathway_key, cluster_id in default_membership.items():
        default_families.setdefault(int(cluster_id), set()).add(pathway_key)

    for variant in config.hybrid_c_sensitivity:
        membership = hybrid_c_partition(
            context,
            weights=variant.weights,
            similarity_threshold=config.hybrid_c_similarity_threshold,
            clustering_method=config.hybrid_c_clustering_method,
            leiden_resolution=config.leiden_resolution,
        )
        sizes = pd.Series(list(membership.values())).value_counts()
        ari = graph_tools.adjusted_rand_index(default_membership, membership)
        changed = _membership_change_percentage(default_membership, membership)
        records.append(
            {
                "variant": variant.name,
                "weights": ", ".join(
                    f"{key}={value:.2f}" for key, value in sorted(variant.weights.items())
                ),
                "family_count": int(len(sizes)),
                "median_family_size": float(sizes.median()) if len(sizes) else float("nan"),
                "largest_family_size": int(sizes.max()) if len(sizes) else 0,
                "singleton_families": int((sizes == 1).sum()),
                "adjusted_rand_index_vs_default": round(ari, 6),
                "membership_changed_percentage": round(changed, 2),
                "default_family_count": int(len(default_families)),
                "similarity_threshold": config.hybrid_c_similarity_threshold,
                "clustering_method": config.hybrid_c_clustering_method,
                "interpretation_guard": (
                    "agreement is with the default weighting only; neither weighting is "
                    "clinically validated"
                ),
            }
        )
    if not records:
        return pd.DataFrame()
    return pd.DataFrame(records).sort_values(
        "adjusted_rand_index_vs_default", ascending=False, ignore_index=True
    )


def _membership_change_percentage(
    default_membership: Mapping[str, int],
    variant_membership: Mapping[str, int],
) -> float:
    """Return the share of pathways placed differently after greedy family matching.

    Each variant family is matched to the default family it shares the most pathways
    with. A pathway counts as moved when its variant family's matched default family is
    not its own default family. Greedy matching is used rather than an optimal
    assignment because the two partitions can have different family counts, where an
    optimal one-to-one matching does not exist.
    """
    shared = sorted(set(default_membership) & set(variant_membership))
    if not shared:
        return float("nan")

    variant_groups: dict[int, list[str]] = {}
    for pathway_key in shared:
        variant_groups.setdefault(int(variant_membership[pathway_key]), []).append(pathway_key)

    moved = 0
    for members in variant_groups.values():
        counts: dict[int, int] = {}
        for pathway_key in members:
            default_id = int(default_membership[pathway_key])
            counts[default_id] = counts.get(default_id, 0) + 1
        matched = max(counts.items(), key=lambda item: (item[1], -item[0]))[0]
        moved += sum(
            1 for pathway_key in members if int(default_membership[pathway_key]) != matched
        )
    return 100.0 * moved / len(shared)


# ======================================================================================
# Naming and final candidate outputs (sections 21 and 22)
# ======================================================================================
def derive_family_names(
    candidate: CandidateFamilySet,
    cohesion: pd.DataFrame,
    *,
    config: FamilyDiscoveryConfig,
) -> pd.DataFrame:
    """Derive a display name for each family, or a neutral one where none is justified.

    A name is taken from dominant NHS metadata only when one value covers at least
    ``presentation.naming_dominance_threshold`` of the family's pathways. Symptom group
    is tried first, then clinical area, then area group. Otherwise the family keeps a
    neutral name such as ``Community_07``, and its dominant metadata is reported in
    separate columns.

    Inventing a clinical-sounding name for a community that has no dominant grouping
    would be the single most misleading thing this analysis could do: the name would be
    read as a clinical claim that nothing in the evidence supports.

    Returns:
        Frame with ``FamilyId``, ``FamilyName`` and ``FamilyNameBasis``.
    """
    subset = cohesion.loc[cohesion["strategy"] == candidate.strategy]
    neutral_prefix = "Community" if candidate.basis == FAMILY_BASIS_GRAPH else "Family"
    records = []
    for position, row in enumerate(
        subset.sort_values(["PathwayCount", "FamilyId"], ascending=[False, True]).itertuples()
    ):
        name = ""
        basis = "neutral"
        for share_column, value_column, label in (
            ("DominantSymptomGroupShare", "DominantSymptomGroup", "dominant symptom group"),
            ("DominantClinicalAreaShare", "DominantClinicalArea", "dominant clinical area"),
            ("DominantAreaGroupShare", "DominantAreaGroup", "dominant area group"),
        ):
            share = float(getattr(row, share_column, 0.0) or 0.0)
            value = str(getattr(row, value_column, "") or "").strip()
            if value and share >= config.naming_dominance_threshold:
                name = value
                basis = f"{label} ({share:.0%} of the family's pathways)"
                break
        if not name:
            name = f"{neutral_prefix}_{position:02d}"
        records.append(
            {
                "FamilyId": row.FamilyId,
                "FamilyName": name,
                "FamilyNameBasis": basis,
                "NamingDominanceThreshold": config.naming_dominance_threshold,
            }
        )
    frame = pd.DataFrame(records)
    if frame.empty:
        return frame

    # Two families can share a dominant metadata value -- two small communities both
    # dominated by the same symptom group, for example. Names must stay unique or the
    # review pack and the family table become ambiguous about which family is meant, so
    # the family id is appended to every member of a duplicated name.
    duplicated = frame["FamilyName"].duplicated(keep=False)
    if duplicated.any():
        frame.loc[duplicated, "FamilyName"] = (
            frame.loc[duplicated, "FamilyName"] + " (" + frame.loc[duplicated, "FamilyId"] + ")"
        )
        frame.loc[duplicated, "FamilyNameBasis"] = (
            frame.loc[duplicated, "FamilyNameBasis"]
            + "; family id appended because another family shares the same dominant value"
        )
    return frame


def candidate_family_table(
    candidate: CandidateFamilySet,
    cohesion: pd.DataFrame,
    overlap: pd.DataFrame,
    boundary: pd.DataFrame,
    shared_core: pd.DataFrame,
    names: pd.DataFrame,
    model: PathwayFeatureModel,
    *,
    config: FamilyDiscoveryConfig,
) -> pd.DataFrame:
    """Build ``candidate_bayesian_families.csv`` (section 21).

    ``ConfidenceInStructuralCohesion`` bands the family on graph and feature cohesion
    together, and is explicitly about **structure only**. A family can be
    structurally strong and clinically wrong, which is why
    ``ClinicalReviewRequired`` is true for every family without exception.
    """
    subset = cohesion.loc[cohesion["strategy"] == candidate.strategy].merge(
        names, on="FamilyId", how="left"
    )
    if subset.empty:
        return pd.DataFrame()

    overlap_subset = (
        overlap.loc[overlap["strategy"] == candidate.strategy]
        if not overlap.empty
        else pd.DataFrame()
    )
    strong_overlaps: dict[str, list[str]] = {}
    if not overlap_subset.empty and "OverlapBand" in overlap_subset.columns:
        high = overlap_subset.loc[overlap_subset["OverlapBand"] == "high"]
        for row in high.itertuples():
            strong_overlaps.setdefault(row.FamilyA, []).append(row.FamilyB)
            strong_overlaps.setdefault(row.FamilyB, []).append(row.FamilyA)

    boundary_subset = (
        boundary.loc[boundary["strategy"] == candidate.strategy]
        if not boundary.empty
        else pd.DataFrame()
    )
    boundary_counts: dict[str, int] = {}
    hub_counts: dict[str, int] = {}
    if not boundary_subset.empty:
        for row in boundary_subset.itertuples():
            if row.BoundaryClassification == "internal pathway":
                continue
            for family_id in str(row.FamilyId).split(" | "):
                boundary_counts[family_id] = boundary_counts.get(family_id, 0) + 1
                if row.BoundaryClassification == "cross-family hub":
                    hub_counts[family_id] = hub_counts.get(family_id, 0) + 1

    core_dependencies: dict[str, int] = {}
    if not shared_core.empty:
        families = candidate.families()
        for dimension in shared_core["FeatureType"].unique():
            frame = getattr(model.maps, str(dimension), None)
            if frame is None or frame.empty:
                continue
            flagged = set(
                shared_core.loc[
                    shared_core["FeatureType"] == dimension, "FeatureId"
                ].astype(str)
            )
            relevant = frame.loc[frame["feature_id"].astype(str).isin(flagged)]
            by_pathway = {
                key: set(group)
                for key, group in relevant.groupby("pathway_key")["feature_id"]
            }
            for family_id, members in families.items():
                used: set[str] = set()
                for member in members:
                    used |= by_pathway.get(member, set())
                core_dependencies[family_id] = core_dependencies.get(family_id, 0) + len(used)

    records = []
    for row in subset.itertuples():
        overlaps = sorted(set(strong_overlaps.get(row.FamilyId, [])))
        records.append(
            {
                "FamilyId": row.FamilyId,
                "FamilyName": row.FamilyName,
                "FamilyNameBasis": row.FamilyNameBasis,
                "FamilyBasis": candidate.basis,
                "Strategy": candidate.strategy,
                "PathwayCount": int(row.PathwayCount),
                "PrimaryClinicalAreas": row.PrimaryClinicalAreas,
                "PrimarySymptomGroups": row.PrimarySymptomGroups,
                "DominantSymptomGroupShare": row.DominantSymptomGroupShare,
                "DominantClinicalAreaShare": row.DominantClinicalAreaShare,
                "InternalEdgePercentage": row.InternalEdgePercentage,
                "ExternalEdgePercentage": row.ExternalEdgePercentage,
                "UniqueQuestions": int(row.UniqueQuestionCount),
                "UniqueSDs": int(row.UniqueSymptomDiscriminatorCount),
                "UniqueSnomed": int(row.UniqueSnomedCount),
                "UniqueDispositions": int(row.UniqueDispositionCount),
                "MeanPairwiseSdJaccard": row.MeanPairwiseSdJaccard,
                "SharedQuestionPercentage": row.SharedQuestionPercentage,
                "BoundaryPathwayCount": boundary_counts.get(row.FamilyId, 0),
                "CrossFamilyHubCount": hub_counts.get(row.FamilyId, 0),
                "StrongOverlapFamilies": " | ".join(overlaps),
                "StrongOverlapFamilyCount": len(overlaps),
                "SharedCoreDependencyCount": core_dependencies.get(row.FamilyId, 0),
                "ConfidenceInStructuralCohesion": _cohesion_band(row, config),
                "ClinicalReviewRequired": True,
                "Notes": _family_notes(row, overlaps, boundary_counts.get(row.FamilyId, 0)),
            }
        )
    return pd.DataFrame(records).sort_values(
        ["PathwayCount", "FamilyId"], ascending=[False, True], ignore_index=True
    )


def _cohesion_band(row: object, config: FamilyDiscoveryConfig) -> str:
    """Band a family's structural cohesion. Structural only -- never a clinical verdict."""
    internal = float(getattr(row, "InternalEdgePercentage", float("nan")) or float("nan"))
    sd_cohesion = float(getattr(row, "MeanPairwiseSdJaccard", float("nan")) or float("nan"))
    graph_strong = pd.notna(internal) and internal >= 50.0
    graph_weak = pd.notna(internal) and internal < 25.0
    features_strong = (
        pd.notna(sd_cohesion) and sd_cohesion >= config.hybrid_a_clinical_cohesion_threshold
    )
    if graph_strong and features_strong:
        return "high (graph and clinical-feature evidence agree)"
    if graph_strong or features_strong:
        return "moderate (one of graph or clinical-feature evidence is strong)"
    if graph_weak:
        return "low (pathways mostly transfer outside the family)"
    return "low (neither graph nor clinical-feature cohesion is strong)"


def _family_notes(row: object, overlaps: Sequence[str], boundary_count: int) -> str:
    """Return factual notes for one candidate family."""
    notes = []
    if str(getattr(row, "FamilyNameBasis", "")) == "neutral":
        notes.append(
            "no dominant NHS grouping, so the name is neutral and the family needs "
            "clinical identification"
        )
    if overlaps:
        notes.append(f"high overlap with {len(overlaps)} other candidate family/families")
    if boundary_count:
        notes.append(f"{boundary_count} boundary pathways")
    internal = getattr(row, "InternalEdgePercentage", None)
    if internal is not None and pd.isna(internal):
        notes.append("no internal or outgoing edges, so graph cohesion is not measurable")
    membership_basis = str(getattr(row, "FamilyLabel", ""))
    if membership_basis == UNASSIGNED:
        notes.append(
            "artefact of missing metadata rather than a clinical grouping"
        )
    return "; ".join(notes) if notes else "no structural concerns flagged"


def candidate_membership_table(
    candidate: CandidateFamilySet,
    names: pd.DataFrame,
    boundary: pd.DataFrame,
    routing: pd.DataFrame,
    model: PathwayFeatureModel,
) -> pd.DataFrame:
    """Build ``candidate_family_membership.csv`` (section 22).

    Multiple rows per pathway are emitted where membership genuinely overlaps.
    ``MembershipStrength`` is the pathway's affinity to that family divided by its best
    affinity to any family, so 1.0 means the assigned family is also its best structural
    match and a lower value means the assignment disagrees with the affinity evidence.
    """
    membership = candidate.membership.copy()
    name_lookup = dict(zip(names["FamilyId"], names["FamilyName"])) if not names.empty else {}
    titles = model.features.set_index("PathwayKey")[["PathwayID", "PathwayTitle"]]

    routing_subset = (
        routing.loc[routing["strategy"] == candidate.strategy]
        if not routing.empty
        else pd.DataFrame()
    )
    best_affinity = (
        dict(zip(routing_subset["PathwayKey"], routing_subset["DominantAffinity"]))
        if not routing_subset.empty else {}
    )
    secondary = family_routing.secondary_family_candidates(
        routing, strategy=candidate.strategy
    )

    boundary_subset = (
        boundary.loc[boundary["strategy"] == candidate.strategy]
        if not boundary.empty
        else pd.DataFrame()
    )
    boundary_class = (
        dict(zip(boundary_subset["PathwayKey"], boundary_subset["BoundaryClassification"]))
        if not boundary_subset.empty else {}
    )

    records = []
    for row in membership.itertuples():
        pathway_key = row.pathway_key
        title_row = titles.loc[pathway_key] if pathway_key in titles.index else None
        records.append(
            {
                "FamilyId": row.family_id,
                "FamilyName": name_lookup.get(row.family_id, row.family_id),
                "PathwayID": title_row["PathwayID"] if title_row is not None else pathway_key,
                "PathwayKey": pathway_key,
                "PathwayTitle": title_row["PathwayTitle"] if title_row is not None else "",
                "MembershipBasis": row.membership_basis,
                "MembershipStrength": round(float(row.membership_strength), 6),
                "BoundaryClassification": boundary_class.get(pathway_key, "not classified"),
                "SecondaryFamilyCandidates": " | ".join(secondary.get(pathway_key, [])),
                "SecondaryFamilyCandidateCount": len(secondary.get(pathway_key, [])),
                "BestFamilyAffinity": round(float(best_affinity.get(pathway_key, 0.0)), 6),
            }
        )
    if not records:
        return pd.DataFrame()
    return pd.DataFrame(records).sort_values(
        ["FamilyId", "PathwayID"], ignore_index=True
    )


# ======================================================================================
# Orchestration
# ======================================================================================
class Phase2FamilyDiscovery:
    """Executes the Phase 2 family-discovery analyses end to end."""

    def __init__(
        self,
        database: PathwaysDatabase,
        paths: Paths,
        config: FamilyDiscoveryConfig,
    ) -> None:
        self.db = database
        self.paths = paths
        self.config = config
        self.extracts: dict[str, pd.DataFrame] = {}
        self.tables: dict[str, pd.DataFrame] = {}
        self.result = Phase2Result()
        self.candidate_sets: list[CandidateFamilySet] = []
        self.partitions: dict[str, dict[str, int]] = {}
        self.unavailable_methods: dict[str, str] = {}
        self.edge_crosscheck: dict[str, object] = {}
        self.strategies_excluded: dict[str, str] = {}
        self.model: PathwayFeatureModel | None = None
        self.similarity: PairwiseSimilarity | None = None
        self.context: family_routing.AffinityContext | None = None
        self.hybrid_c_membership: dict[str, int] = {}

    # -- helpers ---------------------------------------------------------------------
    def _table(self, frame: pd.DataFrame, name: str, *, subdirectory: str = "tables") -> Path:
        """Write a Phase 2 table and register it for the report."""
        directory = {
            "tables": self.paths.phase2_tables,
            "reports": self.paths.phase2_reports,
        }[subdirectory]
        path = exports.write_table(frame, directory / f"{name}.csv")
        self.tables[name] = frame
        self.result.tables_written.append(path)
        return path

    def _note(self, message: str) -> None:
        self.result.notes.append(message)
        LOGGER.info("NOTE: %s", message)

    # -- 1. extraction ---------------------------------------------------------------
    def extract(self) -> None:
        """Run every read-only extract Phase 2 needs and normalise identifier case."""
        LOGGER.info("--- Extracting from SQL Server (read-only) ---")
        for name in PHASE1_QUERIES + PHASE2_QUERIES:
            self.extracts[name] = self.db.read_query(name)
        for frame in self.extracts.values():
            for column in frame.columns:
                if column.endswith("_key"):
                    frame[column] = normalise_id(frame[column])

        inventory = self.extracts["inventory"]
        self.result.notes.append(
            f"Extracted {len(PHASE1_QUERIES + PHASE2_QUERIES)} read-only queries."
        )
        self.inventory = dict(
            zip(inventory["metric"], inventory["value"].astype("int64"))
        )

    # -- 2. pathway graph ------------------------------------------------------------
    def build_graph(self) -> tuple[nx.DiGraph, pd.DataFrame, pd.DataFrame]:
        """Rebuild the Phase 1 pathway graph and cross-check it against SQL.

        The graph is re-derived here rather than read from the Phase 1 GraphML so that a
        Phase 2 run is self-contained and cannot silently depend on a stale artefact.
        Both derivations of the edge list are then compared: a divergence would
        invalidate every cohesion, boundary and routing metric downstream, so it is
        checked rather than assumed.
        """
        LOGGER.info("--- Pathway graph ---")
        transfers = self.extracts["transfer_values"].copy()
        transfers["resolves_pathway"] = transfers["resolves_pathway"].astype(bool)
        transfers["resolved_pathway_key"] = transfers["candidate_pathway_key"].where(
            transfers["resolves_pathway"]
        )
        pathway_rows = transfers.loc[transfers["resolves_pathway"]]
        edges = graph_tools.aggregate_pathway_edges(pathway_rows)

        sql_edges = self.extracts["pathway_transition_edges"]
        python_pairs = set(zip(edges["source_pathway_key"], edges["target_pathway_key"]))
        sql_pairs = set(zip(sql_edges["source_pathway_key"], sql_edges["target_pathway_key"]))
        self.edge_crosscheck = {
            "python_edges": len(edges),
            "sql_edges": len(sql_edges),
            "python_transitions": int(edges["transition_count"].sum()),
            "sql_transitions": int(sql_edges["transition_count"].sum()),
            "edges_only_in_python": len(python_pairs - sql_pairs),
            "edges_only_in_sql": len(sql_pairs - python_pairs),
            "matches": (
                python_pairs == sql_pairs
                and int(edges["transition_count"].sum())
                == int(sql_edges["transition_count"].sum())
            ),
        }
        if self.edge_crosscheck["matches"]:
            self._note(
                f"Edge-list cross-check passed: the Python and server-side derivations "
                f"agree on {len(edges):,} edges and "
                f"{int(edges['transition_count'].sum()):,} transitions."
            )
        else:
            self._note(
                "EDGE-LIST CROSS-CHECK DIVERGED: Python "
                f"{len(edges):,} edges / {int(edges['transition_count'].sum()):,} "
                f"transitions vs SQL {len(sql_edges):,} / "
                f"{int(sql_edges['transition_count'].sum()):,}. "
                f"{len(python_pairs - sql_pairs)} edges only in Python, "
                f"{len(sql_pairs - python_pairs)} only in SQL. Every downstream cohesion "
                "metric should be treated as provisional until this is resolved."
            )
        self._table(
            pd.DataFrame([self.edge_crosscheck]), "edge_derivation_crosscheck",
            subdirectory="reports",
        )

        pathways = self.extracts["pathways"].copy()
        pathways["is_active"] = pathways["is_active"].astype(bool)
        complexity = self.extracts["pathway_complexity"]
        symptom_groups = self.extracts["symptom_groups"][["sg_id", "sg_desc"]]

        participating = set(edges["source_pathway_key"]) | set(edges["target_pathway_key"])
        node_mask = pathways["is_active"] | pathways["pathway_key"].isin(participating)
        node_attributes = (
            pathways.loc[node_mask]
            .merge(symptom_groups, left_on="symptom_group_id", right_on="sg_id", how="left")
            .merge(complexity, on="pathway_key", how="left", suffixes=("", "_complexity"))
        )
        attribute_columns = [
            column
            for column in (
                "pathway_key", "pathway_id", "pathway_title", "is_active",
                "symptom_group_id", "sg_desc",
            )
            if column in node_attributes.columns
        ]
        pathway_graph = graph_tools.build_pathway_graph(
            edges, node_attributes[attribute_columns]
        )
        node_metrics = graph_tools.node_metrics(pathway_graph)
        summary = graph_tools.graph_summary(pathway_graph)
        LOGGER.info(
            "Graph: %d nodes, %d edges, %d weakly connected components",
            summary["node_count"],
            summary["edge_count"],
            summary["weakly_connected_components"],
        )
        return pathway_graph, edges, node_metrics

    # -- 3. scope and feature maps ----------------------------------------------------
    def build_scope(self) -> list[str]:
        """Return the pathway keys eligible for family membership."""
        pathways = self.extracts["pathways"]
        if self.config.pathway_scope == "all":
            scope = pathways["pathway_key"].tolist()
        else:
            scope = pathways.loc[
                pathways["is_active"].astype(bool), "pathway_key"
            ].tolist()
        return sorted(set(scope))

    def build_disposition_map(self, scope: Sequence[str]) -> pd.DataFrame:
        """Union the two routes from a pathway to a disposition.

        A pathway reaches a disposition either by a T1-T4 transfer resolving to a
        DispositionCode, or by holding a Dx disposition node in its own triage logic.
        Both put the disposition in the pathway's outcome set, so they are unioned
        rather than one being chosen; the ``routes`` column records which applied.
        """
        nodes = self.extracts["pathway_disposition_nodes"].copy()
        transfers = self.extracts["pathway_disposition_transfers"].copy()

        unmatched_nodes = int(nodes["disposition_code_key"].isna().sum())
        if unmatched_nodes:
            self._note(
                f"{unmatched_nodes} Dx node references did not match a DispositionID in "
                "tblDxDispositions and carry no disposition code; they are excluded from "
                "the disposition feature map and reported here rather than dropped "
                "silently."
            )
        nodes = nodes.dropna(subset=["disposition_code_key"]).assign(route="dx_node")
        nodes = nodes.rename(columns={"logic_row_count": "occurrence_count"})
        transfers = transfers.dropna(subset=["disposition_code_key"]).assign(
            route="transfer"
        )
        transfers = transfers.rename(columns={"transfer_row_count": "occurrence_count"})

        columns = ["pathway_key", "disposition_code_key", "occurrence_count", "route"]
        combined = pd.concat(
            [nodes[columns], transfers[columns]], ignore_index=True
        )
        combined = combined.loc[combined["pathway_key"].isin(set(scope))]
        grouped = (
            combined.groupby(["pathway_key", "disposition_code_key"])
            .agg(
                occurrence_count=("occurrence_count", "sum"),
                routes=("route", lambda values: " | ".join(sorted(set(values)))),
            )
            .reset_index()
        )
        return grouped

    # -- 4. community detection (section 3) -------------------------------------------
    def detect_communities(
        self, pathway_graph: nx.DiGraph, scope: Sequence[str]
    ) -> None:
        """Run every configured community-detection method and compare them."""
        LOGGER.info(
            "--- Community detection (%d methods) ---",
            len(self.config.community_methods),
        )
        self.partitions, self.unavailable_methods = graph_tools.detect_community_methods(
            pathway_graph,
            self.config.community_methods,
            leiden_resolution=self.config.leiden_resolution,
        )
        self.result.community_methods_run = len(self.partitions)
        primary = self.partitions.get(self.config.primary_community_method)
        if primary is None:
            raise ConfigurationError(
                f"The primary community method "
                f"{self.config.primary_community_method!r} did not run: "
                + self.unavailable_methods.get(
                    self.config.primary_community_method, "unknown reason"
                )
                + ". "
                "Phase 2 cannot proceed without it; choose another method in "
                "community_detection.primary_method."
            )
        self.result.graph_communities = len(set(primary.values()))

        scope_set = set(scope)
        lookup = self.extracts["pathways"][["pathway_key", "pathway_id", "pathway_title"]]
        membership_rows = []
        for method, membership in self.partitions.items():
            for pathway_key, community_id in sorted(membership.items()):
                membership_rows.append(
                    {
                        "method": method,
                        "community_id": int(community_id),
                        "pathway_key": pathway_key,
                        "in_family_scope": pathway_key in scope_set,
                    }
                )
        membership_frame = pd.DataFrame(membership_rows).merge(
            lookup, on="pathway_key", how="left"
        )
        self._table(
            membership_frame.sort_values(
                ["method", "community_id", "pathway_key"], ignore_index=True
            ),
            "graph_community_membership",
        )

        comparison = []
        for method in self.config.community_methods:
            if method not in self.partitions:
                comparison.append(
                    {
                        "method": method,
                        "available": False,
                        "reason_unavailable": self.unavailable_methods.get(method, "unknown"),
                        "community_count": 0,
                        "modularity": float("nan"),
                        "largest_community_size": 0,
                        "median_community_size": float("nan"),
                        "mean_community_size": float("nan"),
                        "singleton_communities": 0,
                        "median_internal_edge_percentage": float("nan"),
                        "mean_internal_edge_percentage": float("nan"),
                        "adjusted_rand_index_vs_primary": float("nan"),
                        "is_primary_method": method == self.config.primary_community_method,
                    }
                )
                continue
            membership = self.partitions[method]
            sizes = pd.Series(list(membership.values())).value_counts()
            cohesion = graph_tools.community_summary(
                pathway_graph, membership, algorithm=method
            )
            comparison.append(
                {
                    "method": method,
                    "available": True,
                    "reason_unavailable": "",
                    "community_count": int(len(sizes)),
                    "modularity": round(
                        graph_tools.modularity_score(pathway_graph, membership), 6
                    ),
                    "largest_community_size": int(sizes.max()),
                    "median_community_size": float(sizes.median()),
                    "mean_community_size": round(float(sizes.mean()), 2),
                    "singleton_communities": int((sizes == 1).sum()),
                    "median_internal_edge_percentage": (
                        round(float(cohesion["internal_edge_percentage"].median()), 2)
                        if not cohesion.empty else float("nan")
                    ),
                    "mean_internal_edge_percentage": (
                        round(float(cohesion["internal_edge_percentage"].mean()), 2)
                        if not cohesion.empty else float("nan")
                    ),
                    "adjusted_rand_index_vs_primary": round(
                        graph_tools.adjusted_rand_index(primary, membership), 6
                    ),
                    "is_primary_method": method == self.config.primary_community_method,
                }
            )
        self._table(pd.DataFrame(comparison), "community_method_comparison")
        if self.unavailable_methods:
            self._note(
                "Community methods that could not run: "
                + "; ".join(
                    f"{method} ({reason})"
                    for method, reason in sorted(self.unavailable_methods.items())
                )
            )

    def community_summary_table(self, pathway_graph: nx.DiGraph) -> None:
        """Write the per-community composition summary (section 3)."""
        assert self.model is not None and self.similarity is not None
        frames = []
        for method, membership in self.partitions.items():
            cohesion = graph_tools.community_summary(
                pathway_graph, membership, algorithm=method
            )
            if cohesion.empty:
                continue
            communities: dict[int, set[str]] = {}
            for pathway_key, community_id in membership.items():
                communities.setdefault(int(community_id), set()).add(pathway_key)
            enrichment = []
            for community_id in cohesion["community_id"]:
                members = communities.get(int(community_id), set())
                in_scope = members & set(self.model.scope)
                metrics = family_evaluation.cohesion_for_group(
                    in_scope, self.model, similarity=self.similarity
                )
                metadata = family_evaluation._metadata_shares(  # noqa: SLF001
                    in_scope, self.model
                )
                enrichment.append(
                    {
                        "community_id": int(community_id),
                        "pathways_in_family_scope": len(in_scope),
                        "unique_symptom_discriminators": metrics[
                            "UniqueSymptomDiscriminatorCount"
                        ],
                        "unique_snomed_concepts": metrics["UniqueSnomedCount"],
                        "unique_dispositions": metrics["UniqueDispositionCount"],
                        "unique_questions": metrics["UniqueQuestionCount"],
                        "shared_sd_percentage": metrics["SharedSdPercentage"],
                        "shared_snomed_percentage": metrics["SharedSnomedPercentage"],
                        "shared_disposition_percentage": metrics[
                            "SharedDispositionPercentage"
                        ],
                        "mean_pairwise_sd_jaccard": metrics["MeanPairwiseSdJaccard"],
                        "distinct_symptom_groups": metadata["DistinctSymptomGroups"],
                        "dominant_symptom_group": metadata["DominantSymptomGroup"],
                        "dominant_symptom_group_share": metadata["DominantSymptomGroupShare"],
                        "distinct_clinical_areas": metadata["DistinctClinicalAreas"],
                        "dominant_clinical_area": metadata["DominantClinicalArea"],
                        "dominant_clinical_area_share": metadata["DominantClinicalAreaShare"],
                        "dominant_area_group": metadata["DominantAreaGroup"],
                        "dominant_trauma_classification": metadata[
                            "DominantTraumaClassification"
                        ],
                        "dominant_age_classification": metadata["DominantAgeClassification"],
                    }
                )
            frames.append(
                cohesion.merge(pd.DataFrame(enrichment), on="community_id", how="left")
            )
        if frames:
            self._table(
                pd.concat(frames, ignore_index=True).assign(
                    grouping_class="graph_derived -- not a clinical family"
                ),
                "graph_community_summary",
            )

    # -- 5. candidate strategies ------------------------------------------------------
    def build_candidates(self, strategy_filter: str) -> None:
        """Generate the candidate family sets requested by ``--strategy``."""
        assert self.model is not None
        assert self.similarity is not None
        assert self.context is not None
        LOGGER.info("--- Candidate family sets (--strategy %s) ---", strategy_filter)
        wanted = (
            {"native", "graph", "hybrid"}
            if strategy_filter == "all"
            else {strategy_filter}
        )

        if "native" in wanted:
            self.candidate_sets.extend(
                native_candidate_sets(
                    self.model, clinical_areas=self.extracts["clinical_areas"]
                )
            )

        if "graph" in wanted:
            scope_set = set(self.model.scope)
            for method, membership in self.partitions.items():
                families: dict[str, set[str]] = {}
                for pathway_key, community_id in membership.items():
                    if pathway_key in scope_set:
                        families.setdefault(f"GC_{int(community_id):03d}", set()).add(
                            pathway_key
                        )
                if not families:
                    continue
                strategy = f"graph_{method}"
                self.candidate_sets.append(
                    CandidateFamilySet(
                        strategy=strategy,
                        basis=FAMILY_BASIS_GRAPH,
                        description=(
                            f"{method} communities of the undirected projection of the "
                            "pathway transfer graph. Graph-derived: a property of "
                            "transfer topology only, with no clinical endorsement."
                        ),
                        membership=build_membership_frame(
                            families,
                            strategy=strategy,
                            labels={family_id: family_id for family_id in families},
                            membership_basis=f"graph_community:{method}",
                        ),
                        notes=[
                            "Community ids are renumbered largest-first, so id 000 is "
                            "the largest community.",
                        ],
                    )
                )

        if "hybrid" in wanted:
            primary = self.partitions[self.config.primary_community_method]
            self.candidate_sets.append(
                build_hybrid_a(
                    primary, self.model, self.similarity, self.context, config=self.config
                )
            )
            self.candidate_sets.append(
                build_hybrid_b(self.model, self.similarity, config=self.config)
            )
            hybrid_c, membership = build_hybrid_c(self.context, config=self.config)
            self.candidate_sets.append(hybrid_c)
            self.hybrid_c_membership = membership

            hybrid_rows = []
            for candidate in self.candidate_sets:
                if candidate.basis != FAMILY_BASIS_HYBRID:
                    continue
                frame = candidate.membership.copy()
                frame["hybrid_rule"] = candidate.description
                hybrid_rows.append(frame)
            if hybrid_rows:
                self._table(
                    pd.concat(hybrid_rows, ignore_index=True), "hybrid_family_candidates"
                )
                self.result.hybrid_families = int(
                    pd.concat(hybrid_rows, ignore_index=True)["family_id"].nunique()
                )

            if self.hybrid_c_membership:
                self._table(
                    hybrid_c_sensitivity(
                        self.context, self.hybrid_c_membership, config=self.config
                    ),
                    "hybrid_family_sensitivity",
                )

        self.result.strategies_tested = len(self.candidate_sets)
        for candidate in self.candidate_sets:
            LOGGER.info(
                "  %-28s %4d families  %4d pathways  overlapping=%s",
                candidate.strategy,
                len(candidate.family_ids),
                candidate.pathway_count,
                candidate.overlapping,
            )

    def battery_strategies(self) -> list[CandidateFamilySet]:
        """Return the candidate sets that get the full metric battery.

        Two kinds of strategy are excluded, and the reason is recorded rather than the
        strategy being quietly skipped:

        * a grouping the data cannot populate (``native_module``: NULL for every row);
        * a partition that is a connectivity diagnostic rather than a candidate family
          set (``graph_strongly_connected``: hundreds of singletons).
        """
        selected = []
        for candidate in self.candidate_sets:
            reason = BATTERY_EXCLUSIONS.get(candidate.strategy)
            if reason is not None:
                self.strategies_excluded[candidate.strategy] = reason
                continue
            if len(candidate.family_ids) < 2:
                self.strategies_excluded[candidate.strategy] = (
                    f"only {len(candidate.family_ids)} family, so no overlap, boundary "
                    "or routing question exists"
                )
                continue
            selected.append(candidate)
        return selected

    # -- 6. measurement ---------------------------------------------------------------
    def measure(self, battery: Sequence[CandidateFamilySet]) -> None:
        """Compute cohesion, overlap, routing and boundary tables for every strategy."""
        assert self.model is not None
        assert self.similarity is not None
        assert self.context is not None
        LOGGER.info("--- Cohesion, overlap, routing and boundaries ---")

        cohesion = family_evaluation.family_cohesion(
            battery, self.model, similarity=self.similarity
        )
        self._table(cohesion, "family_cohesion")

        overlap_frames = []
        for candidate in battery:
            overlap_frames.append(
                family_overlap.family_overlap_matrix(candidate, self.model)
            )
        overlap = (
            pd.concat([frame for frame in overlap_frames if not frame.empty], ignore_index=True)
            if any(not frame.empty for frame in overlap_frames)
            else pd.DataFrame()
        )
        classified = family_overlap.classify_overlap(overlap, self.config)
        self._table(classified, "family_overlap_matrix")

        by_strategy = {candidate.strategy: candidate for candidate in battery}
        high = family_overlap.high_overlap_evidence(classified, by_strategy, self.model)
        self._table(high, "high_overlap_family_pairs")
        self.result.strong_overlap_pairs = len(high)

        routing_frames = [
            family_routing.routing_ambiguity(
                candidate, self.model, self.context, config=self.config
            )
            for candidate in battery
        ]
        routing = (
            pd.concat([frame for frame in routing_frames if not frame.empty], ignore_index=True)
            if any(not frame.empty for frame in routing_frames)
            else pd.DataFrame()
        )
        self._table(routing, "pathway_family_routing")
        self._table(family_routing.routing_summary(routing), "pathway_family_routing_summary")

        boundary_frames = [
            family_boundaries.boundary_pathways(
                candidate, self.model, routing, config=self.config
            )
            for candidate in battery
        ]
        boundary = (
            pd.concat(
                [frame for frame in boundary_frames if not frame.empty], ignore_index=True
            )
            if any(not frame.empty for frame in boundary_frames)
            else pd.DataFrame()
        )
        self._table(boundary, "boundary_pathways")
        self._table(family_boundaries.boundary_summary(boundary), "boundary_pathway_summary")

        self._table(
            family_evaluation.split_candidates(
                battery,
                self.model,
                cohesion,
                config=self.config,
                similarity=self.similarity,
            ),
            "family_split_candidates",
        )
        self._table(
            family_overlap.merge_candidates(
                classified,
                by_strategy,
                self.model,
                cohesion,
                config=self.config,
                similarity=self.similarity,
            ),
            "family_merge_candidates",
        )

        self._table(
            family_evaluation.family_quality_scorecard(
                cohesion, classified, routing, boundary, config=self.config
            ),
            "family_quality_scorecard",
        )
        self._table(
            family_evaluation.strategy_comparison(
                battery, cohesion, classified, routing, boundary, self.model
            ),
            "family_strategy_comparison",
        )

    # -- 7. primary-set deep dive -----------------------------------------------------
    def deep_dive(self, primary: CandidateFamilySet) -> None:
        """Run the analyses that only make sense for the presented candidate set."""
        assert self.model is not None and self.similarity is not None
        LOGGER.info(
            "--- Shared features, shared core, age and trauma (%s) ---", primary.strategy
        )

        occurrences = family_boundaries.build_occurrence_frames(
            triage_logic=self.extracts["triage_logic"],
            pathway_discriminators=self.extracts["pathway_discriminators"],
            pathway_snomed=self.extracts["pathway_snomed"],
            pathway_dispositions=self.disposition_map,
            scope=self.model.scope,
        )
        descriptions = self._feature_descriptions()
        shared = family_boundaries.shared_feature_tables(
            primary,
            self.model,
            occurrences=occurrences,
            config=self.config,
            descriptions=descriptions,
        )
        for stem, frame in shared.items():
            self._table(frame, stem)

        boundary = self.tables.get("boundary_pathways", pd.DataFrame())
        cross_family = (
            boundary.loc[
                (boundary["strategy"] == primary.strategy)
                & (boundary["BoundaryClassification"] != "internal pathway"),
                "PathwayKey",
            ].tolist()
            if not boundary.empty else []
        )
        core = family_core.shared_core_candidates(
            shared,
            primary,
            self.model,
            config=self.config,
            cross_family_pathways=cross_family,
        )
        self._table(core, "shared_core_candidates")
        self._table(
            family_core.shared_core_summary(shared, core, config=self.config),
            "shared_feature_summary",
        )
        self.result.shared_core_features = len(core)

        age = family_evaluation.age_family_analysis(primary, self.model, self.similarity)
        self._table(age, "age_family_analysis")
        self._table(
            family_evaluation.metadata_spread_summary(
                primary,
                self.model,
                classification_column="AgeClassification",
                values=("paediatric_only", "adult_only", "adult_and_paediatric", "unspecified"),
                dimension_name="age",
            ),
            "age_spread_summary",
        )

        trauma = family_evaluation.trauma_family_analysis(primary, self.model, self.similarity)
        self._table(trauma, "trauma_family_analysis")
        self._table(
            family_evaluation.metadata_spread_summary(
                primary,
                self.model,
                classification_column="TraumaClassification",
                values=("trauma", "non_trauma", "trauma_and_non_trauma", "unspecified"),
                dimension_name="trauma",
            ),
            "trauma_spread_summary",
        )

    def _feature_descriptions(self) -> dict[str, dict[str, str]]:
        """Return ``{dimension: {feature_id: description}}`` for labelling outputs."""
        descriptions: dict[str, dict[str, str]] = {}
        discriminators = self.extracts["symptom_discriminators"]
        descriptions["symptom_discriminator"] = {
            str(row.sd_id): str(row.sd_desc) for row in discriminators.itertuples()
        }
        snomed = self.extracts["pathway_snomed"]
        descriptions["snomed"] = {
            str(row.snomed_concept_id): str(row.snomed_preferred_term)
            for row in snomed.drop_duplicates("snomed_concept_id").itertuples()
        }
        dispositions = self.extracts["disposition_catalogue"]
        descriptions["disposition"] = {
            str(row.disposition_code_key): str(row.disposition_text)
            for row in dispositions.itertuples()
        }
        # Question text is deliberately not loaded: the shared-feature tables are keyed
        # by question id, and pulling clinical question wording into a family-level
        # summary would put confidential content where it is not needed.
        descriptions["question"] = {}
        return descriptions

    # -- 8. final candidate outputs ---------------------------------------------------
    def finalise(self, primary: CandidateFamilySet) -> pd.DataFrame:
        """Write the candidate family and membership outputs (sections 21 and 22)."""
        assert self.model is not None
        LOGGER.info("--- Candidate family set (%s) ---", primary.strategy)
        cohesion = self.tables.get("family_cohesion", pd.DataFrame())
        names = derive_family_names(primary, cohesion, config=self.config)
        self._table(names, "candidate_family_names")

        candidates = candidate_family_table(
            primary,
            cohesion,
            self.tables.get("family_overlap_matrix", pd.DataFrame()),
            self.tables.get("boundary_pathways", pd.DataFrame()),
            self.tables.get("shared_core_candidates", pd.DataFrame()),
            names,
            self.model,
            config=self.config,
        )
        self._table(candidates, "candidate_bayesian_families")
        self._table(
            candidate_membership_table(
                primary,
                names,
                self.tables.get("boundary_pathways", pd.DataFrame()),
                self.tables.get("pathway_family_routing", pd.DataFrame()),
                self.model,
            ),
            "candidate_family_membership",
        )

        if not candidates.empty:
            self.result.median_family_size = float(candidates["PathwayCount"].median())
            self.result.largest_family_size = int(candidates["PathwayCount"].max())
            self.result.presented_family_count = len(candidates)

        high = self.tables.get("high_overlap_family_pairs", pd.DataFrame())
        if not high.empty:
            self.result.strong_overlap_pairs_presented = int(
                (high["strategy"] == primary.strategy).sum()
            )

        boundary = self.tables.get("boundary_pathways", pd.DataFrame())
        if not boundary.empty:
            primary_boundary = boundary.loc[boundary["strategy"] == primary.strategy]
            self.result.boundary_pathways = int(
                (primary_boundary["BoundaryClassification"] != "internal pathway").sum()
            )
        routing_summary = self.tables.get("pathway_family_routing_summary", pd.DataFrame())
        if not routing_summary.empty:
            row = routing_summary.loc[routing_summary["strategy"] == primary.strategy]
            if not row.empty:
                self.result.percentage_single_family = float(
                    row.iloc[0]["PercentageStrongSingleFamilyAssociation"]
                )
                self.result.percentage_ambiguous = float(
                    row.iloc[0]["PercentageModerateAmbiguity"]
                    + row.iloc[0]["PercentageHighAmbiguity"]
                )
        return names

    # -- 9. orchestration -------------------------------------------------------------
    def run(self, *, strategy: str = "all", render_charts: bool = True) -> Phase2Result:
        """Execute the whole of Phase 2."""
        started = time.perf_counter()
        self.paths.ensure_phase2_directories()

        self.extract()
        pathway_graph, edges, node_metrics = self.build_graph()
        scope = self.build_scope()
        self.disposition_map = self.build_disposition_map(scope)

        maps = build_feature_maps(
            triage_logic=self.extracts["triage_logic"],
            pathway_discriminators=self.extracts["pathway_discriminators"],
            pathway_snomed=self.extracts["pathway_snomed"],
            pathway_dispositions=self.disposition_map,
            pathway_clinical_areas=self.extracts["pathway_clinical_areas"],
            scope=scope,
        )
        self.detect_communities(pathway_graph, scope)
        primary_membership = self.partitions[self.config.primary_community_method]

        LOGGER.info("--- Per-pathway feature model ---")
        self.model = build_pathway_feature_model(
            pathways=self.extracts["pathways"],
            complexity=self.extracts["pathway_complexity"],
            symptom_groups=self.extracts["symptom_groups"],
            clinical_areas=self.extracts["clinical_areas"],
            pathway_clinical_areas=self.extracts["pathway_clinical_areas"],
            pathway_ages=self.extracts["pathway_ages"],
            pathway_genders=self.extracts["pathway_genders"],
            pathway_trauma=self.extracts["pathway_trauma"],
            age_reference=self.extracts["age_reference"],
            gender_reference=self.extracts["gender_reference"],
            trauma_reference=self.extracts["trauma_reference"],
            maps=maps,
            pathway_graph=pathway_graph,
            edges=edges,
            node_metrics=node_metrics,
            graph_community=primary_membership,
            graph_community_method=self.config.primary_community_method,
            scope=scope,
        )
        self._table(self.model.features, "pathway_family_features")
        exports.write_parquet(
            self.model.features, self.paths.phase2_tables / "pathway_family_features.parquet"
        )
        self.result.tables_written.append(
            self.paths.phase2_tables / "pathway_family_features.parquet"
        )
        self._table(self.model.metadata_coverage, "pathway_metadata_coverage")
        self._verify_feature_counts()

        self.similarity = PairwiseSimilarity.build(self.model)
        self.context = family_routing.AffinityContext.build(self.model, self.similarity)
        self.community_summary_table(pathway_graph)

        LOGGER.info("--- Pairwise similarity per evidence dimension ---")
        self._write_similarity_tables()

        self._table(family_evaluation.metric_definition_table(), "metric_definitions",
                    subdirectory="reports")
        self._table(
            pd.DataFrame(self.config.describe(), columns=["setting", "value"]),
            "configuration_used",
            subdirectory="reports",
        )

        self.build_candidates(strategy)
        battery = self.battery_strategies()
        if not battery:
            raise ConfigurationError(
                "No candidate family set survived the battery filter, so there is "
                "nothing to measure. Check --strategy and the configured methods."
            )
        self._table(
            native_group_metrics(
                [
                    candidate
                    for candidate in self.candidate_sets
                    if candidate.basis == "nhs_native"
                ],
                self.model,
            ),
            "native_group_candidates",
        )
        self.measure(battery)

        primary = self._primary_candidate(battery)
        self.deep_dive(primary)
        names = self.finalise(primary)

        if render_charts:
            LOGGER.info("--- Charts ---")
            self.result.charts_written = family_charts.render_all(
                charts_dir=self.paths.phase2_charts,
                graphs_dir=self.paths.phase2_graphs,
                primary=primary,
                primary_names=dict(zip(names["FamilyId"], names["FamilyName"]))
                if not names.empty else {},
                model=self.model,
                cohesion=self.tables.get("family_cohesion", pd.DataFrame()),
                overlap=self.tables.get("family_overlap_matrix", pd.DataFrame()),
                boundary=self.tables.get("boundary_pathways", pd.DataFrame()),
                shared_core=self.tables.get("shared_core_candidates", pd.DataFrame()),
                strategy_comparison=self.tables.get(
                    "family_strategy_comparison", pd.DataFrame()
                ),
                community_comparison=self.tables.get(
                    "community_method_comparison", pd.DataFrame()
                ),
                native_candidates=self.tables.get("native_group_candidates", pd.DataFrame()),
            )
        else:
            LOGGER.info("--- Charts skipped (--no-charts) ---")

        self._write_reports(primary, names)
        self.result.elapsed_seconds = time.perf_counter() - started
        return self.result

    def _primary_candidate(self, battery: Sequence[CandidateFamilySet]) -> CandidateFamilySet:
        """Return the candidate set presented for review, or fall back with a note."""
        wanted = self.config.primary_candidate_strategy
        for candidate in battery:
            if candidate.strategy == wanted:
                return candidate
        fallback = max(battery, key=lambda candidate: len(candidate.family_ids))
        self._note(
            f"The configured primary candidate strategy {wanted!r} was not generated "
            f"in this run, so {fallback.strategy!r} is presented instead. This changes "
            "which family set the candidate outputs and the review pack describe."
        )
        return fallback

    def _write_similarity_tables(self) -> None:
        """Write the six per-dimension similarity tables (section 4)."""
        assert self.model is not None
        tables = similarity_tables(
            self.model, minimum_intersection=self.config.similarity_minimum_intersection
        )
        naming = {
            "question": "pathway_similarity_questions",
            "symptom_discriminator": "pathway_similarity_sd",
            "snomed": "pathway_similarity_snomed",
            "disposition": "pathway_similarity_disposition",
            "clinical_area": "pathway_similarity_clinical_area",
        }
        summary_rows = []
        for dimension, frame in tables.items():
            self._table(frame, naming[dimension])
            entities = getattr(self.model.maps, dimension)["pathway_key"].nunique()
            possible = graph_tools.pair_count(entities)
            summary_rows.append(
                {
                    "dimension": dimension,
                    "pathways_with_any_feature": entities,
                    "overlapping_pairs": len(frame),
                    "possible_pairs": possible,
                    "percentage_of_pairs_overlapping": round(
                        100.0 * len(frame) / max(possible, 1), 2
                    ),
                    "median_jaccard": (
                        round(float(frame["jaccard_similarity"].median()), 4)
                        if not frame.empty else float("nan")
                    ),
                    "max_jaccard": (
                        round(float(frame["jaccard_similarity"].max()), 4)
                        if not frame.empty else float("nan")
                    ),
                    "pairs_at_or_above_0_5": (
                        int((frame["jaccard_similarity"] >= 0.5).sum())
                        if not frame.empty else 0
                    ),
                }
            )
        graph_similarity = graph_similarity_table(
            self.model, max_hops=self.config.similarity_max_graph_hops
        )
        self._table(graph_similarity, "pathway_similarity_graph")
        summary_rows.append(
            {
                "dimension": "graph_relationship",
                "pathways_with_any_feature": len(self.model.scope),
                "overlapping_pairs": len(graph_similarity),
                "possible_pairs": graph_tools.pair_count(len(self.model.scope)),
                "percentage_of_pairs_overlapping": round(
                    100.0 * len(graph_similarity)
                    / max(graph_tools.pair_count(len(self.model.scope)), 1),
                    2,
                ),
                "median_jaccard": float("nan"),
                "max_jaccard": float("nan"),
                "pairs_at_or_above_0_5": (
                    int(graph_similarity["direct_edge_exists"].sum())
                    if not graph_similarity.empty else 0
                ),
            }
        )
        self._table(pd.DataFrame(summary_rows), "pathway_similarity_summary")

    def _verify_feature_counts(self) -> None:
        """Cross-check the Python feature maps against the server-side counts."""
        assert self.model is not None
        sql_counts = self.extracts["feature_pathway_counts"]
        rows = []
        dimension_map = {
            "question": "question",
            "sd": "symptom_discriminator",
            "snomed": "snomed",
            "disposition": "disposition",
        }
        for sql_type, dimension in dimension_map.items():
            frame = getattr(self.model.maps, dimension)
            python_counts = (
                frame.groupby("feature_id")["pathway_key"].nunique()
                if not frame.empty else pd.Series(dtype="int64")
            )
            sql_subset = sql_counts.loc[sql_counts["feature_type"] == sql_type]
            sql_series = pd.Series(
                sql_subset["pathway_count"].values,
                index=sql_subset["feature_id"].astype(str),
            )
            python_series = pd.Series(
                python_counts.values, index=python_counts.index.astype(str)
            )
            aligned = pd.concat(
                [python_series.rename("python"), sql_series.rename("sql")], axis=1
            ).fillna(0)
            mismatches = int((aligned["python"] != aligned["sql"]).sum())
            rows.append(
                {
                    "dimension": dimension,
                    "python_features": int(len(python_series)),
                    "sql_features": int(len(sql_series)),
                    "features_with_mismatched_pathway_count": mismatches,
                    "agrees": mismatches == 0 and len(python_series) == len(sql_series),
                }
            )
            if mismatches:
                self._note(
                    f"Feature-count cross-check for {dimension}: {mismatches} features "
                    "have a different pathway count in the Python map than in the "
                    "server-side count. Both derivations are exported; the difference "
                    "is not resolved here."
                )
        self._table(pd.DataFrame(rows), "feature_count_crosscheck", subdirectory="reports")

    def _write_reports(self, primary: CandidateFamilySet, names: pd.DataFrame) -> None:
        """Write the evidence report and the clinical review pack."""
        assert self.model is not None and self.similarity is not None
        LOGGER.info("--- Reports ---")
        inputs = family_report.ReportInputs(
            config=self.config,
            model=self.model,
            similarity=self.similarity,
            tables=self.tables,
            primary=primary,
            primary_names=dict(zip(names["FamilyId"], names["FamilyName"]))
            if not names.empty else {},
            candidate_sets=self.candidate_sets,
            community_methods_unavailable=self.unavailable_methods,
            edge_crosscheck=self.edge_crosscheck,
            inventory=getattr(self, "inventory", {}),
            notes=self.result.notes,
            generated=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
            strategies_in_battery=[
                candidate.strategy for candidate in self.battery_strategies()
            ],
            strategies_excluded=self.strategies_excluded,
        )
        self.result.reports_written.append(
            family_report.write_evidence_report(
                inputs, self.paths.phase2 / "family_discovery_report.md"
            )
        )
        self.result.reports_written.append(
            family_report.write_clinical_review_pack(
                inputs, self.paths.phase2 / "clinical_review_pack.md"
            )
        )


# ======================================================================================
# CLI
# ======================================================================================
def configure_logging(level: str) -> None:
    """Configure stdout logging."""
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s  %(levelname)-7s %(message)s",
        datefmt="%H:%M:%S",
        stream=sys.stdout,
    )
    logging.getLogger("matplotlib").setLevel(logging.WARNING)


def build_argument_parser() -> argparse.ArgumentParser:
    """Build the Phase 2 CLI parser."""
    parser = argparse.ArgumentParser(
        prog="python -m pathways_analysis.family_discovery",
        description=(
            "Phase 2 candidate Bayesian family discovery for the NHS Pathways dataset. "
            "Read-only: this command never modifies the source database. It produces "
            "family evidence only -- no sizing, cost or architecture recommendation."
        ),
    )
    parser.add_argument(
        "--strategy",
        default="all",
        choices=["all", "native", "graph", "hybrid"],
        help=(
            "Which family discovery approaches to generate (default: all). "
            "'hybrid' still runs community detection, because Hybrid A is built from "
            "graph communities."
        ),
    )
    parser.add_argument(
        "--no-charts",
        action="store_true",
        help="Skip chart rendering. All tables and reports are still written.",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help=(
            "Phase 2 configuration file (default: config/family_discovery.yaml, or "
            "built-in defaults if that file is absent)."
        ),
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging verbosity (default: INFO).",
    )
    parser.add_argument(
        "--check-connection",
        action="store_true",
        help="Validate database connectivity and exit without running the analysis.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Entry point for ``python -m pathways_analysis.family_discovery``."""
    args = build_argument_parser().parse_args(argv)
    configure_logging(args.log_level)

    paths = Paths.discover()
    env_file = load_dotenv_if_present(paths)
    if env_file:
        LOGGER.info("Loaded environment from %s", env_file)

    config_path = args.config
    if config_path is None:
        default_path = default_config_path(paths.project_root)
        config_path = default_path if default_path.is_file() else None

    try:
        config = load_family_config(config_path)
        settings = DatabaseSettings.from_env()
    except ConfigurationError as exc:
        LOGGER.error("Configuration error: %s", exc)
        return 2

    database = PathwaysDatabase(settings, paths)
    try:
        info = database.validate_connectivity()
    except DatabaseConnectionError as exc:
        LOGGER.error("DATABASE CONNECTIVITY FAILURE")
        LOGGER.error("%s", exc)
        return 3

    if args.check_connection:
        LOGGER.info(
            "Connectivity OK: database=%s server_time=%s",
            info["database_name"],
            info["server_utc_time"],
        )
        database.dispose()
        return 0

    runner = Phase2FamilyDiscovery(database, paths, config)
    try:
        result = runner.run(strategy=args.strategy, render_charts=not args.no_charts)
    except DatabaseConnectionError as exc:
        LOGGER.error("Database failure during analysis: %s", exc)
        return 3
    except ConfigurationError as exc:
        LOGGER.error("Configuration error during analysis: %s", exc)
        return 2
    finally:
        database.dispose()

    _print_summary(result, paths, config)
    return 0


def _print_summary(
    result: Phase2Result, paths: Paths, config: FamilyDiscoveryConfig
) -> None:
    """Print the Phase 2 terminal summary.

    Deliberately identifiers and counts only: no question text, symptom-discriminator
    wording or other clinical content is printed, because a terminal transcript is not
    a controlled artefact.
    """
    csv_count = len([path for path in result.tables_written if path.suffix == ".csv"])
    print()
    print("=" * 78)
    print("NHS PATHWAYS BAYESIAN FAMILY DISCOVERY - PHASE 2 COMPLETE")
    print("=" * 78)
    print(f"  Candidate family strategies tested   {result.strategies_tested:>8,}")
    print(f"  Community detection methods run      {result.community_methods_run:>8,}")
    print(
        f"  Graph communities ({config.primary_community_method[:14]:<14})"
        f" {result.graph_communities:>8,}"
    )
    print(f"  Hybrid candidate families (A+B+C)    {result.hybrid_families:>8,}")
    print(
        f"  High-overlap pairs, all strategies    {result.strong_overlap_pairs:>7,}"
    )
    print("-" * 78)
    print(f"  Presented candidate set: {config.primary_candidate_strategy}")
    print(f"  Candidate families                   {result.presented_family_count:>8,}")
    print(f"  Median candidate family size         {result.median_family_size:>8,.1f}")
    print(f"  Largest candidate family             {result.largest_family_size:>8,}")
    print(f"  High-overlap family pairs            {result.strong_overlap_pairs_presented:>8,}")
    print(f"  Boundary pathways                    {result.boundary_pathways:>8,}")
    print(f"  Shared-core candidate features       {result.shared_core_features:>8,}")
    print("-" * 78)
    print(
        f"  Pathways with strong single-family   {result.percentage_single_family:>7.1f}%"
    )
    print(
        f"  Pathways with ambiguous association  {result.percentage_ambiguous:>7.1f}%"
    )
    print("-" * 78)
    print(f"  CSV tables written                   {csv_count:>8,}   -> outputs/phase2/")
    print(
        f"  Charts written                       {len(result.charts_written):>8,}"
        "   -> outputs/phase2/charts|graphs/"
    )
    print(
        f"  Reports written                      {len(result.reports_written):>8,}"
        "   -> outputs/phase2/"
    )
    print("-" * 78)
    print(f"  Elapsed                              {result.elapsed_seconds:>8.1f}s")
    print("=" * 78)
    print("Phase 2 is family evidence only. No sizing, cost or architecture choice is")
    print("made, and no candidate family is clinically endorsed.")
    print(f"Evidence report: {paths.phase2 / 'family_discovery_report.md'}")
    print(f"Clinical review: {paths.phase2 / 'clinical_review_pack.md'}")
    print()


if __name__ == "__main__":
    raise SystemExit(main())
