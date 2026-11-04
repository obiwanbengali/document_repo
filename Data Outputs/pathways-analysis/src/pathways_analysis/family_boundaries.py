"""Phase 2: pathways and features that sit between candidate families.

Sections 9 and 10 of the Phase 2 brief.

Boundary pathways (section 9) are pathways whose structure does not sit cleanly inside
one candidate family. Boundary features (section 10) are questions, symptom
discriminators, SNOMED concepts and dispositions used across many families.

What the classification is and is not
-------------------------------------
The classification is **purely structural**. "Cross-family hub" means a pathway has
transfer edges to several candidate families and sits on many shortest transfer routes.
It does not mean the pathway is clinically central, safety-critical, or wrongly placed.
Reading a clinical claim into these labels would be exactly the error the Phase 2 brief
warns against.
"""

from __future__ import annotations

import logging
from typing import Final, Mapping, Sequence

import numpy as np
import pandas as pd

from .family_config import FamilyDiscoveryConfig
from .family_features import CandidateFamilySet, PathwayFeatureModel
from .family_routing import pathway_family_edge_counts, plausible_family_counts

LOGGER: Final = logging.getLogger(__name__)

#: Boundary classes, ordered from least to most entangled.
BOUNDARY_CLASSES: Final[tuple[str, ...]] = (
    "internal pathway",
    "weak boundary pathway",
    "strong boundary pathway",
    "cross-family hub",
)

#: Feature dimensions analysed for cross-family sharing, with their output file stems.
SHARED_FEATURE_DIMENSIONS: Final[tuple[tuple[str, str], ...]] = (
    ("question", "shared_questions"),
    ("symptom_discriminator", "shared_symptom_discriminators"),
    ("snomed", "shared_snomed"),
    ("disposition", "shared_dispositions"),
)


