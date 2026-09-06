# Adaptive Question Selection

## Purpose

Probabilistic Triage should ask the next question based on the expected value of the information it provides rather than following a fixed deterministic path.

## Current direction

Use information-gain or equivalent value-of-information logic to identify the next useful question from the current evidence state.

## Expected behaviour

At each step the engine should:

1. update posterior probabilities from current evidence;
2. identify clinically eligible candidate questions;
3. score questions by expected information value and safety relevance;
4. apply guardrails and policy constraints;
5. return the next question or conclude when sufficient evidence exists.

## Safety constraints

Question selection must not optimise for question reduction alone. Red-flag, emergency and mandatory safety questions may override pure information-gain ranking.

The engine should support:

- mandatory questions where clinically required;
- suppression of irrelevant or already-resolved questions;
- channel-specific constraints where appropriate;
- stop criteria based on confidence, safety and disposition requirements;
- deterministic reproduction from the same evidence/model/policy versions.

## Current evidence from PoCs

Previous experiments indicated that adaptive questioning could materially reduce the number of questions compared with deterministic pathways while maintaining high-risk detection. These results remain evidence to validate rather than a guarantee for production behaviour.

## Metrics

Useful evaluation measures include:

- questions per completed triage;
- emergency/high-risk sensitivity;
- inappropriate early stopping;
- information gain per question;
- disposition agreement against validated reference cases;
- calibration before and after additional evidence.