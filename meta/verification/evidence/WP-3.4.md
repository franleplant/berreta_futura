# WP-3.4 figures, plates, ornaments

## Base

`art_directed` `85d1d4c`, rebased onto `f5754b8` (carries WP-0.2o's comparator
change) before the final measurements; detached worktree `.../tmp/wp34`, tracked
content run `editions/010/run-2026-09-13T01-34-51`, `--langs en`.

**Status: NOT LANDED, blocked on a comparator defect.** The typst leg now
places rasters, and the committed comparator cannot trace any typst PDF that
carries one: `mag parity` exits 1 with
`error: tracing page 9 of .../reader.pdf: operator Do: decoding image: expected
name, got [/ICCBased 318 0 R]` and produces no verdict. Landing would break the
ratchet for every later WP. All numbers below marked *patched* were measured
with a scratch comparator binary carrying the 5-line fix quoted under
"Comparator defect"; the fix was never committed and `mag/src/parity/**` is
unchanged in this commit (`git diff f5754b8 -- mag/src/parity` is empty).

With that fix: page count 56 = 56, WP-2.1 projection byte-identical, staged
ratchet pass with 0 regressions, placement set Tier S same-page 11/11, figure
boxes equal to the oracle to the printed digit and `effective_ppi` equal on all
three figures, tail arts printed on the same 8 of 9 articles.

## What changed

- **Rasters reach typst** (`world.rs`): `World::file` reads a `.png`/`.jpg`/
  `.jpeg` path from disk; the emitter writes absolute paths
  (`content.rs::path_literal`) for figures, tail art and closing plates.
- **Figures** (`template.typ` `figure-image`, `figure-block`): the image is
  fitted as before (`min(width/px_w, max_height/px_h)`), centred in the block
  (`margin: 0 auto`, `weasyprint-a5.css:1075`), and stroked with the 0.55pt INK
  rule exactly on its edges (`img.figure-rule`, css:1096, an `RG`/`S` stroke in
  the oracle). The whole figure is painted `DATUM` (10.0046pt) lower
  (`article > figure[data-figure-id] { top: 10.0046pt }`, css:1059), the caption
  0.1166pt (`figcaption { top: .1166pt }`) and the credit a further -0.09023pt
  (`figcaption .credit { transform: translateY(-.09023pt) }`). A
  `<mag-figure-box>` mark at the image origin carries its size.