def boundary_pathways(
    candidate: CandidateFamilySet,
    model: PathwayFeatureModel,
    routing: pd.DataFrame,
    *,
    config: FamilyDiscoveryConfig,
) -> pd.DataFrame:
    """Classify every pathway's position relative to its candidate family (section 9).

    Evidence used, each reported as its own column:

    * ``ExternalDegree`` -- distinct non-member pathways adjacent in either direction.
    * ``ExternalFamilyCount`` -- distinct other candidate families the pathway has
      edges to.
    * ``BetweennessPercentile`` -- percentile rank of the pathway's unweighted
      betweenness centrality within the in-scope pathways.
    * ``PlausibleFamilyCount`` -- families whose affinity reaches the configured ratio
      of the pathway's best family (from the routing analysis).
    * ``ClinicalAreaCount`` -- clinical areas the pathway maps to; more than one is an
      NHS-native signal that the pathway spans areas.
    * ``FamiliesSharingSymptomDiscriminators`` -- candidate families whose symptom
      discriminator set intersects the pathway's.

    Classification rules, all thresholds from configuration:

    * ``internal pathway`` -- no edges to a non-member.
    * ``cross-family hub`` -- edges to at least ``boundary.hub_external_family_count``
      other families **and** betweenness at or above
      ``boundary.hub_betweenness_percentile``. Both are required so a locally chatty
      pathway is not promoted to a hub.
    * ``strong boundary pathway`` -- external degree at or above
      ``boundary.strong_external_degree``, or edges to at least
      ``hub_external_family_count`` other families without the betweenness to be a hub.
    * ``weak boundary pathway`` -- anything else with at least one external edge.
    """
    families = candidate.families()
    if not families:
        return pd.DataFrame()

    membership_by_pathway: dict[str, set[str]] = {}
    for family_id, members in families.items():
        for member in members:
            membership_by_pathway.setdefault(member, set()).add(family_id)

    edge_counts = pathway_family_edge_counts(candidate, model)
    edges_by_pathway: dict[str, dict[str, dict[str, int]]] = {}
    for row in edge_counts.itertuples():
        edges_by_pathway.setdefault(row.pathway_key, {})[row.family_id] = {
            "edges_out": int(row.edges_out),
            "edges_in": int(row.edges_in),
            "transitions": int(row.transitions),
        }

    graph = model.pathway_graph
    features = model.features.set_index("PathwayKey")
    betweenness = features["BetweennessCentrality"].astype(float)
    # Percentile rank within the in-scope pathways: an absolute betweenness value is
    # not interpretable on its own, and the threshold is expressed as a percentile.
    betweenness_percentile = betweenness.rank(pct=True) * 100.0

    sd_sets = model.maps.feature_sets("symptom_discriminator")
    family_sd_sets = {
        family_id: set().union(*(sd_sets.get(member, set()) for member in members))
        if members else set()
        for family_id, members in families.items()
    }
    plausible_counts = plausible_family_counts(
        routing.loc[routing["strategy"] == candidate.strategy] if not routing.empty else routing
    )
    routing_indexed = (
        routing.loc[routing["strategy"] == candidate.strategy].set_index("PathwayKey")
        if not routing.empty else pd.DataFrame()
    )

    records = []
    for pathway_key in model.scope:
        own_families = membership_by_pathway.get(pathway_key, set())
        if not own_families:
            continue
        member_pool = set().union(*(families[family_id] for family_id in own_families))

        internal_neighbours: set[str] = set()
        external_neighbours: set[str] = set()
        if pathway_key in graph:
            neighbours = (
                set(graph.successors(pathway_key)) | set(graph.predecessors(pathway_key))
            ) - {pathway_key}
            for neighbour in neighbours:
                if neighbour in member_pool:
                    internal_neighbours.add(neighbour)
                else:
                    external_neighbours.add(neighbour)

        family_edges = edges_by_pathway.get(pathway_key, {})
        external_families = sorted(set(family_edges) - own_families)
        own_sd = sd_sets.get(pathway_key, set())
        sd_spanning = sorted(
            family_id
            for family_id, family_sd in family_sd_sets.items()
            if family_id not in own_families and own_sd & family_sd
        )

        percentile = float(betweenness_percentile.get(pathway_key, 0.0))
        external_degree = len(external_neighbours)
        classification = _classify_boundary(
            external_degree=external_degree,
            external_family_count=len(external_families),
            betweenness_percentile=percentile,
            config=config,
        )

        routing_row = (
            routing_indexed.loc[pathway_key] if pathway_key in routing_indexed.index else None
        )
        feature_row = features.loc[pathway_key]
        records.append(
            {
                "strategy": candidate.strategy,
                "PathwayID": feature_row["PathwayID"],
                "PathwayKey": pathway_key,
                "PathwayTitle": feature_row["PathwayTitle"],
                "FamilyId": " | ".join(sorted(own_families)),
                "FamilyLabel": " | ".join(
                    candidate.labels().get(family_id, family_id)
                    for family_id in sorted(own_families)
                ),
                "InternalDegree": len(internal_neighbours),
                "ExternalDegree": external_degree,
                "ExternalFamilyCount": len(external_families),
                "ExternalFamilies": " | ".join(external_families),
                "ExternalTransitionCount": sum(
                    values["transitions"]
                    for family_id, values in family_edges.items()
                    if family_id not in own_families
                ),
                "BetweennessCentrality": round(float(betweenness.get(pathway_key, 0.0)), 8),
                "BetweennessPercentile": round(percentile, 2),
                "ClinicalAreaCount": int(feature_row["ClinicalAreaCount"]),
                "SymptomGroupId": feature_row["SymptomGroupId"],
                "FamiliesSharingSymptomDiscriminators": len(sd_spanning),
                "PlausibleFamilyCount": int(plausible_counts.get(pathway_key, 0)),
                "AmbiguityScore": (
                    float(routing_row["AmbiguityScore"]) if routing_row is not None else np.nan
                ),
                "AmbiguityClassification": (
                    routing_row["AmbiguityClassification"] if routing_row is not None else ""
                ),
                "BoundaryClassification": classification,
                "ClassificationBasis": (
                    "structural only -- no clinical claim is made by this label"
                ),
                "StrongExternalDegreeThreshold": config.boundary_strong_external_degree,
                "HubExternalFamilyCountThreshold": config.boundary_hub_external_family_count,
                "HubBetweennessPercentileThreshold": config.boundary_hub_betweenness_percentile,
            }
        )
    if not records:
        return pd.DataFrame()
    frame = pd.DataFrame(records)
    frame["_class_rank"] = frame["BoundaryClassification"].map(
        {name: index for index, name in enumerate(BOUNDARY_CLASSES)}
    )
    return frame.sort_values(
        ["strategy", "_class_rank", "ExternalDegree", "BetweennessCentrality"],
        ascending=[True, False, False, False],
        ignore_index=True,
    ).drop(columns="_class_rank")


