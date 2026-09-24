# WP-3.8 template divergences the fixtures show and 010 cannot

## Base

`art_directed` `8ce85e5` (WP-3.3b), detached worktree `.../tmp/wp38`. The base
binary for the BEFORE legs was built from a second worktree at `8ce85e5`.

**Status: met for items 0, 2, 3 and 4 and for the plain opener without an
opener figure (item 1). Fixture 903 passes Tier S text with G max 0.021pt,
and so do fixtures 904 and 905's plain-opener pages. The plain opener WITH an
opener figure has its field, image trim and note suppression ported, but the
flow after that figure is not the oracle's (905 pages 6 and 7, a measured gap
below). 010: 56 = 56, typst reader.pdf byte-identical to the base binary's,
WP-2.1 projection equal, staged ratchet pass with 0 regressions.**

## 0. Baseline digest

`staged_input_digest` covers `src/magazine` and `uv.lock` (`parity.rs:374`).
`git diff --stat 0e20ab8^ 8ce85e5 -- src/magazine uv.lock` shows one file,
`src/magazine/web_edition.py` (1 line, WP-5.10). The digest was recomputed from
git blobs with the 010 request `editions/010/render-2026-09-24T01-58-11/request.json`
(57 inputs) and the digest rule of `parity.rs:391-427` (scratch `wp38-digest.py`):

| tree | digest |
|---|---|
| `0e20ab8^` | `1a570792e6db0e76fc7a4944be60d0355eafcb82d8054770f5dde987b3e872ae` (the old baseline) |
| `0e20ab8^` with only `web_edition.py` taken from `0e20ab8` | `ae9d6dafbdb5a5870fe5fbd3fa2a6122b242caeb7aaf7548b20cd84db0ba7d1f` |
| `0e20ab8`, `8ce85e5` | `ae9d6daf...` |

So the whole delta is that one file. `baseline.json` now holds old
`1a570792...` -> new `ae9d6daf...`. No page entry was touched.

## What changed

- **Closing plates (item 2).** The plates now follow `_place_closing_plates` and
  `_signature_closing_plates`. The count is the signature count from the content
  pages (`format.target_pages` honoured). The configured list is cut to that count,
  and too few plates are refused with the adapter's wording. Slot 0 goes after the
  LAST article. Plates that share a slot print in reverse order, because the
  adapter inserts each one at `index(after) + 1`. Only articles count as slots,
  not the editorial or sections. The old `piece-counter` counted those too, and
  the old code put the last slot after the sections. The content-page count needs
  a layout, and computing it inside typst would not converge (904 cycled through
  opener-state transients past five passes). So `template::paginate` compiles once
  with no plates, reads `pages - 2`, writes it into `#closing-signature(N)`,
  compiles again, and checks that `pages == content + 2 + plates` and that
  `pages % 4 == 0`.
- **Contents (item 3).** The row pitch is `393 / n` for every n. WeasyPrint
  ignores `max-height: 65.5pt` on the flex items, so four entries get 98.25pt rows.
  `CONTENTS-ROW-MAX` and `CONTENTS-ROWS-MIN` are gone.
- **Heading after an illustrated opener (item 4).** The first body heading after
  the opener's forced break gets `lead: true`, which sets its `above` as strong
  spacing inside the unbreakable heading block. Typst no longer drops it at the
  page top. The flag is not set when the standfirst was split, or when an opener
  figure or extract comes first.
- **Plain opener (item 1).** `Metrics::plain_opener` (estimate.rs) ports several
  adapter pieces:
  - `_fitted_display` over `serif-display`: 325pt measure, 165pt box, 35 or 30 to
    24pt, 4 lines.
  - `_opener_prose_field` for the field.
  - The has-figure branch: `59 + flow` against the code floor, plus the
    `270 - (floor - title_field)` image trim.
  - `_fit_credit_measure`'s byline compression: estimated width, tracking of
    `(column - width) / (n - 1)`, refused under 0.78.

  The emitter wraps the plain head in `#plain-opener(size, field, tracking,
  title)`. The template places each part:
  - The label is split into its 4 flex items with `h(1fr)` between them, each
    carrying its trailing 0.45pt letter-space, and the secondary moved 0.45pt.
  - The title's first baseline sits at `DATUM + 37 + size`.
  - The byline sits at `+ lines * 0.96 * size + 10`, where lines is the title as
    typst actually wraps it.
  - The note sits 12pt under the byline. This fixes the 2.69pt low note.
  - The field is a fixed-height block.
