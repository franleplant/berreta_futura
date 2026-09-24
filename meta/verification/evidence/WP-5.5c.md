# WP-5.5c package and SHA256SUMS

## Base

`d4866a0` (art_directed).

## What changed

- `mag/src/package/release.rs`: `package_release` port of `package.py`, in
  Python's order (copy reader, impose all/interior/cover, write
  edition-manifest.json, critic, contact sheets, render-critic.json, fail on a
  critic error, printing instructions, studio note, preflight.json,
  SHA256SUMS sorted by relative path). Also the report-dict assembly and
  `_visual_review_status` from `render_critic.py:551-815`, which WP-5.3b-iii
  left unported (its finding 1), `_adopt_rendered_layout`, `sha256`,
  `_printing_instructions`, `_studio_note`, and `py_json`, a writer that
  reproduces `json.dumps(ensure_ascii=False, indent=2, sort_keys=True)`
  including Python's float repr.
- `mag/src/package/contact.rs`: `_write_contact_sheets` (`render_critic.py:1384`),
  with a port of Pillow's BICUBIC `ImagingResample` for `ImageOps.fit`, and
  the `PAGE nnn` labels drawn from `label_glyphs.txt`, the FreeType masks
  Pillow 12.3.0's default font (Aileron Regular 10, FreeType 2.14.3, basic
  layout) produces for `"PAGE "` and each digit, blended with Pillow's
  `fill_mask_L` rounding.
- `mag/src/package/archive.rs`: `_archive_tree` from
  `engine_render_bridge.py:277`, since the WP's oracle names the archives.
- `mag/src/package/preflight.rs`: `Pdf`, `read`, `page_count`, `all_near`
  made `pub(crate)` (visibility only), so the report reuses the page reader
  rather than a third copy.
- `mag/src/package.rs`: declares the three new modules.
- `mag/tests/package.rs`, `mag/tests/package_fixtures/`.

## Measured first: the dependency the earlier review raised

Byte-equal `SHA256SUMS` is NOT reachable, and not only because of the
contact sheets. Measured on 010 (122 digested entries):

