# WP-5.4b-i verification: headline refusal fixture straddles its size boundary

Verifier replay at `0494017` (art_directed tip), in a fresh detached worktree.
WP landed at `25184fb`. No code was changed.

## Verdict

**ACCEPTED.** All three `## Commands` blocks were extracted programmatically
from the evidence file and replayed; all exit 0, every oracle number matches,
and all eight sweep rows reproduce the evidence's `failing` lists exactly.

## Replay

**Oracle (block 1), real Python compiler.** Matches the evidence line for
line: `...Is` fits at size 20.0 in 3 lines; `...As` and the inherited string
are refused with the `Cover headline cannot fit:` message; line counts at
21.0/20.5/20.0/19.5/19.0 are `[4,4,3,3,3]`, `[4,4,4,3,3]`, `[4,4,4,4,4]`, with
first three-line sizes 20.0, 19.5 and 10.5; third-line widths 307.869 /
300.36 / 292.851 and 314.675 / 307.0 / 299.325 against 302.0; `A` minus `I`
6.64 pt; `The Speed Limit` wraps to `THE SPEED` / `LIMIT` at 29.0. The
inherited wordmark and title slack (8 and 3 steps) that WP-5.4b-ii later
fixed also reproduce.

**Sweep (block 3), `svg.rs` restored by content equality and reported
identical to `36df6e8`:**

| perturbation | inherited (`a537a24` tests, `cover_modes` only) | tightened (whole suite, 25 binaries) |
|---|---|---|
| floor 20.0 -> 19.5 | 11 passed, none failing | `a_headline_that_cannot_fit_is_refused` |
| floor 20.0 -> 20.5 | 11 passed, none failing | `a_headline_of_three_lines_at_the_size_floor_still_fits` |
| limit `<= 3` -> `<= 4` | 10 passed, `a_headline_that_cannot_fit_is_refused` | both headline tests |
| limit `<= 3` -> `<= 2` | 11 passed, none failing | `a_headline_of_three_lines_at_the_size_floor_still_fits` |

Identical to both evidence tables, flip for flip. The tightened totals (257,
256 of 258) differ from the evidence's (153, 152 of 154 at `ba9c3ea`) only
because the tree has grown; nothing outside the two headline tests is
disturbed, now including `cover_pdf`. The `<= 4` panic at `svg.rs:537` was
reproduced independently in the WP-5.4b-ii replay.

**Gates (block 2) at this tip:** `cargo test` exit 0 (25 binaries, 258
passed), `cargo fmt --check` exit 0, `cargo clippy --all-targets -D warnings`
exit 0.

The "tightened" column now runs against WP-5.4b-ii's refactored
`cover_modes.rs`, not this WP's own version. The headline fixture strings and
assertions were read in the current file and match this WP's pair
(`HEADLINE_STEM` + ` Is` / ` As`).

## Findings (none blocking)

- The loose wordmark and title fixtures this WP measured and declined to fix
  were discharged by WP-5.4b-ii (accepted in `WP-5.4b-ii.verify.md`).
- The fitting headline test asserts acceptance, not the chosen size (20.0);
  the oracle reads the size off Python but no Rust test pins it. WP-5.4b-ii
  records the same gap for all four fitting tests.

## What is and is not proven

PROVEN here, independently: the headline size floor 20.0 and line limit 3 are
each pinned from both sides by a one-step pair, and the inherited fixture
detected only the loosening of the line limit. NOT PROVEN: the chosen size of
the fitting headline, and anything about `headline_layout` beyond those two
numbers.
