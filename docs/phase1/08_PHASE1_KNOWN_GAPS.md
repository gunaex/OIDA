# Phase 1 Known Gaps

- Live AI acceptance requires an explicitly configured provider credential and was
  not run when credentials were absent. Deterministic adapter evidence is labeled.
- Only pasted/direct text context is ingested; PDF/DOCX parsing is not claimed.
- Local identity is not enterprise IAM. Account Again replacement, password reset,
  invitation, role management UI, CSRF token defense, rate limits, and production
  session-store hardening precede public deployment.
- Secure cookies require `OIDA_COOKIE_SECURE=true` behind HTTPS; the example defaults
  to local HTTP.
- Context packets are assembled in full; chunk selection and retrieval are deferred
  until real input size justifies them.
- No bulk candidate actions or compare alternatives. Individual control proves the
  product contract without extra approval machinery.
- SQLite is correct for local Phase 1 but production concurrency/backup/operations
  need a later persistence decision.
- Browser automation was not added; API Golden Flow and real browser workspace are
  present, while visual/manual browser acceptance remains a release activity.
- Quantitative time-saved and AI-quality targets remain a pilot decision.

These gaps do not weaken project isolation, human-only Gate 1, exact baseline
membership, audit, or no-fake-success behavior.

