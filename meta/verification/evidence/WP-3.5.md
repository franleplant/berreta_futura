# WP-3.5 furniture and navigation

## Base

`art_directed` `2559eb1`, rebased onto `502f099` before landing (the new commits add only `#[ignore]` tests under `mag/src/parity`, plus package, critic and highlight code; after the rebase the staged parity run and `cargo test` were re-run with identical tier figures), detached worktree `.../tmp/wp35`, tracked content run
`editions/010/run-2026-09-13T01-34-51`, `--langs en`. WeasyPrint leg
`render-2026-09-24T00-26-40` (this base); typst BEFORE leg
`render-2026-09-24T00-27-52` (base binary); typst AFTER leg
`render-2026-09-24T00-42-08` (final binary).

**Status: page set `furniture` G2 0 pages beyond, before and after (target met).
Tier S navigation 4 mismatches -> 3, not green: the 3 left are not template
defects (below, with owners). Running-head paint order fixed: Tier S colour 30
pages -> 9, E display list 52 pages -> 43. Ratchet pass, 0 regressions; 56 = 56;
WP-2.1 projection byte-identical.**

## What changed

- **Furniture paints last** (`template.typ`). WeasyPrint puts the running head
  (`@top-center`) and folio (`@bottom-left`, `@bottom-right`) in page margin
  boxes. It paints those after the page's content, in that order. Typst had
  the furniture in `page.background` (painted first) and the folio before the
  running head. The furniture now goes in `page.foreground`, after
  `tail-layer()` (a tail is body flow in the oracle), running head then folio.
  `plain-page` and `plate-page` suppressed furniture with `background: none`;
  they now use `foreground: none` (they carry no tail).
- **A styled inline inside a link carries its own link, as in WeasyPrint.**
  `anchors.py` `gather_anchors` adds a link annotation for every non-text,
  non-line box whose inherited `link` is set, with that box's own hit area.
  So `<a><em>..</em></a>` gets one annotation for the `a` fragment and one for
  the `em` fragment on each line, in the order a, em. Typst gives one
  `FrameItem::Link` per shaped run, and a nested link replaces the outer
  destination instead of adding to it (measured: `a #strong[bold] b` gave 3
  rects, `#emph[..]` gave 1). Fix: inside `doc-link`, `emph`/`strong` link to
  the destination plus a ` mag-inline-link` marker. `template::pdf`
  then walks the frames before export (`weasyprint_links`): it merges
  contiguous same-destination runs on one line into the outer rect and
  re-emits each marked run as a second link with the clean destination, right
  after the outer rect for its line.

## Commands

```sh
unset TYPST_ROOT; RUN=editions/010/run-2026-09-13T01-34-51
./mag/target/debug/mag render 010 --engine weasyprint --no-model --langs en --run $RUN   # T00-26-40, exit 0
./mag/target/debug/mag render 010 --engine typst --no-model --langs en --run $RUN        # base: T00-27-52; final: T00-42-08, exit 0
./mag/target/debug/mag parity 010 --pre-rendered editions/010/render-2026-09-24T00-26-40 editions/010/render-2026-09-24T00-27-52  # exit 1 (tiers), BEFORE
./mag/target/debug/mag parity 010 --pre-rendered editions/010/render-2026-09-24T00-26-40 editions/010/render-2026-09-24T00-42-08  # exit 1 (tiers), AFTER
./mag/target/debug/mag parity 010 --run $RUN     # exit 1 (tiers); staged fresh 12c24234...; ratchet pass, 54 measured, 0 regressions
uv run python mag/tests/typeset_oracle.py stage --request editions/010/render-2026-09-24T00-42-08/request.json --into $ST/live --artifact-root .   # exit 0
uv run python mag/tests/typeset_oracle.py project --root $ST/live --edition 010 --publication-name "Berreta Futura" --out $ST/oracle-010.json    # exit 0
(cd mag && MAG_TYPESET_ROOT=$ST/live MAG_TYPESET_ORACLE=$ST/oracle-010.json MAG_TYPESET_PUBLICATION="Berreta Futura" \
  cargo test --bin mag the_live_edition -- --nocapture)   # "compared the live edition: 68758 characters of reader text", ok
uv run --with pikepdf python <scratch nav.py> <reader.pdf>          # catalog keys, outlines (both legs)
uv run python <scratch annots.py> 19,21,27 <weasy.pdf> <typst.pdf>  # normalized rects to 4 decimals + targets
pdftotext -f 27 -l 27 -bbox <each reader.pdf> -                     # word origins on the page-27 link line
(cd mag && cargo fmt --check && cargo clippy --all-targets -- -D warnings && cargo test)  # all exit 0; 576 passed, 0 failed, 31 binaries after the rebase
python3 tools/nocomments.py   # "no comments"
```

## Metrics: `mag parity 010`, before and after (same WeasyPrint leg)

