# OIDA 2.0

OIDA 2.0 is a clean AI-first product rebuild.

OIDA 1.x is historical reference and requirement source only. Its architecture,
code, APIs, schemas, UI, services, names, and implementation assumptions are not
inherited automatically.

The product is an **AI-first Project Delivery Operating System with
Human-Controlled Authority**. It gives a project one coherent workspace in which
AI prepares and performs the maximum useful delivery work while people retain
inspection, correction, override, commitment, and final authority.

## Current phase

Phases 0–2 are accepted. Phase 3 implements the next thin vertical slice: frozen
Delivery Baseline → AI materialization plan → human routing/exception review and
batch authorization → owner-target execution → read-after-write reconciliation →
Execution Truth and drift. Internal execution is the real core target; PM Again
remains an explicit adapter boundary and is not claimed live.

The Phase 0 definition begins at [Product Vision](docs/00_OIDA_2_PRODUCT_VISION.md),
continues through the [Phase 1 Recommendation](docs/17_OIDA_2_PHASE1_RECOMMENDATION.md),
and concludes with the [Phase 0 Final Report](docs/18_OIDA_2_PHASE0_FINAL_REPORT.md).
Historical evidence and the reconciled requirement delta are recorded in the
[Historical Recovery Addendum](docs/19_OIDA_2_HISTORICAL_RECOVERY_ADDENDUM.md).

## Run locally

Requires Python 3.9+.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload
```

Environment files are not loaded implicitly. Export the selected values from
`.env` in your shell or process manager. Open `http://127.0.0.1:8000` and sign in
with the configured bootstrap identity.

`AI_PROVIDER=disabled` is the honest default. Set `AI_PROVIDER=fake` only for the
clearly labeled deterministic local/test adapter. Live adapters are selected with
`AI_PROVIDER=openai` plus `OPENAI_API_KEY`, or with the following DeepSeek setup:

```bash
export AI_PROVIDER=deepseek
export AI_MODEL=deepseek-v4-pro
export AI_REASONING_EFFORT=high
export DEEPSEEK_API_KEY='set-in-your-secret-manager'
export DEEPSEEK_BASE_URL=https://api.deepseek.com
```

Provider keys stay server-side. An unknown `AI_PROVIDER` fails explicitly with
`AI_PROVIDER_INVALID`; it never falls back to the fake or another live provider.

```bash
pytest
```

SQLite migrations run once at startup in filename order from `migrations/`. Local
data is stored under `data/` by default. Phase 3 needs no vector database, graph
database, event bus, QA, Infra, or Conductor runtime. External execution projection
freshness defaults to 900 seconds and is configured with
`EXECUTION_FRESHNESS_SECONDS`.

Phase 1 documentation starts at
[Phase 1 Scope](docs/phase1/00_PHASE1_SCOPE.md) and concludes with the
[Phase 1 Final Report](docs/phase1/09_PHASE1_FINAL_REPORT.md).

Phase 2 documentation starts at
[Phase 2 Scope](docs/phase2/00_PHASE2_SCOPE.md). Structural closure is recorded in
the [Phase 2 Final Report](docs/phase2/10_PHASE2_FINAL_REPORT.md), and current live
provider status is in the
[DeepSeek Provider and Live Acceptance](docs/phase2/12_DEEPSEEK_PROVIDER_AND_LIVE_ACCEPTANCE.md),
with final Gate 2 evidence in the
[DeepSeek Live Closure Report](docs/phase2/13_PHASE2_DEEPSEEK_LIVE_CLOSURE_FINAL_REPORT.md).

Phase 3 documentation starts at [Phase 3 Scope](docs/phase3/00_PHASE3_SCOPE.md)
and concludes with the [Phase 3 Final Report](docs/phase3/12_PHASE3_FINAL_REPORT.md).
