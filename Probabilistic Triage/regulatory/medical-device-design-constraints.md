# Medical Device Design Constraints

## Purpose

Capture design constraints that help maintain a clear and governable medical-device boundary while Probabilistic Triage evolves.

Formal regulatory and clinical-safety documentation takes precedence over this working summary.

## Separation of runtime decisioning and support tooling

Keep a clear architectural boundary between:

- software that directly performs patient-specific probabilistic triage; and
- software used to author, inspect, test, govern, approve or monitor that capability.

Where practical, higher-risk patient-specific decision functions should not be casually embedded into general administrative tooling.

## No runtime generative-AI decisioning

Generative AI / LLM output must not directly determine live patient triage or disposition under the current programme position.

Approved AI use is build-time assistance with human review before clinically significant outputs become active.

## Controlled activation

Changes to clinically significant artefacts should follow a controlled lifecycle:

1. draft/change created;
2. validation performed;
3. tests executed;
4. clinician review completed;
5. formal approval recorded;
6. immutable version produced;
7. controlled release/promotion;
8. rollback path retained.

## Configuration boundaries

Thresholds, guardrails, model parameters and channel-specific clinical policies must not become unconstrained runtime knobs.

Prefer:

- validated ranges;
- role restrictions;
- named approval;
- versioned configuration;
- effective dates;
- full audit history.

## Explainability and evidence

For clinically meaningful outputs, retain sufficient information to establish:

- input evidence;
- model version;
- policy/configuration version;
- relevant probability/risk state;
- decision or stopping rationale;
- resulting disposition;
- timestamp and interaction reference.

## Continuous learning

Do not permit production models to autonomously learn from live patient interactions and alter clinical behaviour without the governed model lifecycle.

Training or recalibration based on operational data should result in a new candidate version that passes the normal validation and approval process.

## Vignette generation

AI-generated vignettes may support build/test activity, but generated cases should be identifiable as synthetic/draft and require appropriate clinical review before being treated as assurance evidence.

## Administrative UI

Where possible, design Clinical Admin UI features as:

- inspection;
- controlled authoring;
- simulation/testing;
- review;
- workflow approval;
- release management.

Avoid allowing an admin action to silently alter active patient-specific decision behaviour without explicit governed promotion.

## Architectural decomposition

If a feature would materially increase the regulatory significance of an otherwise lower-risk component, consider separating it into a distinct service/component with its own classification, controls and evidence rather than blurring boundaries.

## Reassessment triggers

A regulatory reassessment should be expected for changes involving:

- new patient-specific diagnostic claims;
- materially different triage/disposition behaviour;
- autonomous recommendations;
- new intended users or use settings;
- production learning/adaptation;
- removal of human review from clinically significant model changes;
- new generative-AI runtime use;
- changes to intended purpose.