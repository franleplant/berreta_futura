# WP-5.4c cover PDF writer

## Base

Parent `62e665a`, plan revision 53. Depends on WP-5.4 (accepted, `01975a3`/`c084e16`,
verify `6702c7c`), WP-5.4a (accepted, verify `443aaa8`) and WP-5.4b (accepted,
verify `03532ad`). This WP consumes only `materialize` and the three layout
names.

Owns: `mag/src/cover/pdf.rs`, the `pub mod pdf;` line in `mag/src/cover.rs`,
`mag/tests/cover_pdf.rs`, `mag/tests/cover_pdf_front_stream_expected.txt`,
`mag/tests/cover_pdf_back_stream_expected.txt`,
`mag/tests/cover_pdf_widths_expected.txt`, this file.

## Commands

Both commands below are run from a repository root and neither names a
developer-specific path; the first creates its own scratch directory with
`mktemp -d` and the second writes nothing. They were extracted programmatically
from this finished file and replayed in a clean shell from a repository root
that is NOT the one they were developed in (the `wp54c-wt` worktree rather than
the main checkout, where the first built its own virtualenv from scratch); the
replay's output is quoted verbatim under `## Verdicts`.

The oracle drives the REAL Python compiler and regenerates every committed
expectation in this WP: the three rendered page hashes, the two normalized
content streams, and the font widths.

Edition 010's manuscripts live in an untracked run directory, so `load_edition`
cannot run from a clean checkout. The oracle therefore builds the same stand-in
WP-5.4b uses, carrying exactly the attributes the cover compiler reads. The
stand-in is VALIDATED, not assumed, by the second command.

```
set -o pipefail
OUT=$(mktemp -d); echo "scratch: $OUT"
uv run python - "$OUT" <<'ORACLE'
import sys, re, hashlib, subprocess
sys.path.insert(0, "src")
from pathlib import Path
from types import SimpleNamespace
from pypdf import PdfReader
from PIL import Image
from magazine.cover import CoverCompiler

out = Path(sys.argv[1])
ART = Path("editions/010/art/rounds/2026-09-13T01-40-20/cover-wildcard-sign-punched-v3.png")
AUTHORS = ["FRANK RIETTA","ANTHROPIC","DARIO AMODEI","SANTI RUIZ","MICHAEL TRUELL",
           "WILSON LIN","DEEPSEEK-AI","JON LEE, CHAOMIN YU, BEN RIES"]
PREAMBLE = "1 0 0 1 0 0 cm  BT /F1 12 Tf 14.4 TL ET"

def edition(layout, language="en"):
    return SimpleNamespace(
        identifier="010", language=language, issue_number=10, place="Buenos Aires",
        publication_name="Berreta Futura", publication_date="2026-09-13",
        title="The Speed Limit",
        cover={"layout": layout, "headline": "The Speed Limit"},
        cover_art=ART,
        articles=[SimpleNamespace(author=a) for a in AUTHORS],
    )

def normalize(pdf):
    data = PdfReader(pdf).pages[0].get_contents().get_data().decode("latin-1")
    data = re.sub(r"/FormXob\.[0-9a-f]{32}|/Cover", "/IMG", data)
    data = re.sub(r"/F2\+0|/Inter", "/FONT", data)
    lines = [l.rstrip() for l in data.split("\n")]
    return "\n".join(l for l in lines if l and l != PREAMBLE) + "\n"

def page_sha(pdf):
    stem = pdf.with_suffix("")
    subprocess.run(["pdftoppm","-r","72","-png","-singlefile",str(pdf),str(stem)], check=True)
    return hashlib.sha256(Image.open(f"{stem}.png").tobytes()).hexdigest()

compiler = CoverCompiler(Path("."))
for layout in ["footer_caption","framed","honored_plate"]:
    ed = edition(layout)
    pdf = out / f"{layout}.pdf"
    compiler._svg_to_pdf(compiler._materialize_svg(ed).encode("utf-8"), pdf, ed, face="front")
    print(f"{layout:15s} {page_sha(pdf)}")

ed = edition("footer_caption")
(out / "front_stream.txt").write_bytes(normalize(out / "footer_caption.pdf").encode("latin-1"))
back = out / "back.pdf"
compiler._svg_to_pdf(compiler._materialize_svg(ed).encode("utf-8"), back, ed, face="back")
(out / "back_stream.txt").write_bytes(normalize(back).encode("latin-1"))

font = PdfReader(out / "footer_caption.pdf").pages[0]["/Resources"]["/Font"]["/F2+0"].get_object()
first, widths = font["/FirstChar"], font["/Widths"]
(out / "widths.txt").write_text("".join(f"{c} {widths[c-first]}\n" for c in range(32,127)))
print("front_stream bytes", (out/"front_stream.txt").stat().st_size)
print("back_stream  bytes", (out/"back_stream.txt").stat().st_size)
print("widths rows", len((out/"widths.txt").read_text().splitlines()))
ORACLE
for f in front_stream back_stream; do
  cmp "$OUT/$f.txt" "mag/tests/cover_pdf_${f%_stream}_stream_expected.txt" && echo "$f fixture identical"
done
cmp "$OUT/widths.txt" mag/tests/cover_pdf_widths_expected.txt && echo "widths fixture identical"
```

