# Cloud Acceptance Results

Date: 2026-08-30
Phase: 4.5D

## P1 closure result

- Live DeepSeek strict structured output: PASS through the Responses API with strict JSON Schema and application/domain-reference validation.
- Durable asynchronous AI: PASS. Requirements, solution, delivery, and execution returned HTTP 202 in 0.42–0.55 seconds and reached `QUEUED → RUNNING → COMPLETED` through the public Cloudflare URL.
- Long-run edge behavior: PASS. Live operations took 91.61, 170.60, 129.23, and 92.30 seconds without holding the browser request or producing HTTP 524.
- Multi-session/reload recovery: PASS. An independent session observed every run and its terminal durable result. The completed run and Project Truth remained readable after restarting the Fly API machine.
- First-login password control: PASS. Project access was denied until password change; the session version rotated; the old password was rejected.
- Cloud Golden Flow: PASS through login, project/context, asynchronous requirements, human acceptance, Gate 1, asynchronous solution and delivery, human decision deferral, Gate 2, execution materialization, reconciliation, and Project Truth.
- Final execution state: 8 confirmed items, `MATERIALIZED`, reconciliation `SUCCEEDED`, execution health `HEALTHY`.

## Regression and infrastructure

- SQLite regression: 86 passed.
- Managed PostgreSQL critical regression: 32 passed against the dedicated `oida_acceptance_tests` database.
- Production PostgreSQL: 63 public tables, seven additive migrations through `007_cloud_p1_async_auth`, and durable async job rows present.
- Python compile, JavaScript syntax, Docker build, Cloudflare Worker build/dry-run, repository secret scan, and frontend exposure scan: PASS.
- Fly API/worker, Cloudflare Worker/static UI, HTTPS, authentication/session controls, Origin enforcement, project scoping, persistence, and no-local-machine dependency: PASS.
- Public URL: `https://oida-pilot-web.gunaex.workers.dev`.

Document Again and PM Again remain `BLOCKED_NOT_CONFIGURED`; these are external integration limitations rather than core P1 defects.

## Preserved earlier result

Phase 4.5C previously failed because a live response violated the application schema, synchronous generation produced Cloudflare 524, and forced first-login password change was absent. That evidence is retained as historical diagnosis and is superseded by the Phase 4.5D acceptance above; it has not been erased or reclassified as a pass.

Result: `CLOUD_PILOT_ACCEPTANCE=PASS_WITH_EXTERNAL_INTEGRATION_GAP`.
