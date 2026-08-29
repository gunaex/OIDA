# Cloud Deployment Runbook

1. Provision managed PostgreSQL with TLS, backups, and a least-privilege application role.
2. Copy `fly.toml.example` to an untracked deployment configuration and select a unique app/region.
3. Set backend secrets: `DATABASE_URL`, `OIDA_ENV=pilot`, 48+ character `OIDA_SESSION_SECRET`, secure bootstrap identity/password, `OIDA_COOKIE_SECURE=true`, explicit `OIDA_ALLOWED_ORIGINS`, build commit, AI and integration credentials.
4. Deploy the Docker image; require `/ready` success and verify `/health` reports the expected commit and AI configured state.
5. Run `scripts/build_cloudflare_assets.sh`, copy `wrangler.toml.example` to an untracked config, set the HTTPS `API_ORIGIN`, then deploy with Wrangler.
6. Verify HTTPS, login, project persistence after restart, DeepSeek generation, integrations, audit, and two-browser access.

Do not use local SQLite, quick tunnels, default passwords, or a Pages-only deployment as cloud acceptance.
