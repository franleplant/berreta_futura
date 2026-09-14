# WP-5.3a critic raster metrics

## Base

6378ae3 (verify(parity): WP-0.0c accepted)

## Commands

Worktree isolation, per orchestrator policy:

    git worktree add /Users/franguijarro/.claude/jobs/7d99e27f/tmp/wp53a HEAD

Fixture generation (deterministic, regenerates the committed PNGs byte for byte):

    uv run python -c "
    from PIL import Image
    import os
    d='mag/tests/critic_metrics_fixtures'
    def save(im,name): im.save(os.path.join(d,name),format='PNG',optimize=False)
    save(Image.new('RGB',(600,400),(255,255,255)),'pure_white.png')
    save(Image.new('RGB',(600,400),(0,0,0)),'pure_black.png')
    save(Image.new('RGB',(600,400),(128,128,128)),'uniform_gray.png')
    save(Image.new('RGB',(3,2),(10,200,30)),'tiny.png')
    save(Image.new('L',(600,400),200),'gray8.png')
    save(Image.new('LA',(600,400),(200,128)),'gray_alpha.png')
    im=Image.new('RGBA',(600,400),(255,0,0,0))
    for y in range(200):
        for x in range(600): im.putpixel((x,y),(0,255,0,255))
    save(im,'rgba_alpha.png')
    im=Image.new('RGB',(2000,40))
    px=im.load()
    for y in range(40):
        for x in range(2000): px[x,y]=((x*7+y*13)%256,(x*3)%256,(y*29+x)%256)
    im.save(os.path.join(d,'extreme_aspect.png'),format='PNG',optimize=False)
    im=Image.new('RGB',(2401,1351))
    px=im.load()
    for y in range(1351):
        for x in range(2401): px[x,y]=((x*11+y*5)%256,(x+y)%256,(x*y)%256)
    im.save(os.path.join(d,'odd_reduce.png'),format='PNG',optimize=False)
    im=Image.new('RGB',(600,400),(255,255,255))
    for y in range(20,60):
        for x in range(600): im.putpixel((x,y),(211,211,211))
    save(im,'low_contrast.png')
    p=Image.new('P',(600,400))
    p.putpalette([255,255,255, 211,211,211, 0,0,255]+[0]*(253*3))
    for y in range(400):
        for x in range(600): p.putpixel((x,y), 1 if 20<=y<60 else 0)
    p.save(os.path.join(d,'palette_trns.png'),format='PNG',transparency=0)
    "

Oracle generation (writes `mag/tests/critic_metrics_expected.json`):

    uv run python -c "
    import hashlib, json, glob
    from PIL import Image, ImageOps
    from src.magazine.image_contrast import analyze_print_contrast, prepare_print_image
    from pathlib import Path
    figures=['library/sources/an-alignment-assessment-of-recent-cybersecurity-415f8f1a/media/001.png','library/sources/the-third-era-of-ai-software-development-7395f18d/media/001.png','library/sources/towards-self-driving-codebases-3fd7b9ca/media/004.png']
    fixtures=sorted(glob.glob('mag/tests/critic_metrics_fixtures/*.png'))
    def row(p):
        with Image.open(p) as o:
            mode=o.mode
            im=ImageOps.exif_transpose(o).convert('RGB')
        src=hashlib.sha256(im.tobytes()).hexdigest()
        t=im.copy(); t.thumbnail((512,512), Image.Resampling.LANCZOS)
        a=analyze_print_contrast(Path(p)); pr=prepare_print_image(Path(p))
        return {'path':p,'source_mode':mode,'source_size':list(im.size),'source_sha256':src,'thumb_size':list(t.size),'thumb_sha256':hashlib.sha256(t.tobytes()).hexdigest(),'analysis':a.to_dict(),'adjusted':pr.adjusted,'after':pr.after.to_dict(),'unresolved':pr.unresolved}
    data={'figures':[row(p) for p in figures],'fixtures':[row(p) for p in fixtures]}
    open('mag/tests/critic_metrics_expected.json','w').write(json.dumps(data,indent=1,sort_keys=True)+'\n')
    "

Rounding oracle (writes `mag/tests/critic_metrics_rounding_expected.json`):

    uv run python -c "
    import json
    half=[0.5,1.5,2.5,3.5,-0.5,60.5,59.5,0.0,100.0,12.5,13.5,0.4999999999,0.5000000001,99.5,98.5]
    places=[(0.8043045,6),(0.1234565,6),(0.1234575,6),(2.3565,3),(2.3575,3),(0.0000005,6),(21.0,3),(1.0005,3),(0.9999995,6),(0.0,6),(0.052578,6),(2.192,3)]
    data={'half_even':[{'value':v,'expected':round(v)} for v in half],'places':[{'value':v,'places':n,'expected':round(v,n)} for v,n in places]}
    open('mag/tests/critic_metrics_rounding_expected.json','w').write(json.dumps(data,indent=1)+'\n')
    "

