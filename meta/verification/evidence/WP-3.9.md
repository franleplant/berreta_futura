# WP-3.9 the typst leg beyond 010, measured on 008

## Base

`art_directed` `e1822cf` (WP-0.2x). I started from `7ab3ebc` and moved the work
onto `e1822cf` before any measurement below. Detached worktree `.../tmp/wp39`.
The base binary was built from a second worktree at `e1822cf`.

**Status: `mag parity --adhoc 008` exit 1 -> exit 0 (Tier S pass).** Of the four
display-list pages still differing, none has a typst-template cause (ledger
below). 010: 56 = 56, typst reader.pdf byte-identical to the base binary's
(`6709dc15...`), full staged parity exit 0 (ratchet 0 regressions, display list 0,
navigation 0). WP-2.1 projection equal. Fixtures 902-905: typst reader.pdf
byte-identical to the base binary's, every clause pass.

## 008 before and after (both with the `e1822cf` comparator)

| clause | before (base binary) | after |
|---|---|---|
| exit | 1 | **0** |
| S text | fail, pages 16-20 | **pass** |
| S colour | fail, 5 pages | **pass** |
| S navigation | fail: p10 annotation rects, document outlines | **pass (0)** |
| G | max dx 327.8, dy 140.7; beyond G2 62; structure 22 | max dx 4.004, dy 102.4 (p4 only); beyond G2 24 (p4); structure 0 |
| E display list | 8 pages: 4, 10, 11, 16, 17, 18, 19, 20 | 4 pages: 4 (text), 16, 17, 19 (image only) |
| E glyph positions | 40 printed, worst 216.84 pt p4 | 40 printed, all on p4 |
| V worst page fraction | 0.1507 | 0.1103 (p4). Every other page is <= 0.000336, which is 010's own passing worst |

## What changed (owned files only)

Each item is listed with the pages it fixed, in order of page count.

1. **Heading kept with its figure (p16-20, 5 pages).** `h1-h3 { break-after: avoid }`
   applies here. The adapter adds no `.heading-clearance` after a heading whose next
   sibling is a figure (`_install_flow_clearances`), so the oracle carries the heading
   to the figure's page. Typst left "PRICE PER TOKEN" alone at the foot of p16. Now
   `heading-stack` takes `sticky:`, which `doc-heading` sets when the next flow item
   is a figure (`next-flow`, shared with `band-anchored`). A heading before an
   extract keeps its clearance and stays non-sticky: I first made it sticky too, and
   903 p4/5 regressed. That is also why the adapter's rule is figure-only.
2. **Caption runts bound on the caption's own measure (p16).** The oracle binds
   `span.caption` / `span.credit` (bindable `span` in `main`) against the box width:
   333.008 on a band, 260 on a compact band. Figure caption and credit are now prose
   blocks: `edge-prose` labels them `mag-prose-band` / `mag-prose-compact` /
   `mag-prose` from a `caption-edge` state that `figure-block` sets. `runt.rs` reads
   each label's right-edge shift (+4.00395 / -32.5 / 0) when it opens the block. The
   p16 caption now ends "effort goes." as the oracle's does.
3. **Carried band keeps the bridge page's left edge (p11, p17, p19).** This ports
   `_measured_band_offsets`. When a band's bridge (the element before its anchor
   heading) ends on an earlier page than the figure, the adapter gives the figure
   `left: live_left(bridge) - live_left(landed)` (+-1.4803 pt). That is ReportLab's
   stale-frame behaviour, reproduced deliberately. `figure-block` now moves the whole
   figure (label, image, caption) by that amount when its anchor heading's flow mark
   sits at the page top. The heading itself does not move, as in the oracle. First
   attempt, dropped: the heading emitted a metadata marker the figure queried. That
   added an introspection level and 008 stopped converging in five passes. Reading
   the heading's flow-mark position directly converges.
