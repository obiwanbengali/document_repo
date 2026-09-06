# Probabilistic Triage — Agent Instructions

This repository area contains working context for the NHS England Probabilistic Triage programme.

Before proposing architecture, product, delivery, governance, or implementation changes, read:

1. `PROJECT_CONTEXT.md`
2. `DECISIONS.md`
3. Relevant ADRs, ODPs, architecture diagrams, policy documents, and evidence artefacts where available

## How to use this context

Treat the information in these files as the current working position unless newer project evidence explicitly supersedes it.

Do not assume previously agreed decisions are open for reconsideration unless:

- new evidence has emerged;
- a regulatory, clinical, product, security, commercial, or technical constraint has materially changed; or
- the user explicitly asks for an options analysis or to revisit a decision.

When a proposal conflicts with an accepted decision, call out the conflict rather than silently replacing the existing position.

Distinguish clearly between:

- **Accepted decision** — agreed and should be treated as the baseline;
- **Direction** — preferred approach but still subject to validation;
- **Option under consideration** — not yet agreed;
- **Future capability** — outside the immediate MVP/beta baseline.

## Product intent

Probabilistic Triage is a centralised, clinically explainable probabilistic triage capability. It uses Bayesian reasoning across symptoms, findings, demographics, risk factors and other evidence to adaptively select questions and produce structured clinical triage outcomes for onward service selection.

The service also provides clinical users with tools to review, test, approve and govern model behaviour.

## Key settled positions

- Probabilistic inference and decisioning are provided as a **centralised capability**.
- Integrating services and channels consume probabilistic triage via APIs rather than implementing their own probabilistic decision logic.
- The core clinical reasoning model is Bayesian/probabilistic.
- A **federated/hierarchical Bayesian topology** is the preferred direction for scaling specialised clinical domains.
- Runtime inference is separated from the Bayesian Network build pipeline.
- AWS Bedrock is used for **build-time assistance only** and is not intended to make runtime clinical triage decisions.
- A clinician remains in the loop for model generation, review, validation, approval and release governance.
- AWS Neptune, SageMaker and Bedrock have received Engineering Board approval for the programme's intended use.
- CIS2 is the intended authentication approach for the Clinical Admin UI.
- FHIR is the target interoperability contract for probabilistic triage integration.
- EventBridge is not part of the synchronous triage request/response path.
- CloudWatch logging and telemetry can support operational monitoring and analytics.
- Clinical explainability, auditability and reproducibility are mandatory design qualities.
- Safety guardrails and risk policy belong within the controlled probabilistic triage capability, not in consuming channels.

## Architecture principles

1. Keep the runtime clinical path deterministic in operation even where the underlying reasoning is probabilistic: inputs, model version, policy version and outputs must be reproducible and auditable.
2. Separate build-time AI assistance from runtime clinical decision support.
3. Keep clinical model artefacts versioned, immutable after approval, and traceable to their source evidence and sign-off.
4. Prefer explicit APIs and contracts over hidden coupling between services.
5. Keep channel-specific presentation concerns outside the inference engine where possible.
6. Treat clinical safety, explainability, evidence provenance, approval and rollback as first-class architecture concerns.
7. Avoid unnecessary components in the synchronous request path where they add latency or operational complexity without clear value.
8. Preserve the ability to evaluate probabilistic behaviour against deterministic baselines and clinical test cases.

## Working style for AI assistants

When supporting this programme:

- maintain continuity with existing terminology and decisions;
- identify whether a statement is a fact, assumption, option or recommendation;
- favour concise decision-oriented outputs suitable for Confluence, architecture boards, product leadership and clinical governance;
- avoid reopening accepted decisions without new evidence;
- surface downstream impacts across product, clinical safety, regulation, information governance, cyber, interoperability, delivery and operations;
- when creating ADRs or ODPs, avoid section numbering unless explicitly requested;
- when describing AWS architecture, separate build-time, runtime, admin/governance and analytics concerns;
- when discussing LLM use, make clear that LLMs assist build-time processes and are not the runtime triage decision-maker;
- preserve clinician-in-the-loop controls where model content or behaviour is generated or changed.

## Source of truth

These Markdown files are a portable project-memory layer, not a replacement for approved project artefacts. Where an approved ADR, ODP, clinical safety artefact, regulatory document, DPIA, security decision or governance record conflicts with this context, the approved artefact takes precedence and these files should be updated.