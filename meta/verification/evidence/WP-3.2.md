# WP-3.2 headings, openers, TOC

## Base

`art_directed` `6ce2e1e`, rebased onto `917aff1` (WP-0.2n comparator) before landing and every parity figure below re-run on it; detached worktree `.../tmp/wp32`, tracked content run
`editions/010/run-2026-09-13T01-34-51`, `--langs en`.

**Status: opener-fit target met (9/9 equal to the oracle, all nine really fit);
page set `openers` improved from 9/9 pages failing Tier S text and G2 to 1/9
(page 4, an inline-code residual owned elsewhere, below). Color and display
list still differ on every compared page for structural reasons outside this
WP. Ratchet: pass, 0 regressions. 56 = 56 pages. WP-2.1 projection unchanged.**

## What changed

- **Opener fitting, the Python way** (`mag/src/typeset/estimate.rs`, new;
  `content.rs`). The oracle does not shrink an overlong standfirst: when even
  the compact density overflows, `_split_standfirst_overflow`
  (`weasyprint_adapter.py:2808`) keeps the words that fill the compact budget
  (`illustrated_opener_intro_budget`, `_standfirst_keep_words`) and moves the
  rest into an ordinary paragraph after the header. Both the budget and the
  word count come from the adapter's string estimator (`_wrap`,
  `_string_width` on hmtx advances, `_fitted_display` at the compact 30pt
  title), not from layout. `estimate.rs` ports that estimator over the same
  four faces (ttf-parser hmtx), and the emitter splits the first paragraph at
  that word count with the adapter's rule (cut inside text at a word start; an
  inline element that does not fit whole moves whole). The kept part is emitted
  `split: true`, which the template reads to force compact density as the
  adapter's `data-opener-density="compact"` does; the moved part is a plain
  `doc-paragraph`. Python probe on the staged 010 inputs: 7 of 9 illustrated
  openers split (91, 94, 95, 89, 91, 83, 89 words kept), dario and third-era do
  not; the typst tree splits the same seven, and the kept tails and moved heads
  match the oracle's page break text on all seven (pdftotext).
- **Opener geometry** (`template.typ`): the credit/QR grid picked up the
  document's 5.4pt `par.spacing` (PARAGRAPH-AFTER) below it, putting every
  standfirst 5.40pt low on all nine openers (measured against an oracle render
  with the drop cap disabled: 402.87 vs 397.47, 432.96 vs 427.56). The grid is
  now wrapped in a zero-spacing block; the standfirst then lands exactly.
- **Drop initial** (`template.typ`): the CSS
  `.standfirst::first-letter` (Serif Display 600, 18.7pt, PAPER-BLUE,
  line-height .7, margin-right 1pt) was not set. `initial()` sets the first
  letter (with any leading punctuation, as `::first-letter` does) in a box with
  a 1pt right inset and a top edge of 13.0992pt. That edge is MEASURED, not
  derived: the oracle's first line sits 3.13433pt (compact) and 2.32413pt
  (standard) below the no-drop-cap render, and strut top + offset gives
  13.0992pt at both densities (9.9648 + 3.1343, 10.7751 + 2.3241).
- **Plain opener end mark**: the emitter writes `#opener-end()` after a plain
  article header (template: `metadata(none)<mag-opener-end>`); `layout.rs`
  records its page, refuses a plain article without it, exposes
  `plain_opener_fits()` (end-mark page == head page) and warns when one spills.
  **`article_opener_fits` stays illustrated-only**, because that is the
  oracle's contract: the adapter fills it from `header.article-opener` boxes
  (`weasyprint_adapter.py:2317`) and `html_edition.py` gives that class only to
  the illustrated header (line 393; the plain header at 244 is a bare
  `<header>`). WP-2.3's "not proven" note expecting plain articles to show as
  differing typst-null cells was wrong: both sides omit them.
- **TOC links**: each contents row now carries the oracle's three link
  annotations to the piece: two zero-height rects across the folio width at the
  folio line (`.entry-folio` is `line-height: 0`, `top` 15.9pt tight / 17.7pt
  standard) and one over the title box (live width minus 47pt, 10.2pt tall).
- **Opener source links**: `source-link` now collects its destination inside an
  illustrated opener, and the QR cell carries two URI links over the 41pt box,
  as the oracle does.
- **`design_direction`**: orchestrator decision recorded: it is an engine
  identity label read by nothing and is excluded from the comparison as engine
  metadata, not a divergence. `the_live_field_by_field_table` drops it from the
  cells and prints it on an `excluded as engine metadata` line.

## Commands

