# Decision — Graph Technology

## Status

Accepted technology direction.

## Decision

Use AWS Neptune as the approved graph-oriented technology for relevant Probabilistic Triage graph use cases.

## Context

The programme explored graph technologies while shaping the Bayesian Network build and governance capability. Neptune has been accepted through Engineering Board alongside SageMaker and Bedrock.

## Rationale

The choice aligns with the approved AWS technology estate and supports graph-oriented representations that may be useful for Bayesian structure, knowledge relationships, lineage, model inspection or related tooling.

## Important constraint

Neptune is not automatically the runtime Bayesian inference engine. Graph storage/representation and probabilistic inference are separate concerns and should only be coupled where there is a clear design benefit.

## Consequences

- architecture should define exactly what data Neptune owns;
- model artefacts used at runtime should remain versioned and reproducible;
- graph queries should not create hidden mutable clinical behaviour;
- alternatives should not be introduced without a material requirement or formal decision.