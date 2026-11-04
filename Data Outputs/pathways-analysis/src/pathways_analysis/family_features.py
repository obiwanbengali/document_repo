"""Phase 2: the per-pathway feature model and the NHS-native candidate groupings.

This module is the single source of the data every other Phase 2 module consumes:

* :class:`FeatureMaps` -- long-format ``pathway -> feature`` maps, one per evidence
  dimension, never combined into a single score.
* :class:`PathwayFeatureModel` -- one normalised row per in-scope pathway.
* :class:`CandidateFamilySet` -- a candidate grouping of pathways, which may overlap.
* the NHS-native candidate groupings and their structural metrics.
* pairwise similarity, computed separately per evidence dimension.

Design rules
------------
**A pathway does not belong to exactly one family.** Membership is held long-format so
a pathway can appear in several families of the same strategy (clinical areas, trauma
and age tags are all genuinely overlapping in this dataset), and
:attr:`CandidateFamilySet.overlapping` records whether a strategy is a partition.

**Evidence dimensions stay separate.** Question, symptom-discriminator, SNOMED,
disposition, clinical-area and graph evidence are computed independently. Only Hybrid C
combines them, under weights declared in configuration.

**Nothing here is a clinical statement.** A grouping produced by this module is a
structural candidate. Naming, and any claim that a group is a clinical family, requires
the clinical review pack.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Final, Iterable, Mapping, Sequence

import networkx as nx
import numpy as np
import pandas as pd

from . import graph as graph_tools

LOGGER: Final = logging.getLogger(__name__)

#: Evidence dimensions held as pathway -> feature sets. Graph adjacency is deliberately
#: absent: it is a relation between pathways, not a feature of one, and is handled
#: through the pathway graph itself.
FEATURE_DIMENSIONS: Final[tuple[str, ...]] = (
    "question",
    "symptom_discriminator",
    "snomed",
    "disposition",
    "clinical_area",
)

#: Basis categories for a candidate family set. Kept distinct throughout Phase 2
#: because a graph cluster and an NHS grouping are different kinds of claim.
FAMILY_BASIS_NATIVE: Final = "nhs_native"
FAMILY_BASIS_GRAPH: Final = "graph_derived"
FAMILY_BASIS_HYBRID: Final = "hybrid"

#: Placeholder used where a pathway carries no value for a native grouping key. Kept as
#: an explicit group rather than dropped, so the size of the unclassifiable remainder
#: stays visible.
UNASSIGNED: Final = "UNASSIGNED"


# ======================================================================================
# Feature maps
# ======================================================================================
@dataclass(frozen=True)
class FeatureMaps:
    """Long-format ``pathway_key -> feature_id`` maps, one per evidence dimension.

    Each frame has exactly two columns, ``pathway_key`` and ``feature_id``, is
    de-duplicated, and is restricted to the in-scope pathways. ``feature_id`` is always
    a string so that the five dimensions can share one code path; the original typed
    identifier is preserved in the catalogue frames.
    """

    question: pd.DataFrame
    symptom_discriminator: pd.DataFrame
    snomed: pd.DataFrame
    disposition: pd.DataFrame
    clinical_area: pd.DataFrame

    def as_mapping(self) -> dict[str, pd.DataFrame]:
        """Return the maps keyed by dimension name, in :data:`FEATURE_DIMENSIONS` order."""
        return {dimension: getattr(self, dimension) for dimension in FEATURE_DIMENSIONS}

    def feature_sets(self, dimension: str) -> dict[str, set[str]]:
        """Return ``{pathway_key: {feature_id, ...}}`` for one dimension."""
        frame = getattr(self, dimension)
        return {
            key: set(group)
            for key, group in frame.groupby("pathway_key")["feature_id"]
        }


def _two_column_map(
    frame: pd.DataFrame,
    *,
    pathway_column: str,
    feature_column: str,
    scope: Iterable[str],
) -> pd.DataFrame:
    """Reduce an extract to a de-duplicated in-scope ``pathway_key``/``feature_id`` map."""
    scope_set = set(scope)
    if frame.empty:
        return pd.DataFrame(columns=["pathway_key", "feature_id"])
    reduced = (
        frame[[pathway_column, feature_column]]
        .dropna()
        .rename(columns={pathway_column: "pathway_key", feature_column: "feature_id"})
    )
    reduced["feature_id"] = reduced["feature_id"].astype("string").str.strip()
    reduced = reduced.loc[reduced["pathway_key"].isin(scope_set)]
    return reduced.drop_duplicates().sort_values(
        ["pathway_key", "feature_id"], ignore_index=True
    )


def build_feature_maps(
    *,
    triage_logic: pd.DataFrame,
    pathway_discriminators: pd.DataFrame,
    pathway_snomed: pd.DataFrame,
    pathway_dispositions: pd.DataFrame,
    pathway_clinical_areas: pd.DataFrame,
    scope: Sequence[str],
) -> FeatureMaps:
    """Build the five pathway -> feature maps from the Phase 1/2 extracts.

    Args:
        triage_logic: Full triage logic table, including the ``node_kind`` column.
            Only ``question`` rows are used: ``tblTriageLogic.QuestionID`` is
            polymorphic, and only ``Tx`` nodes are answerable questions and therefore
            candidate Bayesian variables.
        pathway_discriminators: ``pathway_key``/``sd_id`` map.
        pathway_snomed: ``pathway_key``/``snomed_concept_id`` map.
        pathway_dispositions: ``pathway_key``/``disposition_code_key`` map, unioned
            across both routes from a pathway to a disposition.
        pathway_clinical_areas: ``pathway_key``/``clinical_area_id`` map.
        scope: Pathway keys eligible for family membership.

    Returns:
        The five maps, restricted to ``scope``.
    """
    questions = triage_logic.loc[triage_logic["node_kind"] == "question"]
    return FeatureMaps(
        question=_two_column_map(
            questions, pathway_column="pathway_key", feature_column="question_key", scope=scope
        ),
        symptom_discriminator=_two_column_map(
            pathway_discriminators,
            pathway_column="pathway_key",
            feature_column="sd_id",
            scope=scope,
        ),
        snomed=_two_column_map(
            pathway_snomed,
            pathway_column="pathway_key",
            feature_column="snomed_concept_id",
            scope=scope,
        ),
        disposition=_two_column_map(
            pathway_dispositions,
            pathway_column="pathway_key",
            feature_column="disposition_code_key",
            scope=scope,
        ),
        clinical_area=_two_column_map(
            pathway_clinical_areas,
            pathway_column="pathway_key",
            feature_column="clinical_area_id",
            scope=scope,
        ),
    )


def indicator_matrix(
    map_frame: pd.DataFrame,
    entities: Sequence[str],
) -> tuple[np.ndarray, list[str]]:
    """Build a boolean ``entities x features`` matrix from a long-format map.

    Every overlap, cohesion and affinity metric in Phase 2 is a product of two such
    matrices. Doing it this way rather than with per-pair Python loops keeps the whole
    of Phase 2 to a handful of deterministic matrix products over small matrices
    (~800 pathways, ~4,000 features).

    Args:
        map_frame: Two-column ``pathway_key``/``feature_id`` frame.
        entities: Row order. Entities absent from ``map_frame`` get an all-zero row,
            which is the correct representation of "this pathway has no such feature".

    Returns:
        ``(matrix, features)`` where ``matrix`` is float32 0/1 and ``features`` is the
        sorted column order.
    """
    entity_index = {value: position for position, value in enumerate(entities)}
    if map_frame.empty:
        return np.zeros((len(entities), 0), dtype=np.float32), []

    pairs = map_frame.loc[map_frame["pathway_key"].isin(entity_index)]
    features = sorted(pairs["feature_id"].dropna().unique())
    if not features:
        return np.zeros((len(entities), 0), dtype=np.float32), []
    feature_index = {value: position for position, value in enumerate(features)}

    matrix = np.zeros((len(entities), len(features)), dtype=np.float32)
    matrix[
        pairs["pathway_key"].map(entity_index).to_numpy(dtype=np.int64),
        pairs["feature_id"].map(feature_index).to_numpy(dtype=np.int64),
    ] = 1.0
    return matrix, [str(feature) for feature in features]


def adjacency_matrices(
    graph: nx.DiGraph,
    entities: Sequence[str],
) -> tuple[np.ndarray, np.ndarray]:
    """Return directed edge-count and transition-weight matrices over ``entities``.

    Both are returned because the two answer different questions: the unweighted matrix
    counts distinct pathway-to-pathway relationships, and the weighted one counts the
    transfer records carrying them. Reporting only the weighted form would let a single
    heavily-branched answer dominate a family boundary metric.

    Self loops are retained: a pathway transferring to itself is a real structure in
    this data, and it is internal to whatever family holds the pathway.
    """
    index = {value: position for position, value in enumerate(entities)}
    size = len(entities)
    unweighted = np.zeros((size, size), dtype=np.float32)
    weighted = np.zeros((size, size), dtype=np.float32)
    for source, target, data in graph.edges(data=True):
        row = index.get(source)
        column = index.get(target)
        if row is None or column is None:
            continue
        unweighted[row, column] = 1.0
        weighted[row, column] = float(data.get(graph_tools.WEIGHT_ATTRIBUTE, 1) or 1)
    return unweighted, weighted


# ======================================================================================
# Candidate family sets
# ======================================================================================
@dataclass
class CandidateFamilySet:
    """One candidate grouping of pathways into families.

    Attributes:
        strategy: Unique strategy name, e.g. ``native_symptom_group``, ``graph_louvain``,
            ``hybrid_a``.
        basis: One of :data:`FAMILY_BASIS_NATIVE`, :data:`FAMILY_BASIS_GRAPH`,
            :data:`FAMILY_BASIS_HYBRID`. Kept explicit so a graph cluster is never
            reported as a clinical family.
        description: One-line statement of how the grouping was produced, carried into
            the evidence report so no family set is unexplained.
        membership: Long-format frame with ``family_id``, ``family_label``,
            ``pathway_key``, ``membership_basis`` and ``membership_strength``. Multiple
            rows per pathway are allowed and expected for overlapping strategies.
        overlapping: Whether a pathway may appear in more than one family. Measured
            from ``membership``, not asserted.
        notes: Free-text observations recorded while the set was built (absorbed small
            families, splits applied, metadata gaps).
    """

    strategy: str
    basis: str
    description: str
    membership: pd.DataFrame
    notes: list[str] = field(default_factory=list)

    @property
    def overlapping(self) -> bool:
        """Whether any pathway belongs to more than one family in this strategy."""
        if self.membership.empty:
            return False
        return bool(self.membership["pathway_key"].duplicated().any())

    @property
    def family_ids(self) -> list[str]:
        """Sorted family ids in this strategy."""
        return sorted(self.membership["family_id"].unique())

    @property
    def pathway_count(self) -> int:
        """Distinct pathways placed in at least one family."""
        return int(self.membership["pathway_key"].nunique())

    def families(self) -> dict[str, set[str]]:
        """Return ``{family_id: {pathway_key, ...}}``."""
        return {
            family_id: set(group)
            for family_id, group in self.membership.groupby("family_id")["pathway_key"]
        }

    def labels(self) -> dict[str, str]:
        """Return ``{family_id: family_label}``."""
        return dict(
            self.membership.drop_duplicates("family_id")
            .set_index("family_id")["family_label"]
            .astype(str)
        )


def build_membership_frame(
    assignments: Mapping[str, Iterable[str]],
    *,
    strategy: str,
    labels: Mapping[str, str] | None = None,
    membership_basis: str = "",
    strengths: Mapping[tuple[str, str], float] | None = None,
) -> pd.DataFrame:
    """Build a membership frame from ``{family_id: pathways}``.

    Args:
        assignments: Mapping of family id to its member pathway keys.
        strategy: Strategy name, recorded on every row.
        labels: Optional family labels. Defaults to the family id.
        membership_basis: Why the pathway is in the family, recorded per row.
        strengths: Optional ``{(family_id, pathway_key): strength}`` in 0..1. Defaults
            to 1.0, which means "assigned by the grouping rule with no partial
            membership claim".

    Returns:
        Sorted long-format membership frame.
    """
    labels = labels or {}
    strengths = strengths or {}
    records = []
    for family_id, pathways in assignments.items():
        for pathway_key in pathways:
            records.append(
                {
                    "strategy": strategy,
                    "family_id": family_id,
                    "family_label": str(labels.get(family_id, family_id)),
                    "pathway_key": pathway_key,
                    "membership_basis": membership_basis,
                    "membership_strength": round(
                        float(strengths.get((family_id, pathway_key), 1.0)), 6
                    ),
                }
            )
    if not records:
        return pd.DataFrame(
            columns=[
                "strategy", "family_id", "family_label", "pathway_key",
                "membership_basis", "membership_strength",
            ]
        )
    return pd.DataFrame(records).sort_values(
        ["family_id", "pathway_key"], ignore_index=True
    )


# ======================================================================================
# Per-pathway feature model
# ======================================================================================
def classify_age(age_ids: set[int], adult_age_id: int | None) -> str:
    """Classify a pathway's age tags.

    The adult band is identified from the stored ``MinHours`` boundary, not from the
    description text, so the classification does not depend on wording. Every band
    other than the adult band is treated as paediatric.

    Args:
        age_ids: Age ids tagged on the pathway.
        adult_age_id: Id of the band with the highest ``MinHours``.

    Returns:
        ``adult_only``, ``paediatric_only``, ``adult_and_paediatric`` or ``unspecified``.
    """
    if not age_ids:
        return "unspecified"
    if adult_age_id is None:
        return "unclassified"
    has_adult = adult_age_id in age_ids
    has_paediatric = bool(age_ids - {adult_age_id})
    if has_adult and has_paediatric:
        return "adult_and_paediatric"
    if has_adult:
        return "adult_only"
    return "paediatric_only"


def classify_trauma(trauma_ids: set[int], trauma_labels: Mapping[int, str]) -> str:
    """Classify a pathway's trauma tags.

    A pathway may carry both trauma values (24 active pathways do), so this is not a
    binary flag. The stored descriptions supply the labels; the structure of the
    classification comes from the tag set.
    """
    if not trauma_ids:
        return "unspecified"
    if len(trauma_ids) > 1:
        return "trauma_and_non_trauma"
    only = next(iter(trauma_ids))
    label = str(trauma_labels.get(only, only)).strip().lower().replace(" ", "_")
    return label or "unspecified"


def classify_gender(gender_ids: set[int], gender_labels: Mapping[int, str]) -> str:
    """Classify a pathway's gender tags into a stable structural label."""
    if not gender_ids:
        return "unspecified"
    labels = sorted(
        str(gender_labels.get(gender_id, gender_id)).strip().lower() for gender_id in gender_ids
    )
    if len(labels) == 1:
        return f"{labels[0]}_only"
    return "_and_".join(labels)


