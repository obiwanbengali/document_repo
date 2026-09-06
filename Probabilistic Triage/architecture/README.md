# Probabilistic Triage — Architecture

This folder captures the current architectural baseline for the Probabilistic Triage capability.

## Logical view

The service is a **centralised probabilistic triage capability**. Consuming channels and orchestration services call the Probabilistic Triage API; they do not implement their own probabilistic clinical decision logic.

Typical flow:

1. Channel or orchestrator gathers/forwards patient evidence.
2. FHIR-aligned API contract passes structured evidence into Probabilistic Triage.
3. Runtime inference engine loads the approved model/version and policy configuration.
4. Bayesian reasoning updates probabilities from the available evidence.
5. Question-selection logic identifies the next useful question where further evidence is required.
6. Risk/disposition policy applies controlled clinical thresholds and safety guardrails.
7. The service returns a structured triage response with explainability/audit information.

## Core components

### Bayesian Network build pipeline

Purpose: convert approved clinical knowledge, deterministic pathway content, datasets and expert input into governed Bayesian model artefacts.

Typical stages:

- source extraction;
- ontology/terminology mapping;
- variable definition;
- graph/edge construction;
- CPT generation and calibration;
- clinical review;
- test/evaluation;
- approval;
- immutable model artefact publication.

AWS Bedrock may assist build-time engineering/clinical tasks, but generated output is reviewed before entering the approved model.

### Runtime inference engine

Responsibilities include:

- loading approved Bayesian model artefacts;
- applying observed evidence;
- probabilistic inference;
- information-gain/adaptive question selection;
- risk tolerance and safety policy;
- disposition determination;
- explainability and trace capture.

Runtime inference is deliberately separated from the build pipeline.

### FHIR/API integration

The API is the central contract between Probabilistic Triage and consuming services such as PTA/iNav and channels. Interoperability work should be aligned with the NHSE interoperability team.

### Clinical Admin UI

Primary capabilities include:

- CIS2 authentication;
- model/version visibility;
- DAG review;
- CPT review;
- thresholds and guardrails;
- channel settings;
- approval/release gates;
- test/vignette access;
- audit trail;
- rollback/governance support.

### Testing/evaluation capability

The evaluation platform and safety harness should be able to exercise triage workflows, compare model versions, run synthetic/clinical vignettes, and provide evidence for clinical and regulatory assurance.

## Bayesian topology

A single monolithic Bayesian Network can become difficult to scale, govern and calibrate across all possible conditions. The preferred direction is a **federated/hierarchical topology** with specialised Bayesian Networks for contained clinical families, coordinated by an appropriate routing/aggregation layer.

The target design should preserve:

- cross-domain evidence where clinically required;
- transparent routing between specialised models;
- consistent safety/disposition policy;
- versioning and traceability for every participating model;
- an explainable end-to-end reasoning trace.

## AWS baseline

Approved/expected technologies include:

- API Gateway / appropriate API layer for service exposure;
- Lambda and/or managed compute for service components where appropriate;
- SageMaker for model engineering/build workloads;
- Neptune for graph-oriented representation/use cases;
- Bedrock for approved build-time AI assistance;
- S3 for governed artefacts/evidence;
- CloudWatch for logging, metrics and operational telemetry;
- CloudTrail for audit;
- WAF and standard AWS security controls;
- CI/CD services for controlled promotion.

EventBridge is **not** part of the synchronous triage request/response path unless a new asynchronous use case explicitly warrants it.

## Integration context

Known/expected integration points include:

- Patient Triage API (deterministic pathways);
- iNav / ATN orchestration;
- NHS App;
- 111 Online;
- DoS / Find the Right Service;
- NICE terminology/content APIs where appropriate;
- evaluation/testing platform;
- TIM/analytics capability.

## Architecture qualities

The architecture must optimise for:

- clinical safety;
- explainability;
- reproducibility;
- version traceability;
- auditability;
- resilience;
- controlled latency;
- interoperability;
- rollback/release governance;
- separation of build-time AI assistance from runtime clinical decisioning.

See `../DECISIONS.md` for accepted decisions and current directions.