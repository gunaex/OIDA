# OIDA 2.0 State Model

States are separated by concern; a single universal status is prohibited.

## Canonical families

| Concern | States | Notes |
|---|---|---|
| Candidate | `DRAFT`, `READY_FOR_REVIEW`, `COMMITTED`, `REJECTED` | Commit creates/revises domain content; it is not approval. |
| Baseline | `DRAFT`, `ACTIVE`, `SUPERSEDED` | Activation is an authorized human command; active versions are immutable. |
| Execution | `NOT_STARTED`, `IN_PROGRESS`, `BLOCKED`, `COMPLETED`, `CANCELLED` | Owned by execution source. |
| Validation | `NOT_RUN`, `PASS`, `FAIL`, `PARTIAL`, `BLOCKED` | Evidence and waiver remain separate facts. |
| AI Run | `QUEUED`, `RUNNING`, `SUCCEEDED`, `FAILED`, `CANCELLED` | Review need belongs to candidate/finding, not runtime success. |
| Integration | `READY`, `DEGRADED`, `NOT_CONFIGURED`, `BLOCKED_AUTH`, `WAITING_EXTERNAL`, `ERROR` | Never collapsed into success/failure alone. |
| Acceptance | `PENDING`, `ACCEPTED`, `REJECTED`, `REWORK_REQUIRED` | Human authority only. |

## State rules

- A successful AI run says only that validated output was produced.
- `COMPLETED` work does not imply validation `PASS` or acceptance `ACCEPTED`.
- An active baseline cannot be edited; revision creates a new draft and later
  supersedes the previous version.
- Unknown/missing facts use explicit `UNCONFIRMED` data quality, not a lifecycle
  status invented per domain.
- Failure reasons use codes (timeout, grounding, policy, etc.) orthogonal to state.