| class | entries | cause |
|---|---|---|
| byte-equal | 90 | reader.pdf, edition-manifest.json, preflight.json, instructions, studio note, 85 pdftoppm rasters (56 reader, 28 booklet, 1 cover side) |
| pixel-equal, bytes differ | 28 | 22 crops + 6 contact sheets. Pillow encodes PNG with `optimize=True` through zlib-ng (`PIL.features.version("zlib")` = `1.3.1.zlib-ng`); the port uses the `png` crate |
| PDF bytes differ | 3 | the booklets: pypdf vs lopdf serialization (WP-5.2 already proved display lists equal and rasters byte-equal; here the 29 booklet rasters are byte-equal too) |
| report differs | 1 | render-critic.json: `visual_review.booklet_sha256` digests the booklet bytes above, and 56 text leaves differ because the Rust critic reads the tracer where Python reads pypdf (WP-5.3b-i's recorded decision) |

So SHA256SUMS itself differs, and would differ even with perfect contact
sheets. What was portable within the WP was ported: the contact sheets are
pixel-equal (they were not ported at all before), the report dict is
byte-equal to Python's up to the two stated causes, and every entry is
checked at the strongest level its bytes allow.

## Commands

Spec (same inputs both sides; the figure and cover paths are the tracked
originals, as in WP-5.5b):

```
R=editions/010/render-2026-09-14T01-49-02/en   # in the main tree
S=/Users/franguijarro/.claude/jobs/7d99e27f/tmp
uv run python -c "
import json, pathlib
R=pathlib.Path('/Users/franguijarro/code/magazine/$R')
archived = json.load(open(R/'preflight.json'))
manifest = json.load(open(R/'edition-manifest.json'))
images = {
 'four-incidents': 'library/sources/an-alignment-assessment-of-recent-cybersecurity-415f8f1a/media/001.png',
 'agent-usage-growth': 'library/sources/the-third-era-of-ai-software-development-7395f18d/media/001.png',
 'recursive-planners': 'library/sources/towards-self-driving-codebases-3fd7b9ca/media/004.png',
}
figs = [{'figure_id': f['figure_id'], 'article_id': f['article_id'], 'page': f['page'],
         'path': str(pathlib.Path(images[f['figure_id']]).resolve()),
         'pixel_dimensions': f['pixel_dimensions'], 'box_points': f['box_points'],
         'effective_ppi': f['effective_ppi'], 'caption': f['caption'], 'credit': f['credit']}
        for f in archived['figures']]
lay = manifest['layout']
spec = {'reader_pdf': str((R/'reader.pdf').resolve()), 'manifest': manifest,
        'cover_art': str(pathlib.Path('editions/010/art/rounds/2026-09-13T01-40-20/cover-wildcard-sign-punched-v3.png').resolve()),
        'cover_art_size_points': None, 'figures': figs, 'language': 'en',
        'toc': lay['toc'], 'article_pages': lay['article_pages'], 'editorial_pages': lay.get('editorial_pages'),
        'edition_id': '010'}
pathlib.Path('$S/spec.json').write_text(json.dumps(spec, indent=2, ensure_ascii=False))
"
```

Spec sha256 `dd74ec7ecf15c695b73d6db92793ec5f074d42744088a1820a4969a990b491f3`.

Python oracle (pypdf text, the shipped behaviour), into `$S/py-out`:

```
uv run python -c "
import json, pathlib, sys
sys.path.insert(0,'src')
from magazine.package import package_release
spec = json.load(open('$S/spec.json'))
class P:
    def __init__(s, d):
        s.figure_id=d['figure_id']; s.article_id=d['article_id']; s.page=d['page']
        s.path=pathlib.Path(d['path']); s.pixel_dimensions=tuple(d['pixel_dimensions'])
        s.box_points=tuple(d['box_points']); s.effective_ppi=d['effective_ppi']
        s.caption=d['caption']; s.credit=d['credit']
files = package_release(pathlib.Path(spec['reader_pdf']), pathlib.Path(sys.argv[1]), spec['manifest'],
  cover_art=pathlib.Path(spec['cover_art']), cover_art_size_points=spec['cover_art_size_points'],
  figure_placements=[P(f) for f in spec['figures']], language=spec['language'],
  toc=spec['toc'], article_pages=spec['article_pages'], editorial_pages=spec['editorial_pages'],
  edition_id=spec['edition_id'], recorded_review=None)
print(len(files))
" $S/py-out
```

Exit 0, 123 files, 28.8 s. Its SHA256SUMS equals the SHIPPED
`$R/SHA256SUMS` on every line except `preflight.json` (whose `path` fields
name the staging directory), so the Python side is run-to-run deterministic.

Tracer text dump and the Python oracle with the tracer substituted for
pypdf, exactly WP-5.3b-iii's block-4 substitution, into `$S/py-tracer-out`:

```
cd mag && MAG_CRITIC_RENDER_DIR=$S/py-out MAG_CRITIC_RULES_TEXT=$S/tracer-text.json \
  cargo test --release --test critic_rules dumps_the_tracer -- --nocapture
```

(exit 0, `MODE: full`, 56/28/26/1 pages; sha256 `e68b23f8...bbbd1948`), then
the same `package_release` invocation as above with this prologue before the
call and `$S/py-tracer-out` as argument:

```
import magazine.render_critic as critic
traced = json.load(open('$S/tracer-text.json'))
by_pages = {len(traced[leg]['raw']): traced[leg] for leg in ('reader','booklet','interior','cover')}
original = critic._PageTexts
class Tracer(original):
    def __init__(self, document): self._rows = by_pages[len(document.pages)]
    @property
    def page_count(self): return len(self._rows['raw'])
    def raw(self, n): return self._rows['raw'][n - 1]
    def normalized(self, n): return self._rows['normalized'][n - 1]
critic._PageTexts = Tracer
```

Its SHA256SUMS differs from `py-out` on `render-critic.json` only.

Gated comparison (both modes, rule 2b):

```
cd mag && MAG_PACKAGE_SPEC=$S/spec.json MAG_PACKAGE_ORACLE=$S/py-out \
  MAG_PACKAGE_TRACER_ORACLE=$S/py-tracer-out \
  cargo test --release --test package -- --nocapture --test-threads 1
cd mag && cargo test --test package -- --nocapture     # prints MODE skipped
```

Python failure-path reference (critic error, message and what is left):

```
uv run python -c "
import json, pathlib, sys
sys.path.insert(0,'src')
from magazine.package import package_release
spec = json.load(open('$S/spec.json'))
out = pathlib.Path(sys.argv[1])
try:
    package_release(pathlib.Path(spec['reader_pdf']), out, spec['manifest'], language='en', toc=spec['toc'], article_pages=spec['article_pages'], editorial_pages=3, edition_id='010')
except Exception as e: print(type(e).__name__, e)
print(sorted(p.name for p in out.iterdir()))
" $S/py-fail-out
```

prints `ValidationError Render critic rejected en reader: editorial-page-cap`
and a directory without preflight.json, SHA256SUMS, instructions or studio.

Fixtures (`mag/tests/package_fixtures/expected.json`, the four synthetic
pages and the tree) are generated by one inline script, run from the
worktree root as `uv run python - <<'EOF' ... EOF`:

```
import hashlib, json, sys, tempfile, zipfile
from pathlib import Path
sys.path.insert(0, "src")
from PIL import Image
import magazine.render_critic as critic
from magazine.package import _printing_instructions, _studio_note
from magazine.engine_render_bridge import _archive_tree
root = Path("mag/tests/package_fixtures")
sizes = [(130, 184), (300, 200), (200, 330), (97, 61)]
paths = []
for index, (w, h) in enumerate(sizes):
    image = Image.new("RGB", (w, h))
    image.putdata([((x * 7 + y * 3 + index * 50) % 256, (x * y + index) % 256, (255 - x * 5 + y) % 256)
                   for y in range(h) for x in range(w)])
    path = root / "pages" / f"page-{index + 1:03d}.png"
    image.save(path)
    paths.append(path)
pages = [paths[i % 4] for i in range(17)]
out = Path(tempfile.mkdtemp())
sheets = critic._write_contact_sheets(pages, out, prefix="fixture-sheet")
def pixels(p):
    with Image.open(p) as im:
        im = im.convert("RGB")
        return hashlib.sha256(im.width.to_bytes(4, "little") + im.height.to_bytes(4, "little") + im.tobytes()).hexdigest()
floats = [1e-05, 1.5e-07, 1e16, 1234567890123456.0, 1.0, 0.0001, 123456789012345680.0, -0.0, 0.1, 2.5e-310, 1e22, 12345.678, -3.0e-5]
values = {"floats": floats, "ints": [0, -7, 2**63 - 1], "text": "ñ \"q\" \\ \n\t\x01\x7f  é", "empty": [[], {}],
          "nested": {"b": [1, {"z": None, "a": True}], "a": False, "É": "x", "Z": 1}}
archive = _archive_tree(root / "tree", out / "tree.zip")
with zipfile.ZipFile(archive) as z:
    entries = [[i.filename, i.date_time, i.external_attr, i.compress_type, i.CRC, i.file_size] for i in z.infolist()]
expected = {
    "sheet_pixels": [pixels(p) for p in sheets],
    "sheet_names": [p.name for p in sheets],
    "json_input": values,
    "json_text": json.dumps(values, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    "instructions": {lang: _printing_instructions(lang, reader_page_count=56, all_in_one_sheets=14, interior_sheets=13, cover_sheets=1)
                     for lang in ["en", "es", "es-AR", "fr", "esp"]},
    "studio": {lang: _studio_note(lang) for lang in ["en", "es", "es-AR", "fr", "esp"]},
    "archive_entries": entries,
}
(root / "expected.json").write_text(json.dumps(expected, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
```

The tree is `a.txt` (`alpha\n`), `sub/b.md` (`beta\n`), `sub-c.json`
(`gamma`), `ñ.txt` (`ñandú\n`). expected.json sha256 `306a48f8...71266d98`.

The glyph atlas: `for key, text in [('prefix', 'PAGE ')] + [(c, c) for c in
'0123456789']: m, o = ImageFont.load_default().getmask2(text, 'L')`, each
asserted at offset (0, 2) and height 8, written as `key width hex`. The
atlas composition (prefix mask at x 0, digit masks at 27 + 6k) was checked
against Pillow's own `getmask2(f'PAGE {n:03d}')` for n = 1..1199: 0
mismatches. A max-composition of per-glyph masks does NOT reproduce it (A
and G overlap by one pixel at (12, 9), 41 + 1 = 42), which is why the prefix
is one mask.

Rest: `cd mag && cargo fmt --check && cargo clippy --all-targets -- -D warnings && cargo test`:
fmt exit 0, clippy clean, `cargo test` exit 0 with every binary `ok` (the
package binary 42 passed in skipped mode; rust_helpers 2 passed after the
fix recorded under Duplicated helpers).

## Tool versions

rustc 1.96.0, python 3.12.11, Pillow 12.3.0 (FreeType 2.14.3, zlib-ng
1.3.1, raqm absent), pypdf 6.14.2, poppler 25.08.0.

## Metrics

Live 010, gated run, exit 0, 42 passed in 63.7 s:

```
CLASSES {"bytes": 90, "pdf": 3, "pixels": 28, "report": 1}
REPORT vs tracer-text Python: ["/visual_review/booklet_sha256"]
REPORT vs pypdf-text Python: 57 leaves, 56 text fields
SHEET reader-contact-sheet-01..04, booklet-contact-sheet-01..02: differing channel bytes 0
```

- Entry list and order: equal (122 names).
- Every Rust SHA256SUMS line is its file's actual digest (self-check).
- The 3 PDF entries: page counts equal (28 / 26 / 1 sides).
- render-critic.json: identical to the tracer-substituted Python report in
  every leaf except `booklet_sha256`, which the test asserts equals the Rust
  booklet's own digest. Against the pypdf report the 57 differing leaves are
  that one plus 56 `text_characters` / `body_text_lines` leaves, the
  text-source difference only.
- Archive: `archive_tree(ours, ours/package.zip)` holds exactly the 122
  entries plus SHA256SUMS, sorted, and not itself.
- Failure run (`editorial_pages` 3): error `Render critic rejected en reader:
  editorial-page-cap` (Python's text, measured above), render-critic.json
  written with `result` fail, preflight.json / SHA256SUMS / instructions /
  studio absent.

Skipped mode prints `MODE skipped, env not set: MAG_PACKAGE_SPEC,
MAG_PACKAGE_ORACLE, MAG_PACKAGE_TRACER_ORACLE`; setting only some of them
fails the test.

**Found while porting the contact sheets: Pillow passes the resize box as C
`float`.** `_resize` parses the box `(ffff)` and `precompute_coeffs` takes
`float in0, in1` and computes `scale` as `(double)(in1 - in0) / outSize`.
With the box kept in f64 the reader sheet differed from Pillow in 182 channel
bytes (max delta 1); with the box and the subtraction in f32 it is 0 on all
six sheets. FMA contraction was tested first and changed nothing.

### Fixtures, and the branches 010 cannot reach

| branch | test |
|---|---|
| contact sheet: `live == output` ratio (no crop), wider (crop width), taller (crop height), upscaling (97x61 source), a second sheet (17 pages), empty page list | `contact_sheets_match_pillow_on_equal_wide_tall_and_upscaled_pages` (pixel digests from Pillow) |
| Python float repr at both exponent boundaries (1e-05 / 0.0001, 1234567890123456.0 / 1e16), subnormal, -0.0, big ints, control and non-ASCII escapes, U+2028, empty containers, non-ASCII key order | `json_writer_reproduces_python_dumps_with_indent_and_sorted_keys` |
| Spanish, `es-AR`, unknown language, `esp` (not a base-`es` tag) for instructions and studio note | `printing_instructions_and_studio_note_match_python_for_every_language_branch` |
| ledger present / present with existing layout / null / edition not a mapping / no ledger / no edition; layout not a mapping | `adopting_the_rendered_layout_moves_only_a_present_non_null_ledger` |
| review absent, approved, changes required, stale by edition, by missing language row, by moved digest, by no languages; string findings | `visual_review_status_covers_every_recorded_review_branch` |
| zip entry names (incl. non-ASCII, `sub-c` vs `sub/` order), date 1980-01-01, external attr 0o100644, deflate, CRC, sizes, contents | `archive_entries_match_python_zipfile_metadata_and_contents` |

Perturbations, each ONE step and each run: bicubic `a` -0.5 to -0.6, the
resize box nudged by 1e-4, the label x origin 7 to 8, the blend `255 - a` to
`256 - a`: the fixture sheet test FAILS on each. `py_float` fixed range
`-4..16` moved to `-5..16`, `-4..15` and `-4..17`, and the exponent's `{:02}`
to `{}`: the json test FAILS on each. All restored and green.

Refusal classification: the critic-failure bail is MESSAGE-ONLY (its
threshold, the editorial cap, is the critic's and is fixtured by WP-5.3b);
the three visual-review bails and the layout bail are MESSAGE-ONLY
(categorical type checks).

## Deliberate divergences

All toward diagnosis where Python crashes; all covered by tests:

| input | Python | Rust |
|---|---|---|
| `_rendered_tail_arts` present, `layout` not a mapping | TypeError / AttributeError | bail `manifest layout must be a mapping to adopt the rendered tail arts` |
| recorded review not a mapping | AttributeError | bail `a recorded visual review must be a mapping` |
| review `languages` present but not a mapping | AttributeError | bail `...languages must be a mapping` |
| review `findings` null / number / bool | TypeError | bail `...findings must be iterable` |

One divergence is NOT toward diagnosis and is recorded rather than fixed: a
review whose `findings` is a MAPPING. Python's `list(dict)` gives the keys
in insertion order; the Rust `Value` has already sorted them (serde_json
without `preserve_order`), so the keys come out sorted. The only production
caller (`engine_render_bridge.py:343`) passes `recorded_review=None`, so
every non-None review branch is unreachable today.

## Duplicated helpers, and why

- The bicubic resampler duplicates the SHAPE of `metrics.rs`'s private
  Lanczos `resize`, which hardcodes its filter and is WP-5.3a's, outside this
  WP's Owns. Strong form: pinned to Pillow by its own oracle (six live sheets
  and two fixture sheets pixel-equal), not to its sibling.
- The contact sheet's PNG save repeats the five `png`-crate lines of
  `rules.rs`'s private `write_png`, inlined at its one call site; neither is
  byte-matched to anything. `tests/rust_helpers.rs` caught the first draft's
  same-signature copy (and a copy of `model/manifest.rs::relative_posix`,
  now a posix-only `strip_prefix(...).to_string_lossy()`), both measured
  failing and fixed before landing. Making `rules.rs::write_png`
  `pub(crate)` would remove the repetition; that file is WP-5.3b's.

## Unicode and copy

The printing instructions carry U+2014 in Python's shipped copy and the
oracle is byte equality, so the port emits it through `\u{2014}` escapes; no
literal U+2014 is authored.

## What is and is not proven

PROVEN on 010: the entry list and its order; 90 entries byte-equal to
Python; 28 PNGs pixel-equal; the three booklets page-count equal; the
critic report equal to Python's with the same text source except the one
field that digests the booklet bytes; the failure path's message, its
written report and the four files it must not write; the archive's contents.

NOT PROVEN, with the precise gap (fail loud):

- **SHA256SUMS is not byte-equal and cannot be within this WP.** 32 of 122
  lines differ: 3 booklet PDFs (pypdf vs lopdf serialization), 28 PNGs
  (Pillow's `optimize=True` through zlib-ng vs the `png` crate; pixels
  equal), render-critic.json (booklet digest, and pypdf vs tracer text), so
  SHA256SUMS' own digest differs too. Closing it needs PDF writer parity
  with pypdf and a zlib-ng-exact PNG encoder with Pillow's filter choice and
  IDAT chunking; neither is a package concern. What the test pins instead
  is per-entry: bytes where the bytes are the port's, pixels where the
  encoder is not, structure plus the WP-5.2 display-list proof for the PDFs.
- **Archives are compared per entry, not byte for byte.** Deflate output
  differs (flate2's miniz vs zlib-ng); names, order, dates, attributes,
  method, CRC, sizes and contents match Python on the fixture, and the live
  archive's membership is checked. `package.zip` is still built by the
  Python bridge in production; WP-5.6 wires this one.
- **That any value is CORRECT** beyond equality: the contact sheets, report
  and instructions are equal to Python's, and Python's `result` for 010
  (`pass`, 4 review issues) is the critic's editorial question, not this
  WP's.
- **Labels for page 1000 and above** are covered only by the Python-side
  atlas check (n up to 1199), not by a Rust fixture: no edition has that
  many pages and a fixture would need 1000 rasters.
- **The label atlas is tied to Pillow 12.3.0 / FreeType 2.14.3.** A Pillow
  upgrade that changes the default font or its hinting changes Python's
  sheets and not the port's; the live sheet test would then fail loudly.

## Findings for others

1. **`critic/metrics.rs::resize` passes its box as f64, and Pillow uses C
   float** (see the measurement above). `thumbnail` feeds it
   `(0, 0, w / factor, h / factor)` after `reduce`, which is not
   f32-exact whenever the reduce factor does not divide the size (e.g.
   3073 / 3). 010 cannot show it: its figures reduce by factor 1 and the
   cover by 2 (2160 / 2 exact). Owner WP-5.3a (preflight's contrast
   analysis consumes it). Latent, unmeasured on metrics.rs itself.
2. `package.zip` / `web-output.zip` are built by `engine_render_bridge.py`,
   not `package.py`; `archive_tree` is ported here because this WP's oracle
   names the archives, and WP-5.6 should call it rather than re-port it.
