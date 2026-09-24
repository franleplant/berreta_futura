# WP-3.11 the editorial opener on the typst leg

## Base

`art_directed` `d320995` (WP-5.11). Detached worktree `.../tmp/wp311`, own target dir.
Base binary for the non-regression runs: a second worktree at `d320995`
(`.../tmp/wp311-base-target`).

**Status: `mag parity --adhoc 008` exit 1 -> exit 0**, with every clause equal on
every page, p4 included: critic 0 leaves differ, glyph positions 0 violations,
display list 0 pages, G max dx 0.000 / dy 0.006. 010 staged exit 0 at target E.
Fixtures 902-906: typst reader.pdf byte-identical to the base binary's.

## What changed (owned files only)

The typst editorial was a stub: a 24 pt title in flow, a 12 pt block-spaced byline,
no field. WP-5.11 measured the result on 008 p4 (smaller headline, byline jammed
under it, a 354x160 pt trailing void). It now uses the plain opener the articles
use, with the three editorial differences the oracle has
(`weasyprint_adapter._pin_opener_fields` section branch, `weasyprint-a5.css`
`.editorial > header`):

1. **Title fit on the live width.** `Metrics::editorial_opener` fits on 333.0079 pt,
   box 135 pt, 35 pt down to 25 pt, at most 4 lines (`_EDITORIAL_TITLE_BOX`,
   `_EDITORIAL_TITLE_MAX`, `_LIVE_WIDTH_POINTS`). Articles fit on 325 pt, box 165 pt,
   24 pt minimum.
