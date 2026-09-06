# Probabilistic Triage — Project Context

## Purpose

Probabilistic Triage is a centralised, clinically explainable probabilistic triage capability for NHS England Digital Urgent and Emergency Care / Access, Triage and Navigation.

It uses Bayesian reasoning across symptoms, findings, demographics, risk factors and other clinical evidence to dynamically select questions and produce structured clinical triage outcomes for onward service selection.

The service also provides clinical users with tools to review, test, approve and govern model behaviour.

## Product context

The programme sits within a wider urgent and emergency care landscape including:

- Patient Triage API (deterministic pathway capability)
- iNav / ATN orchestration
- NHS App and 111 Online channels
- DoS / Find the Right Service
- TIM analytics
- Evaluation Platform / Provena
- Improve How We Author Content
- Triage Outcome Model (TOM)

Probabilistic Triage should be treated as a reusable national capability rather than channel-specific decision logic.

## Core components

### 1. Bayesian Network Build Pipeline

Purpose: create clinically governed Bayesian Network artefacts from trusted source material and data.

Typical stages:

- extract deterministic pathway questions, answers, relationships and metadata;
- derive or maintain ontology / clinical variables;
- define Bayesian Network structure;
- generate or estimate CPTs;
- use Bedrock / LLM assistance where appropriate at build time;
- use SageMaker or equivalent controlled compute for modelling activities;
- perform automated and clinical validation;
- present model structure and CPTs for clinician review;
- approve and publish an immutable versioned model artefact.

Key rule: AI/LLM assistance does not independently approve clinical content. Clinician review and sign-off remain mandatory.

### 2. Testing and Evaluation Capability

Purpose: establish evidence that a model behaves safely and effectively before release.

Capabilities include:

- clinical vignettes;
- deterministic baseline comparison;
- regression testing;
- safety-critical test suites;
- model discrimination and calibration metrics;
- question-efficiency analysis;
- outcome comparison;
- explainability review;
- test evidence suitable for release governance.

The Provena / Evaluation Platform workstream is relevant to the strategic testing capability.

### 3. Runtime Inference Engine

Purpose: execute approved Bayesian models during a triage interaction.

Responsibilities include:

- maintain interaction evidence/state;
- update posterior probabilities as evidence arrives;
- select the next most useful question;
- apply clinical risk policy and stopping rules;
- determine whether sufficient evidence exists to produce an outcome;
- provide explainability information;
- emit a structured triage result.

Question selection has been explored using Information Gain and similar approaches.

The engine must be version-aware so that model version, policy version, inputs and outputs can be reconstructed for audit.

### 4. FHIR API

Purpose: expose probabilistic triage through a stable interoperability contract.

The FHIR API should support integration from consuming services such as Patient Triage API and ATN/iNav rather than embedding inference inside those services.

Interop specialists are advisory rather than a dedicated delivery squad; implementation remains part of the programme delivery unless explicitly changed.

### 5. Clinical Admin UI

Purpose: allow authorised clinical/admin users to review, test, configure, approve and govern the probabilistic capability.

Known areas of functionality include:

- CIS2 authentication;
- model/version dashboard;
- Bayesian DAG visualisation;
- CPT viewing and review;
- model approval gates;
- model release / rollback controls;
- safety guardrails;
- risk tolerance and thresholds;
- channel-specific settings where required;
- model thresholds / stopping rules;
- testing and vignette integration;
- audit trail;
- evidence provenance;
- clinical sign-off workflow.

An AI vignette generator belongs within or adjacent to the testing/evaluation workflow, with generated material subject to clinical review.

### 6. ML-based Diagnostic Probability Capability — Future

A later capability may use machine learning to estimate condition/diagnostic probabilities from symptoms and available evidence.

This is not required to define the current runtime architecture and should not be treated as an excuse to move LLM reasoning into the live triage path.

## Bayesian Network direction

The programme originally considered larger monolithic Bayesian Networks and smaller specialised networks.

The preferred direction is now a hierarchical / federated topology:

- specialised Bayesian Networks model contained clinical families or domains;
- an aggregation/routing layer determines relevant specialist models;
- outputs can be reconciled into a coherent risk/disposition decision;
- common variables can be shared or mapped consistently;
- each specialist model remains clinically governable and testable.

This direction aims to reduce model complexity and CPT explosion while preserving cross-domain reasoning.

## Clinical model concepts

Clinical modelling discussed to date includes layers such as:

- demographics;
- comorbidities / exposure;
- history;
- risk assessment;
- clinical findings;
- symptoms;
- diagnostic hypotheses;
- disposition / urgency.

Disposition concepts have included T1/T2/T3/T4 style tiers, though API-facing outputs should align to the agreed Triage Outcome Model / FHIR representation.

## Runtime interaction pattern

Typical high-level flow:

1. Channel or orchestration service starts or continues a triage interaction.
2. Request enters the Probabilistic Triage API.
3. Runtime selects the approved model/model family and policy.
4. Existing evidence is applied to the Bayesian model.
5. Posterior probabilities are calculated.
6. Risk/stopping policy determines whether another question is required.
7. If required, the next question is returned.
8. If sufficiently resolved, a structured triage outcome is returned.
9. Explainability/audit information is recorded with relevant model and policy versions.