def _pipe_join(values: Iterable[object]) -> str:
    """Join values with ' | ', sorted and de-duplicated, skipping nulls."""
    cleaned = sorted({str(value) for value in values if value is not None and pd.notna(value)})
    return " | ".join(cleaned)


@dataclass
class PathwayFeatureModel:
    """The normalised Phase 2 dataset: one row per in-scope pathway, plus its context.

    Attributes:
        features: One row per pathway, PascalCase columns as specified for this
            deliverable.
        maps: The five feature maps.
        pathway_graph: The directed pathway transfer graph (Phase 1 scope: every active
            pathway plus any pathway taking part in a resolved transfer).
        edges: The aggregated pathway-to-pathway edge list.
        node_metrics: Per-pathway graph metrics.
        scope: In-scope pathway keys, sorted. This is the row order of every matrix.
        metadata_coverage: Per-metadata-field coverage counts, so an empty field
            (``Module`` is NULL for every row in this snapshot) is reported rather than
            silently producing a one-family grouping.
    """

    features: pd.DataFrame
    maps: FeatureMaps
    pathway_graph: nx.DiGraph
    edges: pd.DataFrame
    node_metrics: pd.DataFrame
    scope: list[str]
    metadata_coverage: pd.DataFrame
    adult_age_id: int | None = None

    def title_lookup(self) -> dict[str, str]:
        """Return ``{pathway_key: "PathwayID PathwayTitle"}`` for labelling."""
        return {
            row.PathwayKey: f"{row.PathwayID} {row.PathwayTitle}"
            for row in self.features.itertuples()
        }


