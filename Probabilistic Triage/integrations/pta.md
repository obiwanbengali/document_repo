# Integration — Patient Triage API (PTA)

## Role

PTA is the deterministic triage API and may hand off to Probabilistic Triage in a hybrid model.

## Ownership boundary

PTA should orchestrate the handoff and preserve its deterministic responsibilities. Probabilistic Triage owns probabilistic inference, adaptive questioning, risk policy and probabilistic disposition logic.

PTA should not duplicate or reimplement probabilistic decisioning.

## Hybrid flow

A possible interaction is:

1. PTA begins or manages the triage interaction.
2. A defined trigger determines when probabilistic triage is invoked.
3. PTA passes the available structured evidence through the agreed API/FHIR contract.
4. Probabilistic Triage returns either the next question or a structured triage outcome.
5. PTA/channel presents the question or continues downstream orchestration.

## Key design concerns

- avoid duplicated questions across deterministic and probabilistic phases;
- preserve evidence already collected;
- make handoff state explicit;
- avoid divergent interpretations of the same clinical variable;
- maintain latency within the overall interaction target;
- ensure failures have a clinically safe fallback;
- carry model/policy/version identifiers into audit where required.

## Contract principles

The integration should prefer a stable, versioned contract rather than tight coupling to the internal Bayesian representation.

PTA should not need to know:

- internal graph topology;
- CPT structure;
- inference implementation details.

It should need to understand:

- evidence supplied;
- question requested;
- response/value sets;
- completion state;
- outcome/disposition;
- relevant trace/version metadata.

## Strategic implication

The decision to centralise probabilistic inference means hybrid overhead is an integration concern, not a reason to distribute probabilistic logic into PTA.