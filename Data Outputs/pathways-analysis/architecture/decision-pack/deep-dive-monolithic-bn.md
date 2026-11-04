# Deep Dive — Monolithic Bayesian Network

**Status:** Draft for review  
**Decision pack:** Adaptive Triage Bayesian Architecture  
**Purpose:** Provide evidence for and against representing the supported Adaptive Triage clinical domain as one Bayesian Network.

---

## 1. Executive summary

A monolithic Bayesian Network means that the supported clinical domain is represented within one logically integrated BN artefact and inference graph.

The analysis does **not** currently support the statement that a monolithic BN is inherently too large to build. Raw node count and raw CPT storage alone are unlikely to be sufficient reasons to reject it. The more material uncertainties are:

- the dependency topology required by a clinically valid model;
- graph connectivity and resulting treewidth;
- intermediate factor size during exact inference;
- runtime latency and memory at clinically realistic topology;
- the breadth of regression and clinical assurance required when the model changes;
- whether one estate-wide model remains understandable and governable as the clinical domain expands.

A monolithic BN therefore remains a credible strategic comparator. It should not be rejected using pathway count alone.

The current evidence suggests that the principal trade-off is:

> **Runtime and coordination simplicity versus a potentially broad computational, clinical and change-management blast radius.**

---

## 2. What is meant by a monolithic BN?

There are at least three materially different monolithic representations.

### 2.1 Literal source-occurrence monolith

Every relevant question occurrence in every active pathway/order position is treated as a separate candidate BN variable.

This is useful as an **upper-bound structural stress case**, but it is not a credible target clinical model because it retains repetition inherited from deterministic pathway authoring.

### 2.2 QuestionID-deduplicated monolith

Repeated occurrences of the same source QuestionID are represented once.

Current source analysis identifies approximately **3,968 distinct Tx QuestionIDs referenced by active triage logic**. This provides a more useful technical sizing baseline than the total number of question occurrences.

This remains a structural representation, not a claim that every QuestionID maps one-to-one to a clinically valid BN variable.

### 2.3 Clinically normalised monolith

A future model in which source questions are mapped to clinician-approved clinical concepts before becoming BN variables.

This may merge multiple QuestionIDs that mean the same thing and may keep superficially similar questions separate where their clinical meaning differs by referent or context.

This is the most clinically meaningful monolithic representation, but it cannot be sized definitively until a clinician-approved semantic mapping exists.

---

## 3. Why pathway count is not BN size

The Pathways estate contains approximately 845 pathways in the current structural dataset, but pathway count does not directly determine Bayesian complexity.

BN computational size is driven more directly by:

- number of variables;
- number of states per variable;
- parent count per variable;
- graph topology;
- treewidth / induced width;
- largest clique or intermediate factor produced by the inference algorithm.

For a discrete variable, CPT entries grow as:

`child states × product(parent states)`

This means modest increases in parent count can have a much larger effect than adding many sparsely connected variables.

---

## 4. Question reuse and deduplication

Question reuse is potentially beneficial because deterministic pathways can ask the same authored question in many different contexts.

However, deduplication must be treated carefully.

### 4.1 Safe structural deduplication

A repeated occurrence of the same source QuestionID can be represented once for **technical sizing purposes**.

### 4.2 Clinical semantic deduplication

The final BN should deduplicate **clinical concepts rather than strings**.

For example, a question such as “Are you short of breath?” may represent one reusable observation whose effect differs across cardiac, respiratory or infection hypotheses.

In contrast, apparently similar wording such as “Is the pain severe?” may refer to clinically different variables if the referent is chest pain, abdominal pain or headache.

The semantic normalisation flow should therefore be:

```text
Source QuestionID / occurrence
            │
            ▼
Clinician-reviewed clinical concept
            │
            ▼
BN variable
            │
            ▼
State definition
            │
            ▼
Parent / child relationships
```

The QuestionID-deduplicated monolith should therefore be treated as a **technical sizing scenario**, not the final clinical variable model.

---

## 5. Structural sizing evidence

The current structural analysis supports three useful sizing perspectives:

| Representation | Purpose | Evidence status |
|---|---|---|
| Literal source occurrence | Upper-bound stress case | Measurable now |
| QuestionID deduplicated | Technical monolith baseline | Measurable now |
| Clinically normalised | Future clinical model | Pending clinician semantic review |

Phase 3A produces the detailed representation and cardinality evidence.

Relevant generated evidence:

- `representation_summary.csv`
- `state_cardinality_summary.csv`
- `variable_cardinality_baseline.csv`
- `family_sizing_baseline.csv`

The generated evidence should be inserted into the final version of this paper once the local Phase 3 outputs are signed off.

---

## 6. CPT growth

CPT storage is a more useful sizing measure than variable count alone.

Phase 3B evaluates:

