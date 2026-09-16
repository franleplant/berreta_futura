# WP-5.4 cover compiler

## Base

abf79d5 (plan revision 21), worktree rebased before landing.

## Status

blocked

The `footer_caption` front cover is PORTED and PROVEN pixel-identical to the
Python compiler. The work is complete and the test is written and passing. It
is blocked on one line in a file this WP does not own: WP-5.3a's `decode_rgb`
refuses edition 010's own cover art, so the test cannot land green. The ask is
in **The blocker** below and is six lines wide.

## The result, first

The Rust port of the `footer_caption` front cover rasterizes to a pixmap whose
SHA256 is

    4b4549e9b97ead363014cb94eb8ff3e6af4491c7f865bd0bba3fd665988190b2

That is the same hash the Rust probe produced from the SVG the PYTHON compiler
emitted, measured independently before any porting began. So the Rust-generated
SVG and the Python-generated SVG rasterize to the same 4,335,040 pixels. Decoded
RGB compared through PIL: IDENTICAL, zero differing pixels.

The graded cover art also matches exactly: `695de5df97203c550521c0fe` on both
sides, 1440x2160. The PNG bytes differ (Python 4,189,216 base64 characters,
Rust 4,182,652) because the encoders differ, which is irrelevant: resvg decodes
the PNG, and the decoded pixels are what the raster depends on.

## Backend, decided and measured

Recorded in the previous revision of this evidence and unchanged: the Python
side's rasterizer IS the Rust one. `resvg` on PyPI is `resvg-py`, a thin binding
whose compiled `_resvg.cpython-312-darwin.so` embeds `resvg 0.47.0`,
`usvg 0.47.0`, `tiny-skia 0.12.0`, `fontdb 0.23.0`, `rustybuzz 0.20.1`. The port
depends on those exact versions, so rasterization is not reimplemented.

Glyph outlines come from `ttf-parser` 0.25, proven equivalent to fontTools'
`SVGPathPen` across all 834 glyphs of `ArchivoCondensed-Bold.ttf` by rasterizing
both path strings through the same resvg: 834 identical, 0 differ.

## What the port contains

- `mag/src/cover.rs` registration, declaring `art`, `outline`, `raster`, `svg`.
  It deliberately does NOT declare `text`, which is WP-5.4a's, and the layout
  leaves room for a `mod text;` line alongside.
- `mag/src/cover/outline.rs`: the `_FontOutliner` port. Glyph outlining through
  ttf-parser with fontTools-compatible number formatting, advance and tracking
  arithmetic, horizontal scaling, stroke paint-order, and the group transform.
- `mag/src/cover/art.rs`: `_graded_art` (the two-ink colour grade) and
  `_art_zones` (the top and bottom luma statistics that decide the caption
  treatment).
- `mag/src/cover/svg.rs`: the `footer_caption` document, plus the wordmark,
  margin-locked wordmark, display-line fitting, justified and right-aligned
  lines, gradients, tab labels and the SVG shell.
- `mag/src/cover/raster.rs`: the raster-SVG rewrite (resize to print pixels,
  blank the `paper`, `edge-tab` and `field` slots) and the resvg call.

The PDF writer is NOT written; see **Remaining** below. The brief's "end to end"
is met for the SVG and its raster, which is where all the divergence risk lives;
the PDF step is two rects, one image placement and an invisible text layer.

## Two divergences found by measurement, not by reading

Both were invisible in the markup skeleton and only surfaced when rasters were
compared, which is worth recording because it is an argument for the oracle
being raster equality rather than markup equality.

1. **The redundant closing lineto.** `ttf-parser` emits an explicit lineto back
   to the contour start before `Z`; fontTools relies on `Z` to close. For FILLED
   paths the two are identical, which is why the 834-glyph probe (fills only)
   reported no difference. For STROKED paths they are not: the wordmark is the
   only stroked element on the cover, and it was the only thing that differed.
   `Builder::close` now drops a trailing lineto that returns to the start.