The synchronous path should remain as small and predictable as practical.

## Integration landscape

Potential/known consumers and adjacent services include:

- Patient Triage API;
- iNav / ATN orchestration;
- NHS App;
- 111 Online;
- DoS / Find the Right Service;
- NICE API where relevant;
- analytics / TIM capabilities;
- clinical authoring and evaluation platforms.

A hybrid deterministic-to-probabilistic pattern remains possible where Patient Triage API hands off to Probabilistic Triage, but the probabilistic decision making remains centrally owned by Probabilistic Triage.

## AWS technology position

Engineering Board has approved use of:

- AWS Bedrock;
- Amazon SageMaker;
- Amazon Neptune.

### Bedrock

Intended for controlled build-time assistance such as:

- source interpretation;
- extraction assistance;
- ontology/variable suggestions;
- model-generation assistance;
- test/vignette generation assistance;
- documentation and assurance support.

Bedrock is not intended to perform live runtime triage decisions.

All clinically relevant generated outputs must be reviewable and subject to clinician oversight before becoming part of an approved model or evidence pack.

### SageMaker

Intended for modelling, experimentation, data science and build-time compute where appropriate.

### Neptune

Approved graph technology for graph/model representations where the architecture requires it.

## Other AWS architecture principles

Likely/previously discussed components include:

- API Gateway;
- Lambda where suitable;
- S3 for versioned artefacts/evidence;
- DynamoDB or another state store where justified;
- CloudWatch for logging/telemetry;
- CloudTrail for audit;
- WAF;
- Step Functions for build workflows where orchestration provides value;
- CodePipeline / CodeBuild or equivalent CI/CD controls.

EventBridge was removed from the synchronous runtime triage request path because it is not required for a direct request/response interaction and can add unnecessary complexity.

## Security and information governance

Known programme positions include:

- DPIA in place;
- no PII intended for LLM processing;
- build/test LLM use only;
- clinician in the loop;
- outputs must be verifiable and suitable for scrutiny;
- auditability and traceability required;
- Class 4 data security requirements apply to the AWS environment;
- encryption, access control, audit logging and environment separation are expected baseline controls.

## Clinical safety and regulatory context

The system is clinical decision support and requires formal clinical safety and medical-device consideration.

Relevant principles include:

- DCB0129 / DCB0160 responsibilities where applicable;
- named clinical sign-off;
- reproducible evidence;
- controlled model release;
- regression and safety testing;
- traceability from source evidence through model version to runtime outcome;
- explicit human governance over model changes.

The programme is also assessing component/feature boundaries against medical-device software classification and function groups, including what keeps components within lower function groups versus what features push them higher.

## Explainability and audit

Runtime and build-time outputs should support:

- model version identification;
- policy/threshold version identification;
- input evidence reconstruction;
- probability/evidence contribution explanation;
- question-selection rationale where appropriate;
- final outcome rationale;
- clinician approval provenance;
- rollback to an earlier approved model.

Explainability should be useful to clinicians, assurance teams and investigators rather than exposing only opaque model internals.

## Triage Outcome Model / FHIR

Existing TOM work has rationalised output concepts including:

- main complaint;
- significant findings;
- management request;
- service type;
- timeframe;
- acuity / priority.

SNOMED CT is used for relevant coded clinical concepts and FHIR is the target interoperable representation.

The probabilistic service should align its structured output with the agreed TOM rather than inventing a competing outcome model.

## Delivery context

The programme has been moving rapidly from Alpha toward Beta, with a target direction of private beta by around March 2027.

Available roles have included architecture, software engineering, data science/AI engineering, testing, platform operations, business analysis, product, delivery, clinical, medical-device documentation, security, AI ethics, content, interaction design, technical writing and clinical safety.

The interoperability team is advisory and provides specialist FHIR guidance when engaged.

## Related strategic workstreams

There is significant overlap between:

- Probabilistic Triage;
- Evaluation Platform / Provena;
- TIM analytics;
- Improve How We Author Content.

The strategic direction is to avoid four isolated products where a coherent shared clinical safety/authoring/testing/governance capability is possible, while still allowing tactical delivery because the workstreams are at different maturity stages.

## Key non-functional qualities

Prioritise:

- clinical safety;
- explainability;
- reproducibility;
- auditability;
- interoperability;
- low-latency runtime behaviour;
- scalability;
- model/version governance;
- security;
- testability;
- rollback/recovery;
- operational observability.

## Performance context

The surrounding Patient Triage API has historically targeted approximately 300 ms response performance for its own synchronous interactions. Probabilistic Triage integration therefore needs to be conscious of latency, particularly in hybrid interactions, even if its final service-level targets differ.

## Working evidence from PoCs

Earlier proofs of concept indicated that adaptive probabilistic questioning could materially reduce question counts relative to deterministic pathways while maintaining high-risk detection in test scenarios. These are indicative results rather than production claims and should be backed by controlled evaluation before being used as formal benefit evidence.

## Scope discipline

When evaluating new features, consider whether they belong to:

- build-time modelling;
- testing/evaluation;
- runtime inference;
- interoperability/API;
- clinical administration/governance;
- analytics/monitoring;
- future ML capability.

Avoid allowing convenience features to blur those boundaries, particularly where this would alter medical-device classification, safety responsibilities, runtime risk or governance.