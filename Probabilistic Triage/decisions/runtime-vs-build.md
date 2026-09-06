# Decision — Separate Model Build from Runtime Inference

## Status

Accepted.

## Decision

Keep the Bayesian Network build lifecycle physically and logically separate from runtime triage inference.

## Build-time responsibilities

- extract and transform source clinical content;
- define variables and ontology mappings;
- construct graph structure;
- generate or refine CPTs;
- use approved AI/LLM assistance where appropriate;
- run evaluation and safety tests;
- obtain clinical review and approval;
- publish an immutable, versioned model artefact.

## Runtime responsibilities

- load an approved model artefact;
- apply patient evidence;
- perform Bayesian inference;
- choose the next useful question;
- apply approved risk and disposition policy;
- return structured outcomes and trace information.

## Rationale

The separation reduces the regulatory and safety complexity of runtime behaviour, prevents unapproved model changes during live triage, improves reproducibility, and makes model release/rollback auditable.

## Design constraint

No build-time generative process should alter the live model or clinical policy without passing through the defined approval and release process.