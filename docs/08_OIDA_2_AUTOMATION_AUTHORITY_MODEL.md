# OIDA 2.0 Automation and Authority Model

## Levels

| Level | Meaning | Typical MVP use |
|---|---|---|
| L0 Human only | AI may provide context; a person performs the action | acceptance, risk waiver, baseline approval |
| L1 Assist | AI recommends/drafts; person performs the committed action | decision and exception resolution |
| L2 Prepare + human commit | AI completes a candidate; person edits/commits | requirements and delivery baselines |
| L3 Execute + human review | AI performs reversible operational work | work/test generation, summaries |
| L4 Policy autonomous | automatic within explicit low-risk boundaries | classification, indexing, gap detection |

## Policy record

Each action type defines default level, maximum level, authority owner role,
required permission, reversibility/compensation, audit level, risk class, scope,
and escalation rule. A project may lower automation. Raising it above the product
maximum is prohibited. Policy evaluation is deterministic and recorded.

## MVP action matrix

| Action | Default / max | Authority owner | Reversible | Audit |
|---|---|---|---|---|
| extract/classify/index context | L4 / L4 | project owner | rebuild | run |
| draft requirements | L2 / L2 | requirement owner | yes | run + candidate |
| commit requirement baseline | L0 / L0 | requirement approver | revision only | full |
| draft solution/plan/QA scope | L2 / L2 | delivery lead | yes | run + candidate |
| commit delivery baseline | L0 / L0 | delivery approver | revision only | full |
| create work and test items | L3 / L3 | delivery/QA lead | archive/undo | full |
| summarize/detect gaps | L4 / L4 | project owner | dismiss/recompute | run |
| change committed status | L3 / L3 | work owner | compensate | full |
| waive failed validation/risk | L0 / L0 | named approver | revision only | full |
| final acceptance | L0 / L0 | acceptance authority | no simple undo | signed/full |

## Attention policy

Routine successful L3/L4 actions appear in activity history. Human attention is
requested for blocked policy, conflict, low confidence, irreversible impact,
baseline change, material risk, validation failure, or authority-required action.

