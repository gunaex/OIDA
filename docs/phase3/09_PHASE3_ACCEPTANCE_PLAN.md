# Phase 3 Acceptance Plan

Acceptance covers:

1. Run every Phase 1 and Phase 2 regression without weakening assertions.
2. Prove Gate 2 prerequisite and exact frozen lineage.
3. Validate AI schemas, domain refs, honest failure and manual fallback.
4. Exercise edit, reroute, owner change, split/merge, disable, manual mapping and
   owner-only batch authorization.
5. Prove Internal and external-contract create/readback, partial result,
   unconfirmed safe retry and no duplicates.
6. Reconcile confirmed, missing and modified work; detect/acknowledge/resolve
   drift and unlinked work.
7. Prove project isolation and AI authority denial.
8. Run a live DeepSeek 24-item golden flow and review usefulness.
9. Verify workspace value, Python compile, JavaScript syntax, HTTP/login smoke,
   migration upgrade, secret scan and Git hygiene.

PM Again live is optional; lack of a configured service API must be `BLOCKED`, not
mock success. Stop before Phase 4 implementation and Gate 3.
