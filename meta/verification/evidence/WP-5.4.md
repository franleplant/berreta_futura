# WP-5.4 cover compiler

## Base

abf79d5 (plan revision 21), worktree rebased before landing.

## Status

done

The `footer_caption` front cover is ported, proven pixel-identical to the Python
compiler, and its test is committed and green. The eXIf guard that blocked it
was fixed under an orchestrator grant extending this WP's Owns to
`mag/src/critic/metrics.rs` for that guard only; WP-5.3a's full oracle was
re-run and did not move. See **The eXIf guard** below.

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

1. **The redundant closing lineto: COSMETIC, not a divergence.** `ttf-parser`
   emits an explicit lineto back to the contour start before `Z`; fontTools
   relies on `Z` to close. `Builder::close` drops that trailing lineto so the
   emitted path data reads like fontTools', which keeps the SVG diff small.
   It does NOT reach the raster. This WP originally claimed it did; WP-5.4's
   verifier disproved that by reverting the pop and measuring: the SVG changed
   (4,234,729 against 4,233,478 bytes) while the PNG was BYTE-IDENTICAL and the
   test still passed, with synthetic probes agreeing that fill and stroke render
   identically across miter-sharp, round-cap and curve-close cases. The earlier
   claim, and the "a fill-only probe is not evidence about stroked elements"
   lesson drawn from it, are both WITHDRAWN as unsupported.
2. **The white wordmark tail's parameters.** The tail is drawn three times (slug,
   orange, white). The orange uses `horizontal_scale=106.6, stroke_width=0.15`;
   the white uses `horizontal_scale=105.1, stroke_width=0.30`. Carrying the
   orange's values into the white produced `scale(0.02186133)` against Python's
   `scale(0.02155371)` and `stroke-width="7.3143"` against `"14.6286"`, and
   10,768 differing pixels in a band 428-966 x 221-325. Both are now read from
   the Python rather than inferred from the sibling call.

So divergence 2 alone accounts for all 10,768 differing pixels (bbox
428,221,967,326). After fixing it: zero differing pixels.

## The eXIf guard, fixed under an orchestrator grant

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

**Fixed by NARROWING, not deleting**, which was the instructed preference and is
the right one here: the guard now parses the eXIf blob's TIFF structure, reads
tag 274, and bails only when an orientation is present and is not 1. Other EXIF
content is ignored, which is what PIL does.

Narrowing was cleanly implementable: the eXIf chunk payload is a bare TIFF
header, so `exif_orientation` reads the byte order from `II`/`MM`, checks the
42 magic, walks IFD0's 12-byte entries and returns tag 274's SHORT value. No
dependency was added.

One honesty note about what the retained bail is FOR. Since PIL never applies
orientation on `convert("RGB")`, a naive decode matches PIL whatever the tag
says, so the bail is not a fidelity requirement. It is a conservative stop for
an image whose intended display differs from its stored pixels, which a human
should look at before it reaches a cover. That is worth keeping and worth
stating plainly rather than implying the port would otherwise diverge.

This also reached WP-5.5: its preflight port consumes `metrics.rs` and preflight
runs over the same cover art, so the fix unblocks that WP too.

## Metrics

| check | result |
|---|---|
| front cover raster, Rust port vs Python compiler | IDENTICAL, 0 of 4,335,040 pixels differ |
| pixmap sha256 | 4b4549e9b97ead363014cb94eb8ff3e6af4491c7f865bd0bba3fd665988190b2 |
| graded art pixels | IDENTICAL, 695de5df97203c550521c0fe, 1440x2160 |
| glyph outlines, fontTools vs ttf-parser | 834 of 834 identical rasters |
| resvg Python binding vs Rust crate | IDENTICAL both faces, 4,335,040 pixels each |
| markup skeleton, transforms and translates | identical to 8 decimal places |
| WP-5.3a oracle BEFORE the guard change | 5 of 5 tests pass, oracle digest c519fdfb764af26a9ff2664545eb846a, 12 fixtures |
| WP-5.3a oracle AFTER the guard change | 5 of 5 tests pass, oracle digest c519fdfb764af26a9ff2664545eb846a, unchanged |
| exif_orientation unit test | orientation 6 read as 6, orientation 1 read as 1, ExifOffset-only blob and non-EXIF bytes both None |
| full suite after the change | 11 test binaries, all ok |
| WP-5.3a oracle after the luma601 visibility change | 6 of 6 tests pass; expectation blob 39be9e815b4403a8bcd8b27c07944fe3daa29e31, byte-identical across commits 5a3fa71, 78711a5 and this one |
| zone statistics against PIL | top_mean 109.566899493971, top_stddev 40.232386208079, bottom_mean 128.222435631229, bottom_stddev 28.664079039767, all within 1e-9 |
| zone assertion discriminates | reverting to the per-mille formula fails it at top_mean 109.56702330964686 against 109.56689949397072, WHILE THE RASTER TEST STILL PASSES |

