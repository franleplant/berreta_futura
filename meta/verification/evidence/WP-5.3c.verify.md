# WP-5.3c verify

**Verdict: ACCEPTED.**

Verified at art_directed tip `01a7ac6`, fresh detached worktree, own
`CARGO_TARGET_DIR`. No code changed.

## Replayed commands

| command | exit | observed |
| --- | --- | --- |
| `cargo fmt --check` | 0 | |
| `cargo clippy -q --all-targets -- -D warnings` | 0 | no output |
| `uv run python tools/nocomments.py` | 0 | `no comments` |
| `cargo test` (debug, gate unset) | 0 | 27 binaries, 392 passed, 0 failed (the tip has more tests than the 347 the evidence cites at `917aff1`) |
| `cargo test --test critic_faults both_critics -- --nocapture`, gate unset | 0 | `MODE: skipped, MAG_CRITIC_FAULTS_RENDER_DIR unset` |
| full mode, `--release`, gate on `editions/010/render-2026-09-14T01-49-02/en` | 0 | `MODE: full`, 21 passed, 129.34 s |

Full mode per variant, Python / Rust issue counts: resaved 4/4 pass,
swapped-sheets 7/7 fail, half-swaps 5/5 fail, missing-tail-band 5/5 pass,
low-ppi-figure 4/4 pass, text-fields 16/16 fail, raster-halves 6/6 fail.
The evidence says 4, 7, 5, 5, 4, 16 and 6: they match. 42 PROBE lines, and an
awk comparison of the python and rust values on every line found 0
mismatches. The baseline rows in the test (whitespace-void p17,
article-stub-last-page p29, tail-art-dropped, article-page-cap) match the
shipped `render-critic.json`, which I read.

## My mutation (not among the worker's four)

The worker's probes each broke ONE engine, so they were all caught by the
cross-engine comparison. I broke BOTH engines the same way, to check that
the rule-authored expectation catches a defect the two critics agree on
(brief rule 4):
`TAIL_GAP_MIN_LIVE_FRACTION` 0.35 -> 0.45 in both `mag/src/critic/rules.rs`
and `src/magazine/render_critic.py`. The threshold becomes 252.7 pt, above
the roughly 238 pt void that missing-tail-band creates.

Predicted: both critics drop `article-tail-gap` p44, agree with each other,
and only the expectation check fails. Observed: exit 101, missing-tail-band
went to 4/4 issues, and there was no "critics disagree" failure. The single
failure was `missing-tail-band: decided [...] the rule wants [...
("article-tail-gap", "review", Some(44)) ...]`. Every other variant was
unchanged. Both lines were restored with a reverse sed, and `git status` was
clean afterwards.

## Evidence claims checked

- Only `mag/tests/critic_faults.rs` plus the evidence were added (57e192f):
  within Owns.
- The skipped and full modes print their mode: confirmed.
- The declared gaps in half-swaps (`missed` ORDER[0] and ORDER[2],
  `spurious` ORDER[1]) are in the test as the evidence describes, and the
  full run passes with them. If a critic started deciding by position, the
  run would fail. I did not independently re-render the mirrored sides.
- The plan's Verify clause ("both critics emit the same issue codes" on a
  swapped spread, a missing tail band and a low-ppi figure) is met. The
  low-ppi figure yields no code on either side, because no render-critic
  site reads resolution (finding 3). That is honest, but in the render
  critic the plan's third fault is a silence check, not a detection check.

## Notes, not defects

- low-ppi-figure has no field probes, so the test itself does not show that
  the downsample landed. The evidence rests that on an eye check.
- In plain `cargo test` the suite passes in skipped mode. Its protection
  depends on someone running the gated mode (about 131 s in release).
- On failure, the scratch tree `$TMPDIR/wp53c-faults-<pid>` is left behind,
  because `remove_dir_all` runs only after the assert.
- Findings 1 (paint-order defect in both critics), 2 (dead
  `cover-booklet-inside-not-blank`) and 4 (tracer refusals) are still for
  the orchestrator to act on. I did not re-derive them. The ungated
  imposition test that backs finding 2 passes.