4. **Illustrated opener title fitted as the adapter fits it (p10).** `_fitted_display`
   wraps on advance widths: untracked, unkerned, 348 pt rail, 64 pt box, 32.5 / 30 to
   22 pt, 2 lines. Typst measured its own tracked set, so it chose 23 pt where the
   oracle chose 22.5 pt, which put the credit block and QR link 0.96 pt low. The new
   `Metrics::illustrated_titles` computes both fits, and the emitter passes them as
   `piece(titles: ...)`. The template's `fitted-title` loop and its six constants
   are gone. The template still makes the standard/compact density decision, and it
   now uses those fits. This fixed p10's annotation and rule differences, and with
   them the navigation clause.
5. Fixture `mag/tests/typeset_fixtures/media/exif.jpg`: 24x16, EXIF orientation 1,
   751 bytes, made with Pillow.

## Tests added

- `a_heading_goes_to_the_next_page_with_the_figure_it_anchors`: 64 steps x (band,
  column), heading and figure label on one page every time. Control: with
  `sticky: false` some step parts them. Extract case: some step leaves the heading
  on an earlier page than the extract. I mutated the rule to include extracts, and
  that assertion failed.
- `a_band_carried_past_its_bridge_keeps_the_bridge_page_s_left_edge_as_the_adapter_does`:
  a band label sits at `live_left(bridge page)`: the previous page when carried,
  its own page otherwise. A column figure is never shifted. Both carried and
  stayed cases occur.
- `a_jpeg_figure_is_embedded_as_its_own_bytes_exif_and_all`: the only DCTDecode
  stream equals the fixture file byte for byte.
- `a_band_caption_is_bound_on_the_band_s_own_measure` (runt.rs): with the 008
  caption, a band binds `effort\u{a0}goes`. Control: the same caption in a column
  figure is not bound, and neither is the one-line credit.
- `an_illustrated_title_is_fitted_on_advance_widths_as_the_adapter_fits_it`: the
  008 p10 title gives (22.5, 2) for both densities, which is the size the oracle
  printed. A short title gives (32.5, 1). An unfittable title is refused.
- Updated: `the_fixture_pieces_measure_as_emitted` pins the 900 band at x 87.504
  (was 86.024). Its heading is at the top of page 6 and its bridge is on page 5, so
  the adapter's rule shifts it +1.4803. 900 has no oracle render (WP-3.8), so this
  value comes from the rule, not from a rendered oracle. `opener_run` passes
  `titles`.

## Commands (exit status, key numbers)

```sh
S=.../tmp; M=$S/wp39-target/debug/mag; B=$S/wp39-base-target/debug/mag   # B = e1822cf
uv run python tools/sourcecodes.py 008          # exit 0, "print declines on 0"; NOT committed (below)
$B parity --adhoc 008 --run editions/008/run-2026-08-30T13-59-32   # exit 1, before column above
$M parity --adhoc 008 --run editions/008/run-2026-08-30T13-59-32   # exit 0, after column above
#   verdict $S/wp39-scr/p008-final/verdict.json; a 8d4dde58..., b ac815563...
$B / $M render 010 --engine typst --no-model --langs en --run editions/010/run-2026-09-13T01-34-51
#   both exit 0, 56 pages, reader.pdf 6709dc151c875df1... (identical; no warning)
$M parity 010 --run editions/010/run-2026-09-13T01-34-51       # exit 0
#   staged inputs fresh ae9d6daf..., ratchet pass (54 checked, 54 measured, 0 regressions)
#   S all pass, navigation 0, G max dx 0.000 dy 0.006, E glyph 0 violations, display list 0 pages, V1/V2 pass
typeset_oracle.py stage (57 inputs) / project: exit 0; cargo test --bin mag the_live_edition
#   "68758 characters of reader text, 0 verbatim runs", ok
$S/wp39-scr/fx.sh <bin> <tag>   # 902-905 from WP-3.7a's store, scored against WP-3.7a's oracle renders
#   base and after: reader sha ed48f3fc / f4b4c233 / 77e10f44 / b4e0631b on both; every clause pass
(cd mag && cargo fmt --check && cargo clippy --all-targets -- -D warnings && cargo test)
#   exit 0 each; 32 result lines, 869 passed, 0 failed
python3 tools/nocomments.py    # "no comments", exit 0
```

