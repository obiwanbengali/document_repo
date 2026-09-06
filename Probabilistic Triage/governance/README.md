# Probabilistic Triage — Governance

This folder captures the current governance and assurance baseline for Probabilistic Triage.

## Governance model

Probabilistic Triage is a clinically governed decision-support capability. Changes to model structure, clinical variables, CPTs, thresholds, safety policy or release artefacts must be controlled, reviewable and auditable.

## Clinical governance

- Named clinicians review and approve clinically significant model changes.
- Build-time AI outputs are treated as proposals, not approved clinical truth.
- Model changes require evidence from testing/evaluation before release.
- Approved artefacts should be immutable and versioned.
- The system must support traceability from runtime outcome back to model version, policy version and relevant evidence.
- Rollback must be possible to a previously approved model/policy version.

## Clinical safety

Clinical safety work should align with applicable NHS clinical safety standards, including DCB0129/DCB0160 where relevant to the product and its deployment context.

Safety controls should include:

- explicit hazard analysis;
- controlled safety guardrails;
- high-risk scenario testing;
- regression testing across approved vignette sets;
- audit of model/policy changes;
- documented residual risk and clinical sign-off.

## Engineering and architecture governance

The programme has received Engineering Board approval to use:

- AWS Bedrock;
- AWS SageMaker;
- AWS Neptune.

The approved design intent is that Bedrock is used for build-time assistance and not as the runtime clinical triage decision-maker.

## Information governance

Current working position:

- DPIA in place;
- no requirement for personally identifiable information to be sent to LLMs for the approved build-time use cases;
- development/test use is controlled;
- clinician-in-the-loop review is maintained;
- evidence and audit trails are retained for assurance.

Any future use of production/patient-identifiable data with AI services requires explicit review rather than being inferred from the current approval.

## Cyber/security governance

Expected controls include:

- least-privilege IAM;
- encryption in transit and at rest;
- segregated environments/accounts as required;
- WAF/API protection;
- CloudTrail audit;
- CloudWatch operational monitoring;
- controlled secrets/configuration management;
- CIS2 for Clinical Admin UI access;
- controlled release pipelines.

## AI governance

The project should clearly distinguish between:

- **build-time generative AI assistance** — used to accelerate extraction, modelling or engineering tasks, always subject to human/clinical review;
- **runtime probabilistic reasoning** — performed by governed Bayesian/probabilistic models and policy logic;
- **future ML capabilities** — to be separately assured if/when introduced.

This distinction is important for AI policy, assurance, medical-device classification and evidence generation.

## Evidence expectations

Assurance outputs should stand scrutiny independently of the AI system that helped generate them. Evidence must be logically traceable and verifiable from source material through transformation, review, decision and approval.

## Release governance

A release should have, at minimum:

- unique model/version identifier;
- unique policy/configuration version;
- source provenance;
- test/evaluation evidence;
- clinical approval;
- technical approval as required;
- release timestamp;
- rollback target;
- audit trail of material changes.

See `../regulatory/README.md` for medical-device and regulatory context.