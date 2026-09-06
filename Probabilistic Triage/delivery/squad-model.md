# Squad Model

## Available capability

Current known delivery capability includes:

- 1 Architect
- 1 Lead Software Engineer
- 3 Senior Software Engineers
- 1 Test Engineer
- 4 Data Scientists / AI Engineers
- 2 Platform Ops
- 3 Business Analysts
- 1 Delivery Manager
- 1 Product Manager
- 1 MDD Writer
- 2 Clinicians
- 1 Technical Writer
- 1 Security Engineer
- 1 AI Ethics Manager
- 1 CSO
- 1 User Researcher
- 1 Content Writer
- 1 Interaction Designer

The interoperability team is advisory rather than a dedicated implementation squad.

## Recommended workstream grouping

### Model and Inference Squad

Focus:

- BN build pipeline;
- ontology/variables;
- CPTs/calibration;
- federated model design;
- runtime inference;
- adaptive questioning;
- explainability.

Typical core roles:

- Lead SWE / Senior SWE
- Data Scientists / AI Engineers
- Architect
- Clinicians
- BA support
- Test support

### Clinical Experience and Governance Squad

Focus:

- Clinical Admin UI;
- DAG/CPT review;
- guardrails and threshold management;
- model/version workflow;
- testing/vignette UX;
- approvals and release governance.

Typical core roles:

- Senior SWE
- Interaction Designer
- User Researcher
- Product Manager
- Content Writer
- Clinicians
- BA
- Test

### Platform, Integration and Assurance Workstream

Focus:

- AWS platform;
- CI/CD;
- API/FHIR implementation;
- observability;
- security;
- operational resilience;
- evidence/audit plumbing;
- regulatory and safety coordination.

Typical core roles:

- Senior SWE
- Platform Ops
- Security Engineer
- Architect
- MDD Writer
- CSO
- Technical Writer
- AI Ethics Manager
- interoperability advisors when required

## Cross-cutting roles

Some roles should not be permanently isolated inside one squad:

- Architect — maintains end-to-end design and decision coherence.
- Clinicians — support model design, test cases, UI governance and safety.
- Test Engineer — establishes common automation and safety-test strategy across components.
- CSO / MDD Writer — ensure architecture/product changes remain aligned to safety and regulatory evidence.
- Product Manager / Delivery Manager — coordinate dependencies and strategic convergence.

## Delivery constraints

With only one dedicated test engineer and one architect, avoid creating too many independent squads. Prefer two primary delivery squads plus one lighter platform/assurance workstream rather than fragmenting scarce specialist roles.

## Interoperability model

The interoperability team should be engaged at design and review points for:

- FHIR resource/profile choices;
- TOM alignment;
- API semantics;
- terminology representation;
- compatibility with ATN/iNav ecosystem standards.

They are an expert advisory dependency, not assumed delivery capacity.

## Strategic coordination

Maintain active alignment with:

- Evaluation Platform / Provena;
- TIM;
- Improve How We Author Content;
- PTA / iNav / ATN integration teams.

The immediate goal is to deliver Probabilistic Triage safely without duplicating strategic platform capabilities unnecessarily.