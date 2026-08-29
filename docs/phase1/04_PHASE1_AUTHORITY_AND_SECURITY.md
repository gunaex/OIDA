# Phase 1 Authority and Security

Local authentication verifies a PBKDF2 password and issues an HMAC-signed,
HTTP-only, SameSite=Strict session cookie. Secure-cookie mode is configurable and
must be enabled behind HTTPS. The server resolves actor identity for every protected
route; missing/invalid context fails 401.

Project access requires an exact `(project_id,user_id)` membership. Absence returns
404 to avoid resource disclosure. Gate 1 additionally requires PROJECT_OWNER and a
HUMAN actor. AI and SYSTEM actors cannot freeze. Project IDs from browser state are
never trusted without these checks.

AI context assembly and every query use direct project scope. No fallback project,
slug inference, global data set, provider key in the browser, or frontend-only
permission exists. Denials are structured-logged; known-actor project/authority
denials are stored as audit evidence.

Deterministic code—not AI—enforces state transitions, required fields, stale
blocking, membership, baseline membership, idempotency, and reconciliation.