The stand-in validation. It reproduces WP-5.4's accepted SVG raster hash, an
oracle accepted before this WP existed, so the stand-in is not assumed faithful.
Per rule 9's citation clause the expected value is re-derived here rather than
quoted from WP-5.4:

```
set -o pipefail
uv run python - <<'CHECK'
import sys, re, io, hashlib
sys.path.insert(0, "src")
from pathlib import Path
from types import SimpleNamespace
from magazine.cover import CoverCompiler, PAGE_WIDTH, PAGE_HEIGHT
import resvg
from PIL import Image

ART = Path("editions/010/art/rounds/2026-09-13T01-40-20/cover-wildcard-sign-punched-v3.png")
AUTHORS = ["FRANK RIETTA","ANTHROPIC","DARIO AMODEI","SANTI RUIZ","MICHAEL TRUELL",
           "WILSON LIN","DEEPSEEK-AI","JON LEE, CHAOMIN YU, BEN RIES"]
ed = SimpleNamespace(
    identifier="010", language="en", issue_number=10, place="Buenos Aires",
    publication_name="Berreta Futura", publication_date="2026-09-13",
    title="The Speed Limit",
    cover={"layout": "footer_caption", "headline": "The Speed Limit"},
    cover_art=ART, articles=[SimpleNamespace(author=a) for a in AUTHORS])

svg = CoverCompiler(Path("."))._materialize_svg(ed).encode("utf-8")
w = round(PAGE_WIDTH/72*300); h = round(PAGE_HEIGHT/72*300)
out = re.sub(rb'width="[^"]+" height="[^"]+"', f'width="{w}" height="{h}"'.encode(), svg, count=1)
for slot in (b"paper", b"edge-tab", b"field"):
    out = re.sub(rb'(<rect data-slot="'+slot+rb'"[^>]*?) fill="[^"]+"', rb'\1 fill="none"', out, count=1)
tree = resvg.usvg.Tree.from_str(out.decode("utf-8"), resvg.usvg.Options.default())
im = Image.open(io.BytesIO(resvg.render(tree, (1,0,0,0,1,0)))).convert("RGBA")
px = bytearray(im.tobytes())
for i in range(0, len(px), 4):
    a = px[i+3]
    if a != 255:
        px[i]=(px[i]*a+127)//255; px[i+1]=(px[i+1]*a+127)//255; px[i+2]=(px[i+2]*a+127)//255
print("stand-in SVG raster sha256:", hashlib.sha256(bytes(px)).hexdigest())
print("WP-5.4 recorded            : 4b4549e9b97ead363014cb94eb8ff3e6af4491c7f865bd0bba3fd665988190b2")
CHECK
```

