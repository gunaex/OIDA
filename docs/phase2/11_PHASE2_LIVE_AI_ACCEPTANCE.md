# Phase 2.1 Live AI Acceptance

Evaluation date: 2026-08-29 (Asia/Bangkok)

## Runtime Configuration

```text
AI_PROVIDER=openai
AI_MODEL=gpt-5.5
REASONING_EFFORT=medium_provider_default
OPENAI_API_KEY=NOT_CONFIGURED
RESPONSES_API=CONFIGURED
STRUCTURED_OUTPUTS=CONFIGURED
```

No secret value was read, printed, logged or committed. The shell environment did
not contain `OPENAI_API_KEY`, and the workspace contained no `.env` file.

Official OpenAI documentation confirms that GPT-5.5 supports the Responses API,
Structured Outputs and reasoning effort `none|low|medium|high|xhigh`; `medium` is
the default. The pricing snapshot used for this evaluation is input $5.00/M,
cached input $0.50/M and output $30.00/M tokens:

- https://developers.openai.com/api/docs/models/gpt-5.5
- https://developers.openai.com/api/docs/guides/latest-model?model=gpt-5.5

## Live Solution Test

`BLOCKED_NOT_CONFIGURED`. A realistic secure Customer Portal project was created
in an isolated temporary runtime with an exact frozen Requirement Baseline. The
OpenAI adapter was invoked with no credential and returned the honest terminal
state:

```text
HTTP_RESULT=200_WITH_EXPLICIT_FAILED_RUN
AI_RUN_STATUS=FAILED
FAILURE_CODE=AI_UNAVAILABLE
SOLUTION_CANDIDATE_COUNT=0
COMMITTED_SOLUTION_COUNT=0
```

No provider request was possible, so this is failure-path evidence—not live output.

## Solution Quality Findings

```text
SOLUTION_OPTION_COUNT=NOT_OBSERVED
OPTIONS_STRUCTURALLY_VALID=NOT_EVALUATED_LIVE
OPTIONS_MATERIALLY_DIFFERENT=NOT_EVALUATED_LIVE
REQUIREMENT_COVERAGE_USEFUL=NOT_EVALUATED_LIVE
TRACEABILITY_VALID=NOT_EVALUATED_LIVE
MAJOR_REQUIREMENTS_IGNORED=NOT_EVALUATED_LIVE
UNSUPPORTED_REQUIREMENTS_INVENTED=NOT_EVALUATED_LIVE
TRADE_OFFS_USEFUL=NOT_EVALUATED_LIVE
RISKS_USEFUL=NOT_EVALUATED_LIVE
OPEN_DECISIONS_USEFUL=NOT_EVALUATED_LIVE
MULTI_OPTION_QUALITY=BLOCKED_NOT_CONFIGURED
```

The existing deterministic structural tests remain PASS but are not substituted
for these quality judgments.

## Live Delivery Plan Test

`BLOCKED_NOT_CONFIGURED`. No live solution could be committed, therefore no honest
live Delivery Plan could be generated from an exact live solution revision.

## Solution/Plan Consistency

`NOT_EVALUATED_LIVE`. Consistency cannot be inferred from deterministic fake output.

## Traceability Sample

```text
TRACE_SAMPLE_VALID=NOT_OBSERVED
TRACE_SAMPLE_PARTIAL=NOT_OBSERVED
TRACE_SAMPLE_INVALID=NOT_OBSERVED
TRACE_SAMPLE_MISSING=NOT_OBSERVED
```

No numerical percentage was invented.

## Human Control Verification

Structural browser/API controls remain covered by regression tests. The required
human actions were not performed against live-generated artifacts, so Phase 2.1
human-control acceptance remains `BLOCKED_NOT_CONFIGURED` rather than being
promoted from structural evidence.

## Gate 2 Live Verification

```text
REQUIREMENT_BASELINE_REFERENCE=CONFIRMED_IN_FAILURE_SCENARIO
SOLUTION_REVISION_REFERENCE=NOT_AVAILABLE
DELIVERY_PLAN_REVISION_REFERENCE=NOT_AVAILABLE
DELIVERY_BASELINE_STATUS=NONE
LIVE_GATE2_FREEZE=NOT_RUN
```

The pre-existing Requirement Baseline remained `FROZEN`; failed AI generation did
not corrupt it or create solution, plan or Delivery Baseline authority.

## Latency

Provider latency was not observed because no authenticated provider request was
made. Local failure-path latency is not reported as model latency.

## Token Usage

No provider usage object exists. Input, cached input, output and total tokens are
recorded as `NOT_OBSERVED`, not estimated from text length.

## Cost

No API call was made, so observed provider cost is `USD 0.00`. This is not a model
cost evaluation. Once configured, calculate from actual Responses usage:

```text
INPUT_COST=(input_tokens-cached_input_tokens) * 5.00 / 1_000_000
CACHED_INPUT_COST=cached_input_tokens * 0.50 / 1_000_000
OUTPUT_COST=output_tokens * 30.00 / 1_000_000
TOTAL_RUN_COST=INPUT_COST+CACHED_INPUT_COST+OUTPUT_COST
```

## Prompt Evaluation

Static authority/security policy is concise and separate from dynamic untrusted
baseline/solution data. Output shape is supplied through Structured Outputs rather
than duplicated in prose. This matches current OpenAI guidance. Real-result prompt
tuning was not attempted without evidence.

The static developer prompt is stable enough for automatic prompt caching. If
repeated production traffic justifies explicit grouping, use a stable
`prompt_cache_key` per task contract and track
`usage.input_tokens_details.cached_tokens`; do not add caching complexity yet.

Failure-path verification showed one initial attempt, zero automatic repair
retries, explicit failure and zero authoritative mutation. Retry count is bounded
below the required maximum of one. A schema-repair retry should only be evaluated
after an actual recoverable live invalid-output case; it is not fabricated here.

## Known AI Quality Limitations

- Live option diversity, grounding and risk quality are unknown.
- Live solution/plan consistency and actionability are unknown.
- The adapter does not yet persist provider usage/latency telemetry; acceptance
  execution must capture the actual Responses `usage` object before cost review.
- No live evidence exists to compare `low` versus `medium` reasoning effort.

## Recommended Model Configuration

```text
DEFAULT_MODEL=gpt-5.5_PROVISIONAL
DEFAULT_REASONING_EFFORT=medium_PROVISIONAL
```

This preserves the accepted configurable model and official balanced default. It
is not a Phase 3 recommendation until live quality, latency and cost are observed.
No multi-model routing is implemented.

## Acceptance Decision

```text
PHASE1_REGRESSION=PASS
PHASE2_STRUCTURAL_REGRESSION=PASS
AUTOMATED_TESTS=31_PASS
SECRET_SCAN=PASS
FAILURE_PATH_NO_CORRUPTION=PASS

LIVE_AI_ACCEPTANCE=BLOCKED_NOT_CONFIGURED
PHASE_2_ACCEPTANCE=READY_WITH_OPERATIONAL_BLOCKER
GATE_2_OPERATIONAL=YES_STRUCTURAL
PHASE_3_READY=NO

FINAL_TAG=none
REMOTE_PUSH=SKIPPED
```

Required next action: configure `OPENAI_API_KEY` in the server process without
committing it, then rerun this Phase 2.1 acceptance from the canonical live project.
