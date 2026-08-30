# Cloud Pilot Deployment Closure

Date: 2026-08-30  
Phase: 4.5C  
Source: `48b4678d67d5a511d2a44fd1e9b78b2ae7af8965` / `v2.0-phase4.5`

## Topology

- Public UI/API: Cloudflare Worker and static assets at `https://oida-pilot-web.gunaex.workers.dev`.
- Backend origin: Fly application `oida-2-pilot`, region `sin`, at `https://oida-2-pilot.fly.dev`.
- Database: Fly Managed Postgres cluster `oida-2-pilot-pg`, region `sin`, database `oida_pilot`.
- Runtime database identity: dedicated schema-admin user. Credentials exposed by CLI/test output during provisioning were treated as compromised and revoked; the surviving credential is Fly-secret-only.

The historical OIDA 1.x tree remained read-only. No application code was copied, ported, or migrated from it.

## Evidence

- Backend `/ready`: `READY`, PostgreSQL `READY`, DeepSeek configured.
- Migration ledger: six migrations; 62 public tables.
- Managed PostgreSQL critical tests: 27 pass in 141.94 seconds from an ephemeral private-network runner.
- Local regression/build: 79 SQLite tests pass; Python compile, JavaScript syntax, Docker build, and Worker build/dry-run pass.
- Backups: completed full backup plus completed incremental backups.
- Cloudflare: Worker version `2c41a25f-f8cf-422d-a159-0363848cd4d2`; TLS UI and proxied readiness pass.
- Auth: remote login pass; cookie Secure/HttpOnly/SameSite=Strict; missing Origin returns 403; malformed input returns safe 422; attempts 9 and 10 return 429.
- Isolation: a temporary second cloud user received 404 for both read and write against a project with no membership; the user was removed after the test.
- Persistence: a real project, context, committed requirement, and frozen Gate 1 remained readable from a new session after a Fly machine restart.
- Independent sessions: both sessions observed the same authoritative project state.
- No local dependency: all evidence endpoints remained available after remote restart without a local application server or tunnel.

## Live AI result

Provider connectivity and authentication succeeded, and the real configured model was invoked. The accepted-path result is nevertheless FAIL:

- model: `deepseek-v4-pro`
- telemetry: 720 input tokens, 6,081 output tokens, 6,801 total tokens, 72,382 ms
- result: `AI_OUTPUT_INVALID`
- authoritative candidates created: zero
- public edge behavior: HTTP 524 on a separate long request; the backend later recorded the failed run

This is fail-closed behavior, but it prevents Gate 1 AI acceptance and therefore prevents the required cloud golden flow.

## External integrations

- Document Again `/api/health`: HTTP 200; OIDA status `BLOCKED_NOT_CONFIGURED` because API/account/tenant credentials are absent.
- PM Again `/api/health`: HTTP 200; OIDA status `BLOCKED_NOT_CONFIGURED` because its API token is absent.
- No external records were fabricated or created.

## Login handoff limitation

The requested login email is configured. The requested temporary password was not installed because it violates OIDA's production minimum length, and OIDA does not yet implement forced password change at first login. A generated strong bootstrap password is retained in macOS Keychain under service `OIDA 2.0 Cloud Pilot` and the requested email account.

## Closure decision

- P0: 0
- P1: 3 (strict DeepSeek output failure, synchronous edge timeout, first-login password-change gap)
- P2: 4 (Document credentials, PM credentials, aggregate throttling, Cloudflare Access/custom-domain/operations hardening)
- Cloud pilot acceptance: FAIL
- OIDA cloud pilot ready: NO
- Cloud tag: not created
- Phase 5 started: NO

Real-project dogfood is NO-GO until a live AI run passes the strict contract through a deployment path that supports its runtime, followed by the complete cloud golden flow.