```sh
unset TYPST_ROOT; RUN=editions/010/run-2026-09-13T01-34-51
./mag/target/debug/mag render 010 --engine weasyprint --no-model --langs en --run $RUN   # render-...T20-51-45, exit 0
./mag/target/debug/mag render 010 --engine typst --no-model --langs en --run $RUN        # base binary: T20-52-56 (BEFORE)
./mag/target/debug/mag parity 010 --pre-rendered <weasy> <typst-before>                  # exit 1 (tiers fail), figures below
./mag/target/debug/mag parity 010 --run $RUN                                             # final binary, staged: exit 1, ratchet pass
./mag/target/debug/mag parity 010 --run $RUN --set openers                               # exit 1, scored set below
(cd mag && MAG_LAYOUT_ORACLE=.../T20-51-45/en/edition-manifest.json \
  MAG_LAYOUT_TYPST=.../T21-23-18/en/layout.json cargo test --bin mag the_live_field_by_field_table -- --nocapture)  # exit 0
uv run python mag/tests/typeset_oracle.py stage --request <final request.json> --into $STAGE/live --artifact-root .
uv run python mag/tests/typeset_oracle.py project --root $STAGE/live --edition 010 --publication-name "Berreta Futura" --out $STAGE/oracle-010.json
(cd mag && MAG_TYPESET_ROOT=$STAGE/live MAG_TYPESET_ORACLE=$STAGE/oracle-010.json MAG_TYPESET_PUBLICATION="Berreta Futura" \
  cargo test --bin mag the_live_edition -- --nocapture)   # "compared the live edition: 68758 characters", ok
for pg in 4 7 11 17 31 36 40 46 50; do pdftotext -f $pg -l $pg -bbox <typst>/en/reader.pdf - | grep "<word" \
  | awk -F'"' '$4<569{print $8}' | sort -n | tail -1; done
DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib uv run python <probe>   # patches _standfirst_keep_words, runs _pin_opener_fields on the staged 010 HTML
(cd mag && cargo fmt --check && cargo clippy --all-targets -- -D warnings && cargo test)  # all exit 0
python3 tools/nocomments.py   # "no comments"
```

## Metrics: `mag parity 010`, before and after

Same WeasyPrint leg (`T20-51-45`). Before = base binary typst leg, compared
`--pre-rendered` (so the ratchet reads `not_evaluated`); after = the final
binary, staged `--run` (ratchet evaluated). The after figures are identical in
`--pre-rendered` mode against the same oracle leg.

| tier | before | after |
|---|---|---|
| ratchet | not_evaluated (pre-rendered) | **pass, 54 measured, 0 regressions**; staged digest fresh `d92eca1d...` |
| S page_count | pass 56 vs 56 | pass 56 vs 56 |
| S boxes | pass | pass |
| S text | fail, 30 of 54 pages differ | fail, **5** of 54 (4, 6, 42, 43, 44) |
| G | beyond G1 118, beyond G2 201, structure mismatches 141, max dy 367.872 | beyond G1 56, beyond G2 141, structure mismatches **9**, max dy 167.672 |
| G pages over 0.5 pt or with line-count mismatches | 38 | 18 |
| S color | fail, 47 pages | fail, 47 pages |
| S navigation | fail, 22 mismatches (count mismatches on 3, 4, 7, 11, 17, 31, 36, 40, 46, 50) | fail, 22 mismatches (counts now equal on all of those) |
| E glyph positions | 3295 glyphs, 62 shows, worst excess 88.97 pt, 40 violations | 2837 glyphs, 51 shows, worst excess 37.99 pt, 40 violations |
| E display list | 2189 vs 1629 elements, 52 pages | 2189 vs 1642 elements, 52 pages |
| V | V1/V2 fail, worst fraction 0.624 | unchanged |

**Page set `openers`** (4, 7, 11, 17, 31, 36, 40, 46, 50), from the verdict:

| clause | before | after |
|---|---|---|
| S text | 9/9 differ | 1/9 (page 4) |
| G2 (max dx/dy, line-count mismatches) | 9/9 fail: seven at dx 325-329 with 2 line mismatches, 17 and 36 at dy 11.88 | 1/9: page 4 dy 0.57; the other eight 0.22 or less, 0 mismatches |
| S navigation | 9/9 count mismatch (2 vs 0), contents 27 vs 0 | counts equal; geometry and targets equal (below) |
| S color, E display list | 9/9 | 9/9 |

**Opener fits (WP-2.3 table):** `article_opener_fits` 9/9 equal (was 4/9).
Cells 125 (design_direction excluded), equal 94, differing 31, all owned by
WP-3.4 (figure boxes/ppi, tail arts). Typst ink bottoms (poppler) on the nine
opener pages: 521.77, 519.37, 528.25, 446.71, 534.97, 477.91, 521.77, 526.33,
521.77 against the oracle's 522.34, 519.37, 528.25, 446.71, 534.97, 477.91,
521.77, 526.33, 521.77 (WP-2.3 evidence); all under 540.276. Only page 4
differs, by the 0.57pt inline-code line below.

