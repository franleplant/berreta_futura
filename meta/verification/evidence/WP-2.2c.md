# WP-2.2c placement

## Base

- **Re-landed at `art_directed` `0494017`.** The work below was measured at
  `0cd65b2` and parked as `b31c05e`; it was cherry-picked onto `0494017`
  (clean apply, no conflict) in a fresh detached worktree at `.../tmp/wp22c2`,
  and this slice then landed WP-2.2b's rework, the opener-title tracking
  (`### The opener title tracking` under `## Metrics`). Steps 1 to 5, 7 and 8
  of `## Commands` were re-run there; step 6 was not (it touches nothing this
  WP owns and its table is dated below). Numbers in `## Metrics` are the
  re-run's unless a row says otherwise.
- Measured at `art_directed` **`0cd65b2`** (`verify(parity): WP-0.2i accepted`)
  with this WP's diff applied, in a detached worktree at `.../tmp/wp22c2`.
  **The first worktree of this WP (`.../tmp/wp22c`, based at `746a649` and
  then `3449552`) was deleted from disk under the agent** between two rate-limit
  kills, with the diff uncommitted. Every file was reconstructed from the exact
  edit scripts in the transcript and one `/tmp` copy of the template, and the
  reconstruction was verified against the pre-loss measurement: the typst leg
  compiled to the **same sha256 `99ff9ae2...`** the deleted worktree had
  produced at the same template state. The orphan/widow discriminator under
  `## Metrics` was measured in the deleted worktree at base `746a649`; it
  changes nothing this WP owns and is reported with that base, not re-run,
  except for the single re-derivation in `## Commands` step 6.
- Owns, per the WP-2.2 preamble and the brief: `mag/assets/typeset/template.typ`,
  `mag/src/typeset/template.rs`, the new submodule `mag/src/typeset/media.rs`
  (declared by the one line `pub(crate) mod media;` in `mag/src/typeset/mod.rs`,
  which Rust requires to introduce a submodule at all), the fixtures under
  `mag/tests/typeset_fixtures/media/`, and this file.
- **Scoped Owns extension, granted by the coordinator in flight**: `Writer::figure`
  in `mag/src/typeset/content.rs`, to emit one named argument carrying the
  figure's natural pixel size. The extension's spirit required `figure()` to
  return `Result`, and that propagates through `article_body` (its return type,
  two `?` call sites, one `Ok(out)`); those five lines are the whole ripple and
  are recorded here rather than left to be found. Nothing else in `content.rs`
  changed. Rule 1's alternatives were rejected: a panic or a silent zero height
  both violate rule 6.
- `world.rs`, `mod.rs` (beyond the one line), `render.rs`, `parity*`,
  `parity.yaml`, `baseline.json` and `weasyprint-a5.css` were read and **not
  written**. The stylesheet was edited only as an uncommitted ablation and
  restored (step 6 checks it is unchanged afterwards). No crate was added.

## Commands

Run from the root of a checkout at `## Base` with the WP's diff applied, built
once with `cargo build --manifest-path mag/Cargo.toml`. `RUN` is the untracked
010 content run both legs render; `MAG_PARITY_OUT_DIR` keeps this WP's
comparator output out of the shared `output/parity/010` (WP-0.2k). Step 6
edits `src/magazine/assets/weasyprint-a5.css` and restores it; it needs
`DYLD_FALLBACK_LIBRARY_PATH` only for the synthetic WeasyPrint probe.

