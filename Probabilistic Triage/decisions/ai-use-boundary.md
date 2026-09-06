# Decision — AI / LLM Use Boundary

## Status

Accepted.

## Decision

Use generative AI/LLMs only as controlled build-time assistants for Probabilistic Triage. Do not use them as the runtime clinical triage decision-maker.

## Approved intent

Build-time AI assistance may support activities such as:

- extracting or structuring clinical knowledge;
- proposing ontology mappings;
- assisting variable or relationship definition;
- supporting CPT/scaffold generation;
- generating synthetic vignettes or test artefacts;
- drafting supporting engineering or assurance material.

Every clinically relevant output must be reviewable and subject to the appropriate human and clinical governance before it can affect an approved model.

## Runtime boundary

Live triage should execute approved probabilistic model artefacts and policy deterministically from known inputs, versions and configuration. It should not depend on open-ended LLM generation for clinical decisioning.

## Rationale

This boundary improves reproducibility, explainability, evidence quality, regulatory clarity and clinical safety while still allowing AI to accelerate engineering and authoring work.

## Data constraint

The current programme position is that no PII is required for the approved build-time LLM use cases. Any change to the data classification, purpose, model provider or deployment pattern must be reassessed through IG, cyber, legal/commercial and clinical governance.