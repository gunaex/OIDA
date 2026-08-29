# Phase 3 Reconciliation Model

Confirmation is `create request → target response → authoritative get → verify`.
A successful create response without readback is `UNCONFIRMED`, never success.
Safe retry reuses the semantic materialization key and first discovers the
existing target item; it does not blindly create another.

Reconciliation compares authorized expected title, description, owner role,
priority, milestone and dependencies with target-observed state. Runs record
confirmed, missing, mismatch, stale and unconfirmed counts. Any detected drift
makes the run `PARTIAL`; OIDA does not delete successful siblings or auto-fix
high-impact drift.

External projections use `last_verified_at`; the configurable default freshness
threshold is 900 seconds. Internal records are read from OIDA authority directly.