Verification:

    cd mag && cargo fmt && cargo clippy --all-targets -- -D warnings && cargo test

Near-threshold survey:

    python3 -c "
    import json
    d=json.load(open('mag/tests/critic_metrics_expected.json'))
    th={'minimum_mark_contrast_ratio':2.0,'mark_pixel_ratio':0.001}
    worst=1e9
    for grp in ('figures','fixtures'):
      for r in d[grp]:
        for k,t in th.items(): worst=min(worst,abs(r['analysis'][k]-t)/t)
    print('smallest relative margin: %.4e'%worst)
    "

## Tool versions

python 3.12.11, uv 0.8.17, Pillow 12.3.0, rustc 1.96.0, png crate 0.18.

## Metrics

**Oracle result: exact equality on every metric, not merely within tolerance.** The test
compares with `!=` on `f64`, so the observed relative delta against
`critic_metric_tolerances.float_relative_epsilon` (1e-6) is **0.0** for all 14 images
(3 edition-010 figures plus 11 fixtures), and integer-valued fields are exact as the
tolerance requires. The comparison is stronger than the tolerance permits; the tolerance
was not consumed.

Equality holds at three levels, each asserted separately:

| level | assertion | result |
|---|---|---|
| decode | sha256 of the RGB buffer equals PIL `convert("RGB")` | 14/14 equal |
| resample | sha256 of the thumbnail equals PIL `thumbnail(LANCZOS)` | 14/14 pixel-identical |
| metrics | all four `PrintContrastAnalysis` fields, plus `adjusted`, `unresolved`, `after` | 14/14 equal |

Edition 010 figures, with the PIL mode each exercises:

| figure | mode | size | paper | mark | contrast |
|---|---|---|---|---|---|
| an-alignment-assessment .../001.png | RGB | 2000x1418 | 0.804305 | 0.125414 | 2.711 |
| the-third-era-of-ai .../001.png | P | 2400x1350 | 0.65939 | 0.052578 | 2.356 |
| towards-self-driving-codebases/004.png | RGBA | 2400x1350 | 0.962219 | 0.02219 | 2.192 |

**Near-threshold: none.** Smallest relative margin between any observed metric and its
decision threshold (`MIN_PRINT_CONTRAST_RATIO` 2.0, `MIN_MARK_PIXEL_RATIO` 0.001) is
**9.6e-2**, four orders of magnitude outside the 1e-5 near-threshold window. No metric
owned by this WP requires a near-threshold fixture. WP-0.2d's one near-threshold metric
(`pages[39].largest_void.height_points`) belongs to WP-5.3b, not here.

**Discriminating probes.** Each ported behaviour was reverted in place and the suite
re-run, to prove the tests are not vacuously green:

| probe | change | result |
|---|---|---|
| A | skip `reduce()` before resampling | figures and fixtures FAIL |
| B | drop `reduce()`'s rounding amend (`scale/2`) | figures and fixtures FAIL |
| C | drop the coefficient rounding (`0.5 +` before truncation) | figures and fixtures FAIL |
| D | half-even to half-down in the luminance histogram | images pass, **rounding test FAILS** |

Probe D is recorded honestly: no luminance in this corpus lands exactly on a `.5`
histogram boundary, so the image oracles cannot discriminate Python's banker's rounding.
That is why `rounding_matches_python_round` tests `round_half_even` and `round_places`
directly against a committed Python oracle including exact-half cases; probe D fails that
test. Two cases in it are the kind a naive port gets wrong: `round(2.3575, 3)` is `2.357`
and `round(1.0005, 3)` is `1.0`, both because the decimal literal is not exactly
representable.

`cargo test`: 92 tests across 8 binaries, all passing; the metrics suite runs in 9.8 s.

## Verdicts

No `mag parity` verdicts: per the Phase 5 preamble this WP's oracle shells the pinned
tools from `cargo test` and does not use the comparator.

Committed oracle digests:

- `mag/tests/critic_metrics_expected.json` covers 3 figures + 11 fixtures
- `mag/tests/critic_metrics_rounding_expected.json` covers 15 half-even + 12 places cases

## Residuals

