# WP-3.1 body text

## Base

`art_directed` `b7a1bb8`; detached worktree `.../tmp/wp31`, tracked content run
`editions/010/run-2026-09-13T01-34-51`, `--langs en`. `mag/src/parity/**` is
not touched; every tier number below comes from the committed comparator at
that base.

Result: the `body` page set (34 pages) now passes Tier S text and G2 on every
page, and so does the whole interior: text 0 of 54 pages differ (was 2), G
beyond G2 0 (was 95), max dy 0.220pt (was 7.182). 56 = 56 pages, WP-2.1
projection byte-identical, staged ratchet pass with 0 regressions and a verdict
written, WP-2.3 field table 134/134 equal (was 133/134). Tier S color still
fails on 27 body pages, and none of those failures come from body styling (see
below).

## What changed (`mag/assets/typeset/template.typ`)

- **Inline code** (`code`, `weasyprint-a5.css:946-954`). The template now sets:
  - the 3pt horizontal padding, as a U+00A0 in Geist Mono at 5pt (advance 0.6em,
    so exactly 3pt) on each side. NBSP is line-break class GL, which gives the
    CSS break behaviour: a break is allowed after a real space before the code,
    and never between the padding and the code or between the code and the
    padding. `h()` or `box()` would add a break opportunity (typst turns spacing
    into U+0020 and a box into U+FFFC);
  - the PALE-VIOLET chip, drawn with `highlight` (radius 2pt, extent 3pt). Its
    top is `0.855em + 1.2pt` and its bottom `0.145em + 1.2pt` from the
    baseline. That box is measured from the oracle on page 6, not derived:
    `mutool trace` rect height 14.1333px = 10.6pt = 8.2 + 2.4, top 8.2106pt
    above the 182.0072px baseline. It is one em centred on Geist Mono's
    `(A-D)/2` = 0.355em;
  - the inline line box. CSS gives the code span the parent's line-height
    (13pt), centred on the mono content area, so its bottom sits
    `6.5 - 0.355*8.2` = 3.589pt below the baseline, not the serif's 2.9954.
    The line grows by 0.5936pt, the "about 0.59pt" in WP-3.2.md. The code text
    gets `edges(size, L, HALF-MONO)`, with L read in context from the parent's
    `top-edge - bottom-edge` and the size `0.82 * text.size`, so the standfirst
    (13.2pt, 9.6pt) and the body (13pt, 10pt) both come out right.
- **List spacing**: `doc-list` `above: auto`, `below: 6pt` (3pt for
  references). CSS `ul { margin: 0 }` lets the last `li`'s 6pt `margin-bottom`
  collapse through the list, and a heading's margin collapses into the list
  unchanged. The old `above: PARAGRAPH-AFTER` was a weakness-3 spacing that
  added 5.4pt under a heading (page 29 footnote list), and `below: 5.4pt` put
  every paragraph after a list 0.60pt high (pages 20, 24 twice, 26, 28, 39).
- **End mark**: `block(above: auto)` inside `set par(spacing: 0pt)`, where it
  was `above: 0pt`. A weakness-3 `0pt` replaced the preceding paragraph's
  weakness-4 5.4pt `par.spacing` (`flow/distribute.rs`
  `keep_weak_rel_spacing`), which put every mark 5.40pt high. CSS collapses
  `margin-bottom: 5.4pt` with the mark's `margin-top: -20pt` to -14.6pt. A
  weakness-4 zero keeps the previous weak spacing, whatever it is, the way
  that collapse does.
- **List disc**: drawn as a `curve` with WeasyPrint's constant 0.55 (control
  offset 1.125pt on the 2.5pt radius; `circle` used typst's 0.5523, 1.12054pt),
  starting and turning as typst's circle did, `close(mode: "straight")`. The
  oracle clip path, read from `mutool trace` page 20: radius 3.3333px, control
  offset 1.8333px, ratio 0.55.
- **WP-1.2 line-break miss**: already resolved before this WP by
  `MEASURE-DELTA = 0.025pt` (WP-1.7, WP-2.2a). Block 135's first line reads
  `The Causal Encoder-Decoder handles the other half. The lower twenty` in both
  legs (`pdftotext -layout`: weasy line 1545 of T23-25-06, typst line 1530 of
  the base leg T23-26-19). Text tier: 0 pages differ.

