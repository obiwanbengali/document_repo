"""Phase 2: shared-core candidate features.

Section 11 of the Phase 2 brief.

A shared-core candidate is a feature that would have to be duplicated in many families
if each family became a separate model. This module identifies them from the
cross-family sharing evidence and records **why** each was flagged.

What this is not
----------------
Flagging a feature here does **not** conclude that it belongs in a shared Bayesian
Network, nor that a shared network should exist. There are at least three readings of a
broadly shared question, and structure alone cannot separate them:

* one clinical concept genuinely used everywhere (a shared node is natural);
* several distinct clinical concepts that happen to share an identifier or wording
  (a shared node would conflate them);
* a routing artefact of how Pathways is authored (no Bayesian meaning at all).

Section 11 therefore outputs evidence and defers. The clinical review pack asks the
question explicitly.
"""

from __future__ import annotations

import logging
from typing import Final, Mapping, Sequence

import pandas as pd

from .family_config import FamilyDiscoveryConfig
from .family_features import CandidateFamilySet, PathwayFeatureModel

LOGGER: Final = logging.getLogger(__name__)

#: Human-readable feature-type labels used in the output.
FEATURE_TYPE_LABELS: Final[dict[str, str]] = {
    "question": "Tx triage question",
    "symptom_discriminator": "symptom discriminator",
    "snomed": "SNOMED concept",
    "disposition": "disposition code",
}


def shared_core_candidates(
    shared_features: Mapping[str, pd.DataFrame],
    candidate: CandidateFamilySet,
    model: PathwayFeatureModel,
    *,
    config: FamilyDiscoveryConfig,
    cross_family_pathways: Sequence[str] = (),
) -> pd.DataFrame:
    """Identify shared-core candidate features (section 11).

    A feature is flagged when it meets the family-count threshold from configuration
    (``shared_core.minimum_family_count``). Each flagged feature carries:

    * ``FamilyCount`` / ``PathwayCount`` / ``TotalOccurrences`` -- the measured spread.
    * ``DuplicationIfFederated`` -- ``FamilyCount - 1``: how many extra copies the
      feature would need if every family held its own, which is the quantity that makes
      a shared core attractive or not. This is a structural count, not a sizing
      estimate; sizing is Phase 3.
    * ``GraphCentralityIfApplicable`` -- for features whose carrier pathways are
      identifiable, the maximum betweenness centrality among the pathways using the
      feature. A broadly shared feature carried only by peripheral pathways is a
      different proposition from one carried by the graph's hubs.
    * ``UsedByCrossFamilyPathway`` -- whether any pathway using the feature is
      classified as a boundary pathway or cross-family hub.
    * ``ReasonFlagged`` -- the specific evidence, stated per feature.

    Args:
        shared_features: Output of
            :func:`~pathways_analysis.family_boundaries.shared_feature_tables`.
        candidate: The candidate family set the family counts refer to.
        model: The feature model, for centrality and carrier pathways.
        config: Supplies the minimum family count.
        cross_family_pathways: Pathway keys classified as boundary pathways or
            cross-family hubs.

    Returns:
        One row per flagged feature, sorted by family count then pathway count.
    """
    centrality = (
        model.features.set_index("PathwayKey")["BetweennessCentrality"].astype(float)
        if not model.features.empty
        else pd.Series(dtype="float64")
    )
    cross_family = set(cross_family_pathways)
    minimum = config.shared_core_minimum_family_count

    records = []
    for frame in shared_features.values():
        if frame.empty:
            continue
        flagged = frame.loc[frame["FamilyCount"] >= minimum]
        if flagged.empty:
            continue
        dimension = str(flagged["FeatureType"].iloc[0])
        feature_map = getattr(model.maps, dimension, None)
        carriers: dict[str, list[str]] = {}
        if feature_map is not None and not feature_map.empty:
            carriers = {
                str(feature_id): sorted(set(group))
                for feature_id, group in feature_map.groupby("feature_id")["pathway_key"]
            }

        for row in flagged.itertuples():
            using_pathways = carriers.get(str(row.FeatureId), [])
            max_centrality = (
                max(
                    (float(centrality.get(pathway, 0.0)) for pathway in using_pathways),
                    default=0.0,
                )
                if using_pathways
                else 0.0
            )
            touches_boundary = bool(set(using_pathways) & cross_family)

            reasons = [
                f"used by {int(row.FamilyCount)} candidate families "
                f"(threshold {minimum})",
                f"{int(row.PathwayCount)} pathways",
            ]
            if row.TotalOccurrences:
                reasons.append(f"{int(row.TotalOccurrences):,} triage-logic occurrences")
            if touches_boundary:
                reasons.append("carried by at least one boundary pathway or cross-family hub")
            if max_centrality > 0:
                reasons.append(
                    f"max carrier betweenness {max_centrality:.4f}"
                )

            records.append(
                {
                    "FeatureType": dimension,
                    "FeatureTypeLabel": FEATURE_TYPE_LABELS.get(dimension, dimension),
                    "FeatureId": row.FeatureId,
                    "Description": row.Description,
                    "strategy": row.strategy,
                    "FamilyCount": int(row.FamilyCount),
                    "PathwayCount": int(row.PathwayCount),
                    "TotalOccurrences": int(row.TotalOccurrences),
                    "DuplicationIfFederated": int(row.FamilyCount) - 1,
                    "GraphCentralityIfApplicable": round(max_centrality, 8),
                    "UsedByCrossFamilyPathway": touches_boundary,
                    "TopFamilyId": row.TopFamilyId,
                    "TopFamilyLabel": row.TopFamilyLabel,
                    "FamilyDistribution": row.FamilyDistribution,
                    "SharingBand": row.SharingBand,
                    "ReasonFlagged": "; ".join(reasons),
                    "Conclusion": (
                        "evidence only -- whether this belongs in a shared network "
                        "requires clinical review and Phase 3 sizing"
                    ),
                }
            )
    if not records:
        return pd.DataFrame(
            columns=[
                "FeatureType", "FeatureTypeLabel", "FeatureId", "Description", "strategy",
                "FamilyCount", "PathwayCount", "TotalOccurrences",
                "DuplicationIfFederated", "GraphCentralityIfApplicable",
                "UsedByCrossFamilyPathway", "TopFamilyId", "TopFamilyLabel",
                "FamilyDistribution", "SharingBand", "ReasonFlagged", "Conclusion",
            ]
        )
    return pd.DataFrame(records).sort_values(
        ["FeatureType", "FamilyCount", "PathwayCount", "FeatureId"],
        ascending=[True, False, False, True],
        ignore_index=True,
    )


