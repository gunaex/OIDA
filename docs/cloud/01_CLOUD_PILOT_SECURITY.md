# Cloud Pilot Security

Pilot mode fails startup unless it has PostgreSQL, a session secret of at least 32 characters, a non-development bootstrap password, secure cookies, and an explicit origin allowlist. Sessions are signed, HttpOnly, SameSite=Strict, Secure cookies with 12-hour expiry. The browser sends credentials only same-origin through the Worker proxy.

State-changing requests require an Origin exactly in the allowlist (CSRF defense); CORS is credentialed and explicit, never `*`. Login failures are rate-limited in-process and both successful/failed login plus logout are audited without storing plaintext email on failure. Cloudflare WAF/rate limiting or Access is recommended as an outer layer; OIDA authorization remains mandatory.

Secrets are environment-only. TLS terminates at Cloudflare and origin HTTPS remains required. Backups, database encryption, provider rotation, security headers, and Access policy must be verified at deployment.
