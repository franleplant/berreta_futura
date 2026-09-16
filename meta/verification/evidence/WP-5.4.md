# WP-5.4 cover compiler

## Base

6a9b5cf (art_directed), plan revision 18 at the time of the work; revision 19
landed during it and moved the four pure text helpers to WP-5.4a.

## Status

blocked

Not because the port is infeasible. Both make-or-break questions are answered
positively and the technical path is clear. Blocked because the WP as scoped
cannot be delivered as one work package, and a partial port presented as done
would be worse than a measured statement of what it takes. The measured gap and
a proposed split are below.

No code was written, so no commit message claiming a port was used, and no
Cargo change was made.

## Backend decision, and the measurement behind it

Decided: call the SAME libraries the Python path already calls, rather than
reimplementing or substituting.

- rasterizer: `resvg` 0.47.0, `usvg` 0.47.0, `tiny-skia` 0.12.0
- glyph outlines: `ttf-parser` 0.25
- PDF writing: still open, see the gap below

The Python side does not use a Python rasterizer. `resvg` on PyPI is
`resvg-py` by Brice Yan, a thin binding whose compiled `_resvg.cpython-312-
darwin.so` embeds the Rust crates. Their versions are recoverable from the
binary's build paths:

    fontdb-0.23.0  resvg-0.47.0  rustybuzz-0.20.1  tiny-skia-0.12.0  usvg-0.47.0

So "port the rasterizer to Rust" is not a port at all: it is calling the same
crate at the same version. That is what makes pixel parity reachable here where
WP-0.2f found it unreachable for the engines.

## Metrics

### Feasibility 1: resvg parity, PASS

Both cover faces of edition 010 were compiled by the Python compiler, the SVG
handed to `resvg.usvg.Tree.from_str` was captured verbatim, and the same SVG was
rendered by a Rust probe depending on `resvg =0.47.0` / `usvg =0.47.0` /
`tiny-skia =0.12.0`. Decoded RGBA compared through PIL on both sides:

| face | size | python rgba sha256 (24) | rust rgba sha256 (24) | result |
|---|---|---|---|---|
| front | 1748x2480 | 3f853a0a65b06dd5b912a001 | 3f853a0a65b06dd5b912a001 | IDENTICAL |
| back | 1748x2480 | beb601e1ff00de843e8a43b6 | beb601e1ff00de843e8a43b6 | IDENTICAL |

4,335,040 pixels per face, exact. Not "within a bound": equal.

### Feasibility 2: glyph outline parity, PASS

The cover SVG contains NO `<text>` elements. All typography is glyph outlines
emitted as `<path>` by fontTools' `SVGPathPen` (front 178 paths, back 312). So
`usvg` needs no font database for the cover SVG and font resolution cannot
diverge between the two sides.

The remaining question was whether Rust can produce those outlines. Compared
across the whole cover face, `ArchivoCondensed-Bold.ttf`, 834 glyphs: for each
glyph id, the `SVGPathPen` path string and the `ttf-parser` outline were each
wrapped in a minimal SVG and rasterized by the SAME resvg, and the pixmaps
hashed.

    glyphs 834  identical_raster 834  differ 0  parse_fail 0

The two representations differ textually and agree geometrically. fontTools uses
SVG shorthand (`H`, `V`, implicit lineto after `M`) and relies on `Z` to close;
ttf-parser is explicit and emits a closing lineto before `Z`. Both expand
TrueType's implied on-curve points to the same midpoints, which is the case that
matters: for glyph `A`, control points `324 452` and `317 480` yield the implied
on-curve point `320.5 466` on both sides.

Recorded as a method note, since it cost a wrong measurement: fontTools'
`RecordingPen` is NOT the right instrument for this comparison. It preserves the
raw TrueType point stream with implied on-curve points omitted, so it reports 714
of 834 glyphs differing where the rendered geometry is identical. `SVGPathPen` is
what production uses and what must be compared.

### What a cover PDF actually contains

Measured from `reader.pdf` page 1 and page 56, which are the merged cover faces.
This contradicts the expectation in the WP brief and changes the oracle.

1. two path fills: the white page rect and the orange tab band (front), or a
   single bled orange rect (back)
2. ONE full-page Form XObject carrying the resvg raster at `PRINT_DPI` 300,
   drawn edge to edge by `drawImage`
3. an INVISIBLE text layer, render mode 3

The glyph outlines are NOT paths in the PDF. They are baked into the raster
inside the Form XObject. So the visible marks are one image plus two rects, and
the brief's premise that covers carry outlines as paths is true of the SVG and
false of the PDF.

The consequence for raster parity is favourable: invisible text paints no
pixels, and there are no text shows contributing visible marks, so the
origin-snapping WP-0.2f measured cannot reach a cover raster. If the image
pixels match and the placement matrix matches, the rasters are identical by
construction.