def build_pathway_feature_model(
    *,
    pathways: pd.DataFrame,
    complexity: pd.DataFrame,
    symptom_groups: pd.DataFrame,
    clinical_areas: pd.DataFrame,
    pathway_clinical_areas: pd.DataFrame,
    pathway_ages: pd.DataFrame,
    pathway_genders: pd.DataFrame,
    pathway_trauma: pd.DataFrame,
    age_reference: pd.DataFrame,
    gender_reference: pd.DataFrame,
    trauma_reference: pd.DataFrame,
    maps: FeatureMaps,
    pathway_graph: nx.DiGraph,
    edges: pd.DataFrame,
    node_metrics: pd.DataFrame,
    graph_community: Mapping[str, int],
    graph_community_method: str,
    scope: Sequence[str],
) -> PathwayFeatureModel:
    """Assemble the per-pathway Phase 2 feature model.

    Feature-id lists are emitted as pipe-joined strings so the dataset stays one row per
    pathway and survives a CSV round trip. Counts are emitted alongside them so no
    consumer has to parse the strings to get a magnitude.

    Returns:
        The populated :class:`PathwayFeatureModel`.
    """
    scope_list = sorted(set(scope))
    scope_set = set(scope_list)

    base = pathways.loc[pathways["pathway_key"].isin(scope_set)].copy()
    base = base.merge(
        symptom_groups[["sg_id", "sg_desc"]],
        left_on="symptom_group_id",
        right_on="sg_id",
        how="left",
    )

    areas = pathway_clinical_areas.merge(clinical_areas, on="clinical_area_id", how="left")
    areas = areas.loc[areas["pathway_key"].isin(scope_set)]
    area_grouped = (
        areas.groupby("pathway_key")
        .agg(
            ClinicalAreaIds=("clinical_area_id", _pipe_join),
            ClinicalAreas=("clinical_area_description", _pipe_join),
            AreaGroups=("area_group", _pipe_join),
            ClinicalAreaCount=("clinical_area_id", "nunique"),
            AreaGroupCount=("area_group", "nunique"),
        )
        .reset_index()
    )

    # -- age / gender / trauma -------------------------------------------------------
    # The adult band is the one with the greatest MinHours. Neonate carries NULL
    # boundaries in this snapshot, so NULL sorts below every populated band and is
    # therefore treated as paediatric, which matches its stored description.
    adult_age_id: int | None = None
    if not age_reference.empty:
        ordered = age_reference.copy()
        ordered["age_min_hours"] = pd.to_numeric(
            ordered["age_min_hours"], errors="coerce"
        ).fillna(-1)
        adult_age_id = int(ordered.sort_values("age_min_hours").iloc[-1]["age_id"])

    gender_labels = dict(
        zip(gender_reference["gender_id"], gender_reference["gender_description"])
    ) if not gender_reference.empty else {}
    trauma_labels = dict(
        zip(trauma_reference["trauma_id"], trauma_reference["trauma_description"])
    ) if not trauma_reference.empty else {}

    def tag_sets(frame: pd.DataFrame, column: str) -> dict[str, set[int]]:
        if frame.empty:
            return {}
        subset = frame.loc[frame["pathway_key"].isin(scope_set)]
        return {
            key: {int(value) for value in group}
            for key, group in subset.groupby("pathway_key")[column]
        }

    age_sets = tag_sets(pathway_ages, "age_id")
    gender_sets = tag_sets(pathway_genders, "gender_id")
    trauma_sets = tag_sets(pathway_trauma, "trauma_id")

    age_descriptions = (
        pathway_ages.loc[pathway_ages["pathway_key"].isin(scope_set)]
        .groupby("pathway_key")["age_description"].apply(_pipe_join).to_dict()
        if not pathway_ages.empty else {}
    )
    gender_descriptions = (
        pathway_genders.loc[pathway_genders["pathway_key"].isin(scope_set)]
        .groupby("pathway_key")["gender_description"].apply(_pipe_join).to_dict()
        if not pathway_genders.empty else {}
    )
    trauma_descriptions = (
        pathway_trauma.loc[pathway_trauma["pathway_key"].isin(scope_set)]
        .groupby("pathway_key")["trauma_description"].apply(_pipe_join).to_dict()
        if not pathway_trauma.empty else {}
    )

    # -- feature id lists ------------------------------------------------------------
    feature_columns: dict[str, dict[str, str]] = {}
    feature_counts: dict[str, dict[str, int]] = {}
    for dimension, frame in maps.as_mapping().items():
        if frame.empty:
            feature_columns[dimension] = {}
            feature_counts[dimension] = {}
            continue
        grouped = frame.groupby("pathway_key")["feature_id"]
        feature_columns[dimension] = grouped.apply(_pipe_join).to_dict()
        feature_counts[dimension] = grouped.nunique().to_dict()

    # -- graph context ---------------------------------------------------------------
    outgoing = (
        edges.groupby("source_pathway_key")["target_pathway_key"].apply(_pipe_join).to_dict()
        if not edges.empty else {}
    )
    incoming = (
        edges.groupby("target_pathway_key")["source_pathway_key"].apply(_pipe_join).to_dict()
        if not edges.empty else {}
    )
    metrics_indexed = (
        node_metrics.set_index("pathway_key") if not node_metrics.empty else pd.DataFrame()
    )

    def metric(pathway_key: str, column: str, default: float = 0.0) -> float:
        if metrics_indexed.empty or pathway_key not in metrics_indexed.index:
            return default
        value = metrics_indexed.at[pathway_key, column]
        return default if pd.isna(value) else float(value)

    complexity_indexed = (
        complexity.set_index("pathway_key") if not complexity.empty else pd.DataFrame()
    )

    def complexity_value(pathway_key: str, column: str) -> float:
        if complexity_indexed.empty or pathway_key not in complexity_indexed.index:
            return 0.0
        if column not in complexity_indexed.columns:
            return 0.0
        value = complexity_indexed.at[pathway_key, column]
        return 0.0 if pd.isna(value) else float(value)

    area_indexed = (
        area_grouped.set_index("pathway_key") if not area_grouped.empty else pd.DataFrame()
    )

    def area_value(pathway_key: str, column: str, default: object = "") -> object:
        if area_indexed.empty or pathway_key not in area_indexed.index:
            return default
        value = area_indexed.at[pathway_key, column]
        return default if pd.isna(value) else value

    base_indexed = base.set_index("pathway_key")
    records = []
    for pathway_key in scope_list:
        row = base_indexed.loc[pathway_key]
        age_ids = age_sets.get(pathway_key, set())
        records.append(
            {
                "PathwayID": row["pathway_id"],
                "PathwayKey": pathway_key,
                "PathwayTitle": row["pathway_title"],
                "PathwayVersionNo": row["pathway_version_no"],
                "Module": row["module"],
                "Party": row["party"],
                "SymptomGroupId": row["symptom_group_id"],
                "SymptomGroupDescription": row["sg_desc"],
                "ClinicalAreaIds": area_value(pathway_key, "ClinicalAreaIds"),
                "ClinicalAreas": area_value(pathway_key, "ClinicalAreas"),
                "AreaGroups": area_value(pathway_key, "AreaGroups"),
                "ClinicalAreaCount": int(area_value(pathway_key, "ClinicalAreaCount", 0) or 0),
                "AreaGroupCount": int(area_value(pathway_key, "AreaGroupCount", 0) or 0),
                "AgeIds": _pipe_join(sorted(age_ids)),
                "AgeDescriptions": age_descriptions.get(pathway_key, ""),
                "AgeClassification": classify_age(age_ids, adult_age_id),
                "GenderIds": _pipe_join(sorted(gender_sets.get(pathway_key, set()))),
                "GenderDescriptions": gender_descriptions.get(pathway_key, ""),
                "GenderClassification": classify_gender(
                    gender_sets.get(pathway_key, set()), gender_labels
                ),
                "TraumaIds": _pipe_join(sorted(trauma_sets.get(pathway_key, set()))),
                "TraumaDescriptions": trauma_descriptions.get(pathway_key, ""),
                "TraumaClassification": classify_trauma(
                    trauma_sets.get(pathway_key, set()), trauma_labels
                ),
                "QuestionIDs": feature_columns["question"].get(pathway_key, ""),
                "QuestionCount": int(feature_counts["question"].get(pathway_key, 0)),
                "SymptomDiscriminatorIds": feature_columns["symptom_discriminator"].get(
                    pathway_key, ""
                ),
                "SymptomDiscriminatorCount": int(
                    feature_counts["symptom_discriminator"].get(pathway_key, 0)
                ),
                "SnomedConceptIds": feature_columns["snomed"].get(pathway_key, ""),
                "SnomedConceptCount": int(feature_counts["snomed"].get(pathway_key, 0)),
                "DispositionIds": feature_columns["disposition"].get(pathway_key, ""),
                "DispositionCount": int(feature_counts["disposition"].get(pathway_key, 0)),
                "LogicPositionCount": int(
                    complexity_value(pathway_key, "logic_position_count")
                ),
                "LogicRowCount": int(complexity_value(pathway_key, "logic_row_count")),
                "OutgoingPathwayEdges": outgoing.get(pathway_key, ""),
                "OutgoingEdgeCount": int(metric(pathway_key, "out_degree")),
                "IncomingPathwayEdges": incoming.get(pathway_key, ""),
                "IncomingEdgeCount": int(metric(pathway_key, "in_degree")),
                "TotalDegree": int(metric(pathway_key, "total_degree")),
                "WeightedOutDegree": int(metric(pathway_key, "weighted_out_degree")),
                "WeightedInDegree": int(metric(pathway_key, "weighted_in_degree")),
                "BetweennessCentrality": round(
                    metric(pathway_key, "betweenness_centrality"), 8
                ),
                "PageRank": round(metric(pathway_key, "pagerank"), 8),
                "SelfLoop": bool(
                    pathway_graph.has_edge(pathway_key, pathway_key)
                ),
                "GraphCommunityMethod": graph_community_method,
                "GraphCommunityId": graph_community.get(pathway_key, -1),
            }
        )

    features = pd.DataFrame(records).sort_values("PathwayKey", ignore_index=True)

    coverage_rows = []
    for label, column in (
        ("Module", "Module"),
        ("Party", "Party"),
        ("SymptomGroupId", "SymptomGroupId"),
        ("ClinicalAreas", "ClinicalAreas"),
        ("AreaGroups", "AreaGroups"),
        ("AgeIds", "AgeIds"),
        ("GenderIds", "GenderIds"),
        ("TraumaIds", "TraumaIds"),
        ("QuestionIDs", "QuestionIDs"),
        ("SymptomDiscriminatorIds", "SymptomDiscriminatorIds"),
        ("SnomedConceptIds", "SnomedConceptIds"),
        ("DispositionIds", "DispositionIds"),
    ):
        series = features[column]
        if series.dtype == object or str(series.dtype) == "string":
            filled = series.fillna("").astype(str).str.strip()
            populated = int((filled != "").sum())
            # Multi-valued fields are pipe-joined, so distinct values are counted after
            # splitting: "Area A | Area B" is two values, not one.
            distinct = len(
                {
                    part.strip()
                    for value in filled
                    for part in str(value).split("|")
                    if part.strip()
                }
            )
        else:
            populated = int(series.notna().sum())
            distinct = int(series.nunique(dropna=True))
        coverage_rows.append(
            {
                "field": label,
                "pathways_in_scope": len(features),
                "pathways_populated": populated,
                "pathways_missing": len(features) - populated,
                "coverage_percentage": round(
                    100.0 * populated / max(len(features), 1), 2
                ),
                "distinct_values": distinct,
                # "Usable" means the field can actually separate pathways: it needs at
                # least two distinct values. A field populated on 12 of 815 pathways
                # with a single value is populated but useless as a grouping.
                "usable_as_grouping": populated > 0 and distinct >= 2,
            }
        )
    coverage = pd.DataFrame(coverage_rows)

    LOGGER.info(
        "Feature model: %d pathways, %s",
        len(features),
        ", ".join(
            f"{row.field} {row.coverage_percentage:.0f}%"
            for row in coverage.itertuples()
            if row.field in {"SymptomGroupId", "ClinicalAreas", "AgeIds", "TraumaIds"}
        ),
    )

    return PathwayFeatureModel(
        features=features,
        maps=maps,
        pathway_graph=pathway_graph,
        edges=edges,
        node_metrics=node_metrics,
        scope=scope_list,
        metadata_coverage=coverage,
        adult_age_id=adult_age_id,
    )


