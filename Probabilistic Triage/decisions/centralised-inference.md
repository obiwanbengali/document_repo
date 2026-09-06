# Decision — Centralised Probabilistic Inference

## Status

Accepted.

## Decision

Probabilistic inference and probabilistic clinical decisioning are owned by the central Probabilistic Triage capability. Integrating products and channels consume the capability through APIs rather than embedding or reproducing the inference logic themselves.

## Context

A distributed model would allow integrating services to host or implement parts of probabilistic decisioning. That creates variation in model versions, policy application, release governance and clinical safety evidence.

A centralised service keeps probabilistic reasoning, model execution, safety policy and explainability under one controlled product boundary.

## Rationale

The centralised approach provides:

- consistent clinical behaviour across channels;
- one place to govern model versions and thresholds;
- simpler audit and traceability;
- lower risk of policy drift between consumers;
- clearer ownership of clinical safety controls;
- easier rollback and controlled release;
- reduced duplication of probabilistic logic;
- clearer separation between orchestration/presentation and clinical reasoning.

## Consequences

Consuming systems such as PTA and iNav need stable API contracts and handoff patterns. The Probabilistic Triage service becomes a critical shared runtime capability and therefore needs appropriate resilience, latency and support characteristics.

## Revisit only if

- a regulatory or clinical-safety requirement forces local decisioning;
- latency or availability evidence demonstrates the central service cannot meet required service levels; or
- the programme explicitly changes the product operating model.