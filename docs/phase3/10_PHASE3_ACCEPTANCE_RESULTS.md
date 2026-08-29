# Phase 3 Acceptance Results

## Automated and runtime evidence

All 54 automated tests pass. They include all prior regressions plus Gate 2,
authority, exact lineage, plan versioning/override, manual fallback, partial batch,
Internal readback, external timeout/failure/unconfirmed/dedup/deletion, drift,
unlinked work, project scope and migration upgrade. Python compile, JavaScript
syntax and diff checks pass. Final runtime and secret/Git checks are recorded in
the final report.

## Live DeepSeek evidence

Canonical source: `dbl_17c101f5aba04d4e95ef8e0798ce6de6`, version 1, with
24 delivery items. `deepseek-v4-pro` produced 24 grounded one-to-one Internal
mappings with useful role specialization and exact dependency/milestone refs.

```text
AI_RUN=mrun_93f903f5aa9946e195b227b4a8ff7735
PLAN=mplan_7b1056b9b98a49899a28d17311975e6c
INPUT_TOKENS=8594
CACHE_HIT_TOKENS=0
OUTPUT_TOKENS=7768
TOTAL_TOKENS=16362
LATENCY_MS=80492.96
ESTIMATED_COST_USD=0.021052680
```

Cost uses the accepted off-peak snapshot of USD 0.66/M cache-miss input and USD
1.98/M output from the [official DeepSeek pricing page](https://api-docs.deepseek.com/quick_start/pricing/?article_id=article_1779470751466_8).

Human review changed a target then explicitly rerouted to Internal, changed an
owner role, disabled one AI mapping and added one manual replacement. Plan revision
became 5. Authorization and materialization retries were identical. Materialized:
24 confirmed, 0 failed, 0 unconfirmed, 0 blocked. Initial and final reconciliation
were 24/24 confirmed; controlled owner drift was detected between them.

Quality evaluation: routing useful PASS; owner roles useful PASS; dependency and
milestone preservation PASS; split quality PASS (no needless split); warnings
quality PASS for a fully ready Internal route. Administrative work was reduced from
manual recreation of 24 tasks to exception review and one batch action.