# ======================================================================================
# NHS-native candidate groupings
# ======================================================================================
def _family_id(prefix: str, index: int) -> str:
    """Return a stable, sortable family id."""
    return f"{prefix}_{index:03d}"


def _assignments_from_column(
    features: pd.DataFrame,
    *,
    key_column: str,
    label_column: str | None,
    split_pipe: bool,
) -> tuple[dict[str, set[str]], dict[str, str]]:
    """Group pathways by a metadata column, optionally splitting a pipe-joined set.

    Returns:
        ``({group_value: pathways}, {group_value: label})`` keyed by the raw value so
        the caller controls id allocation.
    """
    groups: dict[str, set[str]] = {}
    labels: dict[str, str] = {}
    for row in features.itertuples():
        raw = getattr(row, key_column)
        label_source = getattr(row, label_column) if label_column else None
        if raw is None or (not isinstance(raw, str) and pd.isna(raw)):
            values = []
            label_values = []
        elif split_pipe:
            values = [part.strip() for part in str(raw).split("|") if part.strip()]
            label_values = (
                [part.strip() for part in str(label_source).split("|") if part.strip()]
                if label_source else []
            )
        else:
            values = [str(raw).strip()] if str(raw).strip() else []
            label_values = (
                [str(label_source).strip()]
                if label_source is not None and pd.notna(label_source)
                else []
            )

        if not values:
            groups.setdefault(UNASSIGNED, set()).add(row.PathwayKey)
            labels[UNASSIGNED] = UNASSIGNED
            continue
        for position, value in enumerate(values):
            groups.setdefault(value, set()).add(row.PathwayKey)
            if value not in labels:
                if len(label_values) == len(values):
                    labels[value] = label_values[position]
                elif len(label_values) == 1:
                    labels[value] = label_values[0]
                else:
                    labels[value] = value
    return groups, labels


