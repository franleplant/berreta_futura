# WP-0.2e close the display-list blind spots

## Base

6c13738 (plan revision 10). Work began at 7d79b9d; revision 10 landed mid-WP
and codified the glyph-count addition this WP had already been given by the
orchestrator, so the shipped code matches the current plan text exactly.

## Commands

Fixture generator, written to a scratch dir (never committed; fixture PDFs are
throwaway and `mag/tests/parity_faults*` belongs to WP-0.2d):

    mkdir -p "$TMP/wp02e"
    cat > "$TMP/wp02e/fixtures.py" <<'PY'
    <the generator, reproduced verbatim below under Fixture generator>
    PY
    cd "$TMP/wp02e" && python3 fixtures.py trees

Each variant is a 3-page A5 PDF whose interior (page 2) carries one text show
and one image. All five share a byte-identical font object (Type1 Helvetica,
FirstChar 65, Widths [556 556 1112], ToUnicode bfchar 41->0041, 42->0042,
43->00410042) so a variant differs only in the content stream under test.

    base            Tm 1 0 0 1 100 700     cm 100 0 0 50 100 500    show (AB)
    text_mirror     Tm -1 0 0 1 100 700    cm 100 0 0 50 100 500    show (AB)
    text_rot180     Tm -1 0 0 -1 100 700   cm 100 0 0 50 100 500    show (AB)
    image_flip      Tm 1 0 0 1 100 700     cm 100 0 0 -50 100 550   show (AB)
    glyph_ligature  Tm 1 0 0 1 100 700     cm 100 0 0 50 100 500    show (C)

Every variant is constructed to be INDISTINGUISHABLE under the pre-WP-0.2e
definition: `text_mirror` and `text_rot180` keep the show origin at
(100, 700); `image_flip` maps the unit square to the same bounding box
x [100, 200] y [500, 550] as `base`, with min/max over the corners erasing the
sign; `glyph_ligature` decodes to the same string "AB" at the same origin with
the same total advance (1112/1000 x 12 = 13.344 pt, equal to 556 + 556).

Fixture runs, new code (from the repo root, after `cargo build`):

    for v in base text_mirror text_rot180 image_flip glyph_ligature; do
      ./mag/target/debug/mag parity 010 --pre-rendered "$TMP/wp02e/trees/base" "$TMP/wp02e/trees/$v"
      echo "$v exit=$?"
    done

Fixture runs, pre-change code, which is what proves these are blind spots and
not merely faults:

    git worktree add "$TMP/wp02e/old" 7d79b9d
    cd "$TMP/wp02e/old/mag" && cargo build
    for v in text_mirror text_rot180 image_flip glyph_ligature; do
      "$TMP/wp02e/old/mag/target/debug/mag" parity 010 \
        --pre-rendered "$TMP/wp02e/trees/base" "$TMP/wp02e/trees/$v"
      echo "$v exit=$?"
    done

Edition 010 regression, twice each for byte determinism:

    A=editions/010/render-2026-09-14T01-47-59
    B=editions/010/render-2026-09-14T01-49-02
    ./mag/target/debug/mag parity 010 --pre-rendered $A $A
    shasum -a 256 output/parity/010/verdict.json
    ./mag/target/debug/mag parity 010 --pre-rendered $A $B
    shasum -a 256 output/parity/010/verdict.json

Both trees predate WP-1.5 (5504e5a), which disabled `:lang(en)` hyphenation
and rebroke 428 lines. They are used as a matched pair from one pre-switch
state, so A-vs-A still tests "same input twice" and A-vs-B "two independent
renders of one state". A freshly rendered tree will NOT reproduce these
digests and must never be compared against either of them.