## Residual ledger (008, not fixed here)

- **p4, editorial opener (1 page: G, glyphs, V, display text).** The typst
  editorial is a stub. The plan puts the editorial path out of scope: "the Typst
  engine targets the current format (editions 010+: no opening editorial)". Not
  touched.
- **p16, p17, p19 images: the ORACLE re-encodes.** The typst leg embeds
  `media/005.jpg`, `006.jpg` and `011.jpg` byte for byte (`cmp` exit 0; 69816 /
  181241 / 138702 bytes). WeasyPrint writes 65555 / 160892 / 128809-byte JFIF
  re-encodes. The cause is `weasyprint/images.py`. The default
  `image-orientation: from-image` calls `ImageOps.exif_transpose` for any JPEG that
  carries EXIF, and that returns a copy even for orientation 1. `RasterImage` then
  treats the image as transformed, drops the source bytes, and saves again at
  Pillow's default quality. The p6 JPEG has no EXIF, and its bytes are identical on
  both legs. The typst leg is the correct one: a lossless pass-through, now pinned by
  a test. The fix belongs to the renderer (`src/magazine`, not owned here), for
  example `image-orientation: none` on figure images, or stripping EXIF at capture.
  Either one changes the staged digest and needs a baseline decision. **Owner: the
  orchestrator or the renderer WP.**
- **Cover and back cover (p1, p44):** outside the interior domain (WP-5.6).
- The 1-quantum running-head blips (p26/p28, 0.000015 pt) that the base comparator
  showed are gone with WP-0.2x. They were never a template cause.
- **008 source-codes are not committed.** `editions/008/source-codes` is edition data
  outside this WP's Owns line. Only 010's were committed, by a verify WP. The
  directory is generated in the worktree only, as WP-4.0g did, and is not in the
  commit. Whether to commit it is for the orchestrator.

## What is and is not proven

- Proven: on 008 every Tier S clause passes. The typst-caused display-list
  differences are gone on 5 of 8 pages, and three more pages differ in the image
  element only, which is an oracle re-encode. On 010 and fixtures 902-905 the typst
  reader is byte-identical to the base binary's, so nothing there moved. Each new
  rule is pinned by a test with a positive control, and the extract exception by a
  mutation.
- Equality caveats (rule 4):
  - The carried-band offset reproduces a ReportLab stale-frame artefact. The
    carried figure sits 1.48 pt off the live area's centre on both legs. I matched
    it because the adapter applies it deliberately (`_apply_band_offsets`), not
    because it is good typography.
  - The title fit on advance widths ignores tracking and kerning, so both engines
    can pick a smaller size than the set line needs. That is what the adapter does.
- Not proven:
  - The carried rule assumes the bridge ends on the page just before the figure. A
    full-page plate between them would make the parity wrong. 008 and 010 have no
    such case.
  - Caption runts on extract captions and key ideas, which the oracle also binds:
    008 has none.
  - Spanish.
  - Any edition but 008, 010 and the fixtures.

## After the rebase onto `4c3697b` (WP-3.0g, comparator and baseline only)

`cargo test`: 32 result lines, 870 passed, 0 failed. `mag parity 010 --run
editions/010/run-2026-09-13T01-34-51` exit 0: staged inputs fresh `ae9d6daf...`,
ratchet pass (target E, 54 checked, 54 measured, 0 regressions), navigation 0,
glyph 0 violations, display list 0 pages, V1/V2 pass. Typst reader `6709dc15...`.
