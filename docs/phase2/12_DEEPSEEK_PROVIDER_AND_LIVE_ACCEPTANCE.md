# OIDA 2.0 — DeepSeek Provider and Live Acceptance

Evaluation date: 2026-08-29 (Asia/Bangkok)

## Decision and Configuration

```text
LIVE_PROVIDER_SELECTED=DEEPSEEK
AI_PROVIDER=deepseek
AI_MODEL=deepseek-v4-pro
AI_REASONING_EFFORT=high
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_API_KEY=NOT_CONFIGURED
TRANSPORT=POST /chat/completions
STRUCTURED_MODE=response_format:{type:json_object}
THINKING=enabled
```

OIDA uses DeepSeek Chat Completions because it is the simplest currently documented
stable path for `deepseek-v4-pro`, thinking mode and JSON output. The adapter places
the JSON Schema in the system instruction, requests one JSON object, then performs
strict Pydantic schema validation and existing deterministic domain/reference
validation. Provider reasoning content is neither requested as product output nor
persisted.

Official sources used for this implementation:

- [DeepSeek API documentation](https://api-docs.deepseek.com/)
- [Create Chat Completion](https://api-docs.deepseek.com/api/create-chat-completion/)
- [JSON Output](https://api-docs.deepseek.com/guides/json_mode/)
- [Current pricing](https://api-docs.deepseek.com/quick_start/pricing/?article_id=article_1779470751466_8)

## Provider-Neutral Contract

The existing `RequirementAdapter` remains the domain boundary for requirement,
solution and delivery-plan generation. `fake`, `openai` and `deepseek` implement
the same typed outputs. An unsupported provider returns `AI_PROVIDER_INVALID` and
does not fall back.

Normalized telemetry is persisted per run:

```text
provider, model, reasoning_effort, input_tokens, cache_hit_tokens,
output_tokens, total_tokens, latency_ms, provider_request_id, error_class
```

Normalized failures include `AI_AUTH_ERROR`, `AI_TIMEOUT`, `AI_RATE_LIMITED`,
`AI_OUTPUT_INVALID`, `AI_GROUNDING_INSUFFICIENT`, `AI_UNAVAILABLE` and
`AI_PROVIDER_INVALID`. Keys remain server-side and are absent from telemetry,
responses and audit detail.

## Automated Acceptance

```text
PYTHON_COMPILE=PASS
AUTOMATED_TESTS=39_PASS
PHASE1_PHASE2_REGRESSION=PASS
DEEPSEEK_VALID_JSON_SCHEMA=PASS
DEEPSEEK_MALFORMED_JSON_REJECTED=PASS
DEEPSEEK_SCHEMA_INVALID_REJECTED=PASS
DEEPSEEK_TIMEOUT_NORMALIZED=PASS
DEEPSEEK_AUTH_NORMALIZED=PASS
DEEPSEEK_RATE_LIMIT_NORMALIZED=PASS
DEEPSEEK_UNKNOWN_REFERENCE_REJECTED=PASS
UNKNOWN_PROVIDER_NO_FALLBACK=PASS
```

The mocked matrix proves transport construction, JSON/schema enforcement,
reference rejection and deterministic error mapping. It is integration evidence,
not live quality evidence.

## Live Acceptance Status

The process contains no `DEEPSEEK_API_KEY`, and the workspace contains no `.env`.
No authenticated request can be made without inventing authority or exposing a
credential. Consequently no canonical live project, live solution alternatives,
live plan or live Gate 2 baseline was created in this attempt.

```text
DEEPSEEK_AUTH=BLOCKED_NOT_CONFIGURED
DEEPSEEK_API_REACHABLE=NOT_TESTED_AUTHENTICATED
LIVE_SOLUTION_GENERATION=NOT_RUN
LIVE_SOLUTION_OPTIONS=NOT_OBSERVED
LIVE_HUMAN_SOLUTION_CONTROLS=NOT_RUN
LIVE_DELIVERY_PLAN_GENERATION=NOT_RUN
LIVE_HUMAN_PLAN_CONTROLS=NOT_RUN
LIVE_TRACEABILITY_SAMPLE=NOT_OBSERVED
LIVE_GATE2_FREEZE=NOT_RUN
LIVE_GATE2_READBACK=NOT_RUN
LIVE_AI_ACCEPTANCE=BLOCKED_NOT_CONFIGURED
```

There is no fake success: mocked or deterministic output is not substituted for
semantic quality, diversity, trade-off usefulness, actionability, traceability or
human browser acceptance.

## Pricing Snapshot and Cost Method

The current official DeepSeek v4-pro pricing snapshot has two time bands:

| Band | Cache hit input | Cache miss input | Output |
| --- | ---: | ---: | ---: |
| Off-peak | $0.022/M | $0.66/M | $1.98/M |
| Peak | $0.044/M | $1.32/M | $3.96/M |

Peak hours are 01:00–04:00 and 06:00–10:00 UTC; all other times are off-peak.
Cost must be computed from the actual provider usage and request time:

```text
COST=(cache_hit_tokens * cache_hit_rate
    + (input_tokens-cache_hit_tokens) * cache_miss_rate
    + output_tokens * output_rate) / 1_000_000
```

No authenticated call occurred, so observed tokens, latency and provider cost are
`NOT_OBSERVED`. Local/mock execution is not reported as provider latency or cost.

## Gate Decision

```text
DEEPSEEK_ADAPTER=PASS
DEEPSEEK_MOCKED_ACCEPTANCE=PASS
PROVIDER_TELEMETRY=PASS_STRUCTURAL
LIVE_PROVIDER_SELECTED=DEEPSEEK
LIVE_AI_ACCEPTANCE=BLOCKED_NOT_CONFIGURED
PHASE_2_ACCEPTANCE=READY_WITH_OPERATIONAL_BLOCKER
GATE_2_OPERATIONAL=YES_STRUCTURAL_ONLY
PHASE_3_READY=NO
PHASE2_TAG=none
```

Required next action: inject `DEEPSEEK_API_KEY` through the authorized server-side
secret mechanism and rerun the canonical Phase 2.1A live flow. Only after live
solution/plan quality, human controls, exact traceability, Gate 2 readback, actual
usage/latency/cost and the full regression suite pass may `v2.0-phase2` be created.
