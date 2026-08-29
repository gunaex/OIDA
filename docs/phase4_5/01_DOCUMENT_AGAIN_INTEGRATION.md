# Document Again Integration

Document Again is read-only from OIDA. The adapter lists projects and artifacts, verifies an exact external project, reads the latest immutable revision, and imports only a human-selected document into existing Project Context.

States are `UNBOUND`, `INVALID`, `READY`, `PARTIAL`, `STALE`, and `ERROR`. A binding becomes READY only after external readback. Missing URL/token is `BLOCKED_NOT_CONFIGURED`, never a simulated live success. OIDA stores no provider credential in its database or audit log.