def native_candidate_sets(
    model: PathwayFeatureModel,
    *,
    clinical_areas: pd.DataFrame,
) -> list[CandidateFamilySet]:
    """Build the NHS-native candidate family sets (Phase 2 section 2).

    Six groupings are attempted: symptom group, clinical area, area group,
    trauma, module and age classification. Gender is added as a seventh because the
    metadata exists and excluding it would leave an available dimension untested.

    A grouping whose source metadata is empty in this snapshot is still returned, with
    every pathway in ``UNASSIGNED`` and a note, so that "unusable" is a measured result
    rather than an omission.

    **None of these is a Bayesian family.** They are the baseline against which the
    graph-derived and hybrid candidates are compared.
    """
    features = model.features
    sets: list[CandidateFamilySet] = []

    specs = (
        (
            "native_symptom_group",
            "SymptomGroupId",
            "SymptomGroupDescription",
            False,
            "SG",
            "NHS SymptomGroupId as stored on tblPathways.",
        ),
        (
            "native_clinical_area",
            "ClinicalAreaIds",
            "ClinicalAreas",
            True,
            "CA",
            "NHS ClinicalAreaID from tblPathway2ClinicalAreas. Overlapping by design: "
            "a pathway may map to several clinical areas.",
        ),
        (
            "native_area_group",
            "AreaGroups",
            "AreaGroups",
            True,
            "AG",
            "tblClinicalAreas.AreaGroup, the anatomical grouping above clinical area. "
            "Overlapping, because a pathway's clinical areas may span area groups.",
        ),
        (
            "native_trauma",
            "TraumaIds",
            "TraumaDescriptions",
            True,
            "TR",
            "tblPathway2Trauma tags. Overlapping: a pathway may carry both trauma and "
            "non-trauma.",
        ),
        (
            "native_age_group",
            "AgeIds",
            "AgeDescriptions",
            True,
            "AGE",
            "tblPathway2Ages bands. Overlapping: most pathways carry several bands.",
        ),
        (
            "native_gender",
            "GenderIds",
            "GenderDescriptions",
            True,
            "GEN",
            "tblPathway2Genders tags. Overlapping.",
        ),
        (
            "native_module",
            "Module",
            None,
            False,
            "MOD",
            "tblPathways.Module.",
        ),
    )

    for strategy, key_column, label_column, split_pipe, prefix, description in specs:
        groups, labels = _assignments_from_column(
            features, key_column=key_column, label_column=label_column, split_pipe=split_pipe
        )
        ordered = sorted(
            groups.items(), key=lambda item: (-len(item[1]), str(item[0]))
        )
        assignments: dict[str, set[str]] = {}
        id_labels: dict[str, str] = {}
        for index, (value, pathways) in enumerate(ordered):
            family_id = _family_id(prefix, index)
            assignments[family_id] = pathways
            raw_label = labels.get(value, str(value))
            id_labels[family_id] = (
                UNASSIGNED if value == UNASSIGNED else f"{raw_label} [{key_column}={value}]"
            )

        notes = []
        unassigned_ids = [
            family_id for family_id, label in id_labels.items() if label == UNASSIGNED
        ]
        if unassigned_ids:
            missing = sum(len(assignments[family_id]) for family_id in unassigned_ids)
            notes.append(
                f"{missing} of {len(features)} in-scope pathways carry no {key_column} "
                f"value and are held in an explicit {UNASSIGNED} family rather than dropped."
            )
        if len(assignments) <= 1:
            notes.append(
                f"{key_column} yields {len(assignments)} group(s) in this snapshot, so it "
                "cannot separate pathways and is not analytically usable as a grouping."
            )

        sets.append(
            CandidateFamilySet(
                strategy=strategy,
                basis=FAMILY_BASIS_NATIVE,
                description=description,
                membership=build_membership_frame(
                    assignments,
                    strategy=strategy,
                    labels=id_labels,
                    membership_basis=f"nhs_native:{key_column}",
                ),
                notes=notes,
            )
        )

    # Area-group coverage note: clinical areas are the only route to an area group, so
    # a pathway with no clinical area also has no area group.
    area_group_count = clinical_areas["area_group"].nunique() if not clinical_areas.empty else 0
    for candidate in sets:
        if candidate.strategy == "native_area_group":
            candidate.notes.append(
                f"{area_group_count} distinct AreaGroup values exist across "
                f"{len(clinical_areas)} clinical areas."
            )
    return sets