- **Found on the way and fixed, in owned files:**
  - `.standfirst + h1/h2/h3` margins of 31/28/23pt.
  - Inline code inside pinned text such as the standfirst or headings. It now
    shifts its line-box edges by the same paint lift as the parent's pinned
    edge, so it no longer grows the line by 1.689pt.
  - `document()` now prints a warning when typst reports non-convergence. The
    warning used to be dropped silently.

## Commands (exit status, key numbers)

```sh
uv run python ../wp38-digest.py editions/010/render-2026-09-24T01-58-11/request.json <tree> [swap]   # table above
M=../wp38-target/debug/mag   # fixtures copied into the worktree for rendering, moved out after
$M render 90N --engine weasyprint|typst --no-model --langs en; $M parity 90N --pre-rendered <W> <T>   # exit 1 (tiers) each
$M render 010 --engine typst --no-model --langs en --run editions/010/run-2026-09-13T01-34-51   # T04-19-12, 56 pages
shasum -a 256 .../T04-12-26/en/reader.pdf (base binary) .../T04-19-12/en/reader.pdf   # both 471998f3...
typeset_oracle.py stage + project (57 inputs, exit 0); cargo test --bin mag the_live_edition   # "68758 characters of reader text", ok
$M parity 010 --run editions/010/run-2026-09-13T01-34-51   # exit 1 (tiers), verdict output/parity/010/verdict.json
(cd mag && cargo fmt --check && cargo clippy --all-targets -- -D warnings && cargo test)   # exit 0; 31 binaries, 682 passed, 0 failed
python3 tools/nocomments.py   # "no comments"
```

## Metrics

| fixture | BEFORE (8ce85e5, WP-3.3b) | AFTER |
|---|---|---|
| 903 S text | fail, 5 pages | **pass** |
| 903 G | max dy 357.8, dx 323.3 | **max dx 0.021, dy 0.006, 0 beyond G2** |
| 903 S colour | fail, pages 4, 5 | fail, page 4 only (paint order, below) |
| 903 plates | pages 6,7 / 11,12 swapped vs oracle | same image on every page |
| 902 G | max dy 98.25 (page 3 contents) | **max dy 0.006, 0 beyond** |
| 904 (new: 2 illustrated, heading-first body, 8 plates, count 7, slot 0) | 15 vs 16 pages (typst printed 7 plates in the wrong slots) | **16 = 16, text pass, G 0.006, colour pass; plate colours page for page equal** |
| 905 (new: compressed byline, 2-line note, plain opener figure) | typst refused (byline assert, then 266.7 ppi) | 12 = 12; pages 4, 5 G within 0.1; pages 6-7 differ (gap) |

On 903, the new binary's label items land within 0.021pt. Title, byline and note
land within 0.002pt. The standfirst and everything after it land within 0.001pt.

**010, staged run** `render-2026-09-24T04-21-03`: staged inputs fresh
(`ae9d6daf...`, 57 edition inputs, 43 renderer files). Ratchet: pass, 54
committed entries checked, 54 measured, 0 regressions. S page_count 56 vs 56,
text pass, colour pass (58800), G max dy 0.006, V1 pass. Navigation shows 21
mismatches, the same count as the base. The typst leg is byte-identical to the
base binary's (`471998f3...`), and the typst tree differs only in where the plate
calls sit.

## Residuals and defects (owners)

- **Plain opener with an opener figure (mine, gap).** On 905 page 6, typst sets
  the standfirst below the figure at baseline 492.77. That is above the figure
  credit's 496.82. The oracle moves it to page 7. There are two causes. The typst
  figure has no `.band-clearance` after it (`_install_flow_clearances`; the
  template has none for any figure). And an opener figure's zero gap leaves the
  `move(dy: DATUM)` paint offset uncounted in the flow. Both are figure-flow items
  that apply to every figure, not only openers. **Owner: the figure-flow WP.**
