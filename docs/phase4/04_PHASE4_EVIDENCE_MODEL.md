# Phase 4 Evidence Model

Evidence has explicit `TEST`, `INTERNAL`, or `CUSTOMER` classification and a concrete type such as report, log, screenshot, API response, record, or approval. It links relationally to project, validation item, exact result, execution item, and frozen requirement revisions.

Inline content receives a server-side storage URN, SHA-256 digest, and size. External references accept only safe credential-free HTTPS URLs or URNs; local file paths and unsafe schemes are rejected. Status history records valid, invalid, stale, and superseded transitions.

Gate 3 counts evidence only when it is valid, matches the active item, matches the exact current result, and satisfies every required type. A re-test therefore creates an evidence gap until fresh evidence is attached. CUSTOMER evidence is a real model but was not fabricated for the canonical internal scenario.