def native_group_metrics(
    candidate_sets: Sequence[CandidateFamilySet],
    model: PathwayFeatureModel,
) -> pd.DataFrame:
    """Compute the Phase 2 section 2 metrics for every native candidate grouping.

    Metric definitions
    ------------------
    * ``internal_edges`` -- directed transfer edges whose source and target are both in
      the group. Self loops count as internal.
    * ``external_edges_outgoing`` -- source in the group, target outside it. A target
      outside the family-membership scope (an archived pathway participating in a
      transfer) counts as external rather than being dropped.
    * ``internal_edge_percentage`` -- ``internal / (internal + outgoing) * 100``, the
      same definition Phase 1 uses, so the two phases' cohesion figures are comparable.
    * ``pathways_with_external_links`` -- members adjacent in either direction to a
      non-member.
    * ``average_pathway_degree`` / ``median_pathway_degree`` -- total degree in the full
      pathway graph, over the group's members.
    """
    graph = model.pathway_graph
    degrees = {node: graph.degree(node) for node in graph.nodes()}
    records = []

    for candidate in candidate_sets:
        families = candidate.families()
        labels = candidate.labels()
        for family_id in sorted(families):
            members = families[family_id]
            present = {node for node in members if node in graph}
            internal = outgoing = incoming = 0
            internal_weight = outgoing_weight = 0
            boundary_members = 0
            external_neighbours: set[str] = set()
            for node in present:
                node_external = False
                for _, target, data in graph.out_edges(node, data=True):
                    weight = int(data.get(graph_tools.WEIGHT_ATTRIBUTE, 0) or 0)
                    if target in members:
                        internal += 1
                        internal_weight += weight
                    else:
                        outgoing += 1
                        outgoing_weight += weight
                        external_neighbours.add(target)
                        node_external = True
                for source, _, _ in graph.in_edges(node, data=True):
                    if source not in members:
                        incoming += 1
                        external_neighbours.add(source)
                        node_external = True
                if node_external:
                    boundary_members += 1

            member_degrees = [degrees.get(node, 0) for node in members]
            boundary_total = internal + outgoing
            records.append(
                {
                    "strategy": candidate.strategy,
                    "family_basis": candidate.basis,
                    "family_id": family_id,
                    "family_label": labels.get(family_id, family_id),
                    "pathway_count": len(members),
                    "pathways_in_graph": len(present),
                    "unique_questions": _unique_feature_count(model, members, "question"),
                    "unique_symptom_discriminators": _unique_feature_count(
                        model, members, "symptom_discriminator"
                    ),
                    "unique_snomed_concepts": _unique_feature_count(model, members, "snomed"),
                    "unique_dispositions": _unique_feature_count(model, members, "disposition"),
                    "internal_edges": internal,
                    "external_edges_outgoing": outgoing,
                    "external_edges_incoming": incoming,
                    "internal_transition_count": internal_weight,
                    "outgoing_transition_count": outgoing_weight,
                    "internal_edge_percentage": (
                        round(100.0 * internal / boundary_total, 2)
                        if boundary_total else float("nan")
                    ),
                    "external_edge_percentage": (
                        round(100.0 * outgoing / boundary_total, 2)
                        if boundary_total else float("nan")
                    ),
                    "pathways_with_external_links": boundary_members,
                    "distinct_external_neighbours": len(external_neighbours),
                    "average_pathway_degree": (
                        round(float(np.mean(member_degrees)), 3) if member_degrees else 0.0
                    ),
                    "median_pathway_degree": (
                        float(np.median(member_degrees)) if member_degrees else 0.0
                    ),
                }
            )
    if not records:
        return pd.DataFrame()
    return pd.DataFrame(records).sort_values(
        ["strategy", "pathway_count", "family_id"],
        ascending=[True, False, True],
        ignore_index=True,
    )