```sh
set -o pipefail
unset TYPST_ROOT

RUN=${RUN:-editions/010/run-2026-09-13T01-34-51}
OUT=${OUT:-$PWD/output/parity-wp22c}
test -d "$RUN" || { echo "point RUN at the staged 010 content run"; exit 1; }

# 1. The hermetic suite and its two totals, re-derived rather than cited.
(cd mag && cargo fmt --check && cargo clippy --all-targets -- -D warnings && cargo test)
(cd mag && cargo test 2>&1 | grep -cE '^\s+Running')
(cd mag && cargo test 2>&1 | grep -E '^test result' | awk -F'[ ;]' '{s+=$4} END {print s}')

# 2. WP-2.1's projection oracle, before and after this WP's emitter change.
#    The oracle is built from the WeasyPrint-side reader text, so it does not
#    see the emitter; the test then projects THIS tree and compares. Both the
#    oracle digest and the compared character count are printed.
./mag/target/debug/mag render 010 --engine typst --no-model --langs en --run "$RUN" > /dev/null
TYPST=$(ls -d editions/010/render-* | tail -1)
STAGE=$(mktemp -d)
uv run python mag/tests/typeset_oracle.py stage --request "$TYPST/request.json" --into "$STAGE/live" --artifact-root .
uv run python mag/tests/typeset_oracle.py project --root "$STAGE/live" --edition 010 \
  --publication-name "Berreta Futura" --out "$STAGE/oracle-010.json"
uv run python -c "
import json,hashlib,sys;t=json.load(open(sys.argv[1]))['text']
print('oracle chars',len(t),'bytes',len(t.encode()),'sha256',hashlib.sha256(t.encode()).hexdigest())" "$STAGE/oracle-010.json"
(cd mag && MAG_TYPESET_ROOT="$STAGE/live" MAG_TYPESET_ORACLE="$STAGE/oracle-010.json" \
  MAG_TYPESET_PUBLICATION="Berreta Futura" cargo test --bin mag the_live_edition -- --nocapture 2>&1 \
  | grep -E 'compared|skipped|test result')
grep -h "pixels:" "$TYPST"/typst/pieces/*.typ

# 3. THE TARGET: page count, per-article spans and plate pages on both legs.
#    Article starts are located by each article's own title text; blank pages
#    are located by having no extractable text, so neither leg's structure is
#    assumed. The oracle leg is rendered here rather than taken from a cache.
./mag/target/debug/mag render 010 --engine weasyprint --no-model --langs en --run "$RUN" > /dev/null
ORACLE=$(ls -d editions/010/render-* | tail -1)
echo "oracle leg: $ORACLE"; echo "typst leg:  $TYPST"
cat > "$STAGE/spans.py" <<'PY'
import re, subprocess, pathlib, sys
def count(pdf):
    return int(re.search(r"Pages:\s+(\d+)", subprocess.run(["pdfinfo", pdf], capture_output=True, text=True).stdout).group(1))
def titles(pieces):
    return [re.sub(r"\\(.)", r"\1", re.search(r"#piece-title\[(.*?)\]\n", p.read_text(), re.S).group(1))
            for p in sorted(pathlib.Path(pieces).glob("*.typ"))]
def starts(pdf, names):
    n = count(pdf)
    txt = [re.sub(r"\s+", " ", t) for t in subprocess.run(["pdftotext", pdf, "-"], capture_output=True, text=True).stdout.split("\f")]
    return n, [next(p for p, t in enumerate(txt[:n], 1) if p > 3 and re.sub(r"\s+", " ", title) in t) for title in names]
def blanks(pdf, n):
    return [p for p in range(1, n + 1) if len(subprocess.run(["pdftotext", "-f", str(p), "-l", str(p), pdf, "-"],
            capture_output=True, text=True).stdout.strip()) < 30 and p > 3]
def spans(n, s, b):
    return [min([p for p in b if p > s[i]] + ([s[i + 1]] if i + 1 < len(s) else []) + [n + 1]) - s[i] for i in range(len(s))]
names = titles(sys.argv[2]); n, s = starts(sys.argv[1], names); b = blanks(sys.argv[1], n); sp = spans(n, s, b)
print(f"pages: {n}"); print(f"blank/plate pages past the contents: {b}")
for i, t in enumerate(names): print(f"{t[:46]:46s} start {s[i]:3d} span {sp[i]:3d}")
print(f"TOTAL article pages: {sum(sp)}")
PY
echo "--- weasyprint"; uv run python "$STAGE/spans.py" "$ORACLE/en/reader.pdf" "$TYPST/typst/pieces"
echo "--- typst";      uv run python "$STAGE/spans.py" "$TYPST/en/reader.pdf"  "$TYPST/typst/pieces"
shasum -a 256 "$TYPST/en/reader.pdf"

# 4. The comparator. It now proceeds PAST page_count and aborts in its tracer
#    on the first typst page it reads; the exit status and the operator it
#    names are the measurement. No verdict.json is written (see Verdicts).
MAG_PARITY_OUT_DIR="$OUT" ./mag/target/debug/mag parity 010 --run "$RUN" > "$STAGE/parity.log" 2>&1
echo "parity exit=$?"
grep -E "^(error|tier S page_count)" "$STAGE/parity.log" || true
ls "$OUT"
uv run python - "$TYPST/en/reader.pdf" "$ORACLE/en/reader.pdf" <<'PY'
import sys, re, pypdf
from collections import Counter
for pdf in sys.argv[1:]:
    data = pypdf.PdfReader(pdf).pages[2].get_contents().get_data().decode("latin1")
    print(pdf.split("/")[-3], "page 3 colour operators:",
          dict(Counter(re.findall(r"(?<![\w/])(cs|CS|scn|SCN|rg|RG|g|G)(?=\s)", data))))
PY

# 5. Figure geometry on the three figure pages, both legs: FIGURE label text
#    and x, label-to-caption distance, and the anchor heading's x. These are
#    the values the template owns; same-page y equality is WP-3.4's.
uv run python - "$ORACLE/en/reader.pdf" "$TYPST/en/reader.pdf" <<'PY'
import re, subprocess, sys
def words(pdf, page):
    out = subprocess.run(["pdftotext","-f",str(page),"-l",str(page),"-bbox-layout",pdf,"-"],capture_output=True,text=True).stdout
    return [(float(m.group(1)), float(m.group(2)), m.group(5)) for m in re.finditer(r'<word xMin="([\d.]+)" yMin="([\d.-]+)" xMax="([\d.]+)" yMax="([\d.-]+)">([^<]*)<', out)]
for page, head in ((12, "How"), (37, "Agent"), (42, "design")):
    for pdf, name in ((sys.argv[1], "weasyprint"), (sys.argv[2], "typst")):
        ws = words(pdf, page)
        lab = [w for w in ws if w[2] == "FIGURE"][0]
        num = [w for w in ws if abs(w[1]-lab[1]) < 0.5 and w[2] != "FIGURE"][0]
        cap = [w for w in ws if w[1] > lab[1] + 150 and w[0] < 50][0]
        hd = [w for w in ws if w[2] == head][0]
        print(f"{name:11s} p{page}: '{lab[2]} {num[2]}' x={lab[0]:.3f} | label->caption {cap[1]-lab[1]:.3f} | '{head}' x={hd[0]:.3f}")
PY

# 6. The orphan/widow discriminator, re-derived at one point each side of the
#    binding threshold: the oracle at orphans/widows 7 paginates as shipped (2)
#    and at 8 it does not. The stylesheet is restored and checked afterwards.
for N in 7 8; do
  uv run python - "$N" <<'PY'
import pathlib, re, sys
p = pathlib.Path("src/magazine/assets/weasyprint-a5.css"); s = p.read_text()
s2 = re.sub(r"p \{ margin: 0 0 5\.4pt; orphans: \d+; widows: \d+; \}",
            f"p {{ margin: 0 0 5.4pt; orphans: {sys.argv[1]}; widows: {sys.argv[1]}; }}", s)
assert s2 != s; p.write_text(s2)
PY
  ./mag/target/debug/mag render 010 --engine weasyprint --no-model --langs en --run "$RUN" > /dev/null
  echo "--- weasyprint at orphans/widows $N"
  uv run python "$STAGE/spans.py" "$(ls -d editions/010/render-* | tail -1)/en/reader.pdf" "$TYPST/typst/pieces" | grep -E "^pages|^blank|Frontier|TOTAL"
done
uv run python - <<'PY'
import pathlib, re
p = pathlib.Path("src/magazine/assets/weasyprint-a5.css"); s = p.read_text()
p.write_text(re.sub(r"p \{ margin: 0 0 5\.4pt; orphans: \d+; widows: \d+; \}", "p { margin: 0 0 5.4pt; orphans: 2; widows: 2; }", s))
PY
git diff --stat -- src/magazine/assets/weasyprint-a5.css | grep . || echo "stylesheet restored, no diff"
DYLD_FALLBACK_LIBRARY_PATH=${DYLD_FALLBACK_LIBRARY_PATH:-/opt/homebrew/lib} uv run python - <<'PY'
import weasyprint
def html(orph, h):
    return f"""<html><head><style>@page {{ size: 200pt 160pt; margin: 10pt; }}
body {{ font-family: serif; font-size: 10pt; line-height: 12pt; }} p {{ margin: 0; orphans: {orph}; widows: {orph}; }}
.f {{ height: {h}pt; }}</style></head><body><div class="f"></div><p>{'alpha beta gamma delta epsilon zeta eta theta iota kappa ' * 6}</p></body></html>"""
def lines(orph, h):
    out = []
    for page in weasyprint.HTML(string=html(orph, h)).render().pages:
        n = 0
        def walk(b):
            nonlocal n
            if type(b).__name__ == "LineBox": n += 1
            for c in getattr(b, "children", ()): walk(c)
        walk(page._page_box); out.append(n)
    return out
print("weasyprint", weasyprint.__version__, "filler 120pt: orphans/widows 1 ->", lines(1, 120), " 2 ->", lines(2, 120))
PY

# 7. Determinism of the typst leg.
./mag/target/debug/mag render 010 --engine typst --no-model --langs en --run "$RUN" > /dev/null
shasum -a 256 "$TYPST/en/reader.pdf" "$(ls -d editions/010/render-* | tail -1)/en/reader.pdf"

# 8. The opener title tracking: on each of the nine opener pages, the title's
#    line count, first-line word count and first-line width on both legs.
#    Title lines are the lines at least 0.8x the page's tallest line.
cat > "$STAGE/titles.py" <<'PY'
import re, subprocess, sys
def lines(pdf, page):
    out = subprocess.run(["pdftotext","-f",str(page),"-l",str(page),"-bbox-layout",pdf,"-"],capture_output=True,text=True).stdout
    return [(float(l.group(1)), float(l.group(3)), float(l.group(4)) - float(l.group(2)), re.findall(r'>([^<]*)</word>', l.group(5)))
            for l in re.finditer(r'<line xMin="([\d.]+)" yMin="([\d.]+)" xMax="([\d.]+)" yMax="([\d.]+)">(.*?)</line>', out, re.S)]
def title(pdf, page):
    ls = lines(pdf, page); big = max(h for *_, h, _ in ls)
    return [(x1 - x0, ws) for x0, x1, h, ws in ls if h > big * 0.8]
for p in [4, 7, 11, 17, 31, 36, 40, 46, 50]:
    a, b = title(sys.argv[1], p), title(sys.argv[2], p)
    print(f"p{p:2d} lines {len(a)}/{len(b)} | first-line words {len(a[0][1])}/{len(b[0][1])} | width {a[0][0]:.2f}/{b[0][0]:.2f} delta {b[0][0]-a[0][0]:+.2f}")
PY
uv run python "$STAGE/titles.py" "$ORACLE/en/reader.pdf" "$TYPST/en/reader.pdf"
```

