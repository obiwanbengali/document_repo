# Delivery Roadmap

## Current position

Probabilistic Triage is moving from Alpha toward Beta. Delivery should prioritise the minimum integrated capability needed to demonstrate safe, governed probabilistic triage end to end.

## Recommended build sequence

### 1. Model foundations

- establish clinical domain and variable model;
- build initial Bayesian Network pipeline;
- define terminology mappings;
- create repeatable model artefact/version format;
- establish clinician review gates.

### 2. Runtime inference core

- implement Bayesian inference runtime;
- evidence application;
- adaptive question selection;
- stopping criteria;
- risk/disposition policy;
- explainability trace.

### 3. Test and evaluation baseline

- automated model checks;
- safety harness;
- clinical vignette runner;
- deterministic baseline comparison;
- regression testing;
- initial calibration measures.

### 4. Clinical governance interface

Deliver a minimal Clinical Admin UI supporting:

- model/version inspection;
- DAG/CPT visibility;
- guardrails and threshold visibility;
- test/vignette review;
- clinical approval gates;
- release audit.

### 5. Integration contract

- define FHIR-aligned API;
- implement interaction contract;
- integrate with PTA/iNav as appropriate;
- establish error/fallback semantics;
- performance and resilience testing.

### 6. Beta hardening

- security and operational controls;
- regulatory evidence;
- DCB0129 clinical safety evidence;
- observability;
- rollback/release process;
- performance/load testing;
- usability/accessibility for clinical admin functions;
- production-readiness evidence.

### 7. Federated topology evolution

As clinical scope expands:

- partition domains into specialised networks;
- implement routing/aggregation;
- establish shared variable/ontology standards;
- test composed-model safety and calibration.

### 8. Future ML capability

Machine-learning approaches for diagnosis probability estimation/calibration may be introduced later through the governed build pipeline. They should not bypass the approved Bayesian/runtime governance model.

## Key dependencies

- clinical availability and sign-off;
- CSO and clinical safety process;
- regulatory/MDD direction;
- interoperability expertise;
- source clinical content and data;
- TIM/ECDS data access where needed;
- AWS platform/security controls;
- Evaluation Platform alignment;
- authoring-tool strategic direction.

## Strategic product convergence

Probabilistic Triage, Evaluation Platform, TIM and Improve How We Author Content have overlapping needs around:

- clinical content;
- model/configuration authoring;
- testing;
- analytics;
- approval;
- governance.

Near-term delivery should avoid blocking Probabilistic Triage Beta, while using interfaces and reusable components that support convergence toward a strategic clinical authoring, assurance and evaluation capability.

## Delivery principle

Do not make Beta dependent on solving the entire strategic platform. Build tactical capability where necessary, but make the boundary explicit and avoid decisions that prevent later convergence.