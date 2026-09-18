# WP-5.3b-ii page inspection

## Base

`d8bc6ef` (`verify(critic): WP-5.3b-i rework accepted, join rule unit fix
reproduced`), branch `art_directed`. Worked in
`git worktree add <scratch>/wp53bii d8bc6ef`.

## What was built

`mag/src/critic/inspect.rs` ports, from `src/magazine/render_critic.py`:

- `_inspect_page` (:965) as `inspect_page(png, page_number, text)` returning a
  `PageInspection`, whose `row()` emits Python's dict field for field,
  `largest_void`, `voids` and `tail_band` placeholders included so WP-5.3b-iii
  fills them in the same shape.
- `_render_pages` (:888) as `render_pages(pdf, output_dir, shards)`: the
  `pdftoppm -png -r 144` invocation, the `worker_count(page_count // 2)` shard
  derivation, the `cuts`/`windows` split, `ordered_map`, the trailing-number
  sort and the `page-%03d` rename. `shards` is a test seam; `None` is Python's
  behaviour and is what `render_review_pages` passes.
- `render_review_pages`, the three 144 dpi rasterisations `inspect_render`
  performs (:583-585) into `reader-pages`, `booklet-sides` and
  `cover-booklet-sides`.
- The raster helpers the original WP-5.3b bullet named and `metrics.rs` does
  not carry: `grayscale` (PIL `ImageOps.grayscale`), `point_below` (PIL
  `Image.point` with the two thresholds), `histogram` and `rgb_histogram` (PIL
  `Image.histogram` for mode L and mode RGB), `getbbox`, `extrema` and
  `difference` (`ImageChops.difference`).

`mag/src/critic.rs` gains the one line `pub mod inspect;`. It is not in the
Owns list; both predecessors in this directory added exactly the same line
under the same reading (`5d9d154` for `metrics`, `26391ab` for `text`), and
without it the module is not compiled by the binary at all, so `clippy`,
`fmt` and `nocomments` would never see it. Declared here rather than assumed,
and offered as an Owns EXTENSION to record rather than a self-grant, in the
shape revision 43 requires: `mag/src/critic.rs` is not comparator territory
and rule 1c assigns it to nobody, the line adds a module rather than changing
an existing public surface, and the diff is exactly `+pub mod inspect;`. If
the orchestrator would rather it did not stand, the module file lands
uncompiled and unlinted, which is worse; say so and I will report instead of
landing it.

LANCZOS resize, the fourth helper the original bullet named, was NOT ported:
`metrics.rs:411 fn resize` already implements PIL's `Image.resize` exactly and
is private to that module, so a sibling cannot call it. See `## Residuals`.

## Commands

Every block below was extracted programmatically from this file and executed
in a clean shell from a directory that is not the one the work was developed
in. `$PWD` is the repository checkout root. The 010 corpus is untracked and
therefore exists only in a working tree, never in a fresh worktree, so it
arrives by rule 2b's env gate through `MAG_010_RENDER`, which is the only
path in this file that is not `$PWD`-relative and is overridable.

Block 1, the committed fixtures and the fixture oracle. Regenerating must
leave every committed byte unchanged:

