# Probabilistic Triage — Project Knowledge Base

This folder is the portable project-memory layer for the NHS England Probabilistic Triage programme.

It is designed so that ChatGPT, Claude, Codex, GitHub Copilot or another approved AI assistant can quickly recover the current project context without relying on a single vendor's conversation memory.

## Start here

AI assistants should read these files first:

1. [`AGENTS.md`](AGENTS.md) — working instructions, architectural principles and how to treat existing decisions.
2. [`PROJECT_CONTEXT.md`](PROJECT_CONTEXT.md) — consolidated factual project context.
3. [`DECISIONS.md`](DECISIONS.md) — accepted decisions, directions and areas still expected to evolve.

## Knowledge areas

### [Architecture](architecture/README.md)

Current logical architecture, component boundaries, AWS baseline, runtime/build separation, federated Bayesian direction and integration context.

### [Product](product/README.md)

Product definition, goals, users, scope, ownership boundaries, measures and relationship to the wider ATN/DUEC landscape.

### [Governance](governance/README.md)

Clinical governance, safety, engineering approvals, IG, cyber, AI governance, evidence expectations and release controls.

### [Regulatory](regulatory/README.md)

Medical-device context, component/feature classification principles, design boundaries intended to avoid unintended regulatory escalation, and reassessment triggers.

### [Delivery](delivery/README.md)

Delivery stage, build sequence, team/squad model, dependencies, tactical-versus-strategic considerations and Beta-readiness baseline.

## Source-of-truth rule

These Markdown files summarise the current working position. They do **not** replace approved artefacts.

Where an approved ADR, ODP, Intended Use statement, Software Structure Classification, clinical safety artefact, DPIA, regulatory record, security decision or formal governance approval conflicts with this knowledge base, the approved artefact takes precedence.

The knowledge base should then be updated so future AI-assisted work starts from the new accepted position.

## Maintenance convention

When a material decision changes:

1. update the relevant formal project artefact;
2. update `DECISIONS.md`;
3. update the affected knowledge-area README;
4. update `PROJECT_CONTEXT.md` if the change affects the wider project baseline.

This keeps project memory concise while preserving traceability to the formal evidence base.