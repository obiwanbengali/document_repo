# Clinical Risk Policy

## Purpose

Risk policy converts probabilistic reasoning into clinically safe operational behaviour. It defines how probability, consequence, urgency and safety constraints affect triage outcomes and question flow.

## Core principle

Risk tolerance is a controlled clinical policy, not an emergent property of the Bayesian model alone.

## Responsibilities

Risk policy should define or govern:

- probability thresholds that require escalation;
- treatment of low-probability/high-consequence conditions;
- mandatory emergency or red-flag pathways;
- minimum evidence required before de-escalation;
- stopping rules;
- disposition thresholds;
- confidence requirements;
- channel-specific constraints where clinically justified;
- fallback behaviour when inference is uncertain or incomplete.

## Separation of concerns

The Bayesian model estimates probabilities. Risk policy determines what the service should do with those probabilities.

This separation supports clearer governance because clinical thresholds can be reviewed and versioned independently from graph structure or CPT calibration where appropriate.

## Governance

Changes to risk policy should be:

- version-controlled;
- clinically reviewed;
- tested against known safety scenarios;
- auditable;
- released through controlled promotion;
- reversible.

## Clinical Admin UI

The Clinical Admin UI may expose controlled risk-policy configuration, but changes must pass the required approval gates. Direct ungoverned production editing should be avoided.

## Evaluation

Risk-policy testing should include:

- emergency/high-risk sensitivity;
- under-triage and over-triage;
- effect of threshold changes;
- edge cases near decision boundaries;
- low-probability/high-severity scenarios;
- incomplete or contradictory evidence;
- model uncertainty.