def _classify_boundary(
    *,
    external_degree: int,
    external_family_count: int,
    betweenness_percentile: float,
    config: FamilyDiscoveryConfig,
) -> str:
    """Apply the boundary classification rules. See :func:`boundary_pathways`."""
    if external_degree == 0:
        return "internal pathway"
    is_multi_family = external_family_count >= config.boundary_hub_external_family_count
    if is_multi_family and betweenness_percentile >= config.boundary_hub_betweenness_percentile:
        return "cross-family hub"
    if external_degree >= config.boundary_strong_external_degree or is_multi_family:
        return "strong boundary pathway"
    return "weak boundary pathway"


def boundary_summary(boundary: pd.DataFrame) -> pd.DataFrame:
    """Summarise boundary classification counts per strategy."""
    if boundary.empty:
        return pd.DataFrame()
    records = []
    for strategy, group in boundary.groupby("strategy"):
        total = max(len(group), 1)
        row: dict[str, object] = {"strategy": strategy, "PathwaysClassified": len(group)}
        for name in BOUNDARY_CLASSES:
            count = int((group["BoundaryClassification"] == name).sum())
            key = name.replace(" ", "_").replace("-", "_")
            row[f"count_{key}"] = count
            row[f"percentage_{key}"] = round(100.0 * count / total, 2)
        row["BoundaryPathwayCount"] = int(
            (group["BoundaryClassification"] != "internal pathway").sum()
        )
        row["BoundaryPathwayPercentage"] = round(
            100.0
            * float((group["BoundaryClassification"] != "internal pathway").sum())
            / total,
            2,
        )
        records.append(row)
    return pd.DataFrame(records).sort_values("strategy", ignore_index=True)


def shared_feature_tables(
    candidate: CandidateFamilySet,
    model: PathwayFeatureModel,
    *,
    occurrences: Mapping[str, pd.DataFrame],
    config: FamilyDiscoveryConfig,
    descriptions: Mapping[str, Mapping[str, str]] | None = None,
) -> dict[str, pd.DataFrame]:
    """Build the cross-family shared-feature tables (section 10).

    For every feature this reports how many candidate families use it, how many
    pathways, how many times it appears in triage logic, and the full distribution
    across families.

    Banding is purely analytical, using ``shared_core.family_count_bands``:
    ``family-specific`` (one family), ``shared by 2 families``,
    ``shared by 3-5 families``, ``broadly shared`` (more than five).

    Args:
        candidate: The candidate family set whose families are counted.
        model: The feature model supplying the feature maps.
        occurrences: ``{dimension: frame}`` with ``feature_id`` and
            ``total_occurrences``, so a feature appearing once in 20 pathways is
            distinguishable from one appearing 500 times in 20 pathways.
        config: Supplies the band boundaries.
        descriptions: Optional ``{dimension: {feature_id: description}}`` for labelling.

    Returns:
        ``{output_stem: frame}``.
    """
    families = candidate.families()
    membership_by_pathway: dict[str, set[str]] = {}
    for family_id, members in families.items():
        for member in members:
            membership_by_pathway.setdefault(member, set()).add(family_id)
    labels = candidate.labels()
    descriptions = descriptions or {}

    bands = config.shared_core_bands
    results: dict[str, pd.DataFrame] = {}

    for dimension, stem in SHARED_FEATURE_DIMENSIONS:
        frame = getattr(model.maps, dimension)
        if frame.empty:
            results[stem] = pd.DataFrame(
                columns=[
                    "strategy", "FeatureType", "FeatureId", "Description", "FamilyCount",
                    "PathwayCount", "TotalOccurrences", "FamilyDistribution",
                    "SharingBand",
                ]
            )
            continue

        occurrence_lookup: dict[str, int] = {}
        if dimension in occurrences and not occurrences[dimension].empty:
            occurrence_frame = occurrences[dimension]
            occurrence_lookup = dict(
                zip(
                    occurrence_frame["feature_id"].astype(str),
                    occurrence_frame["total_occurrences"].astype("int64"),
                )
            )
        dimension_descriptions = descriptions.get(dimension, {})

        records = []
        for feature_id, group in frame.groupby("feature_id"):
            pathways = sorted(set(group["pathway_key"]))
            family_counts: dict[str, int] = {}
            for pathway in pathways:
                for family_id in membership_by_pathway.get(pathway, set()):
                    family_counts[family_id] = family_counts.get(family_id, 0) + 1
            family_count = len(family_counts)
            ordered = sorted(family_counts.items(), key=lambda item: (-item[1], item[0]))
            records.append(
                {
                    "strategy": candidate.strategy,
                    "FeatureType": dimension,
                    "FeatureId": str(feature_id),
                    "Description": dimension_descriptions.get(str(feature_id), ""),
                    "FamilyCount": family_count,
                    "PathwayCount": len(pathways),
                    "TotalOccurrences": occurrence_lookup.get(str(feature_id), 0),
                    "FamilyDistribution": " | ".join(
                        f"{family_id}:{count}" for family_id, count in ordered[:12]
                    ),
                    "TopFamilyId": ordered[0][0] if ordered else "",
                    "TopFamilyLabel": labels.get(ordered[0][0], "") if ordered else "",
                    "TopFamilyPathwayCount": ordered[0][1] if ordered else 0,
                    "SharingBand": _sharing_band(family_count, bands),
                }
            )
        results[stem] = pd.DataFrame(records).sort_values(
            ["FamilyCount", "PathwayCount", "FeatureId"],
            ascending=[False, False, True],
            ignore_index=True,
        )
        LOGGER.info(
            "Shared features %-24s %6d features, %4d used by >= %d families",
            dimension,
            len(results[stem]),
            int(
                (
                    results[stem]["FamilyCount"]
                    >= config.shared_core_minimum_family_count
                ).sum()
            ),
            config.shared_core_minimum_family_count,
        )
    return results


