# WP-3.7a Tier E burn-down, first slice (structure items)

## Base

`art_directed` `8afd7d0` (WP-3.8 queue), rebased onto `1b3107c` before the final
measurements (upstream moved the comparator: WP-0.2u, WP-0.2v). Detached worktree
`.../tmp/wp37a`, target `.../tmp/wp37a-target`. BEFORE legs come from a binary
built at `8afd7d0` in a second worktree (`.../tmp/wp37a-base`) and are re-scored
with the rebased comparator, so BEFORE and AFTER use one comparator.

**Status: all seven items met on 010. 010 E display list 45 differing pages ->
7, navigation 21 mismatches -> 2. The 7 pages left are all WeasyPrint
serialization drift (WP-3.7b's mechanisms), none is template geometry or order.
56 = 56, WP-2.1 projection equal, staged ratchet pass with 0 regressions,
fixtures 902-905 improve on every tier and regress on none. One fixture residual
(plain-opener QR bottom row) has no established cause (below).**

## What changed (owned files only)

1. **Links** (`template::pdf`). A lopdf pass over typst-pdf's bytes writes every
   link as the oracle does: `/BS <</W 0>>`, no `/Border`, no `/F` (the comparator
   masks `/F` with 2|4|32, so typst's `/F 4` was a mismatch). Internal link
   destinations are converted from `Location` to `Position` with typst-pdf's
   10 pt `pos_to_xyz` offset added back, and the illustrated piece mark is
   placed 12 pt up (`OPENER-MARK-LIFT`), so the XYZ top is the oracle's 553.28
   (plain) or 565.28 (illustrated) exactly.
2. **Outline** (`template::pdf`): every outline node's `/Count` is set to its
   descendant count (open), as WeasyPrint writes it; root 51 on 010.
3. **Paint order** (`template::pdf`, `weasyprint_paint_order`). WeasyPrint paints
   by CSS stacking: block backdrops, then in-flow inline content, then positioned
   and transformed boxes in tree order, each painted the same way inside. The
   template labels boxes `<mag-layer>` (figures and the figure rule, list items
   and their disc, headings (transform), end marks and their tick, the plain
   standfirst (transform), the plain opener's source code (absolute)) and
   `<mag-backdrop>` (`ruled`: code and quote fill and rule). The frame pass lifts
   layers after the page body and backdrops before it; links keep document
   order (WeasyPrint's `/Annots` order is tree order, measured on 010 p26).
   Furniture stays last.
4. **Inline code chip** (`weasyprint_chips`). A chip fragment with no code pad
   on a side is sliced there (no padding, square corners), as CSS
   `box-decoration-break: slice`; every chip arc uses WeasyPrint's handle
   (0.55 r, typst used 0.5523 r: the 0.0046 pt of WP-3.1.md).
5. **Tail convergence.** `tail-layer` read `<mag-tail>`, whose values come from
   end-mark positions, one hop too late for typst's five passes. It now reads a
   static `<mag-tail-art>` label and the end-mark position itself; `<mag-tail>`
   stays for `layout.rs`. 010 prints no convergence warning.
6. **Figure band clearance.** Every figure is followed by the adapter's
   `.band-clearance`: 4 reading lines, unbreakable, pulled back out of the flow.
   905 p6's standfirst now moves to p7 as in the oracle. The second cause WP-3.8
   named (the `move(dy: DATUM)` offset) is the oracle's own relative `top` too,
   so it needed nothing.
7. **010 walk, further attributable causes fixed:**
   - **Runt binds** (new `typeset/runt.rs`): the adapter's `_is_runt` /
     `_bind_last_two_words` ported. Measured on the unplated layout, bound with
     `\u{a0}` at the source span between the last two words, recompiled until no
     new bind (3 passes max, else refused). This was 12 of the 19 pages left on
     010 (words moving across lines), not glyph drift.
   - Images clipped to their boxes as WeasyPrint clips them (figure, tail,
     plate).
   - End-mark tick 2.47375 pt too high on all nine article ends (a WP-2.2a
     constant): now `28.53085 - 0.07625`, as the stylesheet's `top: -.07625pt`.
   - Code/quote fill 0.025 pt too wide (`outset: (right: -MEASURE-DELTA)`), and
     non-band/compact figures centred on 325 pt instead of the widened column.
   - Tail foot: typst writes 44.994995 (f32) for the oracle's 44.9950005, across
     the comparator's 0.01 rounding edge; the tail is lifted 0.0001 pt
     (`TAIL-FOOT-F32-LIFT`), a representation change below both writers'
     printed precision.

## Commands (exit status, key numbers)

```sh
M=../wp37a-target/debug/mag
$M parity 010 --run editions/010/run-2026-09-13T01-34-51            # exit 1 (tiers); staged fresh ae9d6daf... 57 inputs, 43 renderer files
#   ratchet: pass (54 committed entries checked, 54 recorded, 54 measured, 0 regressions)
#   S page_count 56 vs 56, boxes/text/color pass, G max dx 0.003 dy 0.006, V1 pass
#   navigation 2 mismatches (pages 21, 27); E display list 58850 vs 58850, 7 pages differ
#   E glyph positions 40 violations, worst 4.04 pt; no "did not settle" warning
$M parity 010 --pre-rendered editions/010/render-2026-09-24T04-35-52 editions/010/render-2026-09-24T04-37-25  # base leg, rebased comparator
#   navigation 21, E display 58850 vs 58834, 45 pages, glyph worst 314.43 pt; the base render printed "did not converge"
uv run python mag/tests/typeset_oracle.py stage --request editions/010/render-2026-09-24T06-22-56/request.json --into $ST/live --artifact-root .  # exit 0, 57 inputs
uv run python mag/tests/typeset_oracle.py project --root $ST/live --edition 010 --publication-name "Berreta Futura" --out $ST/oracle-010.json   # exit 0
(cd mag && MAG_TYPESET_ROOT=... MAG_TYPESET_ORACLE=... MAG_TYPESET_PUBLICATION="Berreta Futura" cargo test --bin mag the_live_edition)  # "68758 characters of reader text, 0 verbatim runs", ok
# fixtures: copied into the worktree, rendered on both engines, moved out again
$M render 90N --engine weasyprint|typst --no-model --langs en; $M parity 90N --pre-rendered W T   # exit 1 (tiers) each
(cd mag && cargo fmt --check && cargo clippy --all-targets -- -D warnings && cargo test)  # exit 0; 775 passed, 0 failed
```

The staged 010 typst leg is `render-2026-09-24T06-22-56` (reader.pdf
`bd3e9a06...`); it is no longer byte-identical to the base leg, by intent.

## Fixtures (rebased comparator, base `8afd7d0` leg vs this WP)

| fixture | S text | S color | navigation | E display list |
|---|---|---|---|---|
| 902 | pass / pass | pass / pass | 5 -> **0** | 15 pages -> **1** |
| 903 | pass / pass | fail 1 -> **pass** | 1 -> **0** | 12 -> **4** |
| 904 | pass / pass | pass / pass | 3 -> **0** | 12 -> **0 (pass)** |
| 905 | fail 2 -> **pass** | fail 2 -> **pass** | 1 -> **0** | 8 -> **2** |

905 G: max 326.3 pt, 6 pages beyond G2 -> max 0.021 pt, 0 beyond. 900 and 901 have
no oracle render (900's `sections/` is not staged, 901 needs a fourth plate), so
they are covered by the unit tests only.

## Residual ledger (every non-equal page)

010, staged run above. "Drift" = WP-3.7b's WeasyPrint serialization mechanisms
(integer `/W`, truncated TJ kerns, truncated `Tf`), where typst's value is the
exact one.

| page | display-list diff | cause | class |
|---|---|---|---|
| 3 | folio line starts of rows 11, 36, 50: y 367.40/236.40/105.40 vs 367.39/236.39/105.39 | every typst folio baseline is 0.00027 pt below the oracle's (454.72854 vs 454.72827); three rows straddle the 0.01 quantum. Same sign and size as WeasyPrint's truncated `Tf` at 23 pt (3.7b (d), predicts 0.0002 pt); not proven exactly | drift (serialization) |
| 4 | standfirst chip path: top 100.79 vs 100.78, right 296.60 vs 296.62 | top 100.78507 vs 100.78495 (0.00012 pt at the edge); right edge follows the serif text end (kern truncation) | drift |
| 6 | broken chip fragment right edge 353.45 vs 353.46 | fragment ends at its text end: "security" ends 353.4457 vs 353.4636 (kern truncation along the line) | drift |
| 8, 9 | running-head right item line start x 302.34/303.82 vs 302.33/303.81 | right-aligned Inter: integer `/W` widths | drift |
| 21, 27 | link rect x1 0.01 | link follows the kerned words (WP-3.5.md) | drift |

Glyph-position clause (not the display list): 40 violations, worst 4.04 pt at
"page 3 glyphs 24..33": the show pairs the FEATURE label glyphs with the folio
"0"; G max dx is 0.003 pt, so no glyph is placed 4 pt off. In-line advances are
WP-3.7b/3.7c's.

Fixtures:

| fixture page | diff | cause | class |
|---|---|---|---|
| 902 p4 | standfirst chip right edge 0.01 | text width (kern truncation) | drift |
| 903 p4, 905 p4, 905 p6, 903 p8/10/13 | opener label items x 0.01-0.02 | justified label items sized by Inter `/W` | drift |
| same pages | plain-opener QR modules: bottom row y 0.01 | typst's whole QR is 0.00036 pt below the oracle's (903 p8: 399.45469 vs 399.45433, 359.2651 vs 359.26473); only the bottom row crosses the edge | **cause not established** |
| 903 p4 | standfirst chip right edge 0.01 | text width | drift |

## What is and is not proven

- Proven by measurement: the counts above, BEFORE and AFTER on one comparator;
  the 12 line-break pages were runts, not drift (T lines had 5-40 pt to spare,
  and binding makes them equal); the tick, clip, tail foot, and order fixes are
  each visible as display-list equality on the pages they touched.
- Tests pin the CORRECT values, each with a control that fails without the fix:
  `links_and_bookmarks_are_written_as_weasyprint_writes_them` (903 553.275591,
  902 565.275591; unpatched export writes `/Border`; lift constant 0 fails),
  `an_inline_code_chip_broken_across_lines_is_sliced_as_weasyprint_slices_it`
  (typst's own handle 0.8954 fails), `a_page_paints_backdrops_first_and_positioned_boxes_after_its_flow_as_weasyprint_does`
  (unordered frame fails), `the_fixture_with_tail_art_settles_and_draws_the_end_tick_where_the_oracle_does`
  (base template gives 5.02375 pt tick-to-baseline, not 2.55),
  `every_body_image_is_clipped_to_its_own_box_as_weasyprint_clips_it`,
  `a_figure_carries_what_follows_to_the_next_page_when_four_lines_do_not_fit_under_it`
  (template without the clearance never carries), and
  `a_one_word_last_line_is_bound_to_its_neighbour_as_the_adapter_binds_it`
  (the bare compile sets "BMP." alone).
- The tail-convergence test does not have a firing control: fixture 900 converges
  on the base template too. The evidence for convergence is 010 (warning before,
  none after).
- The paint-order model is CSS Appendix E as WeasyPrint implements it, checked
  on 010 and 902-905. A layer split across a page keeps its continuation in the
  flow on the second page (only the first fragment is lifted); no page in the
  corpus exercises that.
- Runt binding ports the adapter's thresholds; the hyphen check uses
  "not English" for WeasyPrint's `hyphens: auto` and `-`/U+2010 for its
  hyphenate character. No Spanish edition was measured.
- Not done: the QR bottom-row offset (cause unknown, owner: next typeset WP);
  glyph drift (WP-3.7c).
