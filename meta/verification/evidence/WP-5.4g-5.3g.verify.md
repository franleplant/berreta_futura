# WP-5.4g + WP-5.3g verify: ACCEPTED

Verifier (WP-4.1 gate), tip `fa3fe15`.

## Replay

The gate (WP-4.1.md) is the replay: domain "reader.pdf end to end: pages 1..n",
first 1, last 56. Critic clause pass: 1999 leaves compared, 1022 excluded, 0 differ,
Rust text fields on 111 pages 0 differ. Two clean runs, identical normalized verdicts.
WP-4.1 raised pages 1 and 56 from the seed rows to E. Since then `tests/parity_ratchet.rs`
runs its tier-lowering branch on page 1 ("MODE: full, ... exercising page 1 at tier E").

## Injected defects

- Data: the typst leg's `render-critic.json` `issues[0].severity` changed from review to
  error, in a copy of the gate's two render dirs. `mag parity 010 --pre-rendered A B`
  exit 1, "tier S critic: fail (... 1 differ ...)", while text, color and display list
  pass.
- Code: the exclusion match accepts any prefix (`parity/critic.rs:138`, `true`).
  `cargo test parity::critic` exit 101:
  `a_decision_leaf_or_a_one_sided_leaf_differs_and_a_prefix_is_not_a_match` FAILED.
  Restored.

## Not proven

The report comparison sets the Python critic against the Rust one, so an issue both
miss passes (as WP-5.4g-5.3g.md says).
