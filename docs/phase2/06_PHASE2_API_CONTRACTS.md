# Phase 2 API Contracts

Primary routes (all under `/api/projects/{project_id}`):

| Route | Purpose |
|---|---|
| `GET /solution-readiness` | prove Gate 1 prerequisite |
| `POST /ai/solutions:generate` | exact-baseline alternatives |
| `GET/PATCH /solution-candidates...` | inspect and append human revision |
| `POST ...:select|:reject|:regenerate|:commit` | solution controls |
| `POST /solution-candidates:merge` | human composite with lineage |
| `GET/PATCH /solutions...` | committed current solution/revisions |
| `POST /ai/delivery-plans:generate` | exact solution → plan candidate |
| `GET/PATCH /delivery-plan-candidates...` | inspect/edit full structure |
| `POST/DELETE .../items` | manual add/remove |
| `PUT .../dependencies` | replace validated dependency set |
| `POST ...:reject|:regenerate|:commit` | plan controls |
| `GET /delivery-baselines/readiness` | deterministic Gate 2 blockers |
| `POST /delivery-baselines:freeze` | human-owner exact freeze |
| `GET /delivery-baselines[/{id}]` | list/exact readback |

Generation, merge, commits, regeneration and freeze require `Idempotency-Key`.
Commits and freeze reconcile authoritative reads before reporting success.
Field-level schemas remain available from the generated OpenAPI `/docs` endpoint.