def _unique_feature_count(
    model: PathwayFeatureModel, members: Iterable[str], dimension: str
) -> int:
    """Count distinct features of one dimension across a set of pathways."""
    frame = getattr(model.maps, dimension)
    if frame.empty:
        return 0
    member_set = set(members)
    return int(frame.loc[frame["pathway_key"].isin(member_set), "feature_id"].nunique())


# ======================================================================================
# Pairwise similarity, per evidence dimension
# ======================================================================================
def similarity_tables(
    model: PathwayFeatureModel,
    *,
    minimum_intersection: int = 1,
) -> dict[str, pd.DataFrame]:
    """Compute per-dimension pairwise pathway similarity (Phase 2 section 4).

    Each dimension is returned separately and **not** combined. Combining them is a
    modelling decision, made only by Hybrid C under declared weights.

    Returns:
        Mapping of dimension name to a frame with ``pathway_key_a``, ``pathway_key_b``,
        set sizes, intersection, union and Jaccard similarity.
    """
    results: dict[str, pd.DataFrame] = {}
    for dimension, frame in model.maps.as_mapping().items():
        if frame.empty:
            results[dimension] = pd.DataFrame(
                columns=[
                    "pathway_key_a", "pathway_key_b", "set_size_a", "set_size_b",
                    "intersection_count", "union_count", "jaccard_similarity",
                ]
            )
            continue
        results[dimension] = graph_tools.jaccard_similarity(
            frame.rename(columns={"feature_id": dimension}),
            entity_column="pathway_key",
            feature_column=dimension,
            min_intersection=minimum_intersection,
        )
        LOGGER.info(
            "Similarity %-22s %8d overlapping pairs across %4d pathways",
            dimension,
            len(results[dimension]),
            frame["pathway_key"].nunique(),
        )
    return results