| tier | before | after |
|---|---|---|
| ratchet | not_evaluated (pre-rendered) | **pass, 54 measured, 0 regressions** (staged, fresh digest) |
| S page_count | pass 56 vs 56 | pass 56 vs 56 |
| S boxes / text | pass / pass, 0 of 54 | pass / pass, 0 of 54 |
| G (page set `furniture` = every compared page) | max dx 0.003, max dy 0.220, beyond G2 0, structure 0 | identical |
| S color | fail, 30 pages | fail, **9** pages (4, 7, 11, 17, 31, 36, 40, 46, 50) |
| S navigation | fail, 4 (19: 11 vs 9; 21; 27; document title/lang/outlines) | fail, **3** (21; 27; document) |
| E glyph positions | 2881 shows, 40 violations, worst excess 325.789 | 1802 shows, 40 violations, worst excess 325.212 |
| E display list | 52 pages differ | **43** pages differ |
| V | V1/V2 fail, worst 0.281752 | unchanged |

Colour: the 21 pages that no longer differ all had their first difference at
paint 0, typst's running rule (224,227,230) against the oracle's first body
paint. The 9 left are the illustrated opener pages, first difference at paint
1: oracle PALE-VIOLET/SIGNAL-ORANGE fill against typst white fill then a
stroke (`fillstroke...`). That is the opener QR/credit block, not furniture.

## Residuals, with owners

- **Pages 21 and 27: glyph-advance drift, not link geometry.** The rects
  match in count, target, y and height. x differs by about 0.01 pt (21:
  283.4131 oracle vs 283.4239 typst; 27: 157.2498 vs 157.2539), which crosses
  the comparator's 0.01 quantum. Every typst word origin on those lines is the
  line start (48.0039) plus an exact multiple of 0.01 pt (the fonts have 1000
  units per em at 10 pt). The oracle's are not: "eminently" starts at 65.2235
  against 65.2239, and "(as" at 153.7313 against 153.7139. The link x
  inherits that per-glyph advance difference. It is the Tier E glyph-origin
  drift (WP-0.2o class T, WP-1.6), owned by WP-3.7, not by the template.
  Hypothesis, untested: WeasyPrint rounds each advance to 1/1024 pt (Pango
  units). What would kill it: summing `round(units * 10.24) / 1024` over the
  line prefix fails to reproduce 109.2459 on page 27.
- **"document title/lang/outlines differ": an oracle defect, not a typst one.**
  The oracle reader.pdf has no `/Lang`, no Info `/Title` and no `/Outlines`.
  Typst writes `/Lang (en)`, and typst-pdf 0.15.1 always writes a language
  (`metadata.rs:10`). WeasyPrint 69.0 does write all three: on
  `<html lang="en"><title>T</title><h1>` it gives `/Lang en`, `/Title T` and
  an outline. They are lost afterwards, because `cover.py`
  `replace_first_page`/the two-cover variant (lines 1428-1455) rebuild the
  PDF with pypdf `PdfWriter().add_page(...)`. That keeps the pages and named
  dests and drops the catalog `/Lang`, `/Outlines` and the Info `/Title`.
  Rule 4: `/Lang en` is correct for the English edition, so the typst leg
  keeps it and I did not strip it to match. **Orchestrator: fix the oracle's
  cover step to carry `/Lang` (and `/Title`, `/Outlines`) across, an
  oracle-side WP.** Once that lands the typst leg will need a document
  title (`html_edition.py:83` joins publication and title with U+2014, which
  repo rules forbid authoring in Rust or template copy) and
  whatever outline the oracle's bookmark CSS produces. Neither was measurable
  here.
- **Opener colour, 9 pages**: see above; opener/placement territory
  (WP-3.2 closed, so this needs an owner).

## Tests added

- `layout::the_running_furniture_paints_after_the_body_as_the_oracle_margin_boxes_do`:
  on every page carrying the 0.55 pt running rule, body text comes before it
  and only folio-baseline text comes after it. Positive control: with
  `template.typ` stashed back to the base, it fails (`52.0054 against
  575.7756`: body text after the rule).
- `layout::an_inline_inside_a_link_carries_its_own_link_as_weasyprint_does`:
  a plain link gives 1 rect. An `emph` filling the link gives 2 identical
  rects. `a *bold* b` gives the full outer rect plus the narrower inner one.
  A 20-word emph wrapping over three lines gives 6 rects in pairs
  (outer, inner) per line, top to bottom. Red before the change (1 vs 2).

## What is and is not proven

- Proven on 010 en: running head and folio now paint after the body and
  tails, in the oracle's margin-box order. Colour drops from 30 pages to 9,
  and none of the 9 differs at furniture. Page 19's four pacing-the-frontier
  annotations now equal the oracle's in count, order and rect (to 0.01).
  Pages 56 = 56, text and G2 unchanged, ratchet pass with 0 regressions on a
  fresh staged digest, WP-2.1 projection byte-identical.
- Proven: the oracle's missing `/Lang` comes from the pypdf cover rewrite, not
  from WeasyPrint (WeasyPrint 69.0 probe above, `cover.py` read).
- Not proven: links containing `inline-code`, whose WeasyPrint hit area
  includes the 3 pt horizontal padding and the code element's own line
  height. No 010 link contains one and the template adds no inner link for
  it, so such a link would read 1 annotation against the oracle's 2 per
  line. Also not proven: links inside other styled inlines beyond
  emph/strong, and Spanish.
- Not proven: the glyph-rounding cause of the page 21/27 drift (a hypothesis
  with a named kill test, above).
