# Integration Security

Bindings and imports require authenticated project membership; bind/import/refresh and task authorization require a human project owner. Queries are project-scoped and cross-project tests prove isolation. Provider secrets come only from environment variables and are omitted from responses, persistence, telemetry, and audit details.

Provider errors are bounded and classified. External content is treated as untrusted project data, not an instruction to OIDA. OIDA never writes to Document Again and does not bypass Account Again/Conductor service boundaries.