- **Band anchor headings** (`doc-heading`): the anchor's `above` was `0pt`,
  which in typst-layout 0.15.1 is a weakness-3 spacing that *replaces* the
  paragraph's weakness-4 `par.spacing` (`flow/collect.rs:246-253`,
  `distribute.rs:185-196`), so the heading sat 5.40pt high. CSS `margin-top: 0`
  collapses with the preceding margin instead; `above: auto` (weakness 4)
  reproduces that collapse. A midpage anchor (not at the page's top, the
  adapter's `_measured_midpage_anchors` condition: its bridge ends on the
  heading's page) is painted down by the dropped space-before, 15pt for h2 and
  10pt for h3 (css `band-anchor-midpage`, 7.77035 = 15 - 7.22965 and
  10.91256 = 10 + .91256).
- **Tail art** (`tail-art`, `tail-layer`): the end mark drops a
  `<mag-end-baseline>` mark at its label baseline; `tail-art` computes the
  adapter's room (`_tail_art_room`: baseline above the page foot minus the 45pt
  frame bottom minus the 12pt clearance) and strip height
  (`min(325 * h/w, 214)`), and prints when `room >= height`
  (`_measured_tail_art`). The strip is placed by the page **foreground** at the
  column's left, foot `MARGIN-BOTTOM - DATUM` = 44.995pt above the page foot
  (the oracle's `bottom: -10.0046pt` under a 54.9996pt margin), fit from
  `tail_art_fit` (010: `contain`). A first attempt placed it from the flow;
  `place(bottom)` there resolved against the flow position, 164pt high, so the
  layer draws it in page coordinates instead (and paints after the text, as
  CSS paints an absolutely positioned box).
- **Closing plates** (`plate-page`): the art is set 333.0079 x 595.2756pt from
  the page's top-left of the live area, `fit: "contain"` (css:1646).
- **layout.json** (`layout.rs`): `figures[].box_points` =
  `(x, page_h - top - h + 0.005, w, h)` rounded to 3 places, the oracle's
  `_figure_placement` definition including its `_RASTER_NUDGE_POINTS`;
  `effective_ppi` = `min(px_w/(w/72), px_h/(h/72))` to 1 place; `tail_arts`
  from the `<mag-tail>` marks with the adapter's exact drop-reason wording.

## Commands

```sh
unset TYPST_ROOT; RUN=editions/010/run-2026-09-13T01-34-51
./mag/target/debug/mag parity 010 --run $RUN        # base binary 85d1d4c: exit 1, ratchet pass; weasy T21-39-26, typst T21-40-36
./mag/target/debug/mag render 010 --engine typst --no-model --langs en --run $RUN   # iterations, final T22-13-20, exit 0
./mag/target/debug/mag parity 010 --pre-rendered <T21-39-26> <T21-40-36>   # rebased binary, BEFORE: exit 1 (tiers)
./mag/target/debug/mag parity 010 --pre-rendered <T21-39-26> <T22-14-04>   # rebased binary, AFTER leg: exit 1, "decoding image: expected name, got [/ICCBased 318 0 R]"
<scratch patched binary> parity 010 --run $RUN                             # AFTER, staged: exit 1 (tiers), ratchet pass; typst leg T22-18-17
python3 .../wp34s/place.py <weasy> <typst> <verdict.json>                   # placement-set rows below (scratch script)
(cd mag && MAG_LAYOUT_ORACLE=<T21-39-26>/en/edition-manifest.json MAG_LAYOUT_TYPST=<leg>/en/layout.json \
  cargo test --bin mag the_live_field_by_field_table -- --nocapture)        # exit 0 before (T21-40-36) and after (T22-18-17)
uv run python mag/tests/typeset_oracle.py stage --request <T22-13-20>/request.json --into $ST/live --artifact-root .
uv run python mag/tests/typeset_oracle.py project --root $ST/live --edition 010 --publication-name "Berreta Futura" --out $ST/oracle-010.json
(cd mag && MAG_TYPESET_ROOT=$ST/live MAG_TYPESET_ORACLE=$ST/oracle-010.json MAG_TYPESET_PUBLICATION="Berreta Futura" \
  cargo test --bin mag the_live_edition -- --nocapture)   # "compared the live edition: 68758 characters of reader text", ok
uv run --with pypdf python .../tmp/wp02n-colours.py <weasy pdf> <typst pdf>  # WP-0.2n's colour census, before and after
mutool trace <pdf> <page>                                                    # image and rule transforms quoted below
DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib uv run python .../wp34s/boxes.py <staged root> 12,37,42   # oracle box dump (scratch)
(cd mag && cargo fmt --check && cargo clippy --all-targets -- -D warnings && cargo test)  # all exit 0 on the rebased tree, 394 passed 0 failed, 27 result lines
python3 tools/nocomments.py   # "no comments"
```

## Metrics: `mag parity 010`, before and after

Same WeasyPrint leg (T21-39-26). Before = base typst leg T21-40-36, rebased
comparator, `--pre-rendered` (ratchet `not_evaluated` in that mode; the base
binary's own staged run passed, 54 measured, 0 regressions). After = the final
binary, staged `--run`, *patched* comparator.

| tier | before | after (patched comparator) |
|---|---|---|
| ratchet | pass on the base staged run | **pass, 54 committed, 54 measured, 0 regressions**; digest fresh `d92eca1d...` |
| S page_count | pass 56 vs 56 | pass 56 vs 56 |
| S boxes | pass | pass |
| S text | fail, 5 of 54 (4, 6, 42, 43, 44) | fail, **2** of 54 (4, 6) |
| G | max dx 325.563, max dy 167.672, beyond G1 56, beyond G2 141, structure mismatches 9 | max dx **0.003**, max dy **7.182**, beyond G1 10, beyond G2 95, structure mismatches **0** |
| G pages over 0.5 pt or with line mismatches | 18 | 14 |
| S color | fail, 58855 glyph entries, 47 pages | fail, 58855, 47 pages |
| S navigation | fail, 22 mismatches | fail, 22 mismatches |
| E glyph positions | 2837 glyphs, 51 shows, worst excess 37.99, 40 violations | 2910 glyphs, 52 shows, worst excess 37.99, 40 violations |
| E display list | 2189 vs 1642 elements, 52 pages | 2189 vs 1661 elements, 52 pages |
| V | V1/V2 fail, worst fraction 0.624 (plate pages) | V1/V2 fail, worst fraction **0.288** (page 4, an opener) |

**Page set `placement`** (9, 12, 16, 29, 34, 37, 39, 42, 44, 49, 53), from the
two verdicts and layouts:

| page | kind | typst placed before | after | G dy before | G dy after | text | V before | V after |
|---|---|---|---|---|---|---|---|---|
| 9 | tail | no | yes | 5.399 | 5.399 | eq | 0.1432 | 0.0032 |
| 12 | figure | frame only | yes | 20.400 | **0.002** | eq | 0.0885 | 0.0024 |
| 16 | tail | no | yes | 5.398 | 5.398 | eq | 0.1412 | 0.0014 |
| 29 | tail | no | yes | 5.400 | 5.400 | eq | 0.1488 | 0.0079 |
| 34 | tail | no | yes | 5.399 | 5.399 | eq | 0.1417 | 0.0025 |
| 37 | figure | frame only | yes | 15.521 | **0.002** | eq | 0.0233 | 0.0024 |
| 39 | tail | no | yes | 5.998 | 5.998 | eq | 0.1606 | 0.0198 |
| 42 | figure | frame only | yes | 20.400 (1 line mismatch, text differs) | **0.002** (text eq) | eq | 0.0619 | 0.0021 |
| 44 | tail | no | yes | 167.672 (5 mismatches, text differs) | 5.399 (text eq) | eq | 0.2453 | 0.0036 |
| 49 | tail | no | yes | 5.398 | 5.398 | eq | 0.1404 | 0.0020 |
| 53 | tail | no | yes | 5.398 | 5.398 | eq | 0.1420 | 0.0016 |

- Tier S same-page: 11/11 (before 3/11: typst printed no tail).
- G2 boxes: figure `box_points` identical to the oracle's on all three
  (`[64.454, 248.276, 289.14, 205.0]`, `[44.0, 80.259, 333.008, 187.317]`,
  `[42.52, 213.959, 333.008, 187.317]`); raw mutool transforms agree to 3e-5pt
  (p12 oracle `289.13963 0 0 205 64.45381 142.005`, typst
  `289.13966 0 0 205 64.45381 142.005`); tail strips 325 x 108.3333 at
  (48.004/46.524, 441.947) on both legs.
- `effective_ppi` equal: 498.0, 518.9, 518.9 on both.
- The remaining G2 failure on the eight tail pages is the `END / NN` mark,
  5.40pt off (6.00 on 39), already a named WP-3.1 / WP-3.5 residual in
  WP-3.2.md; the strip itself is not text and is not in G.
- Closing plates (10, 30, 35, 45, 54): V differing fraction 0.62 -> 0.0004
  (0.6242/0.6152/0.6226/0.6226/0.6237 -> 0.0004/0.0003/0.0004/0.0004/0.0004).

## WP-2.3 field table, before and after

`the_live_field_by_field_table`, oracle = T21-39-26 manifest `layout`.

| | cells | equal | differing | WP-3.4 cells differing |
|---|---|---|---|---|
| before (T21-40-36) | 125 | 94 | 31 | 31 (6 figure box/ppi, 25 tail art) |
| after (T22-18-17) | 134 | 133 | **1** | 1 |

Cells grew by 9 because `box_points` is now an array of four cells instead of
one null. The one differing cell:

| field | key | oracle | typst |
|---|---|---|---|
| tail_arts | 0.drop_reason | "...leaves -15.7pt of open tail room..." | "...leaves -8.5pt of open tail room..." |

Both legs drop that strip (the rails article, page 6, room far below 108.3pt).
The number differs because typst's last line on page 6 sits 7.18pt away from
the oracle's (page 6 is a Tier S text page and the G maximum): the room is read
from each leg's own end-mark baseline, so it is the body-flow residual on that
page, WP-3.1, not the tail rule. Figures and tail rows after:

```
| figures | 0.box_points.0..3 | 64.454, 248.276, 289.14, 205.0 | same | equal x4 |
| figures | 0.effective_ppi | 498.0 | 498.0 | equal |
| figures | 1.box_points.0..3 | 44.0, 80.259, 333.008, 187.317 | same | equal x4 |
| figures | 1.effective_ppi | 518.9 | 518.9 | equal |
| figures | 2.box_points.0..3 | 42.52, 213.959, 333.008, 187.317 | same | equal x4 |
| figures | 2.effective_ppi | 518.9 | 518.9 | equal |
| tail_arts | 0 | declared, not printed, height null | same | equal, drop_reason DIFFERS (above) |
| tail_arts | 1..8 | declared, printed, height 108.3333, drop_reason null | same | equal x32 |
```

## Colours (WP-0.2n's census, distinct fill/stroke pairs at n/255, pages 2-55)

- before: WeasyPrint-only fill PALE-VIOLET (244,241,249) and stroke INK
  (14,19,22); typst-only stroke (23,25,28).
- after: WeasyPrint-only fill PALE-VIOLET; typst-only stroke (23,25,28).
- The INK stroke was the figure rule; it is now painted.
- **PALE-VIOLET** is not figure/plate/ornament paint: it is the background of
  inline `code` (`weasyprint-a5.css:951`; `pre` at :940, and 010 has no fenced
  code). Owner: WP-3.1 (inline code, the same residual WP-3.2 named for page 4).
- **(23,25,28)** is PAPER-INK stroked by `opener-art()`'s 2.4pt frame border;
  the oracle paints that border as a fill (WeasyPrint `border` is filled,
  css note at :1082-1086). Owner: WP-3.2 (illustrated opener).

## Comparator defect (for the orchestrator, `mag/src/parity/streams.rs`, not touched)

`image_pixels` reads `/ColorSpace` with `name_str`, so any image XObject whose
colour space is an array fails. typst-pdf 0.15.1 writes every image that way:
`convert.rs:56` sets `no_device_cs: true`, so krilla emits `[/ICCBased n]` (an
sRGB profile) for all RGB images. The 010 PNGs carry only an `sRGB` chunk and
no `iCCP` profile; the array comes from typst, not from the art. The scratch
fix used for the *patched* figures, at `streams.rs` `image_pixels`:

```rust
let cso = resolve(doc, dict.get(b"ColorSpace")?)?;
let cs = match cso.as_array() {
    Ok(a) => { let n = num(resolve(doc, resolve(doc, &a[1])?.as_stream()?.dict.get(b"N")?)?)?;
               if n == 3.0 { "DeviceRGB".to_string() } else { "DeviceGray".to_string() } }
    Err(_) => name_str(cso)?,
};
```

It decodes the samples as their N components, which is right for an sRGB or
grey ICC profile and says nothing about other profiles. A comparator WP should
make the real fix with its own tests; after it lands, this commit rebases and
lands with the unpatched gate.

## Tests added or changed

- `layout::the_fixture_pieces_measure_as_emitted`: fixture 900's band figure
  (48 x 40 px, verso page 6) has `box_points` x 86.024, w 246.0, h 205.0 and
  `effective_ppi` 14.0, all derived by hand: scale `min(333.008/48, 205/40)` =
  5.125, x = 42.5197 + (333.008 - 246)/2, ppi = 48 / (246/72) = 14.05. Its tail
  art prints at 108.3333 (= 325 x 20/60).
- `layout::the_tail_art_prints_only_when_its_strip_fits_the_room_under_the_end_mark`:
  a 1pt straddle: the last gap that prints and the first that does not, with
  room >= height on one side and < on the other, and the rooms 1pt apart.
- `layout::a_midpage_band_anchor_is_painted_down_by_its_dropped_space_before`:
  the same anchor midpage and at a column top; the heading-to-image distance
  differs by exactly 15pt (h2).
- `template::closing_plates_interleave_after_the_articles_the_adapter_names`
  now finds plates as the pages that draw an image (and the covers as the blank
  ones), since plate pages are no longer empty; the banker's-rounding slots are
  unchanged. The two figure sweeps pass a raster path.

## Not ported, with owners

- The 300 ppi floor. The adapter raises below 300 ppi (`_figure_placement`,
  `_measured_tail_art`); the typst leg reports `effective_ppi` and does not
  refuse, because fixture 900's own figure is 14 ppi and replacing that fixture
  is outside this WP's paths. Needs an orchestrator call (a fixture WP, or the
  preflight port reading `effective_ppi`).
- `adaptive_band` image shrinking (`_measured_adaptive_images`), a band landing
  on another page than its bridge (`_measured_band_offsets`), landscape plates
  (`_rewrite_landscape_plates`) and the `band-clearance` rule. 010 has none of
  them, so nothing measures them; they stay unported rather than unverified.
- Opener art rasters. `opener-art()` still draws a white frame and no image;
  the opener pages are now the V maxima (0.288 on 4, 0.281 on 46, 0.281 on 7).
  The world can load them now; owner WP-3.2.

## What is and is not proven

- Proven (patched comparator): on 010 en every placement page carries its
  figure or tail on the same page as the oracle, the three figure boxes and
  PPIs are equal to the printed digit, the band anchor pages 12, 37, 42 are
  within 0.002pt in G, the tail decision matches 9/9, closing plates match to a
  V fraction of 0.0004, page count 56 = 56, ratchet pass with 0 regressions on
  a fresh staged digest.
- Proven without the comparator: the WP-2.1 projection is byte-identical
  (68758 characters, the new arguments are paths, not reader text); the
  WP-2.3 table goes from 31 to 1 differing cell; `cargo test` 394/0 (rebased), fmt,
  clippy, nocomments clean.
- Not proven: any of the tier numbers under the committed comparator, which
  cannot produce a verdict on this leg at all. That is the blocker.
- Equality caveats (rule 4): `box_points` keeps the oracle's 0.005pt raster
  nudge and the tail room keeps its 45pt frame bottom although the strip's foot
  lands at 44.995pt; both are the oracle's definitions, ported as such. The
  midpage anchor repair reproduces a flow defect the stylesheet itself
  documents (css:1148-1185, a 2.65pt gap repaired in paint only); typst keeps
  it deliberately so the languages paginate the same way.
- Not proven: the page-top anchor path on a real edition (all three 010
  anchors are midpage; the synthetic column-top case covers it), `cover` fit
  on a strip capped at 214pt, and Spanish.
