# Probabilistic Triage — Product

This folder captures the product intent, scope, users, capabilities, boundaries and integration context for Probabilistic Triage.

## Product definition

Probabilistic Triage is a **centralised, clinically explainable probabilistic triage capability** that reasons across symptoms, findings, demographics and risk factors using Bayesian Networks. It dynamically selects questions and produces structured clinical triage outcomes for onward service selection.

The service also provides clinical users with tools to review, test, approve and govern model behaviour.

## Product goals

- Improve triage efficiency by reducing unnecessary questioning.
- Preserve or improve clinical safety compared with deterministic baselines.
- Provide explainable probabilistic reasoning suitable for clinical assurance.
- Enable consistent probabilistic decisioning across consuming channels.
- Support controlled model authoring, testing, approval and release.
- Provide structured outputs suitable for downstream service selection and orchestration.
- Create a national capability that can be reused across multiple digital urgent and emergency care channels.

## Primary users and stakeholders

### End-user channels

Probabilistic Triage does not own the main public-facing user interfaces. Expected consumers include:

- NHS App;
- 111 Online;
- Patient Triage API integrations;
- iNav / ATN orchestration.

### Clinical/admin users

Clinical authors, reviewers and governance users require a Clinical Admin UI to inspect and govern model behaviour.

### Delivery and assurance stakeholders

- Product;
- Architecture;
- Clinical safety;
- Clinical SMEs;
- Data science / AI engineering;
- Software engineering;
- Test/evaluation;
- Information governance;
- Cyber/security;
- AI ethics;
- Medical device/regulatory teams;
- Interoperability specialists.

## Core product components

1. **Bayesian Network Build Pipelines** — extraction, ontology, model structure, CPTs and artefact generation.
2. **Testing / Evaluation Capability** — vignette execution, safety harness, model comparison and evidence generation.
3. **Inference Engine** — runtime Bayesian inference, adaptive questioning, risk policy and disposition.
4. **FHIR API** — central integration contract for consuming services.
5. **Clinical Admin UI** — model review, gates, guardrails, thresholds, channel settings and governance.
6. **ML-based diagnostic probability capability** — future capability for learned diagnosis probabilities.

## Current delivery emphasis

The near-term focus is on:

- Bayesian model build capability;
- inference engine;
- minimum viable Clinical Admin UI;
- test/evaluation harness;
- FHIR integration;
- evidence, audit and release governance;
- progression from Alpha toward Private Beta.

## Product boundaries

Probabilistic Triage owns:

- probabilistic clinical inference;
- model and policy versioning;
- adaptive question selection;
- risk tolerance / disposition policy;
- explainability;
- model governance and release controls.

Consuming channels own:

- public-facing presentation and interaction;
- channel-specific UX;
- orchestration around the triage journey where appropriate;
- onward use of the returned structured outcome.

## Relationship with deterministic triage

A hybrid model may exist where deterministic Patient Triage API flows hand off to Probabilistic Triage. This introduces integration overhead and makes the centralised ownership decision important: probabilistic reasoning remains within the Probabilistic Triage capability even when another service controls the wider journey.

## Expected product measures

Candidate measures include:

- reduction in average number of questions;
- emergency/high-risk detection performance;
- calibration and discrimination;
- AUC-ROC where appropriate;
- disposition accuracy;
- safety test pass rate;
- model/version regression performance;
- latency and availability;
- clinician approval turnaround;
- explainability completeness;
- concept drift indicators once production data supports monitoring.

## Related strategic workstreams

The product overlaps with four Kainos/NHSE workstreams:

- Evaluation Platform / Provena;
- TIM analytics;
- Improve How We Author Content;
- Probabilistic Triage itself.

The strategic direction is to avoid four disconnected products where a shared platform capability can serve multiple workstreams, while allowing tactical delivery because the teams are at different stages of maturity.

See `../PROJECT_CONTEXT.md` and `../DECISIONS.md` for the broader project baseline.