Tests: `cargo test --test cover_pdf`, `cargo test`, `cargo fmt --check`,
`cargo clippy --all-targets -- -D warnings`, all run in `mag/`.

## Tool versions

rustc 1.96.0, lopdf 0.45.0, flate2 1.1.10, ttf-parser 0.25, png 0.18,
resvg/usvg 0.47.0 and tiny-skia 0.12.0 (all three pinned with `=`).
python 3.12.11 via `uv run` (Unicode 15.0.0; the system `python3` is 3.9.6 on
Unicode 13.0.0 and must not be used), reportlab 5.0.0, pypdf 6.14.2.
pdftoppm (poppler) 25.08.0. No `mag parity` run was needed, so no `out_dir` was
written and the concurrent-verdict hazard does not apply to any number here.

## Metrics

### Three oracles, because each is blind to what the others see

The cover PDF has a visible layer (two or three `re f*` fills plus one full-page
image) and an invisible layer (the selectable text, drawn in render mode
`3 Tr`). A rendered-page comparison CANNOT see the invisible layer at all: the
page hash is identical whether the text is present or absent, which is measured
below, not argued. So this WP carries three oracles and the discrimination table
shows each catching a class the others miss.

**Oracle 1, rendered page.** `pdftoppm -r 72 -png -singlefile`, then sha256 of
the decoded RGB. Cardinality: 3 layouts, 420x596 px each, 750,960 bytes hashed
per layout.

| layout | expected (Python) | Rust |
|---|---|---|
| `footer_caption` | `5f498b2a9cbab4b8a1c651bd19f908f7e31a0cc3b4e7b6c15b21819a5d8dd1ef` | equal |
| `framed` | `330ae10cf0dcae7163d5389c502284d7aeb1818ed7a0503f37120adf2ef67120` | equal |
| `honored_plate` | `02d379d867f748b9efe45a98abcdd3546bb8b65e43d8b8cfbb75e2d1af82e453` | equal |

All three matched on the first run, with no tuning. The test accumulates
mismatches rather than asserting inside the loop, so a failure reports all three
layouts and not only the first; perturbation G below confirms it prints
`3 of 3` with three distinct hashes.

**Oracle 2, content stream.** The page's decoded content stream, normalized and
compared as BYTES against a fixture that is the Python compiler's own output.
Cardinality: front 768 bytes over 15 lines, back 627 bytes over 13 lines; 5 text
shows and 2 fills on the front, 5 shows and 1 fill on the back.

| face | fixture | Rust |
|---|---|---|
| front (`footer_caption`) | `cover_pdf_front_stream_expected.txt` | equal, byte for byte |
| back | `cover_pdf_back_stream_expected.txt` | equal, byte for byte |

Every operator, coordinate, point size, horizontal scale, character-space value,
render mode, leading and string literal agrees to the byte, in paint order.

**Oracle 3, the shared Tier E tracer.** `parity::display::extract` over both
PDFs, then `compare_display`, `compare_glyphs` and `compare_color`. This is the
instrument WP-5.4g will point at the cover pages, and running it here is what
the WP's brief means by "display-list equality". Measured at parent `62e665a`
on `footer_caption`:

| clause | result | cardinality |
|---|---|---|
| `compare_display` | pass | 8 elements against 8, 0 pages differing |
| `compare_glyphs` | pass | 166 glyphs over 5 shows, worst ratio 0.0, worst excess 0.000000 pt, 0 violations |
| `compare_color` | pass | 7 entries compared, 0 pages differing |

The glyph clause is EXACT: worst per-glyph difference 0.000000 pt across all 166
glyphs, not merely within the bound. Because it is a one-off measurement against
an artifact Python produces at run time, it is not a committed test; what IS
committed are the two properties whose absence made it fail, below.

### Three defects the tracer found, all mine, all class A

Running oracle 3 is what turned this WP from "looks right" into "is right". It
refused my PDF outright, and fixing that exposed two more. All three are class A
port-fidelity gaps: Rust differed, Python was right, and the fix is to match
Python. None is a product defect, so none needs a correct-value regression test
in the class B sense.

