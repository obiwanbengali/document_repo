# Probabilistic Triage — Regulatory / Medical Device Context

This folder captures the current working regulatory context for Probabilistic Triage. It is a project-memory summary and does not replace formal regulatory advice, the intended-use statement, medical-device documentation or approved classification artefacts.

## Regulatory framing

Probabilistic Triage is intended to support clinical triage and therefore must be designed with medical-device classification and assurance boundaries in mind.

The project has been actively assessing which software components and features fall within different functional groups and what changes could move a component into a higher regulatory classification.

## Core principle

Regulatory classification should be considered at both:

- **component level** — what the component fundamentally does; and
- **feature level** — whether a particular feature changes the intended purpose, autonomy, clinical influence or risk profile of that component.

A feature should not automatically inherit the lowest classification of the wider platform if its behaviour materially changes clinical decision-making or device functionality.

## Important design boundary

Where feasible, keep administrative, visualisation, workflow and configuration capabilities clearly separated from autonomous clinical decision-making behaviour.

Examples of lower-risk patterns can include:

- displaying a Bayesian Network DAG without automatically changing clinical behaviour;
- displaying CPT values for review rather than automatically rewriting them;
- requiring explicit clinician approval before a model or threshold change becomes active;
- treating AI-generated model suggestions as proposals rather than direct executable clinical logic;
- separating model authoring from runtime execution;
- enforcing controlled release gates between design-time changes and patient-facing use.

Features are more likely to increase regulatory significance when they:

- autonomously alter clinical decision logic;
- directly recommend or determine patient-specific diagnosis, urgency or disposition without an appropriate controlled boundary;
- change thresholds or CPTs automatically in production;
- learn/adapt from live patient data without prospective review and release governance;
- bypass clinician approval for clinically meaningful model changes;
- generate patient-specific clinical decisions using a generative model rather than a validated probabilistic model/policy.

## Clinical Admin UI boundary

The Clinical Admin UI should primarily support review, governance and controlled configuration.

Design patterns that help preserve that boundary include:

- read-only DAG/CPT inspection by default;
- role-based controls;
- staged draft/review/approved states;
- independent validation before release;
- explicit sign-off for clinically material changes;
- full audit logging;
- prohibition on direct live-model mutation from exploratory tooling;
- controlled publication to immutable model artefacts.

## Build-time AI

AWS Bedrock is currently positioned as build-time assistance only.

LLM-generated content should not become approved clinical model content without human review and, where clinically significant, named clinician approval.

This separation is important because direct autonomous generation or alteration of runtime clinical logic could materially change the medical-device position.

## Runtime model

The intended runtime decisioning is based on approved Bayesian Networks, risk/disposition policy and controlled configuration, rather than a generative LLM making live clinical decisions.

Runtime behaviour should therefore be:

- versioned;
- reproducible;
- explainable;
- testable;
- clinically approved;
- traceable to evidence and release artefacts.

## Change control

Any proposal that introduces one of the following should trigger explicit regulatory reassessment:

- self-learning or continuously adaptive clinical models;
- automatic CPT recalibration in production;
- autonomous diagnosis generation;
- automatic threshold optimisation with no prospective approval;
- new patient-specific recommendations;
- changes to intended use;
- new user groups or care settings;
- new levels of autonomy;
- new data sources that materially affect clinical decisions.

## Relationship to formal artefacts

When formal documents are available, the following take precedence over this summary:

- Intended Use statement;
- Software Structure / Classification documentation;
- medical-device feature mapping tables;
- regulatory strategy;
- clinical safety case;
- approved risk-management artefacts.

The project-memory files should be updated whenever one of those artefacts changes the accepted regulatory position.