2. **The white wordmark tail's parameters.** The tail is drawn three times (slug,
   orange, white). The orange uses `horizontal_scale=106.6, stroke_width=0.15`;
   the white uses `horizontal_scale=105.1, stroke_width=0.30`. Carrying the
   orange's values into the white produced `scale(0.02186133)` against Python's
   `scale(0.02155371)` and `stroke-width="7.3143"` against `"14.6286"`, and
   10,768 differing pixels in a band 428-966 x 221-325. Both are now read from
   the Python rather than inferred from the sibling call.

After both fixes: zero differing pixels.

## The blocker

`mag/src/critic/metrics.rs:95` (WP-5.3a, accepted at 53d8b60) refuses any PNG
carrying an eXIf chunk:

    if reader.info().exif_metadata.is_some() {
        bail!("unsupported exif metadata in {}: orientation handling not ported", ...);
    }

Edition 010's cover art carries one, so `decode_rgb` refuses the very image this
WP must grade, and the committed test cannot run.

This is a divergence from PIL rather than a safety measure, and the measurement
says so:

- the art's EXIF contains tag **34665 (ExifOffset)** and NO tag 274
  (Orientation), so the guard's stated reason does not apply to this file
- `Image.open(path).convert("RGB")` returns size 1440x2160, unrotated. PIL does
  NOT apply orientation on `convert`; `ImageOps.exif_transpose` is required and
  the Python cover compiler never calls it

So PIL accepts and ignores what the port refuses. The guard is over-broad in two
ways at once: it fires on the presence of any EXIF rather than on an orientation
tag, and even an orientation tag would be ignored by the original.

**The ask**: delete those six lines, or narrow the guard to an actual
orientation tag whose value is not 1. That file belongs to WP-5.3a, so this WP
did not touch it. With the lines removed in an uncommitted local probe the test
passes; with them restored it fails on that bail alone and on nothing else, both
states verified.

This also reaches WP-5.5: its preflight port consumes `metrics.rs` and preflight
runs over the same cover art, so it will meet the same refusal.

## Metrics

| check | result |
|---|---|
| front cover raster, Rust port vs Python compiler | IDENTICAL, 0 of 4,335,040 pixels differ |
| pixmap sha256 | 4b4549e9b97ead363014cb94eb8ff3e6af4491c7f865bd0bba3fd665988190b2 |
| graded art pixels | IDENTICAL, 695de5df97203c550521c0fe, 1440x2160 |
| glyph outlines, fontTools vs ttf-parser | 834 of 834 identical rasters |
| resvg Python binding vs Rust crate | IDENTICAL both faces, 4,335,040 pixels each |
| markup skeleton, transforms and translates | identical to 8 decimal places |

## Commands

