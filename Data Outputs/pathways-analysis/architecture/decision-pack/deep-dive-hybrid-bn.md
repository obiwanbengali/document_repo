# Deep Dive — Hybrid Bayesian Network Architecture

**Status:** Draft for review  
**Decision pack:** Adaptive Triage Bayesian Architecture  
**Purpose:** Examine architectures combining shared/common probabilistic capability with clinically bounded family Bayesian Networks.

---

## 1. Executive summary

A hybrid Bayesian architecture combines more than one topology pattern.

In the Adaptive Triage context, the most relevant hybrid is likely to combine:

- a small set of shared/common evidence or probabilistic concepts; and
- multiple clinically bounded family BNs.

The attraction is that common concepts do not need to be independently reinvented inside every family, while family-specific inference remains bounded.

However, “hybrid” is not a single architecture. Several materially different variants exist, and selecting one too early risks creating a large shared core that recreates many of the disadvantages of a monolith.

The central architectural question is:

> **Is there enough clinically meaningful shared probabilistic structure between family BNs to justify a common probabilistic layer, rather than simply sharing evidence and policy?**

The answer should come from clinician-led family modelling, not from infrastructure preference.

---

## 2. Definition

A hybrid architecture combines:

- shared/common capability;
- family-specific BNs;
- central coordination.

The shared capability might be:

- evidence only;
- deterministic safety/policy;
- a small Bayesian shared core;
- a higher-level routing/aggregation BN;
- or a combination.

Therefore the strategic ADR should not treat “hybrid” as one fixed implementation.

---

## 3. Candidate hybrid patterns

### 3.1 Shared evidence + family BNs

```text
             Shared evidence
          age / fever / risks
             /      |      \
            /       |       \
         ENT BN   Resp BN   Cardiac BN
```

The evidence is shared, but there is no shared probabilistic BN.

This is the lightest hybrid.

### 3.2 Shared safety/policy + family BNs

```text
Evidence
   │
   ▼
Common safety / guardrail layer
   │
   ▼
Family routing
   │
   ├── ENT BN
   ├── Respiratory BN
   └── Cardiac BN
```

This is likely to be required regardless of whether a probabilistic shared core exists.

### 3.3 Shared/core BN + family BNs

```text
               Shared/Core BN
                    │
          ┌─────────┼─────────┐
          ▼         ▼         ▼
        ENT BN    Resp BN   Cardiac BN
```

Common probabilistic concepts are modelled once.

### 3.4 Hierarchical routing BN + family BNs

```text
Evidence
   │
   ▼
Higher-level BN
   │
   ├── ENT probability
   ├── Resp probability
   └── Cardiac probability
          │
          ▼
     Family BN(s)
```

The upper model helps determine which specialist models should participate.

### 3.5 Shared core + federated families + policy

The richest pattern:

```text
          Safety / policy
                │
                ▼
           Shared Core BN
                │
                ▼
          Family routing
                │
        ┌───────┼────────┐
        ▼       ▼        ▼
      ENT BN  Resp BN  Cardiac BN
        │       │        │
        └───────┼────────┘
                ▼
          Coordination
```

This has the greatest expressive power but also the greatest coupling.

---

## 4. Why a hybrid could be attractive

Clinical families are unlikely to be completely independent.

Some concepts may genuinely be cross-cutting.

Examples might include:

- age-related risk;
- pregnancy;
- immunosuppression;
- consciousness;
- airway compromise;
- breathing difficulty;
- haemodynamic instability;
- severe systemic illness indicators.

If those concepts are modelled independently in every family:

- semantics may drift;
- evidence can be duplicated;
- CPT logic can become inconsistent;
- maintenance becomes repetitive.

A shared layer may therefore improve consistency.

---

## 5. The danger of recreating the monolith

The most important hybrid pitfall is shared-core growth.

A reasonable design may start with:

```text
Shared core
├── age
├── sex
├── fever
└── consciousness
```

and gradually become:

```text
Shared core
├── demographics
├── observations
├── comorbidities
├── common symptoms
├── generic diagnoses
├── risk
├── disposition
└── ...
```

At that point the architecture has recreated a central monolith plus family extensions.

Therefore:

> **The shared probabilistic core should exist only where there is evidence that the concept and its probabilistic meaning are genuinely shared.**

