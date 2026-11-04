"""Phase 1 runner: structural profiling of the NHS Pathways dataset.

Usage::

    python -m pathways_analysis.profiling
    python -m pathways_analysis.profiling --no-charts

The run validates connectivity, extracts read-only from SQL Server, derives every
Phase 1 analysis, writes tables/graph artefacts/charts and prints a summary.

Scope boundary
--------------
Phase 1 measures structure only. It deliberately produces no Bayesian-network sizing
and no monolithic-vs-federated recommendation; those belong to Phase 2.
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Final

import pandas as pd

from . import exports
from . import graph as graph_tools
from .config import ConfigurationError, DatabaseSettings, Paths, load_dotenv_if_present
from .db import DatabaseConnectionError, PathwaysDatabase, normalise_id

LOGGER: Final = logging.getLogger("pathways_analysis")

#: Percentiles reported for every size distribution in Phase 1.
PERCENTILES: Final = (75, 90, 95, 99)

#: Question-reuse bands, as (label, inclusive_lower, inclusive_upper_or_None).
REUSE_BANDS: Final = (
    ("1 pathway", 1, 1),
    ("2-5 pathways", 2, 5),
    ("6-10 pathways", 6, 10),
    ("11-25 pathways", 11, 25),
    ("26+ pathways", 26, None),
)

#: JumpID values the supplied Pathways description accounts for. Anything else is
#: reported as unexpected rather than being silently folded into a bucket.
DOCUMENTED_JUMP_IDS: Final = (-1, -2, -3, -4, -5, -6, -9)


@dataclass
class RunResult:
    """Outcome of a Phase 1 run."""

    inventory: dict[str, int] = field(default_factory=dict)
    graph_summary: dict[str, Any] = field(default_factory=dict)
    tables_written: list[Path] = field(default_factory=list)
    charts_written: list[Path] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    elapsed_seconds: float = 0.0


class Phase1Profiler:
    """Executes the Phase 1 structural analyses end to end."""

    def __init__(self, database: PathwaysDatabase, paths: Paths) -> None:
        self.db = database
        self.paths = paths
        self.extracts: dict[str, pd.DataFrame] = {}
        self.result = RunResult()
        self._summary_sections: list[tuple[str, list[str]]] = []

    # -- helpers -----------------------------------------------------------------
    def _table(self, frame: pd.DataFrame, name: str) -> Path:
        path = exports.write_table(frame, self.paths.tables / f"{name}.csv")
        self.result.tables_written.append(path)
        return path

    def _note(self, message: str) -> None:
        self.result.notes.append(message)
        LOGGER.info("NOTE: %s", message)

    # -- extraction --------------------------------------------------------------
    def extract(self) -> None:
        """Run every read-only extract and normalise identifier case."""
        LOGGER.info("--- Extracting from SQL Server (read-only) ---")
        names = (
            "inventory", "pathways", "questions", "answers", "dispositions",
            "symptom_groups", "symptom_discriminators",
            "symptom_group_disc_combinations", "clinical_areas",
            "pathway_clinical_areas", "answer_snomeds", "dx_rank", "triage_logic",
            "pathway_complexity", "question_reuse", "unreferenced_questions",
            "unreferenced_answers", "answer_cardinality", "control_types",
            "jump_distribution", "positive_jumps", "transfer_values",
            "pathway_discriminators", "symptom_group_discriminator_counts",
            "answers_with_discriminators", "pathway_snomed", "snomed_catalogue",
            "data_quality", "orphan_tx_question_detail", "node_prefix_distribution",
        )
        for name in names:
            self.extracts[name] = self.db.read_query(name)

        # Identifier case is normalised at the boundary. Every *_key column already
        # arrives upper-cased from SQL; this re-applies it defensively so a hand-edited
        # query cannot reintroduce a case-sensitive join bug downstream.
        for frame in self.extracts.values():
            for column in frame.columns:
                if column.endswith("_key"):
                    frame[column] = normalise_id(frame[column])

    # -- 1. dataset inventory ----------------------------------------------------
    def analyse_inventory(self) -> None:
        LOGGER.info("--- 1. Dataset inventory ---")
        inventory = self.extracts["inventory"].copy()
        inventory["value"] = inventory["value"].astype("int64")
        self.result.inventory = dict(zip(inventory["metric"], inventory["value"]))
        self._table(inventory.sort_values("metric", ignore_index=True), "dataset_inventory")

        counts = self.result.inventory
        self._summary_sections.append(
            (
                "Dataset inventory (measured facts)",
                [
                    f"- Active pathways: **{counts['pathways_active']:,}** "
                    f"of {counts['pathways_total']:,} catalogued "
                    f"({counts['pathways_archived']:,} archived, "
                    f"{counts['pathways_flagged_for_deletion']:,} flagged for deletion).",
                    f"- Active questions: **{counts['questions_active']:,}** "
                    f"of {counts['questions_total']:,} catalogued.",
                    f"- Answers: **{counts['answers_total']:,}**.",
                    f"- Triage logic rows: **{counts['triage_logic_rows']:,}**.",
                    f"- Active dispositions: **{counts['dispositions_active']:,}** "
                    f"of {counts['dispositions_total']:,}; "
                    f"{counts['disposition_items_total']:,} disposition items; "
                    f"{counts['dx_rank_total']} Dx ranks.",
                    f"- Symptom groups: **{counts['symptom_groups_total']:,}** "
                    f"({counts['symptom_groups_active']:,} flagged Active).",
                    f"- Symptom discriminators: **{counts['symptom_discriminators_total']:,}** "
                    f"({counts['symptom_discriminators_active']:,} flagged Active).",
                    f"- Clinical areas: **{counts['clinical_areas_total']}** "
                    f"with {counts['pathway_clinical_area_links']:,} pathway links.",
                    f"- SNOMED: {counts['answer_snomed_assignments']:,} answer assignments "
                    f"covering {counts['distinct_snomed_concepts']:,} distinct concepts.",
                    f"- Distinct pathways present in triage logic: "
                    f"{counts['distinct_pathways_in_triage_logic']:,}; distinct order "
                    f"positions: {counts['distinct_order_positions_in_triage_logic']:,}.",
                ],
            )
        )

    # -- 6. jump analysis (runs early: classifies before anything assumes edges) --
    def analyse_jumps(self) -> pd.DataFrame:
        LOGGER.info("--- 6. Jump analysis ---")
        distribution = self.extracts["jump_distribution"].copy()
        distribution["is_documented"] = (
            distribution["jump_id"].isin(DOCUMENTED_JUMP_IDS)
            | (distribution["jump_id"] > 0)
        )

        positive = self.extracts["positive_jumps"]
        buckets = []
        for jump_id in DOCUMENTED_JUMP_IDS:
            row = distribution.loc[distribution["jump_id"] == jump_id]
            buckets.append(
                {
                    "bucket": f"JumpID = {jump_id}",
                    "row_count": int(row["row_count"].iloc[0]) if len(row) else 0,
                    "t_fields_populated": int(row["t1_populated"].iloc[0]) if len(row) else 0,
                }
            )
        buckets.insert(
            0,
            {
                "bucket": "JumpID > 0",
                "row_count": int(distribution.loc[distribution["jump_id"] > 0, "row_count"].sum()),
                "t_fields_populated": int(
                    distribution.loc[distribution["jump_id"] > 0, "t1_populated"].sum()
                ),
            },
        )
        unexpected = distribution.loc[~distribution["is_documented"]]
        buckets.append(
            {
                "bucket": "unexpected values",
                "row_count": int(unexpected["row_count"].sum()),
                "t_fields_populated": int(unexpected["t1_populated"].sum()),
            }
        )
        bucket_frame = pd.DataFrame(buckets)
        self._table(bucket_frame, "jump_buckets")
        self._table(distribution.sort_values("jump_id", ignore_index=True), "jump_distribution")

        unresolved_targets = int((positive["target_resolved"] == 0).sum())
        direction_counts = positive["jump_direction"].value_counts().to_dict()
        distances = graph_tools.describe_distribution(
            positive["jump_distance"].abs(), percentiles=PERCENTILES
        )
        self._table(
            pd.DataFrame(
                [
                    {
                        "metric": "positive_jump_rows",
                        "value": len(positive),
                    },
                    {"metric": "forward_jumps", "value": direction_counts.get("forward", 0)},
                    {"metric": "backward_jumps", "value": direction_counts.get("backward", 0)},
                    {"metric": "self_jumps", "value": direction_counts.get("self", 0)},
                    {"metric": "unresolved_target_order_numbers", "value": unresolved_targets},
                    *[
                        {"metric": f"abs_jump_distance_{key}", "value": value}
                        for key, value in distances.items()
                    ],
                ]
            ),
            "jump_positive_summary",
        )

        # Rendered as `value (n rows)` because at least one undocumented value IS the
        # integer 0, and a bare "0" here would read as "there are none".
        if unexpected.empty:
            unexpected_list = "none"
        else:
            unexpected_list = ", ".join(
                f"`{int(row.jump_id)}` ({int(row.row_count):,} rows)"
                for row in unexpected.sort_values("jump_id").itertuples()
            )
        self._summary_sections.append(
            (
                "JumpID classification (measured facts)",
                [
                    f"- Positive (intra-pathway) jumps: "
                    f"**{bucket_frame.loc[0, 'row_count']:,}** rows; "
                    f"{direction_counts.get('forward', 0):,} forward, "
                    f"{direction_counts.get('backward', 0):,} backward.",
                    f"- Unresolved positive-jump targets: **{unresolved_targets:,}** "
                    "(every positive JumpID resolves to an existing OrderNumber in its "
                    "own pathway)." if unresolved_targets == 0 else
                    f"- Unresolved positive-jump targets: **{unresolved_targets:,}**.",
                    f"- JumpID values not documented in the supplied Pathways "
                    f"description: {unexpected_list}.",
                    "- T1-T4 are populated for JumpID -1, -3 and -6 only. JumpID -2, -4, "
                    "-5, -9 and 0 carry no transfer payload, so they are control "
                    "behaviour that cannot be resolved to a target from tblTriageLogic "
                    "alone and are **not** treated as graph edges.",
                ],
            )
        )
        return distribution

    # -- 7. transfer analysis ----------------------------------------------------
    def analyse_transfers(self) -> pd.DataFrame:
        LOGGER.info("--- 7. Transfer analysis ---")
        transfers = self.extracts["transfer_values"].copy()

        transfers["resolves_pathway"] = transfers["resolves_pathway"].astype(bool)
        transfers["resolves_disposition_code"] = transfers["resolves_disposition_code"].astype(bool)
        transfers["resolves_disposition_id"] = transfers["resolves_disposition_id"].astype(bool)
        transfers["resolves_disposition"] = (
            transfers["resolves_disposition_code"] | transfers["resolves_disposition_id"]
        )
        transfers["resolved_pathway_key"] = transfers["candidate_pathway_key"].where(
            transfers["resolves_pathway"]
        )

        def classify(row: pd.Series) -> str:
            if row["resolves_pathway"] and row["resolves_disposition"]:
                return "both"
            if row["resolves_pathway"]:
                return "pathway"
            if row["resolves_disposition"]:
                return "disposition"
            return "neither"

        transfers["resolution_class"] = transfers.apply(classify, axis=1)

        self._table(
            transfers[
                [
                    "source_pathway_id", "source_pathway_key", "source_order",
                    "question_id", "question_key", "answer_number", "jump_id",
                    "rank_value", "branch", "transfer_value", "has_dot",
                    "candidate_pathway_key", "candidate_order_number",
                    "resolution_class", "resolves_pathway", "resolves_disposition_code",
                    "resolves_disposition_id", "resolved_pathway_id",
                    "resolved_disposition_code", "resolved_disposition_id",
                    "target_order_resolved", "target_pathway_is_archived",
                ]
            ].sort_values(
                [
                    "source_pathway_key", "source_order", "question_key",
                    "answer_number", "branch",
                ],
                ignore_index=True,
            ),
            "transfer_values",
        )

        class_counts = transfers["resolution_class"].value_counts().to_dict()
        by_jump = (
            transfers.groupby(["jump_id", "resolution_class"], dropna=False)
            .size()
            .reset_index(name="row_count")
            .sort_values(["jump_id", "resolution_class"], ignore_index=True)
        )
        self._table(by_jump, "transfer_resolution_by_jump_id")

        pathway_rows = transfers.loc[transfers["resolution_class"].isin(["pathway", "both"])]
        disposition_rows = transfers.loc[
            transfers["resolution_class"].isin(["disposition", "both"])
        ]
        unresolved_rows = transfers.loc[transfers["resolution_class"] == "neither"]

        edges = graph_tools.aggregate_pathway_edges(pathway_rows)
        self._table(edges, "pathway_to_pathway_edges")

        disposition_edges = (
            disposition_rows.assign(
                disposition_code=disposition_rows["resolved_disposition_code"].fillna(
                    disposition_rows["transfer_value"]
                )
            )
            .groupby(["source_pathway_key", "disposition_code"], dropna=False)
            .agg(
                transition_count=("branch", "size"),
                branches=("branch", "nunique"),
                source_question_count=("question_key", "nunique"),
                source_order_count=("source_order", "nunique"),
            )
            .reset_index()
            .sort_values(["source_pathway_key", "disposition_code"], ignore_index=True)
        )
        self._table(disposition_edges, "pathway_to_disposition_edges")

        unresolved_summary = (
            unresolved_rows.groupby(
                ["transfer_value", "jump_id", "has_dot", "candidate_pathway_key"],
                dropna=False,
            )
            .agg(
                occurrence_count=("branch", "size"),
                source_pathways=("source_pathway_key", "nunique"),
                example_source_pathway=("source_pathway_id", "first"),
                example_source_order=("source_order", "first"),
            )
            .reset_index()
            .sort_values(
                ["occurrence_count", "transfer_value", "jump_id"],
                ascending=[False, True, True],
                ignore_index=True,
            )
        )
        self._table(unresolved_summary, "unresolved_transfer_values")

        target_order_unresolved = int(
            (_as_int_flag(pathway_rows["target_order_resolved"]) == 0).sum()
        )
        archived_targets = int(
            _as_int_flag(pathway_rows["target_pathway_is_archived"]).sum()
        )

        self._summary_sections.append(
            (
                "Transfer resolution (measured facts)",
                [
                    f"- Unpivoted transfer values (T1-T4, non-empty): "
                    f"**{len(transfers):,}**.",
                    f"- Resolve to a pathway: **{class_counts.get('pathway', 0):,}**; "
                    f"to a disposition: **{class_counts.get('disposition', 0):,}**; "
                    f"to both: **{class_counts.get('both', 0):,}**; "
                    f"to neither: **{class_counts.get('neither', 0):,}**.",
                    f"- Distinct unresolved transfer values: "
                    f"**{unresolved_summary['transfer_value'].nunique():,}** "
                    f"(listed in full in `outputs/tables/unresolved_transfer_values.csv`).",
                    "- Transfer grammar is measured, not assumed: a value containing "
                    "`.` is `<PathwayID>.<OrderNumber>` and denotes a pathway transfer; "
                    "a value without `.` is a DispositionCode. No PathwayID or "
                    "DispositionCode in the database contains a `.`, so the split is "
                    "unambiguous.",
                    "- **JumpID = -1 is mixed**: it carries disposition codes on some "
                    "rows and pathway transfers on others. JumpID = -3 and -6 carry "
                    "pathway transfers only. This contradicts treating -1 alone as the "
                    "transfer mechanism.",
                    f"- Pathway transfers pointing at an OrderNumber that does not exist "
                    f"in the target pathway: **{target_order_unresolved:,}**.",
                    f"- Pathway transfers whose target pathway is archived: "
                    f"**{archived_targets:,}**.",
                ],
            )
        )
        self.extracts["_transfers_resolved"] = transfers
        return edges

    # -- 2/3. pathway inventory and complexity -----------------------------------
    def analyse_pathways(self, edges: pd.DataFrame) -> pd.DataFrame:
        LOGGER.info("--- 2/3. Pathway inventory and complexity ---")
        pathways = self.extracts["pathways"].copy()
        pathways["is_active"] = pathways["is_active"].astype(bool)
        complexity = self.extracts["pathway_complexity"]
        transfers = self.extracts["_transfers_resolved"]

        symptom_groups = self.extracts["symptom_groups"][["sg_id", "sg_desc"]]
        clinical_areas = self.extracts["clinical_areas"]
        pathway_areas = self.extracts["pathway_clinical_areas"].merge(
            clinical_areas, on="clinical_area_id", how="left"
        )
        areas_joined = (
            pathway_areas.sort_values(["pathway_key", "clinical_area_description"])
            .groupby("pathway_key")
            .agg(
                clinical_areas=("clinical_area_description", lambda values: " | ".join(
                    str(value) for value in values if pd.notna(value)
                )),
                clinical_area_count=("clinical_area_id", "nunique"),
            )
            .reset_index()
        )

        discriminators = (
            self.extracts["pathway_discriminators"]
            .groupby("pathway_key")["sd_id"].nunique()
            .reset_index(name="unique_symptom_discriminators")
        )
        snomed = (
            self.extracts["pathway_snomed"]
            .groupby("pathway_key")["snomed_concept_id"].nunique()
            .reset_index(name="unique_snomed_concepts")
        )

        transfer_rows = (
            transfers.groupby("source_pathway_key")
            .agg(
                transfer_row_count=("branch", "size"),
                distinct_dispositions=("resolved_disposition_code", "nunique"),
            )
            .reset_index()
            .rename(columns={"source_pathway_key": "pathway_key"})
        )
        outgoing = (
            edges.groupby("source_pathway_key")
            .agg(
                outgoing_pathway_transfers=("target_pathway_key", "nunique"),
                outgoing_transition_count=("transition_count", "sum"),
            )
            .reset_index()
            .rename(columns={"source_pathway_key": "pathway_key"})
        )
        incoming = (
            edges.groupby("target_pathway_key")
            .agg(
                incoming_pathway_transfers=("source_pathway_key", "nunique"),
                incoming_transition_count=("transition_count", "sum"),
            )
            .reset_index()
            .rename(columns={"target_pathway_key": "pathway_key"})
        )

        merged = (
            pathways.merge(symptom_groups, left_on="symptom_group_id", right_on="sg_id",
                           how="left")
            .merge(areas_joined, on="pathway_key", how="left")
            .merge(complexity, on="pathway_key", how="left")
            .merge(discriminators, on="pathway_key", how="left")
            .merge(snomed, on="pathway_key", how="left")
            .merge(transfer_rows, on="pathway_key", how="left")
            .merge(outgoing, on="pathway_key", how="left")
            .merge(incoming, on="pathway_key", how="left")
        )

        count_columns = [
            "question_count", "care_advice_node_count", "disposition_node_count",
            "distinct_node_count", "logic_position_count", "logic_row_count",
            "answer_transition_count", "positive_jump_count", "zero_jump_count",
            "jump_minus_one_count", "special_negative_jump_count",
            "unique_symptom_discriminators", "unique_snomed_concepts",
            "transfer_row_count", "distinct_dispositions",
            "outgoing_pathway_transfers", "outgoing_transition_count",
            "incoming_pathway_transfers", "incoming_transition_count",
            "clinical_area_count",
        ]
        for column in count_columns:
            if column in merged.columns:
                merged[column] = merged[column].fillna(0).astype("int64")
        merged["clinical_areas"] = merged["clinical_areas"].fillna("")
        merged["avg_branches_per_position"] = merged["avg_branches_per_position"].astype(
            "float64"
        )

        # Full complexity table: every catalogued pathway, active or not.
        complexity_columns = [
            "pathway_id", "pathway_key", "pathway_title", "pathway_version_no",
            "is_active", "is_archived", "flag_for_deletion", "symptom_group_id",
            "sg_desc", "clinical_areas", "clinical_area_count", "question_count",
            "care_advice_node_count", "disposition_node_count", "distinct_node_count",
            "logic_position_count", "logic_row_count", "answer_transition_count",
            "avg_branches_per_position", "max_branches_per_position",
            "min_branches_per_position", "min_order_number", "max_order_number",
            "positive_jump_count", "zero_jump_count", "jump_minus_one_count",
            "special_negative_jump_count", "transfer_row_count",
            "distinct_dispositions", "outgoing_pathway_transfers",
            "outgoing_transition_count", "incoming_pathway_transfers",
            "incoming_transition_count", "unique_symptom_discriminators",
            "unique_snomed_concepts",
        ]
        complexity_table = merged[complexity_columns].sort_values(
            "pathway_key", ignore_index=True
        )
        self._table(complexity_table, "pathway_complexity")

        # Pathway inventory: active pathways only, using the column names specified
        # for this deliverable.
        active = merged.loc[merged["is_active"]].copy()
        inventory = pd.DataFrame(
            {
                "PathwayID": active["pathway_id"],
                "PathwayTitle": active["pathway_title"],
                "Module": active["module"],
                "Party": active["party"],
                "SymptomGroupId": active["symptom_group_id"],
                "SymptomGroupDescription": active["sg_desc"],
                "ClinicalAreas": active["clinical_areas"],
                "QuestionCount": active["question_count"],
                "LogicPositionCount": active["logic_position_count"],
                "LogicRowCount": active["logic_row_count"],
                "AnswerTransitionCount": active["answer_transition_count"],
                "PositiveJumpCount": active["positive_jump_count"],
                "TransferRowCount": active["transfer_row_count"],
                "UniqueSymptomDiscriminators": active["unique_symptom_discriminators"],
                "UniqueSnomedConcepts": active["unique_snomed_concepts"],
            }
        ).sort_values("PathwayID", ignore_index=True)

        self._table(inventory, "pathway_inventory")
        exports.write_parquet(inventory, self.paths.data_processed / "pathway_inventory.parquet")

        # Summary statistics over active pathways.
        active_with_logic = active.loc[active["logic_row_count"] > 0]
        distribution_specs = {
            "QuestionCount": active_with_logic["question_count"],
            "LogicPositionCount": active_with_logic["logic_position_count"],
            "LogicRowCount": active_with_logic["logic_row_count"],
            "BranchingFactor": active_with_logic["avg_branches_per_position"],
        }
        summary_rows = []
        for metric, series in distribution_specs.items():
            stats = graph_tools.describe_distribution(series, percentiles=PERCENTILES)
            summary_rows.append({"metric": metric, **stats})
        summary = pd.DataFrame(summary_rows)
        self._table(summary, "pathway_complexity_summary")

        question_stats = summary.loc[summary["metric"] == "QuestionCount"].iloc[0]
        rows_stats = summary.loc[summary["metric"] == "LogicRowCount"].iloc[0]
        branch_stats = summary.loc[summary["metric"] == "BranchingFactor"].iloc[0]
        self._summary_sections.append(
            (
                "Pathway size distribution (derived metrics)",
                [
                    f"- Active pathways with triage logic: "
                    f"**{len(active_with_logic):,}**.",
                    f"- Questions per pathway: min {question_stats['min']:.0f}, "
                    f"median {question_stats['median']:.0f}, "
                    f"mean {question_stats['mean']:.1f}, "
                    f"p90 {question_stats['p90']:.0f}, p95 {question_stats['p95']:.0f}, "
                    f"p99 {question_stats['p99']:.0f}, max {question_stats['max']:.0f}.",
                    f"- Triage logic rows per pathway: median "
                    f"{rows_stats['median']:.0f}, p95 {rows_stats['p95']:.0f}, "
                    f"max {rows_stats['max']:.0f}.",
                    f"- Branching factor (mean distinct answers per order position): "
                    f"median {branch_stats['median']:.2f}, "
                    f"p95 {branch_stats['p95']:.2f}, max {branch_stats['max']:.2f}.",
                    "- Node counts are split by kind because `tblTriageLogic.QuestionID` "
                    "is polymorphic: `QuestionCount` counts only `Tx` triage questions, "
                    "excluding `Cx` care-advice and `Dx` disposition node references.",
                ],
            )
        )
        return merged

    # -- 4. question reuse -------------------------------------------------------
    def analyse_question_reuse(self) -> None:
        LOGGER.info("--- 4. Question reuse ---")
        reuse = self.extracts["question_reuse"].copy()
        reuse["answer_cardinality"] = reuse["answer_cardinality"].fillna(0).astype("int64")

        def band(count: int) -> str:
            for label, lower, upper in REUSE_BANDS:
                if count >= lower and (upper is None or count <= upper):
                    return label
            return "0 pathways"

        reuse["reuse_band"] = reuse["pathway_count"].apply(band)
        self._table(
            reuse.sort_values(
                ["node_kind", "pathway_count", "question_key"],
                ascending=[True, False, True],
                ignore_index=True,
            ),
            "question_reuse",
        )

        questions_only = reuse.loc[reuse["node_kind"] == "question"]
        band_order = [label for label, _, _ in REUSE_BANDS]
        bands = (
            questions_only.groupby("reuse_band")
            .agg(
                question_count=("question_key", "nunique"),
                total_logic_rows=("logic_row_count", "sum"),
                mean_pathways_per_question=("pathway_count", "mean"),
            )
            .reindex(band_order)
            .fillna(0)
            .reset_index()
            .rename(columns={"reuse_band": "band"})
        )
        bands["question_count"] = bands["question_count"].astype("int64")
        bands["total_logic_rows"] = bands["total_logic_rows"].astype("int64")
        bands["mean_pathways_per_question"] = bands["mean_pathways_per_question"].round(2)
        bands["percentage_of_questions"] = (
            100.0 * bands["question_count"] / max(bands["question_count"].sum(), 1)
        ).round(2)
        self._table(bands, "question_reuse_bands")

        by_kind = (
            reuse.groupby("node_kind")
            .agg(
                distinct_references=("question_key", "nunique"),
                logic_rows=("logic_row_count", "sum"),
                max_pathways=("pathway_count", "max"),
            )
            .reset_index()
        )
        self._table(by_kind, "node_reference_kinds")

        stats = graph_tools.describe_distribution(
            questions_only["pathway_count"], percentiles=PERCENTILES
        )
        single = int(bands.loc[bands["band"] == "1 pathway", "question_count"].iloc[0])
        heavy = int(bands.loc[bands["band"] == "26+ pathways", "question_count"].iloc[0])
        most_reused = questions_only.nlargest(1, "pathway_count")
        self._summary_sections.append(
            (
                "Question reuse (derived metrics)",
                [
                    f"- Distinct `Tx` questions referenced by triage logic: "
                    f"**{stats['count']:,}**.",
                    f"- Pathways per question: median {stats['median']:.0f}, "
                    f"mean {stats['mean']:.2f}, p90 {stats['p90']:.0f}, "
                    f"p99 {stats['p99']:.0f}, max {stats['max']:.0f}.",
                    f"- Used by exactly one pathway: **{single:,}** questions "
                    f"({100.0 * single / max(int(stats['count']), 1):.1f}%). "
                    f"Used by 26+ pathways: **{heavy:,}**.",
                    f"- Most reused question: `{most_reused['question_key'].iloc[0]}` "
                    f"in {int(most_reused['pathway_count'].iloc[0]):,} pathways."
                    if len(most_reused) else "- No question reuse data.",
                    "- Reuse is the quantity that decides whether a federated design can "
                    "keep families independent; it is reported here without "
                    "interpretation.",
                ],
            )
        )

    # -- 5. answer cardinality ---------------------------------------------------
    def analyse_answer_cardinality(self) -> None:
        LOGGER.info("--- 5. Answer cardinality ---")
        cardinality = self.extracts["answer_cardinality"].copy()
        control_types = self.extracts["control_types"]
        cardinality = cardinality.merge(control_types, on="control_type", how="left")
        cardinality["is_active"] = cardinality["is_active"].astype(bool)
        self._table(
            cardinality.sort_values("question_id", ignore_index=True), "answer_cardinality"
        )

        active = cardinality.loc[cardinality["is_active"]]
        distribution = (
            active.groupby("catalogue_answer_count")
            .agg(number_of_questions=("question_id", "nunique"))
            .reset_index()
            .rename(columns={"catalogue_answer_count": "answer_count"})
            .sort_values("answer_count", ignore_index=True)
        )
        distribution["percentage_of_questions"] = (
            100.0 * distribution["number_of_questions"]
            / max(distribution["number_of_questions"].sum(), 1)
        ).round(3)
        distribution["cumulative_percentage"] = (
            distribution["percentage_of_questions"].cumsum().round(3)
        )
        self._table(distribution, "answer_cardinality_distribution")

        stats_rows = []
        for label, series in (
            ("catalogue_answer_count_active_questions", active["catalogue_answer_count"]),
            ("used_answer_count_active_questions", active["used_answer_count"]),
            ("catalogue_answer_count_all_questions",
             cardinality["catalogue_answer_count"]),
        ):
            stats_rows.append(
                {
                    "metric": label,
                    **graph_tools.describe_distribution(
                        series, percentiles=(90, 95, 99)
                    ),
                }
            )
        stats_frame = pd.DataFrame(stats_rows)
        self._table(stats_frame, "answer_cardinality_summary")

        by_control = (
            active.groupby(["control_type", "control_type_desc"], dropna=False)
            .agg(
                question_count=("question_id", "nunique"),
                mean_answer_count=("catalogue_answer_count", "mean"),
                max_answer_count=("catalogue_answer_count", "max"),
            )
            .reset_index()
        )
        by_control["mean_answer_count"] = by_control["mean_answer_count"].round(2)
        self._table(by_control, "answer_cardinality_by_control_type")

        active_stats = stats_rows[0]
        divergent = int((active["catalogue_answer_count"] != active["used_answer_count"]).sum())
        self._summary_sections.append(
            (
                "Answer cardinality (derived metrics; input to Phase 2 CPT sizing)",
                [
                    f"- Active questions: **{active_stats['count']:,}**. Answers per "
                    f"question: min {active_stats['min']:.0f}, "
                    f"median {active_stats['median']:.0f}, "
                    f"mean {active_stats['mean']:.2f}, p90 {active_stats['p90']:.0f}, "
                    f"p95 {active_stats['p95']:.0f}, max {active_stats['max']:.0f}.",
                    f"- Questions whose catalogued answer count differs from the number "
                    f"of answers actually exercised in triage logic: "
                    f"**{divergent:,}**. Both counts are exported, because they give "
                    f"different CPT state-space sizes.",
                    f"- Questions with no catalogued answers at all: "
                    f"**{int((active['catalogue_answer_count'] == 0).sum()):,}**.",
                ],
            )
        )

    # -- 8. pathway graph --------------------------------------------------------
    def analyse_graph(self, edges: pd.DataFrame, pathway_frame: pd.DataFrame):
        LOGGER.info("--- 8. Pathway graph ---")
        participating = set(edges["source_pathway_key"]) | set(edges["target_pathway_key"])
        node_mask = pathway_frame["is_active"] | pathway_frame["pathway_key"].isin(
            participating
        )
        node_attributes = pathway_frame.loc[
            node_mask,
            [
                "pathway_key", "pathway_id", "pathway_title", "is_active",
                "symptom_group_id", "sg_desc", "clinical_areas", "question_count",
                "logic_row_count", "logic_position_count",
            ],
        ].rename(columns={"sg_desc": "symptom_group_description"})

        pathway_graph = graph_tools.build_pathway_graph(edges, node_attributes)
        summary = graph_tools.graph_summary(pathway_graph)
        self.result.graph_summary = summary

        metrics = graph_tools.node_metrics(pathway_graph)
        node_table = node_attributes.merge(metrics, on="pathway_key", how="left").fillna(
            {
                "in_degree": 0, "out_degree": 0, "total_degree": 0,
                "weighted_in_degree": 0, "weighted_out_degree": 0,
                "weighted_total_degree": 0, "betweenness_centrality": 0.0,
                "pagerank": 0.0, "successor_count": 0, "predecessor_count": 0,
            }
        )
        node_table["self_loop"] = node_table["self_loop"].fillna(False).astype(bool)

        self._table(node_table.sort_values("pathway_key", ignore_index=True),
                    "pathway_graph_nodes")
        self._table(graph_tools.edge_table(pathway_graph), "pathway_graph_edges")

        active_nodes = [
            node for node, data in pathway_graph.nodes(data=True) if data.get("is_active")
        ]
        active_subgraph = pathway_graph.subgraph(active_nodes)
        active_summary = graph_tools.graph_summary(active_subgraph)

        metrics_rows = [{"scope": "all_participating", "metric": key, "value": value}
                        for key, value in summary.items()]
        metrics_rows += [{"scope": "active_only", "metric": key, "value": value}
                         for key, value in active_summary.items()]
        self._table(pd.DataFrame(metrics_rows), "pathway_graph_metrics")

        exports.write_graphml(pathway_graph, self.paths.outputs / "pathway_graph.graphml")
        self.result.tables_written.append(self.paths.outputs / "pathway_graph.graphml")

        self._summary_sections.append(
            (
                "Pathway graph connectivity (derived metrics)",
                [
                    f"- Graph scope: every active pathway plus any pathway taking part "
                    f"in a resolved transfer. Nodes **{summary['node_count']:,}**, "
                    f"directed edges **{summary['edge_count']:,}**, density "
                    f"{summary['density']:.4f}.",
                    f"- Active-only subgraph: {active_summary['node_count']:,} nodes, "
                    f"{active_summary['edge_count']:,} edges.",
                    f"- Total transfer transitions carried by those edges: "
                    f"**{summary['total_transition_count']:,}**.",
                    f"- Weakly connected components: "
                    f"**{summary['weakly_connected_components']:,}**; largest holds "
                    f"**{summary['largest_weakly_connected_component']:,}** pathways.",
                    f"- Strongly connected components: "
                    f"{summary['strongly_connected_components']:,}, of which "
                    f"**{summary['non_trivial_strongly_connected_components']:,}** "
                    f"contain more than one pathway; largest holds "
                    f"**{summary['largest_strongly_connected_component']:,}**.",
                    f"- Self loops: **{summary['self_loop_count']:,}**. Reciprocal "
                    f"pathway pairs: **{summary['reciprocal_pair_count']:,}**.",
                    f"- Isolated nodes (no transfer in or out): "
                    f"**{summary['isolated_node_count']:,}**.",
                    "- Betweenness is computed unweighted: networkx treats edge weight "
                    "as distance, whereas transition_count means strength, so feeding "
                    "counts in as weights would invert the meaning. PageRank does use "
                    "transition_count, where a larger weight correctly means more flow.",
                ],
            )
        )
        return pathway_graph, node_table

    # -- 14. community detection -------------------------------------------------
    def analyse_communities(self, pathway_graph) -> pd.DataFrame:
        LOGGER.info("--- 14. Graph community detection ---")
        partitions = graph_tools.detect_communities(pathway_graph)
        if not partitions:
            self._note("No community partitions produced (graph had no nodes).")
            return pd.DataFrame()

        membership_rows = []
        summary_frames = []
        for algorithm, membership in partitions.items():
            modularity = graph_tools.modularity_score(pathway_graph, membership)
            for node, community_id in sorted(membership.items()):
                membership_rows.append(
                    {
                        "algorithm": algorithm,
                        "pathway_key": node,
                        "community_id": community_id,
                    }
                )
            community_frame = graph_tools.community_summary(
                pathway_graph, membership, algorithm=algorithm
            )
            community_frame["modularity"] = round(modularity, 6)
            summary_frames.append(community_frame)
            LOGGER.info(
                "  %-20s communities=%-4d modularity=%.4f",
                algorithm,
                community_frame["community_id"].nunique(),
                modularity,
            )

        membership_frame = pd.DataFrame(membership_rows)
        node_lookup = self.extracts["pathways"][["pathway_key", "pathway_id", "pathway_title"]]
        membership_frame = membership_frame.merge(node_lookup, on="pathway_key", how="left")
        self._table(
            membership_frame.sort_values(
                ["algorithm", "community_id", "pathway_key"], ignore_index=True
            ),
            "graph_communities",
        )

        summary_frame = pd.concat(summary_frames, ignore_index=True)
        self._table(summary_frame, "graph_community_summary")

        lines = [
            "- These are **graph-derived communities**: a property of transfer topology "
            "only. They are not clinical families and carry no clinical endorsement.",
        ]
        for algorithm in partitions:
            subset = summary_frame.loc[summary_frame["algorithm"] == algorithm]
            largest = subset.nlargest(3, "pathway_count")
            sizes = ", ".join(
                f"{int(row.pathway_count)}" for row in largest.itertuples()
            )
            singletons = int((subset["pathway_count"] == 1).sum())
            lines.append(
                f"- `{algorithm}`: **{len(subset):,}** communities "
                f"(modularity {subset['modularity'].iloc[0]:.4f}); three largest hold "
                f"{sizes} pathways; {singletons:,} are singletons; median "
                f"internal-edge share "
                f"{subset['internal_edge_percentage'].median():.1f}%."
            )
        self._summary_sections.append(("Graph-derived communities (derived metrics)", lines))
        return membership_frame

    # -- 9/10. symptom group and clinical area cohesion --------------------------
    def analyse_groupings(self, pathway_graph, pathway_frame: pd.DataFrame) -> None:
        LOGGER.info("--- 9. Symptom group analysis ---")
        active = pathway_frame.loc[pathway_frame["is_active"]]

        sg_membership = {
            row.pathway_key: row.symptom_group_id
            for row in active.itertuples()
            if pd.notna(row.symptom_group_id)
        }
        sg_cohesion = graph_tools.group_cohesion(
            pathway_graph, sg_membership, group_label="sg_id"
        )
        sg_cohesion["sg_id"] = sg_cohesion["sg_id"].astype("int64")

        sg_questions = (
            active.groupby("symptom_group_id")
            .agg(
                total_questions_in_member_pathways=("question_count", "sum"),
                total_logic_rows=("logic_row_count", "sum"),
            )
            .reset_index()
            .rename(columns={"symptom_group_id": "sg_id"})
        )
        sg_questions["sg_id"] = sg_questions["sg_id"].astype("int64")

        # Distinct questions across member pathways (not the sum, which double-counts
        # a question reused inside the same symptom group).
        logic = self.extracts["triage_logic"]
        questions_logic = logic.loc[logic["node_kind"] == "question"]
        pathway_sg = active[["pathway_key", "symptom_group_id"]].dropna()
        sg_distinct = (
            questions_logic.merge(pathway_sg, on="pathway_key", how="inner")
            .groupby("symptom_group_id")["question_key"].nunique()
            .reset_index(name="distinct_questions_in_member_pathways")
            .rename(columns={"symptom_group_id": "sg_id"})
        )
        sg_distinct["sg_id"] = sg_distinct["sg_id"].astype("int64")

        sd_counts = self.extracts["symptom_group_discriminator_counts"]
        symptom_groups = self.extracts["symptom_groups"]

        sg_analysis = (
            symptom_groups.merge(sg_cohesion, on="sg_id", how="left")
            .merge(sg_questions, on="sg_id", how="left")
            .merge(sg_distinct, on="sg_id", how="left")
            .merge(sd_counts, on="sg_id", how="left")
        )
        for column in (
            "pathway_count", "pathways_in_graph", "internal_edges", "outgoing_edges",
            "incoming_edges", "internal_transition_count", "outgoing_transition_count",
            "total_questions_in_member_pathways", "total_logic_rows",
            "distinct_questions_in_member_pathways", "combination_count",
            "active_combination_count", "discriminator_count",
        ):
            if column in sg_analysis.columns:
                sg_analysis[column] = sg_analysis[column].fillna(0).astype("int64")
        self._table(
            sg_analysis.sort_values(
                ["pathway_count", "sg_id"], ascending=[False, True], ignore_index=True
            ),
            "symptom_group_analysis",
        )

        LOGGER.info("--- 10. Clinical area analysis ---")
        area_links = self.extracts["pathway_clinical_areas"]
        active_keys = set(active["pathway_key"])
        area_membership: dict[str, set[int]] = {}
        for row in area_links.itertuples():
            if row.pathway_key in active_keys:
                area_membership.setdefault(row.pathway_key, set()).add(row.clinical_area_id)

        area_cohesion = graph_tools.group_cohesion(
            pathway_graph, area_membership, group_label="clinical_area_id"
        )
        if not area_cohesion.empty:
            area_cohesion["clinical_area_id"] = area_cohesion["clinical_area_id"].astype(
                "int64"
            )

        area_questions = (
            questions_logic.merge(
                area_links.loc[area_links["pathway_key"].isin(active_keys)],
                on="pathway_key",
                how="inner",
            )
            .groupby("clinical_area_id")["question_key"].nunique()
            .reset_index(name="distinct_questions")
        )
        area_rows = (
            area_links.loc[area_links["pathway_key"].isin(active_keys)]
            .merge(active[["pathway_key", "question_count", "logic_row_count"]],
                   on="pathway_key", how="left")
            .groupby("clinical_area_id")
            .agg(
                total_questions_in_member_pathways=("question_count", "sum"),
                total_logic_rows=("logic_row_count", "sum"),
            )
            .reset_index()
        )
        area_analysis = (
            self.extracts["clinical_areas"]
            .merge(area_cohesion, on="clinical_area_id", how="left")
            .merge(area_questions, on="clinical_area_id", how="left")
            .merge(area_rows, on="clinical_area_id", how="left")
        )
        for column in (
            "pathway_count", "pathways_in_graph", "internal_edges", "outgoing_edges",
            "incoming_edges", "internal_transition_count", "outgoing_transition_count",
            "distinct_questions", "total_questions_in_member_pathways",
            "total_logic_rows",
        ):
            if column in area_analysis.columns:
                area_analysis[column] = area_analysis[column].fillna(0).astype("int64")
        self._table(
            area_analysis.sort_values(
                ["pathway_count", "clinical_area_id"],
                ascending=[False, True],
                ignore_index=True,
            ),
            "clinical_area_analysis",
        )

        multi_area = (
            area_links.loc[area_links["pathway_key"].isin(active_keys)]
            .groupby("pathway_key")["clinical_area_id"].nunique()
        )
        populated_sg = sg_analysis.loc[sg_analysis["pathway_count"] > 0]
        populated_area = area_analysis.loc[area_analysis["pathway_count"] > 0]

        self._summary_sections.append(
            (
                "Symptom-group and clinical-area cohesion (derived metrics)",
                [
                    f"- Symptom groups with at least one active pathway: "
                    f"**{len(populated_sg):,}** of {len(sg_analysis):,} catalogued.",
                    f"- Symptom-group internal-edge share (share of edges leaving a "
                    f"group's pathways that stay inside the group): median "
                    f"**{populated_sg['internal_edge_percentage'].median():.1f}%**, "
                    f"mean {populated_sg['internal_edge_percentage'].mean():.1f}%.",
                    f"- Symptom groups that are fully self-contained (100% internal): "
                    f"**{int((populated_sg['internal_edge_percentage'] == 100).sum()):,}**; "
                    f"fully outward-facing (0% internal): "
                    f"**{int((populated_sg['internal_edge_percentage'] == 0).sum()):,}**.",
                    f"- Clinical areas with at least one active pathway: "
                    f"**{len(populated_area):,}** of {len(area_analysis):,}.",
                    f"- Clinical-area internal-edge share: median "
                    f"**{populated_area['internal_edge_percentage'].median():.1f}%**, "
                    f"mean {populated_area['internal_edge_percentage'].mean():.1f}%.",
                    f"- Active pathways mapped to more than one clinical area: "
                    f"**{int((multi_area > 1).sum()):,}** "
                    f"(max {int(multi_area.max()) if len(multi_area) else 0} areas), so "
                    f"clinical areas are an overlapping grouping, not a partition.",
                ],
            )
        )

    # -- 11. discriminators ------------------------------------------------------
    def analyse_discriminators(self) -> pd.DataFrame:
        LOGGER.info("--- 11. Symptom discriminator analysis ---")
        mapping = self.extracts["pathway_discriminators"].copy()
        discriminators = self.extracts["symptom_discriminators"]
        pathways = self.extracts["pathways"][["pathway_key", "pathway_id", "pathway_title"]]

        detail = (
            mapping.merge(discriminators, on="sd_id", how="left")
            .merge(pathways, on="pathway_key", how="left")
            .sort_values(["pathway_key", "sd_id"], ignore_index=True)
        )
        self._table(detail, "pathway_discriminators")

        per_pathway = (
            mapping.groupby("pathway_key")["sd_id"].nunique()
            .reset_index(name="unique_discriminators")
            .sort_values(
                ["unique_discriminators", "pathway_key"],
                ascending=[False, True],
                ignore_index=True,
            )
        )
        self._table(per_pathway, "pathway_discriminator_counts")

        reuse = (
            mapping.groupby("sd_id")
            .agg(
                pathway_count=("pathway_key", "nunique"),
                logic_row_count=("logic_row_count", "sum"),
            )
            .reset_index()
            .merge(discriminators, on="sd_id", how="left")
            .sort_values(
                ["pathway_count", "sd_id"], ascending=[False, True], ignore_index=True
            )
        )
        self._table(reuse, "discriminator_reuse")

        distribution = (
            reuse.groupby("pathway_count")
            .size()
            .reset_index(name="number_of_discriminators")
            .sort_values("pathway_count", ignore_index=True)
        )
        self._table(distribution, "discriminator_reuse_distribution")

        per_pathway_stats = graph_tools.describe_distribution(
            per_pathway["unique_discriminators"], percentiles=PERCENTILES
        )
        reuse_stats = graph_tools.describe_distribution(
            reuse["pathway_count"], percentiles=PERCENTILES
        )
        catalogued = len(discriminators)
        self._summary_sections.append(
            (
                "Symptom discriminators (derived metrics)",
                [
                    f"- Discriminators reachable through pathway answers: "
                    f"**{len(reuse):,}** of {catalogued:,} catalogued "
                    f"({100.0 * len(reuse) / max(catalogued, 1):.1f}%).",
                    f"- Discriminators per pathway: median "
                    f"{per_pathway_stats['median']:.0f}, p95 "
                    f"{per_pathway_stats['p95']:.0f}, max "
                    f"{per_pathway_stats['max']:.0f} "
                    f"(across {per_pathway_stats['count']:,} pathways with any).",
                    f"- Pathways per discriminator: median {reuse_stats['median']:.0f}, "
                    f"p95 {reuse_stats['p95']:.0f}, max {reuse_stats['max']:.0f}.",
                ],
            )
        )
        return mapping

    # -- 12. SNOMED --------------------------------------------------------------
    def analyse_snomed(self) -> pd.DataFrame:
        LOGGER.info("--- 12. SNOMED analysis ---")
        mapping = self.extracts["pathway_snomed"].copy()
        pathways = self.extracts["pathways"][["pathway_key", "pathway_id", "pathway_title"]]

        detail = mapping.merge(pathways, on="pathway_key", how="left").sort_values(
            ["pathway_key", "snomed_concept_id"], ignore_index=True
        )
        self._table(detail, "pathway_snomed")

        per_pathway = (
            mapping.groupby("pathway_key")["snomed_concept_id"].nunique()
            .reset_index(name="unique_snomed_concepts")
            .sort_values(
                ["unique_snomed_concepts", "pathway_key"],
                ascending=[False, True],
                ignore_index=True,
            )
        )
        self._table(per_pathway, "pathway_snomed_counts")

        reuse = (
            mapping.groupby("snomed_concept_id")
            .agg(
                pathway_count=("pathway_key", "nunique"),
                logic_row_count=("logic_row_count", "sum"),
                snomed_preferred_term=("snomed_preferred_term", "first"),
                snomed_semantic_tag=("snomed_semantic_tag", "first"),
            )
            .reset_index()
            .sort_values(
                ["pathway_count", "snomed_concept_id"],
                ascending=[False, True],
                ignore_index=True,
            )
        )
        self._table(reuse, "snomed_reuse")

        distribution = (
            reuse.groupby("pathway_count")
            .size()
            .reset_index(name="number_of_concepts")
            .sort_values("pathway_count", ignore_index=True)
        )
        self._table(distribution, "snomed_reuse_distribution")

        catalogue = self.extracts["snomed_catalogue"]
        per_pathway_stats = graph_tools.describe_distribution(
            per_pathway["unique_snomed_concepts"], percentiles=PERCENTILES
        )
        reuse_stats = graph_tools.describe_distribution(
            reuse["pathway_count"], percentiles=PERCENTILES
        )
        self._summary_sections.append(
            (
                "SNOMED coverage (derived metrics)",
                [
                    f"- Distinct SNOMED concepts assigned to answers: "
                    f"**{len(catalogue):,}**; reachable from at least one pathway: "
                    f"**{len(reuse):,}**.",
                    f"- Pathways carrying at least one SNOMED-coded answer: "
                    f"**{per_pathway_stats['count']:,}**.",
                    f"- Concepts per pathway: median {per_pathway_stats['median']:.0f}, "
                    f"p95 {per_pathway_stats['p95']:.0f}, max "
                    f"{per_pathway_stats['max']:.0f}.",
                    f"- Pathways per concept: median {reuse_stats['median']:.0f}, "
                    f"p95 {reuse_stats['p95']:.0f}, max {reuse_stats['max']:.0f}.",
                    "- SNOMED coverage is sparse relative to the answer catalogue, so it "
                    "is a weak partitioning signal on its own. No clinical meaning is "
                    "inferred from concept ids or semantic tags.",
                ],
            )
        )
        return mapping

    # -- 13. similarity foundations ----------------------------------------------
    def analyse_similarity(
        self,
        pathway_frame: pd.DataFrame,
        discriminator_map: pd.DataFrame,
        snomed_map: pd.DataFrame,
        edges: pd.DataFrame,
    ) -> None:
        LOGGER.info("--- 13. Pathway similarity foundations ---")
        active_keys = set(pathway_frame.loc[pathway_frame["is_active"], "pathway_key"])
        logic = self.extracts["triage_logic"]
        question_map = logic.loc[
            (logic["node_kind"] == "question") & logic["pathway_key"].isin(active_keys),
            ["pathway_key", "question_key"],
        ]

        specs = (
            ("pathway_question_similarity", question_map, "question_key", "shared questions"),
            (
                "pathway_sd_similarity",
                discriminator_map.loc[discriminator_map["pathway_key"].isin(active_keys),
                                      ["pathway_key", "sd_id"]],
                "sd_id",
                "shared symptom discriminators",
            ),
            (
                "pathway_snomed_similarity",
                snomed_map.loc[snomed_map["pathway_key"].isin(active_keys),
                               ["pathway_key", "snomed_concept_id"]],
                "snomed_concept_id",
                "shared SNOMED concepts",
            ),
        )

        lines = [
            "- Jaccard similarity is reported per signal with no weighted composite "
            "score; combining them is a Phase 2 decision.",
            "- Only pairs sharing at least one feature are exported. The count of "
            "possible pairs is given below so the density of overlap is visible.",
        ]
        for name, mapping, feature_column, label in specs:
            similarity = graph_tools.jaccard_similarity(
                mapping, entity_column="pathway_key", feature_column=feature_column
            )
            self._table(similarity, name)
            entities = mapping["pathway_key"].nunique()
            possible = graph_tools.pair_count(entities)
            if similarity.empty:
                lines.append(f"- {label}: no overlapping pairs.")
                continue
            high = int((similarity["jaccard_similarity"] >= 0.5).sum())
            lines.append(
                f"- {label}: **{len(similarity):,}** overlapping pairs out of "
                f"{possible:,} possible ({100.0 * len(similarity) / max(possible, 1):.1f}%) "
                f"across {entities:,} pathways; median Jaccard "
                f"{similarity['jaccard_similarity'].median():.3f}, max "
                f"{similarity['jaccard_similarity'].max():.3f}; "
                f"**{high:,}** pairs at Jaccard >= 0.50."
            )

        direct = edges[["source_pathway_key", "target_pathway_key", "transition_count",
                        "branches", "source_question_count"]].copy()
        # A self loop is trivially its own reverse, so it must not be counted as a
        # reciprocal relationship between two pathways. This matches the definition used
        # in graph.graph_summary, keeping the two reported figures consistent.
        edge_pairs = set(
            zip(edges["source_pathway_key"], edges["target_pathway_key"])
        )
        direct["is_self_loop"] = (
            direct["source_pathway_key"] == direct["target_pathway_key"]
        )
        direct["is_reciprocal"] = [
            (not row.is_self_loop)
            and (row.target_pathway_key, row.source_pathway_key) in edge_pairs
            for row in direct.itertuples()
        ]
        self._table(direct, "pathway_direct_link_similarity")
        reciprocal_edges = int(direct["is_reciprocal"].sum())
        lines.append(
            f"- Direct graph links (signal D): **{len(direct):,}** directed pathway "
            f"pairs, of which {int(direct['is_self_loop'].sum()):,} are self loops and "
            f"{reciprocal_edges:,} are reciprocal "
            f"({reciprocal_edges // 2:,} reciprocal pathway pairs)."
        )
        self._summary_sections.append(("Pathway similarity foundations (derived metrics)", lines))

    # -- 17. data quality --------------------------------------------------------
    def analyse_data_quality(self, edges: pd.DataFrame) -> None:
        LOGGER.info("--- 17. Data quality report ---")
        checks = self.extracts["data_quality"].copy()
        transfers = self.extracts["_transfers_resolved"]
        positive = self.extracts["positive_jumps"]

        derived = pd.DataFrame(
            [
                {
                    "check_name": "positive_jump_target_order_not_in_same_pathway",
                    "affected_rows": int((positive["target_resolved"] == 0).sum()),
                },
                {
                    "check_name": "transfer_value_resolves_to_neither",
                    "affected_rows": int(
                        (transfers["resolution_class"] == "neither").sum()
                    ),
                },
                {
                    "check_name": "transfer_value_resolves_to_both",
                    "affected_rows": int((transfers["resolution_class"] == "both").sum()),
                },
                {
                    "check_name": "pathway_transfer_target_order_not_found",
                    "affected_rows": int(
                        (
                            _as_int_flag(
                                transfers.loc[
                                    transfers["resolution_class"].isin(
                                        ["pathway", "both"]
                                    ),
                                    "target_order_resolved",
                                ]
                            )
                            == 0
                        ).sum()
                    ),
                },
                {
                    "check_name": "pathway_transfer_target_is_archived",
                    "affected_rows": int(
                        _as_int_flag(
                            transfers.loc[
                                transfers["resolution_class"].isin(["pathway", "both"]),
                                "target_pathway_is_archived",
                            ]
                        ).sum()
                    ),
                },
                {
                    "check_name": "undocumented_jump_id_values",
                    "affected_rows": int(
                        self.extracts["jump_distribution"]
                        .loc[
                            ~(
                                self.extracts["jump_distribution"]["jump_id"].isin(
                                    DOCUMENTED_JUMP_IDS
                                )
                                | (self.extracts["jump_distribution"]["jump_id"] > 0)
                            ),
                            "row_count",
                        ]
                        .sum()
                    ),
                },
            ]
        )

        combined = pd.concat([checks, derived], ignore_index=True)
        combined["affected_rows"] = combined["affected_rows"].astype("int64")

        # Interpretation is attached explicitly so a large expected count is not read as
        # corruption, and a genuine problem is not buried next to one.
        expected_by_design = {
            "triage_logic_non_tx_node_reference":
                "Expected. QuestionID is a polymorphic node reference; Cx/Dx rows are "
                "care advice and disposition nodes, not missing questions.",
            "answer_never_referenced":
                "Expected in part. The answer catalogue is shared across pathways and "
                "not every catalogued answer is wired into triage logic.",
            "question_never_referenced":
                "Expected in part. Includes archived and superseded questions.",
            "pathway_with_null_module":
                "Module is NULL for every row in tblPathways in this snapshot, so it "
                "carries no analytical signal here.",
            "pathway_with_null_party":
                "Party is NULL for almost every row in this snapshot.",
            "inactive_pathway_with_triage_logic":
                "Archived/deleted pathways retain their triage logic rows.",
        }
        combined["status"] = [
            "expected_by_design" if name in expected_by_design
            else ("clean" if count == 0 else "investigate")
            for name, count in zip(combined["check_name"], combined["affected_rows"])
        ]
        combined["notes"] = [
            expected_by_design.get(name, "") for name in combined["check_name"]
        ]
        combined = combined.sort_values(
            ["status", "affected_rows"], ascending=[True, False], ignore_index=True
        )
        self._table(combined, "data_quality")

        orphans = self.extracts["orphan_tx_question_detail"]
        if not orphans.empty:
            self._table(orphans, "data_quality_orphan_tx_questions")
        self._table(self.extracts["node_prefix_distribution"], "node_prefix_distribution")
        self._table(self.extracts["unreferenced_questions"], "unreferenced_questions")
        self._table(self.extracts["unreferenced_answers"], "unreferenced_answers")

        investigate = combined.loc[
            (combined["status"] == "investigate") & (combined["affected_rows"] > 0)
        ]
        lines = [
            f"- {len(combined):,} checks run; "
            f"**{int((combined['status'] == 'clean').sum()):,}** clean, "
            f"**{len(investigate):,}** with findings to investigate, "
            f"**{int((combined['status'] == 'expected_by_design').sum()):,}** non-zero "
            f"but expected by design (annotated in the CSV).",
        ]
        for row in investigate.head(12).itertuples():
            lines.append(f"- `{row.check_name}`: **{row.affected_rows:,}** rows.")
        lines.append(
            "- No check result is suppressed; `outputs/tables/data_quality.csv` carries "
            "every check with a status and a note."
        )
        self._summary_sections.append(("Data quality (unresolved data issues)", lines))

    # -- 15. charts --------------------------------------------------------------
    def render_charts(
        self,
        pathway_frame: pd.DataFrame,
        node_table: pd.DataFrame,
        community_frame: pd.DataFrame,
    ) -> None:
        LOGGER.info("--- 15. Charts ---")
        exports.apply_chart_theme()
        charts = self.paths.charts
        active = pathway_frame.loc[pathway_frame["is_active"]]
        source_note = (
            "Source: TriageDB (NHS Pathways current-state tables), read-only extract. "
            "Structural counts only."
        )

        def add(name: str, renderer) -> None:
            path = exports.safe_chart(name, renderer)
            if path is not None:
                self.result.charts_written.append(path)

        # 1. Pathways by symptom group
        sg_counts = (
            active.dropna(subset=["symptom_group_id"])
            .groupby(["symptom_group_id", "sg_desc"])
            .size()
            .reset_index(name="pathway_count")
        )
        sg_counts["label"] = sg_counts.apply(
            lambda row: _truncate(f"{row['sg_desc']} (SG{int(row['symptom_group_id'])})"),
            axis=1,
        )
        add(
            "pathways_by_symptom_group",
            lambda: exports.barh_top_n(
                sg_counts,
                label_column="label",
                value_column="pathway_count",
                top_n=30,
                title="Active pathways per symptom group (top 30)",
                subtitle=(
                    f"{len(active):,} active pathways across "
                    f"{sg_counts['symptom_group_id'].nunique():,} populated symptom "
                    f"groups; long tail of small groups not shown"
                ),
                source=source_note,
                path=charts / "pathways_by_symptom_group.png",
                xlabel="Active pathways",
            ),
        )

        # 2. Pathways by clinical area
        area_analysis = pd.read_csv(self.paths.tables / "clinical_area_analysis.csv")
        area_analysis["label"] = area_analysis["clinical_area_description"].apply(_truncate)
        add(
            "pathways_by_clinical_area",
            lambda: exports.barh_top_n(
                area_analysis,
                label_column="label",
                value_column="pathway_count",
                top_n=25,
                title="Active pathways per clinical area",
                subtitle=(
                    "Pathways may belong to several clinical areas, so the column sums "
                    "to more than the pathway count"
                ),
                source=source_note,
                path=charts / "pathways_by_clinical_area.png",
                xlabel="Active pathways",
            ),
        )

        # 3. Pathway question-count distribution
        with_logic = active.loc[active["logic_row_count"] > 0]
        add(
            "pathway_question_count_distribution",
            lambda: exports.histogram(
                with_logic["question_count"],
                bins=40,
                title="Distribution of question count per active pathway",
                subtitle=(
                    f"{len(with_logic):,} active pathways with triage logic; counts "
                    f"include Tx triage questions only"
                ),
                source=source_note,
                path=charts / "pathway_question_count_distribution.png",
                xlabel="Distinct Tx questions in the pathway",
                ylabel="Pathways",
            ),
        )

        # 4. Answer-cardinality distribution
        cardinality = pd.read_csv(self.paths.tables / "answer_cardinality_distribution.csv")
        capped = cardinality.loc[cardinality["answer_count"] <= 20]
        tail = int(cardinality.loc[cardinality["answer_count"] > 20, "number_of_questions"].sum())
        add(
            "answer_cardinality_distribution",
            lambda: exports.bar_distribution(
                capped["answer_count"].tolist(),
                capped["number_of_questions"].tolist(),
                title="Answer cardinality: questions per answer count",
                subtitle=(
                    f"Active questions, catalogued answers. Answer counts above 20 "
                    f"({tail:,} questions) are excluded from this view"
                ),
                source=source_note + " Input to Phase 2 CPT sizing.",
                path=charts / "answer_cardinality_distribution.png",
                xlabel="Catalogued answers for the question",
                ylabel="Questions",
            ),
        )

        # 5. Question reuse distribution
        bands = pd.read_csv(self.paths.tables / "question_reuse_bands.csv")
        add(
            "question_reuse_distribution",
            lambda: exports.bar_distribution(
                bands["band"].tolist(),
                bands["question_count"].tolist(),
                title="Question reuse: how many pathways use each question",
                subtitle=(
                    f"{int(bands['question_count'].sum()):,} distinct Tx questions "
                    f"referenced by triage logic, grouped into reuse bands"
                ),
                source=source_note,
                path=charts / "question_reuse_distribution.png",
                xlabel="Pathways using the question",
                ylabel="Questions",
            ),
        )

        # 6/7. Top 30 by outgoing degree and betweenness
        node_labels = node_table.copy()
        node_labels["label"] = node_labels.apply(
            lambda row: _truncate(f"{row['pathway_id']} {row['pathway_title']}", 58), axis=1
        )
        add(
            "top30_outgoing_degree",
            lambda: exports.barh_top_n(
                node_labels,
                label_column="label",
                value_column="out_degree",
                top_n=30,
                title="Top 30 pathways by outgoing transfer degree",
                subtitle=(
                    "Out-degree counts distinct target pathways reachable by a resolved "
                    "transfer"
                ),
                source=source_note,
                path=charts / "top30_outgoing_degree.png",
                xlabel="Distinct target pathways (out-degree)",
            ),
        )
        add(
            "top30_betweenness_centrality",
            lambda: exports.barh_top_n(
                node_labels,
                label_column="label",
                value_column="betweenness_centrality",
                top_n=30,
                title="Top 30 pathways by betweenness centrality",
                subtitle=(
                    "Unweighted, normalised betweenness on the directed transfer graph; "
                    "high values sit on many shortest transfer routes"
                ),
                source=source_note,
                path=charts / "top30_betweenness_centrality.png",
                xlabel="Betweenness centrality (normalised)",
                value_format="{:.4f}",
            ),
        )

        # 8. Community size distribution
        if not community_frame.empty:
            algorithm = (
                "louvain" if "louvain" in set(community_frame["algorithm"])
                else sorted(community_frame["algorithm"].unique())[0]
            )
            sizes = (
                community_frame.loc[community_frame["algorithm"] == algorithm]
                .groupby("community_id")
                .size()
                .reset_index(name="pathway_count")
                .sort_values("pathway_count", ascending=False, ignore_index=True)
            )
            add(
                "graph_community_size_distribution",
                lambda: exports.bar_distribution(
                    [f"C{int(row.community_id)}" for row in sizes.itertuples()],
                    sizes["pathway_count"].tolist(),
                    title=f"Graph-derived community sizes ({algorithm})",
                    subtitle=(
                        f"{len(sizes):,} communities over "
                        f"{int(sizes['pathway_count'].sum()):,} pathways. Graph-derived "
                        f"from transfer topology only -- not clinical families"
                    ),
                    source=source_note,
                    path=charts / "graph_community_size_distribution.png",
                    xlabel="Community",
                    ylabel="Pathways",
                    annotate=len(sizes) <= 40,
                    rotate_labels=90 if len(sizes) > 25 else 0,
                    figsize=(12.5, 5.4),
                ),
            )

        # 9. Symptom-group internal vs external edge percentage
        sg_analysis = pd.read_csv(self.paths.tables / "symptom_group_analysis.csv")
        eligible = sg_analysis.loc[
            (sg_analysis["pathway_count"] >= 2)
            & sg_analysis["internal_edge_percentage"].notna()
        ]
        add(
            "symptom_group_edge_cohesion",
            lambda: exports.stacked_share_barh(
                eligible,
                label_column="sg_desc",
                primary_column="internal_edge_percentage",
                primary_label="Internal to the symptom group",
                secondary_label="Leaving the symptom group",
                title="Symptom-group cohesion: internal vs external transfer edges",
                subtitle=(
                    f"Top 30 of {len(eligible):,} symptom groups with 2+ active pathways"
                ),
                source=source_note,
                path=charts / "symptom_group_edge_cohesion.png",
                top_n=30,
            ),
        )

    # -- 18. summary report ------------------------------------------------------
    def write_summary_report(self, *, charts_rendered: bool) -> Path:
        LOGGER.info("--- 18. Summary report ---")
        generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        lines = [
            "# NHS Pathways Structural Analysis - Phase 1 Summary",
            "",
            f"Generated {generated} from a read-only extract of the local SQL Server "
            "`TriageDB` snapshot.",
            "",
            "## Scope and status",
            "",
            "This report contains **factual findings only**. It deliberately makes no "
            "architectural recommendation: the monolithic vs federated vs specialised "
            "Bayesian Network comparison is Phase 2 work and is not attempted here.",
            "",
            "Findings are labelled as:",
            "",
            "- **measured facts** - counts read directly from the database;",
            "- **derived metrics** - computed from those facts by this workbench, using "
            "the definitions stated alongside each metric;",
            "- **unresolved data issues** - things that did not resolve, reported rather "
            "than dropped.",
            "",
            "No NHS Pathways content is reproduced in this report beyond identifiers and "
            "aggregate counts.",
            "",
        ]
        for heading, bullets in self._summary_sections:
            lines.append(f"## {heading}")
            lines.append("")
            lines.extend(bullets)
            lines.append("")

        lines.extend(
            [
                "## Definitions used",
                "",
                "- **Active** pathway / question / disposition: `IsArchived = 0` AND "
                "`FlagForDeletion = 0`. `tblSymptomGroups` and "
                "`tblSymptomDiscriminators` have no `FlagForDeletion`, so their `Active` "
                "and `IsArchived` flags are reported separately rather than combined.",
                "- **Order position**: a `(PathwayID, OrderNumber)` pair. Each was "
                "verified to carry exactly one distinct `QuestionID`, so a position is a "
                "single decision node.",
                "- **Branching factor**: distinct `AnswerNumber` values at an order "
                "position, averaged over the pathway's positions.",
                "- **Pathway transfer**: a T1-T4 value of the form "
                "`<PathwayID>.<OrderNumber>` whose pathway part resolves against "
                "`tblPathways`.",
                "- **Graph edge**: a resolved pathway transfer, aggregated to one edge "
                "per ordered `(source, target)` pathway pair.",
                "- **Internal-edge percentage**: for a group of pathways, "
                "`internal / (internal + outgoing) * 100` - the share of edges leaving "
                "the group's pathways that stay within the group.",
                "",
                "## Artefacts produced by this run",
                "",
                f"- `outputs/tables/`: {len([p for p in self.result.tables_written if p.suffix == '.csv'])} CSV tables.",
                "- `data/processed/pathway_inventory.parquet`: pathway inventory.",
                "- `outputs/pathway_graph.graphml`: the directed pathway graph.",
                (
                    f"- `outputs/charts/`: {len(self.result.charts_written)} charts."
                    if charts_rendered
                    else "- `outputs/charts/`: not rendered (`--no-charts`)."
                ),
                "",
                "The full pathway graph is not rendered as a single node-link diagram: "
                f"at {self.result.graph_summary.get('node_count', 0):,} nodes and "
                f"{self.result.graph_summary.get('edge_count', 0):,} edges it would be "
                "unreadable. `pathway_graph.graphml` is provided for interactive "
                "inspection instead.",
                "",
                "## Suggested Phase 2 entry points",
                "",
                "Phase 1 has not been reviewed yet, so this is a list of what the "
                "measurements make answerable next, not a plan:",
                "",
                "- Map Pathways structures to candidate Bayesian variables, deciding "
                "explicitly how polymorphic `QuestionID` node kinds are treated.",
                "- Compare literal, deduplicated and clinically-normalised BN "
                "representations, using the question-reuse tables as the deduplication "
                "evidence.",
                "- Size a monolithic BN and analyse CPT growth using "
                "`answer_cardinality*.csv`.",
                "- Design candidate federated families and measure boundary nodes, using "
                "the cohesion and community tables as starting partitions.",
                "",
            ]
        )
        path = self.paths.outputs / "phase1_summary.md"
        path.write_text("\n".join(lines), encoding="utf-8")
        LOGGER.info("Wrote %s", path.name)
        return path

    # -- orchestration -----------------------------------------------------------
    def run(self, *, render_charts: bool = True) -> RunResult:
        """Execute the whole of Phase 1."""
        started = time.perf_counter()
        self.paths.ensure_directories()

        self.extract()
        self.analyse_inventory()
        self.analyse_jumps()
        edges = self.analyse_transfers()
        pathway_frame = self.analyse_pathways(edges)
        self.analyse_question_reuse()
        self.analyse_answer_cardinality()
        pathway_graph, node_table = self.analyse_graph(edges, pathway_frame)
        community_frame = self.analyse_communities(pathway_graph)
        self.analyse_groupings(pathway_graph, pathway_frame)
        discriminator_map = self.analyse_discriminators()
        snomed_map = self.analyse_snomed()
        self.analyse_similarity(pathway_frame, discriminator_map, snomed_map, edges)
        self.analyse_data_quality(edges)

        if render_charts:
            self.render_charts(pathway_frame, node_table, community_frame)
        else:
            LOGGER.info("--- 15. Charts skipped (--no-charts) ---")

        self.write_summary_report(charts_rendered=render_charts)
        self.result.elapsed_seconds = time.perf_counter() - started
        return self.result


def _as_int_flag(series: pd.Series) -> pd.Series:
    """Coerce a SQL Server ``bit`` column to a 0/1 integer series.

    pyodbc can surface ``bit`` as an object column holding ``bool``/``None``. Calling
    ``.fillna(0).astype(int)`` on that works today but is deprecated in pandas, so the
    conversion goes through ``to_numeric`` instead.
    """
    return pd.to_numeric(series, errors="coerce").fillna(0).astype("int64")


def _truncate(text: object, limit: int = 46) -> str:
    """Shorten a label for chart axes, preserving readability."""
    value = "" if text is None else str(text)
    return value if len(value) <= limit else value[: limit - 1].rstrip() + "…"


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
    parser = argparse.ArgumentParser(
        prog="python -m pathways_analysis.profiling",
        description=(
            "Phase 1 structural analysis of the NHS Pathways dataset. Read-only: this "
            "command never modifies the source database."
        ),
    )
    parser.add_argument(
        "--no-charts",
        action="store_true",
        help="Skip chart rendering. All tables and graph artefacts are still written.",
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
    """Entry point for ``python -m pathways_analysis.profiling``."""
    args = build_argument_parser().parse_args(argv)
    configure_logging(args.log_level)

    paths = Paths.discover()
    env_file = load_dotenv_if_present(paths)
    if env_file:
        LOGGER.info("Loaded environment from %s", env_file)

    try:
        settings = DatabaseSettings.from_env()
    except ConfigurationError as exc:
        LOGGER.error("Configuration error: %s", exc)
        return 2

    database = PathwaysDatabase(settings, paths)
    try:
        info = database.validate_connectivity()
    except DatabaseConnectionError as exc:
        # Fail loudly: a partial run against an unreachable database would produce a
        # misleading evidence base.
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

    profiler = Phase1Profiler(database, paths)
    try:
        result = profiler.run(render_charts=not args.no_charts)
    except DatabaseConnectionError as exc:
        LOGGER.error("Database failure during analysis: %s", exc)
        return 3
    finally:
        database.dispose()

    _print_summary(result, paths)
    return 0


def _print_summary(result: RunResult, paths: Paths) -> None:
    """Print a concise run summary to stdout."""
    graph_summary = result.graph_summary
    inventory = result.inventory
    csv_count = len([p for p in result.tables_written if p.suffix == ".csv"])

    print()
    print("=" * 78)
    print("NHS PATHWAYS STRUCTURAL ANALYSIS - PHASE 1 COMPLETE")
    print("=" * 78)
    print(f"  Active pathways            {inventory.get('pathways_active', 0):>10,}")
    print(f"  Active questions           {inventory.get('questions_active', 0):>10,}")
    print(f"  Answers                    {inventory.get('answers_total', 0):>10,}")
    print(f"  Triage logic rows          {inventory.get('triage_logic_rows', 0):>10,}")
    print(f"  Active dispositions        {inventory.get('dispositions_active', 0):>10,}")
    print(f"  Symptom groups             {inventory.get('symptom_groups_total', 0):>10,}")
    print(f"  Clinical areas             {inventory.get('clinical_areas_total', 0):>10,}")
    print("-" * 78)
    print(f"  Graph nodes                {graph_summary.get('node_count', 0):>10,}")
    print(f"  Graph edges                {graph_summary.get('edge_count', 0):>10,}")
    print(f"  Graph density              {graph_summary.get('density', 0):>10.4f}")
    print(
        f"  Weakly connected comps     "
        f"{graph_summary.get('weakly_connected_components', 0):>10,}"
        f"   (largest {graph_summary.get('largest_weakly_connected_component', 0):,})"
    )
    print("-" * 78)
    print(f"  CSV tables written         {csv_count:>10,}   -> outputs/tables/")
    print(f"  Charts written             {len(result.charts_written):>10,}   -> outputs/charts/")
    print("  Graph artefact                        1   -> outputs/pathway_graph.graphml")
    print("  Parquet datasets                      1   -> data/processed/")
    print("  Summary report                        1   -> outputs/phase1_summary.md")
    print("-" * 78)
    print(f"  Elapsed                    {result.elapsed_seconds:>10.1f}s")
    print("=" * 78)
    print("Phase 1 is evidence gathering only. No architectural recommendation is made.")
    print(f"Review: {paths.outputs / 'phase1_summary.md'}")
    print()


if __name__ == "__main__":
    raise SystemExit(main())
