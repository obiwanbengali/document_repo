# Integration — DoS / Find the Right Service (FtRS)

## Role

Probabilistic Triage determines a clinically appropriate triage outcome. DoS / Find the Right Service is responsible for resolving that outcome into suitable services or destinations.

## Ownership boundary

Probabilistic Triage should not embed service-directory logic into the Bayesian inference engine.

Probabilistic Triage owns:

- clinical reasoning;
- adaptive questioning;
- risk/disposition policy;
- structured triage outcome generation.

DoS / FtRS owns or supports:

- service discovery;
- service availability/context;
- matching a structured management need to suitable services;
- downstream navigation to an appropriate service.

## Expected flow

1. Probabilistic Triage completes clinical reasoning.
2. The result is mapped into a TOM/FHIR-aligned outcome containing management request, service type, timeframe/urgency, acuity and relevant findings.
3. iNav, PTA or another orchestrating service passes the outcome to DoS/FtRS.
4. DoS/FtRS returns candidate services based on the clinical requirement and service context.
5. The orchestrator/channel presents or acts on the service selection.

## Design principles

- keep clinical decisioning separate from directory/service matching;
- use common terminology and outcome semantics across the boundary;
- avoid encoding individual service identifiers in Bayesian model logic;
- ensure urgency/timeframe semantics remain intact during service matching;
- retain traceability from the service request back to the triage outcome;
- define safe behaviour when no suitable service is returned.

## Strategic implication

The probabilistic capability should produce a stable clinical intent that can be consumed by current or future service-selection capabilities. This avoids coupling the inference engine to one DoS/FtRS implementation.