# WP-5.4b cover modes and refusal branches

## Base

`ee15768`, plan revision 31. Depends on WP-5.4 (accepted, `01975a3`/`c084e16`,
verify `6702c7c`) and WP-5.4a (accepted, verify `443aaa8`).

## Commands

The oracle drives the REAL Python compiler over the three layouts on one set of
inputs, rasterizes each through the same transform `cover.py` applies before
`resvg`, and hashes the premultiplied RGBA so the digest is directly comparable
to `tiny_skia::Pixmap::data()` on the Rust side.

Edition 010's manuscripts live in an untracked run directory, so `load_edition`
cannot run from a clean checkout. The oracle therefore builds a stand-in
carrying exactly the attributes the cover compiler reads
(`cover`, `cover_art`, `publication_name`, `publication_date`, `title`,
`language`, `issue_number`, `place`, `articles[].author`). That stand-in is
VALIDATED rather than assumed: run on `footer_caption` it reproduces WP-5.4's
committed hash `4b4549e9b97ead363014cb94eb8ff3e6af4491c7f865bd0bba3fd665988190b2`
byte for byte, which is the accepted oracle for a mode this WP did not port.

```
uv run python -c '
import sys, re, hashlib, io
sys.path.insert(0, "src")
from pathlib import Path
from types import SimpleNamespace
from magazine.cover import CoverCompiler, PAGE_WIDTH, PAGE_HEIGHT
import resvg
from PIL import Image

ART = Path("editions/010/art/rounds/2026-09-13T01-40-20/cover-wildcard-sign-punched-v3.png")
AUTHORS = ["FRANK RIETTA","ANTHROPIC","DARIO AMODEI","SANTI RUIZ","MICHAEL TRUELL",
           "WILSON LIN","DEEPSEEK-AI","JON LEE, CHAOMIN YU, BEN RIES"]

def edition(layout):
    return SimpleNamespace(
        identifier="010", language="en", issue_number=10, place="Buenos Aires",
        publication_name="Berreta Futura", publication_date="2026-09-13",
        title="The Speed Limit",
        cover={"layout": layout, "headline": "The Speed Limit"},
        cover_art=ART,
        articles=[SimpleNamespace(author=a) for a in AUTHORS],
    )

def raster_prepare(svg, dpi):
    w = round(PAGE_WIDTH / 72 * dpi); h = round(PAGE_HEIGHT / 72 * dpi)
    out = re.sub(rb"width=\"[^\"]+\" height=\"[^\"]+\"", f"width=\"{w}\" height=\"{h}\"".encode(), svg, count=1)
    for slot in (b"paper", b"edge-tab", b"field"):
        out = re.sub(rb"(<rect data-slot=\"" + slot + rb"\"[^>]*?) fill=\"[^\"]+\"", rb"\1 fill=\"none\"", out, count=1)
    return out.decode("utf-8")

c = CoverCompiler(Path("."))
for layout in ["framed", "honored_plate", "footer_caption"]:
    svg = c._materialize_svg(edition(layout)).encode("utf-8")
    tree = resvg.usvg.Tree.from_str(raster_prepare(svg, 300), resvg.usvg.Options.default())
    png = resvg.render(tree, (1, 0, 0, 0, 1, 0))
    im = Image.open(io.BytesIO(png)).convert("RGBA")
    px = bytearray(im.tobytes())
    for i in range(0, len(px), 4):
        a = px[i+3]
        if a != 255:
            px[i] = (px[i]*a + 127)//255; px[i+1] = (px[i+1]*a + 127)//255; px[i+2] = (px[i+2]*a + 127)//255
    print(layout, im.size, hashlib.sha256(bytes(px)).hexdigest())
'
```

The refusal fixture's headline was chosen by asking Python which strings it
refuses, rather than by guessing:

```
uv run python -c '
import sys; sys.path.insert(0,"src")
from pathlib import Path
from magazine.cover import CoverCompiler, CoverOverflowError
c = CoverCompiler(Path("."))
for t in ["Extraordinarily Unfittable Supercalifragilistic Headline",
          "Pneumonoultramicroscopicsilicovolcanoconiosis",
          "Antidisestablishmentarianismxx Pneumonoultramicroscopic Floccinaucinihilipilification Supercalifragilisticexpialidocious"]:
    try:
        lines, size = c._headline_layout(t.upper().strip(), described_as=t)
        print("FITS", len(lines), size)
    except CoverOverflowError as e:
        print("REFUSE", e)
'
```

Tests: `cargo test --test cover_modes`, `cargo test`, `cargo fmt --check`,
`cargo clippy --all-targets -- -D warnings`.

## Tool versions

python 3.12.11 via `uv run` (Unicode 15.0.0; the system `python3` is 3.9.6 on
Unicode 13.0.0 and must not be used), resvg/usvg 0.47.0 and tiny-skia 0.12.0 on
both sides, rustc 1.96.0.

## Metrics

Raster equality, 1748x2480 at 300 dpi, premultiplied RGBA sha256:

| layout | expected (Python) | Rust |
|---|---|---|
| `framed` | `ece03e915b38e0d3fc36cf68499c4f63c3bad698992210119ba07035fcb11aca` | equal |
| `honored_plate` | `c46b2db485d6bcba195cbda9e37ad9ecbcfca6baa0dc2561af1e4522322a02e9` | equal |
| `footer_caption` | `4b4549e9b97ead363014cb94eb8ff3e6af4491c7f865bd0bba3fd665988190b2` | equal (harness validation, and the dispatch path) |

