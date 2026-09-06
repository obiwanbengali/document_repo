# Clinical Testing Strategy

## Purpose

Testing must demonstrate that model behaviour, question selection, risk policy and disposition logic remain clinically safe, explainable and stable across releases.

## Test layers

### Unit and component testing

- evidence ingestion;
- Bayesian updates;
- question-selection calculations;
- policy threshold logic;
- fallback behaviour;
- version loading;
- audit trace generation.

### Model evaluation

- discrimination and calibration;
- AUC-ROC where appropriate;
- sensitivity for high-risk conditions;
- probability movement from known evidence;
- comparison of candidate model versions.

### Clinical vignette testing

Use representative and edge-case vignettes to exercise complete triage interactions. Include:

- emergency presentations;
- common low-risk cases;
- ambiguous presentations;
- rare/high-consequence cases;
- contradictory evidence;
- incomplete evidence;
- cross-domain presentations for federated-network testing.

### Regression testing

Every model or policy release should be tested against a stable reference suite so changes in behaviour are visible before promotion.

### Comparative testing

Where useful, compare probabilistic behaviour with deterministic NHS Pathways baselines to understand:

- question-count reduction;
- disposition differences;
- high-risk sensitivity;
- over-triage and under-triage;
- explainability differences.

## Evaluation platform

The Provena/Evaluation Platform workstream is strategically aligned with this need and should be capable of testing triage workflows rather than being tightly coupled to one implementation.

## Safety gates

A candidate model should not progress solely because aggregate metrics improve. Release gates must also include mandatory high-risk scenarios, clinician review, known regression thresholds and evidence that safety-critical cases have not deteriorated.

## Future monitoring

As real-world data becomes available, introduce monitoring for:

- calibration drift;
- population/data drift;
- changes in question patterns;
- disposition distribution changes;
- emerging safety signals.

Monitoring must not silently change production model behaviour; retraining or recalibration should return through the governed build and approval lifecycle.