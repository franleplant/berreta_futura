# WP-0.2b evidence: canonical display-list extractor (Tier E instrument)

## Base

e9c6953 (art_directed)

## Commands

All commands run from the repo root. The two render trees are regenerated,
not stored; renders are deterministic per WP-0.1.

```
cd mag && cargo build && cd ..
./mag/target/debug/mag render 010 --no-model --run editions/010/run-2026-09-13T01-34-51 --langs en
./mag/target/debug/mag render 010 --no-model --run editions/010/run-2026-09-13T01-34-51 --langs en
```

Name the two new `editions/010/render-*` directories A and B (chronological
order). Self-test, A vs A, then A vs B twice (byte-identical verdicts):

```
./mag/target/debug/mag parity 010 --pre-rendered <A> <A>
shasum -a 256 output/parity/010/verdict.json
./mag/target/debug/mag parity 010 --pre-rendered <A> <B>
shasum -a 256 output/parity/010/verdict.json
./mag/target/debug/mag parity 010 --pre-rendered <A> <B>
shasum -a 256 output/parity/010/verdict.json
```

Element count metric:

```
python3 -c "import json; d = json.load(open('output/parity/010/verdict.json'))['tier_e']['display_list']; print(d['elements_a'], d['elements_b'], d['status'])"
```

Corpus probes backing the ExtGState confirmation and the font inventory
(run before implementation; replayable against any 010 render):

```
uv run python -c "
from pypdf import PdfReader
import collections
r = PdfReader('<A>/en/reader.pdf')
gs = collections.Counter()
for p in r.pages:
    for g in ((p.get('/Resources') or {}).get('/ExtGState') or {}).values():
        gs[str(sorted((k, str(v)) for k, v in g.get_object().items()))] += 1
print(dict(gs))
"
```

Fixture suite. Write the two scripts below to a scratch directory, then:

```
DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib uv run python <scratch>/wp02b_fixtures.py <scratch>/wp02b-fx
cmp -s <scratch>/wp02b-fx/f4a/en/reader.pdf <scratch>/wp02b-fx/f4b/en/reader.pdf; echo "f4 bytes differ: $?"
zsh <scratch>/wp02b_matrix.sh <scratch>/wp02b-fx
```

Expected: `f4 bytes differ: 1`; the matrix prints 15 `OK` lines and no `BAD`.

`wp02b_fixtures.py`:

