# Deep Dive — Specialised Bayesian Networks

**Status:** Draft for review  
**Decision pack:** Adaptive Triage Bayesian Architecture  
**Purpose:** Examine an architecture in which multiple independent Bayesian Networks each cover a bounded clinical domain and an interaction is routed to one specialised network.

---

## 1. Executive summary

A specialised Bayesian Network architecture uses multiple smaller BNs, each focused on a defined clinical domain or family. A routing decision selects the most appropriate BN and the interaction then continues within that model.

This has several attractive properties:

- smaller individual graphs;
- easier model comprehension;
- potentially simpler CPT authoring and review;
- clearer local ownership;
- smaller regression and release units;
- better failure isolation than one estate-wide monolith.

The key limitation is that real clinical presentations do not always respect clean family boundaries. If a patient presents with evidence spanning two or more domains, a strict specialised architecture must either:

1. choose one network before enough evidence is available;
2. transfer between networks;
3. duplicate shared concepts across networks; or
4. escalate outside the probabilistic model.

The central architectural question is therefore:

> **Can presentations be routed safely and sufficiently early to one independent specialist BN without losing clinically important cross-domain evidence?**

This is the principal distinction between specialised and federated approaches.

---

## 2. Definition

A specialised architecture contains multiple independent Bayesian Networks.

Each network:

- has its own graph;
- has its own CPTs;
- can be versioned independently;
- has a bounded clinical scope;
- receives a patient interaction after routing;
- does not formally coordinate posterior beliefs with other specialist networks.

Conceptually:

```text
Patient evidence
      │
      ▼
Family / domain router
      │
      ├────► ENT BN
      │
      ├────► Cardiac BN
      │
      ├────► Respiratory BN
      │
      └────► Neurology BN
                 │
                 ▼
              Outcome
```

A key characteristic is:

> **One interaction is intended to be owned by one specialist BN at a time.**

That differentiates this option from federation.

---

## 3. Why this option is attractive

### Smaller inference problems

Each BN contains only the variables needed for its clinical domain.

This can reduce:

- node count;
- CPT size;
- graph connectivity;
- treewidth;
- inference memory;
- inference latency.

### Easier clinical review

Clinicians can inspect a bounded graph rather than an estate-wide model.

This should make:

- DAG review;
- CPT review;
- vignette creation;
- safety-sign-off;
- impact assessment

more manageable.

### Localised change

A change to the ENT family need not automatically create a new Cardiac or Neurology artefact.

This can reduce release and assurance blast radius.

### Clearer ownership

Clinical ownership can align more naturally to clinical families or specialties.

### Incremental rollout

New specialist BNs can be added over time without requiring the complete clinical estate to be modelled first.

This aligns well with a tactical first-family private beta.

---

## 4. The routing problem

The main weakness of a specialised architecture is the need to decide which BN owns the interaction.

Consider:

```text
Sore throat
   +
Breathing difficulty
   +
Rash
```

Possible relevant domains might include:

- ENT;
- respiratory;
- allergy/anaphylaxis;
- systemic infection.

The correct domain may not be obvious at the start of the interaction.

A strict specialist approach therefore risks making a clinically significant architectural decision before enough evidence has been collected.

---

## 5. Routing strategies

Several routing strategies are possible.

### 5.1 Complaint-based routing

Use the patient's initial complaint to select a BN.

**Advantages**

- simple;
- fast;
- explainable.

**Risks**

- complaint wording may be ambiguous;
- patients may select the wrong symptom;
- important cross-domain risks may be hidden.

### 5.2 Deterministic pre-triage routing

Use a small ruleset before entering the BN.

**Advantages**

- safety rules can catch obvious red flags;
- domain choice can use several pieces of evidence.

**Risks**

- reintroduces deterministic clinical logic;
- routing rules become another governed clinical artefact;
- boundary cases remain.

### 5.3 Lightweight probabilistic router

Use a small probabilistic model to select a specialist BN.

**Advantages**

- supports uncertainty.

**Risks**