Both new modes matched on the first run, with no tuning.

Discrimination, each perturbation reverted in place afterwards. Note each fails
ONLY its own mode, which is what shows the two oracles are independent rather
than one covering for the other:

| perturbation | framed | honored_plate | footer_caption |
|---|---|---|---|
| headline colour cycle violet to ink | FAIL | pass | pass |
| `honored_plate` right_edge 8.0 to 9.0 | pass | FAIL | pass |
| deck tracking +0.01 | FAIL | pass | pass |
| drop the missing-art guard | (refusal test FAILS) | | |

The SVGs are NOT byte-comparable across languages and the oracle deliberately
does not compare them: Rust and Python encode the graded art PNG differently, so
the base64 payload differs while the decoded pixels agree. That is the same
reason WP-5.4's oracle is the raster, confirmed here by `cmp` differing at char
448 inside the base64 while the rasters hash equal.

### WP-5.4's acceptance survives this WP

Extending `Design` with the fields the two modes need forced an edit to
`mag/tests/cover_footer_caption.rs`, which is inside this WP's Owns
(`mag/tests/cover*`) but is what WP-5.4's acceptance rests on. The edit is +38/-1
and is entirely CONSTRUCTION, not assertion: the new `Design` fields, the
widened `use`, and an `#[allow(dead_code)]` on its `#[path]` include of `svg.rs`
(the new fields are genuinely unread in that target, which calls only
`footer_caption`). No assertion, expected value or hash literal changed.

Expectation blobs unchanged, by `git hash-object`:

| file | blob |
|---|---|
| `tests/critic_metrics_expected.json` | `39be9e815b4403a8bcd8b27c07944fe3daa29e31` |
| `tests/cover_zone_expected.json` | `b94e31893752a4fdbf98375fcb42ae7d7a7d209d` |
| `tests/cover_footer_caption_expected.txt` | `1228bfa8e8677ec6c4249d0d5d4eedecf01212d1` |

WP-5.4's discrimination proof re-run under this WP's change, reverting
`art.rs` to the per-mille luma: `zone_statistics_match_the_python_compiler`
FAILS at `top_mean diverged from PIL: 109.56702330964686 against
109.56689949397072` while `footer_caption_raster_matches_the_python_compiler`
PASSES in the same run. Both halves reproduce exactly as WP-5.4 recorded them.

### Branches edition 010 cannot reach

Inherited from WP-5.4's enumeration rather than re-derived. Covered here:

| branch | fixture |
|---|---|
| `framed` layout (the default when `cover.layout` is unset) | `framed_raster_matches_the_python_compiler` |
| `honored_plate` layout | `honored_plate_raster_matches_the_python_compiler` |
| unknown-layout refusal (`cover.py:401`) | `an_unknown_layout_is_refused_as_python_refuses_it` |
| missing cover art (`cover.py:424` framed, `:505` via `_full_art`) | `missing_cover_art_is_refused_by_every_mode_that_places_it` |
| headline overflow (`cover.py:968`) | `a_headline_that_cannot_fit_is_refused` |

010 reaches none of these: it ships `footer_caption` with art present and a
headline that fits.

## Verdicts

`cargo test`: 13 binaries green including `cover_modes` (7) and
`cover_footer_caption` (3). `cargo fmt --check` and
`cargo clippy --all-targets -- -D warnings` clean.

## Residuals

**The PDF writer does not exist, so this WP's guard could not apply.** The brief
said to add coverage rather than a second writer, because the writer was
required to be general. WP-5.4's own `## What is and is not proven` lists "the
PDF writer" as NOT built, and `mag/src/cover/` contains no PDF module. So there
is no writer to be narrow, and the modes are proven at the SVG-and-raster level
only, which is the same level at which WP-5.4 proved `footer_caption`. Whoever
writes it inherits three modes rather than one, and the invisible `3 Tr` layer
comparison (content and placement, never subset bytes) applies to all three.

`design.toml` loading is still unported; both this WP and WP-5.4 construct
`Design` in test code. The values here are transcribed from
`design/covers/canto-vivo/design.toml` and would silently diverge if that file
changed, which is an argument for porting the loader before either WP's oracle
is relied on outside the test suite.

The back cover remains unported and unproven, unchanged by this WP.

Deck overflow (`cover.py:1004`, more than five wrapped lines) and the
contributor-less deck path are NOT covered: both need contributor text the
stand-in would have to invent, and the refusal message includes the full text,
so a fixture would pin a string of no significance. Recorded as uncovered rather
than papered over.

## What is and is not proven

PROVEN by committed tests, each against a number Python produced, each shown to
discriminate by a perturbation reverted in place: the `framed` front cover
raster, the `honored_plate` front cover raster, the unknown-layout refusal
message, the missing-cover-art refusal message in both modes that place art, and
the headline-overflow refusal message. The `footer_caption` hash is asserted
here too, which proves the layout DISPATCH reaches it unchanged; WP-5.4 owns the
mode itself.

NOT PROVEN and not claimed: the PDF writer for any mode (it does not exist), the
back cover in any mode, `design.toml` loading, deck overflow, the contributor-less
deck path, and the invisible text layer for the two new modes (no PDF, so no
layer). None of the three modes is proven end to end to a PDF; all three are
proven to a raster.

No row in this WP compares an empty set against an empty set or a constant
against itself.

## Status

done
