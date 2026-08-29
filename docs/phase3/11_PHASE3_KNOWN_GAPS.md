# Phase 3 Known Gaps

- `PM_AGAIN_LIVE_INTEGRATION=BLOCKED`: the read-only local repository exposes
  human-session APIs but no configured service task-write runtime. The adapter
  boundary and mocked contract are tested; live ecosystem integration is not
  claimed.
- Browser behavior is syntax/runtime-smoke tested, not covered by a full browser
  automation suite.
- External capability-degradation decisions use authorization/audit and warnings;
  a richer per-field degradation policy UI is deferred.
- External freshness is implemented, but no live external target was available for
  operational freshness measurement.
- AI correction rate and time-saved measurement need repeated user studies beyond
  this canonical run.
- Production database, identity operations and secret management remain deployment
  concerns outside this local vertical slice.

QA execution, evidence, acceptance package and human Gate 3 belong to Phase 4 and
were intentionally not built.
