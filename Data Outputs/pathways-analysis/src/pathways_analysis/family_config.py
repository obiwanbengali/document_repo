"""Phase 2 configuration loading for family discovery.

Every threshold, weight and method choice used by Phase 2 lives in
``config/family_discovery.yaml``. This module loads it, validates it and exposes it as
typed dataclasses.

Why a config file rather than module constants
----------------------------------------------
Phase 2 output is evidence for an architecture decision. A reader has to be able to see
which numbers were chosen rather than measured, and re-run with different ones. A
weight buried in a function default is an unexamined modelling assumption; a weight in
a YAML file next to a comment saying it is not clinically validated is a stated one.

Defaults here duplicate the shipped YAML so that the loader still works if the file is
absent, and so that a missing key is filled with a documented value rather than a
``KeyError``.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final, Mapping

from .config import ConfigurationError

LOGGER: Final = logging.getLogger(__name__)

#: Feature dimensions that carry a weight in Hybrid C and in routing affinity.
WEIGHT_DIMENSIONS: Final[tuple[str, ...]] = (
    "graph",
    "symptom_discriminator",
    "snomed",
    "question",
    "disposition",
)

#: Community-detection methods this package knows how to run.
KNOWN_COMMUNITY_METHODS: Final[tuple[str, ...]] = (
    "louvain",
    "networkx_louvain",
    "leiden",
    "greedy_modularity",
    "label_propagation",
    "strongly_connected",
)


def _require_positive(value: float, name: str) -> float:
    """Return ``value`` if it is positive, else raise."""
    if value <= 0:
        raise ConfigurationError(f"{name} must be positive, got {value!r}.")
    return value


def _normalise_weights(weights: Mapping[str, float], *, label: str) -> dict[str, float]:
    """Validate a weight mapping and rescale it to sum to 1.

    Rescaling is applied so that a sensitivity variant can be written with whatever
    numbers read most clearly (``{graph: 1.0, ...: 0.0}``) without the resulting
    similarity scores changing scale between variants, which would make the
    similarity threshold mean different things in different runs.

    Args:
        weights: Mapping of dimension name to weight.
        label: Name used in error messages.

    Returns:
        Weights for every dimension in :data:`WEIGHT_DIMENSIONS`, summing to 1.

    Raises:
        ConfigurationError: On an unknown dimension, a negative weight, or an
            all-zero mapping.
    """
    unknown = set(weights) - set(WEIGHT_DIMENSIONS)
    if unknown:
        raise ConfigurationError(
            f"{label} contains unknown dimension(s) {sorted(unknown)}. "
            f"Known dimensions: {list(WEIGHT_DIMENSIONS)}."
        )
    resolved = {
        dimension: float(weights.get(dimension, 0.0)) for dimension in WEIGHT_DIMENSIONS
    }
    negative = [name for name, value in resolved.items() if value < 0]
    if negative:
        raise ConfigurationError(f"{label} has negative weight(s) for {negative}.")
    total = sum(resolved.values())
    if total <= 0:
        raise ConfigurationError(f"{label} weights sum to zero; at least one must be positive.")
    return {name: value / total for name, value in resolved.items()}


@dataclass(frozen=True)
class WeightVariant:
    """A named weighting used for Hybrid C sensitivity analysis."""

    name: str
    weights: dict[str, float]


@dataclass(frozen=True)
class FamilyDiscoveryConfig:
    """Resolved Phase 2 configuration.

    Attributes are grouped to mirror ``config/family_discovery.yaml``. Every numeric
    attribute is a modelling assumption, not a measurement.
    """

    source_path: Path | None = None

    # Scope
    pathway_scope: str = "active"

    # Community detection
    community_methods: tuple[str, ...] = KNOWN_COMMUNITY_METHODS
    primary_community_method: str = "louvain"
    leiden_resolution: float = 1.0

    # Family size
    minimum_family_size: int = 5
    split_review_size: int = 40
    minimum_split_part_size: int = 8

    # Overlap classification
    overlap_band_measure: str = "discriminating"
    overlap_moderate: float = 0.15
    overlap_high: float = 0.35
    shared_pathway_escalation: int = 1

    # Hybrid C
    hybrid_c_weights: dict[str, float] = field(
        default_factory=lambda: _normalise_weights(
            {
                "graph": 0.35,
                "symptom_discriminator": 0.20,
                "snomed": 0.15,
                "question": 0.20,
                "disposition": 0.10,
            },
            label="hybrid_c_weights",
        )
    )
    hybrid_c_similarity_threshold: float = 0.12
    hybrid_c_clustering_method: str = "louvain"
    hybrid_c_sensitivity: tuple[WeightVariant, ...] = ()

    # Hybrid A / B
    hybrid_a_clinical_cohesion_threshold: float = 0.20
    hybrid_a_split_feature: str = "symptom_group"
    hybrid_a_absorption_affinity_floor: float = 0.05
    hybrid_b_primary_grouping: str = "symptom_group_then_clinical_area"
    hybrid_b_weak_cohesion_internal_edge_pct: float = 25.0

    # Boundary classification
    boundary_strong_external_degree: int = 3
    boundary_hub_external_family_count: int = 3
    boundary_hub_betweenness_percentile: float = 90.0

    # Shared core
    shared_core_minimum_family_count: int = 5
    shared_core_bands: dict[str, int] = field(
        default_factory=lambda: {"family_specific": 1, "shared_2": 2, "shared_3_to_5": 5}
    )

    # Routing
    routing_weights: dict[str, float] = field(
        default_factory=lambda: _normalise_weights(
            {
                "graph": 0.35,
                "symptom_discriminator": 0.20,
                "snomed": 0.15,
                "question": 0.20,
                "disposition": 0.10,
            },
            label="routing.weights",
        )
    )
    routing_moderate_ambiguity: float = 0.40
    routing_high_ambiguity: float = 0.70
    routing_plausible_affinity_ratio: float = 0.60

    # Similarity export
    similarity_minimum_intersection: int = 1
    similarity_max_graph_hops: int = 2

    # Presentation
    primary_candidate_strategy: str = "hybrid_a"
    naming_dominance_threshold: float = 0.50
    representative_pathways: int = 6
    top_features: int = 8

    # Optional composite score
    composite_score_enabled: bool = False
    composite_score_weights: dict[str, float] = field(
        default_factory=lambda: {
            "graph_cohesion": 0.30,
            "symptom_discriminator_cohesion": 0.20,
            "snomed_cohesion": 0.10,
            "disposition_cohesion": 0.10,
            "boundary_simplicity": 0.15,
            "routing_clarity": 0.15,
        }
    )

    def describe(self) -> list[tuple[str, str]]:
        """Return the configuration as (setting, value) pairs for the evidence report."""
        return [
            ("pathway_scope", self.pathway_scope),
            ("community_detection.methods", ", ".join(self.community_methods)),
            ("community_detection.primary_method", self.primary_community_method),
            ("family_size.minimum_family_size", str(self.minimum_family_size)),
            ("family_size.split_review_size", str(self.split_review_size)),
            ("family_size.minimum_split_part_size", str(self.minimum_split_part_size)),
            ("overlap_thresholds.band_measure", self.overlap_band_measure),
            ("overlap_thresholds.moderate", f"{self.overlap_moderate:g}"),
            ("overlap_thresholds.high", f"{self.overlap_high:g}"),
            (
                "hybrid_c_weights",
                ", ".join(f"{k}={v:.3f}" for k, v in sorted(self.hybrid_c_weights.items())),
            ),
            ("hybrid_c.similarity_threshold", f"{self.hybrid_c_similarity_threshold:g}"),
            ("hybrid_c.clustering_method", self.hybrid_c_clustering_method),
            (
                "hybrid_c_sensitivity variants",
                ", ".join(variant.name for variant in self.hybrid_c_sensitivity) or "none",
            ),
            (
                "hybrid_a.clinical_cohesion_threshold",
                f"{self.hybrid_a_clinical_cohesion_threshold:g}",
            ),
            ("hybrid_a.split_feature", self.hybrid_a_split_feature),
            (
                "hybrid_b.weak_cohesion_internal_edge_pct",
                f"{self.hybrid_b_weak_cohesion_internal_edge_pct:g}",
            ),
            ("boundary.strong_external_degree", str(self.boundary_strong_external_degree)),
            (
                "boundary.hub_external_family_count",
                str(self.boundary_hub_external_family_count),
            ),
            (
                "boundary.hub_betweenness_percentile",
                f"{self.boundary_hub_betweenness_percentile:g}",
            ),
            ("shared_core.minimum_family_count", str(self.shared_core_minimum_family_count)),
            (
                "routing.weights",
                ", ".join(f"{k}={v:.3f}" for k, v in sorted(self.routing_weights.items())),
            ),
            ("routing.moderate_ambiguity", f"{self.routing_moderate_ambiguity:g}"),
            ("routing.high_ambiguity", f"{self.routing_high_ambiguity:g}"),
            (
                "routing.plausible_affinity_ratio",
                f"{self.routing_plausible_affinity_ratio:g}",
            ),
            ("similarity.max_graph_hops", str(self.similarity_max_graph_hops)),
            ("presentation.primary_candidate_strategy", self.primary_candidate_strategy),
            ("presentation.naming_dominance_threshold", f"{self.naming_dominance_threshold:g}"),
            ("composite_score.enabled", str(self.composite_score_enabled)),
        ]


def default_config_path(project_root: Path) -> Path:
    """Return the conventional location of the Phase 2 config file."""
    return project_root / "config" / "family_discovery.yaml"


def load_family_config(path: Path | None = None) -> FamilyDiscoveryConfig:
    """Load Phase 2 configuration from YAML.

    Args:
        path: Config file. When None, the shipped defaults are returned unchanged.

    Returns:
        A validated configuration.

    Raises:
        ConfigurationError: If the file is missing when explicitly requested, is not
            a YAML mapping, or contains an invalid threshold, weight or method name.
    """
    if path is None:
        LOGGER.info("No Phase 2 config file supplied; using built-in defaults.")
        return FamilyDiscoveryConfig(hybrid_c_sensitivity=_default_sensitivity())

    if not path.is_file():
        raise ConfigurationError(f"Phase 2 config file not found: {path}")

    try:
        import yaml
    except ImportError as exc:  # pragma: no cover - declared dependency
        raise ConfigurationError(
            "PyYAML is required to read config/family_discovery.yaml. "
            "Install the package dependencies and re-run."
        ) from exc

    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if raw is None:
        raw = {}
    if not isinstance(raw, dict):
        raise ConfigurationError(f"{path.name} must contain a YAML mapping at the top level.")

    return _from_mapping(raw, path)


def _default_sensitivity() -> tuple[WeightVariant, ...]:
    """Return the built-in Hybrid C sensitivity variants.

    These exist so that ``--config`` being absent still produces a sensitivity table:
    a single weighting with no sensitivity analysis would present an experimental
    baseline as if it were settled.
    """
    specs = {
        "graph_only": {"graph": 1.0},
        "features_only": {
            "symptom_discriminator": 0.30,
            "snomed": 0.25,
            "question": 0.30,
            "disposition": 0.15,
        },
        "equal": {dimension: 0.20 for dimension in WEIGHT_DIMENSIONS},
        "sd_heavy": {
            "graph": 0.20,
            "symptom_discriminator": 0.50,
            "snomed": 0.10,
            "question": 0.15,
            "disposition": 0.05,
        },
    }
    return tuple(
        WeightVariant(
            name=name,
            weights=_normalise_weights(weights, label=f"sensitivity.{name}"),
        )
        for name, weights in specs.items()
    )


def _section(raw: Mapping[str, Any], name: str) -> dict[str, Any]:
    """Return a mapping section, treating a missing or null section as empty."""
    value = raw.get(name) or {}
    if not isinstance(value, dict):
        raise ConfigurationError(f"Config section {name!r} must be a mapping.")
    return value


def _from_mapping(raw: Mapping[str, Any], path: Path) -> FamilyDiscoveryConfig:
    """Build a configuration from a parsed YAML mapping."""
    defaults = FamilyDiscoveryConfig()

    scope = _section(raw, "scope")
    detection = _section(raw, "community_detection")
    sizes = _section(raw, "family_size")
    overlap = _section(raw, "overlap_thresholds")
    hybrid_c = _section(raw, "hybrid_c")
    hybrid_a = _section(raw, "hybrid_a")
    hybrid_b = _section(raw, "hybrid_b")
    boundary = _section(raw, "boundary")
    shared_core = _section(raw, "shared_core")
    routing = _section(raw, "routing")
    similarity = _section(raw, "similarity")
    presentation = _section(raw, "presentation")
    composite = _section(raw, "composite_score")

    pathway_scope = str(scope.get("pathway_scope", defaults.pathway_scope))
    if pathway_scope not in {"active", "all"}:
        raise ConfigurationError(
            f"scope.pathway_scope must be 'active' or 'all', got {pathway_scope!r}."
        )

    methods = tuple(detection.get("methods") or defaults.community_methods)
    unknown_methods = set(methods) - set(KNOWN_COMMUNITY_METHODS)
    if unknown_methods:
        raise ConfigurationError(
            f"community_detection.methods contains unknown method(s) "
            f"{sorted(unknown_methods)}. Known: {list(KNOWN_COMMUNITY_METHODS)}."
        )
    if not methods:
        raise ConfigurationError("community_detection.methods must list at least one method.")

    primary_method = str(detection.get("primary_method", defaults.primary_community_method))
    if primary_method not in methods:
        raise ConfigurationError(
            f"community_detection.primary_method {primary_method!r} is not in the "
            f"configured method list {list(methods)}."
        )

    hybrid_c_weights = _normalise_weights(
        raw.get("hybrid_c_weights") or defaults.hybrid_c_weights,
        label="hybrid_c_weights",
    )
    routing_weights = _normalise_weights(
        routing.get("weights") or defaults.routing_weights,
        label="routing.weights",
    )

    sensitivity_raw = raw.get("hybrid_c_sensitivity")
    if sensitivity_raw is None:
        sensitivity = _default_sensitivity()
    else:
        if not isinstance(sensitivity_raw, list):
            raise ConfigurationError("hybrid_c_sensitivity must be a list of variants.")
        variants = []
        seen: set[str] = set()
        for entry in sensitivity_raw:
            if not isinstance(entry, dict) or "name" not in entry:
                raise ConfigurationError(
                    "Each hybrid_c_sensitivity entry must be a mapping with a 'name'."
                )
            name = str(entry["name"])
            if name in seen:
                raise ConfigurationError(f"Duplicate hybrid_c_sensitivity variant {name!r}.")
            seen.add(name)
            variants.append(
                WeightVariant(
                    name=name,
                    weights=_normalise_weights(
                        entry.get("weights") or {}, label=f"hybrid_c_sensitivity.{name}.weights"
                    ),
                )
            )
        sensitivity = tuple(variants)

    band_measure = str(overlap.get("band_measure", defaults.overlap_band_measure))
    if band_measure not in {"discriminating", "all_features"}:
        raise ConfigurationError(
            "overlap_thresholds.band_measure must be 'discriminating' or "
            f"'all_features', got {band_measure!r}."
        )
    overlap_moderate = float(overlap.get("moderate", defaults.overlap_moderate))
    overlap_high = float(overlap.get("high", defaults.overlap_high))
    if not 0 <= overlap_moderate <= overlap_high <= 1:
        raise ConfigurationError(
            "overlap_thresholds must satisfy 0 <= moderate <= high <= 1, got "
            f"moderate={overlap_moderate}, high={overlap_high}."
        )

    routing_moderate = float(
        routing.get("moderate_ambiguity", defaults.routing_moderate_ambiguity)
    )
    routing_high = float(routing.get("high_ambiguity", defaults.routing_high_ambiguity))
    if not 0 <= routing_moderate <= routing_high <= 1:
        raise ConfigurationError(
            "routing ambiguity thresholds must satisfy 0 <= moderate <= high <= 1, got "
            f"moderate={routing_moderate}, high={routing_high}."
        )

    split_feature = str(hybrid_a.get("split_feature", defaults.hybrid_a_split_feature))
    if split_feature not in {"symptom_group", "clinical_area"}:
        raise ConfigurationError(
            "hybrid_a.split_feature must be 'symptom_group' or 'clinical_area', got "
            f"{split_feature!r}."
        )

    clustering_method = str(
        hybrid_c.get("clustering_method", defaults.hybrid_c_clustering_method)
    )
    if clustering_method not in KNOWN_COMMUNITY_METHODS:
        raise ConfigurationError(
            f"hybrid_c.clustering_method {clustering_method!r} is not a known method."
        )

    config = FamilyDiscoveryConfig(
        source_path=path,
        pathway_scope=pathway_scope,
        community_methods=methods,
        primary_community_method=primary_method,
        leiden_resolution=_require_positive(
            float(detection.get("leiden_resolution", defaults.leiden_resolution)),
            "community_detection.leiden_resolution",
        ),
        minimum_family_size=int(sizes.get("minimum_family_size", defaults.minimum_family_size)),
        split_review_size=int(sizes.get("split_review_size", defaults.split_review_size)),
        minimum_split_part_size=int(
            sizes.get("minimum_split_part_size", defaults.minimum_split_part_size)
        ),
        overlap_band_measure=band_measure,
        overlap_moderate=overlap_moderate,
        overlap_high=overlap_high,
        shared_pathway_escalation=int(
            overlap.get("shared_pathway_escalation", defaults.shared_pathway_escalation)
        ),
        hybrid_c_weights=hybrid_c_weights,
        hybrid_c_similarity_threshold=float(
            hybrid_c.get("similarity_threshold", defaults.hybrid_c_similarity_threshold)
        ),
        hybrid_c_clustering_method=clustering_method,
        hybrid_c_sensitivity=sensitivity,
        hybrid_a_clinical_cohesion_threshold=float(
            hybrid_a.get(
                "clinical_cohesion_threshold", defaults.hybrid_a_clinical_cohesion_threshold
            )
        ),
        hybrid_a_split_feature=split_feature,
        hybrid_a_absorption_affinity_floor=float(
            hybrid_a.get(
                "absorption_affinity_floor", defaults.hybrid_a_absorption_affinity_floor
            )
        ),
        hybrid_b_primary_grouping=str(
            hybrid_b.get("primary_grouping", defaults.hybrid_b_primary_grouping)
        ),
        hybrid_b_weak_cohesion_internal_edge_pct=float(
            hybrid_b.get(
                "weak_cohesion_internal_edge_pct",
                defaults.hybrid_b_weak_cohesion_internal_edge_pct,
            )
        ),
        boundary_strong_external_degree=int(
            boundary.get("strong_external_degree", defaults.boundary_strong_external_degree)
        ),
        boundary_hub_external_family_count=int(
            boundary.get(
                "hub_external_family_count", defaults.boundary_hub_external_family_count
            )
        ),
        boundary_hub_betweenness_percentile=float(
            boundary.get(
                "hub_betweenness_percentile", defaults.boundary_hub_betweenness_percentile
            )
        ),
        shared_core_minimum_family_count=int(
            shared_core.get("minimum_family_count", defaults.shared_core_minimum_family_count)
        ),
        shared_core_bands={
            **defaults.shared_core_bands,
            **(shared_core.get("family_count_bands") or {}),
        },
        routing_weights=routing_weights,
        routing_moderate_ambiguity=routing_moderate,
        routing_high_ambiguity=routing_high,
        routing_plausible_affinity_ratio=float(
            routing.get("plausible_affinity_ratio", defaults.routing_plausible_affinity_ratio)
        ),
        similarity_minimum_intersection=int(
            similarity.get("minimum_intersection", defaults.similarity_minimum_intersection)
        ),
        similarity_max_graph_hops=int(
            similarity.get("max_graph_hops", defaults.similarity_max_graph_hops)
        ),
        primary_candidate_strategy=str(
            presentation.get("primary_candidate_strategy", defaults.primary_candidate_strategy)
        ),
        naming_dominance_threshold=float(
            presentation.get("naming_dominance_threshold", defaults.naming_dominance_threshold)
        ),
        representative_pathways=int(
            presentation.get("representative_pathways", defaults.representative_pathways)
        ),
        top_features=int(presentation.get("top_features", defaults.top_features)),
        composite_score_enabled=bool(
            composite.get("enabled", defaults.composite_score_enabled)
        ),
        composite_score_weights={
            **defaults.composite_score_weights,
            **(composite.get("weights") or {}),
        },
    )

    if config.minimum_family_size < 1:
        raise ConfigurationError("family_size.minimum_family_size must be at least 1.")
    if config.minimum_split_part_size < 1:
        raise ConfigurationError("family_size.minimum_split_part_size must be at least 1.")
    if not 0 < config.naming_dominance_threshold <= 1:
        raise ConfigurationError(
            "presentation.naming_dominance_threshold must be in (0, 1]."
        )
    LOGGER.info("Loaded Phase 2 configuration from %s", path)
    return config
