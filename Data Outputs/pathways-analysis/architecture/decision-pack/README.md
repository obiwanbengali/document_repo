# Adaptive Triage Bayesian Architecture Decision Pack

**Status:** Working draft  
**Purpose:** Provide a concise set of decision records supported by deeper technical evidence.

## Document set

| Document | Purpose | Status |
|---|---|---|
| ADR — Strategic Bayesian Network Topology | Decide between monolithic, specialised, federated and hybrid Bayesian topologies | Planned |
| Deep Dive — Monolithic Bayesian Network | Test the feasibility, benefits and risks of a single estate-wide BN | Draft |
| Deep Dive — Specialised Bayesian Networks | Examine independent clinical-domain BNs with single-family routing | Draft |
| Deep Dive — Federated Bayesian Networks | Examine coordinated family BNs with shared evidence and multi-family routing | Draft |
| Deep Dive — Hybrid Bayesian Network | Examine shared/common probabilistic capability combined with family BNs | Draft |
| ADR — Tactical to Strategic Bayesian Approach | Decide the April 2027 single-family pilot approach and migration to the strategic topology | Planned |

## Decision sequence

1. Establish the evidence for each topology independently.
2. Apply the same decision criteria to all options.
3. Produce the strategic topology ADR.
4. Produce the tactical-to-strategic ADR.
5. Revisit the strategic topology when clinician-led family definition is complete.

## Common decision criteria

The topology papers will use the same criteria:

- clinical coherence;
- inference complexity and expected latency;
- CPT and memory growth;
- adaptive-questioning capability;
- cross-family presentations and boundary handling;
- clinical assurance scope;
- testing and regression scope;
- change blast radius;
- explainability and auditability;
- model versioning and compatibility;
- runtime and infrastructure complexity;
- resilience and failure isolation;
- NHS-wide scalability;
- operational supportability;
- infrastructure cost;
- extensibility as new clinical families are introduced.

## Evidence principles

The pack distinguishes:

- **Measured** — directly observed from the Pathways structural analysis or benchmark.
- **Derived** — calculated from measured evidence.
- **Assumption** — explicit modelling assumption used for sensitivity analysis.
- **Benchmark** — measured in a controlled synthetic or PoC runtime.
- **Architectural interpretation** — design consequence inferred from the evidence.

A deterministic Pathways graph is not treated as the final Bayesian DAG. Question identity is also not assumed to equal clinical semantic identity.

## Current architectural context

The runtime service boundary is centralised. The choice in the strategic ADR is the **logical Bayesian model topology inside that service**, not whether to deploy one microservice per clinical family.

The tactical April 2027 private beta is expected to begin with one **ENT — Ear, Nose and Throat — family Bayesian Network**. It should be implemented as the first family of the future strategic architecture, rather than as a disposable one-off design.
