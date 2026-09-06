# Probabilistic Triage — Delivery

This folder captures the working delivery baseline for Probabilistic Triage.

## Delivery stage

The programme is in Alpha and moving toward Private Beta, with the near-term target framed around progression by March 2027.

## Delivery priorities

The build sequence should prioritise the capabilities that unlock safe end-to-end triage first:

1. Bayesian Network build pipeline;
2. inference engine foundation;
3. test/evaluation harness;
4. minimum Clinical Admin UI for review and release gates;
5. FHIR/API integration;
6. observability, audit and operational controls;
7. extended authoring/admin capability;
8. future ML-based diagnostic probability capability.

## Team shape

Known team capacity includes:

- 1 Architect;
- 1 Lead Software Engineer;
- 3 Senior Software Engineers;
- 1 Test Engineer;
- 4 Data Scientists / AI Engineers;
- 2 Platform Ops engineers;
- 3 Business Analysts;
- 1 Delivery Manager;
- 1 Product Manager;
- 1 MDD writer;
- 2 Clinicians;
- 1 Technical Writer;
- 1 Security Engineer;
- 1 AI Ethics Manager;
- 1 Content Writer;
- 1 Interaction Designer;
- CSO support;
- UR support;
- interoperability specialists available in an advisory capacity.

## Squad model

A practical delivery split is:

### Model / Inference squad

Focus:

- BN build pipeline;
- hierarchical/federated model design;
- CPT construction/calibration;
- inference engine;
- adaptive questioning;
- risk/disposition policy;
- explainability.

Likely disciplines:

- Data Science / AI Engineering;
- Lead/Senior Software Engineering;
- Architecture;
- Clinicians;
- BA support;
- Test support.

### Platform / Integration squad

Focus:

- runtime service/API;
- FHIR integration;
- persistence/configuration;
- CI/CD;
- AWS infrastructure;
- observability;
- security controls;
- integration with PTA/iNav and consuming channels.

Likely disciplines:

- Senior Software Engineering;
- Platform Ops;
- Architecture;
- Security;
- BA;
- Test;
- interoperability advisers.

### Clinical Experience / Governance squad

Focus:

- Clinical Admin UI;
- DAG/CPT review;
- thresholds and guardrails;
- approval workflow;
- audit visibility;
- vignette/test integration;
- clinical authoring/governance UX.

Likely disciplines:

- Product;
- Interaction Design;
- Content Design;
- Clinicians;
- Software Engineering;
- BA;
- UR;
- Test;
- MDD / Technical Writing.

These are delivery groupings rather than rigid organisational boundaries; clinical, safety, security and architecture input cuts across all squads.

## Interoperability model

The interoperability team is an **advisory expert team**, not a separate delivery squad expected to implement the full FHIR solution. Internal delivery teams remain responsible for implementation while engaging interoperability specialists at key design and assurance points.

## Evaluation dependency

The Evaluation Platform / Provena workstream is a strategic dependency for richer workflow testing and evidence generation. Probabilistic Triage still needs enough local test capability to progress safely without being blocked by another workstream's discovery/build timeline.

## Tactical vs strategic delivery

The broader landscape includes:

- Evaluation Platform / Provena — funded discovery;
- TIM — build phase;
- Improve How We Author Content — discovery pending;
- Probabilistic Triage — Alpha moving rapidly toward Beta.

Because these workstreams are at different maturity levels, delivery should allow tactical components where necessary while steering toward a shared strategic clinical authoring, evaluation, analytics and governance platform.

## Key delivery dependencies

- clinical availability and sign-off;
- approved model content / source data;
- Bedrock/SageMaker/Neptune environment readiness;
- FHIR contract agreement;
- Clinical Admin UI discovery and interaction design;
- evaluation capability;
- medical-device/regulatory position;
- cyber/IG controls;
- release governance and evidence production.

## Delivery risks

- attempting to build a monolithic BN too early;
- coupling runtime progress to unfinished strategic platform workstreams;
- unclear ownership between PTA/iNav and Probabilistic Triage;
- insufficient clinical review capacity;
- treating the Clinical Admin UI as a secondary concern when it is required for safe model governance;
- allowing build-time AI convenience to bypass formal review gates;
- insufficient automated regression and vignette coverage before Beta;
- premature introduction of ML/self-learning behaviour before the regulated baseline is stable.

## Working definition of Beta readiness

A credible Private Beta baseline should demonstrate:

- approved and versioned clinical model artefacts;
- stable inference runtime;
- safe adaptive questioning;
- structured API integration;
- minimum viable Clinical Admin UI and release gates;
- end-to-end traceability;
- automated and clinical vignette testing;
- security/IG controls;
- medical-device and clinical-safety evidence appropriate to the intended deployment;
- operational monitoring and rollback capability.