Tests added (`layout.rs`); each fails on the base template (positive control
run: 19 vs 18.4 on the list gap, 0 NBSP pads found, disc controls 2.2411 vs
2.25):
- `body_blocks_collapse_their_margins_as_the_oracle_css_does`: paragraph to
  list 18.4, list to paragraph 19.0, heading to list equals heading to
  paragraph, end-mark baseline `13 - 10.0046 - 20 + 2.47375 + 28.53085` plus
  5.4 after a paragraph and plus 6 after a list.
- `inline_code_carries_the_oracle_padding_chip_and_line_box`: two 3pt pads,
  chip at text x - 3, width + 6, height 10.6, top `0.855*8.2 + 1.2`, next
  paragraph lower by the derived 0.5936pt.
- `the_list_disc_takes_the_oracle_bezier_constant`: 0.55, and it tells 0.55
  apart from 0.5523.

## Commands

```sh
unset TYPST_ROOT; RUN=editions/010/run-2026-09-13T01-34-51; M=../wp31s/target/debug/mag
$M parity 010 --run $RUN        # BEFORE (base b7a1bb8): exit 1 (tiers), ratchet pass 0 regressions; weasy T23-25-06, typst T23-26-19
$M render 010 --engine typst --langs en --run $RUN --no-model   # iteration legs T23-36-59, T23-39-22
$M parity 010 --pre-rendered editions/010/render-2026-09-23T23-25-06 editions/010/render-2026-09-23T23-39-22   # exit 1 (color/nav/E/V)
$M parity 010 --run $RUN        # AFTER, staged: exit 1 (tiers), ratchet pass, verdict output/parity/010/verdict.json; typst T23-41-57
python3 ../wp31s/body.py <verdict>          # body-set text / G2 / color rows (scratch)
python3 ../wp31s/endm.py <weasy.pdf> <typst.pdf>     # END mark tops (scratch)
python3 ../wp31s/colseq.py <weasy.pdf> <typst.pdf> <verdict>   # path fill sequence, furniture excluded (scratch)
(cd mag && MAG_LAYOUT_ORACLE=<T23-25-06>/en/edition-manifest.json MAG_LAYOUT_TYPST=<T23-41-57>/en/layout.json \
  cargo test --bin mag the_live_field_by_field_table -- --nocapture)   # exit 0, "cells: 134, equal: 134, differing: 0"
uv run python mag/tests/typeset_oracle.py stage --request <T23-41-57>/request.json --into $ST/live --artifact-root .
uv run python mag/tests/typeset_oracle.py project --root $ST/live --edition 010 --publication-name "Berreta Futura" --out $ST/oracle-010.json
(cd mag && MAG_TYPESET_ROOT=$ST/live MAG_TYPESET_ORACLE=$ST/oracle-010.json MAG_TYPESET_PUBLICATION="Berreta Futura" \
  cargo test --bin mag the_live_edition -- --nocapture)   # "compared the live edition: 68758 characters of reader text", ok
(cd mag && cargo fmt --check && cargo clippy --all-targets -- -D warnings && cargo test)   # all exit 0; 28 result lines, 463 passed, 0 failed
python3 tools/nocomments.py    # "no comments", exit 0
```

## Metrics: `mag parity 010`, before and after

Both runs are staged and use the same WeasyPrint leg (T23-25-06, cached) and
the same comparator. The staged digest `d92eca1d...` is fresh on both.

| tier | before (T23-26-19) | after (T23-41-57) |
|---|---|---|
| ratchet | pass, 54 measured, 0 regressions | **pass, 54 measured, 0 regressions** |
| S page_count | pass 56 vs 56 | pass 56 vs 56 |
| S boxes | pass | pass |
| S text | fail, 2 of 54 (4, 6) | **pass, 0 of 54** |
| G | max dy 7.182, beyond G1 10, beyond G2 95 | max dy **0.220**, beyond G1 **0**, beyond G2 **0** |
| S color | fail, 47 pages | fail, 47 pages (first difference unchanged, below) |
| S navigation | 6 mismatches | **4** (26, 39 now equal) |
| E glyph positions | 2910 glyphs, 52 shows, worst 37.99 | 3035 glyphs, 54 shows, worst 43.82 (below) |
| E display list | 1728 vs 1661, 52 pages; path-class diffs 214 | 1728 vs 1671, 52 pages; path-class diffs **170** |
| V | worst page fraction 0.2885 | 0.2818 |