def _sharing_band(family_count: int, bands: Mapping[str, int]) -> str:
    """Return the analytical sharing band for a family count."""
    if family_count <= bands.get("family_specific", 1):
        return "family-specific"
    if family_count <= bands.get("shared_2", 2):
        return "shared by 2 families"
    if family_count <= bands.get("shared_3_to_5", 5):
        return "shared by 3-5 families"
    return "broadly shared"


def build_occurrence_frames(
    *,
    triage_logic: pd.DataFrame,
    pathway_discriminators: pd.DataFrame,
    pathway_snomed: pd.DataFrame,
    pathway_dispositions: pd.DataFrame,
    scope: Sequence[str],
) -> dict[str, pd.DataFrame]:
    """Count total triage-logic occurrences per feature, within the pathway scope.

    Occurrence counts and pathway counts answer different questions: a question
    appearing once in each of 20 pathways is a shared screening question, whereas one
    appearing 40 times in each of 20 pathways is structurally load-bearing. Both are
    needed to judge a shared-core candidate.
    """
    scope_set = set(scope)
    results: dict[str, pd.DataFrame] = {}

    questions = triage_logic.loc[
        (triage_logic["node_kind"] == "question") & triage_logic["pathway_key"].isin(scope_set)
    ]
    results["question"] = (
        questions.groupby("question_key").size().reset_index(name="total_occurrences")
        .rename(columns={"question_key": "feature_id"})
    )

    for dimension, frame, key_column in (
        ("symptom_discriminator", pathway_discriminators, "sd_id"),
        ("snomed", pathway_snomed, "snomed_concept_id"),
    ):
        if frame.empty or "logic_row_count" not in frame.columns:
            results[dimension] = pd.DataFrame(columns=["feature_id", "total_occurrences"])
            continue
        subset = frame.loc[frame["pathway_key"].isin(scope_set)]
        results[dimension] = (
            subset.groupby(key_column)["logic_row_count"].sum().reset_index(
                name="total_occurrences"
            ).rename(columns={key_column: "feature_id"})
        )

    if pathway_dispositions.empty:
        results["disposition"] = pd.DataFrame(columns=["feature_id", "total_occurrences"])
    else:
        subset = pathway_dispositions.loc[pathway_dispositions["pathway_key"].isin(scope_set)]
        count_column = (
            "occurrence_count" if "occurrence_count" in subset.columns else None
        )
        if count_column is None:
            results["disposition"] = (
                subset.groupby("disposition_code_key").size().reset_index(
                    name="total_occurrences"
                ).rename(columns={"disposition_code_key": "feature_id"})
            )
        else:
            results["disposition"] = (
                subset.groupby("disposition_code_key")[count_column].sum().reset_index(
                    name="total_occurrences"
                ).rename(columns={"disposition_code_key": "feature_id"})
            )

    for frame in results.values():
        if not frame.empty:
            frame["feature_id"] = frame["feature_id"].astype(str)
    return results
