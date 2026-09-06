# Functional Group Mapping — Working Guidance

## Purpose

Capture the working approach used when assessing Probabilistic Triage components and features against functional groups G0–G4.

This is not a substitute for the formal classification artefacts or regulatory advice.

## Core principle

Classify what the software **does**, not what the team calls the component.

A component can contain features with different regulatory significance. The safest assessment is therefore performed at both:

1. component level; and
2. feature level.

## Working interpretation

The project has been particularly concerned with keeping non-clinical-support components at or below **G3** where that is consistent with intended purpose, while recognising that features that directly influence clinical triage decisions may legitimately cross into a higher group.

Do not artificially constrain a clinically necessary function merely to obtain a lower classification.

## Feature assessment questions

For every feature, ask:

- Does it only store, transport, display or administer information?
- Does it transform or calculate information?
- Does it interpret patient-specific clinical information?
- Does it recommend or determine an action for an individual patient?
- Can the result influence diagnosis, triage, treatment or disposition?
- Is the clinician/user making an independent decision, or effectively accepting the software's decision?
- Can the feature change runtime clinical behaviour?
- Is the output advisory, constrained, or autonomous?

## Patterns that tend to stay lower risk

Subject to the formal rubric, examples may include:

- viewing an approved DAG;
- viewing CPTs;
- version/history display;
- audit log access;
- controlled metadata management;
- test-result display;
- workflow/approval administration;
- configuration editing that is not made clinically active until separately reviewed and approved.

## Patterns that can push classification upward

Examples requiring closer scrutiny include:

- calculating patient-specific clinical probabilities;
- recommending the next clinical question based on patient evidence;
- determining triage/disposition;
- dynamically altering clinically meaningful thresholds in production;
- generating patient-specific recommendations;
- autonomous model adaptation based on live patient data;
- automated approval or release of clinically significant model changes;
- using generative AI output directly in runtime clinical decision-making.

## Workaround pattern for keeping an administrative feature below the decision boundary

Where clinically appropriate, a feature may be designed so that it:

1. prepares or displays a proposed change;
2. does not affect the active clinical model immediately;
3. requires named clinical review;
4. passes controlled validation/tests;
5. requires explicit approval;
6. is released as a versioned artefact through a separate governance step.

This does not guarantee a particular functional group, but it helps preserve a meaningful separation between authoring/governance software and runtime clinical decision software.

## Component-versus-feature rule

If a component contains even one materially higher-risk feature, do not assume the rest of the component automatically shares the same classification. Record the feature-level rationale and consider whether architectural separation would create a clearer regulatory boundary.

## Change triggers

Reassess classification whenever a feature changes from:

- display → calculation;
- calculation → interpretation;
- interpretation → recommendation;
- recommendation → autonomous action;
- offline/build-time → live runtime;
- clinician-reviewed → automatically released;
- static model → continuously learning/adapting model.

## Source precedence

Always reconcile this guidance with the formal Feature Mapping Table, Intended Use, Software Structure Classification and regulatory rubric.