- measured child state cardinalities;
- different parent-count scenarios;
- median and higher-cardinality parent-state cases;
- total CPT entries;
- free parameters;
- largest individual CPT;
- raw float32/float64 probability storage.

### Key interpretation

Even where raw CPT storage remains modest, this does not prove exact inference will be fast.

A network can have manageable stored CPTs but produce very large intermediate factors during variable elimination if the topology has high treewidth.

Therefore:

> **Raw CPT size is necessary evidence, but it is not sufficient evidence of monolithic inference feasibility.**

---

## 7. Inference feasibility

The critical technical question for the monolith is not simply whether the artefact can be loaded into memory.

It is whether clinically realistic inference can be performed within the service latency and resilience envelope.

The runtime evaluation needs to consider:

- query latency;
- p95/p99 latency;
- evidence-update latency during multi-step triage;
- memory during model construction;
- memory during inference;
- serialised artefact size;
- elimination order;
- maximum intermediate factor size;
- topology/treewidth;
- concurrency under expected workload.

Phase 3C provides a controlled benchmark framework, but benchmark topology must not be presented as clinical topology.

### NHS-wide workload context

If Adaptive Triage eventually handled approximately 33 million assessments per year, average request throughput would still be modest relative to common cloud workloads. The harder scalability question is therefore expected to be **per-assessment model complexity and predictable latency**, rather than simple transaction count.

This needs to remain an explicit hypothesis until measured with the production-shaped model.

---

## 8. Runtime architecture

A monolithic logical BN does not require a single server.

It can still run behind the same centralised Adaptive Triage service and be horizontally replicated.

A likely runtime pattern is:

```text
Patient / Channel
       │
       ▼
Adaptive Triage API
       │
       ▼
Central Inference Service
       │
       ├── Worker 1 ── Monolithic BN vN
       ├── Worker 2 ── Monolithic BN vN
       └── Worker N ── Monolithic BN vN
                 │
                 ▼
          Structured outcome
```

The model can remain resident in memory on every worker, with session/evidence state externalised from the worker.

This is operationally simpler than a multi-model coordination architecture.

---

## 9. Advantages

### Single probabilistic context

All variables and dependencies can be represented in one graph. Cross-clinical-family presentations do not require a separate family router or aggregation mechanism.

### Simpler runtime coordination

There is:

- one active graph per model version;
- no multi-family fan-out;
- no family selection problem;
- no cross-family evidence duplication;
- no family compatibility matrix.

### Natural handling of overlapping presentations

Evidence can influence any connected hypothesis without deciding first which clinical family owns the presentation.

### Simpler model-set versioning

A release can be represented by one model artefact/version, rather than a compatible set of family artefacts.

### Potentially simpler inference semantics

The posterior is derived from one coherent probabilistic graph rather than requiring coordination between independently authored family networks.

---

## 10. Disadvantages and risks

### Dependency complexity

As the clinical estate expands, the network may accumulate cross-domain dependencies that increase treewidth and exact-inference cost.

### Broad change blast radius

A local clinical change creates a new version of the estate-wide artefact.

Even where only a small part of the graph changes, the assurance question becomes whether the change could affect inference elsewhere.

### Whole-model regression pressure

The technically safe regression scope may be much wider than the clinical area being changed.

### Clinical governance scale

Clinicians need to understand the effect of local changes within a larger probabilistic graph.

The model may become difficult to reason about as a single governed clinical artefact.

### Release coupling

Unrelated clinical areas may become coupled to the same model release cadence.

### Failure isolation

A model-level defect potentially affects the whole supported service rather than one family.

### Organisational ownership

A very large shared clinical model may make ownership, approval boundaries and change authority harder to define.

---

## 11. Clinical safety considerations

The monolith removes some family-routing safety risks but creates other safety considerations.

### Risks reduced

- no incorrect initial family selection;
- no evidence double counting across family BNs;
- no incompatibility between separately versioned family models;
- no missing cross-family relationship purely because networks are separate.

### Risks introduced or amplified

- unintended long-range probabilistic effects;
- difficult-to-understand downstream consequences of local CPT/DAG changes;
- broader regression and assurance scope;
- a defect in the shared artefact can affect all presentations;
- the model may become too complex for meaningful human review without strong tooling.

The Clinical Admin UI would need strong support for:

- DAG visualisation;
- dependency tracing;
- CPT review;
- impact analysis;
- model differencing;
- regression/vignette selection;
- version comparison.

---

## 12. Change blast radius

A simple example illustrates the strategic difference.

```text
ENT model variable changes
          │
          ▼
Estate-wide BN artefact changes
          │
          ▼
Dependency impact assessment
          │
          ▼
Potential broad regression
          │
          ▼
Model-wide release / rollback unit
```

This does not mean every change must always trigger every test. Tooling may allow impact-based regression.

