# Cloud Acceptance Results

Date: 2026-08-30

- Fly Managed Postgres `oida-2-pilot-pg` in `sin`: PASS. The production database has 62 public tables and all six migrations (`001_phase1` through `006_phase4_5_pilot_integrations`). Full and incremental backups are completed.
- Managed-PostgreSQL critical Gate 1–3/Phase 4.5 suite: PASS (`27 passed in 141.94s`) from an ephemeral Fly runner in the private network.
- SQLite full regression: PASS (79 tests). Python compile, JavaScript syntax, Docker build, and Worker build/dry-run also pass.
- Fly application `oida-2-pilot`: PASS. `/health`, `/ready`, Fly health checks, restart recovery, and data persistence pass.
- Cloudflare Worker and assets: PASS at `https://oida-pilot-web.gunaex.workers.dev`. HTTPS UI and same-origin API proxy pass.
- Authentication/session controls: PASS. Secure, HttpOnly, SameSite=Strict cookie; Origin denial; safe validation errors; throttling on attempt 9; and a temporary second-user read/write isolation test all pass.
- Independent-session write/read and post-restart readback: PASS. Physical second-device evidence remains `MANUAL_PENDING`.
- Live DeepSeek network/provider invocation: reached `deepseek-v4-pro`, but strict acceptance failed with `AI_OUTPUT_INVALID`. No candidate was materialized. The Worker request also returned Cloudflare 524 before the backend completed and recorded its failed run.
- Document Again and PM Again health endpoints return HTTP 200, but both OIDA adapters are `BLOCKED_NOT_CONFIGURED` because service credentials are absent.

Result: `CLOUD_PILOT_ACCEPTANCE=FAIL`. Cloud infrastructure and non-AI flows are operational, but live AI and the required remote cloud golden flow are not accepted.