```sh
set -eu
uv run python - <<'PY'
import hashlib, io, json, sys, types
from pathlib import Path
from PIL import Image, ImageChops, ImageOps
sys.path.insert(0, "src")
from magazine.render_critic import _inspect_page, _render_pages
from pypdf import PdfReader, PdfWriter

root = Path("mag/tests/critic_inspect_fixtures")
root.mkdir(parents=True, exist_ok=True)

def compact(values):
    return json.dumps(values, separators=(",", ":")).encode("utf-8")

def solid(name, size, colour):
    Image.new("RGB", size, colour).save(root / name)

def dotted(name, size, count):
    image = Image.new("RGB", size, (255, 255, 255))
    pixels = image.load()
    for index in range(count):
        pixels[index % size[0], index // size[0]] = (0, 0, 0)
    image.save(root / name)

solid("pure_white.png", (128, 128), (255, 255, 255))
solid("paper_tint.png", (128, 128), (250, 250, 250))
dotted("sparse.png", (128, 128), 32)
dotted("tie_down.png", (128, 128), 128)
dotted("tie_up.png", (128, 128), 384)

corner = Image.new("RGB", (128, 128), (255, 255, 255))
corner.load()[5, 7] = (0, 0, 0)
corner.save(root / "corner_ink.png")

edges = Image.new("RGB", (128, 128), (255, 255, 255))
pixels = edges.load()
pixels[0, 0] = (0, 0, 0)
pixels[127, 127] = (0, 0, 0)
edges.save(root / "corner_edges.png")

bands = Image.new("RGB", (4, 2), (255, 255, 255))
pixels = bands.load()
for x, value in enumerate((244, 245, 254, 255)):
    pixels[x, 0] = pixels[x, 1] = (value, value, value)
bands.save(root / "threshold_bands.png")

state = 1
colours = []
for _ in range(64 * 64):
    state = (state * 1103515245 + 12345) % (1 << 31)
    colours.append(((state >> 16) & 255, (state >> 8) & 255, state & 255))
pins = Image.new("RGB", (64, 64))
pins.putdata(colours)
pins.save(root / "luma_pins.png")
shifted = Image.new("RGB", (64, 64))
shifted.putdata([((r + 37) % 256, (g + 91) % 256, (b + 173) % 256) for r, g, b in colours])
shifted.save(root / "luma_shifted.png")

disagreeing = []
for r in range(256):
    for g in range(0, 256, 7):
        for b in range(0, 256, 11):
            if ((r * 19595 + g * 38470 + b * 7471 + 0x8000) >> 16) != int(
                r * 0.299 + g * 0.587 + b * 0.114 + 0.5
            ):
                disagreeing.append((r, g, b))
assert len(disagreeing) >= 64, len(disagreeing)
edge = Image.new("RGB", (8, 8))
edge.putdata(disagreeing[:64])
edge.save(root / "luma_edges.png")
print("luma triples where the float formula disagrees with PIL:", len(disagreeing))

def raw_pdf(pages):
    objects = []
    def add(payload):
        objects.append(payload)
        return len(objects)
    font = add(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    content_ids, page_ids = [], []
    for index in range(pages):
        stream = (
            f"BT /F1 24 Tf 40 520 Td (Page {index + 1}) Tj ET\n"
            f"0 0 0 rg 40 60 {20 + index * 25} {20 + index * 15} re f\n"
        ).encode("ascii")
        content_ids.append(add(b"<< /Length %d >>\nstream\n%s\nendstream" % (len(stream), stream)))
    pages_id = len(objects) + pages + 1
    for index in range(pages):
        page_ids.append(add(
            b"<< /Type /Page /Parent %d 0 R /MediaBox [0 0 420 595] "
            b"/Resources << /Font << /F1 %d 0 R >> >> /Contents %d 0 R >>"
            % (pages_id, font, content_ids[index])))
    tree = add(b"<< /Type /Pages /Kids [%s] /Count %d >>"
               % (b" ".join(b"%d 0 R" % pid for pid in page_ids), pages))
    assert tree == pages_id
    catalog = add(b"<< /Type /Catalog /Pages %d 0 R >>" % tree)
    out = io.BytesIO()
    out.write(b"%PDF-1.4\n")
    offsets = []
    for number, payload in enumerate(objects, 1):
        offsets.append(out.tell())
        out.write(b"%d 0 obj\n" % number + payload + b"\nendobj\n")
    start = out.tell()
    out.write(b"xref\n0 %d\n" % (len(objects) + 1))
    out.write(b"0000000000 65535 f \n")
    for offset in offsets:
        out.write(b"%010d 00000 n \n" % offset)
    out.write(b"trailer\n<< /Size %d /Root %d 0 R >>\nstartxref\n%d\n%%%%EOF\n"
              % (len(objects) + 1, catalog, start))
    return out.getvalue()

writer = PdfWriter(clone_from=PdfReader(io.BytesIO(raw_pdf(12))))
writer._ID = None
with (root / "pages12.pdf").open("wb") as handle:
    writer.write(handle)

punctuation = "Intro\n,\n  …  \n?!\na.\n-\n\n...\n:;\nTail"
cases = [
    ("pure_white_no_text", "pure_white.png", 1, ""),
    ("pure_white_with_text", "pure_white.png", 2, "Something"),
    ("paper_tint_no_text", "paper_tint.png", 3, ""),
    ("paper_tint_with_text", "paper_tint.png", 4, "  x  "),
    ("sparse", "sparse.png", 5, ""),
    ("tie_down", "tie_down.png", 6, "lowercase line"),
    ("tie_up", "tie_up.png", 7, "UPPER ONLY"),
    ("corner_ink", "corner_ink.png", 8, ""),
    ("corner_edges", "corner_edges.png", 9, ""),
    ("threshold_bands", "threshold_bands.png", 10, ""),
    ("punctuation", "corner_ink.png", 11, punctuation),
    ("whitespace_only_text", "corner_ink.png", 12, "  \n\t\n "),
    ("astral_text", "corner_ink.png", 13, "\U0001d41a\U0001F600 tail"),
    ("luma_pins", "luma_pins.png", 14, ""),
    ("luma_edges", "luma_edges.png", 15, ""),
]
rows = []
for name, png, page, text in cases:
    texts = types.SimpleNamespace(raw=lambda number, value=text: value)
    rows.append({"name": name, "png": png, "page": page, "text": text,
                 "row": _inspect_page(root / png, None, page, texts=texts)})

def gray_row(png):
    with Image.open(root / png) as opened:
        gray = ImageOps.grayscale(opened)
        return {"png": png,
                "sha256": hashlib.sha256(gray.tobytes()).hexdigest(),
                "histogram_sha256": hashlib.sha256(compact(gray.histogram())).hexdigest()}

def difference_row(first, second):
    with Image.open(root / first) as opened:
        one = opened.convert("RGB")
    with Image.open(root / second) as opened:
        other = opened.convert("RGB")
    histogram = ImageChops.difference(one, other).histogram()
    values = one.width * one.height * 3
    total = sum((i % 256) * c for i, c in enumerate(histogram))
    return {"first": first, "second": second,
            "histogram_sha256": hashlib.sha256(compact(histogram)).hexdigest(),
            "histogram_total": total, "channel_values": values,
            "rgb_mae": repr(total / values)}

oracle = {
    "cases": rows,
    "grayscale": [gray_row(n) for n in
                  ("luma_pins.png", "luma_edges.png", "threshold_bands.png", "paper_tint.png")],
    "difference": [difference_row("luma_pins.png", "luma_shifted.png"),
                   difference_row("luma_pins.png", "luma_pins.png")],
}
Path("mag/tests/critic_inspect_expected.json").write_text(
    json.dumps(oracle, indent=1, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")

import tempfile
with tempfile.TemporaryDirectory() as scratch:
    produced = _render_pages(root / "pages12.pdf", Path(scratch) / "pages")
    render_rows = [{"name": p.name, "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
                   for p in produced]
Path("mag/tests/critic_inspect_render_expected.json").write_text(
    json.dumps({"pdf": "pages12.pdf", "pages": render_rows}, indent=1, sort_keys=True) + "\n",
    encoding="utf-8")
print("fixture cases", len(rows), "render oracle pages", len(render_rows))
PY
git status --porcelain mag/tests/critic_inspect_fixtures mag/tests/critic_inspect_expected.json mag/tests/critic_inspect_render_expected.json
shasum -a 256 mag/tests/critic_inspect_expected.json mag/tests/critic_inspect_render_expected.json mag/tests/critic_inspect_fixtures/*
```

