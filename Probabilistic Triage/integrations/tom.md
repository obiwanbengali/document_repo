# Integration — Triage Outcome Model (TOM)

## Role

The Triage Outcome Model provides the structured representation of triage outcomes that can be passed between triage capabilities and downstream services.

## Current mapping direction

The working TOM mapping uses:

- **SG / SNOMED CT** for main complaint and significant findings;
- **SD / SNOMED CT** for management request and service type;
- **Dx / external value sets** for timeframe and acuity-related outcome properties.

The exact contract should remain aligned with the latest approved TOM definition.

## Probabilistic Triage usage

Probabilistic Triage should map its final clinical outcome into TOM-aligned structures rather than exposing internal Bayesian constructs directly.

A TOM outcome may include:

- main complaint;
- significant findings;
- management request;
- service type;
- timeframe / urgency;
- acuity / priority;
- evidence references;
- interaction metadata;
- model and policy provenance where appropriate.

## Design principles

- do not leak internal graph or CPT structures into TOM;
- keep terminology mappings explicit and versioned;
- use SNOMED CT where the TOM definition requires it;
- preserve traceability from model evidence to the structured outcome;
- separate outcome semantics from channel presentation.

## Relationship with FHIR

TOM should be represented through the agreed FHIR-aligned API contract where appropriate. TOM is the clinical/business outcome model; FHIR is the interoperability representation/transport standard.

## Governance

Changes to TOM mappings can affect downstream consumers and should therefore be versioned, tested and coordinated across PTA, iNav/ATN, DoS/FtRS and other consuming services.