# NHS Pathways Structural Analysis - Phase 1 Summary

Generated 2026-11-04 17:44 UTC from a read-only extract of the local SQL Server `TriageDB` snapshot.

## Scope and status

This report contains **factual findings only**. It deliberately makes no architectural recommendation: the monolithic vs federated vs specialised Bayesian Network comparison is Phase 2 work and is not attempted here.

Findings are labelled as:

- **measured facts** - counts read directly from the database;
- **derived metrics** - computed from those facts by this workbench, using the definitions stated alongside each metric;
- **unresolved data issues** - things that did not resolve, reported rather than dropped.

No NHS Pathways content is reproduced in this report beyond identifiers and aggregate counts.

## Dataset inventory (measured facts)

- Active pathways: **815** of 845 catalogued (5 archived, 27 flagged for deletion).
- Active questions: **4,491** of 5,020 catalogued.
- Answers: **13,609**.
- Triage logic rows: **140,669**.
- Active dispositions: **209** of 210; 682 disposition items; 9 Dx ranks.
- Symptom groups: **365** (219 flagged Active).
- Symptom discriminators: **1,156** (443 flagged Active).
- Clinical areas: **22** with 921 pathway links.
- SNOMED: 588 answer assignments covering 299 distinct concepts.
- Distinct pathways present in triage logic: 840; distinct order positions: 56,695.

## JumpID classification (measured facts)

- Positive (intra-pathway) jumps: **110,728** rows; 81,651 forward, 29,077 backward.
- Unresolved positive-jump targets: **0** (every positive JumpID resolves to an existing OrderNumber in its own pathway).
- JumpID values not documented in the supplied Pathways description: `0` (2 rows).
- T1-T4 are populated for JumpID -1, -3 and -6 only. JumpID -2, -4, -5, -9 and 0 carry no transfer payload, so they are control behaviour that cannot be resolved to a target from tblTriageLogic alone and are **not** treated as graph edges.

## Transfer resolution (measured facts)

- Unpivoted transfer values (T1-T4, non-empty): **95,092**.
- Resolve to a pathway: **39,890**; to a disposition: **55,198**; to both: **0**; to neither: **4**.
- Distinct unresolved transfer values: **1** (listed in full in `outputs/tables/unresolved_transfer_values.csv`).
- Transfer grammar is measured, not assumed: a value containing `.` is `<PathwayID>.<OrderNumber>` and denotes a pathway transfer; a value without `.` is a DispositionCode. No PathwayID or DispositionCode in the database contains a `.`, so the split is unambiguous.
- **JumpID = -1 is mixed**: it carries disposition codes on some rows and pathway transfers on others. JumpID = -3 and -6 carry pathway transfers only. This contradicts treating -1 alone as the transfer mechanism.
- Pathway transfers pointing at an OrderNumber that does not exist in the target pathway: **8**.
- Pathway transfers whose target pathway is archived: **0**.

## Pathway size distribution (derived metrics)

- Active pathways with triage logic: **815**.
- Questions per pathway: min 0, median 25, mean 30.7, p90 64, p95 80, p99 104, max 174.
- Triage logic rows per pathway: median 118, p95 482, max 953.
- Branching factor (mean distinct answers per order position): median 2.36, p95 4.26, max 7.00.
- Node counts are split by kind because `tblTriageLogic.QuestionID` is polymorphic: `QuestionCount` counts only `Tx` triage questions, excluding `Cx` care-advice and `Dx` disposition node references.

## Question reuse (derived metrics)

- Distinct `Tx` questions referenced by triage logic: **3,968**.
- Pathways per question: median 2, mean 6.60, p90 14, p99 64, max 527.
- Used by exactly one pathway: **1,486** questions (37.4%). Used by 26+ pathways: **172**.
- Most reused question: `TX221449` in 527 pathways.
- Reuse is the quantity that decides whether a federated design can keep families independent; it is reported here without interpretation.

## Answer cardinality (derived metrics; input to Phase 2 CPT sizing)

- Active questions: **4,491**. Answers per question: min 1, median 3, mean 2.67, p90 4, p95 5, max 7.
- Questions whose catalogued answer count differs from the number of answers actually exercised in triage logic: **523**. Both counts are exported, because they give different CPT state-space sizes.
- Questions with no catalogued answers at all: **0**.

## Pathway graph connectivity (derived metrics)

- Graph scope: every active pathway plus any pathway taking part in a resolved transfer. Nodes **838**, directed edges **3,478**, density 0.0050.
- Active-only subgraph: 815 nodes, 3,398 edges.
- Total transfer transitions carried by those edges: **39,890**.
- Weakly connected components: **38**; largest holds **767** pathways.
- Strongly connected components: 790, of which **3** contain more than one pathway; largest holds **43**.
- Self loops: **295**. Reciprocal pathway pairs: **20**.
- Isolated nodes (no transfer in or out): **21**.
- Betweenness is computed unweighted: networkx treats edge weight as distance, whereas transition_count means strength, so feeding counts in as weights would invert the meaning. PageRank does use transition_count, where a larger weight correctly means more flow.

## Graph-derived communities (derived metrics)

- These are **graph-derived communities**: a property of transfer topology only. They are not clinical families and carry no clinical endorsement.
- `louvain`: **50** communities (modularity 0.6729); three largest hold 123, 107, 107 pathways; 34 are singletons; median internal-edge share 100.0%.
- `networkx_louvain`: **50** communities (modularity 0.6713); three largest hold 125, 102, 98 pathways; 34 are singletons; median internal-edge share 100.0%.
- `greedy_modularity`: **48** communities (modularity 0.6602); three largest hold 145, 131, 111 pathways; 34 are singletons; median internal-edge share 100.0%.