Block 2, the live 010 oracle. It writes outside the checkout; nothing in the
repository depends on it:

```sh
set -eu
MAG_010_RENDER="${MAG_010_RENDER:-$HOME/code/magazine/editions/010/render-2026-09-14T01-49-02/en}"
MAG_CRITIC_INSPECT_ORACLE="${MAG_CRITIC_INSPECT_ORACLE:-${TMPDIR:-/tmp}/wp53bii-inspect-010.json}"
export MAG_010_RENDER MAG_CRITIC_INSPECT_ORACLE
uv run python - <<'PY'
import hashlib, json, os, sys
from pathlib import Path
sys.path.insert(0, "src")
from magazine.render_critic import _PageTexts, _inspect_page
from pypdf import PdfReader

render = Path(os.environ["MAG_010_RENDER"])
review = render / "render-review"
legs = [("reader", "reader.pdf", "reader-pages"),
        ("booklet", "booklet-a4.pdf", "booklet-sides"),
        ("cover_booklet", "booklet-a4-cover.pdf", "cover-booklet-sides")]
out = {}
for leg, pdf_name, folder in legs:
    reader = PdfReader(str(render / pdf_name))
    texts = _PageTexts(reader)
    pngs = sorted((review / folder).glob("page-*.png"))
    rows = []
    for index, png in enumerate(pngs):
        if index >= len(reader.pages):
            continue
        rows.append({
            "png": str(png.relative_to(render)),
            "png_sha256": hashlib.sha256(png.read_bytes()).hexdigest(),
            "page": index + 1,
            "text": texts.raw(index + 1),
            "row": _inspect_page(png, reader.pages[index], index + 1, texts=texts),
        })
    out[leg] = {"pdf": pdf_name, "pdf_pages": len(reader.pages),
                "rasters": len(pngs), "rows": rows}
    print(leg, "pdf pages", len(reader.pages), "rasters", len(pngs), "rows", len(rows))
target = Path(os.environ["MAG_CRITIC_INSPECT_ORACLE"])
target.write_text(json.dumps(out, indent=1, ensure_ascii=False, sort_keys=True) + "\n",
                  encoding="utf-8")
print("oracle", target, target.stat().st_size, hashlib.sha256(target.read_bytes()).hexdigest())

published = json.loads((render / "render-critic.json").read_text())["pages"]
mismatch = sum(
    1
    for mine, theirs in zip([r["row"] for r in out["reader"]["rows"]], published)
    for key in mine
    if key not in ("largest_void", "voids", "tail_band") and mine[key] != theirs[key]
)
print("reader rows cross-checked against render-critic.json, mismatches:", mismatch)

rows = [r["row"] for leg in out.values() for r in leg["rows"]]
print("rows", len(rows),
      "sparse", sum(1 for r in rows if r["sparse"]),
      "blank", sum(1 for r in rows if r["blank"]),
      "ink_free", sum(1 for r in rows if r["ink_free"]),
      "ink_bbox None", sum(1 for r in rows if r["ink_bbox"] is None),
      "punctuation", sum(1 for r in rows if r["standalone_punctuation_lines"]),
      "pure white with text", sum(1 for r in rows
                                  if r["presence_ratio"] == 0.0 and not r["blank"]))
texts = [r["text"] for leg in out.values() for r in leg["rows"]]
extra = sorted({hex(ord(c)) for t in texts for c in t
                if c in "\v\f\x1c\x1d\x1e\x85  \r"})
print("python splitlines separators beyond newline present in the 010 text:", extra)
PY
```

Block 3, the repository checks:

```sh
set -eu
cargo fmt --manifest-path mag/Cargo.toml --check
cargo clippy --manifest-path mag/Cargo.toml --all-targets -- -D warnings
uv run python tools/nocomments.py
cargo test --manifest-path mag/Cargo.toml 2>&1 | grep -E "^test result|^error" | sort | uniq -c
```

Block 4, the gated live run. Both modes, as rule 2b requires:

```sh
set -eu
MAG_010_RENDER="${MAG_010_RENDER:-$HOME/code/magazine/editions/010/render-2026-09-14T01-49-02/en}"
MAG_CRITIC_INSPECT_ORACLE="${MAG_CRITIC_INSPECT_ORACLE:-${TMPDIR:-/tmp}/wp53bii-inspect-010.json}"
cargo test --manifest-path mag/Cargo.toml --test critic_inspect -- --nocapture 2>&1 \
  | grep -E "^MODE|^COMPARED|^TRACER|^test result"
MAG_CRITIC_RENDER_DIR="$MAG_010_RENDER" MAG_CRITIC_INSPECT_ORACLE="$MAG_CRITIC_INSPECT_ORACLE" \
  cargo test --manifest-path mag/Cargo.toml --test critic_inspect -- --nocapture 2>&1 \
  | grep -E "^MODE|^COMPARED|^TRACER|^test result"
MAG_CRITIC_RENDER_DIR="$MAG_010_RENDER" \
  cargo test --manifest-path mag/Cargo.toml --test critic_inspect inspects_edition 2>&1 \
  | grep -E "panicked|set both|test result" | head -3
```

