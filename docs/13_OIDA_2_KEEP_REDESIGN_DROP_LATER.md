# OIDA 2.0 Keep / Redesign / Drop / Later

## Evidence status

Historical recovery reviewed 30 meaningful OIDA 1.x sources at repository head
`f735fc1f05551838723edd3ee561a5c977556e32`. Thirty-two merged business intents
were classified below. This is intent recovery, not feature parity or migration.
The full source list, mappings, reasons, and actions are in
`19_OIDA_2_HISTORICAL_RECOVERY_ADDENDUM.md`.

| Classification | Count | Meaning in OIDA 2.0 |
|---|---:|---|
| ALREADY_COVERED | 10 | A current OIDA 2.0 requirement already expresses the historical need; no delta. |
| KEEP | 8 | A proven invariant remains essential; one missing security invariant was added and the rest were retained/clarified. |
| REDESIGN | 7 | The need remains, but OIDA 2.0 changes the interaction, ownership, or AI role. |
| DROP | 2 | Capability/registry-first product structure and miscellaneous module parity do not justify product scope. |
| LATER | 5 | Useful intent is outside the MVP/P1 proof or depends on later evidence. |

## Keep as product invariants

- Bounded authority and singular owner truth.
- Tenant/project access isolation and fail-closed identity.
- Immutable baselines and exact-version evidence.
- Provenance, freshness, and explicit empty/unbound/unknown/degraded states.
- Idempotent owner actions with read-after-write reconciliation.
- Action success, resolution, validation, and customer acceptance remain distinct.
- Audit/evidence integrity and flexible, explicit waivers.

## Redesign for AI-first delivery

- Replace module-first workspace navigation with “what the project needs next.”
- Replace manual-first requirement/document generation with grounded AI candidates.
- Collapse repeated artifact approvals into requirement and delivery baseline gates.
- Let policy-bounded AI execute reversible materialization instead of requiring a
  human click for every owner action.
- Keep infrastructure as delivery design/readiness/evidence, not an inventory
  universe or implicit production executor.
- Convert deterministic attention/advisory copilots into proactive grounded work
  preparation while preserving human authority.

## Deliberately drop

- Numerical parity with the 31-item capability registry or module/menu parity.
- Miscellaneous collaboration, quick-note, translation, PWA, and convenience UI as
  core Phase 0 requirements; they can compete later on demonstrated user value.

## Defer

Portfolio intelligence, persistent daily review/checkpoint experiences, advanced
change-impact automation, broad import/export packaging, and resource/commercial
optimization remain later work. P1 retains the narrow change-impact and attention
capabilities already defined by OIDA 2.0.

