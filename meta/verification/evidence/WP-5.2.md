# WP-5.2 booklet imposition

## Base

Started at 507d10c (plan revision 14), rebased onto `art_directed` at 443aaa8 before landing (earlier draft cited
18e35ed). Worked in the worktree
`/Users/franguijarro/.claude/jobs/7d99e27f/tmp/wp52`. No crate was added, so
`mag/Cargo.toml` and `mag/Cargo.lock` are untouched.

## Public surface WP-5.3b consumes

`render_critic.py` imports four names from `booklet.py`. All four are public
in `mag/src/impose.rs`, so WP-5.3b imports rather than copies:

| Python | Rust |
|---|---|
| `A4_LANDSCAPE_POINTS` | `impose::A4_LANDSCAPE_POINTS: (f64, f64)` |
| `section_reader_pages` | `impose::section_reader_pages(page_count, section) -> Result<Vec<usize>>` |
| `imposed_reader_page_plan` | `impose::imposed_reader_page_plan(&[usize]) -> Vec<(Option<usize>, Option<usize>)>` |
| `cover_wrap_plan` | `impose::cover_wrap_plan(page_count) -> Result<Vec<(Option<usize>, Option<usize>)>>` |

`booklet_spreads` and `BOOKLET_SECTIONS` are public too, since the first is
the arithmetic the other three rest on and the second is the validated set.

## How display-list equality is established without `mag parity`

The Phase 5 preamble forbids oracle tests from invoking the comparator, so
`mag/tests/impose.rs` carries its own comparison. It is not a second tracer:
it decodes each page's content stream with `lopdf`, emits one line per
operation with numeric operands at fixed precision, and replaces every
resource NAME operand with the SHA256 of the object that name resolves to in
that page's resource dictionary. Resolution follows references, hashes stream
bytes after decompression, and skips `Length`, `Filter` and `DecodeParms`
because those describe encoding rather than content.

Resolving names to content digests is what makes the comparison correct
without replicating pypdf's internals. pypdf renames a merged resource when a
key collides with a different value (`F1`, then `F1-0`, `F1-1`); the port has
its own collision handling. A name-level comparison would flag that as a
difference and a byte-level one would flag pypdf's encoder against lopdf's.
Digest resolution sees through both while still failing on any genuine change
of what is drawn, in what order, with what operands, against which font,
image or graphics state.

Raster and text are compared with the pinned poppler 25.08.0, asserted at
test start: `pdftoppm -r 150` per sheet compared by SHA256, and `pdftotext`
per document for spread order. Zero differing bytes is the bar, per the WP
bullet, because both legs place the same page content by the same arithmetic.

## Commands

Fixture sources and Python oracles (regenerates every committed fixture
byte-identically):

    uv run python -c '
    import sys, pathlib
    sys.path.insert(0, "src")
    from reportlab.pdfgen import canvas
    from reportlab.lib.colors import Color
    from pypdf import PdfReader, PdfWriter
    from magazine.booklet import impose_a5_on_a4
    d = pathlib.Path("mag/tests/impose_fixtures")
    A5 = (419.5276, 595.2756)
    def build(path, count, size):
        c = canvas.Canvas(str(path), pagesize=size)
        for i in range(count):
            c.setFont("Helvetica", 18)
            c.drawString(25, size[1] - 50, "Sheet page " + str(i + 1))
            c.setStrokeColorRGB(0.1, 0.25, 0.4); c.setLineWidth(1.5)
            c.rect(15, 15, size[0] - 30, size[1] - 80, stroke=1, fill=0)
            c.setFillColor(Color(0.85, 0.35, 0.1)); c.circle(size[0] / 2, size[1] / 2, 20 + 4 * i, stroke=0, fill=1)
            c.showPage()
        c.save()
    specs = {"p" + str(n): (n, A5) for n in range(1, 9)}
    specs["wide"] = (4, (800.0, 400.0))
    for stem, (count, size) in specs.items():
        build(d / (stem + ".src.pdf"), count, size)
    build(d / "crop.src.pdf", 4, A5)
    r = PdfReader(str(d / "crop.src.pdf")); w = PdfWriter()
    for p in r.pages:
        p.cropbox.lower_left = (10, 12); p.cropbox.upper_right = (A5[0] - 8, A5[1] - 6); w.add_page(p)
    with (d / "crop.src.pdf").open("wb") as h: w.write(h)
    for src in sorted(d.glob("*.src.pdf")):
        stem = src.name[:-8]
        for sec in ["all", "interior", "cover"]:
            try:
                impose_a5_on_a4(src, d / (stem + "." + sec + ".pdf"), section=sec)
            except ValueError as exc:
                print("skip", stem, sec, exc)
    '

