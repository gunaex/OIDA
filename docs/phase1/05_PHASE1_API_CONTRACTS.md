# Phase 1 API Contracts

Primary action routes:

| Method / route | Intent |
|---|---|
| `POST /api/auth/login` | establish local human session |
| `POST /api/projects` | idempotently create project and owner membership |
| `POST/PATCH /api/projects/{id}/context...` | add/update authoritative context and revision |
| `POST /api/projects/{id}/ai/requirements:generate` | create validated AI Run/candidates |
| `PATCH .../requirement-candidates/{candidate}` | append human candidate revision |
| `POST .../{candidate}:accept|:reject|:regenerate` | explicit candidate controls |
| `POST/PATCH /api/projects/{id}/requirements...` | manual creation / working revision |
| `GET .../requirement-baselines/readiness` | deterministic Gate 1 blockers |
| `POST .../requirement-baselines:freeze` | human-owner exact-version freeze |
| `GET /api/projects/{id}/truth` | compact derived Gate-1 truth and attention |
| `GET /api/projects/{id}/audit` | project authority and AI history |

Important owner actions require `Idempotency-Key`. Create, accept, manual create,
generate/regenerate, and freeze store their confirmed response by
project/actor/action/key. Accept and freeze then read authoritative records and
membership back; uncertainty returns `ACTION_SUCCEEDED_RESOLUTION_UNCONFIRMED`
rather than business success.

The generated OpenAPI document at `/docs` is the field-level API reference.

