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

Phase 0 and Phase 1 are accepted. Phase 2 implements the next thin vertical slice:
frozen Requirement Baseline → AI solution alternatives → human compare/edit/
reject/regenerate/select/merge → committed solution → AI delivery plan → human
editing → frozen Delivery Baseline (Gate 2) → Project Truth.

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
clearly labeled deterministic local/test adapter, or set `AI_PROVIDER=openai` with
an `OPENAI_API_KEY` for the optional live adapter. Provider keys stay server-side.

```bash
pytest
```

SQLite migrations run once at startup in filename order from `migrations/`. Local
data is stored under `data/` by default. Phase 2 needs no cloud service, vector
database, graph database, event bus, PM, QA, Infra, or Conductor runtime.

Phase 1 documentation starts at
[Phase 1 Scope](docs/phase1/00_PHASE1_SCOPE.md) and concludes with the
[Phase 1 Final Report](docs/phase1/09_PHASE1_FINAL_REPORT.md).

Phase 2 documentation starts at
[Phase 2 Scope](docs/phase2/00_PHASE2_SCOPE.md) and concludes with the
[Phase 2 Final Report](docs/phase2/10_PHASE2_FINAL_REPORT.md).
