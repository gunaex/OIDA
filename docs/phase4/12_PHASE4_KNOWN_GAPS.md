# Phase 4 Known Gaps

- QA Again live is blocked. Its intake trusts `CONDUCTOR_MAIN`; OIDA has no authorized service identity or account binding. The adapter contract passes and no fake live claim is made.
- Automated/external result ingestion is contract-only until trusted service authentication, replay protection, and reconciliation exist.
- CUSTOMER evidence is modeled but intentionally absent from the canonical internal scenario.
- Inline evidence uses local OIDA storage URNs; production object-storage retention and malware scanning are deferred.
- Acceptance exceptions are implemented and policy-tested separately; the canonical acceptance used zero exceptions.
- QA repair telemetry before this closure retained only the successful repair response. Metrics now aggregate bounded repair calls, but the historical first-attempt token count cannot be reconstructed.
- The application is intentionally not a test lab, defect tracker, file browser, vector search system, graph database, or event-bus workflow engine.

These gaps do not weaken the deterministic Internal closed loop. They prevent claiming external QA integration as operational, so the phase result is `PASS_WITH_EXTERNAL_QA_INTEGRATION_GAP`.

