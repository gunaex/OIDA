# Document Provenance

Each imported source stores OIDA project and context item IDs, Document Again project/document/revision identity, revision number, import actor/time, last check, state, and SHA-256 content fingerprint. The context item ID remains the source ID used by downstream AI requirement candidates.

Refresh compares current external revision and fingerprint. A change marks the source and binding STALE and warns the human. It never overwrites imported context or rebases frozen requirements automatically. Content is not copied to logs or integration metrics.