## Residuals, with owners

- **Page 4 text and G2, pages 6's text/G drift: inline code.** The oracle's
  `code` has `padding: 1.2pt 3pt` and a background (`weasyprint-a5.css:946`),
  which makes pdftotext read `rails ,` and grows the line box by about 0.59pt;
  `inline-code` in the template has neither. Body styling, not opener: WP-3.1
  (or WP-3.3). Not touched here.
- **Navigation "mismatches" that are not.** After this WP the 22 remaining
  entries on opener and contents pages are all equal counts; a normalized
  comparison (rect corners sorted, half-point quantized, destination resolved
  to page) finds pages 3, 4, 7, 11, 17, 31, 36, 40, 46, 50 IDENTICAL. The
  comparator compares `/Rect` arrays raw: WeasyPrint writes
  `[x1 ytop x2 ybottom]`, Typst `[x1 ybottom x2 ytop]`, and PDF defines Rect as
  any two opposite corners. **Comparator defect for the orchestrator
  (`parity/display.rs` `page_annots`, which I did not touch):** normalize
  the corners before comparing, or every link on every page reads as a
  mismatch. Remaining real differences: body link pages 19, 21, 26, 27, 39
  (19 is 11 vs 9 annotations; 21 a one-half-point width), plus the document
  title/lang/outlines line: WP-3.5.
- **Headings anchoring a band figure** (page 12 `How we found the fourth`
  -20.40, 42 `The design that held` -20.40, 37 `FROM TAB TO AGENTS` -15.40):
  the oracle zeroes an anchor heading's `margin-top` when a band figure follows
  (`weasyprint-a5.css:1188-1195`) and repaints mid-page anchors
  (`band-anchor-midpage`). These are placement pages; WP-3.4.
- **`END / NN` marks 5.40pt off** on 9, 16, 34, 49, 53 and the -0.60 drift on
  20, 24, 26, 28, 39: end-mark spacing and body flow, WP-3.1 / WP-3.5.
- **Color and display list** differ on every text page. `color_sequence` is a
  paint-order list of text shows and paths; Typst paints the running furniture
  first and splits shows per line, WeasyPrint after and per paragraph line
  runs. Not opener-specific; WP-3.7.

## Tests added

- `estimate::the_standfirst_split_straddles_sixty_three_and_sixty_four_words`:
  63 `standfirst` words keep whole, 64 split at 63. The straddle is the Python
  estimator's, measured with `illustrated_opener_intro_budget` on the same
  title/byline/note (Python: fits at 63, splits at 64 keeping 63).
- `content::a_standfirst_splits_at_its_word_budget_and_moves_an_unfitting_inline_whole`:
  cut inside text, cut before an inline that does not fit, cut in a tail, and
  no cut at 0 or at the full count.
- `layout::the_plain_opener_fit_is_read_from_its_end_mark`: 10-word note fits,
  4000-word note spills.
- `layout::the_contents_and_the_opener_code_carry_their_links`: fixture 900's
  contents page carries 12 links (4 entries x 3); a synthetic illustrated
  opener with a source link carries two identical URI links; without it, none
  (positive and negative control).
- `layout::the_verdict_discriminates_each_rule` now also asserts
  `design_direction` produces no cell.

Suite (after the rebase onto `917aff1`): `cargo test` 336 passed, 0 failed, 25 binaries (summed from the `test
result` lines); fmt and clippy clean; nocomments clean.

## What is and is not proven

- Proven: on 010 en the typst leg splits the same seven standfirsts at the same
  word as the oracle, every opener fits (introspector and poppler agree), and
  `article_opener_fits` equals the oracle 9/9; the oracle's `true` is correct
  (poppler bottoms above, all under the content bottom).
- Proven: page count 56 = 56, the WP-2.1 live projection byte-identical
  (the split changes block boundaries only, which the projection normalizes to
  single spaces; the new calls carry no markup text), ratchet pass with 0
  regressions on a fresh staged digest.
- Proven: TOC and opener link annotations match the oracle in count, geometry
  (after corner normalization) and target page.
- Not proven: the split for an intro whose estimator wraps a word longer than
  the rail (the chunk path is ported but no corpus exercises it), a `[x](y)`
  literal in intro text (the adapter's `_MARKDOWN_LINK` substitution is not
  ported; HTML itertext never carries markdown links in practice), and Spanish.
- Not proven: the drop initial's 13.0992pt top edge is a measurement fitted on
  two densities, not a derivation from WeasyPrint's inline box model; it
  reproduces both densities to the poppler digit. A standfirst starting with
  punctuation or a non-text inline is handled by rule, not by a corpus case.
- Equality caveat (rule 4): the split reproduces the oracle's estimator
  exactly, including its choice to move text off the opener rather than fit
  it; that is the shipped design, and the typst side keeps it deliberately.
