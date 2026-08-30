# External Integration Closure

Date: 2026-08-30  
Scope: Document Again and PM Again live pilot acceptance

## Decision

PM Again live integration is accepted for bounded pilot use. Document Again remains safely blocked because OIDA cannot obtain a least-privilege service identity through an authenticated administrator-controlled provisioning path. The Document Again application, PM Again application, Account Again application, and OIDA 1.x repositories were treated as read-only throughout this closure.

`PM_AGAIN_CLOUD_READY=YES`

`DOCUMENT_AGAIN_CLOUD_READY=NO`

`REAL_PROJECT_DOGFOOD_READY=YES_WITH_LIMITATIONS`

## PM Again live evidence

- Dedicated backend service-user authentication: PASS. The credential is runtime-only and is not present in source, frontend assets, logs, or this report.
- Reachability and bound-project verification: PASS for `true-cloud-migration`; binding `bind_f302dc27399d4288962718a1a06f8b32` is `READY` with a verification timestamp.
- Capability discovery: PASS. Task create, task/status read, owner, and priority are supported. Native milestone and dependency fields are not supported and are not claimed. OIDA lineage is carried in the task description transport marker.
- Human authority: PASS. The OIDA Project Owner authorized materialization; neither AI nor the service account exercised authorization.
- Create/readback: PASS. Exactly two acceptance tasks were materialized, with PM task IDs `1` and `2`; both remained in the bound project and read back with their expected titles, business descriptions, and one exact OIDA idempotency marker each.
- Idempotency: PASS. Replaying the same OIDA materialization request returned the same result, and the authoritative PM project still contains exactly two tasks with the acceptance prefix.
- Status authority: PASS. PM reported `Todo`; OIDA normalized this to `NOT_STARTED` and recorded `last_verified_at`.
- Reconciliation: PASS. Run `recon_03c4b92414544773b0776f7a495d1e7c` completed `SUCCEEDED` with 10 confirmed, 0 missing, 0 mismatch, 0 stale, 0 unconfirmed, and 0 detected drift. The two earlier description drift records are `RESOLVED`; `FALSE_DESCRIPTION_DRIFT=NO`.
- Drift detection: PASS through the deterministic adapter contract test, which changes authoritative owner data and verifies detection without mutating live acceptance tasks.
- Project isolation: PASS. Attempting to verify the binding through a different OIDA project returned HTTP 404.

## Delivery to PM lineage

One representative end-to-end trace is:

```text
delivery item: ditem_9e702d4eb0804299b654db85d5f1d16d
delivery revision: planrev_0f8ee9a512da495aba4a388a780cba28
materialization plan: mplan_f76f99b94bbd4f0381f6f182ac86605c
materialization item: mitem_449c37c24d9242828b106539ae541409
OIDA execution item: exec_e469b70e871140a4a3f89bce8c54c489 / EXEC-009
PM Again project/task: true-cloud-migration / 1
```

The second accepted trace ends at `EXEC-010` / PM task `2`. Both originate from frozen delivery revision `planrev_0f8ee9a512da495aba4a388a780cba28`.

## Document Again limitation

Document Again is reachable and healthy, but live OIDA authentication is `BLOCKED_UNSAFE_IDENTITY_PROVISIONING`. The available identity-provisioning route is not an authenticated administrator-controlled mechanism, so it was not used. Closure requires authenticated administrator-controlled provisioning of a dedicated OIDA service identity with least-privilege read scope.

Until then, operators must provide project context through Direct Project Context/paste or upload. No document provenance or stale-document monitoring is claimed for that fallback.

## Verification gates

- SQLite automated suite: 90 passed.
- Managed PostgreSQL critical suite: 32 passed against the dedicated `oida_acceptance_tests` database; production `oida_pilot` was not used for tests.
- Python compile, JavaScript syntax, Docker build, repository secret scan, and frontend secret exposure scan: PASS.
- Phase 5 started: NO.
- `v2.0-pilot-ready` tag: not created because Document Again remains blocked.

