# Deep Dive — Federated Bayesian Networks

**Status:** Draft for review  
**Decision pack:** Adaptive Triage Bayesian Architecture  
**Purpose:** Examine a coordinated multi-family Bayesian architecture in which clinically bounded BNs can share evidence and more than one family can participate in an interaction.

---

## 1. Executive summary

A federated Bayesian architecture contains multiple clinically bounded family BNs operating as one coordinated Adaptive Triage capability.

Unlike a specialised architecture, federation does not require every interaction to be permanently assigned to exactly one BN. Evidence can be used to identify one or more relevant families and the runtime can coordinate multiple family models where clinically necessary.

This can provide:

- smaller individual inference graphs;
- more localised model changes;
- family-level clinical ownership;
- incremental model rollout;
- better support for overlapping clinical presentations than strict specialisation.

The cost is additional architectural complexity:

- family routing;
- multi-family fan-out;
- shared evidence;
- prevention of evidence double counting;
- model-set compatibility;
- aggregation/coordination of outputs;
- more complex testing and observability.

The core architectural question is:

> **Can the system gain the computational and governance benefits of smaller family BNs without introducing unsafe or unmanageable coordination between them?**

---

## 2. Definition

A federated BN architecture consists of:

- multiple family BNs;
- a common model contract;
- family discovery/routing;
- shared interaction evidence;
- controlled multi-family execution;
- coordination of family results;
- system-level safety policy;
- compatible model-set versioning.

Conceptually:

```text
Patient evidence
      │
      ▼
Shared safety / evidence handling
      │
      ▼
Family routing
      │
      ├────► ENT BN
      ├────► Respiratory BN
      ├────► Cardiac BN
      └────► Other family BNs
               │
               ▼
      Coordination / aggregation
               │
               ▼
       Next question / outcome
```

Federation is a **logical model topology**. It does not imply a microservice per family.

---

## 3. Why federation is attractive

### Smaller inference units

Each family graph can be materially smaller than an estate-wide monolith.

This can reduce:

- local CPT size;
- local treewidth;
- intermediate-factor size;
- per-family inference memory;
- clinical review scope.

### Localised clinical ownership

A family can be:

- designed;
- reviewed;
- tested;
- approved;
- versioned

as a bounded clinical artefact.

### Localised change blast radius

A family-specific clinical change may only require:

- that family artefact;
- affected boundary tests;
- compatibility tests.

This is potentially a major operational advantage.

### Better boundary handling than strict specialisation

Federation can allow more than one family to remain plausible while evidence is gathered.

### Incremental strategic rollout

The service can begin with one family and add additional clinically approved families over time.

---

## 4. The family problem

Federation relies on a meaningful decomposition of the clinical domain.

The current Phase 2 work provides data-driven candidate families, but these remain provisional.

The strategic family set should be:

1. clinician-led;
2. informed by Pathways structure;
3. evaluated for shared questions and overlap;
4. tested against historical triage data;
5. reviewed using clinically difficult boundary cases.

A poor family taxonomy simply moves complexity from inside one BN into routing and coordination.

---

## 5. Family routing

Federation needs a routing mechanism, but unlike strict specialisation the router does not always need to produce one winner.

A useful model is:

```text
Evidence
   │
   ▼
Candidate family scores
   │
   ├── ENT            high
   ├── Respiratory    medium
   ├── Allergy        medium
   └── Other          low
            │
            ▼
Bounded family set selected
```

The runtime might normally execute one family but allow two or more when evidence is ambiguous.

The exact fan-out policy must be clinically validated.

---

## 6. Bounded multi-family execution

Uncontrolled execution across every family would create unnecessary cost and complex evidence interactions.

Federation should therefore use bounded fan-out.

A conceptual policy might be:

- one family where evidence is strong;
- two families where evidence is materially ambiguous;
- a small controlled maximum for complex cases;
- immediate safety disposition or fallback where the family set remains unclear.

This policy is an architectural principle, not yet a clinically approved threshold.

---

## 7. Shared evidence

Shared evidence is central to federation.

Examples may include:

- demographics;
- pregnancy status;
- comorbidities;
- medication/risk factors;
- fever;
- breathing difficulty;
- consciousness;
- bleeding;
- pain characteristics.

The preferred design should avoid asking or storing the same observation independently in every family.

A possible evidence model is:

