# Cloud Known Gaps

- P1: DeepSeek `deepseek-v4-pro` returned a network-successful response that failed OIDA's strict requirements schema with `AI_OUTPUT_INVALID`. Live AI is fail-closed, but no accepted candidate is available.
- P1: synchronous AI generation can exceed the Cloudflare edge request window; the public Worker returned HTTP 524 while the Fly backend later completed and recorded a failed AI run. Move long AI work to an asynchronous job/status contract before dogfood.
- P1: first-login forced password change is not implemented. The supplied eight-character temporary password also violates the production minimum of 14 characters, so the pilot retains a generated strong password in macOS Keychain for the requested email.
- P2: Document Again is reachable but lacks its API key/account/tenant configuration in OIDA, so binding/import/provenance acceptance was not run.
- P2: PM Again is reachable but lacks its API token in OIDA, so create/readback/idempotency/reconciliation acceptance was not run.
- P2: login throttling is process-local. The single pilot instance passes attempt limiting, but an aggregate Cloudflare rate limit is required before scaling to multiple backend instances.
- P2: Cloudflare Access, custom-domain routing, alerting, and an observed restore drill remain unconfigured. Workers.dev HTTPS and actual managed backups are operational.
- Physical remote-device testing remains manual pending; two independent HTTP session contexts passed.

There are no open P0 security, persistence, isolation, auth, or secret-exposure defects in the observed non-AI cloud path. The live-AI P1 defects keep the overall pilot at NO-GO.