- **Navigation, all fixtures and 010 (WP-3.7).** Every link differs in two ways.
  WeasyPrint writes `/BS <</W 0>>` where typst writes `/Border [0 0 0]` (WP-0.2t).
  The destinations differ too: WeasyPrint's `/XYZ` top is the piece's top
  (553.28 plain, 565.28 illustrated with the 12pt art lift). Typst writes 563.28
  for both, which is the mark minus 10pt, typst-pdf's own offset. The 903 contents
  rects now match within 0.01pt.
- **Paint order, 903 page 4 (WP-3.7).** The oracle paints the positioned source
  code and the transformed standfirst (a stacking context) after the in-flow
  text. Typst paints in tree order. The 905 opener page, which has no fills,
  passes colour.
- **010 typst layout does not converge.** At base `8ce85e5` too, with warnings
  `document did not converge within five attempts` and `<mag-tail> did not
  stabilize`. The output is byte-identical anyway. It is now printed, no longer
  silent. **Owner: tail art.**
- **Fixture 900** has 3 plates, and the signature needs at least 4, so a real
  typst render now refuses it, as the adapter does. Its plain article now spans
  3 pages instead of 2, because of the ported field. The oracle cannot render 900
  (its `sections/` input is not staged), so the new count is unverified.
  `the_fixture_pieces_measure_as_emitted` pins the unpaginated measure.

## Tests added

- `closing_plates_close_the_signature_in_the_adapter_s_slots_and_order`: with 2
  articles and 7 configured plates, 6 print on pages 4-6 and 8-10, and plate 1 is
  on page 10 (slot 0, reversed). With 9 articles and 7 plates, pages 4, 7, 9, 11,
  13, 16, 18. 9 articles with 6 plates is refused as "needs 7". Control: the
  unpaginated compile prints none.
- `a_plain_opener_pins_its_label_title_credit_and_standfirst_as_the_adapter_does`
  (903) checks each part against the stylesheet formula:
  - title baseline at `top + 47.0046 + 35`;
  - byline at `+ 35 * 1.96 + 10`;
  - note 12pt below the byline;
  - standfirst at `field + DATUM`, with the field recomputed from the symbol foot
    plus 40.7548;
  - standfirst lines 16.4pt apart with inline code;
  - Setup at 28pt plus the code descent of 0.7128pt;
  - label gaps equal and the date flush with the column.
- `a_byline_past_its_credit_column_is_tracked_in_as_the_adapter_does` (905): the
  tracked byline sits on one line inside 325.025pt. Control: with tracking 0 it
  wraps.
- `a_heading_that_opens_the_body_after_an_illustrated_opener_keeps_its_margin`
  (904): Notes at `top + 20.4 + DATUM`. Control: `lead: false` gives `top + DATUM`.
- `a_four_entry_contents_divides_its_band_into_four_rows` (903): titles
  98.25pt apart.

## What is and is not proven

- Proven: on 903 and 904, and on 905's plain-opener pages, both engines agree
  within 0.021pt. The tests pin the positions from the stylesheet and adapter
  formulas, not from a render. Each test has a positive control, apart from the
  contents one. On 010 nothing moved.
- Equality caveats (rule 4):
  - The contents pitch equals the oracle but contradicts the stylesheet's own
    comment. The comment wants rows capped at the six-row height; WeasyPrint does
    not honour `max-height` on flex items. Typst matches the rendered oracle, as
    the brief asks. If the cap was the intent, both engines are wrong for fewer
    than six entries.
  - The within-slot reverse plate order is an artifact of the adapter's insertion
    loop, matched deliberately.
  - Byline tracking comes from the unkerned width estimate, so a tracked byline
    ends about 3.6pt short of its column in both engines.
- Not proven:
  - the flow after a plain opener figure (gap above);
  - titles that step below 35pt on a plain opener (no fixture title reaches 5
    lines under the 62-character contents limit);
  - Spanish;
  - the editorial and section openers, which remain stubs.

## After the rebase onto `7bd2fcf` (WP-0.2j, comparator only)

`cargo test`: 31 binaries, 717 passed, 0 failed. The staged ratchet re-ran
(`render-2026-09-24T04-30-34`): inputs fresh `ae9d6daf...`, pass, 54 measured, 0
regressions. S text and colour pass, G max dy 0.006, V1 pass. The typst leg is
still `471998f3...`.
