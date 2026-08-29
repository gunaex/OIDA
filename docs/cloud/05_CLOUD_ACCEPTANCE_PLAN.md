# Cloud Acceptance Plan

Acceptance requires: full SQLite regression; critical PostgreSQL Gate 1–3 and integration flow; migration replay; production fail-closed tests; CORS/Origin CSRF; secure cookie/login/logout/rate limit audit; Docker build and health; HTTPS Worker/backend deployment; persistent data after backend restart; two-device login; live DeepSeek; external integration status; audit/provenance; rollback evidence; and secret scan.

Remote status is accepted only when every mandatory remote condition is observed against the deployed commit. Manual second-device checks are recorded with time/browser/device and no credentials.