---

## 6. Shared evidence is not the same as a shared BN

This distinction is fundamental.

A value such as:

`fever = true`

can be recorded once in the interaction evidence store and injected into several family BNs.

That does not mean its probabilistic relationships must be modelled in a central BN.

The architecture should prefer the simplest sharing mechanism that preserves clinical meaning.

Possible progression:

```text
Shared data value
      │
      ▼
Shared evidence contract
      │
      ▼
Only if justified:
Shared probabilistic variable/core
```

---

## 7. Clinical criteria for shared-core membership

A concept should only enter a shared probabilistic layer where clinicians agree that:

- its semantic meaning is stable across families;
- its state model is consistent;
- it has genuinely cross-family causal/probabilistic relevance;
- centralising it improves rather than obscures clinical reasoning;
- its change governance can be managed system-wide.

If any of these fail, family-local modelling may be safer.

---

## 8. Shared safety policy should remain distinct

Some common behaviour belongs in policy rather than probability.

Examples:

- mandatory red-flag question;
- immediate emergency disposition;
- minimum age restriction;
- unsupported channel;
- model-confidence fallback;
- maximum interaction limits;
- non-negotiable clinical guardrail.

These should not be moved into a probabilistic shared core simply because they apply to all families.

A likely architecture therefore has both:

- common deterministic safety/policy;
- optional shared probabilistic concepts.

---

## 9. Routing and family selection

A hybrid architecture can use the shared layer to support routing.

For example:

```text
Initial evidence
      │
      ▼
Shared/core inference
      │
      ▼
Candidate family signals
      │
      ├── ENT
      ├── Respiratory
      └── Cardiac
```

This may reduce duplicate routing logic.

However, it creates a central dependency: if the shared model is wrong, routing errors can affect every family.

---

## 10. Adaptive questioning

A shared layer may help select questions that are useful across several candidate families.

For example, one question could:

- reduce shared uncertainty;
- discriminate between families;
- provide family-local evidence.

This is potentially a major benefit of a well-designed hybrid.

But question selection becomes more complex because information gain may exist at:

- shared-core level;
- family level;
- family-routing level;
- safety-policy level.

The question-selection engine therefore needs a clearly defined priority policy.

---

## 11. Probabilistic consistency

If a shared BN and family BNs exchange probabilities, the semantics must be explicit.

Potential patterns include:

- shared evidence only;
- shared posterior passed as a prior into a family;
- family likelihood returned to the shared model;
- iterative message passing;
- one-direction hierarchical inference.

Each has different mathematical assumptions.

The system must not pass posterior probabilities between models informally.

Otherwise there is a risk of:

- evidence double counting;
- inconsistent priors;
- cyclic dependency between model layers;
- difficult-to-explain outcomes.

---

## 12. Model contracts

Hybrid models need more explicit compatibility metadata than specialised models.

A family artefact may need to declare:

```text
family_id
family_version
required_shared_core_version
required_schema_version
consumed_shared_variables
produced_family_signals
compatibility_range
clinical_approval
```

Similarly, the shared model must declare which family-model contract versions it supports.

---

## 13. Model-set versioning

An approved release should be represented as one immutable model set.

Example:

```text
Adaptive Triage Model Set 2027.09
├── safety-policy       v4
├── evidence-schema     v5
├── shared-core         v2
├── family-router       v3
├── ENT                 v6
├── Respiratory         v3
└── Cardiac             v5
```

This is essential for audit and rollback.

---

## 14. Runtime architecture

A production-shaped hybrid could look like:

```text
API Gateway / WAF
        │
        ▼
Adaptive Triage Service
        │
        ├── Safety Policy
        ├── Evidence State
        ├── Shared/Core Inference
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
           Coordination
                 │
                 ▼
              Outcome
```

All elements can remain inside one centralised service boundary.

---

## 15. Infrastructure requirements

Infrastructure is similar to federation but may additionally require:

- resident shared-core artefact;
- family-core compatibility checks;
- shared-core health metrics;
- model-set deployment atomicity;
- rollback of coordinated core/family versions;
- performance traces across multiple inference stages.

At modest model counts, both shared and family models can likely remain resident.

---

## 16. Change blast radius

Hybrid architecture creates different release scopes.