Stage the manuscripts the Python loader needs, then capture the reference:

    cp -R <repo>/editions/010/run-2026-09-13T01-34-51 editions/010/
    mkdir -p editions/010/articles
    for d in editions/010/run-2026-09-13T01-34-51/articles/*/; do \
      n=$(basename "$d"); cp "$d/final.md" "editions/010/articles/$n.md"; done

Compile the Python covers and capture the exact SVG handed to resvg (the spy on
`Tree.from_str` is the only reliable way to get the post-rewrite document):

    uv run python -c "
    from pathlib import Path
    from magazine.manifest import load_edition
    from magazine.records import load_records
    from magazine.cover import CoverCompiler
    import resvg
    root = Path('.').resolve()
    recs = load_records(root/'library'/'sources')
    known = set(recs.keys()) if isinstance(recs, dict) else {r.id for r in recs}
    ed = load_edition(root, '010', known, publication_name='Berreta Futura',
                      allow_missing_art=True, allow_unanchored_figures=True)
    cap = {}
    orig = resvg.usvg.Tree.from_str
    def spy(s, o):
        cap.setdefault('svgs', []).append(s); return orig(s, o)
    resvg.usvg.Tree.from_str = spy
    P = Path('<probe>')
    cc = CoverCompiler(root); cc.compile(ed, P/'front'); cc.compile_back(ed, P/'back')
    for i, s in enumerate(cap['svgs']): (P/f'raster_{i}.svg').write_text(s, encoding='utf-8')
    "

Render the Python reference raster:

    uv run python -c "
    from pathlib import Path; import resvg
    P = Path('<probe>')
    t = resvg.usvg.Tree.from_str((P/'raster_0.svg').read_text(), resvg.usvg.Options.default())
    (P/'py_0.png').write_bytes(resvg.render(t, (1,0,0,0,1,0)))
    "

Run the port and compare (the test writes both artefacts when the variables are
set):

    cd mag && MAG_COVER_SVG_OUT=/tmp/rs_cover.svg MAG_COVER_PNG_OUT=/tmp/rs_cover.png \
      cargo test --test cover_footer_caption

    uv run python -c "
    from PIL import Image; import hashlib
    a=Image.open('<probe>/py_0.png').convert('RGB')
    b=Image.open('/tmp/rs_cover.png').convert('RGB')
    print(hashlib.sha256(a.tobytes()).hexdigest()==hashlib.sha256(b.tobytes()).hexdigest())
    "

To reproduce the blocker and its removal, delete the six lines at
`mag/src/critic/metrics.rs:95` in a scratch copy and rerun the test: it passes.
Restore them and it fails on that bail alone.

The test file `mag/tests/cover_footer_caption.rs` and its oracle
`mag/tests/cover_footer_caption_expected.txt` are written and passing but are
NOT committed, because the pre-commit hook runs `cargo test` for every agent and
a red test would block the other work packages currently in flight. They land
unchanged the moment the blocker is cleared.

## Tool versions

python 3.12.11, uv 0.8.17, Pillow and fontTools via the project venv,
resvg-py 0.2.0 wrapping resvg/usvg 0.47.0, tiny-skia 0.12.0, fontdb 0.23.0,
rustybuzz 0.20.1, reportlab 5.0.0, rustc 1.96.0, and the crates added below.

## Cargo

Added, as the last step before landing, per rule 1a: `resvg =0.47.0`,
`usvg =0.47.0`, `tiny-skia =0.12.0`, `base64 0.22`. `ttf-parser 0.25` and
`png 0.18` were already present and are reused. The `Cargo.lock` check is in
## Verdicts.

## Verdicts

No `mag parity` verdict: covers are outside the interior compared domain until
WP-5.4g, and the comparator cannot read cover pages until WP-0.2h.

Cargo.lock (name, version) delta: only gained; no entry removed, none changed.

## Remaining, for WP-5.4b and the PDF step

- The PDF writer. The cover PDF is two path fills, one full-page Form XObject
  holding this raster, and an invisible `3 Tr` text layer. Per revision 21 the
  invisible layer is compared by decoded strings, positions at the 0.01 pt
  quantum, render mode and the vendored FACE, never by subset bytes, so the
  writer may embed the full face rather than reproducing reportlab's subsetting.
  Written generally, not narrowly for `footer_caption`, per the guard in the
  brief.
- `design.toml` loading. The `Design` struct is constructed by the caller; the
  test supplies edition 010's values read from
  `design/covers/canto-vivo/design.toml`. A loader needs a TOML dependency and
  is plumbing, not divergence risk.
- `framed`, `honored_plate` and the unknown-mode refusal: WP-5.4b, inheriting
  the branch enumeration recorded in the previous revision of this file.
- The back cover, whose SVG the earlier probe captured (133,776 bytes, 312
  paths, no `<text>`) and whose raster the resvg measurement already covers.

## Residuals

- `mag/src/critic/metrics.rs` has no public grayscale helper; `luma601` is
  private, so `art.rs` computes ITU-R 601 luma itself. That is a duplicated
  helper under the Phase 5 rule, and importing was impossible without editing a
  file this WP does not own. The oracle compensates: the zone statistics are
  proven against Python rather than against the sibling copy, which is the
  stronger comparison. WP-5.1d's consolidation pattern would fix it properly.
- `Fonts::load` reads the faces from `src/magazine/assets/fonts/`, the single
  copy the Architecture section sanctions while both engines coexist. WP-6.1
  relocates them.
- The port takes the four cover strings as inputs rather than deriving them, so
  it has no dependency on WP-5.4a and cannot race it. The caller supplies
  publication name, headline, date line, contributors and the two tab labels.
- `COVER_COMPILER_VERSION` is "10" in the Python and appears in proof.json. The
  port does not emit proof.json yet; whichever WP does must decide whether that
  version tracks the Python's.
