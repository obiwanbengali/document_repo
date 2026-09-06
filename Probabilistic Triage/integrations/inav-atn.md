# Integration — iNav / ATN

## Role

iNav / Access, Triage and Navigation (ATN) provides orchestration across the wider patient journey and may onboard multiple triage engines and services.

## Probabilistic Triage position

Probabilistic Triage remains the owner of probabilistic clinical inference and decisioning. iNav should orchestrate service selection and journey flow rather than duplicate the probabilistic reasoning model.

## Expected interaction

1. iNav or an upstream channel identifies that Probabilistic Triage is the appropriate triage capability.
2. Structured evidence is passed via the agreed API/FHIR contract.
3. Probabilistic Triage returns the next question or a completed structured triage outcome.
4. iNav uses the outcome to continue navigation, service selection or downstream orchestration.

## Design principles

- keep the clinical decision boundary clear;
- use common API standards across deterministic and probabilistic triage services;
- keep channel-specific presentation concerns outside the inference engine;
- preserve model and policy version metadata for audit;
- minimise bespoke coupling between iNav and internal model implementation;
- define safe fallback behaviour for service unavailability.

## Strategic context

ATN is the broader orchestration context in which Probabilistic Triage should operate as a reusable national capability. The value of centralisation is that NHS App, 111 Online and other channels can consume consistent probabilistic behaviour through the orchestration layer rather than embedding separate inference implementations.

## Open concerns

Areas that require continued alignment include:

- the exact common API standard;
- interaction/session ownership;
- handoff between deterministic and probabilistic triage;
- outcome semantics and TOM mapping;
- service-level and latency expectations;
- responsibility for downstream navigation and service selection.