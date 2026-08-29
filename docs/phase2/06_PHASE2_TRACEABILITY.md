# Phase 2 Traceability

```text
Requirement Baseline
  └─ exact requirement revision members
       └─ solution revision coverage → solution component refs
            └─ delivery plan revision items
                 ├─ exact requirement revision IDs
                 ├─ exact solution component refs
                 ├─ milestone membership
                 └─ dependency edges

Delivery Baseline
  ├─ exact Requirement Baseline ID
  ├─ exact solution revision ID
  └─ exact delivery plan revision ID
```

AI runs record provider/model/prompt version, requesting human, exact source
versions, status, failure and findings. Candidate rows retain original AI JSON;
append-only revisions identify AI or human editor. Commits, selection, merge,
rejection, regeneration, manual plan changes and baseline authority produce audit
events. Idempotency records prevent duplicate owner actions and commit/freeze paths
perform read-after-write reconciliation.

Staleness is derived by comparing exact IDs, not timestamps or a writable flag.
Frozen Gate 2 membership never follows current working pointers, so later solution
or plan revisions cannot rewrite historical authority.
