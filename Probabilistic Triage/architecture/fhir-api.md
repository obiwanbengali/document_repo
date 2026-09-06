# FHIR API

## Purpose

Provide a stable, interoperable API contract between consuming channels/orchestrators and the central Probabilistic Triage capability.

## Architectural position

The API exposes centralised probabilistic inference. Consumers should not duplicate or reinterpret probabilistic clinical decision logic.

Likely consumers include:

- Patient Triage API;
- iNav / ATN;
- NHS App-mediated journeys;
- 111 Online;
- future approved channels.

## Contract principles

- FHIR-aligned representation.
- Stateless interaction contract where practical.
- Explicit API and model versioning.
- Structured evidence rather than free-text dependence where possible.
- Clear distinction between an intermediate `next question` response and a final triage outcome.
- Idempotent/reconstructable behaviour where practical.
- Traceability of evidence supplied by the caller.

## Typical request content

Potential request data includes:

- interaction/session identifier;
- patient demographic context;
- known clinical evidence;
- answers collected so far;
- channel/context metadata;
- requested/compatible API version.

## Typical response types

### Continue assessment

- next question;
- structured answer options;
- question identifier / terminology;
- relevant interaction metadata.

### Assessment complete

- structured triage outcome;
- disposition/acuity/timeframe information;
- supporting clinical findings where contractually appropriate;
- evidence references;
- model/policy version;
- explainability/audit reference.

## TOM alignment

The Triage Outcome Model remains important to downstream outcome representation. Current working direction includes:

- SNOMED CT-backed complaint/findings and management/service concepts where appropriate;
- externally controlled values for properties such as timeframe/priority where the agreed model requires them;
- evidence/reference structures to preserve why the outcome was produced.

Formal TOM and interoperability artefacts take precedence over this summary.

## Hybrid integration

A tactical hybrid flow may involve Patient Triage API handing off from deterministic pathways to Probabilistic Triage. That introduces orchestration, latency, state and versioning overhead and should remain explicit in integration design.

## Performance

The API should minimise additional synchronous-path latency. Detailed non-functional targets should be confirmed against the consuming ecosystem and beta load assumptions.

## Ownership

Probabilistic Triage owns probabilistic clinical reasoning and decision behaviour. Consuming services own their own orchestration/presentation responsibilities. The NHSE interoperability team provides expert advice on FHIR alignment rather than acting as the delivery squad for all API implementation.