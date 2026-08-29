# Phase 4 QA Target Adapter

The adapter contract declares target capabilities and implements create, get, list, and evidence-link operations. `INTERNAL` is fully operational and confirmed by readback. `MANUAL_EXTERNAL` requires a human-provided external reference. `QA_AGAIN` never falls back to Internal.

Deterministic contract tests cover confirmation, timeout, create failure, missing readback, and duplicate-key behavior. Read-only inspection of the current QA Again repository found a real intake boundary, but it accepts only Account-Again-issued `CONDUCTOR_MAIN` identity. OIDA has no authorized service binding, so the live probe is `BLOCKED/ERROR`; no mock is presented as live.

```text
QA_AGAIN_ADAPTER=PASS
QA_AGAIN_LIVE_INTEGRATION=BLOCKED
```