def shared_core_summary(
    shared_features: Mapping[str, pd.DataFrame],
    shared_core: pd.DataFrame,
    *,
    config: FamilyDiscoveryConfig,
) -> pd.DataFrame:
    """Summarise the sharing profile per feature type.

    Gives the counts behind the shared-core flag: how many features of each type exist,
    how they band by family count, and what share would need duplicating across
    families.
    """
    records = []
    for stem, frame in sorted(shared_features.items()):
        if frame.empty:
            continue
        dimension = str(frame["FeatureType"].iloc[0])
        total = len(frame)
        flagged = (
            int((shared_core["FeatureType"] == dimension).sum())
            if not shared_core.empty else 0
        )
        records.append(
            {
                "FeatureType": dimension,
                "FeatureTypeLabel": FEATURE_TYPE_LABELS.get(dimension, dimension),
                "OutputTable": f"{stem}.csv",
                "FeaturesTotal": total,
                "FamilySpecific": int((frame["SharingBand"] == "family-specific").sum()),
                "SharedBy2Families": int(
                    (frame["SharingBand"] == "shared by 2 families").sum()
                ),
                "SharedBy3To5Families": int(
                    (frame["SharingBand"] == "shared by 3-5 families").sum()
                ),
                "BroadlyShared": int((frame["SharingBand"] == "broadly shared").sum()),
                "PercentageFamilySpecific": round(
                    100.0 * float((frame["SharingBand"] == "family-specific").sum()) / total, 2
                ),
                "PercentageBroadlyShared": round(
                    100.0 * float((frame["SharingBand"] == "broadly shared").sum()) / total, 2
                ),
                "MedianFamilyCount": float(frame["FamilyCount"].median()),
                "MaxFamilyCount": int(frame["FamilyCount"].max()),
                "SharedCoreCandidates": flagged,
                "SharedCoreThresholdFamilies": config.shared_core_minimum_family_count,
                "TotalDuplicationIfFederated": (
                    int(
                        shared_core.loc[
                            shared_core["FeatureType"] == dimension, "DuplicationIfFederated"
                        ].sum()
                    )
                    if not shared_core.empty else 0
                ),
            }
        )
    if not records:
        return pd.DataFrame()
    return pd.DataFrame(records).sort_values("FeatureType", ignore_index=True)