**Scope finding, for the orchestrator and WP-5.3b.** `image_contrast.py` is not used by
`render_critic.py` at all. Its consumers are `preflight.py:9,110`, `render.py:14,701,981`
(the reportlab engine, deleted at WP-6.1 and never ported) and
`weasyprint_adapter.py:1790,1804` (replaced by `mag/src/typeset/`). Its metrics land in
**preflight.json** under `figures[*].print_contrast`, not in render-critic.json. Only
`concurrency.py` feeds the critic (`render_critic.py:22` imports `ordered_map` and
`worker_count`). So the plan's grouping of these two modules under "critic raster
metrics" is accurate for `concurrency.py` and misleading for `image_contrast.py`; the
latter is a preflight and render-staging concern, and WP-5.5 is its real consumer.
WP-5.3b's own raster helpers (`render_critic.py:968,1051,1084,1139,1250` use PIL
grayscale, histograms, `ImageChops.difference` and a LANCZOS resize) are a separate body
of work that this WP does not cover; they are what the tolerances surveyed over
render-critic.json actually apply to.

**Module registration.** Adds `mag/src/critic.rs` (`pub mod metrics;`) and
`#[allow(dead_code)] mod critic;` in `mag/src/main.rs`, matching the pattern WP-5.1a
established for `mod model;`. Nothing in the binary consumes it yet; WP-5.3b and WP-5.5
should remove the allow when they wire it in.

**Branches edition 010 cannot reach, covered by fixture.** 010's three figures are all
large, all light-background, all `needs_treatment: false`, so the corpus alone reaches
neither the enhancement path nor any degenerate image. Fixtures cover: pure white (no
marks, `contrast` falls back to 21.0), pure black (background estimate falls back to 1.0),
uniform mid gray (dominant mass below the luminance floor, the `dominant/total < 0.18`
return), a 3x2 image (thumbnail early-return, no resampling at all), grayscale `L`,
grayscale+alpha `LA`, `RGBA` with a fully transparent half (proving alpha is dropped and
never composited, which is PIL's `convert("RGB")` semantic), a 2000x40 extreme aspect
(asymmetric reduce factor 1x2), a 2401x1351 odd-dimension image (`reduce()` remainder
columns, rows and corner, which no other input reaches), and two images that actually
trigger the enhancement path (`low_contrast.png` and `palette_trns.png` both come back
`adjusted: true`). Two fixtures were initially uniform and therefore passed vacuously;
`extreme_aspect.png` was regenerated with a non-uniform pattern and `odd_reduce.png` added
precisely so the reduce paths are discriminating rather than decorative.

**Fail-loud coverage.** `decode_rgb` refuses rather than guesses: any PNG bit depth other
than 8, any colour type outside {Rgb, Rgba, Grayscale, GrayscaleAlpha} after EXPAND, and
any file carrying EXIF metadata (because `ImageOps.exif_transpose`'s orientation handling
is not ported and a rotated source would silently produce different metrics). No 010
image carries EXIF; all three are 8-bit and non-interlaced.

**Floating point, and where the port deliberately differs in form but not in result.**
The sRGB linear table, the luminance sum and the contrast ratio are evaluated in the same
order as Python. The resampler is an exact port of Pillow's fixed-point path
(`PRECISION_BITS` 22, coefficients rounded half-away-from-zero into `i32`, accumulator
seeded at `1 << (PRECISION_BITS - 1)`, arithmetic right shift, clamp to 0..255), so its
output is integer-identical rather than merely close. `Image.blend`'s extrapolation branch
is reproduced in `f32`, matching the C, because the factors in use (1.4 to 3.0) all exceed
1.0 and that branch computes in `float`. `round_places` formats to the requested decimals
and parses back, which reproduces Python's correctly-rounded half-even `round(x, n)`; it
is verified against a Python oracle rather than assumed.

**Two Pillow behaviours the port had to reproduce and which are easy to miss.**
`thumbnail`'s `reducing_gap=2.0` default runs `reduce()` (an integer box downsample)
before the LANCZOS resize whenever `int(dimension / target / 2) > 1`. Edition 010's
2000x1418 figure has factor 1 and needs no reduce, while both 2400x1350 figures have
factor 2 and do; that difference is exactly why the first implementation matched one
figure pixel-for-pixel and missed the other two. And because `_open_rgb` converts to RGB
*before* `thumbnail`, PIL's "mode P or 1 forces NEAREST" and "LA/RGBA premultiply" rules
never fire, so the palette and RGBA figures are resampled as ordinary RGB.

**Not ported.** `prepare_print_image` returns the enhanced pixels as `Rgb` rather than
encoded PNG bytes. The Python writes `io.BytesIO` PNG output for the caller to stage;
reproducing PNG encoder bytes is neither required by any oracle nor meaningful (the
analysis is computed on the in-memory candidate, not on a re-decoded file), and the
consumer that stages the payload is WP-5.5. Python's `lru_cache(maxsize=64)` on
`_prepared_bytes` is not reproduced: it is a memoisation detail with no observable effect
on results.

## Status

done