Pure-function oracle (regenerates `mag/tests/impose_plan_expected.json`):

    uv run python -c '
    import json, sys
    sys.path.insert(0, "src")
    from magazine.booklet import booklet_spreads, section_reader_pages, imposed_reader_page_plan, cover_wrap_plan, A4_LANDSCAPE_POINTS
    counts = list(range(0, 25)) + [28, 36, 52, 56, 60, 100, 101]
    sections = ["all", "interior", "cover", "spine", "", "Cover", "all ", chr(39) + "q", chr(34) + "d", "z" + chr(8203), "b" + chr(7), "a" + chr(0xF0000)]
    out = {"a4_landscape_points": list(A4_LANDSCAPE_POINTS), "spreads": {}, "section_pages": {}, "plans": {}, "cover_wrap": {}}
    for n in counts:
        out["spreads"][str(n)] = [list(s) for s in booklet_spreads(n)]
        for sec in sections:
            key = str(n) + "|" + sec
            try:
                out["section_pages"][key] = {"ok": list(section_reader_pages(n, sec))}
            except ValueError as exc:
                out["section_pages"][key] = {"err": str(exc)}
        try:
            out["cover_wrap"][str(n)] = {"ok": [list(s) for s in cover_wrap_plan(n)]}
        except ValueError as exc:
            out["cover_wrap"][str(n)] = {"err": str(exc)}
    for length in range(0, 18):
        out["plans"]["seq" + str(length)] = [list(s) for s in imposed_reader_page_plan(list(range(1, length + 1)))]
    for name, pages in {"gap": [3, 4, 7, 8, 11], "single": [5], "pair": [2, 9]}.items():
        out["plans"][name] = [list(s) for s in imposed_reader_page_plan(pages)]
    json.dump(out, open("mag/tests/impose_plan_expected.json", "w"), indent=1, sort_keys=True)
    '

Committed suite:

    cd mag && cargo test --test impose

Live edition 010 (the reader.pdf is untracked; both legs use the SAME file,
so it needs no re-render). Python leg:

    uv run python -c '
    import sys, pathlib
    sys.path.insert(0, "src")
    from magazine.booklet import impose_a5_on_a4
    src = pathlib.Path("editions/010/render-2026-09-14T01-49-02/en/reader.pdf")
    out = pathlib.Path("/tmp/wp52-010"); out.mkdir(parents=True, exist_ok=True)
    for sec in ["all", "interior", "cover"]:
        impose_a5_on_a4(src, out / ("py." + sec + ".pdf"), section=sec)
    '

Rust leg and comparison (both variables or neither; exactly one panics):

    cd mag && MAG_IMPOSE_READER=$PWD/../editions/010/render-2026-09-14T01-49-02/en/reader.pdf \
      MAG_IMPOSE_ORACLE_DIR=/tmp/wp52-010 \
      cargo test --test impose imposition_matches_python_on_the_live_edition

## Tool versions

python 3.12.11, uv 0.8.17, pypdf 6.14.2, reportlab 5.0.0, poppler 25.08.0
(asserted by the suite), rustc 1.96.0, lopdf 0.45.0. No crate was added.

## Metrics

### Branch enumeration, read from the Python