### The invisible text layer, in detail

Both faces carry it, and it carries the real content.

| face | Tr modes present | fonts | shows | first strings |
|---|---|---|---|---|
| front (p1) | 3 only | /F1, /F2+0 | 5 | BERRETA FUTURA; THE SPEED LIMIT; FRANK RIETTA / ANTHROPIC / ... |
| back (p56) | 3 only | /F1, /F2+0 | 10 | LOOP; CLOSED; The patch shipped at night and the exploit came at ... |

It is a selectable-text layer: `_add_selectable_text_layer` and
`_add_selectable_back_text_layer` in `cover.py` draw the masthead, headline,
contributor deck and back-cover copy with `setTextRenderMode(3)` in
`Inter-Regular.ttf`, so a reader can select, copy and search the cover text that
is otherwise only pixels. This is why revision 19's decision to RECORD `Tr`
rather than fail loud is the right one for covers specifically: the invisible
layer is the only place the cover's real strings exist as text.

`/F1` is reportlab's default Helvetica, set by `BT /F1 12 Tf 14.4 TL ET` at the
very top of the stream and never used to show anything.

Which of the two tracer stops fires first: by stream order `/F1` is selected
before any `3 Tr` appears, and WP-5.3d measured the failure empirically as
"font Helvetica lacks ToUnicode", so the standard-14 decode is the first stop
and the render mode the second. Both are real and independent. I did not execute
the tracer against a cover page myself; the ordering above is stream order plus
WP-5.3d's measurement, not my own run.

### Branch enumeration, read from cover.py

`cover.py` is 1620 lines, 56 functions and methods, 24 raise sites.

Layout modes dispatch at `:395`, defaulting to `framed` when unset:

| mode | reached by 010 | covered how |
|---|---|---|
| `footer_caption` | YES, 010 uses it | the 010 oracle |
| `framed` | no | needs a fixture edition |
| `honored_plate` | no | needs a fixture edition |
| unknown mode refusal (`:400`) | no | needs a fixture |

Branches 010 cannot reach, beyond layout mode, read from the Python rather than
from the corpus:

- the missing-glyph refusal in `_FontOutliner.outline` and `.measure`: any
  character absent from the bundled face. 010's cover strings are all ASCII
  capitals present in Archivo Condensed Bold.
- `ink_extent` on a glyph with no contours (`_glyph_bounds` returning None)
- the art-analysis path at `:484` (`Image` + `ImageStat`) for art whose
  statistics differ from 010's single cover image
- the back-cover statement fitting loop, which shrinks between
  `statement_max_size` 24.0 and `statement_min_size` 18.0; 010 exercises one
  outcome of that search
- `_wrap` at more than one line count per field
- `replace_outer_pages` / `replace_first_page` argument variants; WP-0.2c
  already calibrated the merge and found inner pages byte-passthrough clean

## Commands

All probes are reproducible from a worktree at ## Base plus the untracked run
directory. Manuscripts must be staged first, because `load_edition` resolves
`editions/010/articles/<id>.md` and the run directory stores them as
`<id>/final.md`:

    cp -R <repo>/editions/010/run-2026-09-13T01-34-51 editions/010/
    mkdir -p editions/010/articles
    for d in editions/010/run-2026-09-13T01-34-51/articles/*/; do \
      n=$(basename "$d"); cp "$d/final.md" "editions/010/articles/$n.md"; done

Capture the raster SVG both faces hand to resvg, and compile the references:

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
        cap.setdefault('svgs', []).append(s)
        return orig(s, o)
    resvg.usvg.Tree.from_str = spy
    P = Path('<probe>')
    cc = CoverCompiler(root)
    cc.compile(ed, P/'front'); cc.compile_back(ed, P/'back')
    for i, s in enumerate(cap['svgs']):
        (P/f'raster_{i}.svg').write_text(s, encoding='utf-8')
        print(i, len(s.encode()), '<text' in s, '<image' in s, s.count('<path'))
    "

Render those SVGs with the Python binding and hash decoded RGBA:

    uv run python -c "
    from pathlib import Path; import resvg, hashlib, io
    from PIL import Image
    P = Path('<probe>')
    for i in (0,1):
        t = resvg.usvg.Tree.from_str((P/f'raster_{i}.svg').read_text(), resvg.usvg.Options.default())
        png = resvg.render(t, (1,0,0,0,1,0))
        (P/f'py_{i}.png').write_bytes(png)
        im = Image.open(io.BytesIO(png)).convert('RGBA')
        print(i, im.size, hashlib.sha256(im.tobytes()).hexdigest())
    "

The Rust probe is a throwaway cargo project outside the repo, `Cargo.toml`
depending on `resvg = "=0.47.0"`, `usvg = "=0.47.0"`, `tiny-skia = "=0.12.0"`,
`ttf-parser = "0.25"`, `sha2 = "0.10"`, with three binaries: `rsprobe` (render an
SVG, write PNG, hash the pixmap), `allglyphs` (dump every glyph outline), and
`rastercmp` (per glyph, rasterize the fontTools path string and the ttf-parser
outline through the same resvg and compare pixmap hashes). Full sources are in
the orchestrator transcript for this WP; they are throwaway spike code and were
not committed, per the Phase 1 spike convention.

Recover the binding's crate versions:

    strings .venv/lib/python3.12/site-packages/resvg/_resvg.cpython-312-darwin.so \
      | grep -oE "cargo/registry/src/[^/]+/(resvg|usvg|tiny-skia|fontdb|rustybuzz)-[0-9][^/]*" \
      | sed 's|.*/||' | sort -u