```python
import sys
import zlib
from pathlib import Path

ROOT = Path(sys.argv[1])
FONTS = Path("src/magazine/assets/fonts").resolve()
from weasyprint import HTML

from PIL import Image
from pypdf import PdfReader, PdfWriter
from pypdf.generic import NameObject

CSS = f"""
@font-face {{ font-family: FxSans; src: url("file://{FONTS}/inter/Inter-Regular.ttf"); }}
@font-face {{ font-family: FxMono; src: url("file://{FONTS}/geist-mono/GeistMono-Regular.ttf"); }}
@page {{ size: 148mm 210mm; margin: 10mm; }}
body {{ font-family: FxSans; font-size: 10pt; }}
.pb {{ page-break-after: always; }}
"""


def render(name, body):
    out = ROOT / name / "en"
    out.mkdir(parents=True, exist_ok=True)
    html = f"<style>{CSS}</style><div class='pb'>cover</div>{body}<div>back</div>"
    HTML(string=html).write_pdf(out / "reader.pdf")


def page2(inner):
    return f"<div class='pb'>{inner}</div>"


def make_images(tmp):
    rgb = Image.new("RGB", (8, 8))
    rgb.putdata([(x * 30 % 256, y * 40 % 256, 90) for y in range(8) for x in range(8)])
    rgb.save(tmp / "rgb.png")
    rgba = Image.new("RGBA", (8, 8))
    rgba.putdata(
        [(200, 40, 40, (x + y) * 16 % 256) for y in range(8) for x in range(8)]
    )
    rgba.save(tmp / "rgba.png")


def reencode_images(src, dst, doctor_smask=False):
    reader = PdfReader(src)
    writer = PdfWriter(clone_from=reader)
    for page in writer.pages:
        xobjects = (page.get("/Resources") or {}).get("/XObject")
        if not xobjects:
            continue
        for ref in xobjects.values():
            xo = ref.get_object()
            if str(xo.get("/Subtype")) != "/Image":
                continue
            targets = [xo]
            smask = xo.get("/SMask")
            if smask is not None:
                targets.append(smask.get_object())
            for i, obj in enumerate(targets):
                data = bytearray(obj.get_data())
                if doctor_smask and i == 1:
                    data[0] ^= 0xFF
                obj[NameObject("/Filter")] = NameObject("/FlateDecode")
                obj.set_data(bytes(data))
                for key in ("/DecodeParms", "/DecodeParams"):
                    if key in obj:
                        del obj[NameObject(key)]
    dst.parent.mkdir(parents=True, exist_ok=True)
    with open(dst, "wb") as fh:
        writer.write(fh)


def main():
    tmp = ROOT / "assets"
    tmp.mkdir(parents=True, exist_ok=True)
    make_images(tmp)
    render("f1a", page2("<p style='color:#f00'>the same words</p>"))
    render("f1b", page2("<p style='color:#00f'>the same words</p>"))
    mono = "<p style='font-family:FxMono'>ab{}</p>"
    render("f2a", page2(mono.format("c")))
    render("f2b", page2(mono.format("d")))
    links = "<p><a href='https://one.example'>one</a>{}</p>"
    render("f3a", page2(links.format(" <a href='https://two.example'>two</a>")))
    render("f3b", page2(links.format(" two")))
    img = f"<img style='width:40pt' src='file://{tmp}/rgb.png'>"
    render("f4a", page2(img))
    reencode_images(ROOT / "f4a/en/reader.pdf", ROOT / "f4b/en/reader.pdf")
    rule = "<hr style='width:60pt;margin-left:{}'>"
    render("f5a", page2(rule.format("0pt")))
    render("f5b", page2(rule.format("0.02pt")))
    boxes = (
        "<div style='position:relative;width:60pt;height:60pt'>"
        "<div style='position:absolute;top:0;left:0;width:40pt;height:40pt;"
        "background:#c00;z-index:{}'></div>"
        "<div style='position:absolute;top:0;left:0;width:40pt;height:40pt;"
        "background:#00c;z-index:{}'></div></div>"
    )
    render("f6a", page2(boxes.format(1, 2)))
    render("f6b", page2(boxes.format(2, 1)))
    clipbox = "<div style='width:40pt;height:40pt;overflow:{}'>" "<div style='width:40pt;height:40pt;background:#0a0'></div></div>"
    render("f7a", page2(clipbox.format("hidden")))
    render("f7b", page2(clipbox.format("visible")))
    imga = f"<img style='width:40pt' src='file://{tmp}/rgba.png'>"
    render("f8a", page2(imga))
    reencode_images(
        ROOT / "f8a/en/reader.pdf", ROOT / "f8b/en/reader.pdf", doctor_smask=True
    )
    print("fixtures written to", ROOT)


main()
```

`wp02b_matrix.sh`:

```zsh
#!/bin/zsh
set -u
FX=$1
MAG=./mag/target/debug/mag
expect() {
  local name=$1 clause=$2 want=$3
  local got
  got=$(python3 -c "
import json
v = json.load(open('output/parity/$name/verdict.json'))
node = v
for part in '$clause'.split('.'):
    node = node[part]
print(node['status'])
")
  if [ "$got" = "$want" ]; then
    echo "OK   $name $clause = $got"
  else
    echo "BAD  $name $clause = $got (want $want)"
  fi
}
run() { $MAG parity "$1" --pre-rendered "$FX/$2" "$FX/$3" > /dev/null 2>&1; echo "exit $1: $?"; }

run fx1 f1a f1b
expect fx1 tier_e.display_list fail
expect fx1 tier_s.color fail
expect fx1 tier_s.text pass
run fx2 f2a f2b
expect fx2 tier_e.display_list fail
expect fx2 tier_s.text fail
run fx3 f3a f3b
expect fx3 tier_s.navigation fail
run fx4 f4a f4b
expect fx4 tier_e.display_list pass
expect fx4 tier_s.color pass
expect fx4 tier_s.text pass
expect fx4 tier_s.navigation pass
run fx5 f5a f5b
expect fx5 tier_e.display_list fail
run fx6 f6a f6b
expect fx6 tier_e.display_list fail
run fx7 f7a f7b
expect fx7 tier_e.display_list fail
run fx8 f8a f8b
expect fx8 tier_e.display_list fail
expect fx8 tier_s.text pass
```

Repo checks:

```
cd mag && cargo fmt --check && cargo clippy -- -D warnings && cargo test
```

## Tool versions

- rustc 1.96.0, cargo (workspace), lopdf 0.45.0 (the display tracer,
  recorded in parity.yaml tools.display_tracer and asserted at startup),
  flate2 1.1.10 (new crates this WP)
- poppler 25.08.0 (unchanged, still asserted)
- fixture generation only: weasyprint 69.0, pypdf 6.14.2, pillow 12.3.0 via
  uv, DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib for the gobject dlopen