## Tool versions

- rustc 1.96.0; `typst*` crates pinned `=0.15.1`, `lopdf` 0.45.0, `png` 0.18
  already present. **This WP adds no crate and touches neither `Cargo.toml`
  nor `Cargo.lock`**; the PNG and JPEG headers are read by 40 lines in
  `media.rs` rather than by a decoder, because only the frame size is wanted
  and a decoder dependency would have put this WP under rule 1a for nothing.
- poppler 25.08.0 (`pdfinfo -v`, matching `parity.yaml:271`; the parked file said 25.09.1, WP-2.2b's defect G carried forward, corrected here); WeasyPrint 69.0 (the oracle leg and the synthetic probe);
  CPython 3.12.11 through `uv run python`; Pillow 12.3.0 generated the three
  media fixtures (40x25 PNG, 17x29 JPEG, 11x13 WebP).
- No typst CLI; `TYPST_ROOT` unset and irrelevant.

## Metrics

Every number below is from `## Commands` at `0494017` with this diff and the
tracking fix, except the orphan/widow table, measured in the deleted worktree
at `746a649` and re-derived at its two boundary values by step 6 at `0cd65b2`.

| quantity | value |
| --- | --- |
| **typst leg pages / weasyprint leg pages** | **56 / 56** (WP-2.2b: 55 / 56) |
| article pages, weasyprint / typst | **46 / 46** (WP-2.2b: 46 / 45) |
| articles whose page span matches the oracle | **9 of 9** |
| articles whose START page matches the oracle | **9 of 9**: 4, 7, 11, 17, 31, 36, 40, 46, 50 on both legs |
| closing-plate pages, weasyprint / typst | **10, 30, 35, 45, 54 on both legs** (WP-2.2b: typst 49-53, trailing) |
| `FIGURE 01` label printed on the figure page, x | 3 of 3; x 42.520 / 44.000 / 42.520, **exact on both legs** |
| label-to-caption distance, three figures | oracle 223.944 / 206.261 / 206.261; typst 223.826 / 206.143 / 206.143; **delta 0.118 pt** on all three = `figcaption`'s 0.1166 pt paint correction (:1184-1190), ink only |
| anchor heading x on the figure page | 42.520 / 42.520 / 75.820 on both legs (the 4.004 pt escape is applied, and applied identically) |
| figure block y on its page, oracle minus typst | +54.4 / +15.4 / +80.4 pt: content above the figure differs, WP-3.1's rows and WP-3.4's images; same-page placement is met, same-y is not claimed |
| WP-2.1 projection oracle | **68,758 characters / 69,097 bytes, sha256 `bec79cc1aa9f...`, before and after**; `compared the live edition: 68758 characters` both times |
| `pixels:` arguments emitted | 3: `(2000, 1418)`, `(2400, 1350)`, `(2400, 1350)`, read from the staged PNG headers |
| typst PDF sha256, two renders of one staged input set | identical, **`02417ef38b39...`** (`23bbbe107f13...` before the tracking fix, at `0cd65b2` and again at `0494017` with the fix reverted) |
| opener title lines / first-line words equal to the oracle's | **9 of 9 / 9 of 9** (before the fix: 9 / 5 of 9) |
| opener title first-line width, typst minus oracle | **-0.53 to -0.82 pt** on all nine (before the fix: +25.1 to +33.1 pt on five, the break different on four) |
| comparator exit / verdict written | **1 / none**: `tracing page 3 ... operator cs: unsupported operator cs` |
| page-3 colour operators, typst / weasyprint | `cs` 48, `scn` 48 / `rg` 48 |
| `cargo test` binaries / tests, all passing | **25 / 265** at `0494017` with this diff and the tracking test (24 / 235 at `0cd65b2`; WP-2.2b landed at 23 / 221) |

### The opener title tracking (WP-2.2b's rejection)

WP-2.2b's verifier found `OPENER-TITLE-TRACKING = -0.045` declared and read
nowhere. Its Python source is `weasyprint-a5.css:1495-1499`,
`article[data-article-opener="illustrated_paper_spots_v1"] > header > h1 {
letter-spacing: -.045em }`: the illustrated opener's title, at render only.
The adapter's fit (`_fitted_display` -> `_wrap`, `weasyprint_adapter.py`)
takes no tracking argument, so the fit is untracked. The template now matches
that scope: `opener-page` sets the title inside
`text(..tracked(OPENER-TITLE-TRACKING * fit.size), ...)`, and `fitted-title`
still measures `opener-title-text` untracked. `opener-title-text` has no other
caller.

- Measured on 010 (step 8): same line count and same first-line words as the
  oracle on all nine openers, first-line width within 0.53 to 0.82 pt,
  typst narrower on all nine. The residual is not explained; it is of the
  size of one glyph's tracking (`0.045 x ~30 pt`) or less, and a trailing
  tracking step after the last glyph is one hypothesis, not tested.
- Positive control, the same script with the fix reverted in the same
  worktree: +31.73 / +29.09 / +29.20 / +33.05 / +25.12 pt on the five
  openers whose break matched, and the break different on Dario, third-era,
  DeepSeek and Storage, exactly WP-2.2b's verifier's measurement. The
  reverted leg hashed `23bbbe107f13...`, the parked leg's hash, so the fix is
  the whole of the difference.
- Page count and all nine spans and starts are unchanged by the fix (56 / 46,
  step 3), as the verifier predicted: the opener page is filled either way.
- Committed test `the_opener_title_is_set_with_its_tracking` compiles fixture
  901 (an illustrated opener) with the template and with the constant zeroed
  and requires different PDF bytes. **It failed with the fix reverted**
  (`OPENER-TITLE-TRACKING reaches no glyph on the illustrated opener`) and
  passes with it. It proves the constant reaches the ink; it does not pin
  the direction or the magnitude, which step 8 measures on 010.

### The central question, answered by measurement

WP-2.2b left the figure account of the missing page competing with the
orphan/widow account, and left one datum against the figure account: two of
the three figure-carrying articles matched the oracle with their figures
unplaced. Both accounts were tested by removing the supposed cause.

**Orphan/widow control, oracle side.** `weasyprint-a5.css:549` rewritten and
the oracle re-rendered at each value (base `746a649`):

| `orphans`/`widows` | pages | article pages | starts | note |
| --- | --- | --- | --- | --- |
| 1 (the sanctioned change) | 56 | 46 | identical to 2 | **page-count-neutral** |
| 2 (shipped) | 56 | 46 | 4, 7, 11, 17, 31, 36, 40, 46, 50 | |
| 4 | 56 | 46 | identical | neutral |
| 6, 7 | 56 | 46 | identical | neutral |
| **8** | 56 | **47** | dario 13 -> 14 | **first binding value** |
| 12 | 56 | 47 | | |
| 99 | 56 | 47 | plates 10, 31, 45, 54, 55 | pagination and plate arithmetic both move |

So the mechanism is **live in WeasyPrint 69.0** (synthetic probe: a paragraph
that would leave one line on the first page splits `[1, 8]` at `orphans: 1`
and moves whole, `[0, 9]`, at `orphans: 2`), **live on 010** (it binds at 8),
and **inert on 010 across 1..7** because the corpus's tightest paragraph
split leaves seven lines. Inert is not absent. The 1..7 interval contains both
the shipped value and the sanctioned change, so the change **cannot move the
page count on this corpus and is not applied**; WP-4.3 inherits nothing.

**Orphan/widow control, typst side.** The plan's premise that Typst 0.15.1
has no mechanism is **false**: `text.costs.widow` and `text.costs.orphan`
(`typst-library-0.15.1/src/text/mod.rs:576-595`) default to 100%, which
prevents a single line on either side of a page break, and `0%` allows it.
That default IS `orphans: 2; widows: 2`. The typst leg has honoured the
constraint since WP-2.2a with no template code. Ablated on 010 by setting
both costs to `0%`: 56 pages, every span identical, **bytes differ**, and
`pdftotext` differs on pages 27, 28, 29, 32, 33, 34, 52, 53 (page 27 gains a
line, page 29 loses one), so the constraint binds on 010 at the line level
while staying page-count-neutral, exactly as on the oracle side. The
committed test `typst_prevents_orphans_and_widows_by_default_as_the_stylesheet_does`
carries the claim the corpus cannot: a synthetic run whose straddling
paragraph pushes a third page under the default and not under `0%`.

**Figures.** With the three figures' flow reserved (`13.1 + image + 6.3 +
text + 15.75`, image fitted from the pixel size): `the-third-era` **stays
4**, `towards-self-driving` **stays 5**, `an-alignment-assessment` goes
**5 -> 6**, and every start page lands on the oracle's. Placing the figures
is page-neutral on the two articles that already matched and closes the one
that did not. **The figure account stands, and the orphan/widow account is
excluded rather than argued away.** The reason the two matched with figures
unplaced is now visible in the measurement rather than assumed: their last
pages carried more open room than the figure block needs, which is also why
both print a tail ornament in the oracle (`layout.tail_arts`, 108.3 pt each).

### Ablations of this WP's own mechanisms

| removed | 010 result |
| --- | --- |
| figure image reservation (heights zero) | 55 pages, 45 article pages, `an-alignment-assessment` 5: **the reservation is the page** |
| plate interleaving | 55 pages with plates trailing at 49-53; page count unchanged, five plate pages either way |
| escape expressed as `pad` instead of `inset` (the first spelling) | 010 identical at 56 / 46 while the synthetic anchor test found **no** effect of the dropped space-before; on p42 the anchor heading sat 5.4 pt lower than under the shipped spelling. Recorded as measured; the mechanism (a `pad` altering how the inner block's weak spacing collapses) is a hypothesis. The shipped spelling is the one the synthetic test proves operative. |
| escape expressed as weak `v` outside a `pad` | **article 1 gains a page** (57 / 47): weak `v` beside paragraph spacing does not collapse as `block.above` does. Rejected by measurement. |

## Defects found

1. **`pad` is not a margin.** Wrapping a block in `pad(left: -x, right: -y)`
   to escape the measure changed how the block's `above`/`below` spacing met
   its neighbours (table above). CSS negative margins map to a block
   **`inset`** with negative values, which keeps the block's own box on the
   column and its spacing semantics unchanged; that is what ships. Found by
   the synthetic anchor test failing at both extremes (rule 10's second
   half), not by the corpus, which paginated identically under both.
2. **The comparator cannot trace a Typst PDF.** `typst-pdf` writes every RGB
   fill as an ICC-based colour space, `/c0 cs ... scn`; the tracer at
   `mag/src/parity/streams.rs:327` supports `rg` and bails on `cs`. WP-2.2b's
   PDF has the same 48 `cs` on page 3; nothing could see it while
   `page_count` gated the run. **Comparator territory (rule 4); not fixed
   here.** Class: a comparator gap, not a port gap. See Status.
3. **The figure's flow height depends on the image's natural size**, which was
   in nothing the template could reach. Fixed through the granted extension:
   `content.rs` states `pixels: (w, h)` from the staged file's header and the
   template fits `min(width / w, max-height / h)` at layout time
   (`fitted-image-height`, `layout(size => ...)`). Refusals are loud: a figure
   with no `pixels` fails compilation naming the figure; a non-PNG/JPEG or an
   unreadable header refuses by path in `media.rs`.
4. **The figure label baseline** first sat 2.47 pt high: `flat` edges put the
   baseline on the box top, where the CSS's `line-height: 0` puts it
   `ZERO-LEADING-SANS` below. Measured as a 2.36 pt label-to-caption excess on
   all three figures, fixed to `FIGURE-LABEL-PAD + ZERO-LEADING-SANS` = 6.8 pt
   = `CAPTION_SIZE` (:1069-1072), leaving the 0.118 pt paint correction.

## Mapping table

Extending WP-2.2b's. Every transcribed value cites its `weasyprint-a5.css`
selector or adapter site; found-but-not-transcribed is PENDING with an owner.

### Transcribed by this slice

| template.typ | value | origin |
| --- | --- | --- |
| `figure-block` unbreakable, no space above, `FIGURE-GAP` 15.75pt below | `figure { break-inside: avoid }` (:1004), `article > figure[data-figure-id] { margin: 0 0 15.75pt }` (:1059-1061) and `_figure_geometry` comment (:1034-1047) |
| `FIGURE-LABEL-ZONE` 13.1pt, `FIGURE-LABEL-PAD` 4.32625pt, baseline at 6.8pt | `article > figure[data-figure-id]::before { height: 13.1pt; padding-top: 4.32625pt }` (:1065-1072) |
| label text `upper(word) + " " + leading-zero(n)`, 6.8pt/0 Inter 500 VIOLET, tracking .25pt | `figure[data-figure-id]::before { content: attr(data-figure-label) " " counter(magazine-figure, decimal-leading-zero) }` (:1022-1032) |
| `figure-counter` reset per piece, stepped per curated figure | `article { counter-reset: magazine-figure }`, `figure[data-figure-id] { counter-increment }` (:1020-1021) |
| image fit `min(width / px_w, max-height / px_h)`, `FIGURE-MAX-HEIGHT` 205pt | `figure img { max-width: 100%; height: auto }` (:1005), `article > figure[data-figure-id] > img { max-height: 205pt }` (:1075-1078) |
| `COMPACT-FIGURE-MAX-HEIGHT` 170pt, `COMPACT-FIGURE-GAP` 12pt, `COMPACT-BAND-INSET` 32.5pt | `article > figure[data-layout="compact_band"]` (:1112-1115) |
| `OPENER-FIGURE-MAX-HEIGHT` 270pt, opener figure gap 0 | `article > figure[data-anchor="__opener__"]` (:1121-1122) |
| `BAND-ESCAPE` = undo `column`'s pad, giving `LIVE-WIDTH` | `figure[data-layout=evidence_band | evidence_band_prose | adaptive_band] { margin-left: -4.004pt; margin-right: -4.004pt }` (:1107-1109). Expressed as a negative `inset`; `LIVE-WIDTH` is 333.00786 against the CSS's 333.008 |
| band anchor heading: escaped to the band width and `above: 0pt` | `article h2:has(+ figure[band]) ... { margin-left: -4.004pt; margin-right: -4.004pt; margin-top: 0 }` (:1195-1205). The `:has(+ figure)` adjacency is reproduced structurally: every heading, figure and extract registers a `<mag-flow>` mark with a running index, and a heading is an anchor iff the mark at `index + 1` is a band figure |
| `figure-caption` 6.8/8.6 serif, 6.3pt above; `figure-credit` 6.8/8.6 Inter 500 SLATE, nothing between | `figcaption` (:1184-1190) and the `_draw_figure` comment (:1174-1183) |
| `extract` unbreakable, `EXTRACT-GAP` 5mm above and below | `.extract { break-inside: avoid; margin: 5mm 0 }` (:923) |
| `extract-label` 6.8pt Inter 500 VIOLET uppercase, tracking .45pt, 2pt below | `.extract::before` (:924-928) |
| `extract-caption` 6.8pt/1.35 Inter VIOLET, 2pt above | `.extract-caption` (:934-937) |
| `tail-art()` stays out of flow, unchanged | `.article-tail { position: absolute }` (:1361-1367) and :1340-1345: "it never moves a line" |
| closing plates interleaved after articles `round(j * n / count)`, banker's rounding | `_place_closing_plates` (`weasyprint_adapter.py:1767-1785`), `py-round` mirrors Python's `round` |
| closing plate page carries no folio and no running head | `@page closing-plate` (:210) and the comment at :202-207 |
| orphan/widow control: Typst's default `costs` | `p { orphans: 2; widows: 2 }` (:549); `text.costs.widow`/`orphan` default 100% |

### PENDING, with the slice that owns each

| pending | origin | owner |
| --- | --- | --- |
| the figure **image** itself, the 0.55pt stroked frame, `top: 10.0046pt` paint offset, `crisp-edges` | :1075-1100 | **WP-3.4**; the field is reserved at the fitted size, so the image lands without moving the flow |
| closing-plate, tail and opener art images | :262, :1361-1374 | **WP-3.4** |
| `h2.band-anchor-midpage` / `h3.band-anchor-midpage` paint transforms | :1207-1210, `_measured_midpage_anchors` | adapter measurement absent from the content tree, ink only; **WP-3.2** |
| `.band-clearance` (4 reading leadings after a band) | :1130, `render.py:947-950` | **not reachable from the emitted tree**: the adapter inserts it and states its height; the template has no signal for it. 010 paginated identically without it. **Finding for WP-3.1 or the emitter** |
| signature plate count `_signature_closing_plates` | `weasyprint_adapter.py:2242-2252` | the emitter passes every declared plate; the count is derived from content pages in the adapter. Equal on 010 (5). **WP-2.3** (`layout`) |
| `landscape_plate` / `column_plate` page, rotor, plate headings | WP-2.2a's table | 010 declares none; **WP-3.4** |
| `pixels` for WebP / GIF / SVG figures | `media.rs` refuses by name | none of 010's 3 figures; a class-B latency (rule 6b): the refusal is the tripwire |

## Verdicts

**No `verdict.json` was written, and this section records why rather than
citing an older one.** `mag parity 010` exits **1** with
`tracing page 3 of .../reader.pdf: operator cs: unsupported operator cs`.
The comparator's first action after `page_count` passes is to trace both
PDFs; `typst-pdf` sets every fill through `/c0 cs` and `scn`, which
`mag/src/parity/streams.rs:327` does not implement. **This is the first run
in the plan's history to get past `page_count` with a real typst leg**, and
it shows the clause it was gated behind was hiding a comparator gap of its
own. WP-2.2b's own PDF (`0c137d27...`) carries the same 48 `cs` on page 3.

What stands in the verdict's place:

- page count **56 == 56**, measured directly by `pdfinfo` on both legs (step 3)
  and demonstrated by the comparator itself reaching the tracer (WP-2.2b's run
  stopped at `tier S page_count: fail (56 vs 55)`);
- `b_reader_sha256` **`02417ef38b3948fe4ca73d72908dbf9104fae5e62b4795ab88f7ae5d92d40e0a`**
  at `0494017` with the tracking fix, reproduced across two renders
  (`23bbbe10...` before the fix); `staged_input_digest` unchanged from WP-2.2a
  and WP-2.2b, `e48eb5c6...`, since the staged inputs are the same 57 files
  (the comparator printed it before aborting in the pre-loss run);
- oracle leg `8e81e8b4...` for this worktree's render, not reproducible
  across renders (WP-2.2a's finding, unchanged).

### The target

| target clause | outcome |
| --- | --- |
| every 010 figure present on some page | **met**: 3 of 3 print `FIGURE 01` with caption and credit on pages 12, 37 and 42, the oracle's own pages |
| every 010 extract present | **vacuous, labelled**: 010 carries no extract; the block is transcribed and fixture-only until WP-3.3 |
| **Tier S page count on 010** | **met**: 56 against 56, nine article spans and nine start pages equal, five plate pages equal |
| a verdict with every tier evaluated | **BLOCKED on the comparator**: the tracer refuses `cs` before any tier is scored. Rule 4 forbids this WP the fix. Owner: a comparator WP (WP-3.0g is the scheduled one), and it should be scheduled **ahead of WP-3.1**, which is otherwise the first WP to hit it |
| orphan/widow control | **resolved by measurement**: present and operative in both engines by default; sanctioned change not needed |

**Status: `blocked`** on the one clause above, with everything else complete
and landed. Per rule 6 the block is stated with its measurement rather than
worked around; per rule 2a it has an owner.

## What is and is not proven

**Which oracle proves what.** WP-2.1's projection proves text and order, and
step 2 shows this WP left it byte-identical: the `pixels` argument is code
mode and enters no reader text. Structure is proved only by the PDF.

**Proven.**

- *Page count and article pagination equal the oracle's.* Direct `pdfinfo`
  and title-located spans, step 3. Discrimination: the same script read 55
  against 56 on WP-2.2b's leg and reads 56 against 56 here; the ablation with
  heights zeroed returns 55.
- *A figure reserves the height its pixel ratio fits, and refuses without
  one.* `a_figure_reserves_the_image_height_its_pixel_ratio_fits` sweeps a
  synthetic piece over paragraph count and a 5pt phase, and asserts three
  things: some phase makes the figure cost a page against no figure; some
  phase paginates a height-limited (2000x1418) figure differently from a
  width-limited (2400x1350) one; and a figure with no `pixels` fails
  compilation naming the figure. Rule 10c: the refusal is a different outcome
  from any page count, and the two pixel shapes differ from each other.
- *A band anchor heading follows its paragraph on the space-after alone.*
  `a_band_anchor_heading_follows_its_paragraph_on_the_space_after_alone`:
  the same sweep with a square image (so both layouts fit to 205pt and only
  the heading's `above` differs) finds phases where the band spelling takes
  fewer pages. Discrimination: this test **failed** under the `pad` spelling
  at every one of 64 phases, which is how defect 1 was found.
- *Closing plates interleave where the adapter puts them, with Python's
  rounding.* `closing_plates_interleave_after_the_articles_the_adapter_names`
  compiles nine one-page pieces with six plates and asserts the blank pages
  are `[1, 2, 5, 7, 9, 12, 15, 17, 18, 19]`, the banker's-rounding answer, and
  asserts that differs from the half-up answer `[.., 10, ..]`; then five
  plates, the 010 shape. On 010 the five plates land on the oracle's pages.
- *Typst prevents orphans and widows by default.* The synthetic sweep above;
  discrimination is the `0%` template compiled from the same source.
- *PNG and JPEG sizes are read from the header, width and height in the right
  order.* `media.rs` tests use a 40x25 PNG and a 17x29 JPEG, assert both,
  assert they differ from each other and are non-square, and assert WebP and a
  missing file refuse by name.
- *The opener title carries its tracking and breaks where the oracle's
  does.* Step 8 on nine openers and the reverted-fix control;
  `the_opener_title_is_set_with_its_tracking` fails when the constant is
  unapplied.
- *The `FIGURE nn` label, which no text oracle sees, is printed, numbered and
  positioned.* Step 5: text `FIGURE 01`, x exact, label-to-caption within
  0.118pt on all three, against the oracle's PDF.

**Not proven, and who owns proving it.**

- **Every tier past page count.** Blocked on the comparator's tracer; owner
  named in Status.
- **Same-page y of the figure blocks** (+54.4 / +15.4 / +80.4 pt): content
  above them. **WP-3.1** (rows) and **WP-3.4** (images, opener art).
- **`.band-clearance`.** No signal reaches the template; 010 cannot tell.
  **Finding**, owner proposed WP-3.1 or WP-2.1's emitter.
- **The signature plate count.** Equal on 010 by coincidence of the emitter
  passing all five declared plates; the derived count is **WP-2.3**'s.
- **The `pad` spacing mechanism** (defect 1): the effect is measured, the
  cause is a hypothesis.
- **Extracts, compact bands, opener figures, plate pages**: transcribed,
  unexercised by 010, fixture-only until **WP-3.3** / **WP-3.4**.
- **The opener title's residual 0.53 to 0.82 pt** first-line width: measured,
  unexplained, no break affected on 010.
- **The `es` locale**: untouched.

## Residuals

1. The `<mag-flow>` marks make heading/figure/extract adjacency a document
   property, so `:has(+ figure)` is reproduced without stringifying content.
   Introspection converges in one extra pass; determinism held across renders.
2. `figure-image` uses `layout(size => ...)` so the fit reads the real band
   width, including the compact band's 260pt, rather than a stated constant.
3. `closing-plate` is now a declaration: it registers the plate in a state and
   the page is emitted by `piece()` before the article the slot names, or by
   the declaration itself for slots equal to the article count. The emitter's
   call sites are unchanged.
4. The evidence for the orphan/widow table was measured in a worktree later
   deleted from disk; step 6 re-derives the two boundary values (7 and 8) and
   the synthetic WeasyPrint probe so the load-bearing part is replayable.
5. The plan's `### WP-2.2c` text sanctions an oracle change this WP measured
   to be unnecessary and asserts a Typst gap this WP measured to be absent;
   revision 66 already records both.

## Landing

Per the worker brief: two commits in the worktree on base `0494017` (the
cherry-pick of `b31c05e`, then the tracking fix with this file), landed with
`git merge --ff-only` from the main tree onto `art_directed` at tip
`0494017`. `cargo fmt --check`, `cargo clippy --all-targets -D warnings` and
`cargo test` (25 binaries, 265 tests, exit 0) were run at the second commit's
tree; the pre-commit hook re-ran fmt, clippy, ruff and nocomments. Branch
`wp22c-parked` deleted after landing.
