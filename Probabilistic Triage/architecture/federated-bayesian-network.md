# Federated / Hierarchical Bayesian Network

## Current direction

The preferred scaling direction is a federated or hierarchical Bayesian topology rather than a single monolithic network containing all possible conditions.

## Why federate

A monolithic Bayesian Network becomes increasingly difficult to:

- author;
- calibrate;
- validate;
- review clinically;
- release safely;
- understand;
- update without unintended effects.

Specialised networks allow contained clinical families or pathway domains to evolve independently while retaining a common runtime and governance model.

## Conceptual topology

A typical topology may contain:

- shared context / demographics layer;
- routing or domain-selection layer;
- specialised Bayesian Networks for contained clinical families;
- an aggregation or coordination layer where multiple specialised networks need to contribute;
- common risk and disposition policy.

## Design requirements

The federated design must support:

- cross-domain evidence where clinically necessary;
- deterministic and explainable routing into specialised networks;
- consistent terminology and variable definitions;
- independent model versioning;
- clear dependency/version compatibility rules;
- end-to-end explainability;
- common safety policy;
- testing both individual networks and the composed system.

## Routing

Routing should not prematurely exclude clinically plausible domains. Options may include:

- evidence-based activation of multiple candidate models;
- a lightweight parent/aggregator Bayesian model;
- deterministic safety/domain gates;
- a hybrid approach.

The routing design remains an implementation detail to validate; the accepted direction is federation, not one specific routing algorithm.

## Shared variables

Common variables such as age, sex, pregnancy status, comorbidities or general red flags should use controlled definitions and should not be independently reinterpreted by every specialised model.

## Aggregation

Where multiple specialised models contribute, the system must define how evidence and risk are combined without creating opaque double-counting or conflicting dispositions.

## Governance

Each specialised network should have:

- an owner;
- clinical scope;
- source evidence;
- model version;
- calibration evidence;
- clinical approval;
- regression pack;
- compatibility information;
- release and rollback history.

## Key risk

Federation reduces model complexity locally but introduces orchestration complexity. This trade-off must remain visible in architecture and safety assessment.