Block 5, the discrimination probes. Each rewrites one string in
`mag/src/critic/inspect.rs`, runs the fixture-only suite, and restores the
file from a pristine copy taken before the first probe:

```sh
set -u
PRISTINE="${TMPDIR:-/tmp}/wp53bii-pristine-inspect.rs"
TARGET="$PWD/mag/src/critic/inspect.rs"
cp "$TARGET" "$PRISTINE"
probe() {
  cp "$PRISTINE" "$TARGET"
  MAG_PROBE_OLD="$2" MAG_PROBE_NEW="$3" uv run python - "$TARGET" <<'PY'
import os, pathlib, sys
path = pathlib.Path(sys.argv[1])
body = path.read_text()
old, new = os.environ["MAG_PROBE_OLD"], os.environ["MAG_PROBE_NEW"]
assert body.count(old) == 1, (old, body.count(old))
path.write_text(body.replace(old, new))
PY
  result=$(cargo test --manifest-path mag/Cargo.toml --test critic_inspect 2>&1 \
    | grep -E "^test result" | head -1)
  echo "PROBE $1 -> $result"
  cp "$PRISTINE" "$TARGET"
}
probe "white-threshold 245->246" \
  "pub const WHITE_THRESHOLD: u8 = 245;" "pub const WHITE_THRESHOLD: u8 = 246;"
probe "paper-white 255->254" \
  "pub const PAPER_WHITE: u8 = 255;" "pub const PAPER_WHITE: u8 = 254;"
probe "point_below < becomes <=" \
  "if value < threshold { 255 } else { 0 }" "if value <= threshold { 255 } else { 0 }"
probe "ink_ratio unrounded" "ink_ratio: round_places(ratio, 6)," "ink_ratio: ratio,"
probe "text_characters counts bytes" \
  "text_characters: stripped.chars().count()," "text_characters: stripped.len(),"
probe "blank drops the empty-text conjunct" \
  "blank: pure_white && stripped.is_empty()," "blank: pure_white,"
probe "ink_free drops the empty-text conjunct" \
  "ink_free: ink_pixels == 0 && stripped.is_empty()," "ink_free: ink_pixels == 0,"
probe "sparse admits a zero ratio" \
  "sparse: ratio > 0.0 && ratio < SPARSE_INK_RATIO," "sparse: ratio < SPARSE_INK_RATIO,"
probe "getbbox right edge inclusive" "right = right.max(x + 1);" "right = right.max(x);"
probe "grayscale uses the float formula" \
  "data: image.data.chunks_exact(3).map(luma601).collect()," \
  "data: image.data.chunks_exact(3).map(|p| (p[0] as f64 * 0.299 + p[1] as f64 * 0.587 + p[2] as f64 * 0.114).round() as u8).collect(),"
probe "punctuation accepts every line" \
  "!line.is_empty()
                && line
                    .chars()
                    .all(|character| STANDALONE_PUNCTUATION.contains(&character))" \
  "!line.is_empty()"
probe "punctuation accepts nothing" \
  "!line.is_empty()
                && line
                    .chars()
                    .all(|character| STANDALONE_PUNCTUATION.contains(&character))" \
  "false"
probe "raster dpi 144->150" "pub const RASTER_DPI: u32 = 144;" "pub const RASTER_DPI: u32 = 150;"
probe "normalised names drop the padding" \
  "format!(\"page-{:03}.png\", index + 1)" "format!(\"page-{}.png\", index + 1)"
probe "shard windows off by one" \
  "(cuts[index] + 1, cuts[index + 1])" \
  "(cuts[index] + 1, cuts[index + 1].max(cuts[index] + 1) - 1)"
cmp "$PRISTINE" "$TARGET" && echo "RESTORED"
```

Block 6, the two live probes, each restored the same way:

```sh
set -u
PRISTINE="${TMPDIR:-/tmp}/wp53bii-pristine-inspect.rs"
TARGET="$PWD/mag/src/critic/inspect.rs"
MAG_010_RENDER="${MAG_010_RENDER:-$HOME/code/magazine/editions/010/render-2026-09-14T01-49-02/en}"
MAG_CRITIC_INSPECT_ORACLE="${MAG_CRITIC_INSPECT_ORACLE:-${TMPDIR:-/tmp}/wp53bii-inspect-010.json}"
cp "$TARGET" "$PRISTINE"
live() {
  MAG_PROBE_OLD="$2" MAG_PROBE_NEW="$3" uv run python - "$TARGET" <<'PY'
import os, pathlib, sys
path = pathlib.Path(sys.argv[1])
body = path.read_text()
old, new = os.environ["MAG_PROBE_OLD"], os.environ["MAG_PROBE_NEW"]
assert body.count(old) == 1, (old, body.count(old))
path.write_text(body.replace(old, new))
PY
  MAG_CRITIC_RENDER_DIR="$MAG_010_RENDER" MAG_CRITIC_INSPECT_ORACLE="$MAG_CRITIC_INSPECT_ORACLE" \
    cargo test --manifest-path mag/Cargo.toml --test critic_inspect inspects_edition 2>&1 \
    | grep -E "assertion|test result" | head -2 | sed "s/^/LIVE PROBE $1: /"
  cp "$PRISTINE" "$TARGET"
}
live "white-threshold 245->246" \
  "pub const WHITE_THRESHOLD: u8 = 245;" "pub const WHITE_THRESHOLD: u8 = 246;"
live "raster order reversed" \
  "        page_number(one)
            .cmp(&page_number(other))
            .then_with(|| one.cmp(other))" \
  "        page_number(other)
            .cmp(&page_number(one))
            .then_with(|| other.cmp(one))"
cmp "$PRISTINE" "$TARGET" && echo "RESTORED"
```