| # | defect | how it surfaced | fix | committed guard |
|---|---|---|---|---|
| 1 | no ToUnicode CMap on the embedded font | tracer REFUSED the file: `operator Tf: loading font Inter: font Inter-Regular lacks ToUnicode and is not a standard-14 text face` | emit a ToUnicode CMap over WinAnsi | `every_win_ansi_code_round_trips_through_the_to_unicode_cmap` |
| 2 | `/Widths` serialized at f32 precision, not reportlab's `fp_str` precision | after fix 1 the tracer READ the file, and `compare_glyphs` FAILED on 2 of 5 shows | route every PDF real through the `fp` port | `the_font_widths_serialize_as_the_python_compiler_serializes_them` |
| 3 | literals emitted as UTF-8 under a `/WinAnsiEncoding` declaration, and `/Widths` built from Latin-1 | reading the font dictionary while fixing 1 and 2 | encode to WinAnsi bytes, refuse the unrepresentable | `text_outside_win_ansi_is_refused_rather_than_written_wrong` |

Defect 2 is the one worth dwelling on. `287.5977` against `287.59766` is the
same number to eleven significant figures, invisible to both other oracles and
to any renderer, and it broke the gate's per-glyph shape constraint on 36 of the
95 ASCII widths. It is a precise instance of the plan's own generalisation that
a defect can be invisible at any given oracle level: oracles 1 and 2 could not
see it, and only the tracer could.

Defect 3 never fires on edition 010, whose cover text is entirely ASCII, where
WinAnsi and UTF-8 coincide. It would have fired on the first accented character.

A fourth, smaller error was found while asserting the CMap's cardinality:
`char::from_u32(0)` returns `Some('\0')`, so the five codes WinAnsiEncoding
leaves undefined (`0x81`, `0x8D`, `0x8F`, `0x90`, `0x9D`) were being mapped to
U+0000. The CMap now carries 219 entries rather than 224, and the test asserts
both the count and the absence of those five codes.

### A test of mine that could not fail

The first version of `the_font_widths_serialize_as_the_python_compiler_serializes_them`
read each width back with lopdf's `as_float()` and applied `fp` to it before
comparing. That re-rounds on the READ side, so it reproduced the fixture whether
or not the writer rounded. Perturbation E passed against it.

This was caught only because the perturbation was actually run rather than
reasoned about. The test now slices the `/Widths` array out of the written PDF
BYTES and compares serialized tokens, and perturbation E then fails on 36 of 95
rows. Recording it because a passing perturbation is the signal, and the
instinct to explain it away is the failure mode.

### What the normalization does, and why it cannot hide a Rust defect

Four differences separate the two content streams. The normalizer erases exactly
these and nothing else:

| difference | normalization | why it is not a divergence |
|---|---|---|
| `/FormXob.<md5>` against `/Cover` | both to `/IMG` | a local resource key; reportlab names image XObjects by the md5 of the image data. Both are `/Subtype /Image`, DeviceRGB 1748x2480 with an SMask. |
| `/F2+0` against `/Inter` | both to `/FONT` | a local resource key resolved through `/Resources /Font`. |
| reportlab's preamble `1 0 0 1 0 0 cm  BT /F1 12 Tf 14.4 TL ET` | dropped | an identity `cm` and a `BT`/`ET` pair containing no show operator. It draws nothing and produces no display-list element, which oracle 3 confirms: 8 elements on both sides. |
| trailing blank line | trimmed | lopdf's `get_page_content` appends a newline. |

`the_normalizer_only_loosens_the_python_side` states what would make it fail and
commits the cases: it asserts the writer's stream contains no `/FormXob.`, no
`/F2+0` and no preamble, so three of the four rules are provably no-ops on the
Rust side and can only loosen Python. It then round-trips the two name
substitutions and requires the result to equal the original stream modulo that
trailing newline, so a fourth normalization rule cannot be added silently. It
would fail if the writer ever emitted a reportlab-only token, or if normalize
changed anything beyond the two names.

