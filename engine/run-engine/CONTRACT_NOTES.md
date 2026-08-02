# RunEngine contract notes

The engine follows the public contracts without changing them. A few contract
edges need explicit interpretation:

- `allowedWorkerCapabilities` is treated as a required capability set. Machine
  offers use compound sets such as `text_model` plus `source_blind`, so treating
  the array as alternatives would bypass executor and exposure constraints.
- Source-aware and source-blind isolation is keyed by worker principal and
  `subjectArtifactId`. The contracts do not expose a broader subject lineage or
  equivalence key. Callers must use the same subject artifact for the two sides
  of an isolation boundary.
- `RunInputChange.replace_spec.value` accepts any JSON value. The engine rejects
  missing paths, then validates the complete successor specification before it
  creates the run.
- `RecordDecisionEffect.details` is retained in the durable decision row and
  exposed through `DecisionView.details`.
- The executor loop requires `answer` and `fail` to return `RunView`. The engine
  advances after an accepted claim and returns that view. `start`, `advance`, and
  `fork` retain the `RunOutcome` return type.

Late answers always create an immutable answer-envelope artifact, including
when the answer contains no output artifacts. A stale envelope is retained with
stale disposition and never enqueues a machine event.
