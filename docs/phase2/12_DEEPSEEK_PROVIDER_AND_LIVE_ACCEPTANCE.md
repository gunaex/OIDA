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

## Phase 2.1B Live Acceptance Closure

The earlier operational blocker was configuration-related and is preserved above.
On 2026-08-29 a credential became available. Preflight detected that the first
credential had also been placed in tracked `.gitignore`; it was removed before any
commit, revoked, and replaced. The restarted acceptance run used the rotated key
from ignored, untracked `.env`. Final scans found no real key in the workspace
outside `.env`, tracked files, Git history or remote content.

### Provider Configuration and Smoke Test

```text
AI_PROVIDER=deepseek
AI_MODEL=deepseek-v4-pro
AI_REASONING_EFFORT=high
DEEPSEEK_AUTH=PASS
DEEPSEEK_API_REACHABLE=PASS
DEEPSEEK_STRUCTURED_OUTPUT=PASS
ROTATED_KEY_SMOKE_LATENCY_MS=2780.93
ROTATED_KEY_SMOKE_INPUT_TOKENS=194
ROTATED_KEY_SMOKE_CACHE_HIT_TOKENS=128
ROTATED_KEY_SMOKE_OUTPUT_TOKENS=96
```

### Canonical Project and Solution Run

The isolated canonical project was `Canonical Customer Self-Service Portal` with
nine frozen requirements covering enterprise authentication, invoice list/PDF,
support creation/status, role authorization, audit, responsive UI and a resilient
billing source-of-truth boundary.

The first live run produced three valid options with 9/9 explicit coverage each:

1. Modular monolith with a Backend-for-Frontend and direct enterprise IdP adapter.
2. Event-driven microservices with an edge gateway and live billing query gateway.
3. Serverless edge composition with managed identity and thin functions.

These differ materially in topology, deployment unit, asynchronous infrastructure,
scaling model, failure modes and operational ownership. The first optimizes for a
lower-complexity initial release; the second for independent scale/evolution at
substantially higher coordination cost; the third for managed operations while
accepting cold-start, timeout and vendor-lock-in trade-offs.

```text
SOLUTION_OPTIONS=3
OPTIONS_MATERIALLY_DIFFERENT=YES
REQUIREMENT_COVERAGE=9_COVERED_0_PARTIAL_0_NOT_COVERED
SOLUTION_LATENCY_MS=188477.67
SOLUTION_INPUT_TOKENS=2327
SOLUTION_CACHE_HIT_TOKENS=0
SOLUTION_OUTPUT_TOKENS=11500
SOLUTION_COST_USD=0.024305820
```

### Human Solution Control and Committed Solution

The human owner compared all options, edited the modular option to set an explicit
eight-second billing timeout/circuit-breaker constraint, clarified a billing risk,
and resolved its required baseline decision. The owner rejected the microservice
option, regenerated from the serverless candidate, selected the edited modular
option and committed `SOL-001` revision
`solrev_10270267a71f4cc0a9848122c0aa8ba1`. Commit retry returned the same solution.
Original AI content and five-candidate history remain available.

The regeneration control call cost $0.022688160, used 2,306 input and 10,690 output
tokens, and took 163,774.30 ms. It was a human-control test, not prompt tuning.

### Delivery Plan Run and Quality

The exact committed solution generated six workstreams, 24 concrete delivery
items, six milestones and 38 initially valid dependencies. Work included identity
claim mapping, billing contract/adapter and chaos validation, ownership-safe PDF
streaming, support persistence/status, synchronous audit, responsive viewport
verification, security testing, deployment configuration and observability.

```text
DELIVERY_PLAN_QUALITY=PASS
DELIVERY_ITEMS_ACTIONABLE=YES
SOLUTION_PLAN_CONSISTENCY=PASS
PLAN_LATENCY_MS=237918.89
PLAN_INPUT_TOKENS=4155
PLAN_CACHE_HIT_TOKENS=0
PLAN_OUTPUT_TOKENS=20456
PLAN_COST_USD=0.043245180
```

### Human Plan Control

The human owner edited the identity integration item and effort, added
`human-architecture-review`, removed a generated runbook item, changed the
dependency set and committed `PLAN-001` revision
`planrev_12399d4c763648898d0f03877836d701`. Revisions 2–5 and the
`DELIVERY_ITEM_ADDED` human audit event provide provenance. Commit retry and
authoritative readback returned the same plan.

### Traceability Sample

All nine requirements have a valid exact-revision chain. Examples include:

```text
REQ-003 Authorized invoice PDF download
→ Invoice Self-Service Module
→ End-to-end customer journey validation

REQ-007 Security audit trail
→ Audit Trail Module
→ Audit durability validation

REQ-009 Billing boundary resilience
→ Billing API Adapter
→ Billing API adapter implementation
```

### Gate 2, Read-after-write and Project Truth

The owner froze Delivery Baseline `dbl_17c101f5aba04d4e95ef8e0798ce6de6`
v1. Its immutable exact membership is Requirement Baseline
`rbl_3d1d1cb60dfa480da93f444ebe8009c4` v1, solution revision
`solrev_10270267a71f4cc0a9848122c0aa8ba1`, and plan revision
`planrev_12399d4c763648898d0f03877836d701`. Retry returned the same baseline;
readback was `FROZEN`; Project Truth reported `GATE_2_COMPLETE`; Phase 2 attention
was empty. Baseline immutability remains covered by the full regression suite.

### Latency, Token Usage and Cost

The pricing snapshot and formula above were applied at off-peak rates. All five
real calls—two smoke calls, solution, human-control regeneration and plan—cost an
estimated $0.090722456. The normal accepted one-solution plus one-plan AI cost is
$0.067551000. No prompt-quality tuning call or repair retry was needed.

Latency of 188.5 seconds for solution generation and 237.9 seconds for planning is
tolerable for professional first-pass work but too slow for a chat-like interaction;
future UX should present these as durable background jobs. High reasoning effort is
retained because only one accepted quality sample exists and quality was strong.

### Prompt Tuning History and Known Quality Limitations

| Cycle | Problem observed | Change | Result |
| --- | --- | --- | --- |
| 0 | No material quality failure | None | Initial solution and plan passed |

The output is verbose and token-heavy, effort classes still require delivery-team
calibration, and this is one canonical-project sample. Browser automation remains
absent; real server/UI loading and all domain actions were verified through HTTP.

### Acceptance Decision

```text
LIVE_AI_ACCEPTANCE=PASS
FULL_PHASE2_GOLDEN_FLOW=PASS
PHASE_2_ACCEPTANCE=PASS
GATE_2_OPERATIONAL=YES
PHASE_3_READY=YES
```

Phase 3 is recommended as Delivery Execution Materialization but was not started.