- effectively begins moving the architecture toward federation/hybrid;
- introduces another model requiring assurance;
- may still select the wrong family.

### 5.4 Transfer between specialist BNs

Start in one BN and transfer to another when evidence changes.

**Advantages**

- allows late discovery of a better family.

**Risks**

- how evidence is mapped between models becomes complex;
- posterior beliefs cannot simply be transferred unless the models share a compatible probabilistic representation;
- question repetition and loss of context become possible.

---

## 6. Shared concepts

Specialised networks will inevitably share some observations.

Examples might include:

- age;
- sex;
- pregnancy status;
- fever;
- pain severity;
- consciousness;
- breathing difficulty;
- bleeding;
- immunosuppression;
- major comorbidity.

There are three broad ways to deal with this.

### Duplicate shared variables

Each BN contains its own copy.

**Benefit:** simplest runtime.

**Risk:** duplicated semantics and CPT logic can drift.

### Externalise shared evidence

Keep evidence values outside the BNs and inject them into whichever model is selected.

**Benefit:** consistent observation semantics.

**Risk:** the effect of the evidence is still duplicated across multiple CPTs.

### Create a shared probabilistic layer

This moves the architecture away from purely specialised BNs and toward a hybrid/federated design.

---

## 7. Adaptive questioning implications

Within a specialist BN, information-gain question selection can be straightforward.

However, the architecture creates a higher-order question:

> **How do we know that the next best question belongs to the selected specialist BN?**

If the wrong network was selected, the adaptive algorithm can optimise efficiently inside the wrong clinical boundary.

That is an important safety risk.

A specialist architecture therefore needs either:

- very strong routing confidence;
- mandatory cross-domain safety gates;
- a transfer mechanism;
- or an external shared question/safety policy.

---

## 8. Clinical safety considerations

### Risks reduced

- smaller graph easier to inspect;
- fewer unintended long-range dependencies;
- family-level regression;
- family-level rollback;
- clearer clinical ownership.

### Risks introduced

- wrong-family routing;
- missed cross-domain presentations;
- duplicated safety logic;
- inconsistent meaning of shared evidence;
- evidence loss during family transfer;
- premature family lock-in.

### Required controls

At minimum:

- clinically approved family boundaries;
- explicit inclusion/exclusion criteria;
- common emergency/red-flag policy;
- routing confidence thresholds;
- deterministic or clinically safe fallback;
- transfer/escalation criteria;
- boundary-specific vignettes;
- audit of why a family was selected.

---

## 9. Family definition

A specialised architecture is only as good as its family taxonomy.

Family definition should be:

1. clinician-led;
2. informed by Pathways structural overlap;
3. validated using historical triage data where available;
4. tested using boundary-case vignettes.

The current Phase 2 candidate families are therefore useful analytical evidence but should not be treated as clinically final.

---

## 10. Model contracts

Every specialist model should conform to the same generic family contract.

For example:

```text
Family model manifest
├── family_id
├── model_version
├── schema_version
├── clinical_scope
├── inclusion_criteria
├── exclusion_criteria
├── variables
├── states
├── DAG
├── CPTs
├── supported_channels
├── supported_age_groups
├── safety_constraints
├── boundary_conditions
└── clinical_approval_metadata
```

The inference engine should not contain family-specific code.

---

## 11. Runtime architecture

A production-shaped implementation could be:

```text
Adaptive Triage API
       │
       ▼
Central Inference Service
       │
       ▼
Family Router
       │
       ├────► ENT BN
       ├────► Cardiac BN
       ├────► Respiratory BN
       └────► ...
       │
       ▼
Structured Outcome
```

All specialist BNs can still run inside the same centrally managed inference service.

A service-per-family deployment is not required.

---

## 12. Infrastructure implications

The infrastructure requirements are broadly similar to the other options:

- API Gateway/WAF;
- horizontally scaled stateless inference workers;
- external interaction-state store;
- immutable model artefacts in S3;
- model registry/manifest;
- KMS encryption;
- CloudTrail;
- observability and audit;
- blue/green or canary deployment;
- previous validated model available for rollback.