### Fixture generator

    import pathlib, sys, zlib

    def build(objs):
        out = bytearray(b"%PDF-1.7\n"); offsets = []
        for i, body in enumerate(objs, 1):
            offsets.append(len(out))
            out += f"{i} 0 obj\n".encode() + body + b"\nendobj\n"
        xref = len(out)
        out += f"xref\n0 {len(objs) + 1}\n".encode() + b"0000000000 65535 f \n"
        for off in offsets:
            out += f"{off:010d} 00000 n \n".encode()
        out += f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
        return bytes(out)

    def stream(dict_extra, data):
        z = zlib.compress(data)
        return f"<< {dict_extra} /Filter /FlateDecode /Length {len(z)} >>\nstream\n".encode() + z + b"\nendstream"

    CMAP = b"""/CIDInit /ProcSet findresource begin
    12 dict begin
    begincmap
    1 begincodespacerange
    <00> <FF>
    endcodespacerange
    3 beginbfchar
    <41> <0041>
    <42> <0042>
    <43> <00410042>
    endbfchar
    endcmap
    CMapName currentdict /CMap defineresource pop
    end
    end
    """

    PIXELS = bytes([255, 0, 0, 0, 255, 0, 0, 0, 255, 255, 255, 0])

    def doc(tm, cm, shown="AB"):
        body = f"BT /F1 12 Tf {tm} Tm ({shown}) Tj ET\nq {cm} cm /Im1 Do Q\n".encode()
        blank = b"BT /F1 12 Tf 1 0 0 1 50 50 Tm (A) Tj ET\n"
        objs = [
            b"<< /Type /Catalog /Pages 2 0 R >>",
            b"<< /Type /Pages /Kids [3 0 R 4 0 R 5 0 R] /Count 3 >>",
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 420 595] /Resources << /Font << /F1 6 0 R >> >> /Contents 9 0 R >>",
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 420 595] /Resources << /Font << /F1 6 0 R >> /XObject << /Im1 8 0 R >> >> /Contents 10 0 R >>",
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 420 595] /Resources << /Font << /F1 6 0 R >> >> /Contents 11 0 R >>",
            b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /FirstChar 65 /Widths [556 556 1112] /ToUnicode 7 0 R >>",
            stream("", CMAP),
            stream("/Type /XObject /Subtype /Image /Width 2 /Height 2 /ColorSpace /DeviceRGB /BitsPerComponent 8", PIXELS),
            stream("", blank), stream("", body), stream("", blank),
        ]
        return build(objs)

    VARIANTS = {
        "base": ("1 0 0 1 100 700", "100 0 0 50 100 500", "AB"),
        "text_mirror": ("-1 0 0 1 100 700", "100 0 0 50 100 500", "AB"),
        "text_rot180": ("-1 0 0 -1 100 700", "100 0 0 50 100 500", "AB"),
        "image_flip": ("1 0 0 1 100 700", "100 0 0 -50 100 550", "AB"),
        "glyph_ligature": ("1 0 0 1 100 700", "100 0 0 50 100 500", "C"),
    }

    root = pathlib.Path(sys.argv[1])
    for name, (tm, cm, shown) in VARIANTS.items():
        d = root / name / "en"
        d.mkdir(parents=True, exist_ok=True)
        (d / "reader.pdf").write_bytes(doc(tm, cm, shown))

## Tool versions

rustc 1.96.0, poppler 25.08.0 (pdfinfo, pdftotext, pdftoppm; asserted at
startup from `parity.yaml tools:`), lopdf 0.45.0, python3 3.12.11 (fixture
generation only). No crate was added: the change needs none.

## Metrics

What the canonical display list now records, and the quantization rule:

- `Element::Text` carries the full text rendering matrix `m`, the glyph count
  `glyphs`, and drops the separate `x`/`y`. The matrix is
  `[Tfs x Th, 0, 0, Tfs, 0, Ts] . Tm . CTM`, so its translation components are
  exactly the old `(x, y)` (the old code computed `apply(Tm . CTM, 0, Ts)`,
  which is that product's translation row): nothing was removed, the position
  is now carried by the matrix that also witnesses orientation.
- Baking the font size and horizontal scaling INTO the matrix is what makes it
  engine-agnostic. An engine emitting `Tf /F1 9.5` with `Tm 1 0 0 1 x y` and
  one emitting `Tf /F1 1` with `Tm 9.5 0 0 9.5 x y` render identically; the raw
  `Tm` linear part would false-fail on that split, the product does not.
- `Element::Image` carries the placement matrix `m` (the CTM at the `Do`) in
  place of `rect`. The old bounding box was computed as min/max over the four
  transformed corners, which is precisely what erased the sign.
- All six components are quantized by the existing `qc` (0.01 pt), one
  rounding path, no new constant. Translation components are lengths, so the
  coordinate quantum applies directly. The linear components carry the font
  size, so they have units of points per unit of text space: quantizing them
  at the same 0.01 absolute flags a difference exactly when it would displace
  a glyph one text-space unit from the origin by more than the coordinate
  quantum. That is strict enough that every sign flip, every rotation beyond
  roughly 0.0006 radians and every skew differs, and coarse enough that an
  engine's decimal emission of a matrix cannot false-fail.
- `glyphs` is the count of character codes decoded per show, already computed
  in the decode loop. Raw CID codes are deliberately NOT recorded: the engines
  subset and assign codes independently, so codes would false-fail on every
  page.

Fixture matrix. Old = the pre-WP-0.2e comparator built from 7d79b9d; new =
this WP. Tier S text passes on all five variants, so text extraction cannot
see any of these faults either.

| fixture | old exit | old display list | new exit | new display list |
|---|---|---|---|---|
| base (control) | 0 | pass | 0 | pass |
| text_mirror | 0 | pass | 1 | fail (1 page) |
| text_rot180 | 0 | pass | 1 | fail (1 page) |
| image_flip | 0 | pass | 1 | fail (1 page) |
| glyph_ligature | 0 | pass | 1 | fail (1 page) |

Every one of the four faults passed before this WP and fails after it, which
is the whole claim: these were blind spots, not merely undetected faults.

Edition 010, 54 compared interior pages, every clause evaluated: A-vs-A and
A-vs-B both Tier E display-list equal, exit 0, unchanged from before this WP.
The additions can only fire on a genuine mirror, rotation, skew or reshaping,
and neither leg does any of those against the other.

## Verdicts

| run | verdict sha256 | result |
|---|---|---|
| 010 A-vs-A (twice) | fd6608a2db8f01fe... | all clauses pass, Tier E raster not_evaluated (WP-0.2f), exit 0 |
| 010 A-vs-B (twice) | 28d7c3a2b0374ab0... | all clauses pass, Tier E raster not_evaluated (WP-0.2f), exit 0 |

Both digests reproduced byte-identically across two consecutive runs, so
verdict determinism is intact.

The digests are unchanged between the matrix-only intermediate state and the
final state that also records glyph counts, because `verdict.json` records
clause outcomes rather than the display list itself, and every clause passes
in both. They DO differ from WP-0.2b's recorded 710878fb / a195f86d, which
predate the raster clause and report sections WP-0.2c added; that drift is not
attributable to this WP.

## Residuals

- The glyph-count addition and its ligature fixture came from the revision-9
  critique's finding 1, delivered mid-WP by the orchestrator; plan revision 10
  (6c13738) has since written both into the WP-0.2e section, so plan and code
  agree and no further alignment is owed.
- `mag/src/parity/display.rs` is in this WP's Owns but needed no change: its
  only use of a text element is `Element::Text { s, fill, .. }` in
  `color_sequence`, and its `rect` field is the annotation rect of the
  navigation clause, unrelated to image placement.
- WP-0.2f must derive its meaningfulness ceiling from fixtures covering the
  blind spots that REMAIN after this WP. Per revision 10 that is intra-show
  kerning whose adjustments cancel; the four faults above are no longer blind
  spots and must not be used for that derivation.
- `cargo test` could not be run in the shared working tree at commit time:
  concurrent WP-5.1b and WP-5.1c agents had `mag/src/model.rs` declaring
  modules whose files were still mid-edit (`file not found for module doc /
  manifest / records`). The suite was therefore run in a clean worktree
  containing only this WP's two source changes, where it passes; the failure
  is entirely outside this WP's Owns.

## Status

done
