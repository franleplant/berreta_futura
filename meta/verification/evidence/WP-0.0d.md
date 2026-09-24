# WP-0.0d rule colour to an 8-bit-exact value (sanctioned oracle change)

## Base

`art_directed` `e8945a5`, detached worktree `.../tmp/wp00d`, its own
`mag/target`, tracked run `editions/010/run-2026-09-13T01-34-51`, `--langs en`.

## Why

WP-0.2o class h and WP-3.1 (evidence files of those names): the oracle wrote
the COOL_GRAY rules as `0.88 0.89 0.9 rg`. 0.9 is 229.5/255, which an 8-bit
writer cannot hold; typst-pdf writes 230, and `pdftoppm -r 300` renders
(224,227,229) against (224,227,230). That first difference at paint 0 hid the
rest of the colour sequence on 17 pages.

## What changed

Every use of the token, found with `grep -rn "88%" src/ mag/assets` (exit 0,
four hits; the fifth hit, `weasyprint-a5.css:115`, is `1.88%` in a comment):

| file:line (after) | use | change |
|---|---|---|
| `src/magazine/assets/weasyprint-a5.css:302` | `.running-head-rule` background (running rule, 0.55pt) | `rgb(88% 89% 90%)` -> `rgb(88% 89% 90.19607843137255%)` |
| `src/magazine/assets/weasyprint-a5.css:347` | contents row rule (`li::after`, 0.7pt) | same |
| `src/magazine/assets/weasyprint-a5.css:218-226` | the colour-token comment | now says COOL_GRAY's blue is exactly 230/255 and why |
| `mag/assets/typeset/template.typ:15` | `COOL-GRAY` (used by the running rule, contents rule, `doc-rule`) | `rgb(88%, 89%, 90%)` -> `rgb(88%, 89%, 230)` |

Both uses in the stylesheet are rules. `screen-edition.css` has no use of the
token (same grep). `src/magazine/render.py:67` `COOL_GRAY = (0.88, 0.89, 0.90)`
belongs to the ReportLab renderer, not the WeasyPrint path. It is not owned
here and stays as it was. The percentage spelling keeps red and green exactly
as before (the comment's reason: a percentage reaches the PDF colour operator
unrounded).

The PDF operator, counted over the decompressed content streams of
`reader.pdf`: before `0.88 0.89 0.9 rg` x45, after `0.88 0.89 0.901961 rg` x45
(0.901961 * 255 = 230.00006).

## Commands

```sh
unset TYPST_ROOT; M=./mag/target/debug/mag; RUN=editions/010/run-2026-09-13T01-34-51
$M parity 010 --run $RUN   # BEFORE, exit 1 (tiers); oracle render-2026-09-24T00-09-41, typst render-2026-09-24T00-10-54
#   edit CSS + template
$M parity 010 --run $RUN   # exit 1: refused, run digest 12c24234..., baseline d92eca1d... (expected); oracle render-2026-09-24T00-14-43
#   rebase baseline.json staged_input_digest
$M parity 010 --run $RUN   # AFTER, exit 1 (tiers); "staged inputs: fresh (12c24234...)", ratchet pass, verdict output/parity/010/verdict.json; typst render-2026-09-24T00-16-07
pdftoppm -r 300 -png <before oracle>/en/reader.pdf ras/a/p; pdftoppm -r 300 -png <after oracle>/en/reader.pdf ras/b/p
uv run --no-project --with numpy --with pillow python rasdiff.py ras/a ras/b   # scratch script, exit 0
diff -r <before>/en/web <after>/en/web                                        # exit 0
diff <(pdftotext -raw before) <(pdftotext -raw after)                         # exit 0
diff pdfinfo -box -f 1 -l 56 (both)                                           # only "File size" differs (87139140 vs 87139291)
cmp edition-manifest.json (both)                                              # exit 0
diff render-critic.json (both)                                                # only booklet_sha256 and reader_sha256
cmp <typst before>/en/reader.pdf <typst after>/en/reader.pdf                  # exit 0; layout.json also cmp 0
(cd mag && cargo fmt --check && cargo clippy --all-targets -- -D warnings && cargo test)   # all exit 0; 29 result lines, 509 passed, 0 failed
```

## Oracle before/after (rasters at 300 dpi, all 56 pages)

- 38 pages change, 131732 pixels. On every changed pixel R and G are equal and
  B is exactly +1 (the script's `bad` list is empty).
- 37 running pages: rows 116-117 only (the rule centred on 28pt = 116.7px),
  2660 pixels each, x 183-1570 or 235-1564. Values (224,227,229)->(224,227,230)
  and, where the rule meets the tick or the antialiased edge,
  (237,139,119)->(237,139,120) and (235,237,238)->(235,237,239).
- Page 3 (contents): 24 rows in groups of three (665-667, 847-849, ...),
  33312 pixels: the contents row rules.
- Web tree: `en/web/` byte-identical (the web stylesheet does not use the
  token). Text, boxes, manifest unchanged; critic differs only in the two PDF
  hashes.
- The typst leg is byte-identical before and after: typst already quantized
  `90%` to 230, so the template constant only states that value explicitly.
  Page 6 pixel (800,116) is (224,227,230) in both typst legs.

## Baseline rebase (protocol of WP-0.2l.verify.md)

`meta/verification/baseline.json` `staged_input_digest`:
old `d92eca1df8acd98237c74be376884ca5bfa90c0e38ab4e37b63816feec5f412d`,
new `12c24234f8b033860b1b04a3ae66f6c67c0a298b625d1957b0df0411b9375f09`
(57 edition inputs, 43 renderer files), taken from the refusal line of a fresh
run on the final tree and confirmed "fresh" by the AFTER run. No other field
changed. (An earlier run with a mis-wrapped comment gave `924e23c3...`. The
comment was rewrapped before the digest was taken.)

## `mag parity 010` staged, before and after

| tier | before | after |
|---|---|---|
| staged inputs | fresh `d92eca1d...` | fresh `12c24234...` |
| ratchet | pass, 54 measured, 0 regressions | pass, 54 measured, 0 regressions |
| S page_count | pass 56 vs 56 | same |
| S boxes | pass (162, 54 rotations) | same |
| S text | pass, 0 of 54 | same |
| G | max dx 0.003, dy 0.220, beyond G1 0, G2 0 | same |
| **S color** | fail, 58800 entries, **47 pages** | fail, 58800 entries, **30 pages** |
| S navigation | 4 mismatches | same |
| E glyph positions | 58623 glyphs, worst 325.789032, 40 violations | same |
| E display list | 58850 vs 58798, 52 pages | same (page details now read rgb 230) |
| V | worst 0.281752 | same |

Colour pages fixed (17, none new): 3, 8, 13, 14, 15, 18, 19, 25, 32, 33, 38,
41, 43, 47, 48, 51, 52. Body page set: 27 -> 10 differing, the 10 that WP-3.1
attributes to running-head paint order (WP-3.5). No remaining colour detail
mentions 229.

## What is and is not proven

Proven on 010 en: the only raster change in the oracle is B+1 on rule pixels
(running rule rows 116-117, contents rules on page 3); the web tree, text,
boxes, manifest and critic verdict are unchanged; the typst leg is unchanged;
Tier S colour drops by exactly 17 pages with no new failures; the ratchet
passes at the rebased digest.

Not proven: other editions and `es` were not rendered. Rule 4: the rule is
now 0.5/255 bluer than `render.py`'s COOL_GRAY token and the ReportLab
renderer, a deliberate departure invisible in print. Both engines now agree
on 230, and 230 is the value both can actually write.