## Metrics

- Interior domain traced: pages 2..55 of the 56-page 010 reader.pdf, both
  legs, zero unsupported-operator failures; 2176 canonical elements per leg.
- Operator inventory encountered on 010 interior: BT/ET, Tm, Tf, TJ, q/Q,
  cm, gs, w/J/j/M, m/l/c/h/re, S/f/f*/n, W/W*, rg/RG, Do (images only, no
  Form XObjects, no inline images, no shadings, no Type3).
- ExtGState: 010 interior resources carry only /ca 1 and /CA 1 entries
  (whole-document count 162: 108 /ca + 54 /CA); any other alpha value or
  key fails loud (enforced in streams.rs, exercised by the corpus pass).
- Fonts on 010 interior: 9 subset-tagged aliases, all Type0/Identity-H with
  ToUnicode; every alias resolved through font_name_map. Helvetica and
  AAAAAA+Inter-Regular appear only on cover pages 1 and 56, outside the
  compared domain.
- Fixture matrix: 8 fixture pairs, 15 clause expectations, 15 OK / 0 BAD.
  f4 doctored PDF differs byte-wise from its base (cmp exit 1) yet passes
  (RGBA pixel hash equality), proving re-encoding insensitivity.
- Wall clock: one 010 pre-rendered comparison approximately 44 s in a debug
  build (dominated by pixel decode + hash of the figure images).

## Verdicts

- 010 A vs A: sha256(verdict.json) =
  710878fb3f6453f6d7dee26a82a3b1af646c08050a62fd988310ab2877a2e891
  Tier S page_count/boxes/text/color/navigation pass, Tier G all zeros,
  Tier E display_list pass (2176 = 2176), code_blocks/critic/V/raster
  not_evaluated. Exit 0.
- 010 A vs B, run twice: sha256(verdict.json) =
  a195f86db2d4b5ae3e6efeb78e8ba95ba784d924fc679e2c1d60ad34c9dd9ea7
  both times (byte-deterministic); same tier summary as A vs A. Exit 0.
- fx1..fx8: per-fixture verdicts under output/parity/fx*/; the matrix
  transcript above is the tier summary (every intended catch caught, the
  must-pass fixture passing, every failing fixture exiting 1).

## Residuals

- Tracer choice: Rust content-stream interpreter (mag/src/parity/streams.rs
  on lopdf 0.45.0). mutool is not installed on this machine; the interpreter
  gives exact control over quantization, clip stacks, and SMask compositing.
  Recorded in parity.yaml tools.display_tracer; asserted at startup.
- Supported stream filters: FlateDecode (with PNG predictors 10..15) and
  ASCII85Decode. Anything else (DCTDecode included) fails loud. If the
  typst leg embeds JPEG passthrough images, a comparator WP must add that
  decode path; not needed for any WeasyPrint output seen.
- Color normalization is computed, not table-driven: g/G to rgb triple
  (family "gray"), k/K to rgb via (1-c)(1-k) (family "cmyk"), rg/RG kept
  (family "rgb"); components quantized at 1e-6. cs/CS/sc/scn/SC/SCN fail
  loud; parity.yaml color_space_map stays empty and unowned (gap already
  recorded by WP-0.1's critique).
- Canonicalizations inside the display list: v and y curve operators are
  recorded as equivalent c entries; re is recorded with its four
  CTM-transformed corners; coordinates are device-space at 0.01 pt quantum;
  stroke width and dash lengths are scaled by sqrt(|det CTM|); text position
  is the Trm origin (rise included) at show start; text size is the Tf size
  scaled by the Trm y-axis magnitude.
- Text shows are recorded per show operation (Tj/TJ/'/") as the Tier E
  definition specifies. Two shows equal in string, font, size, fill, and
  start position but differing in intra-show TJ kern numbers would produce
  equal display lists; the raster zero-diff check (WP-0.2c) is the guard
  for that residue. Advances (including TJ numbers, Tc/Tw/Tz) are tracked
  exactly so any subsequent show's position exposes them.
- Text render modes other than 0 (fill) fail loud; 010 uses only mode 0.
- font_name_map typst-side face names are the PostScript names of the same
  vendored files (provisional until a typst PDF exists, as recorded in the
  map's method note).
- The orchestrator grant for WP-0.2a's main.rs registration lines needed no
  further use here; parity.rs wiring sufficed (main.rs untouched this WP).
- Scratch fixtures live under the job tmp directory and are fully
  regenerable from the inline scripts; nothing binary is committed.

## Status

done