## Symptom-group and clinical-area cohesion (derived metrics)

- Symptom groups with at least one active pathway: **224** of 365 catalogued.
- Symptom-group internal-edge share (share of edges leaving a group's pathways that stay inside the group): median **0.0%**, mean 13.8%.
- Symptom groups that are fully self-contained (100% internal): **10**; fully outward-facing (0% internal): **107**.
- Clinical areas with at least one active pathway: **22** of 22.
- Clinical-area internal-edge share: median **18.1%**, mean 18.5%.
- Active pathways mapped to more than one clinical area: **126** (max 21 areas), so clinical areas are an overlapping grouping, not a partition.

## Symptom discriminators (derived metrics)

- Discriminators reachable through pathway answers: **508** of 1,156 catalogued (43.9%).
- Discriminators per pathway: median 7, p95 16, max 50 (across 658 pathways with any).
- Pathways per discriminator: median 2, p95 32, max 527.

## SNOMED coverage (derived metrics)

- Distinct SNOMED concepts assigned to answers: **299**; reachable from at least one pathway: **297**.
- Pathways carrying at least one SNOMED-coded answer: **626**.
- Concepts per pathway: median 9, p95 33, max 61.
- Pathways per concept: median 10, p95 103, max 331.
- SNOMED coverage is sparse relative to the answer catalogue, so it is a weak partitioning signal on its own. No clinical meaning is inferred from concept ids or semantic tags.

## Pathway similarity foundations (derived metrics)

- Jaccard similarity is reported per signal with no weighted composite score; combining them is a Phase 2 decision.
- Only pairs sharing at least one feature are exported. The count of possible pairs is given below so the density of overlap is visible.
- shared questions: **187,760** overlapping pairs out of 318,801 possible (58.9%) across 799 pathways; median Jaccard 0.036, max 1.000; **1,994** pairs at Jaccard >= 0.50.
- shared symptom discriminators: **151,560** overlapping pairs out of 201,295 possible (75.3%) across 635 pathways; median Jaccard 0.143, max 1.000; **6,065** pairs at Jaccard >= 0.50.
- shared SNOMED concepts: **110,315** overlapping pairs out of 185,745 possible (59.4%) across 610 pathways; median Jaccard 0.088, max 1.000; **2,908** pairs at Jaccard >= 0.50.
- Direct graph links (signal D): **3,478** directed pathway pairs, of which 295 are self loops and 40 are reciprocal (20 reciprocal pathway pairs).

## Data quality (unresolved data issues)

- 30 checks run; **16** clean, **8** with findings to investigate, **6** non-zero but expected by design (annotated in the CSV).
- `active_question_never_referenced`: **523** rows.
- `active_pathway_with_no_clinical_area`: **439** rows.
- `pathway_with_null_symptom_group`: **161** rows.
- `active_pathway_with_null_symptom_group`: **150** rows.
- `disposition_dx_rank_not_catalogued`: **79** rows.
- `pathway_transfer_target_order_not_found`: **8** rows.
- `transfer_value_resolves_to_neither`: **4** rows.
- `undocumented_jump_id_values`: **2** rows.
- No check result is suppressed; `outputs/tables/data_quality.csv` carries every check with a status and a note.

## Definitions used

- **Active** pathway / question / disposition: `IsArchived = 0` AND `FlagForDeletion = 0`. `tblSymptomGroups` and `tblSymptomDiscriminators` have no `FlagForDeletion`, so their `Active` and `IsArchived` flags are reported separately rather than combined.
- **Order position**: a `(PathwayID, OrderNumber)` pair. Each was verified to carry exactly one distinct `QuestionID`, so a position is a single decision node.
- **Branching factor**: distinct `AnswerNumber` values at an order position, averaged over the pathway's positions.
- **Pathway transfer**: a T1-T4 value of the form `<PathwayID>.<OrderNumber>` whose pathway part resolves against `tblPathways`.
- **Graph edge**: a resolved pathway transfer, aggregated to one edge per ordered `(source, target)` pathway pair.
- **Internal-edge percentage**: for a group of pathways, `internal / (internal + outgoing) * 100` - the share of edges leaving the group's pathways that stay within the group.

## Artefacts produced by this run

- `outputs/tables/`: 42 CSV tables.
- `data/processed/pathway_inventory.parquet`: pathway inventory.
- `outputs/pathway_graph.graphml`: the directed pathway graph.
- `outputs/charts/`: 9 charts.

The full pathway graph is not rendered as a single node-link diagram: at 838 nodes and 3,478 edges it would be unreadable. `pathway_graph.graphml` is provided for interactive inspection instead.

## Suggested Phase 2 entry points

Phase 1 has not been reviewed yet, so this is a list of what the measurements make answerable next, not a plan:

- Map Pathways structures to candidate Bayesian variables, deciding explicitly how polymorphic `QuestionID` node kinds are treated.
- Compare literal, deduplicated and clinically-normalised BN representations, using the question-reuse tables as the deduplication evidence.
- Size a monolithic BN and analyse CPT growth using `answer_cardinality*.csv`.
- Design candidate federated families and measure boundary nodes, using the cohesion and community tables as starting partitions.
