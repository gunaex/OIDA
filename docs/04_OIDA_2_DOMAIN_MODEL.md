# OIDA 2.0 Domain Model

Only concepts needed by the Golden Flow are first-class in MVP.

| Concept | Purpose / lifecycle | Authority and source of truth | AI / human boundary | Own or reference |
|---|---|---|---|---|
| Project | Workspace and lifecycle from framing to accepted/closed | OIDA; project owner | AI analyzes; human owns frame | Own |
| Context Source | Versioned grounding input | source owner | AI extracts; human/system controls source | Reference metadata |
| Requirement | Testable statement and acceptance criteria; candidate→committed→baselined→superseded | requirement owner/OIDA baseline | AI prepares; human commits baseline | Own |
| Delivery Baseline | Versioned solution, plan, risks, work, validation scope | delivery approver/OIDA | AI prepares; human commits | Own composition; reference materialized items |
| Decision | Question, options, authority, outcome, rationale | named human authority | AI prepares options only | Own |
| Risk | Exposure, response, owner, acceptance/waiver | risk owner | AI detects/drafts; human accepts risk | Own or reference |
| Work Item | Executable delivery unit | PM owner | AI may materialize/update within policy | Reference when external |
| Validation Item | Test/scope and expected evidence | QA owner | AI drafts/analyzes; humans own waivers | Reference when external |
| Validation Result | Observed result and evidence | QA/execution source | AI summarizes, never invents | Reference |
| Evidence | Immutable/versioned proof reference | evidence/document owner | AI indexes/assesses gaps | Reference |
| Acceptance | Final decision over frozen package references | acceptance authority/OIDA | AI prepares; human decides | Own |
| Typed Link | inspectable traceability between retained concepts | owner of source relation | AI proposes; policy/human commits | Own relationship |
| AI Run/Candidate/Action | Explain AI observation, proposal, and execution | OIDA audit | governed by automation policy | Own |
| Automation Policy | Limits AI/service action authority | governance owner | deterministic enforcement | Own |
| Project Truth Projection | Grounded current read model | underlying owners | AI summarizes only | Derived |

Architecture Artifact, Plan, Milestone, Dependency, Test Case, Issue, and Change are
typed content within the delivery baseline or referenced bounded-system records in
MVP; they become separate OIDA entities only when independent lifecycle/authority
is proven necessary. Project Memory is P1.

## Core relationships

Project contains baselines, decisions, risks, policies, and acceptances. Baselines
reference context-source versions. Requirements are satisfied by delivery-baseline
elements; those materialize work/validation items. Validation results generate or
reference evidence and verify requirements. Acceptance freezes references to the
relevant baseline, results, evidence, waivers, and risks. AI records point to every
source and affected artifact without becoming domain truth.