Cover PDF anatomy and the invisible layer:

    uv run python -c "
    import pypdf, re
    r = pypdf.PdfReader('<render>/en/reader.pdf')
    for idx in (0, len(r.pages)-1):
        c = r.pages[idx].get_contents().get_data()
        print(idx+1, sorted(set(re.findall(rb'(\d+)\s+Tr', c))),
              list(r.pages[idx]['/Resources'].get('/Font',{}).keys()),
              len(re.findall(rb'\((.*?)\)\s*Tj', c)))
    "

## Tool versions

python 3.12.11, uv 0.8.17, fontTools via the project venv, pypdf 6.14.2,
Pillow via the project venv, resvg-py 0.2.0 wrapping resvg/usvg 0.47.0,
tiny-skia 0.12.0, fontdb 0.23.0, rustybuzz 0.20.1, reportlab 5.0.0,
rustc 1.96.0, cargo probe crates resvg/usvg 0.47.0, tiny-skia 0.12.0,
ttf-parser 0.25.

## Verdicts

No parity verdict.json was produced: the comparator's display-list path cannot
read cover pages today (two independent fail-loud stops, both recorded above,
both owned by WP-0.2h), and no Rust cover compiler exists yet to compare
against.

## The measured gap

What remains after the two feasibility results:

1. the SVG generator: layout arithmetic for three modes, the outliner wrapper,
   text wrapping and fitting, art embedding, and the SVG shell. This is the bulk
   of the 1620 lines and the bulk of the 56 functions.
2. art image processing: `Image` + `ImageStat` contrast analysis at `:484` and
   the resize at `:1065`. WP-5.3a already proved PIL-exact decoding, LANCZOS and
   analysis in `mag/src/critic/metrics.rs`, so this should CONSUME that module
   rather than re-port it, exactly as revision 14 directs WP-5.5 to do.
3. the PDF writer: reportlab is Python and has no Rust equivalent in tree. A
   Rust writer must emit two path fills, one Form XObject image, and an
   invisible text layer with an embedded Inter subset. The subset is the awkward
   part: matching reportlab's subsetting byte for byte is the "reproduce a hack
   to stay equal to a tool we are deleting" category this plan has rejected
   three times, so the oracle for the text layer should be its CONTENT (the
   strings, positions, sizes, render mode) rather than the subset bytes. That is
   a scope question for the plan, not a WP's call.
4. fixture editions for `framed` and `honored_plate`, and the unknown-mode
   refusal.

## Residuals

- The WP-5.4 bullet's oracle says "raster agreement within WP-0.2f's derived
  bound". WP-0.2f BLOCKED and produced no bound, and revision 15 withdrew the
  raster guard from Tier E entirely. So the bullet cites a quantity that does
  not exist. For covers the right oracle is stronger than a bound anyway: the
  visible content is one image plus two rects, so raster EQUALITY is reachable,
  and this WP measured that the underlying rasterizer is bit-exact. The bullet
  needs rewording against revision 15+.
- Both cover faces carry `3 Tr` invisible text holding the real masthead,
  headline, contributor deck and back-cover copy. Revision 19 makes this
  recorded rather than fail-loud, which is necessary for WP-5.4g: without it the
  cover pages enter the Tier E compared domain as permanent fail-loud stops.
- `/F1` Helvetica is selected and never shown. WP-0.2h's standard-14 decode has
  to tolerate a font that is set but never used.
- `mag/src/cover/text.rs` belongs to WP-5.4a (revision 19). Nothing here claims
  it; a future `mag/src/cover/mod.rs` must leave room for `mod text;`.
- The Python compiler stages manuscripts from the run directory into
  `editions/010/articles/<id>.md`. `load_edition` refuses without them, which is
  a real prerequisite for any cover oracle and is not obvious from the WP text.
- `COVER_COMPILER_VERSION` is `"10"` and appears in proof.json; a port must
  decide whether it tracks the Python version or starts its own, and the oracle
  must not compare it accidentally.