Replay record, rule 12. The six blocks were extracted from THIS file by

    uv run python - <<'PY'
    import pathlib, re
    text = pathlib.Path("meta/verification/evidence/WP-5.3b-ii.md").read_text()
    section = text.split("## Commands", 1)[1].split("\n## Tool versions", 1)[0]
    for index, block in enumerate(re.findall(r"```sh\n(.*?)```", section, re.S), 1):
        pathlib.Path(f"/tmp/wp53bii-block{index}.sh").write_text(block)
        print(index, len(block.splitlines()), "lines")
    PY

(dedent the heredoc before running it; it is indented here so the extractor
does not pick itself up as a seventh block) and run with `bash /tmp/wp53bii-block<n>.sh` in a worktree created at this
WP's commit, at a path this WP was not developed in. Results: block 1 printed
nothing from `git status --porcelain`, so every regenerated fixture and oracle
byte equals what is committed, and all fourteen digests match `## Metrics`;
block 2 reproduced `sha256 3444cdd4...711e6b`, 0 cross-check mismatches and
the branch counts below; block 3 was clean on fmt, clippy, nocomments and
every test binary; block 4 printed `MODE: skipped`, then `MODE: full` with
`COMPARED: 85 rasters, 85 inspection rows`, then the both-or-neither panic;
blocks 5 and 6 reproduced all seventeen probe outcomes and ended `RESTORED`
with a clean `git status`. The blocks are unchanged since that replay; only
this section and the Owns paragraph were edited after it.

## Tool versions

- rustc/cargo from the repository toolchain; `cargo fmt --check`,
  `cargo clippy --all-targets -D warnings`, `tools/nocomments.py` all clean.
- `uv run python` 3.12.11, Unicode 15.0.0. Pillow 12.3.0, pypdf 6.14.2.
- `pdftoppm` (Poppler) 25.08.0, asserted by `poppler_pinned()` in every raster
  test, the same pin WP-5.2 uses.
- Corpus: `editions/010/render-2026-09-14T01-49-02/en`, English, 56 reader
  pages, 28 booklet sides, 1 cover-booklet side. WP-5.3b-i measured on
  `render-2026-09-14T01-47-59/en`, a DIFFERENT render of the same edition
  (the two `reader.pdf` files differ by sha256); see `## Metrics` for what
  that does and does not change.

## Metrics

Live 010, `inspects_edition_010_like_python`, MODE full:

| measurement | result |
| --- | --- |
| rasters produced by `render_pages` byte-identical to Python's `_render_pages` output | **85 of 85** |
| `inspect_page` rows identical to Python's `_inspect_page`, Python's text fed in | **85 of 85** (56 reader + 28 booklet + 1 cover booklet) |
| reader rows cross-checked against the published `render-critic.json` | 56 of 56, 0 field mismatches outside `largest_void`/`voids`/`tail_band` |

With the tracer's own text (WP-5.3b-i's `page_text`) instead of pypdf's, on
the 56 reader pages, re-derived here rather than cited:

| field | agrees with pypdf |
| --- | --- |
| every raster field (`pixel_dimensions`, `ink_ratio`, `ink_bbox`, `presence_ratio`, `presence_bbox`, `sparse`) | **56 of 56** |
| `blank` | 56 of 56 |
| `ink_free` | 56 of 56 |
| `standalone_punctuation_lines` | 56 of 56 (empty-set agreement, see below) |
| `body_text_lines` | 49 of 56 |
| `text_characters` | 43 of 56 |
| whole row identical | 43 of 56 |

