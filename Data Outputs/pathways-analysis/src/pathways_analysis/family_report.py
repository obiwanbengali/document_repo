"""Phase 2 narrative outputs: the evidence report and the clinical review pack.

Sections 20 and 23 of the Phase 2 brief.

Evidence classes
----------------
Both documents label every statement with one of five classes, and the labelling is
mechanical rather than editorial:

* **measured** -- a count read from the database.
* **derived** -- computed by this workbench from measured values under a stated
  definition.
* **algorithmic** -- produced by a community-detection or clustering algorithm. True of
  the algorithm and the graph; not a clinical claim.
* **assumption** -- a configured threshold, weight or scope choice that could
  reasonably have been made differently.
* **interpretation** -- a reading of the evidence. Kept to the minimum and always
  attributed as such, never stated as fact.

**No architectural recommendation appears in either document.** Monolithic versus
federated is a Phase 3 comparison; Phase 2 produces the family evidence it would need.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final, Mapping, Sequence

import pandas as pd

from .family_config import FamilyDiscoveryConfig
from .family_features import (
    CandidateFamilySet,
    PairwiseSimilarity,
    PathwayFeatureModel,
)

LOGGER: Final = logging.getLogger(__name__)

#: Legend written into both documents.
EVIDENCE_LEGEND: Final[tuple[tuple[str, str], ...]] = (
    ("measured", "a count read directly from TriageDB"),
    (
        "derived",
        "computed by this workbench from measured values, under the definition stated "
        "in `outputs/phase2/reports/metric_definitions.csv`",
    ),
    (
        "algorithmic",
        "produced by a community-detection or clustering algorithm: true of the "
        "algorithm and the transfer graph, and **not** a clinical statement",
    ),
    (
        "assumption",
        "a configured threshold, weight or scope choice that could reasonably have "
        "been made differently; every one is in `config/family_discovery.yaml`",
    ),
    ("interpretation", "a reading of the evidence, attributed as such"),
)


@dataclass
class ReportInputs:
    """Everything the Phase 2 documents are written from.

    Held as a dataclass so the report functions cannot quietly recompute anything: they
    render tables the runner has already written, which is what keeps the documents and
    the CSVs consistent.
    """

    config: FamilyDiscoveryConfig
    model: PathwayFeatureModel
    similarity: PairwiseSimilarity
    tables: dict[str, pd.DataFrame]
    primary: CandidateFamilySet
    primary_names: dict[str, str]
    candidate_sets: list[CandidateFamilySet]
    community_methods_unavailable: dict[str, str]
    edge_crosscheck: dict[str, object]
    inventory: dict[str, int] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)
    generated: str = ""
    strategies_in_battery: list[str] = field(default_factory=list)
    strategies_excluded: dict[str, str] = field(default_factory=dict)

    def table(self, name: str) -> pd.DataFrame:
        """Return a table by name, or an empty frame if it was not produced."""
        return self.tables.get(name, pd.DataFrame())

    def primary_rows(self, name: str) -> pd.DataFrame:
        """Return the rows of a table belonging to the primary candidate strategy."""
        frame = self.table(name)
        if frame.empty or "strategy" not in frame.columns:
            return frame
        return frame.loc[frame["strategy"] == self.primary.strategy]


def _tag(evidence_class: str, text: str) -> str:
    """Render one labelled bullet."""
    return f"- **[{evidence_class}]** {text}"


def _plural(count: int, singular: str, plural: str) -> str:
    """Return the singular or plural form for a count."""
    return singular if count == 1 else plural


def _percentage(numerator: float, denominator: float) -> str:
    """Format a percentage, guarding against a zero denominator."""
    if not denominator:
        return "n/a"
    return f"{100.0 * numerator / denominator:.1f}%"


def _markdown_table(frame: pd.DataFrame, columns: Sequence[tuple[str, str]]) -> list[str]:
    """Render selected columns of a frame as a Markdown table.

    Args:
        frame: Source rows, already ordered and truncated by the caller.
        columns: ``(column_name, header)`` pairs.

    Returns:
        Markdown lines, or a single "no rows" line.
    """
    available = [(name, header) for name, header in columns if name in frame.columns]
    if frame.empty or not available:
        return ["_No rows._", ""]
    lines = [
        "| " + " | ".join(header for _, header in available) + " |",
        "|" + "|".join("---" for _ in available) + "|",
    ]
    for row in frame.itertuples():
        cells = []
        for name, _ in available:
            value = getattr(row, name, "")
            if isinstance(value, float):
                cells.append(
                    "n/a"
                    if pd.isna(value)
                    else f"{value:,.3f}".rstrip("0").rstrip(".")
                )
            elif isinstance(value, bool):
                cells.append("yes" if value else "no")
            else:
                cells.append(str(value).replace("|", "/"))
        lines.append("| " + " | ".join(cells) + " |")
    lines.append("")
    return lines


# ======================================================================================
# Evidence report (section 20)
# ======================================================================================
def write_evidence_report(inputs: ReportInputs, path: Path) -> Path:
    """Write ``outputs/phase2/family_discovery_report.md``."""
    lines: list[str] = []

    lines += [
        "# NHS Pathways Bayesian Family Discovery — Phase 2 Evidence Report",
        "",
        f"Generated {inputs.generated} from a read-only extract of the local SQL Server "
        "`TriageDB` snapshot.",
        "",
        "## How to read this report",
        "",
        "Every statement carries an evidence class:",
        "",
    ]
    lines += [f"- **{name}** — {meaning}" for name, meaning in EVIDENCE_LEGEND]
    lines += [
        "",
        "> **Scope boundary.** Phase 2 answers *what clinically and structurally "
        "coherent Bayesian Network families could be created, how much they overlap, "
        "and what shared structures they would need*. It does **not** size a network, "
        "estimate infrastructure or cost, or compare monolithic against federated. "
        "Those are Phase 3.",
        "",
        "> **No candidate family in this report is clinically endorsed.** A grouping "
        "produced by an algorithm is a structural candidate until a clinician has "
        "reviewed it. `outputs/phase2/clinical_review_pack.md` is the artefact for that "
        "review.",
        "",
    ]

    lines += _section_purpose(inputs)
    lines += _section_dataset_basis(inputs)
    lines += _section_methods(inputs)
    lines += _section_native(inputs)
    lines += _section_graph(inputs)
    lines += _section_feature_overlap(inputs)
    lines += _section_hybrid(inputs)
    lines += _section_candidate_set(inputs)
    lines += _section_overlap_boundaries(inputs)
    lines += _section_shared_core(inputs)
    lines += _section_merge_split(inputs)
    lines += _section_routing(inputs)
    lines += _section_age_trauma(inputs)
    lines += _section_limitations(inputs)
    lines += _section_clinical_questions(inputs)
    lines += _section_phase3(inputs)
    lines += _section_configuration(inputs)
    lines += _section_artefacts(inputs)

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")
    LOGGER.info("Wrote %s", path.name)
    return path


def _section_purpose(inputs: ReportInputs) -> list[str]:
    """Section 1: purpose."""
    return [
        "## 1. Purpose",
        "",
        "To establish, from measured structure, which groupings of NHS Pathways could "
        "form coherent Bayesian Network families; how much those groupings overlap; and "
        "which questions, symptom discriminators, SNOMED concepts and dispositions "
        "would have to be shared between them.",
        "",
        "Three kinds of candidate grouping are generated independently and then "
        "compared, rather than one being assumed:",
        "",
        "1. **NHS-native** groupings that already exist in the data (symptom group, "
        "clinical area, area group, trauma, age, gender, module).",
        "2. **Graph-derived** communities of the pathway-to-pathway transfer graph.",
        "3. **Hybrid** proposals that combine the two under declared rules.",
        "",
        _tag(
            "assumption",
            "Generating candidates three ways is itself a design choice: it exists so "
            "that agreement between independent methods is available as evidence, and "
            "so no single algorithm's output is mistaken for the answer.",
        ),
        "",
    ]


def _section_dataset_basis(inputs: ReportInputs) -> list[str]:
    """Section 2: dataset basis."""
    model = inputs.model
    coverage = model.metadata_coverage
    lines = [
        "## 2. Dataset basis",
        "",
        _tag(
            "measured",
            f"Family-membership scope: **{len(model.scope):,} pathways** "
            f"(`scope.pathway_scope = {inputs.config.pathway_scope}`, which means "
            "`IsArchived = 0 AND FlagForDeletion = 0`, the Phase 1 definition).",
        ),
        _tag(
            "measured",
            f"Transfer graph: **{model.pathway_graph.number_of_nodes():,} nodes** and "
            f"**{model.pathway_graph.number_of_edges():,} directed edges**. The graph "
            "spans every active pathway plus any pathway taking part in a resolved "
            "transfer, so it is wider than the membership scope.",
        ),
        _tag(
            "assumption",
            "An edge from an in-scope pathway to an out-of-scope one is counted as "
            "**external** to whichever family holds the source, not dropped. Dropping "
            "it would inflate every internal-edge percentage.",
        ),
    ]

    crosscheck = inputs.edge_crosscheck
    if crosscheck:
        status = "agree" if crosscheck.get("matches") else "DIVERGE"
        lines.append(
            _tag(
                "measured",
                f"Edge-list cross-check: the Python derivation and the independent "
                f"server-side derivation (`sql/11_family_transitions.sql`) **{status}** "
                f"— {crosscheck.get('python_edges', 0):,} vs "
                f"{crosscheck.get('sql_edges', 0):,} edges, "
                f"{crosscheck.get('python_transitions', 0):,} vs "
                f"{crosscheck.get('sql_transitions', 0):,} transitions.",
            )
        )

    lines += ["", "### Metadata available for grouping", ""]
    lines += _markdown_table(
        coverage,
        [
            ("field", "Field"),
            ("pathways_populated", "Pathways populated"),
            ("pathways_missing", "Missing"),
            ("coverage_percentage", "Coverage %"),
            ("distinct_values", "Distinct values"),
            ("usable_as_grouping", "Can separate"),
        ],
    )
    lines += [
        "",
        _tag(
            "assumption",
            "**Can separate** means the field has at least two distinct values, so a "
            "grouping built on it would produce more than one family. It is a "
            "mechanical test and not a judgement of usefulness: `Party` passes it on "
            "12 of 815 pathways, which is not enough to group anything.",
        ),
        "",
    ]
    lines += [
        _tag(
            "measured",
            "`Module` is NULL for every row of `tblPathways` in this snapshot and "
            "`Party` for almost every row, so neither can separate pathways. Both are "
            "still attempted and reported as unusable rather than omitted.",
        ),
        _tag(
            "measured",
            "Age, gender and trauma metadata **do** exist, in `tblPathway2Ages`, "
            "`tblPathway2Genders` and `tblPathway2Trauma`. Phase 1 did not use them. "
            "All three are many-to-many, so none of them is a partition.",
        ),
        "",
    ]
    return lines


def _section_methods(inputs: ReportInputs) -> list[str]:
    """Section 3: family discovery methods."""
    lines = [
        "## 3. Family discovery methods",
        "",
        "### Candidate strategies generated",
        "",
    ]
    rows = pd.DataFrame(
        [
            {
                "strategy": candidate.strategy,
                "basis": candidate.basis,
                "families": len(candidate.family_ids),
                "pathways_assigned": candidate.pathway_count,
                "overlapping": candidate.overlapping,
                "description": candidate.description,
            }
            for candidate in inputs.candidate_sets
        ]
    )
    lines += _markdown_table(
        rows,
        [
            ("strategy", "Strategy"),
            ("basis", "Basis"),
            ("families", "Families"),
            ("pathways_assigned", "Pathways"),
            ("overlapping", "Overlapping"),
            ("description", "How it was produced"),
        ],
    )
    lines += [
        _tag(
            "assumption",
            "A pathway is **not** assumed to belong to exactly one family. Membership "
            "is held long-format, so an overlapping strategy (clinical area, area "
            "group, trauma, age, gender) places a pathway in every family it qualifies "
            "for, and `candidate_family_membership.csv` allows several rows per pathway.",
        ),
    ]
    if inputs.strategies_excluded:
        lines.append(
            _tag(
                "assumption",
                "Excluded from the full metric battery: "
                + "; ".join(
                    f"`{strategy}` ({reason})"
                    for strategy, reason in sorted(inputs.strategies_excluded.items())
                )
                + ".",
            )
        )
    lines.append("")
    return lines


def _section_native(inputs: ReportInputs) -> list[str]:
    """Section 4: NHS-native grouping findings."""
    native = inputs.table("native_group_candidates")
    comparison = inputs.table("family_strategy_comparison")
    lines = ["## 4. NHS-native grouping findings", ""]
    if native.empty:
        return lines + ["_Not produced._", ""]

    native_comparison = (
        comparison.loc[comparison["FamilyBasis"] == "nhs_native"]
        if not comparison.empty else pd.DataFrame()
    )
    lines += _markdown_table(
        native_comparison,
        [
            ("strategy", "Grouping"),
            ("FamilyCount", "Groups"),
            ("MedianFamilySize", "Median size"),
            ("MaxFamilySize", "Max size"),
            ("MedianInternalEdgePercentage", "Median internal-edge %"),
            ("MedianBoundaryPathwayPercentage", "Median boundary %"),
            ("MeanPairwiseSdJaccard", "Mean SD Jaccard"),
        ],
    )

    for strategy, group in native.groupby("strategy"):
        internal = group["internal_edge_percentage"].dropna()
        group_count = int(group["family_id"].nunique())
        if internal.empty or group_count < 2:
            # A grouping with one group has no cohesion question to answer; the note
            # below records why it is unusable.
            continue
        self_contained = int((internal >= 50).sum())
        outward = int((internal == 0).sum())
        lines.append(
            _tag(
                "derived",
                f"`{strategy}`: **{group_count}** groups; median internal-edge share "
                f"**{internal.median():.1f}%**. Groups keeping at least half their "
                f"edges inside the group: {self_contained}; keeping none: {outward}.",
            )
        )
    # Only the NHS-native sets' notes belong in this section. Graph and hybrid notes
    # are reported in sections 5 and 7 respectively.
    for candidate in inputs.candidate_sets:
        if candidate.basis != "nhs_native":
            continue
        for note in candidate.notes:
            lines.append(_tag("measured", f"`{candidate.strategy}`: {note}"))
    lines.append("")
    return lines


def _section_graph(inputs: ReportInputs) -> list[str]:
    """Section 5: graph-derived community findings."""
    methods = inputs.table("community_method_comparison")
    lines = ["## 5. Graph-derived community findings", ""]
    if methods.empty:
        return lines + ["_Not produced._", ""]

    lines += _markdown_table(
        methods,
        [
            ("method", "Method"),
            ("available", "Ran"),
            ("community_count", "Communities"),
            ("modularity", "Modularity"),
            ("largest_community_size", "Largest"),
            ("singleton_communities", "Singletons"),
            ("median_internal_edge_percentage", "Median internal-edge %"),
            ("adjusted_rand_index_vs_primary", "ARI vs primary"),
        ],
    )
    lines += [
        _tag(
            "algorithmic",
            "These are **graph-derived communities**: a property of the transfer "
            "topology only. None is a clinical family, and none carries clinical "
            "endorsement.",
        ),
        _tag(
            "assumption",
            f"`{inputs.config.primary_community_method}` is used as the graph-derived "
            "input to Hybrid A and as the graph-derived representative in strategy "
            "comparison. That is a configured choice, not a finding that it is best.",
        ),
    ]
    for candidate in inputs.candidate_sets:
        if candidate.basis != "graph_derived":
            continue
        for note in candidate.notes:
            if "renumbered largest-first" in note:
                continue  # a presentation detail, not a finding
            lines.append(_tag("measured", f"`{candidate.strategy}`: {note}"))
    if inputs.community_methods_unavailable:
        lines.append(
            _tag(
                "measured",
                "Methods that could not run: "
                + "; ".join(
                    f"`{method}` ({reason})"
                    for method, reason in sorted(inputs.community_methods_unavailable.items())
                )
                + ".",
            )
        )
    agreement = methods.loc[methods["adjusted_rand_index_vs_primary"].notna()]
    if not agreement.empty:
        others = agreement.loc[agreement["method"] != inputs.config.primary_community_method]
        if not others.empty:
            lines.append(
                _tag(
                    "derived",
                    "Agreement between methods (adjusted Rand index against "
                    f"`{inputs.config.primary_community_method}`) ranges from "
                    f"**{others['adjusted_rand_index_vs_primary'].min():.3f}** to "
                    f"**{others['adjusted_rand_index_vs_primary'].max():.3f}**. "
                    "High agreement means the community structure is a property of the "
                    "graph rather than of one algorithm's objective function.",
                )
            )
    composition = inputs.table("graph_community_summary")
    if not composition.empty and "dominant_symptom_group_share" in composition.columns:
        primary_rows = composition.loc[
            composition["algorithm"] == inputs.config.primary_community_method
        ]
        if not primary_rows.empty:
            lines.append(
                _tag(
                    "derived",
                    "For the primary method, the mean dominant-symptom-group share "
                    f"within a community is "
                    f"**{primary_rows['dominant_symptom_group_share'].mean():.2f}** and "
                    "the mean dominant-clinical-area share is "
                    f"**{primary_rows['dominant_clinical_area_share'].mean():.2f}** — "
                    "the extent to which graph communities already track NHS metadata.",
                )
            )
    lines.append("")
    return lines


def _section_feature_overlap(inputs: ReportInputs) -> list[str]:
    """Section 6: clinical-feature overlap findings."""
    lines = ["## 6. Clinical-feature overlap findings", ""]
    summary = inputs.table("pathway_similarity_summary")
    if not summary.empty:
        lines += _markdown_table(
            summary,
            [
                ("dimension", "Evidence dimension"),
                ("pathways_with_any_feature", "Pathways"),
                ("overlapping_pairs", "Overlapping pairs"),
                ("possible_pairs", "Possible pairs"),
                ("percentage_of_pairs_overlapping", "% of pairs"),
                ("median_jaccard", "Median Jaccard"),
                ("pairs_at_or_above_0_5", "Pairs ≥ 0.50"),
            ],
        )
    lines += [
        _tag(
            "assumption",
            "The six evidence dimensions are kept **separate**. They are combined only "
            "by Hybrid C, under weights in `hybrid_c_weights`, and the sensitivity "
            "table reports what those weights change.",
        ),
        _tag(
            "derived",
            "Symptom-discriminator overlap is the densest signal and SNOMED the "
            "sparsest, so a family set built on SNOMED alone would rest on much thinner "
            "evidence than one built on symptom discriminators.",
        ),
        _tag(
            "derived",
            "**Disposition overlap is high by construction and discriminates poorly.** "
            "The estate has under 200 distinct disposition codes and most families "
            "reach a similar subset of them, so disposition Jaccard is the highest "
            "median of any dimension and is the reported driver for most high-overlap "
            "family pairs. Two families sharing dispositions is close to saying both "
            "can end in an ambulance or a primary-care referral. It is kept as a "
            "dimension because a family's outcome set matters for Phase 3 sizing, but "
            "it should carry little weight in judging whether two families are the same "
            "clinical area.",
        ),
        "",
    ]
    return lines


def _section_hybrid(inputs: ReportInputs) -> list[str]:
    """Section 7: hybrid grouping findings."""
    hybrids = inputs.table("hybrid_family_candidates")
    sensitivity = inputs.table("hybrid_family_sensitivity")
    lines = ["## 7. Hybrid grouping findings", ""]
    if not hybrids.empty:
        summary = (
            hybrids.groupby(["strategy", "hybrid_rule"])
            .agg(
                families=("family_id", "nunique"),
                pathways=("pathway_key", "nunique"),
            )
            .reset_index()
        )
        lines += _markdown_table(
            summary,
            [
                ("strategy", "Strategy"),
                ("hybrid_rule", "Rule applied"),
                ("families", "Families"),
                ("pathways", "Pathways"),
            ],
        )
    lines += [
        _tag(
            "assumption",
            "**Hybrid A** takes graph communities as the primary grouping and refines "
            "them with clinical features: a community whose mean pairwise "
            "symptom-discriminator Jaccard falls below "
            f"`{inputs.config.hybrid_a_clinical_cohesion_threshold}` is split by "
            f"`{inputs.config.hybrid_a_split_feature}`, and a community below "
            f"`{inputs.config.minimum_family_size}` pathways is absorbed into its "
            "highest-affinity neighbour.",
        ),
        _tag(
            "assumption",
            "**Hybrid B** takes the NHS-native grouping as primary (symptom group where "
            "present, otherwise the pathway's most specific clinical area) and splits a "
            "group whose internal-edge percentage falls below "
            f"`{inputs.config.hybrid_b_weak_cohesion_internal_edge_pct}`%.",
        ),
        _tag(
            "assumption",
            "**Hybrid C** clusters a weighted combination of all evidence dimensions. "
            "The default weighting is an **experimental baseline and is not clinically "
            "validated**: "
            + ", ".join(
                f"`{key}`={value:.2f}"
                for key, value in sorted(inputs.config.hybrid_c_weights.items())
            )
            + ".",
        ),
    ]
    for candidate in inputs.candidate_sets:
        if candidate.basis != "hybrid":
            continue
        for note in candidate.notes:
            lines.append(_tag("measured", f"`{candidate.strategy}`: {note}"))
    if not sensitivity.empty:
        lines += ["", "### Hybrid C sensitivity to the weighting", ""]
        lines += _markdown_table(
            sensitivity,
            [
                ("variant", "Weight variant"),
                ("family_count", "Families"),
                ("median_family_size", "Median size"),
                ("largest_family_size", "Largest"),
                ("adjusted_rand_index_vs_default", "ARI vs default"),
                ("membership_changed_percentage", "% membership changed"),
                ("weights", "Weights"),
            ],
        )
        worst = sensitivity.loc[sensitivity["adjusted_rand_index_vs_default"].idxmin()]
        lines.append(
            _tag(
                "derived",
                f"The weighting **does** change the answer: variant "
                f"`{worst['variant']}` agrees with the default at an adjusted Rand "
                f"index of only **{worst['adjusted_rand_index_vs_default']:.3f}**, with "
                f"**{worst['membership_changed_percentage']:.1f}%** of pathways landing "
                "in a different family. Hybrid C must therefore be read as one "
                "weighting's output, not as a stable family set.",
            )
        )
    lines.append("")
    return lines


def _section_candidate_set(inputs: ReportInputs) -> list[str]:
    """Section 8: the candidate family set."""
    candidates = inputs.table("candidate_bayesian_families")
    lines = [
        "## 8. Candidate family set",
        "",
        _tag(
            "assumption",
            f"The set presented for review is `{inputs.primary.strategy}` "
            "(`presentation.primary_candidate_strategy`). This is a **modelling "
            "choice**, made because it is the only strategy that starts from measured "
            "graph cohesion and then requires clinical-feature support before a group "
            "is kept — not a finding that it is the right family set. Every strategy is "
            "compared in `family_strategy_comparison.csv`.",
        ),
        "",
    ]
    if candidates.empty:
        return lines + ["_Not produced._", ""]

    lines += _markdown_table(
        candidates.head(40),
        [
            ("FamilyId", "Family"),
            ("FamilyName", "Name"),
            ("PathwayCount", "Pathways"),
            ("InternalEdgePercentage", "Internal-edge %"),
            ("UniqueQuestions", "Questions"),
            ("UniqueSDs", "SDs"),
            ("BoundaryPathwayCount", "Boundary pathways"),
            ("ConfidenceInStructuralCohesion", "Structural cohesion"),
            ("ClinicalReviewRequired", "Review needed"),
        ],
    )
    named = (
        int((candidates["FamilyNameBasis"] != "neutral").sum())
        if "FamilyNameBasis" in candidates
        else 0
    )
    lines += [
        _tag(
            "derived",
            f"**{len(candidates)}** candidate families covering "
            f"**{int(candidates['PathwayCount'].sum()):,}** pathway memberships; "
            f"median size **{candidates['PathwayCount'].median():.0f}**, largest "
            f"**{int(candidates['PathwayCount'].max())}**.",
        ),
        _tag(
            "derived",
            f"**{named}** of {len(candidates)} families could be given a name derived "
            "from dominant NHS metadata at the configured dominance threshold of "
            f"{inputs.config.naming_dominance_threshold:.0%}. The rest keep a neutral "
            "`Community_NN` name, with their dominant symptom groups and clinical areas "
            "reported separately. A name was never invented for a community that does "
            "not have one.",
        ),
        _tag(
            "interpretation",
            "A neutral name is a finding in itself: it marks a group that is cohesive "
            "in the transfer graph but does not correspond to a single NHS grouping, "
            "which is precisely where clinical judgement is needed.",
        ),
        "",
    ]
    return lines


def _section_overlap_boundaries(inputs: ReportInputs) -> list[str]:
    """Section 9: overlap and boundary areas."""
    overlap = inputs.primary_rows("family_overlap_matrix")
    high = inputs.primary_rows("high_overlap_family_pairs")
    boundary_summary = inputs.table("boundary_pathway_summary")
    lines = ["## 9. Overlap and boundary areas", ""]

    if not overlap.empty:
        bands = (
            overlap["OverlapBand"].value_counts()
            if "OverlapBand" in overlap
            else pd.Series(dtype=int)
        )
        measure = (
            "the largest of the question, symptom-discriminator and SNOMED Jaccard "
            "values (`band_measure: discriminating`, which excludes dispositions "
            "because they overlap by construction)"
            if inputs.config.overlap_band_measure == "discriminating"
            else "the largest of the four feature Jaccard values, dispositions included "
            "(`band_measure: all_features`)"
        )
        lines += [
            _tag(
                "derived",
                f"Within the presented family set, **{len(overlap):,}** family pairs "
                "share at least one feature, pathway or transition: "
                + ", ".join(f"{int(count)} {band}" for band, count in bands.items())
                + f". Bands use `overlap_thresholds` (moderate "
                f"{inputs.config.overlap_moderate}, high {inputs.config.overlap_high}) "
                f"applied to {measure}.",
            ),
        ]
    if not high.empty:
        lines += ["", "### Highest-overlap family pairs", ""]
        lines += _markdown_table(
            high.head(15),
            [
                ("FamilyA", "A"),
                ("FamilyB", "B"),
                ("PathwayCountA", "A size"),
                ("PathwayCountB", "B size"),
                ("BandMeasureJaccard", "Band Jaccard"),
                ("SharedPathways", "Shared pathways"),
                ("OverlapDriver", "Driver"),
                ("WhyTheyOverlap", "Why"),
            ],
        )
        trivial = (
            int((high["SmallerFamilyPathwayCount"] <= 2).sum())
            if "SmallerFamilyPathwayCount" in high.columns
            else 0
        )
        if trivial:
            lines.append(
                _tag(
                    "derived",
                    f"{trivial} of the {len(high)} high-overlap pairs involve a family "
                    "of at most two pathways. Jaccard is scale-free, so two "
                    "one-pathway families that share all three of their questions "
                    "score 1.0: arithmetically correct and analytically trivial. The "
                    "table is therefore ordered by the smaller family's size first, "
                    "and `SmallerFamilyPathwayCount` is carried in the CSV so the "
                    "trivial pairs can be filtered out.",
                )
            )
        lines.append(
            _tag(
                "assumption",
                "High overlap is **not** a merge instruction. Two families sharing a "
                "large symptom-discriminator vocabulary may be one clinical area split "
                "by routing, or two distinct areas sharing screening questions. "
                "Structure cannot tell them apart.",
            )
        )

    if not boundary_summary.empty:
        primary_summary = boundary_summary.loc[
            boundary_summary["strategy"] == inputs.primary.strategy
        ]
        if not primary_summary.empty:
            row = primary_summary.iloc[0]
            lines += [
                "",
                _tag(
                    "derived",
                    f"Boundary pathways in the presented set: "
                    f"**{int(row['BoundaryPathwayCount'])}** of "
                    f"{int(row['PathwaysClassified'])} "
                    f"({row['BoundaryPathwayPercentage']:.1f}%) have at least one edge "
                    "to a pathway outside their family — "
                    f"{int(row.get('count_weak_boundary_pathway', 0))} weak, "
                    f"{int(row.get('count_strong_boundary_pathway', 0))} strong, "
                    f"{int(row.get('count_cross_family_hub', 0))} cross-family hubs.",
                ),
                _tag(
                    "assumption",
                    "The boundary classification is **structural only**. "
                    "'Cross-family hub' means a pathway has edges to several candidate "
                    "families and high betweenness. It makes no claim that the pathway "
                    "is clinically central or wrongly placed.",
                ),
            ]
    lines.append("")
    return lines


def _section_shared_core(inputs: ReportInputs) -> list[str]:
    """Section 10: shared-core candidates."""
    core = inputs.table("shared_core_candidates")
    summary = inputs.table("shared_feature_summary")
    lines = ["## 10. Shared-core candidates", ""]
    if not summary.empty:
        lines += _markdown_table(
            summary,
            [
                ("FeatureTypeLabel", "Feature type"),
                ("FeaturesTotal", "Features"),
                ("FamilySpecific", "1 family"),
                ("SharedBy2Families", "2 families"),
                ("SharedBy3To5Families", "3-5 families"),
                ("BroadlyShared", "6+ families"),
                ("SharedCoreCandidates", "Shared-core candidates"),
                ("TotalDuplicationIfFederated", "Duplicate copies implied"),
            ],
        )
    if not core.empty:
        lines += [
            _tag(
                "derived",
                f"**{len(core):,}** features are used by at least "
                f"{inputs.config.shared_core_minimum_family_count} candidate families "
                f"and are flagged as shared-core candidates. Together they imply "
                f"**{int(core['DuplicationIfFederated'].sum()):,}** duplicate copies if "
                "every family held its own — a structural count, not a sizing estimate.",
            ),
            _tag(
                "assumption",
                "Flagging a feature here does **not** conclude that it belongs in a "
                "shared Bayesian Network. A broadly shared question may be one clinical "
                "concept used everywhere, several distinct concepts sharing wording, or "
                "an artefact of how Pathways is authored. Structure alone cannot "
                "separate those readings.",
            ),
            "",
            "### Most broadly shared features",
            "",
        ]
        lines += _markdown_table(
            core.nlargest(15, ["FamilyCount", "PathwayCount"]),
            [
                ("FeatureTypeLabel", "Type"),
                ("FeatureId", "Id"),
                ("Description", "Description"),
                ("FamilyCount", "Families"),
                ("PathwayCount", "Pathways"),
                ("TotalOccurrences", "Occurrences"),
                ("UsedByCrossFamilyPathway", "On a boundary pathway"),
            ],
        )
    lines.append("")
    return lines


def _section_merge_split(inputs: ReportInputs) -> list[str]:
    """Section 11: potential merge and split areas."""
    merges = inputs.primary_rows("family_merge_candidates")
    splits = inputs.primary_rows("family_split_candidates")
    lines = ["## 11. Potential merge and split areas", ""]

    if merges.empty:
        lines.append(
            _tag(
                "derived",
                "No high-overlap family pairs in the presented set, so no merge was "
                "tested.",
            )
        )
    else:
        sd_improving = (
            merges.loc[merges["MeanPairwiseSdJaccardDelta"] > 0]
            if "MeanPairwiseSdJaccardDelta" in merges.columns
            else merges.iloc[0:0]
        )
        lines += [
            _tag(
                "derived",
                f"**{len(merges)}** high-overlap pairs were merged hypothetically and "
                f"re-measured. **{len(sd_improving)}** would raise the size-weighted "
                "mean pairwise symptom-discriminator Jaccard.",
            ),
            _tag(
                "assumption",
                "**The internal-edge percentage cannot be used to judge a merge.** "
                "Every edge that ran between the two families becomes internal to the "
                "union, so merging can only raise it. It is reported because the size "
                "of the gain separates a pair that genuinely interacts from one that "
                "barely does, but the discriminating signal is the shared-symptom-"
                "discriminator change, which has no such bias: it falls when a merge "
                "combines pathways that route together without being clinically alike.",
            ),
            "",
        ]
        lines += _markdown_table(
            merges.head(10),
            [
                ("FamilyA", "A"),
                ("FamilyB", "B"),
                ("PathwayCountBeforeA", "A size"),
                ("PathwayCountBeforeB", "B size"),
                ("MeanPairwiseSdJaccardBeforeWeighted", "SD Jaccard before"),
                ("MeanPairwiseSdJaccardAfterMerge", "SD Jaccard after"),
                ("InternalEdgePercentageDelta", "Internal % delta (mechanical)"),
                ("StructuralVerdict", "Structural effect"),
            ],
        )
        if len(sd_improving) == 0 and len(merges) > 0:
            lines.append(
                _tag(
                    "interpretation",
                    f"**None of the {len(merges)} tested merges raises shared-SD "
                    "cohesion.** Every high-overlap pair would produce a family less "
                    "clinically alike than its parts, even though each merge raises "
                    "the internal-edge percentage. On this evidence the overlap "
                    "between these families is shared vocabulary and shared routing "
                    "rather than a sign that the boundary is in the wrong place — but "
                    "structure cannot rule out a merge a clinician would still want, "
                    "and two families that legitimately belong together would look "
                    "exactly like this if their shared discriminators were few.",
                )
            )

    if splits.empty:
        lines.append(
            _tag(
                "derived",
                "No family in the presented set met a split trigger with two viable "
                "parts.",
            )
        )
    else:
        lines += [
            "",
            _tag(
                "derived",
                f"**{splits['FamilyId'].nunique()}** families met a split trigger; "
                f"{len(splits)} split proposals were measured across "
                f"{splits['SplitMethod'].nunique()} methods.",
            ),
            "",
        ]
        lines += _markdown_table(
            splits.head(12),
            [
                ("FamilyId", "Family"),
                ("SplitMethod", "Method"),
                ("PathwayCountBefore", "Pathways"),
                ("PartCount", "Parts"),
                ("PartSizes", "Part sizes"),
                ("InternalEdgePercentageDelta", "Internal % delta"),
                ("MeanPairwiseSdJaccardDelta", "SD Jaccard delta"),
                ("StructuralVerdict", "Structural effect"),
            ],
        )
    lines += [
        _tag(
            "assumption",
            "A split has the mirror-image bias: dividing a family turns internal edges "
            "into external ones, so the internal-edge percentage almost always falls. "
            "The split verdicts are therefore also read from the shared-symptom-"
            "discriminator change.",
        ),
        _tag(
            "assumption",
            "**No merge and no split is recommended.** Both tables are before/after "
            "measurements. A split that improves shared-SD cohesion may still separate "
            "pathways a clinician would keep together, and the reverse.",
        ),
        "",
    ]
    return lines


def _section_routing(inputs: ReportInputs) -> list[str]:
    """Section 12: routing ambiguity."""
    summary = inputs.table("pathway_family_routing_summary")
    lines = ["## 12. Routing ambiguity", ""]
    if summary.empty:
        return lines + ["_Not produced._", ""]

    lines += _markdown_table(
        summary,
        [
            ("strategy", "Strategy"),
            ("PercentageStrongSingleFamilyAssociation", "% strong single-family"),
            ("PercentageModerateAmbiguity", "% moderate"),
            ("PercentageHighAmbiguity", "% high"),
            ("PercentageOnePlausibleFamily", "% 1 plausible family"),
            ("PercentageTwoPlausibleFamilies", "% 2 plausible"),
            ("PercentageThreeOrMorePlausibleFamilies", "% 3+ plausible"),
            ("PercentageDominantMatchesAssigned", "% dominant = assigned"),
        ],
    )
    primary_summary = summary.loc[summary["strategy"] == inputs.primary.strategy]
    if not primary_summary.empty:
        row = primary_summary.iloc[0]
        lines += [
            _tag(
                "derived",
                "In the presented set, "
                f"**{row['PercentageStrongSingleFamilyAssociation']:.1f}%** "
                "of pathways associate strongly with a single family, "
                f"**{row['PercentageModerateAmbiguity']:.1f}%** are moderately "
                f"ambiguous and **{row['PercentageHighAmbiguity']:.1f}%** are highly "
                "ambiguous, where ambiguity is the second-best affinity divided by the "
                "best.",
            ),
            _tag(
                "derived",
                f"**{row['PercentageDominantMatchesAssigned']:.1f}%** of pathways have "
                "their assigned family as their highest-affinity family. A mismatch is "
                "not an error: the affinity score and the grouping rule use different "
                "evidence, and disagreement marks a pathway worth reviewing.",
            ),
            _tag(
                "assumption",
                "Affinity weights come from `routing.weights` and are not clinically "
                "validated. The five component scores are exported per pathway so a "
                "reviewer can re-weight without re-running the analysis.",
            ),
            _tag(
                "interpretation",
                "Ambiguity here is a property of the *structure*, measured with the "
                "whole pathway known. A live runtime would have to route on partial "
                "answers, which is strictly harder. These figures are therefore an "
                "optimistic bound on routability, and designing a router is out of "
                "scope for Phase 2.",
            ),
            "",
        ]
    return lines


def _section_age_trauma(inputs: ReportInputs) -> list[str]:
    """Sections on the age and trauma dimensions."""
    lines = ["## 13. Age and trauma dimensions", ""]
    for label, table_name, spread_name in (
        ("Age", "age_family_analysis", "age_spread_summary"),
        ("Trauma", "trauma_family_analysis", "trauma_spread_summary"),
    ):
        frame = inputs.table(table_name)
        spread = inputs.table(spread_name)
        lines += [f"### {label}", ""]
        if frame.empty:
            lines += ["_Not produced._", ""]
            continue
        grouping = frame.loc[frame["AnalysisScope"] == "classification_as_grouping"]
        lines += _markdown_table(
            grouping,
            [
                ("GroupOrFamily", "Classification"),
                ("PathwayCount", "Pathways"),
                ("InternalEdgePercentage", "Internal-edge %"),
                ("PercentageBoundaryPathways", "Boundary %"),
                ("MeanPairwiseSdJaccard", "Mean SD Jaccard"),
                ("UniqueDispositionCount", "Dispositions"),
            ],
        )
        if not spread.empty:
            lines += _markdown_table(
                spread,
                [
                    ("ClassificationValue", "Value"),
                    ("TaggedPathways", "Pathways"),
                    ("FamiliesContainingValue", "Families containing it"),
                    ("LargestFamilyShare", "Largest family share"),
                    ("FamiliesCovering80Percent", "Families for 80%"),
                    ("SpreadReading", "Spread"),
                ],
            )
        composition = frame.loc[frame["AnalysisScope"] == "family_composition"]
        if not composition.empty and "StructuralReading" in composition.columns:
            readings = composition["StructuralReading"].value_counts()
            lines.append(
                _tag(
                    "derived",
                    "Within-family subset comparison across "
                    f"{len(composition)} families: "
                    + "; ".join(
                        f"{int(count)} — {reading}"
                        for reading, count in readings.items()
                    )
                    + ".",
                )
            )
        lines.append(
            _tag(
                "assumption",
                f"No assumption is made that {label.lower()} must be a separate "
                "top-level family. The three readings — separate families, variants "
                "inside families, cross-cutting structure — are each given their "
                "numbers and the choice is left to clinical review.",
            )
        )
        lines.append("")
    return lines


def _section_limitations(inputs: ReportInputs) -> list[str]:
    """Section 14: uncertainties and limitations."""
    coverage = inputs.model.metadata_coverage
    missing_sg = 0
    if not coverage.empty:
        row = coverage.loc[coverage["field"] == "SymptomGroupId"]
        if not row.empty:
            missing_sg = int(row.iloc[0]["pathways_missing"])
    return [
        "## 14. Uncertainties and limitations",
        "",
        _tag(
            "measured",
            f"**{missing_sg}** in-scope pathways carry no `SymptomGroupId`, so the "
            "symptom-group baseline cannot place them. They are held in an explicit "
            "`UNASSIGNED` family rather than dropped, which means that family is an "
            "artefact of missing metadata and not a clinical grouping.",
        ),
        _tag(
            "measured",
            "SNOMED coverage is sparse relative to the answer catalogue (299 concepts "
            "over 13,609 answers), so SNOMED-based cohesion rests on much thinner "
            "evidence than symptom-discriminator cohesion. The two are never averaged.",
        ),
        _tag(
            "assumption",
            "The transfer graph counts only T1-T4 values that resolve to a pathway. "
            "`JumpID` values -2, -4, -5, -9 and 0 carry no payload and are control "
            "behaviour, so they are not edges. If any of them does imply a routing "
            "relationship not visible in `tblTriageLogic`, every cohesion figure here "
            "understates connectivity.",
        ),
        _tag(
            "assumption",
            "Symptom discriminators are attributed to a pathway through the answers it "
            "offers. A discriminator reachable only by a route the pathway never takes "
            "in practice is still counted, because reachability is what the data "
            "records and traversal frequency is not available.",
        ),
        _tag(
            "assumption",
            "Every threshold and weight is a configured default with no clinical "
            "endorsement. The Hybrid C sensitivity table shows the weighting is "
            "material, which means the Hybrid C family set should not be treated as "
            "stable.",
        ),
        _tag(
            "interpretation",
            "Graph cohesion and clinical coherence are different properties, and this "
            "analysis can only measure the first. Where a candidate family is cohesive "
            "but has no dominant NHS grouping, the evidence is genuinely ambiguous "
            "rather than merely incomplete.",
        ),
        _tag(
            "measured",
            "Pathway *usage* data is absent: every count here weights a rarely-used "
            "pathway identically to a heavily-used one. A family set that is coherent "
            "by structure may not be the one that carries the traffic.",
        ),
        "",
    ]


def _section_clinical_questions(inputs: ReportInputs) -> list[str]:
    """Section 15: questions requiring clinical review."""
    high = inputs.primary_rows("high_overlap_family_pairs")
    core = inputs.table("shared_core_candidates")
    candidates = inputs.table("candidate_bayesian_families")
    neutral = (
        candidates.loc[candidates["FamilyNameBasis"] == "neutral"]
        if not candidates.empty and "FamilyNameBasis" in candidates else pd.DataFrame()
    )
    lines = [
        "## 15. Questions requiring clinical judgement",
        "",
        "These are the points where structure has taken the analysis as far as it can. "
        "Each is asked concretely in `outputs/phase2/clinical_review_pack.md`.",
        "",
    ]
    lines += [
        f"1. **Are the {len(candidates)} candidate families clinically recognisable?** "
        "Structure says they are cohesive; only clinicians can say whether each is one "
        "clinical area.",
    ]
    if not neutral.empty:
        lines.append(
            f"2. **{len(neutral)} families have no dominant NHS grouping** and carry "
            "neutral names. Is each a real clinical grouping the metadata does not "
            "capture, or an artefact of how pathways refer to one another?"
        )
    if not high.empty:
        lines.append(
            f"3. **{len(high)} family pairs overlap strongly.** For each: are these one "
            "clinical area that routing has split, or two areas that legitimately share "
            "a screening vocabulary?"
        )
    if not core.empty:
        lines.append(
            f"4. **{len(core):,} features are used across many families.** For the most "
            "widely shared: is each one clinical concept (so a shared structure is "
            "natural), several concepts sharing wording (so sharing would conflate "
            "them), or an authoring artefact?"
        )
    lines += [
        "5. **Should paediatric pathways be their own families, age variants inside "
        "families, or a cross-cutting dimension?** The three sets of numbers are in "
        "`age_family_analysis.csv`; the choice is clinical.",
        "6. **Is trauma one family, several anatomical families, a cross-cutting "
        "dimension, or a shared gateway?** See `trauma_family_analysis.csv`.",
        "7. **Are the boundary pathways and cross-family hubs clinically significant, "
        "or incidental routing?** A hub that is clinically load-bearing is a different "
        "design problem from one that merely has many transfers.",
        "8. **Is any candidate family unsafe to separate?** If splitting two families "
        "could lose a safety-critical route between them, that constraint is invisible "
        "to this analysis and must come from clinical review.",
        "",
    ]
    return lines


def _section_phase3(inputs: ReportInputs) -> list[str]:
    """Section 16: inputs required for Phase 3."""
    return [
        "## 16. What Phase 3 needs from these results",
        "",
        "Phase 3 covers the literal, deduplicated and clinically-normalised Bayesian "
        "representations, monolithic and federated sizing, CPT growth, memory, "
        "inference benchmarks, runtime architecture, infrastructure and cost. From "
        "Phase 2 it will need:",
        "",
        "1. **A reviewed family set.** `candidate_bayesian_families.csv` plus the "
        "clinical review outcome. Sizing an unreviewed family set would carry the "
        "structural assumptions into the cost model.",
        "2. **Family membership, including overlaps.** "
        "`candidate_family_membership.csv`. Pathways in several families are counted "
        "once per family in a federated sizing and once overall in a monolithic one, so "
        "the overlap volume drives the difference between the two.",
        "3. **Per-family variable counts.** `UniqueQuestions`, `UniqueSDs`, "
        "`UniqueSnomed` and `UniqueDispositions` per family, combined with the Phase 1 "
        "answer-cardinality tables, give the per-family state space.",
        "4. **Shared-core candidates and their duplication counts.** "
        "`shared_core_candidates.csv` — `DuplicationIfFederated` is the quantity a "
        "shared-core design would avoid and a fully federated design would pay.",
        "5. **Boundary features and pathways.** The cross-family features are the "
        "nodes a federated design has to synchronise; their count bounds the inter-model "
        "interface.",
        "6. **Routing ambiguity.** The share of pathways without a clear single family "
        "bounds how well any router could work, and is an input to the federated "
        "runtime's error budget.",
        "7. **Merge and split candidates.** Alternative family sets to size alongside "
        "the primary one, so Phase 3 tests a range rather than one arrangement.",
        "8. **Release blast radius inputs.** Family membership plus the boundary "
        "feature tables determine how many families a change to one shared question "
        "would touch.",
        "",
        _tag(
            "assumption",
            "Phase 2 deliberately produces no node, edge, CPT or memory estimate. Any "
            "number of that kind in this report would be a Phase 3 result quoted "
            "without its sizing assumptions.",
        ),
        "",
    ]


def _section_configuration(inputs: ReportInputs) -> list[str]:
    """Appendix: the configuration this run used."""
    lines = [
        "## Appendix A. Configuration used by this run",
        "",
        f"Source: `{inputs.config.source_path or 'built-in defaults'}`",
        "",
        "| Setting | Value |",
        "|---|---|",
    ]
    for setting, value in inputs.config.describe():
        lines.append(f"| `{setting}` | {value} |")
    lines += [
        "",
        _tag(
            "assumption",
            "Every value above is a modelling assumption. None is clinically validated. "
            "Re-running with `--config` pointed at a modified copy reproduces the whole "
            "evidence base under different choices.",
        ),
        "",
    ]
    return lines


def _section_artefacts(inputs: ReportInputs) -> list[str]:
    """Appendix: what this run produced."""
    lines = [
        "## Appendix B. Artefacts produced",
        "",
        f"- `outputs/phase2/tables/`: {len(inputs.tables)} analysis tables.",
        "- `outputs/phase2/charts/`, `outputs/phase2/graphs/`: figures.",
        "- `outputs/phase2/reports/metric_definitions.csv`: the definition of every "
        "derived metric used above.",
        "- `outputs/phase2/clinical_review_pack.md`: the concise review document.",
        "",
    ]
    if inputs.notes:
        lines += ["### Run notes", ""]
        lines += [f"- {note}" for note in inputs.notes]
        lines.append("")
    lines += [
        "Phase 1 outputs under `outputs/tables/` and `outputs/charts/` are untouched by "
        "this run.",
        "",
    ]
    return lines


# ======================================================================================
# Clinical review pack (section 23)
# ======================================================================================
def write_clinical_review_pack(inputs: ReportInputs, path: Path) -> Path:
    """Write ``outputs/phase2/clinical_review_pack.md``.

    Deliberately much shorter than the evidence report: one compact block per candidate
    family, with the questions a clinician is being asked to answer stated explicitly.
    Metrics appear only where they change what is being asked.
    """
    config = inputs.config
    candidates = inputs.table("candidate_bayesian_families")
    overlap = inputs.primary_rows("family_overlap_matrix")
    boundary = inputs.primary_rows("boundary_pathways")
    shared_features = {
        "symptom_discriminator": inputs.table("shared_symptom_discriminators"),
        "snomed": inputs.table("shared_snomed"),
    }

    lines = [
        "# Candidate Bayesian family review pack",
        "",
        f"Generated {inputs.generated}. Candidate set: `{inputs.primary.strategy}`, "
        f"{len(candidates)} families over {inputs.primary.pathway_count:,} active "
        "pathways.",
        "",
        "## What we are asking",
        "",
        "We have grouped NHS Pathways into candidate families using measured structure: "
        "which pathways transfer to one another, and which share questions, symptom "
        "discriminators, SNOMED concepts and dispositions. **Structure cannot tell us "
        "whether a group is clinically sensible.** That is what this review is for.",
        "",
        "For each family below, please tell us:",
        "",
        "1. Is this recognisable as one clinical area? If not, what should it be called, "
        "or how should it be divided?",
        "2. Are any of the listed pathways in the wrong family?",
        "3. Where a family overlaps strongly with another, are they one area or two?",
        "4. Are there safety-critical routes into or out of this family that must not be "
        "broken by separating it from another?",
        "",
        "Nothing here is a decision. No architecture has been chosen.",
        "",
        "---",
        "",
    ]

    if candidates.empty:
        lines.append("_No candidate families were produced._")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(lines), encoding="utf-8")
        return path

    families = inputs.primary.families()
    titles = inputs.model.title_lookup()
    overlap_by_family = _overlap_index(overlap)

    for row in candidates.itertuples():
        members = families.get(row.FamilyId, set())
        representatives = _representative_pathways(
            members, inputs.similarity, titles, limit=config.representative_pathways
        )
        family_overlaps = overlap_by_family.get(row.FamilyId, [])
        family_boundary = (
            boundary.loc[
                boundary["FamilyId"].astype(str).str.contains(row.FamilyId, regex=False)
                & (boundary["BoundaryClassification"] != "internal pathway")
            ].head(4)
            if not boundary.empty else pd.DataFrame()
        )

        lines += [
            f"## {row.FamilyId} — {row.FamilyName}",
            "",
            f"**{int(row.PathwayCount)} pathways.** "
            f"Named from: {getattr(row, 'FamilyNameBasis', 'unknown')}. "
            f"Structural cohesion: {row.ConfidenceInStructuralCohesion}.",
            "",
            f"- **Dominant symptom groups:** {row.PrimarySymptomGroups or '—'}",
            f"- **Dominant clinical areas:** {row.PrimaryClinicalAreas or '—'}",
            "- **Representative pathways:** "
            + ("; ".join(representatives) if representatives else "—"),
        ]

        for dimension, label in (
            ("symptom_discriminator", "Most common symptom discriminators"),
            ("snomed", "Most common SNOMED concepts"),
        ):
            frame = shared_features.get(dimension, pd.DataFrame())
            top = _top_family_features(
                frame, members, inputs.model, dimension, limit=config.top_features
            )
            lines.append(f"- **{label}:** " + ("; ".join(top) if top else "—"))

        if family_overlaps:
            lines.append(
                "- **Strongest overlaps:** "
                + "; ".join(
                    f"{other} ({driver}, Jaccard {jaccard:.2f})"
                    for other, jaccard, driver in family_overlaps[:3]
                )
            )
        else:
            lines.append("- **Strongest overlaps:** none above the reporting threshold")

        if not family_boundary.empty:
            lines.append(
                "- **Major boundary pathways:** "
                + "; ".join(
                    f"{brow.PathwayID} {brow.PathwayTitle} "
                    f"({brow.BoundaryClassification}, "
                    f"{int(brow.ExternalDegree)} external links)"
                    for brow in family_boundary.itertuples()
                )
            )
        else:
            lines.append("- **Major boundary pathways:** none")

        questions = _family_review_questions(row, family_overlaps, family_boundary)
        lines += ["", "**Questions for this family:**", ""]
        lines += [f"{index}. {question}" for index, question in enumerate(questions, start=1)]
        lines += ["", "---", ""]

    lines += _review_cross_cutting(inputs)

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")
    LOGGER.info("Wrote %s", path.name)
    return path


def _overlap_index(overlap: pd.DataFrame) -> dict[str, list[tuple[str, float, str]]]:
    """Index the overlap matrix by family, strongest first.

    The Jaccard quoted is the one the overlap band was read from, so the number and the
    driver named beside it always refer to the same measure. Quoting the all-features
    maximum next to a driver that excludes dispositions would look like an error.
    """
    result: dict[str, list[tuple[str, float, str]]] = {}
    if overlap.empty:
        return result
    value_column = (
        "MaxDiscriminatingJaccard"
        if "MaxDiscriminatingJaccard" in overlap.columns
        else "MaxFeatureJaccard"
    )
    for row in overlap.itertuples():
        driver = getattr(row, "OverlapDriver", "")
        value = float(getattr(row, value_column))
        result.setdefault(row.FamilyA, []).append((row.FamilyB, value, driver))
        result.setdefault(row.FamilyB, []).append((row.FamilyA, value, driver))
    for family_id in result:
        result[family_id].sort(key=lambda item: -item[1])
    return result


def _representative_pathways(
    members: Sequence[str] | set[str],
    similarity: PairwiseSimilarity,
    titles: Mapping[str, str],
    *,
    limit: int,
) -> list[str]:
    """Return the most typical pathways of a family.

    "Typical" means highest mean symptom-discriminator similarity to the family's other
    members, i.e. nearest the family's centre. A reviewer judging whether a family hangs
    together needs its central members, not an arbitrary or alphabetical slice.
    """
    member_list = sorted(members)
    if not member_list:
        return []
    if len(member_list) <= limit:
        return [titles.get(key, key) for key in member_list]

    positions = similarity.positions(member_list)
    if positions.size == 0:
        return [titles.get(key, key) for key in member_list[:limit]]
    matrix = similarity.matrix("symptom_discriminator")
    block = matrix[positions[:, None], positions[None, :]]
    scores = (block.sum(axis=1) - block.diagonal()) / max(positions.size - 1, 1)
    ordered_keys = [similarity.pathways[position] for position in positions]
    ranked = sorted(zip(ordered_keys, scores), key=lambda item: -float(item[1]))
    return [titles.get(key, key) for key, _ in ranked[:limit]]


def _top_family_features(
    frame: pd.DataFrame,
    members: Sequence[str] | set[str],
    model: PathwayFeatureModel,
    dimension: str,
    *,
    limit: int,
) -> list[str]:
    """Return the features most used **within** one family.

    Counted over the family's own pathways, not over the whole estate. The
    shared-feature tables carry a global pathway count, and quoting that inside a
    per-family block would tell a reviewer how widely a discriminator is used
    everywhere while appearing to describe this family.

    The global count is appended in brackets, labelled, so the two are distinguishable:
    a discriminator used by 6 of this family's pathways and 514 estate-wide is a shared
    screening concept, not a marker of the family.
    """
    feature_map = getattr(model.maps, dimension, None)
    if feature_map is None or feature_map.empty:
        return []
    member_set = set(members)
    subset = feature_map.loc[feature_map["pathway_key"].isin(member_set)]
    if subset.empty:
        return []
    within = subset.groupby("feature_id")["pathway_key"].nunique().nlargest(limit)

    descriptions: dict[str, str] = {}
    estate_counts: dict[str, int] = {}
    if not frame.empty and "FeatureId" in frame.columns:
        descriptions = dict(
            zip(frame["FeatureId"].astype(str), frame["Description"].astype(str))
        )
        estate_counts = dict(
            zip(frame["FeatureId"].astype(str), frame["PathwayCount"].astype(int))
        )

    results = []
    for feature_id, count in within.items():
        key = str(feature_id)
        description = descriptions.get(key, "").strip()
        label = key + (f" {description}" if description else "")
        estate = estate_counts.get(key)
        suffix = (
            f" — {int(count)} of this family's pathways, {estate} estate-wide"
            if estate is not None
            else f" — {int(count)} of this family's pathways"
        )
        results.append(label + suffix)
    return results


def _family_review_questions(
    row: object,
    overlaps: Sequence[tuple[str, float, str]],
    boundary: pd.DataFrame,
) -> list[str]:
    """Return the review questions a specific family raises."""
    questions = [
        "Is this one clinical area? If not, how should it be divided, and along what "
        "clinical line?",
    ]
    name_basis = str(getattr(row, "FamilyNameBasis", ""))
    if name_basis == "neutral":
        questions.append(
            "This family has no dominant symptom group or clinical area, so we have not "
            "named it. Is there a clinical grouping here that the metadata does not "
            "capture?"
        )
    else:
        questions.append(
            f"We have named it from its dominant metadata. Is `{row.FamilyName}` the "
            "right name?"
        )
    if overlaps and overlaps[0][1] >= 0.3:
        questions.append(
            f"It overlaps strongly with {overlaps[0][0]} (driver: {overlaps[0][2]}). "
            "Are these one clinical area or two that share a vocabulary?"
        )
    if not boundary.empty:
        questions.append(
            "Are the boundary pathways listed above clinically part of this family, of "
            "another, or genuinely shared?"
        )
    if int(getattr(row, "PathwayCount", 0)) >= 60:
        questions.append(
            "This is one of the larger families. Does it contain more than one clinical "
            "area that should be separated?"
        )
    if int(getattr(row, "PathwayCount", 0)) <= 6:
        questions.append(
            "This is a very small family. Should it stand alone, or belong inside a "
            "larger one?"
        )
    return questions


def _review_cross_cutting(inputs: ReportInputs) -> list[str]:
    """Return the cross-cutting questions section of the review pack."""
    core = inputs.table("shared_core_candidates")
    lines = [
        "## Cross-cutting questions",
        "",
        "### Features used across many families",
        "",
    ]
    if core.empty:
        lines.append("_No feature met the shared-core threshold._")
    else:
        lines += [
            f"{len(core):,} questions, symptom discriminators, SNOMED concepts and "
            f"dispositions are used by at least "
            f"{inputs.config.shared_core_minimum_family_count} candidate families. The "
            "most widely shared are:",
            "",
        ]
        top = core.nlargest(12, ["FamilyCount", "PathwayCount"])
        lines += _markdown_table(
            top,
            [
                ("FeatureTypeLabel", "Type"),
                ("FeatureId", "Id"),
                ("Description", "Description"),
                ("FamilyCount", "Families"),
                ("PathwayCount", "Pathways"),
            ],
        )
        lines += [
            "**For each of these, we need to know:** is it one clinical concept used "
            "across many areas, several different concepts that share an identifier or "
            "wording, or a by-product of how the pathways were authored? The answer "
            "changes whether a shared structure would be correct or would conflate "
            "distinct clinical meanings.",
            "",
        ]

    lines += [
        "### Age",
        "",
        "Paediatric pathways can be read three ways, and the structure supports more "
        "than one. Should paediatric pathways be:",
        "",
        "- their own families, separate from the adult equivalents;",
        "- age variants inside the same family as the adult pathway; or",
        "- a cross-cutting attribute that every family handles?",
        "",
        "### Trauma",
        "",
        "Likewise for trauma. Is trauma one family, several anatomical families, a "
        "cross-cutting dimension applied to other families, or a shared entry point "
        "into them?",
        "",
        "### Safety",
        "",
        "Is there any pair of candidate families that must not be separated, because a "
        "clinically critical route runs between them? This constraint cannot be seen in "
        "the data and has to come from clinical review.",
        "",
        "---",
        "",
        "_No architectural decision has been made. This review feeds the family "
        "definitions that Phase 3 will size and cost._",
        "",
    ]
    return lines
