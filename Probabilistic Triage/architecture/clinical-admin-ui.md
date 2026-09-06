# Clinical Admin UI

## Purpose

Provide a governed interface for authorised clinical and administrative users to inspect, test, configure, approve and release Probabilistic Triage behaviour.

## Authentication and access

- CIS2 authentication.
- Role-based access control.
- Separation of review, approval and administrative permissions where required.
- Complete audit of material changes and approvals.

## Core capabilities

### Model review

- View model catalogue and versions.
- Inspect Bayesian DAG structure.
- Inspect nodes, states and relationships.
- View CPTs and parameter values.
- View terminology mappings and provenance.
- Compare model versions.

### Safety and policy configuration

- View and manage approved model thresholds.
- Configure risk-tolerance policy within controlled bounds.
- Manage safety guardrails.
- Configure channel-specific settings where clinically approved.
- View stopping criteria and disposition thresholds.
- Prevent unauthorised free-form modification of clinically significant logic.

### Testing

- Run clinical vignettes.
- Generate draft vignettes using approved build-time AI assistance, subject to clinician review.
- Run regression/safety packs.
- Compare outcomes across model versions.
- Inspect reasoning/evidence traces.
- Link to the evaluation platform where appropriate.

### Release governance

- Clinical review gates.
- Approval status.
- Version promotion.
- Release notes.
- Effective dates.
- Rollback support.
- Evidence pack links.

### Audit and explainability

Users should be able to understand:

- which model was used;
- which evidence influenced behaviour;
- what changed between versions;
- who approved changes;
- which tests were executed;
- why a threshold or guardrail exists.

## Conceptual workflow

1. Select model/domain.
2. Review structure and clinical content.
3. Review CPTs / probability configuration.
4. Review safety guardrails and thresholds.
5. Run or inspect tests/vignettes.
6. Resolve findings.
7. Clinical approval.
8. Release/promotion.
9. Monitor and review post-release evidence.

## Relationship to other capabilities

The Clinical Admin UI is strategically adjacent to:

- Improve How We Author Content;
- Evaluation Platform / Provena;
- TIM analytics;
- model lifecycle governance.

Long term, these overlaps should be considered as part of a coherent clinical safety/authoring/evaluation product rather than creating multiple disconnected administrative experiences.