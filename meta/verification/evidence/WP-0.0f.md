# WP-0.0f the oracle passes figure JPEG bytes through (sanctioned oracle change)

## Base

`art_directed` `3a9c434`, detached worktree `.../tmp/wp00f`, its own target dir
`.../tmp/wp00f-target`. Runs: 010 `editions/010/run-2026-09-13T01-34-51`, 008
`editions/008/run-2026-08-30T13-59-32`, `--langs en`, `TYPST_ROOT` unset.

## Why

WP-3.9 evidence, residual ledger: WeasyPrint's default `image-orientation:
from-image` runs `ImageOps.exif_transpose` on any image whose Pillow info carries
`exif`. That call returns a copy even at orientation 1, so `RasterImage`
discards the source bytes and re-saves the JPEG at Pillow's default quality
(`weasyprint/images.py` lines 38-43 and 68-74 in the venv's WeasyPrint). This is a
silent quality loss in the printed figure, and on 008 it is a Tier E image
difference against typst, which embeds the source bytes.

## Step 1: measurement

Scratch script `.../tmp/wp00f-exif.py` walks every committed `editions/*/edition.yaml`,
collects each `path` / `*_path` image (a figure `path` resolves under
`library/sources/<source_id>/`), and opens each with Pillow (exit 0):

| format, EXIF in info, orientation tag | files |
|---|---|
| JPEG, no EXIF | 16 (editions 002-004, 008 `how-warp.../001.jpg`, 009) |
| **JPEG, EXIF, orientation 1** | **3: `running-a-software-factory-efficiently-at-uber-s-36ff06c6/media/005.jpg`, `006.jpg`, `011.jpg` (008 only)** |
| JPEG, orientation != 1 | **0** |
| PNG, no EXIF / EXIF without orientation | 111 / 66 |
| WEBP | 2 |

198 referenced images; 5 more are referenced but absent (cover art of editions
001-004, all `.png`, the old editions' own `art/` files).

## What changed

- `src/magazine/weasyprint_adapter.py` `_keep_jpeg_bytes`, the last tree step in
  `_lay_out` before `render`: every `<img>` with a `file:` source that Pillow reads
  as JPEG gets `image-orientation: none` appended to its inline style when its EXIF
  orientation is absent or 1, so WeasyPrint keeps and embeds the source bytes. A
  JPEG with orientation != 1 raises `ValidationError` naming the file ("rotate the
  file losslessly (jpegtran) to orientation 1"). PNGs, WEBPs, data URIs (figure
  rules, contrast-prepared images) are left alone. The semantic HTML (and so the web
  edition) is not touched; this is the PDF hand-off only.
- `mag/src/typeset/media.rs`: the JPEG header walk now also reads the APP1 Exif
  orientation (both byte orders); `pixels` refuses a JPEG whose orientation is not
  1 with the same remedy. Its layout used the unrotated SOF size, so a rotated JPEG
  would have been laid out wrong there.
- New fixtures `mag/tests/typeset_fixtures/media/rotated.jpg` (II) and
  `rotated-mm.jpg` (MM): `exif.jpg` with its APP1 replaced by an orientation 6 one
  (Pillow reads 24x16, orientation 6). Test
  `a_jpeg_that_asks_to_be_rotated_is_refused_and_orientation_one_is_not`.
- `meta/verification/baseline.json` `staged_input_digest` rebased (below).

## Step 3: orientation != 1

None exist in any committed edition. Decision recorded: **fail loud on both legs**.
WeasyPrint can only rotate by re-encoding (not lossless), and the typst leg embeds
bytes and sizes from the unrotated header, so neither leg can rotate losslessly
and they cannot rotate identically. The remedy is a lossless rotation of the
source file. Neither leg rotates anything today.

## Commands

```sh
M=.../tmp/wp00f-target/debug/mag
uv run python .../tmp/wp00f-exif.py                                   # exit 0, table above
uv run python tools/sourcecodes.py 008                                # exit 0; editions/008/source-codes NOT committed (as WP-3.9)
$M parity --adhoc 008 --run editions/008/run-2026-08-30T13-59-32      # exit 0 (below)
pdfimages -list -f 16 -l 19 <008 oracle render-2026-09-24T09-53-14>/en/reader.pdf   # 3 jpeg XObjects, 68.2K / 177K / 135K
pdfimages -all -f 16 -l 19 <oracle> o/p; same for <typst render-2026-09-24T09-54-42> t/p
cmp o/p-000.jpg 005.jpg; o/p-001.jpg 006.jpg; o/p-002.jpg 011.jpg     # all equal (69816 / 181241 / 138702 bytes); typst too
#   positive control: the pre-change oracle render editions/008/render-2026-08-31T14-52-45 (main tree)
#   extracts 65555 / 160892 / 128809-byte streams (WP-3.9's numbers), cmp against the sources: none equal
$M render 010 --engine weasyprint --no-model --langs en --run $RUN   # BEFORE (adapter at HEAD) 09-57-11, AFTER 09-58-27, AFTER again 10-02-50: exit 0 each
pdftoppm -r 300 -png (BEFORE, AFTER); rasdiff                          # "56 pages, 0 differing pixels", exit 0
pdfimages -all (BEFORE, AFTER) | md5                                   # 30 image streams, identical
diff <(pdftotext -raw BEFORE) <(pdftotext -raw AFTER)                  # exit 0
$M parity 010 --run $RUN     # exit 1: refused, run bc49b2aa..., baseline ae9d6daf...
#   rebase baseline.json
$M parity 010 --run $RUN     # exit 0 (below)
python3 -c '_keep_jpeg_bytes on a synthetic tree'                      # exif.jpg, portrait.jpg get the style, png and data: do not;
#   rotated.jpg and rotated-mm.jpg refused with "EXIF orientation 6"
(cd mag && cargo fmt --check && cargo clippy --all-targets -- -D warnings && cargo test)   # exit 0 each; 32 result lines, 872 passed, 0 failed
#   mutation control: MM read as little-endian -> the new test fails (1 failed)
uvx ruff format --check src; uvx ruff check src; python3 tools/nocomments.py   # all clean
```

## 010 oracle

Not byte-identical, and not because of this change: 010 references no JPEG, so no
`<img>` gets the style. BEFORE and AFTER differ only in the trailer `/ID` and the
image XObject names; both are hashes of `file:` URLs under the bridge's random
`mag-engine-render-stage-*` temp dir. Two renders of the same AFTER tree differ the
same way (87148705 vs 87148701 bytes, `cmp` differs at the same offset 2009). Pixels
(300 dpi, 0 differing), text and every image stream are identical.

## `mag parity 010` staged (after)

staged inputs fresh `bc49b2aa...` (57 edition inputs, 43 renderer files); ratchet
pass, target E, 54 checked, 54 measured, 0 regressions; S all pass (navigation 0,
51 outlines); G max dx 0.000 dy 0.006; E glyph 0 violations, display list 0 pages;
V1/V2 pass, worst 0.000336. Typst reader `6709dc15...`, the same sha as WP-3.9's.

## `mag parity --adhoc 008` (after)

exit 0; S all pass; **E display list: 1 page differs, p4** (was 4 pages: 4, 16, 17,
19, WP-3.9 evidence). p4 is the editorial opener, out of scope. Glyph positions
still 40 violations, all p4 as before; V worst 0.110331 (p4).

## Baseline rebase

`staged_input_digest`: old `ae9d6dafbdb5a5870fe5fbd3fa2a6122b242caeb7aaf7548b20cd84db0ba7d1f`,
new `bc49b2aaad8844155a2e5496d135360534771b57c9a87a690b4e9243ae5fed5b`, from the
refusal line on the final tree, confirmed "fresh" by the AFTER run. No other field
changed.

## What is and is not proven

Proven: the three EXIF JPEGs in 008 are now embedded by the oracle as their source
bytes (`cmp` equal, positive control from the pre-change render); the 008 display
list differs only on p4; 010 is unchanged in pixels, text and image streams, and its
staged parity holds at E with 0 regressions on the rebased digest; both legs
refuse orientation != 1 (tests and a synthetic tree, both byte orders).

Not proven: the oracle refusal has no committed Python test (none of the renderer's
steps has one in this repo; the check was a scratch call). PNGs with EXIF (66) are
still re-saved by WeasyPrint's transpose copy; that is pixel-lossless and caused no
difference on 008 or 010, so it was left alone. The `es` editions and editions
other than 008 and 010 were not rendered. Rule 4: the typst leg was already correct
here; the oracle moved to it.