```text
Interaction evidence store
        │
        ├── evidence item A
        ├── evidence item B
        └── evidence item C
              │
              ├──── injected into ENT BN
              ├──── injected into Respiratory BN
              └──── injected into Cardiac BN
```

The evidence value is shared.

The probabilistic interpretation remains family-specific unless a shared probabilistic layer is introduced.

---

## 8. Evidence double counting

This is one of the most important technical risks in federation.

Suppose:

- ENT uses `breathing_difficulty = true`;
- Respiratory also uses the same evidence;
- each produces a posterior;
- an aggregator then combines those posterior values naively.

The same evidence could effectively influence the final decision twice.

Therefore:

> **Independent family posterior probabilities must not be combined as though they are statistically independent unless that independence is explicitly justified.**

Possible approaches include:

- routing to one active family at a time;
- using family outputs as decision signals rather than multiplying probabilities;
- a higher-level probabilistic coordination model;
- shared-core variables;
- explicitly modelled conditional dependencies.

The final aggregation method is a major design item.

---

## 9. Coordination patterns

Several federation patterns are possible.

### 9.1 Routed federation

Multiple families exist, but one is selected for active inference.

This is close to specialised BNs but retains common contracts and the ability to switch.

### 9.2 Parallel candidate-family inference

A bounded set of plausible families is evaluated.

Useful for ambiguity, but aggregation is more complex.

### 9.3 Hierarchical federation

A higher-level model routes or coordinates family models.

This may improve probabilistic consistency but introduces another model and its own dependencies.

### 9.4 Shared evidence with policy coordination

Family BNs remain probabilistically independent; a policy layer determines which question/outcome to act on.

This is simpler than probabilistic posterior aggregation but must be clinically justified.

---

## 10. Adaptive question selection

Federation introduces a question-selection problem above the family level.

Each family may independently propose its highest information-gain question.

The service then needs to decide:

> **Which question is most valuable for the interaction as a whole?**

Possible factors include:

- family plausibility;
- information gain within each model;
- safety priority;
- question cost/burden;
- whether the answer discriminates between families;
- whether the question is already known;
- channel constraints.

A future federated question selector may therefore need a system-level policy rather than simply choosing the highest family-local information gain.

---

## 11. Shared safety policy

Safety rules that apply across families should not be copied independently into every family where avoidable.

A common safety/policy layer can handle:

- emergency red flags;
- mandatory questions;
- channel constraints;
- age restrictions;
- stop conditions;
- maximum uncertainty;
- deterministic escalation;
- model-confidence/fallback rules.

This layer should remain distinct from the Bayesian model where the requirement is a non-negotiable safety constraint rather than a probabilistic relationship.

---

## 12. Model contracts

Every family should implement a common artefact contract.

```text
Family model manifest
├── family_id
├── family_version
├── schema_version
├── graph_version
├── clinical_scope
├── variables
├── states
├── CPTs
├── required_evidence
├── produced_signals
├── supported_channels
├── compatibility
├── boundary metadata
└── clinical approval
```

This is critical to adding new families without changing the inference engine.

---

## 13. Model-set compatibility

Independent family versioning creates a new requirement: compatible combinations must be controlled.

Example:

```text
Adaptive Triage Model Set 2027.06
├── safety-policy       v3
├── family-router       v2
├── ENT                 v4
├── Respiratory         v2
├── Cardiac             v5
└── shared-schema       v3
```

Every assessment should be traceable to the exact model set.

---

## 14. Runtime architecture

The preferred deployment shape remains centralised.

```text
API Gateway / WAF
       │
       ▼
Adaptive Triage Service
       │
       ├── Safety Policy
       ├── Evidence State
       ├── Family Router
       ├── Question Selector
       └── Model Registry
               │
       ┌───────┼────────┐
       ▼       ▼        ▼
     ENT BN   Resp BN  Cardiac BN
       │       │        │
       └───────┼────────┘
               ▼
       Coordination layer
               │
               ▼
      Structured triage outcome
```

The same worker process can hold multiple family models.

---

## 15. Model residency

Possible strategies include:

### All families resident

**Pros**

- predictable latency;
- no cold loading;
- simple runtime.

**Cons**

- higher memory floor.

### Lazy loaded/cache

**Pros**

- lower memory for rarely used families.

**Cons**

- cold-start latency;
- cache complexity;
- artefact-loading failure modes.

### Shared core resident + family cache

