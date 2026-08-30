# Cloud Pilot Deployment Closure

Date: 2026-08-30
Phase: 4.5D

## Topology

- Public UI/API: Cloudflare Worker/static assets at `https://oida-pilot-web.gunaex.workers.dev`.
- Backend: Fly application `oida-2-pilot` in `sin`, with separate `app` and `worker` process groups.
- Database: Fly Managed PostgreSQL cluster `oida-2-pilot-pg`, database `oida_pilot`.
- AI: DeepSeek Responses API, strict JSON Schema, no Chat Completions fallback.
- Secrets: runtime-only configuration. Revoked credentials are not reused; no real secret is stored in source, frontend assets, or reports.

## Deployment evidence

- Fly API health check: PASS; `/ready` reports database ready and DeepSeek configured.
- Fly worker consumption: PASS with deployed `QUEUED → RUNNING → COMPLETED` transitions.
- Cloudflare edge/static UI and same-origin API proxy: PASS over HTTPS.
- Cloudflare Worker deployment used for the full P1 golden run: version `349f1c36-343f-418c-a40d-a2e1f12e97e1`; final closure redeploy: version `9dfab83b-082f-4dac-994d-cea181893d5a`.
- Managed PostgreSQL schema: 63 public tables and seven immutable/additive migration ledger entries through `007_cloud_p1_async_auth`.
- Managed PostgreSQL critical suite: 32 passed. Local SQLite suite: 86 passed.
- Restart persistence: API restart followed by successful login, Project Truth readback, and completed AI job readback.
- No local dependency: acceptance and post-restart evidence used only the public Worker URL and deployed cloud services.

## Live P1 evidence

| Operation | Start response | Start time | Total time | Durable states | Result |
|---|---:|---:|---:|---|---|
| Requirements | 202 | 0.42 s | 91.61 s | QUEUED → RUNNING → COMPLETED | SUCCEEDED |
| Solution | 202 | 0.45 s | 170.60 s | QUEUED → RUNNING → COMPLETED | SUCCEEDED |
| Delivery | 202 | 0.44 s | 129.23 s | QUEUED → RUNNING → COMPLETED | SUCCEEDED |
| Execution | 202 | 0.55 s | 92.30 s | QUEUED → RUNNING → COMPLETED | SUCCEEDED |

The solution contained three decisions requiring human authority. The pilot operator explicitly retained them while changing their baseline classification to `CAN_DEFER`; Gate 2 then passed without deleting the decisions or bypassing readiness.

First-login acceptance passed: forced change detected, project access blocked before change, session version rotated, and old password rejected. Two independent sessions saw the same project, AI status/result, and Project Truth. Originless mutation returned 403, cross-project child-resource access returned 404, and malformed input returned a safe 422.

## External integrations

- `DOCUMENT_AGAIN_CLOUD=BLOCKED_NOT_CONFIGURED`
- `PM_AGAIN_CLOUD=BLOCKED_NOT_CONFIGURED`

No external records were fabricated. These are explicit integration limitations, not core P1 failures.

## Historical closure record

Phase 4.5C, source `48b4678d67d5a511d2a44fd1e9b78b2ae7af8965` / `v2.0-phase4.5`, correctly recorded a NO-GO: strict application validation failed, a synchronous public request returned 524, and forced password change was missing. That record remains historically valid. Phase 4.5D adds the corrective implementation and new live evidence rather than rewriting the earlier result.

## Decision

- P0 open: 0
- Core P1 open: 0
- Cloud pilot acceptance: `PASS_WITH_EXTERNAL_INTEGRATION_GAP`
- OIDA cloud pilot ready: YES
- Real-project dogfood ready: YES, with Document Again and PM Again limitations
- Phase 5 started: NO
