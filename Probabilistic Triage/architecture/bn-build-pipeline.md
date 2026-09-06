# Bayesian Network Build Pipeline

## Purpose

The build pipeline converts clinical knowledge, pathway content, terminology, data and expert judgement into governed Bayesian Network artefacts suitable for controlled runtime use.

## High-level stages

1. Source ingestion
2. Structured extraction
3. Terminology / ontology mapping
4. Variable definition
5. Graph / causal relationship construction
6. CPT generation or estimation
7. Calibration
8. Clinical review
9. Automated and vignette-based testing
10. Approval
11. Immutable artefact publication
12. Controlled promotion

## Source material

Potential sources include:

- NHS Pathways deterministic content;
- approved clinical guidance;
- terminology mappings;
- linked TIM / ECDS-derived evidence where appropriate;
- clinician-authored knowledge;
- curated synthetic examples and vignettes.

## Build-time AI assistance

AWS Bedrock can be used as an engineering and clinical-assistance tool during build-time tasks such as:

- extracting structured concepts;
- proposing candidate mappings;
- generating draft variable descriptions;
- suggesting candidate relationships;
- helping generate test vignettes;
- summarising evidence.

All AI-generated content that could affect model behaviour must be reviewed and approved by an appropriate human before it becomes part of an approved artefact.

LLM output is not the runtime clinical decision.

## Model artefact

An approved artefact should capture enough information to reproduce and audit the model, including:

- graph structure;
- variable definitions;
- state definitions;
- CPTs / parameters;
- terminology identifiers;
- provenance;
- build pipeline version;
- source references;
- test evidence;
- clinical approval;
- model version and release metadata.

## Quality gates

Suggested gates include:

- schema validation;
- terminology validation;
- graph integrity checks;
- CPT completeness and normalisation;
- calibration checks;
- high-risk scenario tests;
- regression tests;
- explainability checks;
- clinician sign-off;
- release approval.

## AWS implementation direction

Expected supporting services may include:

- S3 for source and immutable artefacts;
- SageMaker for model/data-science workloads;
- Bedrock for approved AI-assisted build tasks;
- Neptune for graph-oriented representation or supporting graph workflows;
- Step Functions where orchestration adds value;
- CodePipeline/CodeBuild or equivalent CI/CD controls;
- CloudWatch and CloudTrail for operational and audit evidence.

## Security and information governance

- Do not expose unnecessary patient-identifiable information to build-time AI services.
- Use approved de-identified or appropriately governed data.
- Retain provenance for generated and transformed artefacts.
- Keep build-time and runtime permissions separated.

## Release principle

Runtime systems consume only artefacts that have passed the required clinical, technical and governance gates.