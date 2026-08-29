# Cloud Rollback

Record the deployed image digest, Git commit, schema migration ledger, Worker deployment version, and PostgreSQL backup before release. Roll back Worker routing/assets first if edge behavior fails. Roll back the backend image only to a version compatible with the already-applied schema; accepted migrations are forward-only.

For data corruption, stop writes, preserve evidence, restore into a new PostgreSQL instance, validate membership hashes and audit continuity, then switch `DATABASE_URL`. Never point cloud traffic at a copied local SQLite file. Rotate exposed secrets immediately.
