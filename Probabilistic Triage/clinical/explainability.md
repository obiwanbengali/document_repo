# Clinical Explainability

## Purpose

Every clinically significant output from Probabilistic Triage must be capable of being explained and reconstructed from the evidence, model version and policy version used at the time.

## Explainability requirements

A triage interaction should make it possible to determine:

- what evidence was supplied;
- what model and version were used;
- what policy/configuration version was used;
- which probabilities materially changed;
- which evidence contributed to those changes;
- why a particular question was selected;
- why the interaction stopped;
- why a specific disposition or urgency outcome was returned.

## Runtime trace

The service should capture a structured reasoning trace suitable for:

- clinical review;
- incident investigation;
- testing and regression analysis;
- regulatory evidence;
- litigation or retrospective assurance where required.

The trace should be understandable without requiring someone to reverse-engineer the implementation.

## Build-time traceability

Approved models should also preserve provenance from source material through:

- extracted variables;
- graph relationships;
- CPT derivation or calibration;
- clinician review;
- test evidence;
- approval and release.

## LLM boundary

Where Bedrock or another LLM assists build-time work, the generated suggestion itself is not sufficient evidence. The approved artefact and the rationale for accepting it must stand scrutiny independently.

## Design principle

Explainability is not a reporting add-on. It is part of the core clinical safety and governance architecture.