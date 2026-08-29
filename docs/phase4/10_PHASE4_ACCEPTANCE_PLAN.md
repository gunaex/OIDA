# Phase 4 Acceptance Plan

Acceptance requires:

1. Preserve Phase 1–3 regressions and verify Gate 2 source truth.
2. Exercise fake and live structured QA generation, malformed output, timeout/unavailable behavior, and unknown refs.
3. Demonstrate human edit, reject, add, revision, commit, idempotency, staleness, and full criterion coverage.
4. Materialize Internal validation with readback; test target timeout/failure/dedup contracts.
5. Record PASS, controlled FAIL, BLOCKED policy, re-test, and history.
6. Capture TEST and INTERNAL evidence; test CUSTOMER modeling, missing/invalid/superseded/cross-project/unsafe cases.
7. Generate blocked and ready Acceptance Packages; prove failure and evidence gaps cannot be hidden.
8. Verify deterministic Gate 3, authority, exact membership, idempotency, immutability, and readback.
9. Run browser/runtime, compile, JavaScript, full tests, secret scan, live telemetry, and remote verification.

QA Again live is allowed to remain blocked only when its adapter contract passes and the gap is reported explicitly.

