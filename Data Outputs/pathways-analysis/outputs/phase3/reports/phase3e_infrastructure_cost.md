# Phase 3E — Infrastructure and Cost

## Status

Infrastructure sizing is scenario-based. Absolute AWS costs are illustrative because the checked-in public Fargate rate is an AWS us-east-1 example while the target deployment region is eu-west-2. Refresh the rate card before the ADR is finalised.

## Runtime patterns

- **monolith_always_resident** — 1.00 inference operations/assessment; basis: single whole-model inference.
- **federated_all_resident** — 1.43 inference operations/assessment; basis: Phase 2 structural minimum plausible-family fan-out.
- **federated_lazy_loaded** — 1.43 inference operations/assessment; basis: same structural fan-out plus 10% explicit cache/load coordination sensitivity assumption.
- **hierarchical_shared_core** — 2.43 inference operations/assessment; basis: one shared/core inference plus Phase 2 structural minimum family fan-out.

## Cost scenarios

The generated CSV contains monthly and per-1,000-assessment values for 100k, 1m and 5m assessments/month. These figures should be used for relative sensitivity only until production traffic and eu-west-2 pricing are supplied.

## Phase 3E conclusion

The cost model is now explicit and reproducible. The largest uncertainties are production traffic, observed inference duration, family fan-out under real cases, and the final eu-west-2 commercial rate card. Those uncertainties are carried into Phase 3F rather than hidden.
