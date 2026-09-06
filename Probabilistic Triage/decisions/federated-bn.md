# Decision — Federated / Hierarchical Bayesian Network Direction

## Status

Preferred architectural direction.

## Decision

Scale clinical reasoning through a federated or hierarchical set of specialised Bayesian Networks rather than one unbounded monolithic network containing every condition and pathway.

## Rationale

Specialised networks provide clearer clinical ownership, smaller CPT spaces, easier calibration, more manageable testing, and safer incremental release. A federation can still support cross-domain evidence where clinically required through routing, shared variables, aggregation or higher-level coordination.

## Expected design characteristics

- specialised Bayesian Networks aligned to clinically coherent domains or pathway families;
- explicit routing or orchestration between networks;
- consistent disposition and safety policy across the federation;
- traceability of every network and version used in a triage interaction;
- mechanisms for shared evidence and cross-domain reasoning where justified;
- ability to test and release one domain without destabilising unrelated domains.

## Risks to manage

- incorrect routing between specialised networks;
- loss of clinically relevant cross-domain dependencies;
- duplicated variables or inconsistent terminology;
- inconsistent calibration across models;
- complexity in explaining combined reasoning.

## Revisit only if

Evidence shows that a monolithic network is clinically superior and operationally manageable, or a different model topology provides materially better safety, calibration, maintainability and explainability.