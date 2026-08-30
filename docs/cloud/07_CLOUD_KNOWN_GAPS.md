# Cloud Known Gaps

Date: 2026-08-30
Phase: 4.5D

## Closed core P1 issues

- `P1-001=CLOSED`: DeepSeek strict structured output now expresses priority and confidence as JSON Schema enums using `Literal`; every genuine closed vocabulary is schema-visible. Responses are also validated against Pydantic and exact domain references. One bounded schema repair and one bounded domain/reference repair are allowed; failure remains fail-closed. No Chat Completions fallback exists.
- `P1-002=CLOSED`: long AI operations use durable PostgreSQL jobs, a separate Fly worker, atomic claiming, leases, stale-lease recovery, attempts, idempotency, status polling, and durable terminal results. Public start requests return HTTP 202 quickly and no longer wait inside the Cloudflare request window.
- `P1-003=CLOSED`: a bootstrap user is forced to change password before project access. Current-password verification, 14-character minimum, confirmation, password reuse rejection, session-version rotation, audit events, and rejection of the old password are enforced server-side.

`CORE_P1_OPEN=0`.

## Remaining external/operational limitations

- Document Again reachability passes, but live OIDA access is `BLOCKED_UNSAFE_IDENTITY_PROVISIONING`. An authenticated administrator-controlled path to provision a dedicated OIDA service identity with least-privilege read scope is unavailable. The unauthenticated privileged provisioning route was deliberately not used. Direct Project Context/paste or upload is the temporary pilot path; Document provenance and stale-document monitoring are unavailable through that fallback.
- PM Again live access is closed for pilot use. A dedicated backend service user authenticates through the normal PM API, the `true-cloud-migration` binding is `READY`, exactly two bounded acceptance tasks passed create/readback/idempotency/status/reconciliation, and project isolation returned 404. PM Again has no native milestone or dependency fields, so OIDA does not claim those capabilities.
- Login throttling is process-local; aggregate edge rate limiting is needed before horizontally scaling the backend.
- Cloudflare Access, a custom domain, production alerting, and an observed restore drill remain operational hardening work.
- Physical remote-device testing is `MANUAL_PENDING`; two independent cloud HTTP sessions passed shared-state and AI visibility checks.

The former live-AI/schema, HTTP 524, first-login, and PM-not-configured gaps remain documented in their historical reports, but are no longer open defects. Document Again identity provisioning remains the only external integration blocker for real-project dogfood.
