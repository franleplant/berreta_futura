# WP-5.4b-ii verification: wordmark and title fixtures straddle their floors

Verifier replay at `0494017` (art_directed tip), in a fresh detached worktree.
WP landed at `73ed7e0`. No code was changed.

## Verdict

**ACCEPTED.** All four `## Commands` blocks were extracted programmatically
from the evidence file and replayed; all exit 0, every oracle number matches,
and all 16 sweep rows reproduce the evidence's `failing` lists exactly.

## Replay

**Oracle (block 1), real Python compiler.** Every figure matches the evidence:
wordmark max width 320.527559; `...itiel` first fit 25.0, `...ities` 24.5,
inherited 21.0; tail legs at 25.0 of 319.7958 and 322.1437 against a head leg
of 84.0566 for both (so the tail leg binds, as claimed); `L`/`S` separation
2.3478 pt. Title `...Apostlel` 189.7280 and `...Apostles` 190.5200 at 12.0
against 190.0, first fits 12.0 and 11.5, inherited 10.5, separation 0.7920 pt.
Python accepts both fitting strings and refuses both refusing strings with the
exact messages `cover_modes.rs` asserts. The Rust test stems
(`Berreta Incomprehensibilitie`, `The Speed Limit And Its Apostle`) and the
asserted messages were read in the test file and match.

**Sweep (block 3), whole suite per row, `svg.rs` restored by content equality
and reported identical to `36df6e8` at the end.** At this tip the suite is 25
binaries: baseline 256 passed with the inherited fixtures, 258 with the
tightened ones (the difference is the two fitting tests this WP adds).

| perturbation | inherited: failing | tightened: failing |
|---|---|---|
| wordmark 25.0 -> 25.5 | none | `a_publication_wordmark_at_the_size_floor_still_fits` |
| wordmark 25.0 -> 24.5 | none | `a_publication_wordmark_that_cannot_fit_is_refused` |
| title 12.0 -> 12.5 | none | `a_title_of_one_line_at_the_size_floor_still_fits` |
| title 12.0 -> 11.5 | none | `a_title_that_cannot_fit_on_one_line_is_refused` |
| headline floor 20.0 -> 20.5 | `a_headline_of_three_lines...` | same |
| headline floor 20.0 -> 19.5 | `a_headline_that_cannot_fit_is_refused` | same |
| headline limit `<= 3` -> `<= 4` | both headline tests | same |
| headline limit `<= 3` -> `<= 2` | `a_headline_of_three_lines...` | same |

16 of 16 failing lists identical to the evidence; every row reports 25
binaries, so no row aborted early. The totals differ from the evidence's
(181/183 at `0978ebb`) only because the tree grew; the flips are the claim and
they hold. The four tightened floor rows each fail exactly one test and nothing
else suite-wide, including `cover_pdf`, which the evidence could not have
checked at its measurement commit.

**Panic (block 4).** Reproduced: under `<= 4` the fitting headline panics at
`tests/../src/cover/svg.rs:537:24`, `index out of bounds: the len is 3 but the
index is 3`; restored True.

**Gates (block 2) at this tip:** `cargo test` exit 0 (25 binaries, 258
passed), `cargo fmt --check` exit 0, `cargo clippy --all-targets -D warnings`
exit 0. `cover_modes` binary runs 14; the file holds 13 `#[test]`s plus the
`#[path]`-included `metrics::exif_tests` case, exactly the domain split the
evidence states.

## Findings (none blocking)

- The evidence's `## Verdicts` repeats its fmt/clippy/nocomments sentence
  twice (a paste duplicate). Cosmetic.
- Its NOT PROVEN items stand as written and are real: `Ok` pins acceptance,
  not the chosen size; the head leg of the wordmark guard is not pinned by a
  one-step pair; `footer_caption`'s call to `fit_display_line` is not pinned;
  WP-5.4c's numeric guards in `cover_pdf*` were not swept. Each has a recipe
  and an owner in the evidence.

## What is and is not proven

PROVEN here, independently: the wordmark floor 25.0 and title floor 12.0 are
each pinned from both sides by a one-step pair, and the inherited fixtures
could not detect either one-step move; the headline pins from WP-5.4b-i
survive the refactor. NOT PROVEN: the items listed under Findings.
