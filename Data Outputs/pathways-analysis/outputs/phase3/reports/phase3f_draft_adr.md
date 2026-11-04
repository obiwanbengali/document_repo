# ADR-AI — Bayesian Network Topology for Probabilistic Triage

**Status:** DRAFT — DECISION GATES OPEN

## Context

Probabilistic Triage needs a Bayesian model topology that can represent the NHS Pathways-derived clinical estate while remaining operable, testable and governable. The service deployment boundary is already treated as a central inference capability; this ADR compares the logical Bayesian model topology inside that boundary.

## Options under comparison

1. Literal monolithic Bayesian representation.
2. Question-ID deduplicated monolithic representation.
3. Federated / hierarchical representation using provisional Phase 2 families.

## Evidence summary

### Literal monolith

- Candidate variables: 47983
- Reference CPT case: 3052107 entries (3 parents, median parent-state cardinality)
- Benchmark coverage: 0.5% max model coverage
- Observed benchmark p95 range: 3.636-186.868 ms
- Illustrative 1m-assessment monthly cost: 250.13

### Question-ID deduplicated monolith

- Candidate variables: 3787
- Reference CPT case: 272916 entries (3 parents, median parent-state cardinality)
- Benchmark coverage: 6.6% max model coverage
- Observed benchmark p95 range: 2.348-119.867 ms
- Illustrative 1m-assessment monthly cost: 250.13

### Provisional federated / hierarchical

- Candidate variables: 6990
- Reference CPT case: 493695 entries (3 parents, median parent-state cardinality)
- Benchmark coverage: 100.0% max model coverage
- Observed benchmark p95 range: 3.337-201.060 ms
- Illustrative 1m-assessment monthly cost: 250.13-250.13

## Decision gates

- **PASS — Phase 3A representation evidence:** representation summary exists
- **PASS — Phase 3B CPT sizing evidence:** CPT sizing output exists
- **PASS — Phase 3C benchmark evidence:** benchmark results exist and are non-empty
- **PASS — Phase 3D runtime evidence:** runtime pattern output exists
- **PASS — Phase 3E cost evidence:** cost scenario output exists
- **OPEN — Target-region pricing refreshed:** target=eu-west-2, basis=us-east-1, status=illustrative_only_pending_eu-west-2_refresh
- **OPEN — Clinician-led family review complete:** Phase 2 family refinement is still required before the federated family boundaries can be treated as clinically agreed.

## Decision

No final topology decision is recorded yet. The remaining open gates are visible above. In particular, the federated family set remains provisional until clinician-led refinement, and absolute AWS cost remains illustrative until the eu-west-2 rate card is refreshed. If Phase 3C is still open, runtime performance evidence is also incomplete.

## Existing architectural constraint

Whichever logical topology is selected, it is evaluated inside the same centralised inference-service boundary. Federation does not imply a microservice per family.

## Next actions before finalising

1. Close any remaining Phase 3C benchmark issues and regenerate the evidence.
2. Refresh eu-west-2 pricing with the agreed Commercial / FinOps rate card.
3. Revisit Phase 2 with clinician-led family definition.
4. Re-run affected Phase 3 sizing, benchmark and cost calculations.
5. Record the human architecture decision and consequences in this ADR.