### Family-local change

Potentially limited to:

- one family;
- affected boundary tests;
- compatibility tests.

### Shared-core change

Potentially affects:

- every family consuming that core;
- routing;
- question selection;
- calibration;
- system regression.

Therefore a shared core has a larger blast radius than a family model.

This should make the bar for adding variables to the shared core deliberately high.

---

## 17. Clinical assurance

Assurance becomes layered.

### Shared layer

Needs system-wide clinical ownership because its effects cross families.

### Family layer

Can have local domain ownership.

### Boundary layer

Needs assurance of the interface between shared and family models.

### Policy layer

Needs explicit clinical-safety governance independent of probabilistic calibration.

This may align well with real clinical governance, but only if ownership boundaries are clear.

---

## 18. Failure modes

Important failures include:

### Shared-core failure

Potentially affects every family.

### Shared/family version incompatibility

Could produce invalid inference unless blocked at deployment.

### Shared evidence semantic drift

A family may interpret a shared variable differently from the core.

### Over-centralisation

Too much family logic migrates into the shared layer.

### Double counting

Evidence processed in the shared core may be reintroduced incorrectly into family inference.

### Cascading latency

Sequential shared-core + family inference can increase response time.

---

## 19. Testing requirements

Hybrid testing needs all federated tests plus:

- shared-core unit/calibration testing;
- family-core compatibility tests;
- shared-variable semantic tests;
- double-counting tests;
- end-to-end hierarchical inference tests;
- shared-core change-impact regression;
- multi-stage performance tests;
- fallback where shared core is unavailable;
- rollback of coordinated model sets.

---

## 20. Cost considerations

A shared core can reduce duplication across family models but adds an inference stage.

Cost therefore depends on:

- shared-core model size;
- number of family models invoked;
- whether inference is sequential or parallel;
- resident memory;
- model fan-out.

As with federation, infrastructure cost should be treated as a secondary criterion until measured model behaviour is available.

---

## 21. Advantages

- reduces duplication where concepts are genuinely shared;
- keeps family-specific graphs smaller;
- potentially supports better family routing;
- potentially supports cross-family adaptive questioning;
- localises many family changes;
- allows system-wide safety/policy consistency;
- may provide a better representation of overlapping clinical structure than either pure monolith or strict specialisation.

---

## 22. Disadvantages

- most complex topology option;
- shared-core governance;
- compatibility management;
- risk of recreating a monolith;
- risk of double counting;
- multi-stage latency;
- more complex testing and explainability;
- shared-core failures have broad blast radius.

---

## 23. Evidence gaps

Before selecting hybrid strategically:

1. clinician-approved family taxonomy;
2. measured amount of truly shared clinical structure;
3. definition of shared evidence vs shared probability;
4. candidate shared variables;
5. causal/probabilistic justification for shared-core dependencies;
6. model-to-model message semantics;
7. shared/family compatibility contract;
8. multi-stage inference benchmark;
9. change-impact assessment for shared-core updates;
10. clinical ownership model.

---

## 24. Decision trigger: when hybrid becomes preferable to federation

A hybrid should not be selected simply because it is more sophisticated.

It becomes materially attractive if clinical family analysis shows that:

- substantial concepts are genuinely shared;
- duplicating those concepts causes inconsistency or excessive maintenance;
- cross-family question selection materially benefits from a common probabilistic layer;
- a small shared core can remain stable and understandable;
- shared-core governance is acceptable.

If the families share only evidence values and safety rules, **federation with common evidence/policy may be sufficient without a probabilistic shared core**.

---

## 25. Current conclusion

Hybrid architecture may ultimately provide the best balance where clinically agreed families have significant and meaningful shared probabilistic structure.

However, it should emerge from evidence rather than being designed in advance.

The strategic sequence should therefore be:

```text
Clinician-led family definition
          │
          ▼
Measure overlap and shared concepts
          │
          ├── mainly independent
          │       ▼
          │   Federated
          │
          └── substantial true shared structure
                  ▼
               Hybrid
```

### Working position

> **Treat hybrid as a strong strategic candidate only where clinician-led family modelling demonstrates a stable, genuinely shared probabilistic core. Prefer shared evidence and policy over a shared BN unless probabilistic centralisation is clinically justified.**