However, the architecture makes the **whole model the formal deployment and rollback boundary** unless additional partitioning mechanisms are introduced.

---

## 13. Infrastructure implications

A monolithic implementation would likely require:

- centralised inference service;
- horizontally replicated stateless workers;
- enough task/container memory to keep the whole validated BN resident;
- immutable versioned model artefacts in S3;
- model checksum/signature and manifest;
- externalised interaction/evidence state;
- API Gateway/WAF;
- encryption and KMS;
- CloudTrail and application audit;
- CloudWatch/OpenTelemetry-style metrics and traces;
- controlled blue/green or canary deployment;
- immediate rollback to the previous validated model;
- performance monitoring against model version.

The infrastructure architecture itself is not expected to be unusually complex. The more material uncertainty is how large and computationally expensive the final clinically realistic graph becomes.

---

## 14. Operational considerations

The monolithic model has attractive operational properties:

- one model to load;
- one version to report;
- one compatibility boundary;
- straightforward rollback;
- no family cache;
- no family router;
- no model fan-out.

These benefits should not be understated in the strategic ADR.

At the same time, operations would inherit one high-impact model dependency. Strong controls would be required to prevent a defective model release from affecting the full Adaptive Triage capability.

---

## 15. Cost considerations

Infrastructure cost should not currently be used as the primary reason either to select or reject the monolith.

The expected differences between topologies are more likely to arise through:

- worker memory requirements;
- inference CPU time;
- number of inference operations per interaction;
- minimum resident model footprint;
- operational/support complexity.

At NHS-wide assessment volumes, model safety, predictable latency, assurance scope and maintainability are expected to be more material than marginal compute price differences.

Phase 3E contains scenario-based infrastructure costing and should remain the quantitative source for the ADR.

---

## 16. Evidence gaps

Before a final decision, the following gaps remain material:

1. **Clinical semantic normalisation** — how many source questions become distinct clinical BN variables?
2. **Clinically realistic DAG shape** — deterministic Pathways routing cannot be used as the final Bayesian dependency graph.
3. **Treewidth / induced-width evidence** — a key driver for exact inference feasibility.
4. **Production-shaped performance benchmark** — including evidence updates during an adaptive interaction.
5. **Clinical change-impact analysis** — how broad would assurance actually need to be for a local model change?
6. **Operational memory measurement** — not only raw CPT arrays.
7. **Pilot learning** — the ENT family pilot should provide concrete evidence about modelling density, CPT review, question selection and runtime behaviour.

---

## 17. Potential pitfalls

### Declaring the monolith impossible based on node count

A BN with thousands of variables is not automatically computationally infeasible.

### Treating Pathways routing as the BN DAG

The existing deterministic graph is source evidence, not a causal/probabilistic network design.

### Treating QuestionID as clinical semantic identity

QuestionID deduplication is useful for technical sizing but is not sufficient for clinical modelling.

### Ignoring intermediate factor growth

Raw CPT storage can remain small while exact inference becomes expensive.

### Underestimating governance

The largest strategic disadvantage may eventually be assurance and change coupling rather than CPU or memory.

### Comparing an unrealistic monolith against a clinically refined federation

All strategic options need equivalent clinical normalisation before final comparison.

---

## 18. Evidence required for the strategic ADR

The monolithic option should be represented in the ADR using:

| Evidence | Source |
|---|---|
| Variable count scenarios | Phase 3A |
| State-cardinality distribution | Phase 3A |
| CPT growth | Phase 3B |
| Runtime latency/memory | Phase 3C |
| Runtime/deployment characteristics | Phase 3D |
| Infrastructure/cost sensitivity | Phase 3E |
| Semantic-normalisation findings | Clinical concept work |
| Change/assurance implications | Architecture + clinical safety review |
| Pilot evidence | ENT private beta, when available |

---

## 19. Current conclusion

The evidence currently supports keeping the monolithic architecture as a serious comparator.

A technically deduplicated monolith appears structurally plausible. The unresolved issue is not primarily whether several thousand variables can be stored, but whether a clinically realistic estate-wide dependency structure can deliver:

- predictable inference;
- acceptable latency;
- manageable memory;
- understandable clinical behaviour;
- proportionate regression;
- sustainable clinical governance.

The monolithic option should therefore remain in the strategic ADR until those questions are compared against equivalent federated, specialised and hybrid designs.

### Working position

> **Do not reject the monolith because it is “large”. Test whether its global dependency and assurance boundary remains acceptable once the clinical model becomes realistic.**

---

## 20. Further evidence to add

Before this document is marked complete:

- insert signed-off Phase 3A representation figures;
- insert Phase 3B CPT-growth tables/graphs;
- insert repaired Phase 3C benchmark results;
- add treewidth/intermediate-factor measurement if feasible;
- add an example clinically normalised concept mapping;
- add an example change-impact scenario;
- add a concise architecture diagram for the final published version.