### Discrimination

Every perturbation was reverted in place afterwards and the suite re-run green.
The point of the table is that no single column is redundant.

| perturbation | oracle 1 rendered | oracle 2 streams | oracle 3 tracer | committed tests |
|---|---|---|---|---|
| A: front face carries no text at all | **pass, 3 of 3 layouts** | FAIL (front) | not run | front stream |
| B: footer baseline +0.0001 pt | **pass, 3 of 3 layouts** | FAIL (front) | not run | front stream |
| C: `fp` stops stripping the leading zero | **pass, 3 of 3 layouts** | FAIL (front AND back) | not run | both streams |
| D: `split_pixels` emits premultiplied pixels | FAIL | **pass (both)** | not run | rendered page |
| E: `/Widths` bypass the `fp` rounding | **pass** | **pass** | **FAIL, glyph clause, 2 of 5 shows** | widths, 36 of 95 rows |
| F: WinAnsi high range falls back to Latin-1 | **pass** | **pass** | not run | CMap, `<97> <2014>` missing |
| G: paper fill 1.0 to 0.99 red | FAIL, 3 of 3 reported | FAIL | not run | rendered page |

Row A is the headline result: deleting the ENTIRE invisible text layer leaves
all three rendered page hashes matching Python exactly. A writer shipped on a
raster oracle alone would have proven nothing whatsoever about the selectable
text. Row B puts oracle 2's resolution at 1e-4 pt, four orders of magnitude
finer than a 72 dpi pixel. Rows E and F are the ones only the third oracle or a
direct assertion can see: both pass oracles 1 and 2 completely. Row D is the
converse, invisible to oracle 2 and caught only by the rendered page. Row G
exists to show the rendered-page oracle is not vacuous and that the harness
reports every failure rather than the first.

### f32 in the output

lopdf models every PDF real as `Object::Real(f32)`. Where that reaches this
writer's output, after the fix for defect 2:

| output | f32? | compared? |
|---|---|---|
| content stream numbers | NO | yes, byte-exact |
| `/MediaBox` | yes, via `fp` | yes, byte-exact |
| `/Widths` | yes, via `fp` | yes, byte-exact, 95 of 224 entries |
| `/FontBBox`, `/Ascent`, `/Descent`, `/CapHeight` | yes, via `fp` | no |

The content stream, where every coordinate lives, never passes through f32: `fp`
formats f64 straight to text and the bytes go into the stream. WP-0.2j's
lopdf-f32 concern therefore does not touch this WP's geometry. Every real that
DOES pass through f32 now goes through `fp` first, so it serializes at
reportlab's precision rather than f32's, which is what made the glyph clause
exact. `/MediaBox` is asserted byte-exact as `/MediaBox[0 0 419.5276 595.2756]`,
matching reportlab's `[ 0 0 419.5276 595.2756 ]` real for real; the bracket
padding differs and carries no meaning.

The 129 width entries above code 126 are NOT compared, because reportlab's
subset stops at 127 and there is nothing on the Python side to compare them to.

### One writer, three layouts

Plan revision 21 requires the writer be general rather than fitted to
`footer_caption`. It is, and structurally rather than by luck: the layout
selects the SVG and therefore the raster, while the PDF assembly depends only on
the FACE. Front and back differ in fills and text lines; the three layouts do
not differ at all at this layer. `pdf::write` is called three times with three
different pixmaps and one unchanged code path.

## Verdicts

`cargo test`: 21 binaries green, 0 failures. The three cover binaries were
re-counted at this parent rather than quoted from an earlier WP: `cover_pdf` 8,
`cover_modes` 12 (7 at WP-5.4b, since raised by WP-5.4b-ii) and
`cover_footer_caption` 3. `cargo fmt --check` and
`cargo clippy --all-targets -- -D warnings` clean.

