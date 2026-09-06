# Probabilistic Triage — Decision Register

This file records the current working decisions and architectural directions for Probabilistic Triage. Where a formally approved ADR, ODP, clinical safety record, governance decision or regulatory artefact conflicts with this file, the approved artefact takes precedence and this register should be updated.

| Decision | Status | Rationale / implication |
|---|---|---|
| Centralise probabilistic inference and decisioning in the Probabilistic Triage capability | Accepted | Keeps clinical behaviour, safety policy, versioning and governance consistent across channels and consumers. |
| Consuming services integrate through APIs rather than implementing their own probabilistic reasoning | Accepted | Avoids duplicated clinical logic and inconsistent outcomes. |
| Use Bayesian probabilistic reasoning as the core clinical reasoning approach | Accepted | Supports evidence updates, uncertainty, explainability and adaptive questioning. |
| Progress toward a federated / hierarchical Bayesian topology | Direction | Reduces monolithic model complexity and CPT explosion while allowing specialist clinical-domain models. |
| Separate the Bayesian Network build pipeline from runtime inference | Accepted | Allows controlled model generation, validation, approval and immutable release independently of live triage. |
| Use AWS Bedrock only for build-time assistance, not runtime triage decisions | Accepted | Maintains clinical control and prevents LLM-generated live decision making in the synchronous clinical path. |
| Require clinician review and sign-off for clinically relevant generated model content | Accepted | Ensures human clinical governance and auditable approval. |
| Use AWS SageMaker for modelling / data science workloads where appropriate | Accepted | Approved platform capability for controlled model development and experimentation. |
| Use Amazon Neptune as the approved graph technology where graph persistence/representation is required | Accepted | Engineering Board approved; aligns with model/graph representation needs. |
| Use FHIR as the target interoperability contract | Accepted | Aligns the service with the wider NHS interoperability direction and ATN ecosystem. |
| Keep Patient Triage API / iNav as consumers/orchestrators rather than owners of probabilistic decision logic | Accepted | Preserves central ownership of inference while enabling hybrid deterministic/probabilistic journeys. |
| Use CIS2 for Clinical Admin UI authentication | Accepted | Aligns clinical/admin access with NHS identity controls. |
| Include a Clinical Admin UI for review, testing, approval, guardrails and governance | Accepted | Clinical model behaviour must be visible and governable rather than managed only through engineering tooling. |
| Expose DAG and CPT views in the Clinical Admin UI | Accepted | Supports model understanding, review and clinical assurance. |
| Support model safety guardrails, thresholds, channel settings and risk policy through controlled administration | Accepted | Enables governance of behaviour without distributing clinical logic into consuming channels. |
| Keep EventBridge out of the synchronous runtime triage request/response path | Accepted | Direct synchronous interaction is simpler and avoids unnecessary latency and coupling. |
| Use CloudWatch / operational telemetry for runtime monitoring and analytics where suitable | Accepted | Provides observability without requiring an event bus in the synchronous path. |
| Version model artefacts and policy/threshold configurations | Accepted | Runtime decisions must be reproducible and auditable against the exact approved configuration used. |
| Treat approved model artefacts as immutable releases | Accepted | Protects clinical assurance, rollback and traceability. |
| Maintain explainability and evidence provenance as first-class capabilities | Accepted | Required for clinical assurance, investigation, governance and potential regulatory scrutiny. |
| Align structured triage output with TOM rather than creating a separate outcome model | Accepted | Avoids duplication and supports common downstream integration. |
| Use SNOMED CT for relevant coded clinical concepts | Accepted | Aligns clinical semantics to the established NHS terminology approach. |
| Use adaptive question selection, including Information Gain-style approaches | Direction | Supports reduced question burden while retaining clinically useful evidence gathering. |
| Keep runtime risk/stopping policy separate from raw Bayesian probabilities | Accepted | Clinical disposition decisions require explicit controlled policy rather than probability alone. |
| Maintain deterministic baseline comparison and safety regression testing | Accepted | Enables evidence-based assurance against known pathway behaviour. |
| Use Provena / Evaluation Platform capabilities strategically for model testing where alignment is practical | Direction | Avoids duplicated testing platforms and supports a unified strategic product direction. |
| Treat AI-generated vignettes as test assistance subject to clinician review | Accepted | Useful for scale, but generated clinical test material cannot be trusted without governance. |
| Do not move LLM reasoning into the live patient triage decision path | Accepted | Current product and assurance position is a probabilistic Bayesian runtime with controlled build-time AI assistance. |
| Keep medical-device classification impact visible when adding features | Accepted | Features that increase autonomy, clinical influence or decision-making scope may change component/function-group classification and assurance obligations. |
| Prefer strategic convergence across Probabilistic Triage, Evaluation Platform, TIM and new authoring capability while allowing tactical delivery | Direction | Workstreams are at different maturity stages but share substantial governance, authoring, testing and analytics concerns. |

## Decisions that should only be reopened with new evidence

The following should be treated as baseline architecture unless explicitly challenged by new constraints:

- centralised probabilistic inference;
- API-based consumption;
- Bayesian clinical reasoning;
- separation of build-time and runtime;
- build-time-only LLM use;
- clinician-in-the-loop model governance;
- FHIR interoperability direction;
- CIS2 for clinical administration;
- no EventBridge in the synchronous runtime path;
- explicit model/policy versioning and auditability.

## Areas still expected to evolve

These are not fully fixed and can be refined as discovery, alpha/beta evidence and regulatory work progresses:

- exact federated BN topology and routing/aggregation design;
- runtime state persistence mechanism;
- exact inference library/runtime implementation;
- final API resource/profile design;
- exact channel-specific configuration boundaries;
- strategic integration with Provena and authoring tooling;
- final medical-device component/function-group boundaries;
- ML-based diagnostic probability capability;
- production performance targets and scaling parameters;
- exact model release workflow and approval gates.