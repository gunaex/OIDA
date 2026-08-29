# Cloud Known Gaps

- No managed PostgreSQL or OIDA backend/frontend deployment was provisioned; doing so may create recurring cost and needs target/domain choices.
- No Cloudflare hostname/zone was selected.
- Remote persistence, two-device login, restart, rollback, and live DeepSeek were not observed.
- Login throttling is process-local; Cloudflare rate limiting is required for multi-instance aggregate protection.
- Synchronous AI calls need deployed-path timeout observation; asynchronous job architecture is deferred unless evidence shows it is needed.
- Cloudflare Access, WAF rules, database backup/restore, and alerting remain deployment configuration work.
