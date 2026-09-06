# Logical Architecture

## Purpose

Describe the high-level runtime and build-time shape of the Probabilistic Triage service.

## Runtime flow

1. A consuming channel or orchestrator gathers patient evidence.
2. The evidence is sent through a FHIR-aligned API contract.
3. The Probabilistic Triage API validates the request and resolves the approved model/policy version.
4. The inference engine applies evidence to the relevant Bayesian model(s).
5. The engine determines whether another question is required or whether sufficient evidence exists to make a triage decision.
6. Risk policy and safety guardrails are applied.
7. A structured outcome, explanation and audit trace are returned.

## Logical components

- API / interaction layer
- Runtime inference engine
- Bayesian model runtime
- Model routing / aggregation layer for federated models
- Risk and disposition policy
- Explainability / evidence trace
- Clinical Admin UI
- Testing and evaluation capability
- Build pipeline
- Model artefact repository
- Operational telemetry and audit

## Separation of concerns

### Build-time

Clinical content, data and approved AI assistance are used to create, calibrate, test and validate model artefacts.

### Runtime

Only approved and versioned model artefacts and policy configurations participate in live triage.

### Governance

Clinical users review, test, approve, configure and release model versions through controlled processes.

### Analytics

Operational telemetry and downstream data products must not introduce hidden decision logic into the clinical runtime path.

## Key integrations

- Patient Triage API
- iNav / ATN
- NHS App
- 111 Online
- DoS / Find the Right Service
- Evaluation platform
- TIM / analytics
- Terminology and content services

## Design constraints

- Centralised inference ownership
- Explainable outputs
- Reproducible decisions
- Version traceability
- Low synchronous-path complexity
- Interoperable contracts
- Clinical safety controls remain inside the governed capability