**Page set `body`** (34 pages, from the verdict's `page_sets.body`):

| standard | before | after |
|---|---|---|
| Tier S text | 1 page differs (6) | **0** |
| G2 (0.5pt) | 5 pages beyond (6: 7.182, 20: 0.600, 24: 1.200, 26: 0.600, 28: 0.600) | **0** |
| Tier S color | 27 pages differ | 27 pages differ |
| path fill sequence without running furniture | 1 page differs (6: three PALE-VIOLET chips missing) | **0** |

Every one of the 27 body colour failures has its first difference at paint 0,
in running furniture. On 17 pages it is the running rule, (224,227,229) vs
(224,227,230): WP-0.0d's sanctioned oracle change. On the other 10, the oracle
paints body content first while typst paints the running rule first: the
running-head paint order carried by WP-3.5 (`page.foreground`). With the
running rule, the tick and the page white taken out of the sequence (scratch
`colseq.py`), every body page matches.

END marks (the WP-3.2 residual): the typst top minus the oracle top was -5.40pt
on 9, 16, 34, 44, 49, 53, -6.00 on 39, -7.18 on 6 and +4.80 on 29. It is now
0.000 to 0.002 on all nine.

## Re-measured after rebasing onto `aad29c1` (WP-0.2r comparator)

WP-0.2r landed while this WP was in flight and replaced the display list and
glyph clause (glyph-level, contract b), so the verify was re-run on it: a
fresh WeasyPrint leg T23-56-56, the after leg T23-58-06 (staged `--run`,
exit 1 on tiers), and the base template's leg T23-59-59 rendered by the same
binary with `template.typ` from `aad29c1` and compared `--pre-rendered`.

| tier | before (base template) | after |
|---|---|---|
| ratchet | (pre-rendered, not evaluated) | **pass, 54 measured, 0 regressions**, digest `d92eca1d...` fresh |
| S text | fail, 2 of 54 | **pass, 0 of 54** |
| G | max dy 7.182, beyond G1 10, beyond G2 95 | max dy **0.220**, beyond G1 **0**, beyond G2 **0** |
| S color | fail, 47 pages | fail, 47 pages |
| S navigation | 6 mismatches | **4** |
| E glyph positions | 58623 glyphs, worst 325.84 (page 40, an opener) | identical: 58623 glyphs, worst 325.84 (page 40) |
| E display list | 58850 vs 58794; differing classes text 10250, path 214, annotations 14 | 58850 vs 58798; text **1160**, path **170**, annotations **8** |
| V | worst 0.2885 | 0.2818 |

WP-2.3 table on the rebased legs: `cells: 134, equal: 134, differing: 0`.
`cargo fmt --check`, `cargo clippy --all-targets -D warnings` clean, `cargo
test` 29 result lines, 509 passed, 0 failed.

## What is and is not proven

- Proven on 010 en: Tier S text and G2 pass on every interior page. Inline
  code sits where the oracle puts it: glyph x within 0.02pt (`pdftotext
  -bbox`, page 6 `Mozilla/5.0` 176.3436 vs 176.3374, page 4 `rails` 272.0044
  vs 271.9896), and that residual is the serif shaping drift already present
  earlier on the same lines. Chip height and top match the oracle to 1e-4pt.
- Proven: the three new tests pin values derived from the CSS (margins,
  line-heights, the 0.55 constant), or measured once from the oracle (the chip
  box). They are not "equals typst": each fails on the base template.
- Not proven, known gap (Tier E display list only): a code span that breaks
  across lines. WeasyPrint slices the chip (`box-decoration-break: slice`):
  there is no padding and no rounding on the break side. `highlight` draws
  each fragment with extent and radius on both sides, so the page 6
  `Mozilla/5.0 (...)` fragments run 3pt past the text at the break (right end
  of line 1, left end of line 2). Text and glyph positions are unaffected.
  `highlight` also rounds with typst's 0.5523, not 0.55: 0.0046pt on a 2pt
  radius. Both would need a hand-drawn chip per line fragment, which is out of
  proportion for 1 of 3 spans in 010.
- Not proven: a code span glued to a preceding non-space character with no
  space between. NBSP forbids that break, and so does CSS, which is correct by
  rule, but no corpus case exercises it.
- The pre-rebase glyph clause's "worst" moved 37.99 -> 43.82. That was an
  artifact of the old show-by-index pairing (page 6 element 22 paired two
  different shows). On the WP-0.2r glyph-level clause both legs give the same
  worst, 325.84 on opener page 40, which this WP did not touch.
- Rule 4 note: the end-mark and list fixes reproduce CSS margin collapsing, and
  that is the intended design. The chip geometry copies WeasyPrint's
  font-size-em content box, which is also the shipped look.