2. **Field clamped.** `max(72 + size * (1 + 0.96 * lines), 153.2756)`: the adapter's
   `height: _EDITORIAL_FIELD_BASE + _opener_title_flow` under the CSS
   `min-height: 153.2756pt` (render.py's `min(self.y, 390)`).
3. **Full live-width chrome.** `plain-opener(wide: true)` sets `escape: RAIL` in
   `plain-head`. Label, title and byline are placed `RAIL` left of the column and
   widened by `2 * RAIL`, which is the CSS `margin: 0 -4.004pt` on the editorial
   header. The byline-baseline measure wraps the title on the same width. Articles
   pass nothing and get `escape: 0pt`, so their arithmetic is unchanged.
   `content-label` also accepts a label with one run (the editorial has no
   secondary).

The standfirst (dek) and body already flowed as the oracle does (12/16.4, 6.2 pt
paragraph after). With the field in place they land at the right height.

## Tests added

- `an_editorial_title_is_fitted_on_the_live_width_over_a_clamped_field`
  (estimate.rs): the 008 title gives 35 pt and a field of 174.2. "Upkeep Scaled
  Quickly" gives 35 pt, one line, and the 153.2756 floor. Control: the same title
  on the 325 pt article measure takes 2 lines. An unfittable title is refused.
- `an_editorial_opener_spans_the_live_width_and_wraps_on_it` (template.rs): with
  `wide: true` the label, title and byline start one RAIL (4.00395) left of the
  standfirst, and the title sets on one line. Control, `wide: false`: the title
  starts at the standfirst's x, sets on two lines, and the byline drops by exactly
  one title leading (33.6). The standfirst's y is the same in both, so the field
  holds it.

## Commands (exit status, key numbers)

```sh
S=.../tmp; M=$S/wp311-target/debug/mag; B=$S/wp311-base-target/debug/mag
uv run python tools/sourcecodes.py 008       # exit 0, "print declines on 0"; NOT committed
$M parity --adhoc 008 --run editions/008/run-2026-08-30T13-59-32   # before the change: exit 1
#   critic fail (1695 leaves, 59 differ: p4 void, shifted crops, review_items 7 vs 8),
#   G max dx 4.004 dy 102.360 (24 beyond G2), glyphs 40 violations worst 216.84 pt,
#   display list 1 page, V1/V2 fail worst 0.110331   (log $S/wp311-p008-before.log)
$M parity --adhoc 008 --run editions/008/run-2026-08-30T13-59-32   # after: exit 0
#   critic pass (1676 leaves, 0 differ; Rust text fields 87 pages 0 differ; text_characters 0)
#   boxes, text, color, navigation pass; G max dx 0.000 dy 0.006, beyond G1 0
#   glyph positions pass (36794 glyphs, 0 violations); display list 36969 vs 36969, 0 pages
#   V1/V2 pass, worst 0.000336   (log $S/wp311-p008-after.log)
$M parity 010 --run editions/010/run-2026-09-13T01-34-51            # exit 0
#   staged inputs fresh bc49b2aa...; ratchet pass (target E, 56 checked, 0 regressions)
#   critic 0 differ, glyphs 0 violations (59073), display list 59304 vs 59304, V worst 0.000336
$S/wp311-fx.sh     # 902-906 from mag/tests/typeset_fixtures/corpus, base and new, all exit 0
#   reader.pdf sha256 base = new: 902 7272be38, 903 91a2d703, 904 3b8c3622, 905 25b4713c,
#   906 en 4427b8cd, 906 es a5594d73
(cd mag && cargo fmt --check && cargo clippy --all-targets -- -D warnings && cargo test)
#   exit 0 each; 32 result lines, 951 passed, 0 failed
python3 tools/nocomments.py                  # "no comments", exit 0
```

## A second editorial edition: none loads on the bridge

The observation run was tried on every other edition with an editorial, each
with locally generated source-codes. The oracle leg refuses all of them before
typst is compared:

| edition | exit | bridge refusal |
|---|---|---|
| 007 | 1 | needs 5 closing plates, configures 4 |
| 006 | 1 | needs 6 closing plates, configures 4 |
| 005 | 1 | needs 6 closing plates, configures 3 |
| 009 | 1 | closing plate 'The Listening Shell' repeats the art of 'The Shell at Low Tide' |
| 004 | 1 | pending anchors (pragmatic-leverage figures) |

001-003 have no edition.yaml in the tree. Skipped as the brief allows. 008 is
the only editorial the ladder can compare today.

## Housekeeping

- A first 010 run shared its output directory with a second one I started by
  mistake. One of them reported "typst leg produced 3 new render directories"
  and the other was refused by the run lock. I killed both, moved the stale render
  dirs and the lock to `$S/trash/wp311-010-stale`, and re-ran alone. The exit-0 run
  above is that clean run.
- `editions/00{4..9}/source-codes` were generated in the worktree only. They are
  not committed (edition data, outside the Owns line, as in WP-3.9).

## What is and is not proven

- PROVEN: on 008 the typst editorial opener equals the oracle on every tier,
  down to glyph positions. The WP-5.11 residual (p4, 59 critic leaves) is gone.
  010 and fixtures 902-906 carry no editorial, and their typst readers are
  byte-identical to the base binary's. The three editorial rules are pinned by
  tests with controls.
- Equality caveat (rule 4): the title is fitted on unkerned advance widths, as the
  adapter fits it. Typst then sets the kerned run, which can be narrower. So a
  title whose advance width is just over the box can take a smaller size or an
  extra line in the fit, while the set text would have fitted. Both engines share
  this. For "Upkeep Scales Quickly" (325.85 advance) typst sets one line on 325 pt,
  where the fit counts two.
- NOT PROVEN:
  - Any editorial but 008's (see the table above). That means no editorial with a
    title of 3 or 4 lines, a clamped field, or a two-page editorial.
  - A Spanish editorial on this leg. 008 was compared en only by `--adhoc`.
  - Section openers (`main > section`) still use the stub path. No edition in the
    tree has one.

## After the rebase onto `2680906` (WP-5.12, parity `--lang` and manifest)

`cargo test`: 32 result lines, 953 passed, 0 failed. `mag parity --adhoc 008`
exit 0: critic 1676 leaves, 0 differ; G max dx 0.000 dy 0.006; glyph positions
0 violations (36794); display list 36969 vs 36969. `mag parity 010` exit 0: ratchet
pass (target E, 56 checked, 0 regressions), critic 0 differ, glyph positions 0
violations (59073), display list 59304 vs 59304. `--adhoc 008 --lang es`
(new with WP-5.12) was not run.