Additional specialist-specific requirements include:

- family routing capability;
- family-to-model lookup;
- family-specific model health;
- routing audit;
- family-specific model metrics;
- safe handling when a requested family is unavailable.

---

## 13. Versioning

Specialised BNs allow family-level versioning.

Example:

```text
ENT            v1.4
Respiratory    v2.1
Cardiac        v1.8
Neurology      v1.2
```

This is operationally attractive.

However, the system still needs a versioned model-set manifest so that every interaction is traceable to the approved combination of:

- inference engine;
- safety policy;
- routing logic;
- family BN;
- terminology/schema version.

---

## 14. Failure modes

Important failure cases include:

### Wrong family selected

The model may ask clinically coherent but irrelevant questions.

### Family unavailable

The runtime must fall back safely rather than silently choosing another model.

### Boundary discovered late

The service must determine whether to:

- transfer;
- restart;
- fall back;
- escalate;
- invoke a second model.

### Shared concept inconsistency

Two families may interpret the same observation differently.

### Routing drift

Changes to family scope can alter which patients are routed where.

This needs testing like a clinical model change.

---

## 15. Testing requirements

Specialised BN testing should include:

- family-specific clinical vignettes;
- boundary vignettes;
- deliberately ambiguous presentations;
- wrong-family routing tests;
- emergency/red-flag cases;
- transfer/fallback tests;
- question-selection regression;
- calibration and discrimination;
- family-specific performance/load tests;
- model-version rollback tests.

Boundary testing is particularly important because that is where the architecture is weakest.

---

## 16. Change blast radius

This is one of the strongest characteristics of specialised BNs.

```text
ENT variable/CPT change
        │
        ▼
ENT artefact changes
        │
        ▼
ENT regression / assurance
        │
        ▼
ENT model release
```

However, if the change affects:

- shared safety policy;
- routing;
- common evidence schema;
- terminology;
- family inclusion criteria,

the blast radius becomes broader.

---

## 17. Cost considerations

Smaller BNs may:

- require less memory per loaded model;
- execute inference faster;
- make per-family scaling possible.

But cost savings may be offset by:

- multiple resident model artefacts;
- routing infrastructure;
- extra monitoring;
- compatibility management.

At expected NHS-wide volumes, these cost differences are unlikely to outweigh clinical and operational design concerns without evidence from measured workloads.

---

## 18. Advantages

- smaller individual BNs;
- easier clinical comprehension;
- potentially lower inference complexity;
- localised testing and assurance;
- localised change and rollback;
- incremental family rollout;
- clearer ownership;
- strong fit for the first-family tactical approach.

---

## 19. Disadvantages

- clinically significant routing decision required early;
- weak handling of multi-domain presentations;
- risk of family lock-in;
- shared evidence duplication;
- potential question repetition across transfers;
- transfer semantics are difficult;
- family taxonomy becomes a major safety dependency.

---

## 20. Evidence gaps

Before selecting this as the strategic design we need:

1. clinician-approved family definitions;
2. measured proportion of clearly single-family vs ambiguous presentations;
3. boundary-case analysis;
4. transfer/fallback design;
5. evidence on how often multiple families are plausible;
6. clinical assessment of whether shared safety policy is sufficient;
7. performance evidence for representative family sizes;
8. model ownership and assurance operating model.

---

## 21. Current conclusion

Specialised BNs provide a strong simplification compared with an estate-wide monolith and align naturally with incremental clinical ownership.

Their main weakness is structural:

> **They require the architecture to make a single-family choice even when the patient's presentation may legitimately span multiple clinical domains.**

This makes specialised BNs a credible option where families are strongly separable, and a useful tactical pattern for the first ENT family, but it may be too restrictive as the strategic architecture if clinically approved families have significant overlap.

### Working position

> **Use specialised BNs as a serious comparator and tactical building block, but test whether single-family ownership remains clinically credible once family boundaries are defined.**