| branch | reached by 010 | covered by |
|---|---|---|
| `booklet_spreads` count a multiple of 4 | yes | 010, p4, p8 |
| `booklet_spreads` count not a multiple of 4 | NO | p1, p2, p3, p5, p6, p7, oracle counts 0-101 |
| `section_reader_pages` unknown section | NO | 12 section names including quote and non-printable cases |
| `section_reader_pages` "all" | yes | 010, every fixture |
| `section_reader_pages` page_count < 4 refusal | NO | p1, p2, p3 for both cover and interior |
| `section_reader_pages` "cover" | yes | 010, p4-p8, wide, crop |
| `section_reader_pages` "interior" | yes | 010, p4-p8, wide, crop |
| `section_reader_pages` interior empty (count 4) | NO | p4 interior, 0 sheets |
| `imposed_reader_page_plan` no padding | yes | 010 all/interior/cover |
| `imposed_reader_page_plan` 1, 2, 3 pads | NO | seq lengths 0-17, p5, p6, p7 |
| spread with one `None` half | NO | p1, p2, p3, p5, p6, p7 |
| spread with BOTH halves `None` | NO | p1 (a sheet with no content stream at all) |
| `cover_wrap_plan` first spread only | yes | 010 cover, oracle counts 0-101 |
| scale height-bound | yes | 010 and every A5 fixture |
| scale width-bound | NO | wide (800x400 pages, scale 0.52618113) |
| CropBox differing from MediaBox | NO | crop |
| `impose_a5_on_a4` pypdf import failure | n/a | not ported; the Rust port has no optional dependency |

Edition 010 is 56 pages, so every signature arithmetic other than "already a
multiple of four" is unreachable from it, as is every refusal. Fixtures carry
all of them.

### Results

Pure functions: 469 oracle cases, all equal to Python, including all 12
refusal messages.

Imposition, committed fixtures: 24 cases (10 sources x valid sections).
Display lists equal, rasters byte-equal at 150 dpi, `pdftotext` equal, sheet
counts equal. The 0-sheet case (p4 interior) is asserted as equal sheet
counts and skips rasterization, which poppler cannot perform on an empty
document.

### The sheet 3 investigation

The first live run passed the display list and `pdftotext` on all 28 sheets
of `--section all` and then failed the raster on sheet 3. That ordering is
the finding: identical drawing operations, different pixels.

Measured first, before reasoning. Sheet 3 at 150 dpi is 1754x1241, and the
two PPMs differ in **381 bytes of 6,530,142, maximum channel delta 4**,
confined to x 1072-1327, y 278-1008. That rules out the alarming hypotheses
immediately: a wrong page, a swapped spread or a shifted placement would move
large areas, and WP-0.2f measured that a sub-pixel origin shift against a
grid-fitting rasterizer produces deltas of 241. A handful of edge pixels at
delta 4 is antialiasing responding to a sub-quantum coordinate change.

The cause is that **edition 010's pages do not all carry the same box
precision**:

    pages 1 and 56   MediaBox 0 0 419.5276   595.2756
    pages 2 to 55    MediaBox 0 0 419.527559 595.275591

Pages 1 and 56 are the covers `replace_outer_pages` splices in; pages 2-55
are WeasyPrint's, and their six-decimal values need more precision than an
`f32` holds. lopdf parses every real as `f32`, so the port read 419.52756 and
595.2756 where Python read 419.527559 and 595.275591. The consequence lands
in `scale = min(half / width, A4_height / height)`: Python computes
**1.0000000151**, the port computed **exactly 1.0**, and the emitted clip
rectangle differed in its last decimals too.

The reason this survived the display-list comparison is a weakness in that
instrument worth recording: it formats numeric operands at six decimals, so
1.0000000151 and 1.0 compare **equal**. The raster leg is what caught it,
which is the argument for keeping both legs rather than treating display-list
equality as sufficient.

Sheets 1 and 2 passed because sheet 1 is `(56, 1)`, both cover pages, whose
values do round-trip through `f32`; sheet 2 is interior on both halves but
happened to have no edge sitting on a pixel boundary. Whether a 9e-6 pt shift
flips a pixel is content-dependent, which is exactly why one sheet of 28 was
the symptom.

Fixed by recovering the authored decimals from the file's raw bytes, with a
loud refusal when they cannot be recovered. See Residuals.

### Live edition 010

`reader.pdf` from `editions/010/render-2026-09-14T01-49-02/en/`, 56 pages,
87 MB. Both legs impose the SAME file, so no re-render is involved and the
pre-`5504e5a` vintage of that tree does not matter.

| section | sheets | display list | pdftotext | raster |
|---|---|---|---|---|
| all | 28 | equal | equal | byte-identical |
| interior | 26 | equal | equal | byte-identical |
| cover | 1 | equal | equal | byte-identical |

