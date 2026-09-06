# Inference Engine

## Purpose

The inference engine is the runtime component that performs probabilistic clinical reasoning using approved Bayesian model artefacts and controlled policy configuration.

## Responsibilities

- Load the approved model/version.
- Apply current patient evidence.
- Update posterior probabilities.
- Select the next most useful question using information gain or an equivalent governed strategy.
- Stop questioning when clinically sufficient evidence is available or a safety/disposition threshold is reached.
- Apply risk tolerance, safety guardrails and disposition policy.
- Produce a structured triage outcome.
- Produce an explainability trace showing evidence, model version, probability changes and policy application.

## Inputs

Typical inputs include:

- demographics;
- comorbidities;
- exposure/risk factors;
- historical findings;
- symptoms;
- answers gathered during the interaction;
- channel/context metadata where clinically relevant;
- model and policy version selectors.

## Outputs

Typical outputs include:

- next question and allowable answers; or
- final triage/disposition outcome;
- probability/risk information required for explainability;
- model version;
- policy version;
- evidence references;
- audit metadata.

## Question selection

The preferred adaptive mechanism is information gain. The engine should ask questions that are expected to reduce uncertainty while preserving explicit safety constraints.

A hybrid design may combine:

- mandatory safety questions;
- deterministic gating where necessary;
- probabilistic information-gain selection;
- stopping criteria based on confidence, risk or disposition stability.

## Safety behaviour

Safety policy must be explicit rather than hidden inside model implementation. Examples include:

- emergency overrides;
- minimum evidence requirements;
- confidence thresholds;
- high-risk symptom combinations;
- conservative fallback behaviour;
- channel-specific restrictions where clinically approved.

## Runtime state

The API contract may be stateless from the consumer's perspective while the interaction itself has logical state. That state must be reconstructable from submitted evidence and versioned configuration, or stored in a controlled runtime mechanism where necessary.

## Non-goals

- LLMs must not act as the runtime clinical decision-maker.
- The engine should not author or modify Bayesian models at runtime.
- Channel presentation logic should not be embedded in the core inference algorithm.
- Analytics processing should not block the synchronous clinical response.

## Testing expectations

The engine should support repeatable testing against:

- clinical vignettes;
- deterministic-pathway baselines;
- edge and high-risk cases;
- calibration datasets;
- regression packs;
- model-version comparisons.