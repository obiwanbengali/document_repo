# NHS Pathways Bayesian Family Discovery — Phase 2 Evidence Report

Generated 2026-11-04 17:46 UTC from a read-only extract of the local SQL Server `TriageDB` snapshot.

## How to read this report

Every statement carries an evidence class:

- **measured** — a count read directly from TriageDB
- **derived** — computed by this workbench from measured values, under the definition stated in `outputs/phase2/reports/metric_definitions.csv`
- **algorithmic** — produced by a community-detection or clustering algorithm: true of the algorithm and the transfer graph, and **not** a clinical statement
- **assumption** — a configured threshold, weight or scope choice that could reasonably have been made differently; every one is in `config/family_discovery.yaml`
- **interpretation** — a reading of the evidence, attributed as such

> **Scope boundary.** Phase 2 answers *what clinically and structurally coherent Bayesian Network families could be created, how much they overlap, and what shared structures they would need*. It does **not** size a network, estimate infrastructure or cost, or compare monolithic against federated. Those are Phase 3.

> **No candidate family in this report is clinically endorsed.** A grouping produced by an algorithm is a structural candidate until a clinician has reviewed it. `outputs/phase2/clinical_review_pack.md` is the artefact for that review.

## 1. Purpose

To establish, from measured structure, which groupings of NHS Pathways could form coherent Bayesian Network families; how much those groupings overlap; and which questions, symptom discriminators, SNOMED concepts and dispositions would have to be shared between them.

Three kinds of candidate grouping are generated independently and then compared, rather than one being assumed:

1. **NHS-native** groupings that already exist in the data (symptom group, clinical area, area group, trauma, age, gender, module).
2. **Graph-derived** communities of the pathway-to-pathway transfer graph.
3. **Hybrid** proposals that combine the two under declared rules.

- **[assumption]** Generating candidates three ways is itself a design choice: it exists so that agreement between independent methods is available as evidence, and so no single algorithm's output is mistaken for the answer.

## 2. Dataset basis

- **[measured]** Family-membership scope: **815 pathways** (`scope.pathway_scope = active`, which means `IsArchived = 0 AND FlagForDeletion = 0`, the Phase 1 definition).
- **[measured]** Transfer graph: **838 nodes** and **3,478 directed edges**. The graph spans every active pathway plus any pathway taking part in a resolved transfer, so it is wider than the membership scope.
- **[assumption]** An edge from an in-scope pathway to an out-of-scope one is counted as **external** to whichever family holds the source, not dropped. Dropping it would inflate every internal-edge percentage.
- **[measured]** Edge-list cross-check: the Python derivation and the independent server-side derivation (`sql/11_family_transitions.sql`) **agree** — 3,478 vs 3,478 edges, 39,890 vs 39,890 transitions.

### Metadata available for grouping

| Field | Pathways populated | Missing | Coverage % | Distinct values | Can separate |
|---|---|---|---|---|---|
| Module | 0 | 815 | 0 | 0 | no |
| Party | 12 | 803 | 1.47 | 2 | yes |
| SymptomGroupId | 665 | 150 | 81.6 | 224 | yes |
| ClinicalAreas | 376 | 439 | 46.13 | 22 | yes |
| AreaGroups | 376 | 439 | 46.13 | 8 | yes |
| AgeIds | 796 | 19 | 97.67 | 5 | yes |
| GenderIds | 796 | 19 | 97.67 | 2 | yes |
| TraumaIds | 449 | 366 | 55.09 | 2 | yes |
| QuestionIDs | 799 | 16 | 98.04 | 3787 | yes |
| SymptomDiscriminatorIds | 635 | 180 | 77.91 | 469 | yes |
| SnomedConceptIds | 610 | 205 | 74.85 | 297 | yes |
| DispositionIds | 719 | 96 | 88.22 | 194 | yes |


- **[assumption]** **Can separate** means the field has at least two distinct values, so a grouping built on it would produce more than one family. It is a mechanical test and not a judgement of usefulness: `Party` passes it on 12 of 815 pathways, which is not enough to group anything.

- **[measured]** `Module` is NULL for every row of `tblPathways` in this snapshot and `Party` for almost every row, so neither can separate pathways. Both are still attempted and reported as unusable rather than omitted.
- **[measured]** Age, gender and trauma metadata **do** exist, in `tblPathway2Ages`, `tblPathway2Genders` and `tblPathway2Trauma`. Phase 1 did not use them. All three are many-to-many, so none of them is a partition.

## 3. Family discovery methods

### Candidate strategies generated

| Strategy | Basis | Families | Pathways | Overlapping | How it was produced |
|---|---|---|---|---|---|
| native_symptom_group | nhs_native | 225 | 815 | no | NHS SymptomGroupId as stored on tblPathways. |
| native_clinical_area | nhs_native | 23 | 815 | yes | NHS ClinicalAreaID from tblPathway2ClinicalAreas. Overlapping by design: a pathway may map to several clinical areas. |
| native_area_group | nhs_native | 9 | 815 | yes | tblClinicalAreas.AreaGroup, the anatomical grouping above clinical area. Overlapping, because a pathway's clinical areas may span area groups. |
| native_trauma | nhs_native | 3 | 815 | yes | tblPathway2Trauma tags. Overlapping: a pathway may carry both trauma and non-trauma. |
| native_age_group | nhs_native | 6 | 815 | yes | tblPathway2Ages bands. Overlapping: most pathways carry several bands. |
| native_gender | nhs_native | 3 | 815 | yes | tblPathway2Genders tags. Overlapping. |
| native_module | nhs_native | 1 | 815 | no | tblPathways.Module. |
| graph_louvain | graph_derived | 48 | 815 | no | louvain communities of the undirected projection of the pathway transfer graph. Graph-derived: a property of transfer topology only, with no clinical endorsement. |
| graph_networkx_louvain | graph_derived | 48 | 815 | no | networkx_louvain communities of the undirected projection of the pathway transfer graph. Graph-derived: a property of transfer topology only, with no clinical endorsement. |
| graph_leiden | graph_derived | 49 | 815 | no | leiden communities of the undirected projection of the pathway transfer graph. Graph-derived: a property of transfer topology only, with no clinical endorsement. |
| graph_greedy_modularity | graph_derived | 46 | 815 | no | greedy_modularity communities of the undirected projection of the pathway transfer graph. Graph-derived: a property of transfer topology only, with no clinical endorsement. |
| graph_label_propagation | graph_derived | 92 | 815 | no | label_propagation communities of the undirected projection of the pathway transfer graph. Graph-derived: a property of transfer topology only, with no clinical endorsement. |
| graph_strongly_connected | graph_derived | 767 | 815 | no | strongly_connected communities of the undirected projection of the pathway transfer graph. Graph-derived: a property of transfer topology only, with no clinical endorsement. |
| hybrid_a | hybrid | 34 | 815 | no | Graph communities (louvain) as the primary grouping, split on symptom_group where mean pairwise symptom-discriminator Jaccard < 0.2, with communities below 5 pathways absorbed by affinity. |
| hybrid_b | hybrid | 227 | 815 | no | NHS-native grouping as primary (SymptomGroupId, else the most specific clinical area), split on graph subcommunities where the group's internal-edge percentage < 25.0%. |
| hybrid_c | hybrid | 9 | 815 | no | louvain clustering of a weighted similarity graph (disposition=0.10, graph=0.35, question=0.20, snomed=0.15, symptom_discriminator=0.20) thresholded at 0.12. The weighting is an experimental baseline and is not clinically validated. |

