# Clinical Reasoning Model

## Purpose

The clinical reasoning model represents how Probabilistic Triage reasons across patient evidence to estimate clinically meaningful probabilities and support triage outcomes.

## Current model shape

The working model uses Bayesian reasoning across layers such as:

- demographics, comorbidities and exposure;
- historical factors;
- risk assessment;
- clinical findings;
- symptoms;
- diagnostic hypotheses;
- disposition / urgency outcome.

The exact node structure may differ by specialised network in a federated topology.

## Design principles

- relationships should be clinically meaningful and reviewable;
- variables should use controlled terminology where possible;
- CPTs must be versioned and traceable;
- diagnostic probability is evidence for reasoning, not necessarily the final triage outcome;
- disposition should remain governed by explicit safety and risk policy;
- the model must support explanation of which evidence materially influenced the result.

## Layering

A useful conceptual order is:

1. Background/context — demographics, comorbidities, exposure.
2. Historical evidence — onset, history and relevant prior factors.
3. Risk indicators — red flags and high-consequence characteristics.
4. Findings and symptoms — observed or reported evidence.
5. Diagnostic hypotheses — posterior probabilities across plausible conditions.
6. Disposition — clinically governed urgency/care outcome.

This is a conceptual structure rather than a requirement for every network to contain every layer.

## Safety principle

A low probability of a high-consequence condition must not automatically imply a low-risk disposition. Risk policy must account for consequence as well as probability.

## Future direction

Later ML capability may contribute diagnostic probability estimates or CPT calibration, but should enter the same governed reasoning and approval lifecycle rather than bypass it.