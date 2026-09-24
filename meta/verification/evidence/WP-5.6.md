# WP-5.6 native render_edition

## Base

`art_directed` `5f73d8d`, detached worktree `.../tmp/wp56`, its own
`mag/target`. Tracked run `editions/010/run-2026-09-13T01-34-51`, `--langs en`.
Bridge (oracle) output pre-generated in this worktree:
`editions/010/render-2026-09-24T10-28-07` (`mag render 010 --engine weasyprint`,
exit 0). Final typst output: `editions/010/render-2026-09-24T10-51-29`.

## What changed

`mag render --engine typst --operation render_edition` now runs the whole
bridge pipeline in Rust, in the bridge's order: reader interior, cover faces,
outer-page replacement, `package_release` (impose x3, critic, preflight,
SHA256SUMS), web edition, `web-output.zip`, `package.zip`. No process is
spawned apart from poppler (the critic's `pdftoppm`, as before).

- `mag/src/typeset/cover.rs` (new): `design.toml` loading including `[back]`
  and `[layout.*]` (new dependency `toml` 0.8, already in Cargo.lock through
  typst); `CoverText` and both invisible text layers derived from the Edition
  (`_add_selectable_text_layer`, `_add_selectable_back_text_layer`), the back
  copy table per language (`_back_cover_copy`), the SVG -> resvg -> `pdf::write`
  step for both faces, and `replace_outer_pages` (the WP-0.0e form: the
  interior's catalog is kept, so `/Lang`, `/Outlines` and Info `/Title` survive;
  the first and last page objects keep their ids and take the faces' keys;
  `/Creator` and `/Producer` `magazine-compiler`; orphans pruned).
- `mag/src/typeset/release.rs` (new): edition-manifest (`_render_manifest`),
  figure placements from the layout, `package_release`, `write_web_edition`,
  both `archive_tree` calls, the bridge's file kinds.
- `mag/src/typeset/layout.rs` `report`: measure operations unchanged
  (layout.json); `render_edition` writes no layout.json (edition-manifest.json
  carries the layout, as in the oracle) and calls `release::publish`.
  `mag/src/typeset/mod.rs`: `render_edition` refuses a non-primary language
  on typst with the flag that fixes it (it silently dropped it before).
- `mag/src/render.rs`: the typst render_edition ends with the same next step
  the bridge prints, plus the parity pointer.
- OUTSIDE the Owns line, needed for the cover step (orchestrator brief: "add
  it"): `mag/src/cover/back.rs` (new, `_materialize_back_svg` and
  `_fit_back_statement` port, Source Serif ink extents), `mag/src/cover.rs`
  (`pub mod back`), `mag/src/cover/outline.rs` (`Outliner::wrap`, the one
  `_wrap`; `svg.rs`'s two copies now delegate to it), `mag/src/cover/svg.rs`
  (`pyf`/`escape` `pub(crate)`). The cover tests (`cover_*.rs`) still pass
  unchanged.

## Commands and results

```sh
P=<PATH without the directory holding uv>
env PATH=$P sh -c 'command -v uv'                                   # exit 1
env PATH=$P mag render 010 --engine weasyprint --run $RUN --langs en --no-model
#   positive control: exit 1, "spawning `uv run mag-render-adapter`: No such file or directory"
env PATH=$P mag render 010 --engine typst --run $RUN --langs en --no-model
#   exit 0, ~30 s release build, totalPages=56, criticResult "pass"
env PATH=$P MAG_PARITY_OUT_DIR=<scratch> mag parity 010 --pre-rendered \
    editions/010/render-2026-09-24T10-28-07 editions/010/render-2026-09-24T10-51-29
#   exit 0 (tier lines below)
MAG_PARITY_OUT_DIR=<scratch> mag parity 010 --run $RUN               # staged, uv on PATH
#   exit 0, staged inputs fresh bc49b2aa..., ratchet pass (target E, 54 measured, 0 regressions)
bash pkgcmp.sh <bridge> <typst>                                     # package/web oracle, below
(cd mag && cargo fmt --check && cargo clippy --all-targets -- -D warnings && cargo test)
#   all exit 0; 32 result lines, 875 passed, 0 failed (nocomments included)
```

Parity, identical in both modes: S page_count 56 vs 56, boxes pass, text pass
(54 pages), G max dy 0.006, color pass, navigation pass (85 links, 51
outlines, 1 title, 1 lang), **E glyph positions pass (58623 glyphs, 0
violations), E display list pass (58850 vs 58850, 0 pages differ)**, V pass.

## Package and web oracle (rule of WP-5.5c in QUEUE.md)

Typst leg against the pre-generated bridge tree, `en/`:

| entry | result |
|---|---|
| file set | equal, 176 files |
| SHA256SUMS | same 122 files, same order |
| printing instructions, studio/README.md | byte-equal |
| edition-manifest.json | equal except `layout.design_direction` (engine label, excluded by decision) |
| preflight.json | equal after normalizing the stage root (4 absolute paths; the bridge's is a deleted temp dir) |
| web/ | byte-equal, 51 files |
| web-output.zip | 51 entries, order, content and metadata equal |
| package.zip | 175 entries, order and metadata equal; content differs on 110 (below) |
| reader.pdf pages 1 and 56 (the cover faces) | pixel-equal at 300 dpi (pdftoppm, cmp) |
| booklet-a4-cover.pdf | pixel-equal at 300 dpi; cover-booklet-sides PNG byte-equal |
| booklet-a4 / interior / reader page counts | 28/26/56 on both |
| render-critic.json | result pass on both; cover pages' entries identical |

The 110 differing package entries and the 243 differing critic leaves are the
engine-rendered interior, not this WP's wiring: reader-pages 47, booklet-sides
26, crops 22, contact sheets 6, the three imposed PDFs, reader.pdf, and the
JSON entries that measure or hash them. Critic leaves by field: ink_ratio 72,
text_characters 72, presence_ratio 50, body_text_lines 26, opener crop
rgb_mae/message 15, bboxes 6, the two sha256. Interior rasters are a Tier V
meter (worst page fraction 0.000336); byte equality there would need
WeasyPrint's rasters.

Positive control for the cover-page check: the pre-WP typst reader
(`render-2026-09-24T04-37-08`, placeholder outer pages) page 1 against the
oracle page 1: `cmp` exit 1.

## Tests added (`mag/src/typeset/cover.rs`)

- `the_010_back_cover_rasterizes_to_the_pixels_the_python_compiler_printed`:
  the back face built from `editions/010/edition.yaml`'s cover mapping
  rasterizes (1748x2480, straight RGBA) to `beb601e1...ce100`. The pin is
  PYTHON's number: `CoverCompiler._materialize_back_svg` on the staged 010
  through resvg-py, decoded by PIL. Rust's SVG differs in path notation only
  (fontTools writes `H`/`V`), rasterizing both SVGs through resvg-py gives
  the same hash; a 0.5 pt shift of one statement line changes it. Discriminates:
  statement tracking -0.10 fails it; dropping the descender extent fails it.
- `the_back_cover_text_layer_carries_each_languages_copy`: en lines equal
  WP-5.4c's Python transcription; es gives CICLO/CERRADO, FIN, NÚMERO.
- `outer_pages_take_the_cover_faces_and_keep_the_interiors_catalog`: 4-page
  synthetic interior with `/Lang`, Info `/Title` and an outline entry on page
  2: faces replace pages 1 and 4, pages 2-3 untouched, outline still targets
  page 2, Lang/Title kept, Creator/Producer set, `/Parent` kept.

Ink extents use the glyf header bbox, not fontTools' `BoundsPen`. Measured over
all 909 mapped glyphs of SourceSerif4SmText-Regular: only `asterisk` differs
(exact yMin 352.30 vs header 340), and `ink_extent` clamps the descender at 0
for positive yMin, so the two agree on every string this face can set.

## The compared domain stays 2..n-1

Not extended here: the domain lives in `mag/src/parity.rs` and `parity.yaml`,
which WP-5.4g owns ("comparator switch: the compared artifact becomes
reader.pdf end to end"). Its prerequisite now exists: both legs carry the
cover faces, pixel-equal on 010. For WP-5.4g: the cover faces embed Inter
(`/Inter`, from `pdf::write`) and raster images on both legs; the display list
of pages 1 and n was not traced here.

## What is and is not proven

PROVEN (010, en): `--engine typst` renders reader, covers, critic, package and
web with `uv` absent from PATH; Tier E green pre-rendered and staged (staged
ratchet at target E); package entries equal to the bridge under WP-5.5c's rule
wherever the entry does not depend on interior pixels; the cover faces and
cover-booklet imposition pixel-equal; web tree and web archive equal.

NOT PROVEN: the package entries that depend on interior rendering (differ by
engine, see above); the front cover in `framed`/`honored_plate` through this
path (010 is `footer_caption`; WP-5.4b proves those rasters by fixture);
Spanish covers and any multi-language render (typst now refuses extra
languages); a cover without art (Python draws a violet placeholder for
`framed`; the typst step refuses); the `design.toml`-absent fallback (the typst
step refuses; Python has built-in defaults).

For the orchestrator:
- The Rust critic reads 1-2.6% more `text_characters` on 46 typst interior
  pages than on the bridge's (e.g. p3 653 vs 662), and `body_text_lines`
  differs on 7 pages, while Tier S text is equal: the critic's text layer
  reads the two engines' PDFs differently. The critic still passes. Owner:
  the typst-leg critic (WP-5.3g per the parity line).
- `package_release`'s `cover_art_size_points` is None on both legs
  (layout `cover_art_size_points: null`), so preflight never checks cover-art
  size on either. Equal, and possibly not intended.