WP-5.3a's oracle covers all 14 images at its three levels (decoded pixels by
SHA256 against PIL's `convert("RGB")`, thumbnails pixel-for-pixel against
Pillow's LANCZOS, and every `PrintContrastAnalysis` field plus `adjusted`,
`unresolved` and the post-treatment analysis), plus the `tint_band` fixture and
the rounding oracle. Nothing moved: the committed expectation file is
byte-identical before and after, so WP-5.3a's verification is not invalidated.

## Commands

Stage the manuscripts the Python loader needs, then capture the reference:

    cp -R <repo>/editions/010/run-2026-09-13T01-34-51 editions/010/
    mkdir -p editions/010/articles
    for d in editions/010/run-2026-09-13T01-34-51/articles/*/; do \
      n=$(basename "$d"); cp "$d/final.md" "editions/010/articles/$n.md"; done

REPLAY HAZARD, worth knowing before the spy below looks broken: `compile()`
SKIPS regeneration when its outputs already exist, so running it a second time
into the same destination captures NOTHING through a spy on `Tree.from_str` and
reads as a broken method rather than a skipped step. Use a fresh destination
directory for every capture.

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

The test `mag/tests/cover_footer_caption.rs` and its oracle
`mag/tests/cover_footer_caption_expected.txt` are committed and green.

They were deliberately HELD OUT of the tree on the first submission, and that was
a decision rather than a mechanic: the pre-commit hook runs `cargo test` for
every agent, so committing a test that fails on a sibling module's guard would
have blocked every other work package in flight from committing anything. The
right move was to land the port, report the six-line blocker precisely, and hold
the test until the guard was fixed, which is what happened.

## Tool versions

python 3.12.11, uv 0.8.17, Pillow and fontTools via the project venv,
resvg-py 0.2.0 wrapping resvg/usvg 0.47.0, tiny-skia 0.12.0, fontdb 0.23.0,
rustybuzz 0.20.1, reportlab 5.0.0, rustc 1.96.0, and the crates added below.

## Cargo

Added, as the last step before landing, per rule 1a: `resvg =0.47.0`,
`usvg =0.47.0`, `tiny-skia =0.12.0`, `base64 0.22`. `ttf-parser 0.25` and
`png 0.18` were already present and are reused. The `Cargo.lock` check is in
## Verdicts.

Regenerate the committed zone oracle `mag/tests/cover_zone_expected.json`. This
derivation mirrors `_art_zones` at `src/magazine/cover.py:482` exactly, including
the `int()` truncations and the floor-divided crop offsets, and it reads the
tracked cover art so it needs no run directory:

    uv run python -c "
    import json
    from PIL import Image, ImageStat
    PAGE_WIDTH, PAGE_HEIGHT = 419.527559, 595.275591
    band_x = PAGE_WIDTH - 21.0
    path = 'editions/010/art/rounds/2026-09-13T01-40-20/cover-wildcard-sign-punched-v3.png'
    with Image.open(path) as source:
        image = source.convert('RGB')
    ratio = max(band_x / image.width, PAGE_HEIGHT / image.height)
    width, height = int(band_x / ratio), int(PAGE_HEIGHT / ratio)
    ox, oy = (image.width - width) // 2, (image.height - height) // 2
    image = image.crop((ox, oy, ox + width, oy + height))
    def stat(box):
        values = ImageStat.Stat(image.crop(box).convert('L'))
        return values.mean[0], values.stddev[0]
    top = stat((0, 0, image.width, int(image.height * 0.24)))
    bottom = stat((0, int(image.height * 0.72), image.width, image.height))
    json.dump({'bottom_mean': bottom[0], 'bottom_stddev': bottom[1],
               'top_mean': top[0], 'top_stddev': top[1]},
              open('mag/tests/cover_zone_expected.json', 'w'), indent=2, sort_keys=True)
    "

Verified to reproduce the committed file byte for byte: sha256
303e2e66aedddc073b55b56821ee836d6556dab8 before and after regeneration, `cmp`
clean. The numbers are PIL's own `ImageStat` output, not Rust output committed as
an expectation.

## What is and is not proven

PROVEN by committed tests: the front cover raster equals the Python compiler's
pixel for pixel, and the four zone statistics equal PIL's to within 1e-9. Both
assertions are against numbers PYTHON produced, and both were shown to
discriminate by reverting the code under them.

NOT PROVEN, and not claimed: the back cover (its SVG was captured and its raster
measured identical during the resvg feasibility work, but no committed test
covers it), the PDF writer, the other layout modes, and `design.toml` loading.

The first submission's evidence said the zone statistics were "proven against
Python" when the only assertion in the test was the final raster hash against a
committed constant. That was wrong, it is corrected here, and the missing
assertion now exists.

## Verdicts

No `mag parity` verdict: covers are outside the interior compared domain until
WP-5.4g, and the comparator cannot read cover pages until WP-0.2h.

Cargo.lock (name, version) delta: only gained; no entry removed, none changed.

## A defect can be invisible to any given oracle level

This WP produced two defects that are DUAL rather than alike, and the pair is a
stronger argument than either alone.

The transposed `horizontal_scale`/`stroke_width` pair on the white wordmark tail
was **invisible to structure and visible to pixels**. The Python draws that tail
three times, and the white pass uses 105.1/0.30 where the orange pass three lines
above it uses 106.6/0.15. Carrying the orange values into the white produced a
document whose markup skeleton diffed CLEAN on every transform, translate and
scale, and whose raster differed on 10,768 pixels at 428,221 to 967,326.

The zone-statistics luma formula was **invisible to pixels and visible only to a
direct assertion against Python's numbers**. It disagreed with `convert("L")` on
540 of 3,110,400 pixels and moved the zone means by 1.238e-04 and 5.652e-05, but
the thresholds it feeds sit far away (`bottom_mean < 105` against 128.22,
`bottom_std > 46` against 28.66), so nothing flipped and the raster hash matched.
It passed by aggregation. Reverting it now fails the zone assertion while the
raster test still passes, which is that gap made visible.

So the generalisation is not "compare pixels" and not "compare structure". It is
that **a defect can be invisible to any given oracle level**, and which level
blinds you is not predictable from the defect's kind: a wrong constant hid from
structure, a wrong formula hid from pixels. That is the argument for holding more
than one oracle level at once, which is what this WP now does — raster equality
for the document, and a direct numeric assertion for the statistics feeding its
decisions.

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

- The zone-statistics luma is now `metrics::luma601`, not a local copy. The
  first submission wrote its own per-mille formula
  `(r*299 + g*587 + b*114 + 500)/1000`, which is NOT what `convert("L")` does:
  PIL uses fixed point, `(r*19595 + g*38470 + b*7471 + 0x8000) >> 16`. On 010's
  cover art the two disagree on 540 of 3,110,400 pixels, shifting the zone means
  by 1.238e-04 (top) and 5.652e-05 (bottom). It was inert only because no
  threshold flipped, which is a pass by AGGREGATION rather than by correctness.
  `luma601` is now `pub(crate)` and imported, so there is one implementation.
  The visibility change is the only edit to `metrics.rs` beyond the eXIf work,
  and WP-5.3a's oracle is unmoved (see ## Metrics).
- `Fonts::load` reads the faces from `src/magazine/assets/fonts/`, the single
  copy the Architecture section sanctions while both engines coexist. WP-6.1
  relocates them.
- The port takes the four cover strings as inputs rather than deriving them, so
  it has no dependency on WP-5.4a and cannot race it. The caller supplies
  publication name, headline, date line, contributors and the two tab labels.
- `COVER_COMPILER_VERSION` is "10" in the Python and appears in proof.json. The
  port does not emit proof.json yet; whichever WP does must decide whether that
  version tracks the Python's.
