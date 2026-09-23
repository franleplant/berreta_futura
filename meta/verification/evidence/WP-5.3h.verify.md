# WP-5.3h verification

Verifier worktree at 4727939, own `CARGO_TARGET_DIR`,
`R=editions/010/render-2026-09-14T01-49-02/en` in the main checkout. No code
changed; the mutation was restored (`cmp` exit 0, `git status` clean).

## Verdict: ACCEPTED

## Replay

| command | exit | observed |
| --- | --- | --- |
| `cargo test` in `mag/` (gates unset) | 0 | 28 binaries, 445 passed, 0 failed (includes WP-5.7b, landed after this WP's 434) |
| `cargo fmt --check`, `cargo clippy -q --all-targets -- -D warnings` | 0, 0 | no output |
| WP-5.3b-iii block 3 (tracer dump) with this WP's rules.rs | 0 | reader 56, booklet 28, interior 26, cover 1 pages; sha256 e68b23f8... |
| same with `git show 7d652a3^:mag/src/critic/rules.rs` swapped in, then restored | 0 | sha256 e68b23f8...; `cmp old new` exit 0: position order equals paint order on the real 010 render |
| WP-5.3b-iii block 4 oracle script on the new dump | 0 | tracer and pypdf both `pass`, 4 issues; decision sets and geometry equal across the text swap; pypdf run reproduces shipped render-critic.json (issues, result, pages, crops all True) |
| `MAG_CRITIC_RENDER_DIR=$R MAG_CRITIC_RULES_ORACLE=... cargo test --release --test critic_rules` | 0 | 51 passed; `COMPARED: 4 issues, result pass`; 22 crops pixel for pixel; `TEXT SOURCE SWAP: ... rust equals tracer: true` |
| `MAG_CRITIC_FAULTS_RENDER_DIR=$R cargo test --release --test critic_faults` (the gated fault run) | 0 | 28 passed, 135.4 s |

Fault suite, Python / Rust issue counts: resaved 4/4, swapped-sheets 7/7,
half-swaps 5/6, missing-tail-band 5/5, low-ppi-figure 4/4, text-fields
16/16, raster-halves 6/6. All equal to the evidence.

## My mutation

Different from the worker's `|| true` probe: the unit conversion in
`spread_text` was dropped, `m[4] as f64 / 100.0` to `m[4] as f64`, so x is
compared in hundredths of a point against a middle in points. This is a
plausible real bug (nearly every show lands in the right half, which is
paint order again). Gated `cargo test --release --test critic_faults
rust_decides` exited 101: half-swaps fell to Rust 5 issues and panicked at
`critic_faults.rs:875`, "half-swaps: the critics disagree beyond the declared
python gaps". Restored, `cmp` exit 0.

## Observations

- Only the gated suite sees this behaviour. `grep -rn spread_text src tests`
  finds the function and its one caller and no test; an ungated `cargo test`
  would pass under either mutation. That matches how the other live-render
  rules are guarded here, so it is noted, not held against the WP.
- The Python critic still reads paint order. The suite pins that as a
  declared Python-only gap, so a Python fix or a Rust regression fails it.
- The evidence's NOT PROVEN items stand as written (a show crossing the fold,
  rotated imposition, English 010 only).

## What is and is not proven

Proven: every command in the evidence replays with the same numbers; the
change is a no-op on the real 010 render (byte-identical traced text); a
second, independent mutation of the partition fails the gated suite on the
half-swaps fault.

Not proven: anything beyond 010 English and the imposer's translation-only
halves.
