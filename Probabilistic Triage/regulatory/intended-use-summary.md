# Intended Use — Working Summary

## Purpose

This file is a working project-memory summary of the intended-use position for Probabilistic Triage. Formal approved Intended Use and medical-device documentation always takes precedence.

## Product role

Probabilistic Triage is intended to support clinical triage by using a governed probabilistic model to evaluate structured patient evidence, dynamically select relevant questions, and produce structured triage/disposition outputs for onward care navigation.

It is not intended to operate as an unconstrained general-purpose diagnostic AI or an autonomous LLM clinician.

## Intended users and integrations

The capability is primarily consumed through approved digital channels and orchestration services rather than acting as a standalone public-facing application.

Clinical and administrative users interact with governance functions through the Clinical Admin UI.

## Key boundary assumptions

- Runtime clinical reasoning is performed by approved probabilistic/Bayesian model artefacts and explicit policy logic.
- LLMs are used only for approved build-time assistance and do not directly determine runtime patient triage outcomes.
- Clinicians review and approve clinically significant model content and changes before release.
- Safety guardrails, thresholds and release gates are controlled and auditable.
- Outputs are structured, explainable and traceable to input evidence, model version and policy version.

## Why this matters

Regulatory classification is sensitive not only to the component name but to what the software actually does. Features that move a component from passive authoring, display, administration or workflow support into autonomous interpretation, recommendation or clinical decision-making can change its functional classification.

## Change-control principle

Any proposed feature that materially changes:

- intended purpose;
- intended user;
- clinical decision influence;
- autonomy;
- diagnostic or triage recommendation capability;
- safety-critical control behaviour;
- learning/adaptation in production;

must be reviewed against the formal Intended Use and MDD classification before implementation.

## Evidence hierarchy

Where there is conflict, use this order:

1. Approved Intended Use / regulatory artefact
2. Approved MDD classification and supporting rationale
3. Clinical safety case / DCB0129 artefacts
4. Accepted architecture and product decisions
5. This project-memory summary