Rule 9, re-derivation at the point of citation: WP-5.3b-i's evidence records
`body_text_lines` 49 of 56 and `text_characters` 43 of 56 after its rework
(and 16 of 56 BEFORE it, under the `Show.width` unit defect; the plan's
prose at line 3843 still carries the pre-rework 16). Both post-rework figures
reproduce EXACTLY here, through a different pipeline (Python's own
`_inspect_page` as oracle rather than `-i`'s pypdf comparison) and on a
different render of the same edition. Configuration: edition 010, English, 56
reader pages, hyphenation as rendered, per page.

Committed oracle digests:

    c34f662213a68138437c402bcb4274adb160befe0bdb2912a3947cfebd39bd40  mag/tests/critic_inspect_expected.json
    eb7c183ac6be95e15f546bf517ad5bc410669cd6c914285120526602a2d4ad41  mag/tests/critic_inspect_render_expected.json
    b8f1a59573ece4797e80a17a11070fdf24f0554aaebd4291fea618e523d34f6c  mag/tests/critic_inspect_fixtures/pages12.pdf
    42cfeb41ca67eeb07e6c227800f3bbbf17ccfc06f35724780814446465144a2d  mag/tests/critic_inspect_fixtures/corner_edges.png
    1b9dfdc7852b898e0569075aa5b7e3ca8e0c9316b2c027fbddb28a5bbad5ea82  mag/tests/critic_inspect_fixtures/corner_ink.png
    d8b726e0cb0514ba4851d9e98faeb38353df9cdeb284499e636af6ab2feab03d  mag/tests/critic_inspect_fixtures/luma_edges.png
    d9e00d1ddcc7bb4784f645f25ace57095cb1f4a31785602b35e82827057a0641  mag/tests/critic_inspect_fixtures/luma_pins.png
    8231a74dea7887730907d950adcefba7fbb2ff2bf9bb65b830a02a3ff107dc17  mag/tests/critic_inspect_fixtures/luma_shifted.png
    a018aa49691a8a661e23c447dcb40ed57b3ac5b267b6eeec67ea10611a43ff1c  mag/tests/critic_inspect_fixtures/paper_tint.png
    ef66840596f664535126428db67dad9cd7a17be6922d606f40ca0452e4cc8965  mag/tests/critic_inspect_fixtures/pure_white.png
    386589829913caf4a9992a0f7f250ea19e95abdb0304186da42c832a348a690d  mag/tests/critic_inspect_fixtures/sparse.png
    b6f411762c6bf29900fd63ac60f00152832fe8e70345e16355f8b5b61f7007df  mag/tests/critic_inspect_fixtures/threshold_bands.png
    65a8dd8686a17f41ee7aa237daf9c12728011091a24684be8657321e0c8ff9b7  mag/tests/critic_inspect_fixtures/tie_down.png
    b296c461a4fd10bced8e7f3d3d208c367d0040c732d9e81390eddc994730a85e  mag/tests/critic_inspect_fixtures/tie_up.png

Live oracle produced by block 2 (outside the checkout, not committed):
`sha256 3444cdd4d05e78fedb2b8b1fb137d33f6520a4b8b01b13f8887e800577711e6b`,
206117 bytes.

Discrimination probes, block 5, fixture-only suite (9 tests). Every one FAILS
under the mutation and PASSES restored:

| probe | result |
| --- | --- |
| `WHITE_THRESHOLD` 245 -> 246 | FAILED 1 |
| `PAPER_WHITE` 255 -> 254 | FAILED 1 |
| `point_below` `<` -> `<=` | FAILED 1 |
| `ink_ratio` unrounded | FAILED 1 |
| `text_characters` counts bytes instead of codepoints | FAILED 1 |
| `blank` drops `&& stripped.is_empty()` | FAILED 1 |
| `ink_free` drops `&& stripped.is_empty()` | FAILED 1 |
| `sparse` admits a zero ratio | FAILED 1 |
| `getbbox` right edge inclusive | FAILED 1 |
| `grayscale` uses the float 299/587/114 formula | FAILED 1 |
| punctuation filter accepts EVERY line | FAILED 1 |
| punctuation filter accepts NOTHING | FAILED 1 |
| `RASTER_DPI` 144 -> 150 | FAILED 1 |
| normalised names drop the zero padding | FAILED 1 |
| shard windows off by one | FAILED 2 |

Both extremes of the punctuation filter fail, which is the rule-10 diagnostic
the last verifier used on WP-5.3b-i's join rule; there it exposed inert code,
here it confirms the fixture is doing work in both directions.

Live probes, block 6: `WHITE_THRESHOLD` 245 -> 246 fails at
`inspection row for reader page 1`; reversing the rendered-name ordering fails
at `raster bytes for reader page 1`. The second isolates the raster leg,
because the row leg reads Python's own PNGs and is unaffected by it.

## Verdicts

No `verdict.json` is produced or consumed by this WP. It adds no comparator
clause, touches no `parity.yaml`, and moves no baseline.

## What is and is not proven

PROVEN:

- **`_inspect_page` reproduces Python field for field on the live edition.**
  `inspects_edition_010_like_python` (MODE full), 85 of 85 rows across all
  three rasterisations, with Python's own text fed in so the text SOURCE is
  not part of the comparison. DISCRIMINATES: the live probe of
  `WHITE_THRESHOLD` fails on reader page 1; the fifteen fixture probes above
  each fail under mutation.
- **`render_pages` reproduces `_render_pages` byte for byte.** Same test, 85
  rasters, plus `render_pages_matches_python_on_the_fixture_pdf` on a
  committed 12-page PDF against sha256s produced by Python's `_render_pages`.
  DISCRIMINATES: reversing the rendered-name ordering fails the live raster
  assertion; `RASTER_DPI` 144 -> 150, dropping the zero padding, and an
  off-by-one in the shard windows each fail the fixture test.
- **The shard count does not affect the output.** Rule 11 applied to the
  mechanism rather than asserted:
  `render_pages_output_does_not_depend_on_the_shard_count` rasterises the same
  PDF with 1, 3, 5, 12 and the Python-derived default number of shards and
  compares all twelve PNGs byte for byte across the five runs. This is what
  makes the committed sha256 oracle machine-independent, since Python derives
  the shard count from `os.cpu_count()` and the port from
  `available_parallelism()`. DISCRIMINATES: the off-by-one window probe fails
  this test as well as the oracle test (FAILED 2).
- **PIL's `convert("L")` luma.** `grayscale_matches_pil_and_the_naive_formula_disagrees`
  compares the grayscale BYTES against PIL for four fixtures, and the
  histogram digest for each. DISCRIMINATES in the way the plan's luma pair
  demands: the test also asserts that the float 299/587/114 formula disagrees
  with PIL somewhere in the fixtures, which forced the `luma_edges.png`
  fixture into existence. The first version of the fixture set did NOT
  discriminate: the naive formula agreed on every pixel of a 4096-pixel random
  image, so the control was vacuous and said nothing. `luma_edges.png` is 64
  of the 139 RGB triples where the two formulas differ, found by search.
- **The three 010-unreachable row outcomes are covered by fixture**, each
  named below under the branch enumeration, each asserted in
  `inspect_page_matches_python_on_the_fixtures` against Python's own
  `_inspect_page` output for the same PNG and text, 15 of 15 rows identical.
- **`ImageChops.difference` and PIL's RGB histogram**, which WP-5.3b-iii needs
  for crop fidelity: `difference_and_rgb_histogram_match_pil` pins the
  768-bin histogram digest, the integer weighted total, and the resulting
  `rgb_mae` bit for bit against Python, on one pair that differs and one pair
  that does not. DISCRIMINATES: the zero pair and the 97.715 pair are both
  present and the test asserts both are, so the comparison cannot be satisfied
  by an all-zero histogram. Mismatched sizes are asserted to error rather than
  truncate.
- **serde_json's default float parser is not round-trip exact**, confirmed by
  removing the supposed cause and measuring: `97.71500651041667` parses to
  `0x40586dc2aaaaaaab` through `str::parse` and to `0x40586dc2aaaaaaac`
  through `serde_json::Value::as_f64`. `serde_json_parses_every_oracle_float_exactly`
  asserts every float literal in both committed oracles survives the
  round trip, and asserts that the known-bad literal still diverges, so the
  guard cannot silently become vacuous. `rgb_mae` is consequently carried in
  the oracle as TEXT, not as a JSON number.

NOT PROVEN:

- **Anything WP-5.3b-iii owns**: `largest_void`, `voids` and `tail_band` are
  emitted as Python's placeholders and nothing here computes them. Owner:
  WP-5.3b-iii.
- **LANCZOS resize to an arbitrary size**, the fourth raster helper the
  original WP-5.3b bullet named and the one `_inspect_opener_crop_fidelity`
  needs. NOT ported, deliberately: `metrics.rs:411 fn resize` is PIL's
  `Image.resize` already, verified by WP-5.3a, and is private to `metrics`, so
  `inspect` cannot call it and a second copy would be a duplicate whose oracle
  would be its sibling rather than Python. This is a FINDING, escalated in
  `## Status`: it needs one word of visibility in WP-5.3a's file, which this
  WP does not own.
- **The critic's text source.** Every text-derived field here is WP-5.3b-i's
  under this WP's oracle, because the live comparison feeds Python's text in.
  The separate tracer-text report above is a MEASUREMENT of that inheritance,
  not a proof of it: 43 of 56 reader rows are identical end to end, and the
  seven `body_text_lines` and thirteen `text_characters` differences are
  WP-5.3b-i's recorded and unresolved residuals.
- **`standalone_punctuation_lines` on the live edition.** Agreement is 85 of
  85, but the field is the EMPTY LIST on every page under both
  implementations, so this is an empty-set agreement in exactly rule 10's
  sense and is worth nothing beyond showing nothing was invented. The only
  real evidence for the field is the `punctuation` fixture, where both
  extremes of the filter fail.
- **`sparse` on the live edition.** Zero of 85 pages are sparse, so the field
  is the same constant throughout; its evidence is the `sparse` and
  `corner_ink` fixtures alone.
- **Python's `str.splitlines` beyond `\n`.** `standalone_punctuation_lines`
  uses Rust's `str::lines`, matching what WP-5.3b-i chose for
  `body_text_lines`, so both fields split identically. They diverge from
  Python for `\v \f \x1c \x1d \x1e \x85    ` and a lone `\r`.
  MEASURED, not assumed: block 2 scans all 85 pages of Python's own extracted
  text and finds NONE of those characters, so on this corpus the two splitters
  agree. Owner for the general case: whoever next owns `critic/text.rs`, since
  splitting there and here must stay identical.
- **Anything outside edition 010 English.** Spanish, other editions, other
  page geometries: untested. Two page geometries were exercised, 840x1191 and
  1684x1191.
- **`decode_rgb`'s image-format branches** are WP-5.3a's, re-exercised here
  only on 8-bit RGB PNGs, which is all `pdftoppm -png` emits.
- **A search that found nothing**: no grep or scan is offered above as proof
  of absence.

## Branches of `_inspect_page` and `_render_pages` that 010 cannot reach

Enumerated by reading `src/magazine/render_critic.py`, then measured against
the corpus, in that order, because reading the corpus for cases finds only the
branches the corpus has.

| branch in the Python | 010 | covered by |
| --- | --- | --- |
| `texts is None`, falling back to `pdf_page.extract_text() or ""` (:982) | never: all three call sites pass `texts=` | ELIMINATED by construction, the port takes text as a parameter |
| `_STANDALONE_PUNCTUATION.fullmatch` MATCHING (:986) | 0 of 85 rows | fixture `punctuation`: `,`, `…`, `?!`, `...`, `:;` match, `a.`, `-`, the blank line and a whitespace-only line do not |
| `0 < ratio < SPARSE_INK_RATIO` (:1011) | 0 of 85 rows | fixtures `sparse` (32/16384), `corner_ink`, `corner_edges` |
| `ratio == 0.0` feeding `sparse` false | 3 of 85 | also fixture `pure_white_no_text` |
| `pure_white` true WITH non-empty text, so `blank` is false (:1009) | 0 of 85 rows: no page is pure white and carries text | fixture `pure_white_with_text` |
| `ink_pixels == 0` WITH non-empty text, so `ink_free` is false (:1010) | 0 of 85 rows | fixtures `pure_white_with_text`, `paper_tint_with_text` |
| `ink_pixels == 0` while `pure_white` is FALSE, the two conditions coming apart | 0 of 85 rows | fixture `paper_tint_no_text`, every pixel at 250: `ink_free` true, `blank` false |
| `bbox` falsy -> `None` (:1005) | 3 of 85 | also fixture `pure_white_no_text` |
| the middle pixel class, `WHITE_THRESHOLD <= value < PAPER_WHITE` | present (page 1 ink 0.978 against presence 0.985) | also fixture `threshold_bands`, one column each at 244, 245, 254, 255 |
| `round(ratio, 6)` on an exact `.5` tie | no ratio on 010 lands on a tie | fixtures `tie_down` (1/128 -> 0.007812, down to even) and `tie_up` (3/128 -> 0.023438, up to even) |
| `len(text.strip())` over astral and multi-byte characters | reachable in principle, not isolated on 010 | fixture `astral_text`, U+1D41A and U+1F600: 7 codepoints, 11 bytes |
| `if total_pixels` false (:1001, :1002) | UNREACHABLE anywhere: PNG forbids a zero dimension, so `_render_pages` cannot produce one | ported for fidelity, deliberately uncovered, stated here rather than claimed |
| `_render_pages` `shard_count < 2`, the unsharded call (:943) | never on a 56-page or 28-page PDF; taken on the 1-page cover booklet | fixture probe with `shards = Some(1)` in the shard-invariance test |
| `_render_pages` `shutil.which` returning None (:890) | not reachable where poppler is installed | NOT COVERED. Testing it means mutating `PATH` process-wide, which races the other tests in the binary. The port raises the same message; nothing asserts it |
| `_render_pages` non-zero return code (:933) | not reachable on a valid PDF | `render_pages_reports_the_python_message_when_poppler_fails`, feeding poppler a non-PDF |
| `_render_pages` stdout-only and "unknown Poppler error" detail arms (:934) | not reachable | NOT COVERED, and neither arm changes any decision |
| `_render_pages` `PdfReader` raising -> `page_count = 0` (:939) | not reachable on a valid PDF | NOT COVERED. It collapses to the unsharded call, which IS covered |
| `_render_pages` `page_number` parse failure -> 0 (:952) | not reachable: `pdftoppm` always emits `page-<digits>.png` | NOT COVERED. The port additionally breaks the resulting tie by path, where Python leaves it to glob order; recorded as a deliberate determinism choice |
| `path != target` false, no rename (:957) | not reachable | NOT COVERED. Poppler pads the emitted name to the digit count of the DOCUMENT page count, measured: a 12-page PDF gives `page-03.png` even under `-f 3 -l 4`, an 8-page PDF gives `page-1.png`. So `page-<n>.png` equals `page-%03d.png` only for a document of 100 to 999 pages; 010's legs are 56, 28 and 1, and the fixture is 12 |

## Residuals

- **`metrics.rs:411 fn resize` is private and WP-5.3b-iii needs it.** Same
  shape as the plan's blocker 1, one level down: the capability exists, is
  verified, and is unreachable from the module that must consume it. One word,
  `pub(crate)`, in a file this WP does not own. I did not take it, and I did
  not write a second LANCZOS either, because two copies would be pinned to
  each other rather than each to Python. WP-5.3b-iii should not start crop
  fidelity until it is exposed.
- **`serde_json`'s float parser costs 1 ULP, and an existing test relies on
  it.** `mag/tests/critic_metrics.rs` compares WP-5.3a's ported metrics
  against its JSON oracle through `as_f64()` (`fn number`, :30). Its claim of
  EXACT equality is therefore exact only up to that parser. Nothing is known
  to be wrong: WP-5.3a's values are three-decimal rounded and its tests pass,
  and this WP's own guard shows every float in ITS oracles round-trips. But
  the guarantee is weaker than the wording, and the cheap fix for anyone who
  wants it is the `float_roundtrip` feature or carrying floats as text. This
  is a report, not a change; `mag/Cargo.toml` and `critic_metrics.rs` are not
  mine. NOT a live defect: no measured disagreement exists, only an unproven
  assumption.
- **`#[path]` includes.** `mag` has no library target, so an integration test
  cannot import the crate at all and every test in `mag/tests/` uses
  `#[path]`. Rule 12 asks what that therefore does NOT show: it does not show
  that `mag/src/critic/inspect.rs` is reachable from another module the
  ORDINARY way. What does show it is that `mag/src/critic.rs` declares
  `pub mod inspect;` and the binary compiles with `clippy -D warnings`, which
  exercises the real module graph including `crate::critic::metrics`,
  `crate::critic::text` and `crate::model::shared`. The test's alias modules
  reproduce those paths.
- **`render_pages` takes a `shards` parameter Python does not have.** It is a
  test seam and nothing but the shard-invariance test passes anything but
  `None`. Shown not to change the output.
- **`executable()` checks `is_file()` where `shutil.which` also checks the
  executable bit.** A non-executable file named `pdftoppm` earlier on `PATH`
  would be selected and then fail to run, where Python would skip it. Not
  reachable in practice, not covered.
- **The rendered-name tie break.** Python sorts by the trailing number with
  Python's stable sort over `Path.glob` order, so two files with the same
  number resolve by filesystem order; the port breaks the tie by path so it is
  deterministic. Only reachable with a stale output directory, which
  `inspect_render` prevents by removing `render-review` first.
- **`WORD_GAP_FRACTION = 0.25`** is untouched here, and remains, as
  WP-5.3b-i's verifier put it, unproven over any other value.
- The brief offered `editions/010/run-2026-09-13T01-34-51` for re-rendering.
  It was not needed and was not copied: the oracle is the Python render that
  already exists in `editions/010/render-2026-09-14T01-49-02/en`, whose
  `render-review` PNGs are what `_render_pages` actually produced and whose
  `render-critic.json` cross-checks the reader rows independently.

## Status

`done`, with one finding that belongs to someone else: `fn resize` in
`mag/src/critic/metrics.rs` must become `pub(crate)` before WP-5.3b-iii can
port `_inspect_opener_crop_fidelity`. That file is WP-5.3a's and this WP did
not touch it. Nothing in this WP is blocked by it.