Rule 12 replay. Both `## Commands` blocks were extracted programmatically from
this finished file and run in a clean shell from the `wp54c-wt` worktree root,
which is not the directory they were developed in:

```
footer_caption  5f498b2a9cbab4b8a1c651bd19f908f7e31a0cc3b4e7b6c15b21819a5d8dd1ef
framed          330ae10cf0dcae7163d5389c502284d7aeb1818ed7a0503f37120adf2ef67120
honored_plate   02d379d867f748b9efe45a98abcdd3546bb8b65e43d8b8cfbb75e2d1af82e453
front_stream bytes 768
back_stream  bytes 627
widths rows 95
front_stream fixture identical
back_stream fixture identical
widths fixture identical
stand-in SVG raster sha256: 4b4549e9b97ead363014cb94eb8ff3e6af4491c7f865bd0bba3fd665988190b2
WP-5.4 recorded            : 4b4549e9b97ead363014cb94eb8ff3e6af4491c7f865bd0bba3fd665988190b2
```

Two tree-wide gates fired against this WP and both were fixed rather than
suppressed:

- `clippy::type_complexity` on `font_metrics` returning a five-element tuple.
  Fixed by naming the return type `Metrics`, not by an `#[allow]`.
- `rust_helpers::no_helper_is_defined_in_two_modules` reported
  `escape in [("cover/pdf.rs", "escape"), ("cover/svg.rs", "escape")]`. These
  are NOT the same helper: `cover/svg.rs` escapes XML (`&`, `<`, `>`) and this
  one escapes a PDF literal string (`(`, `)`, `\`). Sharing them would have been
  a defect, so the fix is the specific name `escape_literal`.

## Residuals

**Spanish cover text is NOT byte-comparable to Python, by construction.** This
is the most important thing in this section and it is a finding, not an excuse.
Driving the Python compiler with `language="es"` shows reportlab remapping
non-ASCII into its own subset codes rather than WinAnsi: `antología` is written
`(Una antolog\001a independiente ...)` and `NÚMERO` as `(... N\002MERO ...)`,
with `/F2+0` carrying `/FirstChar 0 /LastChar 127` and a ToUnicode CMap mapping
`\001` back to U+00ED. This writer emits WinAnsi instead, so `í` is the single
byte `0xED`. Both are correct PDFs that select and copy identically; their
content streams simply cannot be equal. Consequence for whoever compares the
Spanish cover: oracle 2 is UNAVAILABLE for non-ASCII text and the comparison
must go through the tracer, which decodes both sides through their own ToUnicode
CMaps. That is now possible only because defect 1 was fixed. Recorded here
rather than worked around, and no Spanish byte fixture was committed, because
one would have pinned a false equality.

**The back cover's rendered page is not compared, only its content stream.**
Producing it needs a back SVG, and `mag/src/cover/svg.rs` materializes the three
front layouts only. The back face is proven at the fills-and-text level, both of
which live in the content stream and both byte-exact, and NOT at the pixel
level. Owner: WP-5.6.

**The back cover's copy is not derived, it is supplied.** `_back_cover_copy`
(`cover.py:1596`) and `CoverCompiler._wrap` are unported;
`mag/src/cover/text.rs` carries only `cover_date`, `cover_contributors`,
`cover_tab_issue` and `cover_tab_identity`. The five back lines in the test are
transcribed from what Python emitted. Two consequences. First, the Spanish back
cover is unproven, because `_back_cover_copy` is where the language branch lives
(`LOOP`/`CLOSED` against `CICLO`/`CERRADO`, `END` against `FIN`, `ISSUE` against
`NÚMERO`) and this WP never executes it. Second, and this is the rule 6a class C
caveat: because the strings come from Python, this WP inherits Python's
correctness and cannot see a copy defect. If `_back_cover_copy` is wrong, my
fixture is wrong in the same way and both oracles agree. Owner: WP-5.6.

**The front deck lines are supplied pre-wrapped** for the same reason:
`Builder::wrap` is private in `svg.rs`, which this WP does not own. This is a
fourth instance of the private-sibling wall. Owner: WP-5.6.

**`design.toml` has a `[back]` section the Rust `Design` struct lacks.** Python
reads the back overdraw from `design["back"]["overdraw"]` (`cover.py:1160`), not
from `[tab]`. Both are 1.5 today, so a test passing `design.tab.overdraw` would
pass while modelling the wrong input. The test names `BACK_OVERDRAW` separately,
transcribed from `[back] overdraw`, so the conflation is not baked in. Owner:
WP-5.6.

`design.toml` loading is still unported and this WP constructs `Design` in test
code, as WP-5.4 and WP-5.4b do. Recorded again because all three WPs' oracles
would silently diverge if that file changed.

Nothing this WP found is a defect in code owned by another WP, so rule 3b's
live-on-branch statement is short: the four defects above were all in
`mag/src/cover/pdf.rs`, all introduced and fixed within this WP, and none was
ever on the branch. No consumer needs warning.

Deliberate divergences from reportlab, each a thing NOT reproduced:

- reportlab's empty preamble is not emitted. Reproducing it would mean embedding
  an unused /F1 Helvetica resource so `/F1 12 Tf` resolves, which is the
  "reproduce a hack" category the plan has rejected repeatedly. That it is
  inert is measured, not asserted: oracle 3 counts 8 elements on both sides.
- The image streams carry `FlateDecode` only, not reportlab's
  `[/ASCII85Decode /FlateDecode]`. The decoded bytes are what a renderer sees
  and oracle 1 agrees on all three layouts.
- The full Inter face is embedded with WinAnsiEncoding rather than reportlab's
  0-127 subset. Permitted because revision 21 excludes the font program from
  comparison, and the consequence for Spanish is recorded above.

## What is and is not proven

PROVEN by committed tests, each against a value the Python compiler produced,
each shown to discriminate by a perturbation reverted in place:

- the rendered page of the front cover PDF in all three layouts, byte-exact at
  72 dpi, with every mismatch reported rather than the first;
- the front cover's complete content stream, byte-exact, covering the invisible
  text layer's content and placement, the background fills, the image placement
  matrix and reportlab's `fp_str` number formatting;
- the back cover's complete content stream, byte-exact, on the same terms;
- the `/Widths` array's serialization for the 95 ASCII codes, byte-exact;
- the ToUnicode CMap: 219 entries, six specific mappings including `<97> <2014>`
  and `<80> <20AC>`, no entry for the five undefined codes, and no bfchar block
  above the 100 the PDF spec allows;
- that text outside WinAnsiEncoding is refused with a named error rather than
  written wrong, and that U+00DA is written as the single byte `0xDA`;
- the `/MediaBox` page box, and `/Info` `/Title` and `/Creator`;
- that the writer serves all three layouts from one code path;
- that oracle 1 is BLIND to the invisible text layer, measured by deleting the
  layer and watching all three page hashes still pass.

PROVEN by one-off measurement at parent `62e665a`, recorded but not committed
because it needs an artifact Python produces at run time: Tier E display-list
equality (8 against 8 elements), exact per-glyph geometry (166 glyphs, worst
difference 0.000000 pt) and colour equality (7 entries) for `footer_caption`.

NOT PROVEN and not claimed: the back cover's rendered page; the back cover's
copy derivation in any language, and the Spanish cover in any form; the front
deck's line wrapping; `design.toml` loading including the `[back]` section; the
embedded font program and the descriptor reals; the 129 width entries above code
126; Tier E equality for `framed` and `honored_plate` (measured for
`footer_caption` only, and the text layer is identical across layouts while the
raster is not); and PDF bytes as a whole, since object numbering, stream
compression and the xref differ between lopdf and reportlab and are not a
rendering property.

No row in this WP compares an empty set against an empty set or a constant
against itself. The guard against the vacuous case is perturbation A for oracle
2 and perturbation E for the widths test, and E is the one that caught a
genuinely vacuous assertion of mine.

## Status

done
