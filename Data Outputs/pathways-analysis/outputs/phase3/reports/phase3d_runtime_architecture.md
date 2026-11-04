# Phase 3D — Runtime Architecture

## Scope

This phase maps the logical model options to runtime deployment patterns. It does not choose a final architecture and it does not assume that a federated Bayesian design requires one microservice per family.

## Runtime patterns carried into costing

### monolith_always_resident

- Logical model: monolithic
- Deployment: one central inference service; model replicated per worker
- Residency: whole model loaded on every active worker
- Scaling unit: whole-model worker
- Versioning: single model artefact/version plus service version
- Implication: Simple routing and version coordination, but every worker carries the full model and every model release has estate-wide blast radius.

### federated_all_resident

- Logical model: federated
- Deployment: one central inference service; all family models resident in each worker
- Residency: all family models loaded on every worker
- Scaling unit: worker containing complete family set
- Versioning: family-set manifest plus per-family versions
- Implication: Keeps deployment simple while preserving smaller inference units, but memory may approach the aggregate size of all family models and duplicate shared features.

### federated_lazy_loaded

- Logical model: federated
- Deployment: one central inference service with model cache; families loaded on demand
- Residency: hot families cached; cold families loaded from artefact store
- Scaling unit: inference worker plus family-model cache capacity
- Versioning: immutable family artefacts referenced by manifest
- Implication: Can reduce resident memory, but introduces cold-load latency, cache policy, artefact availability and more observable runtime states.

### hierarchical_shared_core

- Logical model: federated_hierarchical
- Deployment: central inference service with shared/common model layer plus family models
- Residency: shared layer resident; family models resident or cached according to policy
- Scaling unit: shared-layer worker capacity plus family inference capacity
- Versioning: shared-core version plus compatible family versions in a release manifest
- Implication: Reduces uncontrolled duplication of common evidence, but creates the most explicit compatibility and coordination requirements.

## Cross-family coordination evidence

Phase 2 routing ambiguity and shared-feature evidence are used only as structural indicators. They do not describe production case volumes.

- one plausible family: 70.92 percent of structurally scored pathways. Structural routing evidence only. It indicates where a runtime router may need one versus several candidate families, but it is not a production traffic distribution.
- two plausible families: 15.58 percent of structurally scored pathways. Structural routing evidence only. It indicates where a runtime router may need one versus several candidate families, but it is not a production traffic distribution.
- three or more plausible families: 13.5 percent of structurally scored pathways. Structural routing evidence only. It indicates where a runtime router may need one versus several candidate families, but it is not a production traffic distribution.
- high structural ambiguity: 21.6 percent of structurally scored pathways. Structural routing evidence only. It indicates where a runtime router may need one versus several candidate families, but it is not a production traffic distribution.
- strong single-family association: 46.63 percent of structurally scored pathways. Structural routing evidence only. It indicates where a runtime router may need one versus several candidate families, but it is not a production traffic distribution.
- shared features: disposition: 45.0 broadly shared features. Out of 194 measured features, 60 are family-specific. Broad sharing creates a design choice between duplication, shared model structure or evidence propagation.
- shared features: question: 163.0 broadly shared features. Out of 3787 measured features, 2370 are family-specific. Broad sharing creates a design choice between duplication, shared model structure or evidence propagation.
- shared features: snomed: 65.0 broadly shared features. Out of 297 measured features, 84 are family-specific. Broad sharing creates a design choice between duplication, shared model structure or evidence propagation.
- shared features: symptom_discriminator: 33.0 broadly shared features. Out of 469 measured features, 255 are family-specific. Broad sharing creates a design choice between duplication, shared model structure or evidence propagation.

## Benchmark coverage

Phase 3C benchmark evidence is summarised as an envelope rather than collapsed into one latency figure because parent count, state cardinality and topology materially affect exact inference.

- deduplicated_monolith/whole_model: max benchmark nodes 250, coverage 6.6%. Envelope spans different parent/state cases. It is not a single latency estimate and must be read with benchmark_results.csv.
- literal_monolith/whole_model: max benchmark nodes 250, coverage 0.5%. Envelope spans different parent/state cases. It is not a single latency estimate and must be read with benchmark_results.csv.
- provisional_federated/largest_family: max benchmark nodes 250, coverage 30.6%. Envelope spans different parent/state cases. It is not a single latency estimate and must be read with benchmark_results.csv.
- provisional_federated/median_family: max benchmark nodes 37, coverage 100.0%. Envelope spans different parent/state cases. It is not a single latency estimate and must be read with benchmark_results.csv.

## Phase 3D conclusion

The runtime comparison should carry four deployment patterns into Phase 3E rather than equating logical federation with microservices. The key operational differences are model residency, cross-family fan-out, version coordination, failure scope and release blast radius. Phase 3E can now map these patterns to concrete AWS infrastructure and cost scenarios.