def graph_similarity_table(
    model: PathwayFeatureModel,
    *,
    max_hops: int,
) -> pd.DataFrame:
    """Build the graph-relationship similarity table (Phase 2 section 4, signal F).

    Unlike the set-based dimensions this is a relation, so it carries direction: the
    direct and reverse edge flags and the two transition counts are reported
    separately rather than summed, because a one-way referral and a mutual referral are
    different structural claims.

    Rows are emitted for unordered pairs within ``max_hops`` in the undirected
    projection, which always includes every directly connected pair.
    """
    hops = graph_tools.undirected_hop_distances(model.pathway_graph, max_hops=max_hops)
    scope = set(model.scope)
    hops = hops.loc[
        hops["pathway_key_a"].isin(scope) & hops["pathway_key_b"].isin(scope)
    ].reset_index(drop=True)
    if hops.empty:
        return pd.DataFrame(
            columns=[
                "pathway_key_a", "pathway_key_b", "direct_edge_exists",
                "reverse_edge_exists", "transitions_a_to_b", "transitions_b_to_a",
                "shortest_path_hops",
            ]
        )

    weights: dict[tuple[str, str], int] = {}
    if not model.edges.empty:
        for row in model.edges.itertuples():
            weights[(row.source_pathway_key, row.target_pathway_key)] = int(
                row.transition_count
            )

    hops["transitions_a_to_b"] = [
        weights.get((row.pathway_key_a, row.pathway_key_b), 0) for row in hops.itertuples()
    ]
    hops["transitions_b_to_a"] = [
        weights.get((row.pathway_key_b, row.pathway_key_a), 0) for row in hops.itertuples()
    ]
    hops["direct_edge_exists"] = hops["transitions_a_to_b"] > 0
    hops["reverse_edge_exists"] = hops["transitions_b_to_a"] > 0
    hops["is_reciprocal"] = hops["direct_edge_exists"] & hops["reverse_edge_exists"]
    return hops[
        [
            "pathway_key_a", "pathway_key_b", "direct_edge_exists", "reverse_edge_exists",
            "is_reciprocal", "transitions_a_to_b", "transitions_b_to_a", "shortest_path_hops",
        ]
    ].sort_values(
        ["shortest_path_hops", "pathway_key_a", "pathway_key_b"], ignore_index=True
    )


@dataclass
class PairwiseSimilarity:
    """Dense pairwise Jaccard matrices, one per feature dimension.

    Phase 2 needs the mean within-group similarity for every family of every candidate
    strategy -- several thousand groups. Recomputing that from the long-format
    similarity tables means an ``isin`` filter over ~190k rows per group per dimension;
    reading it out of a dense matrix is a slice. With ~800 pathways each matrix is
    ~2.6 MB, so the memory cost is trivial and the definition is identical.

    Attributes:
        pathways: Row/column order.
        matrices: ``{dimension: (pathways x pathways) Jaccard matrix}``.
    """

    pathways: list[str]
    matrices: dict[str, np.ndarray]

    def __post_init__(self) -> None:
        self._index = {value: position for position, value in enumerate(self.pathways)}

    @classmethod
    def build(cls, model: "PathwayFeatureModel") -> "PairwiseSimilarity":
        """Compute the Jaccard matrix for every feature dimension of a feature model."""
        pathways = list(model.scope)
        size = len(pathways)
        matrices: dict[str, np.ndarray] = {}
        for dimension in FEATURE_DIMENSIONS:
            matrix, _ = indicator_matrix(getattr(model.maps, dimension), pathways)
            if matrix.shape[1] == 0:
                matrices[dimension] = np.zeros((size, size), dtype=np.float32)
                continue
            intersection = matrix @ matrix.T
            sizes = matrix.sum(axis=1)
            union = sizes[:, None] + sizes[None, :] - intersection
            with np.errstate(divide="ignore", invalid="ignore"):
                similarity = np.where(union > 0, intersection / union, 0.0)
            matrices[dimension] = similarity.astype(np.float32)
        return cls(pathways=pathways, matrices=matrices)

    def matrix(self, dimension: str) -> np.ndarray:
        """Return the Jaccard matrix for one dimension."""
        return self.matrices[dimension]

    def positions(self, members: Iterable[str]) -> np.ndarray:
        """Return the matrix row positions of ``members`` that are in scope."""
        return np.array(
            sorted(self._index[key] for key in set(members) if key in self._index),
            dtype=np.int64,
        )

    def mean_within(self, dimension: str, members: Iterable[str]) -> float:
        """Return the mean pairwise Jaccard similarity over all member pairs.

        Pairs sharing no features contribute 0 rather than being excluded, so a group
        of unrelated pathways containing one similar pair does not look cohesive.

        Returns:
            Mean similarity in 0..1, or NaN for fewer than two in-scope members.
        """
        positions = self.positions(members)
        if positions.size < 2:
            return float("nan")
        block = self.matrices[dimension][np.ix_(positions, positions)]
        count = positions.size
        # Subtract the diagonal, then halve: each unordered pair appears twice.
        total = float(block.sum() - np.trace(block)) / 2.0
        pairs = count * (count - 1) / 2
        return round(total / pairs, 6) if pairs else float("nan")

    def mean_between(
        self, dimension: str, members_a: Iterable[str], members_b: Iterable[str]
    ) -> float:
        """Return the mean pairwise Jaccard similarity between two groups.

        Used to ask whether a subgroup (for example a family's paediatric pathways)
        resembles the rest of its family or forms a distinct structure.
        """
        positions_a = self.positions(members_a)
        positions_b = self.positions(members_b)
        if positions_a.size == 0 or positions_b.size == 0:
            return float("nan")
        block = self.matrices[dimension][np.ix_(positions_a, positions_b)]
        shared = set(positions_a.tolist()) & set(positions_b.tolist())
        total = float(block.sum())
        count = positions_a.size * positions_b.size
        if shared:
            # Exclude self-pairs so a pathway in both groups cannot contribute its own
            # similarity of 1.0 to a between-group mean.
            total -= sum(
                float(self.matrices[dimension][position, position]) for position in shared
            )
            count -= len(shared)
        return round(total / count, 6) if count > 0 else float("nan")


def mean_pairwise_similarity(
    similarity: pd.DataFrame,
    members: Iterable[str],
) -> float:
    """Return the mean Jaccard similarity over all member pairs.

    Pairs absent from ``similarity`` share no features, so they contribute 0 rather
    than being excluded -- excluding them would make a group of unrelated pathways with
    one similar pair look highly cohesive.

    Returns:
        Mean similarity in 0..1, or NaN for fewer than two members.
    """
    member_list = sorted(set(members))
    if len(member_list) < 2:
        return float("nan")
    member_set = set(member_list)
    if similarity.empty:
        return 0.0
    subset = similarity.loc[
        similarity["pathway_key_a"].isin(member_set)
        & similarity["pathway_key_b"].isin(member_set)
    ]
    possible = graph_tools.pair_count(len(member_list))
    return round(float(subset["jaccard_similarity"].sum()) / possible, 6) if possible else 0.0