Potential hybrid pattern.

For early federation, keeping approved production families resident may be preferable while the total model estate remains modest.

---

## 16. Infrastructure requirements

Federation requires:

- central API/inference service;
- horizontally scalable stateless workers;
- externalised interaction/evidence state;
- model registry and manifest;
- versioned immutable family artefacts;
- routing configuration;
- model-set compatibility validation;
- family-level health metrics;
- audit of which families were invoked;
- model-version traceability;
- CloudWatch/OpenTelemetry-style traces;
- KMS/CloudTrail;
- blue/green/canary release capability;
- previous validated model set available for rollback.

Optional future capabilities:

- per-family autoscaling;
- artefact pre-warming;
- family-specific queues for non-runtime processing.

---

## 17. Clinical assurance

Federation can reduce assurance scope for local family changes, but only if system-level dependencies are controlled.

Assurance should be layered:

### Family-level

- graph;
- CPTs;
- local vignettes;
- calibration;
- local question selection.

### Boundary-level

- overlaps;
- family routing;
- transfers;
- multi-family cases;
- shared evidence.

### System-level

- safety policy;
- question-selection coordination;
- model compatibility;
- outcome aggregation;
- failover.

This is more complex than specialised BNs but potentially much more manageable than re-assuring an estate-wide graph for every local change.

---

## 18. Change blast radius

A well-designed federation can localise many changes.

```text
ENT CPT change
     │
     ▼
ENT model version
     │
     ├── ENT regression
     ├── boundary regression
     └── compatibility checks
            │
            ▼
     Updated model set
```

A change to shared evidence schema, routing, safety policy or aggregation has broader impact.

---

## 19. Failure isolation

Federation enables useful containment.

Examples:

- one family artefact can be withdrawn;
- a failing family can route to fallback;
- unaffected families can remain operational;
- family-specific rollback is possible.

However, failure of shared components such as:

- router;
- evidence store;
- safety policy;
- model registry

can affect the whole service.

---

## 20. Testing requirements

Federated testing needs:

- family-specific vignettes;
- family calibration;
- boundary vignettes;
- ambiguous-family cases;
- multi-family fan-out;
- evidence-sharing tests;
- double-counting tests;
- compatibility tests;
- model-set rollback;
- failure-isolation tests;
- performance with one vs multiple active families;
- adaptive-question coordination tests.

---

## 21. Cost considerations

Federation may reduce per-model inference cost, but can increase the number of model executions per assessment.

The relevant cost drivers include:

- family fan-out;
- resident model memory;
- average inference time;
- worker count;
- coordination overhead.

Phase 3E treats family fan-out explicitly as a scenario rather than assuming every interaction invokes exactly one model.

Infrastructure cost is not expected to be the primary decision criterion unless measured inference costs become unexpectedly large.

---

## 22. Advantages

- smaller local graphs;
- localised clinical ownership;
- reduced change blast radius;
- incremental rollout;
- potential lower family-level inference complexity;
- supports overlapping presentations better than strict specialisation;
- family-specific rollback/failure isolation;
- natural evolution from the first-family tactical pilot.

---

## 23. Disadvantages

- routing complexity;
- multi-family coordination;
- shared-evidence governance;
- evidence double-counting risk;
- version compatibility;
- more complex adaptive-question selection;
- greater operational observability requirements;
- family taxonomy becomes a strategic dependency.

---

## 24. Evidence gaps

Before final selection:

1. clinician-led family taxonomy;
2. measured family overlap after clinical refinement;
3. routing strategy;
4. safe multi-family fan-out policy;
5. aggregation/coordination method;
6. evidence ownership model;
7. cross-family question-selection policy;
8. representative family treewidth/inference benchmarks;
9. family-level assurance operating model;
10. model-set compatibility rules.

---

## 25. Current conclusion

Federation directly addresses two major concerns with a global monolith:

- computational scope;
- change/assurance blast radius.

It also avoids the strongest limitation of strict specialisation by allowing an interaction to remain associated with more than one plausible clinical family.

Its main cost is **coordination complexity**.

The option becomes increasingly attractive where clinically approved families are reasonably coherent but have meaningful overlap.

### Working position

> **Federation is a strong strategic candidate if clinician-led family decomposition produces coherent but overlapping clinical domains. The architecture must treat routing, shared evidence, double-counting prevention and model-set compatibility as first-class clinical-safety concerns.**