- **[assumption]** A pathway is **not** assumed to belong to exactly one family. Membership is held long-format, so an overlapping strategy (clinical area, area group, trauma, age, gender) places a pathway in every family it qualifies for, and `candidate_family_membership.csv` allows several rows per pathway.
- **[assumption]** Excluded from the full metric battery: `graph_strongly_connected` (strongly connected components are a connectivity diagnostic, not a candidate family set: almost every component is a singleton, so overlap and routing metrics over them would measure the partition's triviality rather than any family structure. The component counts are still reported in community_method_comparison.csv and graph_community_summary.csv); `native_module` (tblPathways.Module carries no value in this snapshot, so the grouping has one family and cannot separate pathways).

## 4. NHS-native grouping findings

| Grouping | Groups | Median size | Max size | Median internal-edge % | Median boundary % | Mean SD Jaccard |
|---|---|---|---|---|---|---|
| native_age_group | 6 | 245 | 440 | 74.36 | 45.85 | 0.06 |
| native_area_group | 9 | 72 | 439 | 19.6 | 95.65 | 0.148 |
| native_clinical_area | 23 | 39 | 439 | 18.18 | 96.43 | 0.172 |
| native_gender | 3 | 596 | 647 | 89.87 | 30.37 | 0.053 |
| native_symptom_group | 225 | 2 | 150 | 0 | 100 | 0.61 |
| native_trauma | 3 | 318 | 366 | 38.62 | 85.22 | 0.127 |

- **[derived]** `native_age_group`: **6** groups; median internal-edge share **74.4%**. Groups keeping at least half their edges inside the group: 5; keeping none: 1.
- **[derived]** `native_area_group`: **9** groups; median internal-edge share **19.6%**. Groups keeping at least half their edges inside the group: 1; keeping none: 0.
- **[derived]** `native_clinical_area`: **23** groups; median internal-edge share **18.2%**. Groups keeping at least half their edges inside the group: 1; keeping none: 1.
- **[derived]** `native_gender`: **3** groups; median internal-edge share **89.9%**. Groups keeping at least half their edges inside the group: 2; keeping none: 1.
- **[derived]** `native_symptom_group`: **225** groups; median internal-edge share **0.0%**. Groups keeping at least half their edges inside the group: 19; keeping none: 107.
- **[derived]** `native_trauma`: **3** groups; median internal-edge share **38.6%**. Groups keeping at least half their edges inside the group: 1; keeping none: 0.
- **[measured]** `native_symptom_group`: 150 of 815 in-scope pathways carry no SymptomGroupId value and are held in an explicit UNASSIGNED family rather than dropped.
- **[measured]** `native_clinical_area`: 439 of 815 in-scope pathways carry no ClinicalAreaIds value and are held in an explicit UNASSIGNED family rather than dropped.
- **[measured]** `native_area_group`: 439 of 815 in-scope pathways carry no AreaGroups value and are held in an explicit UNASSIGNED family rather than dropped.
- **[measured]** `native_area_group`: 8 distinct AreaGroup values exist across 22 clinical areas.
- **[measured]** `native_trauma`: 366 of 815 in-scope pathways carry no TraumaIds value and are held in an explicit UNASSIGNED family rather than dropped.
- **[measured]** `native_age_group`: 19 of 815 in-scope pathways carry no AgeIds value and are held in an explicit UNASSIGNED family rather than dropped.
- **[measured]** `native_gender`: 19 of 815 in-scope pathways carry no GenderIds value and are held in an explicit UNASSIGNED family rather than dropped.
- **[measured]** `native_module`: 815 of 815 in-scope pathways carry no Module value and are held in an explicit UNASSIGNED family rather than dropped.
- **[measured]** `native_module`: Module yields 1 group(s) in this snapshot, so it cannot separate pathways and is not analytically usable as a grouping.

## 5. Graph-derived community findings

| Method | Ran | Communities | Modularity | Largest | Singletons | Median internal-edge % | ARI vs primary |
|---|---|---|---|---|---|---|---|
| louvain | yes | 50 | 0.673 | 123 | 34 | 100 | 1 |
| networkx_louvain | yes | 50 | 0.671 | 125 | 34 | 100 | 0.752 |
| leiden | yes | 51 | 0.674 | 142 | 34 | 100 | 0.703 |
| greedy_modularity | yes | 48 | 0.66 | 145 | 34 | 100 | 0.607 |
| label_propagation | yes | 95 | 0.621 | 114 | 34 | 54.77 | 0.468 |
| strongly_connected | yes | 790 | 0.02 | 43 | 787 | 0 | 0.041 |

- **[algorithmic]** These are **graph-derived communities**: a property of the transfer topology only. None is a clinical family, and none carries clinical endorsement.
- **[assumption]** `louvain` is used as the graph-derived input to Hybrid A and as the graph-derived representative in strategy comparison. That is a configured choice, not a finding that it is best.
- **[derived]** Agreement between methods (adjusted Rand index against `louvain`) ranges from **0.041** to **0.752**. High agreement means the community structure is a property of the graph rather than of one algorithm's objective function.
- **[derived]** For the primary method, the mean dominant-symptom-group share within a community is **0.37** and the mean dominant-clinical-area share is **0.33** — the extent to which graph communities already track NHS metadata.

## 6. Clinical-feature overlap findings

| Evidence dimension | Pathways | Overlapping pairs | Possible pairs | % of pairs | Median Jaccard | Pairs ≥ 0.50 |
|---|---|---|---|---|---|---|
| question | 799 | 187760 | 318801 | 58.9 | 0.036 | 1994 |
| symptom_discriminator | 635 | 151560 | 201295 | 75.29 | 0.143 | 6065 |
| snomed | 610 | 110315 | 185745 | 59.39 | 0.088 | 2908 |
| disposition | 719 | 182782 | 258121 | 70.81 | 0.2 | 15308 |
| clinical_area | 376 | 14915 | 70500 | 21.16 | 0.25 | 5139 |
| graph_relationship | 815 | 42189 | 331705 | 12.72 | n/a | 1224 |

- **[assumption]** The six evidence dimensions are kept **separate**. They are combined only by Hybrid C, under weights in `hybrid_c_weights`, and the sensitivity table reports what those weights change.
- **[derived]** Symptom-discriminator overlap is the densest signal and SNOMED the sparsest, so a family set built on SNOMED alone would rest on much thinner evidence than one built on symptom discriminators.
- **[derived]** **Disposition overlap is high by construction and discriminates poorly.** The estate has under 200 distinct disposition codes and most families reach a similar subset of them, so disposition Jaccard is the highest median of any dimension and is the reported driver for most high-overlap family pairs. Two families sharing dispositions is close to saying both can end in an ambulance or a primary-care referral. It is kept as a dimension because a family's outcome set matters for Phase 3 sizing, but it should carry little weight in judging whether two families are the same clinical area.

## 7. Hybrid grouping findings

| Strategy | Rule applied | Families | Pathways |
|---|---|---|---|
| hybrid_a | Graph communities (louvain) as the primary grouping, split on symptom_group where mean pairwise symptom-discriminator Jaccard < 0.2, with communities below 5 pathways absorbed by affinity. | 34 | 815 |
| hybrid_b | NHS-native grouping as primary (SymptomGroupId, else the most specific clinical area), split on graph subcommunities where the group's internal-edge percentage < 25.0%. | 227 | 815 |
| hybrid_c | louvain clustering of a weighted similarity graph (disposition=0.10, graph=0.35, question=0.20, snomed=0.15, symptom_discriminator=0.20) thresholded at 0.12. The weighting is an experimental baseline and is not clinically validated. | 9 | 815 |

- **[assumption]** **Hybrid A** takes graph communities as the primary grouping and refines them with clinical features: a community whose mean pairwise symptom-discriminator Jaccard falls below `0.2` is split by `symptom_group`, and a community below `5` pathways is absorbed into its highest-affinity neighbour.
- **[assumption]** **Hybrid B** takes the NHS-native grouping as primary (symptom group where present, otherwise the pathway's most specific clinical area) and splits a group whose internal-edge percentage falls below `25.0`%.
- **[assumption]** **Hybrid C** clusters a weighted combination of all evidence dimensions. The default weighting is an **experimental baseline and is not clinically validated**: `disposition`=0.10, `graph`=0.35, `question`=0.20, `snomed`=0.15, `symptom_discriminator`=0.20.
- **[measured]** `hybrid_a`: 3 graph communities were split on symptom_group because their mean pairwise symptom-discriminator Jaccard fell below 0.2.
- **[measured]** `hybrid_a`: 19 families below the minimum size of 5 were absorbed into their highest-affinity neighbour; 16 were retained because no destination reached the affinity floor.
- **[measured]** `hybrid_b`: Small families are retained rather than absorbed: an NHS grouping with few pathways is still a native unit, and absorbing it would discard the structure this strategy exists to test.
- **[measured]** `hybrid_c`: The default weighting is not clinically validated. See hybrid_family_sensitivity.csv for what changes when it changes.

### Hybrid C sensitivity to the weighting

| Weight variant | Families | Median size | Largest | ARI vs default | % membership changed | Weights |
|---|---|---|---|---|---|---|
| question_heavy | 42 | 1 | 201 | 0.651 | 12.27 | disposition=0.05, graph=0.20, question=0.50, snomed=0.10, symptom_discriminator=0.15 |
| sd_heavy | 60 | 1 | 217 | 0.605 | 13.25 | disposition=0.05, graph=0.20, question=0.15, snomed=0.10, symptom_discriminator=0.50 |
| equal | 45 | 1 | 231 | 0.593 | 19.88 | disposition=0.20, graph=0.20, question=0.20, snomed=0.20, symptom_discriminator=0.20 |
| features_only | 58 | 1 | 216 | 0.576 | 17.55 | disposition=0.15, graph=0.00, question=0.30, snomed=0.25, symptom_discriminator=0.30 |
| graph_heavy | 17 | 7 | 174 | 0.423 | 24.66 | disposition=0.05, graph=0.60, question=0.10, snomed=0.10, symptom_discriminator=0.15 |
| graph_only | 51 | 1 | 116 | 0.2 | 31.66 | disposition=0.00, graph=1.00, question=0.00, snomed=0.00, symptom_discriminator=0.00 |

- **[derived]** The weighting **does** change the answer: variant `graph_only` agrees with the default at an adjusted Rand index of only **0.200**, with **31.7%** of pathways landing in a different family. Hybrid C must therefore be read as one weighting's output, not as a stable family set.

## 8. Candidate family set

- **[assumption]** The set presented for review is `hybrid_a` (`presentation.primary_candidate_strategy`). This is a **modelling choice**, made because it is the only strategy that starts from measured graph cohesion and then requires clinical-feature support before a group is kept — not a finding that it is the right family set. Every strategy is compared in `family_strategy_comparison.csv`.

| Family | Name | Pathways | Internal-edge % | Questions | SDs | Boundary pathways | Structural cohesion | Review needed |
|---|---|---|---|---|---|---|---|---|
| HA_C00 | Family_00 | 123 | 85.503 | 741 | 162 | 42 | moderate (one of graph or clinical-feature evidence is strong) | yes |
| HA_C02 | Family_01 | 106 | 60.259 | 743 | 72 | 72 | moderate (one of graph or clinical-feature evidence is strong) | yes |
| HA_C03 | Family_02 | 94 | 62.717 | 778 | 70 | 83 | high (graph and clinical-feature evidence agree) | yes |
| HA_C04_01 | Family_03 | 81 | 59.783 | 816 | 131 | 45 | moderate (one of graph or clinical-feature evidence is strong) | yes |
| HA_C05 | Family_04 | 70 | 77.6 | 633 | 96 | 44 | moderate (one of graph or clinical-feature evidence is strong) | yes |
| HA_C06 | Family_05 | 55 | 52.582 | 464 | 34 | 44 | high (graph and clinical-feature evidence agree) | yes |
| HA_C01_00 | Family_06 | 54 | 46.389 | 483 | 96 | 52 | low (neither graph nor clinical-feature cohesion is strong) | yes |
| HA_C08 | Family_07 | 33 | 100 | 57 | 0 | 0 | moderate (one of graph or clinical-feature evidence is strong) | yes |
| HA_C07_00 | Family_08 | 32 | 48.421 | 426 | 53 | 29 | moderate (one of graph or clinical-feature evidence is strong) | yes |
| HA_C10 | head | 28 | 73.418 | 237 | 28 | 12 | high (graph and clinical-feature evidence agree) | yes |
| HA_C01_03 | Family_10 | 27 | 46.512 | 463 | 99 | 21 | low (neither graph nor clinical-feature cohesion is strong) | yes |
| HA_C09 | not area specific | 26 | 67.619 | 546 | 101 | 19 | moderate (one of graph or clinical-feature evidence is strong) | yes |
| HA_C04_00 | Lower Back Injury, Blunt | 16 | 0 | 119 | 14 | 8 | moderate (one of graph or clinical-feature evidence is strong) | yes |
| HA_C11 | Family_13 | 15 | 72 | 143 | 17 | 7 | high (graph and clinical-feature evidence agree) | yes |
| HA_C01_01 | Trauma Emergency | 12 | 11.111 | 112 | 34 | 12 | moderate (one of graph or clinical-feature evidence is strong) | yes |
| HA_C01_02 | Entry pathway | 11 | 14.286 | 41 | 0 | 11 | low (pathways mostly transfer outside the family) | yes |
| HA_C07_01 | Family_16 | 8 | 25 | 54 | 0 | 8 | low (neither graph nor clinical-feature cohesion is strong) | yes |
| HA_C12 | Ambulance Dispatch | 6 | 73.333 | 26 | 12 | 3 | high (graph and clinical-feature evidence agree) | yes |
| HA_C13 | Family_18 | 2 | 100 | 4 | 0 | 0 | moderate (one of graph or clinical-feature evidence is strong) | yes |
| HA_C14 | Family_19 | 2 | 100 | 5 | 0 | 0 | moderate (one of graph or clinical-feature evidence is strong) | yes |
| HA_C16 | Family_20 | 1 | 100 | 4 | 0 | 0 | moderate (one of graph or clinical-feature evidence is strong) | yes |
| HA_C17 | Family_21 | 1 | 100 | 4 | 0 | 0 | moderate (one of graph or clinical-feature evidence is strong) | yes |
| HA_C18 | Family_22 | 1 | 100 | 3 | 0 | 0 | moderate (one of graph or clinical-feature evidence is strong) | yes |
| HA_C19 | Family_23 | 1 | 100 | 3 | 0 | 0 | moderate (one of graph or clinical-feature evidence is strong) | yes |
| HA_C20 | Family_24 | 1 | 100 | 4 | 0 | 0 | moderate (one of graph or clinical-feature evidence is strong) | yes |
| HA_C21 | Family_25 | 1 | 100 | 3 | 0 | 0 | moderate (one of graph or clinical-feature evidence is strong) | yes |
| HA_C22 | Family_26 | 1 | 100 | 3 | 0 | 0 | moderate (one of graph or clinical-feature evidence is strong) | yes |
| HA_C23 | Family_27 | 1 | 100 | 3 | 0 | 0 | moderate (one of graph or clinical-feature evidence is strong) | yes |
| HA_C24 | Family_28 | 1 | 100 | 3 | 0 | 0 | moderate (one of graph or clinical-feature evidence is strong) | yes |
| HA_C25 | Family_29 | 1 | 100 | 4 | 0 | 0 | moderate (one of graph or clinical-feature evidence is strong) | yes |
| HA_C38 | Repeat Prescription (HA_C38) | 1 | n/a | 10 | 3 | 0 | low (neither graph nor clinical-feature cohesion is strong) | yes |
| HA_C41 | Repeat Prescription (HA_C41) | 1 | n/a | 3 | 1 | 0 | low (neither graph nor clinical-feature cohesion is strong) | yes |
| HA_C48 | Family_32 | 1 | n/a | 19 | 0 | 0 | low (neither graph nor clinical-feature cohesion is strong) | yes |
| HA_C49 | Family_33 | 1 | n/a | 33 | 0 | 0 | low (neither graph nor clinical-feature cohesion is strong) | yes |

- **[derived]** **34** candidate families covering **815** pathway memberships; median size **7**, largest **123**.
- **[derived]** **8** of 34 families could be given a name derived from dominant NHS metadata at the configured dominance threshold of 50%. The rest keep a neutral `Community_NN` name, with their dominant symptom groups and clinical areas reported separately. A name was never invented for a community that does not have one.
- **[interpretation]** A neutral name is a finding in itself: it marks a group that is cohesive in the transfer graph but does not correspond to a single NHS grouping, which is precisely where clinical judgement is needed.

## 9. Overlap and boundary areas

- **[derived]** Within the presented family set, **455** family pairs share at least one feature, pathway or transition: 323 low, 76 high, 56 moderate. Bands use `overlap_thresholds` (moderate 0.15, high 0.35) applied to the largest of the question, symptom-discriminator and SNOMED Jaccard values (`band_measure: discriminating`, which excludes dispositions because they overlap by construction).

### Highest-overlap family pairs

| A | B | A size | B size | Band Jaccard | Shared pathways | Driver | Why |
|---|---|---|---|---|---|---|---|
| HA_C02 | HA_C03 | 106 | 94 | 0.414 | 0 | shared SNOMED concepts | symptom-discriminator Jaccard 0.352 (37 shared); question Jaccard 0.213 (267 shared); SNOMED Jaccard 0.414 (77 shared); 490 transfer transitions between them |
| HA_C03 | HA_C04_01 | 94 | 81 | 0.408 | 0 | shared SNOMED concepts | symptom-discriminator Jaccard 0.272 (43 shared); question Jaccard 0.183 (247 shared); SNOMED Jaccard 0.408 (87 shared); 282 transfer transitions between them |
| HA_C02 | HA_C04_01 | 106 | 81 | 0.404 | 0 | shared SNOMED concepts | symptom-discriminator Jaccard 0.277 (44 shared); question Jaccard 0.181 (239 shared); SNOMED Jaccard 0.404 (78 shared); 212 transfer transitions between them |
| HA_C04_01 | HA_C05 | 81 | 70 | 0.422 | 0 | shared SNOMED concepts | symptom-discriminator Jaccard 0.305 (53 shared); question Jaccard 0.192 (233 shared); SNOMED Jaccard 0.422 (84 shared); 244 transfer transitions between them |
| HA_C02 | HA_C05 | 106 | 70 | 0.422 | 0 | shared SNOMED concepts | symptom-discriminator Jaccard 0.355 (44 shared); question Jaccard 0.227 (255 shared); SNOMED Jaccard 0.422 (73 shared); 212 transfer transitions between them |
| HA_C03 | HA_C05 | 94 | 70 | 0.361 | 0 | shared symptom discriminators | symptom-discriminator Jaccard 0.361 (44 shared); question Jaccard 0.231 (265 shared); SNOMED Jaccard 0.355 (72 shared); 990 transfer transitions between them |
| HA_C02 | HA_C06 | 106 | 55 | 0.441 | 0 | shared SNOMED concepts | symptom-discriminator Jaccard 0.218 (19 shared); question Jaccard 0.195 (197 shared); SNOMED Jaccard 0.441 (71 shared); 174 transfer transitions between them |
| HA_C04_01 | HA_C06 | 81 | 55 | 0.379 | 0 | shared SNOMED concepts | symptom-discriminator Jaccard 0.179 (25 shared); question Jaccard 0.160 (177 shared); SNOMED Jaccard 0.379 (74 shared); 122 transfer transitions between them |
| HA_C01_00 | HA_C01_01 | 54 | 12 | 0.361 | 0 | shared SNOMED concepts | symptom-discriminator Jaccard 0.066 (8 shared); question Jaccard 0.076 (42 shared); SNOMED Jaccard 0.361 (13 shared); 2760 transfer transitions between them |
| HA_C13 | HA_C14 | 2 | 2 | 0.8 | 0 | shared questions | question Jaccard 0.800 (4 shared) |
| HA_C13 | HA_C16 | 2 | 1 | 1 | 0 | shared questions | question Jaccard 1.000 (4 shared) |
| HA_C13 | HA_C17 | 2 | 1 | 1 | 0 | shared questions | question Jaccard 1.000 (4 shared) |
| HA_C13 | HA_C20 | 2 | 1 | 1 | 0 | shared questions | question Jaccard 1.000 (4 shared) |
| HA_C13 | HA_C25 | 2 | 1 | 1 | 0 | shared questions | question Jaccard 1.000 (4 shared) |
| HA_C16 | HA_C17 | 1 | 1 | 1 | 0 | shared questions | question Jaccard 1.000 (4 shared) |

- **[derived]** 67 of the 76 high-overlap pairs involve a family of at most two pathways. Jaccard is scale-free, so two one-pathway families that share all three of their questions score 1.0: arithmetically correct and analytically trivial. The table is therefore ordered by the smaller family's size first, and `SmallerFamilyPathwayCount` is carried in the CSV so the trivial pairs can be filtered out.
- **[assumption]** High overlap is **not** a merge instruction. Two families sharing a large symptom-discriminator vocabulary may be one clinical area split by routing, or two distinct areas sharing screening questions. Structure cannot tell them apart.

- **[derived]** Boundary pathways in the presented set: **512** of 815 (62.8%) have at least one edge to a pathway outside their family — 212 weak, 245 strong, 55 cross-family hubs.
- **[assumption]** The boundary classification is **structural only**. 'Cross-family hub' means a pathway has edges to several candidate families and high betweenness. It makes no claim that the pathway is clinically central or wrongly placed.

## 10. Shared-core candidates

| Feature type | Features | 1 family | 2 families | 3-5 families | 6+ families | Shared-core candidates | Duplicate copies implied |
|---|---|---|---|---|---|---|---|
| disposition code | 194 | 60 | 48 | 41 | 45 | 56 | 466 |
| Tx triage question | 3787 | 2370 | 750 | 504 | 163 | 244 | 1479 |
| SNOMED concept | 297 | 84 | 58 | 90 | 65 | 78 | 505 |
| symptom discriminator | 469 | 255 | 89 | 92 | 33 | 46 | 285 |

- **[derived]** **424** features are used by at least 5 candidate families and are flagged as shared-core candidates. Together they imply **2,735** duplicate copies if every family held its own — a structural count, not a sizing estimate.
- **[assumption]** Flagging a feature here does **not** conclude that it belongs in a shared Bayesian Network. A broadly shared question may be one clinical concept used everywhere, several distinct concepts sharing wording, or an artefact of how Pathways is authored. Structure alone cannot separate those readings.

### Most broadly shared features

| Type | Id | Description | Families | Pathways | Occurrences | On a boundary pathway |
|---|---|---|---|---|---|---|
| Tx triage question | TX170003 |  | 26 | 219 | 1392 | yes |
| disposition code | DX012 | Emergency Ambulance Response (Category 3) | 22 | 404 | 3117 | yes |
| Tx triage question | TX221039 |  | 19 | 180 | 3426 | yes |
| Tx triage question | TX222414 |  | 18 | 42 | 45 | yes |
| Tx triage question | TX222415 |  | 18 | 42 | 44 | yes |
| Tx triage question | TX221449 |  | 14 | 514 | 6703 | yes |
| symptom discriminator | 4003 | PC full Primary Care assessment and prescribing capability | 14 | 514 | 6703 | yes |
| disposition code | DX02 | Refer to Treatment Centre within 1 hour | 14 | 405 | 7405 | yes |
| disposition code | DX11 | Speak to a Primary Care Service within 1 hour | 14 | 262 | 3337 | yes |
| disposition code | DX15 | Speak to a Primary Care Service within 24 hours | 14 | 94 | 616 | yes |
| Tx triage question | TX221017 |  | 14 | 88 | 980 | yes |
| disposition code | DX06 | To Contact a Primary Care Service within 6 hours | 13 | 386 | 5232 | yes |
| Tx triage question | TX221512 |  | 13 | 377 | 1415 | yes |
| symptom discriminator | 4052 | ED full ED assessment and management capability | 13 | 377 | 1415 | yes |
| disposition code | DX08 | To Contact a Primary Care Service within 24 hours | 13 | 356 | 4692 | yes |


## 11. Potential merge and split areas

- **[derived]** **76** high-overlap pairs were merged hypothetically and re-measured. **0** would raise the size-weighted mean pairwise symptom-discriminator Jaccard.
- **[assumption]** **The internal-edge percentage cannot be used to judge a merge.** Every edge that ran between the two families becomes internal to the union, so merging can only raise it. It is reported because the size of the gain separates a pair that genuinely interacts from one that barely does, but the discriminating signal is the shared-symptom-discriminator change, which has no such bias: it falls when a merge combines pathways that route together without being clinically alike.

| A | B | A size | B size | SD Jaccard before | SD Jaccard after | Internal % delta (mechanical) | Structural effect |
|---|---|---|---|---|---|---|---|
| HA_C02 | HA_C03 | 106 | 94 | 0.185 | 0.162 | 9.206 | shared-SD cohesion falls (-0.023): the union is less clinically alike than its parts; graph cohesion +9.2pp (mechanical) |
| HA_C02 | HA_C04_01 | 106 | 81 | 0.15 | 0.133 | 5.17 | shared-SD cohesion falls (-0.017): the union is less clinically alike than its parts; graph cohesion +5.2pp (mechanical) |
| HA_C03 | HA_C04_01 | 94 | 81 | 0.165 | 0.138 | 5.638 | shared-SD cohesion falls (-0.027): the union is less clinically alike than its parts; graph cohesion +5.6pp (mechanical) |
| HA_C04_01 | HA_C05 | 81 | 70 | 0.12 | 0.107 | 9.714 | shared-SD cohesion falls (-0.013): the union is less clinically alike than its parts; graph cohesion +9.7pp (mechanical) |
| HA_C03 | HA_C05 | 94 | 70 | 0.165 | 0.15 | 15.868 | shared-SD cohesion falls (-0.015): the union is less clinically alike than its parts; graph cohesion +15.9pp (mechanical) |
| HA_C02 | HA_C05 | 106 | 70 | 0.149 | 0.134 | 7.599 | shared-SD cohesion falls (-0.015): the union is less clinically alike than its parts; graph cohesion +7.6pp (mechanical) |
| HA_C02 | HA_C06 | 106 | 55 | 0.195 | 0.182 | 5.53 | shared-SD cohesion falls (-0.013): the union is less clinically alike than its parts; graph cohesion +5.5pp (mechanical) |
| HA_C04_01 | HA_C06 | 81 | 55 | 0.171 | 0.141 | 3.456 | shared-SD cohesion falls (-0.030): the union is less clinically alike than its parts; graph cohesion +3.5pp (mechanical) |
| HA_C01_00 | HA_C01_01 | 54 | 12 | 0.282 | 0.134 | 14.538 | shared-SD cohesion falls (-0.148): the union is less clinically alike than its parts; graph cohesion +14.5pp (mechanical) |
| HA_C13 | HA_C14 | 2 | 2 | 0 | 0 | 0 | shared-SD cohesion unchanged (+0.000); graph cohesion +0.0pp (mechanical) |

- **[interpretation]** **None of the 76 tested merges raises shared-SD cohesion.** Every high-overlap pair would produce a family less clinically alike than its parts, even though each merge raises the internal-edge percentage. On this evidence the overlap between these families is shared vocabulary and shared routing rather than a sign that the boundary is in the wrong place — but structure cannot rule out a merge a clinician would still want, and two families that legitimately belong together would look exactly like this if their shared discriminators were few.

- **[derived]** **10** families met a split trigger; 11 split proposals were measured across 2 methods.

| Family | Method | Pathways | Parts | Part sizes | Internal % delta | SD Jaccard delta | Structural effect |
|---|---|---|---|---|---|---|---|
| HA_C00 | graph_subcommunity | 123 | 6 | 38 / 23 / 21 / 16 / 12 / 10 | -17.118 | 0.077 | split improves shared-SD cohesion only |
| HA_C02 | graph_subcommunity | 106 | 5 | 32 / 24 / 23 / 18 / 8 | -15.91 | 0.055 | split improves shared-SD cohesion only |
| HA_C03 | dominant_symptom_group | 94 | 4 | 12 / 10 / 10 / 9 | -57.189 | 0.247 | split improves shared-SD cohesion only |
| HA_C03 | graph_subcommunity | 94 | 5 | 33 / 20 / 15 / 14 / 12 | -26.27 | 0.053 | split improves shared-SD cohesion only |
| HA_C04_01 | graph_subcommunity | 81 | 5 | 22 / 16 / 15 / 13 / 8 | -2.051 | 0.092 | split improves shared-SD cohesion only |
| HA_C05 | graph_subcommunity | 70 | 4 | 25 / 20 / 12 / 8 | -13.152 | 0.06 | split improves shared-SD cohesion only |
| HA_C06 | graph_subcommunity | 55 | 3 | 16 / 15 / 10 | -12.196 | 0.08 | split improves shared-SD cohesion only |
| HA_C01_00 | graph_subcommunity | 54 | 3 | 19 / 11 / 10 | -17.872 | 0.146 | split improves shared-SD cohesion only |
| HA_C08 | graph_subcommunity | 33 | 2 | 18 / 15 | -6.734 | 0 | split improves neither measure |
| HA_C07_00 | graph_subcommunity | 32 | 2 | 11 / 9 | -11.088 | 0.076 | split improves shared-SD cohesion only |
| HA_C09 | graph_subcommunity | 26 | 2 | 11 / 9 | -19.987 | 0.119 | split improves shared-SD cohesion only |

- **[assumption]** A split has the mirror-image bias: dividing a family turns internal edges into external ones, so the internal-edge percentage almost always falls. The split verdicts are therefore also read from the shared-symptom-discriminator change.
- **[assumption]** **No merge and no split is recommended.** Both tables are before/after measurements. A split that improves shared-SD cohesion may still separate pathways a clinician would keep together, and the reverse.

## 12. Routing ambiguity

| Strategy | % strong single-family | % moderate | % high | % 1 plausible family | % 2 plausible | % 3+ plausible | % dominant = assigned |
|---|---|---|---|---|---|---|---|
| graph_greedy_modularity | 40.25 | 34.36 | 25.4 | 65.64 | 13.37 | 20.98 | 84.66 |
| graph_label_propagation | 27.73 | 38.16 | 34.11 | 54.23 | 19.02 | 26.75 | 76.07 |
| graph_leiden | 42.09 | 33.37 | 24.54 | 65.15 | 13.62 | 21.23 | 85.77 |
| graph_louvain | 40.25 | 34.48 | 25.28 | 64.05 | 13.99 | 21.96 | 84.91 |
| graph_networkx_louvain | 40.86 | 33.62 | 25.52 | 64.91 | 13.62 | 21.47 | 84.66 |
| hybrid_a | 46.63 | 31.78 | 21.6 | 70.92 | 15.58 | 13.5 | 81.35 |
| hybrid_b | 18.53 | 26.26 | 55.21 | 34.97 | 15.58 | 49.45 | 54.11 |
| hybrid_c | 56.44 | 25.4 | 18.16 | 76.32 | 19.26 | 4.42 | 75.09 |
| native_age_group | 8.1 | 20.12 | 71.78 | 20.12 | 36.56 | 43.31 | 89.08 |
| native_area_group | 44.66 | 26.87 | 28.47 | 62.45 | 21.6 | 15.95 | 55.09 |
| native_clinical_area | 43.44 | 26.63 | 29.94 | 61.72 | 19.75 | 18.53 | 54.72 |
| native_gender | 6.63 | 14.72 | 78.65 | 14.85 | 84.54 | 0.61 | 90.55 |
| native_symptom_group | 18.28 | 26.13 | 55.58 | 34.72 | 15.46 | 49.82 | 54.48 |
| native_trauma | 48.1 | 28.22 | 23.68 | 67.85 | 30.06 | 2.09 | 55.95 |

- **[derived]** In the presented set, **46.6%** of pathways associate strongly with a single family, **31.8%** are moderately ambiguous and **21.6%** are highly ambiguous, where ambiguity is the second-best affinity divided by the best.
- **[derived]** **81.3%** of pathways have their assigned family as their highest-affinity family. A mismatch is not an error: the affinity score and the grouping rule use different evidence, and disagreement marks a pathway worth reviewing.
- **[assumption]** Affinity weights come from `routing.weights` and are not clinically validated. The five component scores are exported per pathway so a reviewer can re-weight without re-running the analysis.
- **[interpretation]** Ambiguity here is a property of the *structure*, measured with the whole pathway known. A live runtime would have to route on partial answers, which is strictly harder. These figures are therefore an optimistic bound on routability, and designing a router is out of scope for Phase 2.

## 13. Age and trauma dimensions

### Age

| Classification | Pathways | Internal-edge % | Boundary % | Mean SD Jaccard | Dispositions |
|---|---|---|---|---|---|
| paediatric_only | 356 | 34.884 | 86.236 | 0.115 | 75 |
| adult_and_paediatric | 284 | 67.57 | 60.563 | 0.07 | 174 |
| adult_only | 156 | 30.071 | 90.385 | 0.086 | 78 |
| unspecified | 19 | 0 | 94.737 | 0 | 23 |

| Value | Pathways | Families containing it | Largest family share | Families for 80% | Spread |
|---|---|---|---|---|---|
| paediatric_only | 356 | 18 | 0.16 | 9 | spread: tagged pathways are distributed across many families, consistent with a cross-cutting dimension |
| adult_and_paediatric | 284 | 30 | 0.218 | 9 | spread: tagged pathways are distributed across many families, consistent with a cross-cutting dimension |
| adult_only | 156 | 20 | 0.199 | 9 | spread: tagged pathways are distributed across many families, consistent with a cross-cutting dimension |
| unspecified | 19 | 3 | 0.895 | 1 | concentrated: one family holds at least half the tagged pathways |

- **[derived]** Within-family subset comparison across 34 families: 16 — not measurable (one subset has fewer than two pathways); 9 — subsets partially distinguishable (between is 50-100% of within); 9 — subsets are not structurally distinguishable on shared symptom discriminators (between >= within).
- **[assumption]** No assumption is made that age must be a separate top-level family. The three readings — separate families, variants inside families, cross-cutting structure — are each given their numbers and the choice is left to clinical review.

### Trauma

| Classification | Pathways | Internal-edge % | Boundary % | Mean SD Jaccard | Dispositions |
|---|---|---|---|---|---|
| unspecified | 366 | 85.463 | 66.393 | 0.039 | 185 |
| non_trauma | 294 | 37.188 | 87.755 | 0.159 | 65 |
| trauma | 131 | 18.485 | 96.183 | 0.23 | 45 |
| trauma_and_non_trauma | 24 | 25.316 | 66.667 | 0.103 | 59 |

| Value | Pathways | Families containing it | Largest family share | Families for 80% | Spread |
|---|---|---|---|---|---|
| unspecified | 366 | 29 | 0.134 | 11 | spread: tagged pathways are distributed across many families, consistent with a cross-cutting dimension |
| non_trauma | 294 | 13 | 0.276 | 5 | concentrated: 80% of tagged pathways sit in a small number of families |
| trauma | 131 | 9 | 0.542 | 3 | concentrated: one family holds at least half the tagged pathways |
| trauma_and_non_trauma | 24 | 10 | 0.25 | 6 | spread: tagged pathways are distributed across many families, consistent with a cross-cutting dimension |

- **[derived]** Within-family subset comparison across 34 families: 27 — not measurable (one subset has fewer than two pathways); 4 — subsets partially distinguishable (between is 50-100% of within); 3 — subsets are structurally distinct on shared symptom discriminators.
- **[assumption]** No assumption is made that trauma must be a separate top-level family. The three readings — separate families, variants inside families, cross-cutting structure — are each given their numbers and the choice is left to clinical review.

## 14. Uncertainties and limitations

- **[measured]** **150** in-scope pathways carry no `SymptomGroupId`, so the symptom-group baseline cannot place them. They are held in an explicit `UNASSIGNED` family rather than dropped, which means that family is an artefact of missing metadata and not a clinical grouping.
- **[measured]** SNOMED coverage is sparse relative to the answer catalogue (299 concepts over 13,609 answers), so SNOMED-based cohesion rests on much thinner evidence than symptom-discriminator cohesion. The two are never averaged.
- **[assumption]** The transfer graph counts only T1-T4 values that resolve to a pathway. `JumpID` values -2, -4, -5, -9 and 0 carry no payload and are control behaviour, so they are not edges. If any of them does imply a routing relationship not visible in `tblTriageLogic`, every cohesion figure here understates connectivity.
- **[assumption]** Symptom discriminators are attributed to a pathway through the answers it offers. A discriminator reachable only by a route the pathway never takes in practice is still counted, because reachability is what the data records and traversal frequency is not available.
- **[assumption]** Every threshold and weight is a configured default with no clinical endorsement. The Hybrid C sensitivity table shows the weighting is material, which means the Hybrid C family set should not be treated as stable.
- **[interpretation]** Graph cohesion and clinical coherence are different properties, and this analysis can only measure the first. Where a candidate family is cohesive but has no dominant NHS grouping, the evidence is genuinely ambiguous rather than merely incomplete.
- **[measured]** Pathway *usage* data is absent: every count here weights a rarely-used pathway identically to a heavily-used one. A family set that is coherent by structure may not be the one that carries the traffic.

## 15. Questions requiring clinical judgement

These are the points where structure has taken the analysis as far as it can. Each is asked concretely in `outputs/phase2/clinical_review_pack.md`.

1. **Are the 34 candidate families clinically recognisable?** Structure says they are cohesive; only clinicians can say whether each is one clinical area.
2. **26 families have no dominant NHS grouping** and carry neutral names. Is each a real clinical grouping the metadata does not capture, or an artefact of how pathways refer to one another?
3. **76 family pairs overlap strongly.** For each: are these one clinical area that routing has split, or two areas that legitimately share a screening vocabulary?
4. **424 features are used across many families.** For the most widely shared: is each one clinical concept (so a shared structure is natural), several concepts sharing wording (so sharing would conflate them), or an authoring artefact?
5. **Should paediatric pathways be their own families, age variants inside families, or a cross-cutting dimension?** The three sets of numbers are in `age_family_analysis.csv`; the choice is clinical.
6. **Is trauma one family, several anatomical families, a cross-cutting dimension, or a shared gateway?** See `trauma_family_analysis.csv`.
7. **Are the boundary pathways and cross-family hubs clinically significant, or incidental routing?** A hub that is clinically load-bearing is a different design problem from one that merely has many transfers.
8. **Is any candidate family unsafe to separate?** If splitting two families could lose a safety-critical route between them, that constraint is invisible to this analysis and must come from clinical review.

## 16. What Phase 3 needs from these results

Phase 3 covers the literal, deduplicated and clinically-normalised Bayesian representations, monolithic and federated sizing, CPT growth, memory, inference benchmarks, runtime architecture, infrastructure and cost. From Phase 2 it will need:

1. **A reviewed family set.** `candidate_bayesian_families.csv` plus the clinical review outcome. Sizing an unreviewed family set would carry the structural assumptions into the cost model.
2. **Family membership, including overlaps.** `candidate_family_membership.csv`. Pathways in several families are counted once per family in a federated sizing and once overall in a monolithic one, so the overlap volume drives the difference between the two.
3. **Per-family variable counts.** `UniqueQuestions`, `UniqueSDs`, `UniqueSnomed` and `UniqueDispositions` per family, combined with the Phase 1 answer-cardinality tables, give the per-family state space.
4. **Shared-core candidates and their duplication counts.** `shared_core_candidates.csv` — `DuplicationIfFederated` is the quantity a shared-core design would avoid and a fully federated design would pay.
5. **Boundary features and pathways.** The cross-family features are the nodes a federated design has to synchronise; their count bounds the inter-model interface.
6. **Routing ambiguity.** The share of pathways without a clear single family bounds how well any router could work, and is an input to the federated runtime's error budget.
7. **Merge and split candidates.** Alternative family sets to size alongside the primary one, so Phase 3 tests a range rather than one arrangement.
8. **Release blast radius inputs.** Family membership plus the boundary feature tables determine how many families a change to one shared question would touch.

- **[assumption]** Phase 2 deliberately produces no node, edge, CPT or memory estimate. Any number of that kind in this report would be a Phase 3 result quoted without its sizing assumptions.

## Appendix A. Configuration used by this run

Source: `/Users/tharacka/Development/Projects/nhs-duec/triage-poc/pathways-analysis/config/family_discovery.yaml`

| Setting | Value |
|---|---|
| `pathway_scope` | active |
| `community_detection.methods` | louvain, networkx_louvain, leiden, greedy_modularity, label_propagation, strongly_connected |
| `community_detection.primary_method` | louvain |
| `family_size.minimum_family_size` | 5 |
| `family_size.split_review_size` | 40 |
| `family_size.minimum_split_part_size` | 8 |
| `overlap_thresholds.band_measure` | discriminating |
| `overlap_thresholds.moderate` | 0.15 |
| `overlap_thresholds.high` | 0.35 |
| `hybrid_c_weights` | disposition=0.100, graph=0.350, question=0.200, snomed=0.150, symptom_discriminator=0.200 |
| `hybrid_c.similarity_threshold` | 0.12 |
| `hybrid_c.clustering_method` | louvain |
| `hybrid_c_sensitivity variants` | graph_only, features_only, equal, sd_heavy, graph_heavy, question_heavy |
| `hybrid_a.clinical_cohesion_threshold` | 0.2 |
| `hybrid_a.split_feature` | symptom_group |
| `hybrid_b.weak_cohesion_internal_edge_pct` | 25 |
| `boundary.strong_external_degree` | 3 |
| `boundary.hub_external_family_count` | 3 |
| `boundary.hub_betweenness_percentile` | 90 |
| `shared_core.minimum_family_count` | 5 |
| `routing.weights` | disposition=0.100, graph=0.350, question=0.200, snomed=0.150, symptom_discriminator=0.200 |
| `routing.moderate_ambiguity` | 0.4 |
| `routing.high_ambiguity` | 0.7 |
| `routing.plausible_affinity_ratio` | 0.6 |
| `similarity.max_graph_hops` | 2 |
| `presentation.primary_candidate_strategy` | hybrid_a |
| `presentation.naming_dominance_threshold` | 0.5 |
| `composite_score.enabled` | False |

- **[assumption]** Every value above is a modelling assumption. None is clinically validated. Re-running with `--config` pointed at a modified copy reproduces the whole evidence base under different choices.

## Appendix B. Artefacts produced

- `outputs/phase2/tables/`: 43 analysis tables.
- `outputs/phase2/charts/`, `outputs/phase2/graphs/`: figures.
- `outputs/phase2/reports/metric_definitions.csv`: the definition of every derived metric used above.
- `outputs/phase2/clinical_review_pack.md`: the concise review document.

### Run notes

- Extracted 26 read-only queries.
- Edge-list cross-check passed: the Python and server-side derivations agree on 3,478 edges and 39,890 transitions.

Phase 1 outputs under `outputs/tables/` and `outputs/charts/` are untouched by this run.