55 sheets, zero differing bytes at 150 dpi, 1527 s.

### Discriminating proofs

Every ported behaviour was reverted in place and the suite re-run. Six
perturbations, six caught; restored to green each time.

| perturbation | caught by |
|---|---|
| `booklet_spreads` second term `-1` to `-2` | plans, display list, raster (3 tests) |
| `real()` fixed at 6 decimals | raster, via the `wide` fixture |
| `py_repr` astral branch dropped to `\uNNNN` | plans oracle (measured against the then-local copy, before the helper was replaced by the shared import) |
| scale height taken from CropBox | display list, raster, via `crop` |
| clip rectangle taken from MediaBox | raster, via `crop` |
| `authored_boxes` returning nothing | the fail-loud refusal, all imposition tests |

The `crop` fixture is what makes the last three discriminate: edition 010's
CropBox equals its MediaBox on every page, so the corpus alone cannot tell
the two apart.

## Verdicts

- `cargo test` across the whole crate: 11 suites, 0 failures.
- `cargo fmt --check` and `cargo clippy --all-targets -- -D warnings`: clean.
- `cargo test --test impose`: 4 passed, 23.9 s.
- Live edition 010, all three sections: passed, 1527 s.
- Pure-function oracle: 469 cases equal to Python, refusal messages included.
- Committed fixture imposition: 24 cases, display list, raster and text equal.

## Residuals

- **`py_repr` is imported, not copied.** `section_reader_pages`'s
  unknown-section refusal embeds Python's `!r`. The first draft of this WP
  carried a fourth copy of `py_repr` with a copy-agreement test, because the
  helper was then private in both `model/records.rs` and
  `model/manifest.rs`. WP-5.1d landed while this WP was in flight and lifted
  it to `pub(crate) model::shared::py_repr`, so the copy and its agreement
  test were deleted and `impose.rs` now imports the shared one. Nothing is
  lost in coverage: the plans oracle compares the refusal message against
  Python for twelve section names including a zero-width space, a BEL, an
  astral character and both quote kinds, and the discriminating proof shows
  dropping the astral branch fails that oracle.
- **lopdf parses PDF reals as `f32`, and on edition 010 that was a real
  defect, found by the raster leg after the display list had passed.** The
  detail is in Metrics under "The sheet 3 investigation". The port now
  recovers the authored decimal text of `MediaBox` and `CropBox` by scanning
  the file's raw bytes, and **fails loud** rather than silently placing a
  page at `f32` precision when it cannot. **WP-5.4, WP-5.5 and any comparator
  WP doing arithmetic on numbers lopdf parsed will hit the same wall**, and a
  per-WP workaround is the wrong shape for it: this deserves a shared exact
  number path, or a documented decision that `f32` geometry is acceptable
  everywhere except imposition. It is flagged here rather than solved here
  because a shared utility is outside this WP's Owns.
- **The recovery does not work for every PDF.** It reads `N G obj` headers
  and `/MediaBox`/`/CropBox` arrays out of the uncompressed file, so a PDF
  that stores page dictionaries in an object stream (`/ObjStm`) yields
  nothing and the port refuses instead of degrading. Edition 010's
  `reader.pdf` carries no object streams and all 56 boxes are in plain bytes.
  WeasyPrint does not emit object streams today; if that changes, this
  refusal fires and the fix is a real parser rather than a scan.
- **pypdf's float formatting is replicated exactly**: zero prints as `0.0`,
  otherwise the value is formatted to `8 - trunc(log10(abs(v)))` decimals
  (minimum 1) and stripped of trailing zeros then a trailing point. This was
  not cosmetic: truncating to 6 decimals wrote `0.526181` where pypdf writes
  `0.52618113`, and the `wide` fixture's rasters differed as a result.
- **Source page content is passed through byte-for-byte** when no resource
  rename is needed, which is the case for every fixture and for all of 010.
  It is decoded and re-encoded only when a name must be rewritten, matching
  pypdf, which returns the stream unchanged when its rename map is empty.
- The port does not reproduce `DependencyError` for a missing pypdf, since a
  Rust binary has no equivalent optional import.
- The imposed output keeps the source document's object graph and replaces
  its page tree, so fonts and images are shared rather than copied. Orphans
  are pruned before writing.

## Status

done
