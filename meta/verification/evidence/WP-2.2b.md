# WP-2.2b architecture

## Base

- Measured at `art_directed` **`1ed37df`** (`docs(plans): typst parity plan
  revision 55`) with this WP's diff applied, in a detached worktree at
  `.../tmp/wp22b`. **The branch moved to `f127381` while this WP was in
  flight** (`a911ff1` WP-5.4c cover PDF writer, plus plan revisions 56-58);
  the rebase and the re-verification at the landing commit are recorded under
  `## Landing`. Every number under `## Metrics` is from the measurement
  commit unless it says otherwise.
- Owns, per the WP-2.2 preamble and this WP's brief:
  `mag/assets/typeset/template.typ`, `mag/src/typeset/template.rs`, and this
  evidence file. `mag/src/typeset/world.rs`, `content.rs`, `mod.rs`,
  `render.rs`, `parity.rs`, `meta/verification/parity.yaml` and
  `meta/verification/baseline.json` were read and **not written**. No new
  submodule was needed, so `mag/src/typeset/**` gained no file.
- **No Owns extension is requested.** WP-2.2a's outstanding `render.rs`
  request is unaffected by this slice and is not re-raised here.

## Commands

Run from the root of a checkout at `## Base` with the WP's diff applied, built
once with `cargo build --manifest-path mag/Cargo.toml`. **One input comes from
outside the checkout** and is named by a variable with a default, because the
run directory under `editions/010/` is gitignored: `RUN` is the untracked
content run both legs render. `MAG_PARITY_OUT_DIR` keeps this WP's verdict out
of the shared `output/parity/010`, per WP-0.2k.

```sh
set -o pipefail
unset TYPST_ROOT

RUN=${RUN:-editions/010/run-2026-09-13T01-34-51}
OUT=${OUT:-$PWD/output/parity-wp22b}
test -d "$RUN" || { echo "point RUN at the staged 010 content run"; exit 1; }

# 1. The hermetic suite, and the two totals this file quotes. A total is a
#    measurement with a timestamp: these move as other WPs land, so they are
#    re-derived here rather than cited.
(cd mag && cargo fmt --check && cargo clippy --all-targets -- -D warnings && cargo test)
(cd mag && cargo test 2>&1 | grep -cE '^     Running')
(cd mag && cargo test 2>&1 | grep -E '^test result' | awk -F'[ ;]' '{s+=$4} END {print s}')

# 2. The comparator. It writes BOTH legs, and the two render trees below are
#    derived from what it wrote rather than supplied.
MAG_PARITY_OUT_DIR="$OUT" ./mag/target/debug/mag parity 010 --run "$RUN"
echo "parity exit=$?"
shasum -a 256 "$OUT/verdict.json"
uv run python -c "
import json,sys;v=json.load(open(sys.argv[1]))
print('staged_input_digest', v['staged_input_digest'])
print('inputs', v['inputs'])
print('mode', v['mode'], 'self_comparison', v['self_comparison'])
print('tier_s.page_count', v['tier_s']['page_count'])
" "$OUT/verdict.json"

ORACLE=$(uv run python -c "import json;print(json.load(open('$OUT/oracle-cache.json'))['render_dir'])")
TYPST=$(ls -d editions/010/render-* | tail -1)
echo "oracle leg: $ORACLE"
echo "typst leg:  $TYPST"

# 3. THE TARGET: page boxes over the largest domain the two legs share, at
#    parity.yaml's own tolerance and the comparator's own /Rotate rule. The
#    comparator suppresses this clause while the page counts differ, so it is
#    measured directly, as WP-2.2a measured it.
uv run python - "$ORACLE/en/reader.pdf" "$TYPST/en/reader.pdf" <<'PY'
import re, subprocess, sys
NAMES = ("MediaBox", "CropBox", "TrimBox"); TOL = 0.05
def boxes(pdf, first, last):
    out = subprocess.run(["pdfinfo","-f",str(first),"-l",str(last),"-box",pdf],
                         capture_output=True, text=True).stdout
    b, rot = {}, {}
    for line in out.splitlines():
        m = re.match(r"Page\s+(\d+)\s+(\w+):\s+([\d.-]+)\s+([\d.-]+)\s+([\d.-]+)\s+([\d.-]+)", line)
        if m and m.group(2) in NAMES:
            b[(int(m.group(1)), m.group(2))] = tuple(float(x) for x in m.groups()[2:])
        r = re.match(r"Page\s+(\d+)\s+rot:\s+(-?\d+)", line)
        if r: rot[int(r.group(1))] = int(r.group(2))
    return b, rot
def count(pdf):
    return int(re.search(r"Pages:\s+(\d+)",
        subprocess.run(["pdfinfo", pdf], capture_output=True, text=True).stdout).group(1))
a_pdf, b_pdf = sys.argv[1], sys.argv[2]
na, nb = count(a_pdf), count(b_pdf)
last = min(na, nb) - 1
ab, ar = boxes(a_pdf, 2, last); bb, br = boxes(b_pdf, 2, last)
shared = sorted(set(ab) & set(bb))
bad = [k for k in shared if max(abs(x-y) for x,y in zip(ab[k],bb[k])) > TOL]
rbad = [p for p in set(ar) & set(br) if ar[p] != br[p]]
print(f"pages: a={na} b={nb}, compared 2..{last}")
print(f"boxes compared: a={len(ab)} b={len(bb)}; mismatches beyond {TOL}pt: {len(bad)}")
print(f"rotations compared: a={len(ar)} b={len(br)}; mismatches (exact): {len(rbad)}")
print(f"worst single-coordinate delta: "
      f"{max(max(abs(x-y) for x,y in zip(ab[k],bb[k])) for k in shared):.6f} pt")
PY

# 4. Per-article page spans on both legs. Article starts are located by the
#    article's own title text, so neither leg's pagination is assumed. The
#    oracle interleaves its five closing plates and the typst leg does not
#    (WP-2.2c), so the oracle's plate pages are subtracted by page number and
#    the typst leg's plates trail the last article.
uv run python - "$ORACLE/en/reader.pdf" "$TYPST/en/reader.pdf" "$TYPST/typst/pieces" <<'PY'
import subprocess, re, pathlib, sys
titles = [re.sub(r"\\(.)", r"\1", re.search(r"#piece-title\[(.*?)\]\n", p.read_text(), re.S).group(1))
          for p in sorted(pathlib.Path(sys.argv[3]).glob("*.typ"))]
def starts(pdf):
    n = int(re.search(r"Pages:\s+(\d+)",
        subprocess.run(["pdfinfo",pdf],capture_output=True,text=True).stdout).group(1))
    txt = [re.sub(r"\s+"," ",t) for t in
           subprocess.run(["pdftotext",pdf,"-"],capture_output=True,text=True).stdout.split("\f")]
    return n, [next(p for p,t in enumerate(txt[:n],1) if p>3 and re.sub(r"\s+"," ",title) in t)
               for title in titles]
def spans(n, s, plates):
    out = []
    for i in range(len(s)):
        nxt = [s[i+1]] if i+1 < len(s) else []
        out.append(min([p for p in plates if p > s[i]] + nxt + [n+1]) - 1 - s[i] + 1)
    return out
na, sa = starts(sys.argv[1]); nb, sb = starts(sys.argv[2])
plates_a = [p for p in range(1, na+1) if len(subprocess.run(
    ["pdftotext","-f",str(p),"-l",str(p),sys.argv[1],"-"],
    capture_output=True,text=True).stdout.strip()) < 30 and p > 3]
pa = spans(na, sa, plates_a); pb = spans(nb, sb, [])
print("oracle blank/plate pages past the contents:", plates_a)
print(f"{'article':46s} {'o-start':>7s} {'t-start':>7s} {'o-span':>6s} {'t-span':>6s}")
for i, t in enumerate(titles):
    print(f"{t[:46]:46s} {sa[i]:7d} {sb[i]:7d} {pa[i]:6d} {pb[i]:6d}")
print(f"{'TOTAL article pages':46s} {'':7s} {'':7s} {sum(pa):6d} {sum(pb):6d}")
print(f"pages: oracle {na}, typst {nb}")
PY

# 5. Running head, contents grid and opener stack, all by BAND rather than by
#    index: the running head is the only ink above the content box's top edge
#    (42.0004), the folio the only ink below its foot, and everything between
#    is flow. Selecting by index compares a running head against a body line,
#    which is the defect WP-2.2a's replay caught in its own step 6.
uv run python - "$ORACLE/en/reader.pdf" "$TYPST/en/reader.pdf" "$TYPST/typst/pieces" <<'PY'
import re, subprocess, sys, pathlib
TOP, FOOT = 42.0004, 540.276
def words(pdf, page):
    out = subprocess.run(["pdftotext","-f",str(page),"-l",str(page),"-bbox-layout",pdf,"-"],
                         capture_output=True, text=True).stdout
    return [(float(m.group(1)), float(m.group(2)), float(m.group(3)), m.group(5))
            for m in re.finditer(
                r'<word xMin="([\d.]+)" yMin="([\d.-]+)" xMax="([\d.]+)" yMax="([\d.-]+)">([^<]*)<', out)]
def count(pdf):
    return int(re.search(r"Pages:\s+(\d+)",
        subprocess.run(["pdfinfo",pdf],capture_output=True,text=True).stdout).group(1))
def lines(rows):
    out, seen = [], None
    for r in sorted(rows, key=lambda r: (r[1], r[0])):
        if seen is None or abs(r[1]-seen) > 0.4:
            seen = r[1]; out.append(r)
    return out
print("=== running head census (ink above the content top, every page) ===")
for pdf, name in ((sys.argv[1], "weasyprint"), (sys.argv[2], "typst")):
    rows = []
    for p in range(1, count(pdf)+1):
        band = [r for r in words(pdf, p) if r[1] < TOP]
        if band:
            rows.append((p, round(min(r[0] for r in band), 5),
                         round(max(r[2] for r in band), 5), round(band[0][1], 5)))
    census = {}
    for r in rows: census[r[1]] = census.get(r[1], 0) + 1
    print(f"{name:11s} pages with ink above the content top: {len(rows)}")
    print(f"{name:11s} xMin census: {census}")
    print(f"{name:11s} baselines:   {sorted({r[3] for r in rows})}")
print("=== contents page 3, every distinct row ===")
for pdf, name in ((sys.argv[1], "weasyprint"), (sys.argv[2], "typst")):
    print(f"--- {name}")
    for r in lines(words(pdf, 3)):
        print(f"    y={r[1]:9.5f} x={r[0]:9.5f} {r[3]}")
print("=== opener stacks, article by article ===")
titles = [re.sub(r"\\(.)", r"\1", re.search(r"#piece-title\[(.*?)\]\n", p.read_text(), re.S).group(1))
          for p in sorted(pathlib.Path(sys.argv[3]).glob("*.typ"))]
def starts(pdf):
    n = count(pdf)
    txt = [re.sub(r"\s+"," ",t) for t in
           subprocess.run(["pdftotext",pdf,"-"],capture_output=True,text=True).stdout.split("\f")]
    return [next(p for p,t in enumerate(txt[:n],1) if p>3 and re.sub(r"\s+"," ",title) in t)
            for title in titles]
sa, sb = starts(sys.argv[1]), starts(sys.argv[2])
for i, t in enumerate(titles):
    for pdf, name, s in ((sys.argv[1], "weasyprint", sa), (sys.argv[2], "typst", sb)):
        r = lines([w for w in words(pdf, s[i]) if TOP < w[1] < FOOT])
        head = [w for w in words(pdf, s[i]) if w[1] < TOP]
        print(f"{(t[:22] if name=='weasyprint' else ''):24s} {name:11s} "
              f"label y={r[0][1]:9.4f} x={r[0][0]:9.4f} | title y={r[1][1]:9.4f} | "
              f"rows={len(r)} | running-head words={len(head)}")
PY

# 6. Determinism of the typst leg, and the folio past page 9, which is where
#    the defect this WP fixes only becomes visible.
./mag/target/debug/mag render 010 --engine typst --no-model --langs en --run "$RUN" > /dev/null
AGAIN=$(ls -d editions/010/render-* | tail -1)
shasum -a 256 "$TYPST/en/reader.pdf" "$AGAIN/en/reader.pdf"
uv run python - "$ORACLE/en/reader.pdf" "$TYPST/en/reader.pdf" <<'PY'
import re, subprocess, sys
def folio(pdf, page):
    out = subprocess.run(["pdftotext","-f",str(page),"-l",str(page),"-bbox-layout",pdf,"-"],
                         capture_output=True, text=True).stdout
    return [(m.group(5), round(float(m.group(3)), 5)) for m in re.finditer(
        r'<word xMin="([\d.]+)" yMin="([\d.-]+)" xMax="([\d.]+)" yMax="([\d.-]+)">([^<]*)<', out)
        if float(m.group(2)) > 545]
for page in (4, 9, 12, 23, 44):
    print(f"p{page}: weasyprint {folio(sys.argv[1], page)}  typst {folio(sys.argv[2], page)}")
PY
```

## Tool versions

- rustc 1.96.0; `typst`/`typst-layout`/`typst-library`/`typst-pdf`/`typst-syntax`
  all pinned `=0.15.1`, `lopdf` 0.45.0. **This WP adds no crate and does not
  touch `Cargo.toml` or `Cargo.lock`.**
- poppler 25.09.1, as pinned in `meta/verification/parity.yaml`.
- CPython 3.12.11 through `uv run python`. No bare `python3`.
- The typst CLI is not installed and is not used; compilation goes through the
  pinned crates inside `mag`. `TYPST_ROOT` is unset in the block above and is
  irrelevant to this leg.

## Metrics

Every number below is produced by the command block, measured at `1ed37df`
with this WP's diff applied.

| quantity | value |
| --- | --- |
| typst leg pages | **55** (WP-2.2a: 52) |
| weasyprint leg pages | 56 |
| **page boxes compared over the shared domain (pages 2..54)** | **159** (53 pages x 3 box names), both legs |
| **box mismatches beyond `tiers.s.box_tolerance_pt` = 0.05 pt** | **0** |
| **worst single-coordinate box delta** | **0.000000 pt** |
| rotations compared / mismatches | 53 / **0** |
| article pages, weasyprint / typst | 46 / **45** (WP-2.2a: 42) |
| articles whose page span matches the oracle exactly | **8 of 9** |
| running-head pages, weasyprint / typst | 37 / 36 |
| running-head name xMin, recto (19 pages each leg) | oracle 43.99998, typst **44.00000** |
| running-head name xMin, verso (18 pages each leg) | oracle 42.51968, typst **42.51970** |
| running-head baseline, every page | oracle 13.41099, typst **13.41250** (delta 0.00151 pt) |
| running-head pages that are also opener pages | **0** on both legs |
| contents kicker baseline | oracle 24.41599, typst **24.41753** |
| contents display title baseline | oracle 56.03300, typst **56.03290** |
| contents rows, worst row-baseline delta over all 36 rows | 9 rows x 4; **0.00558 pt** on the nine 23pt entry folios, **0.00156 pt** on every other row |
| contents entry-folio x / entry cluster x | **44.00000 / 91.00000**, exact on both legs |
| opener content-label baseline, worst delta over 9 openers | **0.00142 pt** |
| opener display-title baseline, worst delta over 9 openers | **0.00019 pt** |
| openers where the template's density choice matches the adapter's | **9 of 9** (7 compact, 2 standard) |
| openers where the template's fitted title size matches the adapter's | **9 of 9** |
| opener-page text rows, weasyprint / typst | equal on 5 of 9; off by one on 4 (see `_split_standfirst_overflow`) |
| opener standfirst block offset, the seven compact openers | typst **+2.2656 pt**, constant; unexplained, see Residuals |
| folio on pages 10 and beyond | **fixed here**; see Defects |
| typst PDF sha256, three renders of one staged input set | identical, `0c137d27...` |
| `cargo test` binaries / tests, all passing | **22** / **209** at `1ed37df` |

### Per-article page spans

Article starts are located by each article's own title text on each leg
independently, so neither leg's pagination is assumed.

| article | weasyprint | typst | delta | figure on that article |
| --- | --- | --- | --- | --- |
| government-rails-site-hit-hours-after-cve-patch | 3 | **3** | 0 | none |
| countering-misuse-of-ai-september-2026-anthropic | 3 | **3** | 0 | none |
| an-alignment-assessment-of-recent-cybersecurity | 6 | **5** | **-1** | `four-incidents` |
| dario-amodei-we-must-pace-the-frontier | 13 | **13** | 0 | none |
| scenarios-for-our-economic-future | 4 | **4** | 0 | none |
| the-third-era-of-ai-software-development | 4 | **4** | 0 | `agent-usage-growth` |
| towards-self-driving-codebases | 5 | **5** | 0 | `recursive-planners` |
| deepseek-v4-1-flash-pushing-the-limits-of-kv-cac | 4 | **4** | 0 | none |
| rapidly-scaling-online-storage-to-serve-over-1-b | 4 | **4** | 0 | none |
| **total** | **46** | **45** | **-1** | |

**This is a measurement, offered as neither confirmation nor refutation of the
figure account of the missing pages.** What it establishes, and what it does
not:

- The gap is **-1, not -4**, and it is on **one** article. WP-2.2a's -4 was
  `+1, 0, -1, -1, 0, -1, -1, 0, -1`; the three figureless articles that had
  moved (`dario`, `government-rails`, `storage`) now match exactly, as does
  `countering-misuse`.
- **Two of the three figure-carrying articles now match the oracle exactly
  while their figures are still unplaced.** `the-third-era` is 4 against 4
  and `towards-self-driving` is 5 against 5. Under the figure account those
  two should still be short by one page each. They are not. Placing their
  figures would have to be page-neutral for the account to survive, which is
  possible but is now a thing WP-2.2c has to show rather than assume.
- The one remaining -1 **is** on a figure-carrying article
  (`an-alignment-assessment`). That is consistent with the figure account for
  that article and with nothing else measured here.
- **The fourth page WP-2.2a could not explain is accounted for by this
  slice**, not by figures: the opener page, the heading clearance and the
  quote-rule fix together closed three of WP-2.2a's four, and the residual
  count fell from four to one. Which of the three closed which page is not
  separable from this measurement (see the ablation below), so no per-cause
  attribution is claimed.
- **Orphan and widow control is still absent from the typst leg** and is
  WP-2.2c's. Nothing here bounds its contribution; a systematic pagination
  difference that now nets to zero on eight articles is not evidence that it
  nets to zero per page.

### The heading clearance is operative and page-count-neutral on 010

Two renders of edition 010 from the same staged inputs, one with
`HEADING-CLEARANCE = 25pt` and one with `0pt`:

| | pages | article start pages |
| --- | --- | --- |
| 25 pt (transcribed) | 55 | 4, 7, 10, 15, 28, 32, 36, 41, 45 |
| 0 pt (ablated) | 55 | 4, 7, 10, 15, 28, 32, 36, 41, 45 |

**Identical pagination, different bytes** (206,909 against 206,800 before the
folio fix). So on this corpus the 25 pt reservation moves ink and no page
boundary: 010's 41 prose headings (38 at level 2, 3 at level 3) never land
inside it.
That makes 010 **unable to falsify the reservation**, which is why the
committed test does not use it. `the_heading_clearance_reserves_twenty_five_points_below_a_heading`
builds a synthetic piece of *n* one-line paragraphs ending in an h2, sweeps
*n* over 24..40, and asserts that **at least one n** compiles to more pages
under the transcribed template than under a template with the constant
replaced by `0pt`. **The boundary the sweep established**: with 13 pt lines
and 5.4 pt paragraph spacing the frame admits about 27 such paragraphs, the
unbreakable heading block is 21.5 + 13 + 25 = 59.5 pt against 34.5 pt
unreserved, and the sweep covers the whole range in which those two differ.
The assertion names the failure: *no paragraph count put a heading inside the
25pt reservation*, which is what a template that had lost the reservation
would print.

### Which mechanism the 25 pt clearance uses, and why

WP-2.2a's residual 5 left three candidates and said the choice wanted a
measurement. The one shipped is **candidate 1**, the unbreakable block plus an
explicit pull-back, because Typst's spacing rules make it exact rather than
approximate:

```
block(above: spec.above, below: 0pt, breakable: false, {
  <heading text>
  v(spec.below)
  block(height: HEADING-CLEARANCE, width: 100%, spacing: 0pt, [])
})
v(-HEADING-CLEARANCE)
```

- The heading's own `margin-bottom` moves **inside** the unbreakable block as
  an explicit `v`, so the block reserves `heading + 13 + 25`, which is exactly
  what the reader tests. **Re-derived at the point of citation**: the CSS
  comment at :510-521 names `render.py:1133-1137`, and the live site is
  **`render.py:1081-1085`**, `if self.y - needed - 25 < self.frame_bottom:
  self._advance_frame()`. The comment's line numbers have drifted; its
  mechanism has not.
- The outer block's `below` is `0pt` and the trailing `v` is **strong**, so
  Typst removes the following paragraph's weak `above` spacing rather than
  taking `max()` of it. Net advance after the heading's ink is
  `13 + 25 - 25 = 13 pt`, the CSS's own collapsed value.
- WP-2.2a's objection to candidate 1 — that an explicit `v` is not discarded
  at a page break where CSS discards a margin — **does not arise**, because
  the `v` is outside the unbreakable block and therefore always lands on
  whichever page the block landed on. Candidate 2 (`block(sticky: true)`) was
  rejected on the CSS comment's own grounds at `:510-521`: it reserves the
  next block's first fragment, not a flat 25 pt. Candidate 3
  (`context` + `measure()`) was rejected because measuring the next block
  defeats the reservation.

## Defects found

Both are in `mag/assets/typeset/template.typ`, which this slice owns. **Class
A in the taxonomy's terms: port-fidelity gaps, fixed by matching the CSS.**

### 1. The folio printed `012` from page 10 on

`numbering("01", index)` reads `0` as a literal prefix and `1` as the counting
symbol, so it renders `04` for page 4 and **`012`** for page 12, `023` for
page 23. The CSS is `content: counter(page, decimal-leading-zero)`
(`weasyprint-a5.css:153`), which pads to two digits and leaves longer numbers
alone.

**WP-2.2a's evidence could not see it**: it measured the folio on pages 4 and
5 only, the two single-digit pages where the two spellings agree. 43 of
edition 010's 46 folio pages carried the wrong number.

Fixed by `leading-zero(index)`, authored from the CSS keyword rather than from
the oracle's output. Measured after the fix on pages 12, 23 and 44: `12`,
`23`, `44` on both legs, number right edge 377.00786 against the oracle's
377.00625 / 377.0064.

### 2. `doc-quote`'s rule made a short quote swallow its page

WP-2.2a built the blockquote as `grid(columns: (QUOTE-RULE, QUOTE-PAD, 1fr),
rect(width: QUOTE-RULE, height: 100%, ...), [], body)`. In Typst a `100%`
height inside an `auto` grid row resolves against the **page**, not the row,
so a two-line quote expands to the full remaining page height. WP-2.2a
recorded the construction as untested under fragmentation; it is worse than
that — it is wrong wherever the quote is not already at the page foot, and
this WP's pagination change exposed it: edition 010's single blockquote
landed near a page top and took **a whole page with two lines on it**.

Replaced by the CSS's own spelling, a left border and a left padding:
`blockquote { border-left: 1.5pt solid VIOLET; padding-left: 4mm }`
(`:918`), as a `block` with a left `stroke` inside a `pad(left: QUOTE-RULE/2)`
so that the centred Typst stroke occupies `[0, 1.5]` exactly as the CSS border
does. Content then starts at `1.5 + 4mm = 12.838583 pt` and the content width
is `325.025 - 12.838583 = 312.186417 pt`, which is **WP-2.2a's own measured
blockquote width, unchanged**. `doc-code` carried the same construction
(`pre`, `:940`) and is fixed the same way; edition 010 has no fenced code, so
that half is fixture-only until WP-3.3.

Committed test: `a_short_quote_does_not_swallow_the_rest_of_its_page`. **It
states what would make it fail and commits a case that does** — it substitutes
WP-2.2a's exact grid text back into the template and asserts that version
takes *more* pages than the ruled one.

## Mapping table

Extending WP-2.2a's. **Every transcribed value cites its `weasyprint-a5.css`
selector or `weasyprint_adapter.py` constant; anything found and not
transcribed is PENDING with the slice that owns it.**

### Transcribed by this slice

| template.typ | value | origin |
| --- | --- | --- |
| `HEADING-CLEARANCE` 25pt, unbreakable with the heading, pulled back out of flow | `.heading-clearance { break-before: avoid; break-inside: avoid; height: 25pt; margin-bottom: -25pt }` (:522) and the derivation comment at :510-521, whose `render.py:1133-1137` citation has drifted to `render.py:1081-1085` |
| `leading-zero` two-digit folio | `counter(page, decimal-leading-zero)` (:153) |
| running head drawn on every page of a piece except the piece's own first | `@top-center { content: element(runhead, first-except) }` (:170-175) and the comment at :161-169 |
| running head width `LIVE-WIDTH`, anchored to the MIRRORED content box | `@top-center { width: 333.0079pt }` (:174); `.running-head-row { display: flex; justify-content: space-between }` (:291-299). Implemented as two `place` calls at the page's own inner and outer margins, which is what the mirrored box computes to; measured equal on both parities. |
| `RUNNING-BASELINE` 20pt | `.running-head-row { padding-top: 17.52625pt }` at `line-height: 0` (:293-298) and the comment at :283-288: "17.52625pt of padding lands it on 20" |
| running head face 6.8pt Inter Medium INK uppercase | `.running-head-row` (:293-298); identical to the folio's, so `folio-text` is reused |
| `RUNNING-RULE` 0.55pt COOL-GRAY at `RUNNING-RULE-TOP` 27.725pt | `.running-head-rule { background: rgb(88% 89% 90%); height: .55pt; margin-top: 10.19875pt }` (:302) and :300-301: "17.52625 + 10.19875 = 27.725, which is the 0.55pt rule centred on 28" |
| `RUNNING-TICK` 1.15pt x `RUNNING-TICK-WIDTH` 14pt SIGNAL-ORANGE at 27.425pt | `.running-head-rule i { height: 1.15pt; top: -.3pt; width: 14pt }` (:303-306) |
| `ZERO-LEADING-SANS` 2.47375pt | :286, "the baseline of a zero-leading line sits `size * (ascent - descent) / 2` = 2.47375pt below the content box"; `_ZERO_LEADING_SANS_BASELINE` (`weasyprint_adapter.py:157`) |
| contents occupies the full live width, not the 325pt rail | `[data-edition-navigation="contents"] { max-width: none }` (:322) overriding :265 |
| `CONTENTS-KICKER-TOP` -13.46915pt, 6.8pt/0 sans, tracking .45pt, uppercase | `.contents-kicker` (:324-327) |
| `CONTENTS-TITLE-TOP` 32.54098pt, `CONTENTS-TITLE-SIZE` 27pt/0 Serif Display 600 | `[data-edition-navigation="contents"] h2` (:329-332) |
| `CONTENTS-BAND-TOP` 74.2802pt, `CONTENTS-BAND` 393pt | `ol { height: 467.2802pt; padding: 74.2802pt 0 0 }` (:334-337); 467.2802 - 74.2802 = 393 |
| row height `min(393 / max(6, n), 65.5)` | `li { flex: 1 1 0; max-height: 65.5pt }` (:338-340) and :315-320, "the entries divide a fixed 393pt band into `max(6, len(chunk))` equal rows" |
| `CONTENTS-RULE` 0.7pt COOL-GRAY centred on the row's own bottom edge, every row but the last, full live width | `li:not(:last-child)::after { bottom: -.35pt; height: .7pt; width: 333.0079pt }` (:342-345) and :341 |
| `CONTENTS-ENTRY-LEFT` 47pt | `.entry-label`, `.entry-title`, `.entry-author { left: 47pt }` (:354-374) |
| entry offsets standard 8.6 / 17.7 / 17.5 / 32.2pt | `.entry-label`, `.entry-folio`, `.entry-title`, `.entry-author` `top` (:354-374) |
| entry offsets tight 6.8 / 15.9 / 15.8 / 30.5pt | `[data-contents-density="tight"]` (:385-388) |
| entry folio: violet 23pt/0 Inter 600 at left 0, **zero-padded target page** | `.entry-folio` (:356-359) and `.entry-folio::after { content: target-counter(attr(href), page, decimal-leading-zero) }` (:360-362). **Generated content: it is printed and is NOT in WP-2.1's content oracle**, so the template is its only check. Implemented with a per-piece `<mag-piece>` metadata mark and `counter(page).at(mark.location())`. |
| entry title 9.8pt/10.2pt Serif Display 600, width 286.0079pt, one line | `.entry-title` (:364-366) and the contract comment at :367-372 |
| entry author 6.8pt/0 Inter Medium SLATE uppercase | `.entry-author` (:380-384) |
| entry label 6.8pt/0 Inter Medium uppercase, **no tracking** | `.entry-label` (:354-356). **Corrected from WP-2.2a**, which set `tracked(0.45pt)` on it; the contents entry-label rule sets no `letter-spacing`, and `grep -n "letter-spacing"` over the stylesheet returns 12 sites, none of them `.entry-label`. The `.contents-kicker` at :325 does set `.45pt` and keeps it. |
| illustrated opener header is **its own page** | `article[data-article-opener="illustrated_paper_spots_v1"] > header.article-opener { break-after: page; break-inside: avoid }` (:1436-1442). **The single largest structural item in this slice**: WP-2.2a flowed the opener chrome into the body. |
| opener rail 348pt, escaping the 325pt measure by 11.5pt a side | same rule, `margin-left: -11.5pt; margin-right: -11.5pt; width: 348pt` (:1439-1441) and the comment at :1417-1419 |
| `OPENER-ART-HEIGHT` 207.1pt, `OPENER-ART-LIFT` 12.0004pt, width 352.1pt | `.article-opener-art { height: 207.1pt; margin: -12.0004pt 0 0; width: 352.1pt }` (:1445-1452) |
| `OPENER-ART-FLOW` 195.1pt, the field's flow contribution | `_ILLUSTRATED_OPENER_STANDARD["art"]` / `_COMPACT["art"]` (`weasyprint_adapter.py:203, 213`). The adapter rounds 207.1 - 12.0004 to 195.1; the template uses the adapter's own figure for the density decision so the decision reproduces. |
| orange offset 348 x 203pt at +4.1, +4.1 | `.article-opener-art-offset` (:1454-1461) |
| black frame 348 x 203pt, 2.4pt border, box-sizing border-box | `.article-opener-art img { border: 2.4pt solid rgb(23 25 28); height: 203pt; width: 348pt }` (:1464-1478). Drawn inset by `OPENER-BORDER / 2` so Typst's centred stroke occupies the same 2.4pt the CSS border does. |
| opener label: block, 6.5pt/7.15pt Inter 600, `PAPER-BLUE`, tracking .16em, uppercase | `article[...] > header > .content-label` (:1483-1492) |
| opener label spans carry no violet, no grey and **no `translateX`** | `article[...] .content-label span { color: inherit; transform: none }` (:1489-1492), specificity (0,2,1) over `.label-date`'s (0,1,0) and `.content-label .label-secondary`'s (0,2,0) |
| opener title: `PAPER-INK`, tracking -.045em, margin-top 8pt (compact 6pt) | `article[...] > header > h1` (:1494-1498), `[data-opener-density="compact"] > h1` (:1590-1593) |
| opener title fitted size and leading `0.96 * size` | `_set_illustrated_opener_title` (`weasyprint_adapter.py:1034-1038`), `_OPENER_TITLE_LEADING_RATIO` (:150). Derived, not transcribed: see Residuals. |
| `OPENER-TITLE-BOX` 64pt / min 22pt, max 32.5pt (compact 30pt), 2 lines, 0.5pt steps | `_ILLUSTRATED_OPENER_TITLE_BOX`, `_ILLUSTRATED_OPENER_TITLE_MAX`, `_ILLUSTRATED_OPENER_COMPACT_TITLE_MAX`, `_ILLUSTRATED_OPENER_TITLE_MAX_LINES` (:194-199), and the step in `_fitted_display` |
| `OPENER-TICK` 14.5 x 2.4pt SIGNAL-ORANGE, margin-top 25pt (compact 18pt) | `.opener-tick` (:1508-1513), `[data-opener-density="compact"] .opener-tick` (:1595-1598) |
| opener meta grid `1fr 41pt`, gap 14pt, `align-items: center`, padding 9pt (compact 7pt), 1pt `PAPER-RULE` bottom border | `.opener-meta` (:1500-1507), `[data-opener-density="compact"] .opener-meta` (:1600-1603), `.source-link` / `img.source-code` 41pt (:1547-1569) |
| `OPENER-META-MEASURE` 293pt | `_ILLUSTRATED_OPENER_META_MEASURE_POINTS` (:200); independently `348 - 41 - 14`, asserted both ways in `the_architecture_constants_are_the_stylesheet_s_own` |
| opener byline 7.4pt/8.5pt Inter 700 `PAPER-INK`, tracking .04em, uppercase | `article[...] .byline` (:1522-1530) over `.byline { text-transform: uppercase }` (:790) |
| opener byline prefix 6.2pt `PAPER-BLUE`, tracking .15em, margin-right .35em | `.byline-prefix` (:1531-1536) |
| opener author note 6.8pt/9.4pt `PAPER-GRAY`, margin-top 3.2pt | `article[...] .author-note` (:1537-1543) |
| opener standfirst 10.2pt/14.4pt, 23.5pt + 9pt above (compact 9.6/13.2, 16 + 6) | `article[...] > header > .standfirst` (:1571-1577), `[data-opener-density="compact"] > .standfirst` (:1605-1610) |
| `OPENER-PANGO-RESERVE` 13.2pt and the compact switch | `_ILLUSTRATED_OPENER_PANGO_RESERVE_POINTS` (:224) and `_pin_opener_fields` (:1244-1274) |
| `ARTICLE-PAGE-CAP` 7 hard, `VERBATIM-PAGE-CAP` 10 advisory | `_MAX_ARTICLE_PAGES` / `_MAX_VERBATIM_PAGES` (`weasyprint_adapter.py:32-33`) and `render.py:2082-2096`, where a verbatim overrun **warns** and every other mode **raises**. The template asserts the hard branch and is silent on the advisory one: Typst 0.15.1 has no warning channel. |

### PENDING, with the slice that owns each

| pending | origin | owner |
| --- | --- | --- |
| **`orphans: 2; widows: 2`** | `p { orphans: 2; widows: 2 }` (:549) and the deliberate-choice comment at :527 | **WP-2.2c**, as of plan revision 56. Still absent from the typst leg. This slice measured around it, not through it: the eight matching spans do not bound its per-page contribution. |
| **`_split_standfirst_overflow`** — when even compact density will not fit, the adapter **moves the tail of the standfirst out of the header** and it renders as an ordinary body paragraph at 10pt/13pt on the next page | `_pin_opener_fields` (`weasyprint_adapter.py:1268-1271`) | **WP-2.1's emitter**. Measured, not inferred: the oracle's page 5 opens with two lines at the 13pt body leading and the 48.0039 body rail, which is article 1's standfirst tail. The template keeps the whole standfirst on the opener page, so the opener page carries a different number of text rows on **four of nine** openers: typst has one more on articles 1 and 7, one fewer on 2 and 6, and the same count on the other five. The template cannot do this: the cut point is a Pango wrap count. **This is a second concrete instance of WP-2.1's oracle blindness** — the split changes which element the text belongs to and not the text or its order, so byte-identical content passes either way. |
| **opener art image, and the 41pt source-code QR** | `.article-opener-art img` (:1464-1478), `img.source-code` (:1559-1569) | **WP-3.4** (images). The template reserves both **fields** at full geometry and paints the frame and the orange offset; neither image is in the emitted tree, and the QR is adapter-generated (`_apply_source_codes`) rather than semantic HTML. |
| **`.standfirst::first-letter` drop cap** — `PAPER-BLUE`, Serif Display 18.7pt 600, `line-height: .7`, `margin-right: 1pt` | :1612-1618 | **WP-2.1's emitter**, or whoever ships a first-letter span. Splitting one grapheme out of arbitrary content is not something the template can do to `body`; the constants are carried as `OPENER-DROP-SIZE` / `OPENER-DROP-GAP` and applied nowhere. It changes no line box (18.7 x 0.7 = 13.09 pt against the 14.4 pt line), so it is ink only. |
| **`data-opener-density` and the inline fitted title size** are adapter measurements absent from the content tree | `_pin_opener_fields` sets both on the header (`weasyprint_adapter.py:1274-1276`, `1034-1038`) | **WP-2.1's emitter**. The template reproduces both by measuring in Typst and they agree 9 of 9 on 010 (see Residuals), but that agreement is a corpus observation and not a contract. Carrying them across would make it one. |
| **`.content-label .label-secondary { transform: translateX(.45pt) }`** | :779 and the derivation at :746-778 | **still PENDING, and narrower than WP-2.2a recorded.** The correction only means anything under the plain opener's `display: flex; justify-content: space-between` (:740-744), which flushes the tracked box's trailing letter-space to the content edge. The template renders the plain `.content-label` as a left-aligned inline run with no flush, so applying the transform would **displace** the label rather than correct it — which is precisely why the CSS scopes it to `.label-secondary` and not `:last-child`. **Edition 010 exercises neither**: all nine openers are illustrated, and `article[...] .content-label span { transform: none }` (:1489-1492) cancels it there. Owner: whoever implements the plain opener's flex label. |
| **`.standfirst + h1 / h2 / h3` = 31 / 28 / 23pt** | :722-724 and the collapse argument at :715-721 | **WP-3.1** (body text). Transcribed here and applied nowhere: on an illustrated opener the standfirst is inside `<header>` and the heading is a sibling of the header, so the adjacency never matches, and all nine of 010's articles are illustrated. Reaching it needs a plain opener. |
| **the reference-list measure, 312.0256 pt** (`325 - 12.9744`) | `ul[data-reference-list] li` `padding-left` / `text-indent` (:843-848) | **WP-3.3**'s fixture edition. **An unbounded branch**: it is derived, not measured, and no spike has bounded its widening interval the way WP-1.7 bounded the other three. 010 emits `references: false` on all 8 lists, but the branch is **content-reachable, not config-gated** — `_is_reference_heading` (`html_edition.py:792`) is a casefolded heading-text test, so it is one manuscript away. Do not treat 312.0256 as settled. |
| heading levels 1 and 4+ | `.editorial > h1, article > h1` (:489-494) and `calc.min(level, 3)` | **WP-3.1**. Unexercised: 010's manuscripts carry no `#` or `####` heading. |
| the editorial opener's `min-height: 153.2756pt` clamp, `_fitted_title_box`'s stepped display size for plain openers, the section opener's field | :443-465, :477-480 | **WP-3.2** / whoever ships the plain opener. Editions from 010 on carry no editorial and 010 declares no plain opener, so none of it is reachable from the live corpus. |
| landscape plate page, rotor, plate headings; figures, extracts, tail ornaments, band escapes, closing-plate art, **plate interleaving** | as WP-2.2a's table records them | **WP-2.2c**, unchanged by this slice |
| syntax-highlight colour classes for `pre code` | :959-966 | **WP-3.3** |

## Verdicts

`mag parity 010` was run from the worktree root with
`MAG_PARITY_OUT_DIR=.../output/parity-wp22b`, so this WP's verdict cannot
replace another's in the shared `output/parity/010` (WP-0.2k).

- **verdict.json sha256: `6d73960d1e4d008d9fb51e13e6903ae6019d06c099fd2dbc77677355777683e5`**
- `staged_input_digest`: `e48eb5c638a0f25bfdfbb5e26bc989d56c1ecbac3ef85f103e90ed1ac8aac5fa`
  — **identical to WP-2.2a's**, so the two slices compared the same staged
  input set and the page-count movement is the template's and not the corpus's.
- `inputs.a_reader_sha256` (weasyprint leg): `e010c14c8730b15a0e33cf688a5dd477ed7919ead45fd28652ae702f467ab4e0`
- `inputs.b_reader_sha256` (typst leg): `0c137d27b4aa675b0e27ac43d62339603a6c718feb0977f2e1a02bf26428e78e`
- measured at commit **`1ed37df`** with this WP's diff applied.

**`a_reader_sha256` cannot be matched by a replay** and this run reproduces
WP-2.2a's finding rather than citing it: WP-2.2a measured three different
oracle hashes from three renders of identical staged inputs in one worktree.
A verifier should compare **`b_reader_sha256`, `staged_input_digest` and the
tier summary**. `b_reader_sha256` reproduced byte-for-byte across **three**
renders here, including one taken before and one after a template edit that
turned out to change nothing (see Residuals 1).

Tier summary, quoted from the file:

```
mode: render
self_comparison: false
page sets: body 34, code 0, furniture 54, openers 9, placement 11
ratchet: not_measured (54 committed entries checked, 54 recorded, 0 measured, 0 regressions)
tier_s.page_count: fail (a 56, b 55)
tier_s.boxes: null      tier_s.text: null       tier_s.color: null
tier_s.navigation: null tier_g: null            tier_v: null
tier_e.display_list: null  tier_e.glyph_positions: null  tier_e.raster: null
tier_s.code_blocks: not_evaluated (WP-0.2b input level, WP-3.3 fixture)
tier_s.critic:      not_evaluated (WP-2.0b oracle leg, WP-5.3g typst leg)
```

`mode: render` and `self_comparison: false` are the load-bearing part: the
typst leg rendered rather than failing, and the two PDFs are different bytes,
so this is neither the `oracle_only` shape nor a self-comparison. **Per rule
10b that matters here specifically** — a self-comparison would have given this
slice the best possible reading of every clause, and this is not one.

### The target

Per plan revision 56 the page-count clause moved to WP-2.2c and **WP-2.2b is
scored on direct measurement over the shared domain**.

| target clause | outcome |
| --- | --- |
| article openers | **met**: the illustrated opener owns its page on all nine articles, at the transcribed geometry; label and title baselines within 0.00142 pt and 0.00019 pt of the oracle's on 9 of 9 |
| headings | **met**: the 25 pt clearance is transcribed and operative, proved by a committed sweep rather than by the corpus, which cannot falsify it |
| TOC | **met**: nine pinned rows, worst baseline delta 0.00558 pt, both entry columns exact on 44.00000 and 91.00000 |
| page caps | **met**: 7 hard / 10 advisory, enforced at compile time with a committed refusal case |
| **direct measurement over the shared domain** | **met**: 159 boxes and 53 rotations over pages 2..54, **zero** mismatches at `parity.yaml`'s own 0.05 pt tolerance, worst single-coordinate delta **0.000000 pt** |

**Status: `complete`.** No clause is blocked. The page-count clause is not
this slice's and is not recorded as blocked here.

## What is and is not proven

**Which oracle proves what.** WP-2.1's byte-for-byte content equality **proves
text and order only, never structure**, and this WP supplies a second measured
instance of that blindness: `_split_standfirst_overflow` moves the tail of a
standfirst from the opener header into the body, changing which element the
text belongs to and neither the text nor its order, and the content oracle
passes either way. Nothing structural below cites it. **Structure here is
proved only by the PDF**: page boxes, page counts, and measured ink positions.
The contents entry-folio and the `FIGURE nn` / extract labels are the other
half of the same seam: generated content that is printed and that no
text-level oracle sees.

**Did this WP draw its own comparison boundary to make the comparison easier?**
The boundary is `parity.yaml`'s own `tiers.s.box_tolerance_pt` and the
comparator's own box-name set, both unchanged, applied to the largest domain
the two legs share. That domain **grew** from WP-2.2a's pages 2..51 to 2..54,
so this slice compares 159 boxes where WP-2.2a compared 150, and it is the
harder boundary rather than the easier one.

**Proven.**

- *Page boxes and rotations agree exactly over the shared domain.* 159 boxes,
  53 rotations, 0 mismatches, worst single-coordinate delta 0.000000 pt.
- *The illustrated opener owns its page.* Committed test
  `the_illustrated_opener_owns_its_own_page` compiles fixture edition 901
  twice, once with `ILLUSTRATED` bound to the opener name the emitter writes
  and once bound to a name nothing matches, and asserts the first costs more
  pages. **Discrimination**: the second compile is the WP-2.2a behaviour, so a
  template that had lost the break would fail the test.
- *The 25 pt heading clearance is operative.* Proved by a synthetic sweep, not
  by the corpus, because the corpus cannot falsify it (see the ablation).
  **Discrimination**: the same sweep runs against a template with the constant
  zeroed and requires the two to differ.
- *A short quote no longer swallows its page*, and the test that says so
  commits the failing case by substituting WP-2.2a's exact grid text back in.
- *The page cap refuses.* `the_page_cap_refuses_an_article_past_seven_reader_pages`
  patches the cap to 1, compiles fixture 901, and asserts the refusal names
  "the hard cap is 1". **Discrimination**, and specifically rule 10c:
  `a_verbatim_piece_is_not_refused_by_the_article_cap` compiles a 400-paragraph
  piece under `kind: "verbatim"` and asserts it passes — and then compiles
  **the same run under `kind: "article"`** and asserts it is refused. Without
  the second half the expected value (compiles fine) would equal the value a
  template with no cap at all would produce, and the test would pass on the
  wrong branch.
- *The running head is drawn where the stylesheet puts it, on both parities,
  and only where `first-except` puts it.* Name xMin 44.00000 recto and
  42.51970 verso against the oracle's 43.99998 and 42.51968; baseline 13.41250
  against 13.41099; **19 recto and 18 verso pages on each leg**; and **zero**
  running heads on either leg's nine opener pages. **Discrimination**: the
  census is taken over every page of both documents by band rather than by
  index, so a running head drawn on an opener, or missing from a body page,
  would change the count and not only a coordinate.
- *The contents sheet is a pinned grid at the stylesheet's offsets.* Nine
  rows, every baseline within 0.00558 pt of the oracle's, both entry columns
  landing exactly on 44.00000 and 91.00000 (= 44 + 47). The kicker and display
  title likewise. This replaces WP-2.2a's "15 further values, all on page 3
  only, whose placement is PENDING".
- *The folio is correct past page 9*, which no previous evidence had measured.

**Not proven, and who owns proving it.**

- **Page-count equality, and therefore every Tier S, G, V and E clause.** The
  comparator gates all of them on `na == nb`, demonstrated again by this run's
  verdict. **WP-2.2c.**
- **Everything in the PENDING table**, each with its owning slice named there.
- **Text, colour, navigation, glyph and raster agreement.** Not measured here:
  the comparator never reached them. **WP-3.1** to **WP-3.5**.
- **The opener's meta row and standfirst ink.** A constant 2.2656 pt offset
  stands on seven of nine openers (Residuals 1). Measured, cause not found.
- **The density and fitted-size agreement is a corpus observation, not a
  contract** (rule 9). Nine openers is nine data points; the Typst fit differs
  from `_fitted_display` in its text-measurement primitive, which is exactly
  the Pango/Typst difference WP-1.6 and WP-1.7 spent two spikes bounding for
  the body measure. A title one glyph from a step boundary would separate them.
- **The `es` locale.** Untouched and untested, as in WP-2.1 and WP-2.2a.
- **Equality is not correctness.** Both engines now agree that the contents
  entry folio is the target article's own page number, and the two legs print
  *different* numbers (oracle 11, 17, 31, 36, 40, 46, 50; typst 10, 15, 28, 32,
  36, 41, 45) because they paginate differently. That is correct behaviour of
  `target-counter` on each leg and **not** a divergence; it is recorded because
  a reader comparing the two contents pages side by side will see nine
  differences and eight of them are not defects.

## Residuals

1. **A constant +2.2656 pt offset of the opener standfirst on the seven
   compact openers, cause not found, with two hypotheses removed rather than
   argued.** The byline sits 0.2176 pt low and the author note 0.2168 pt low,
   but the standfirst sits 2.2656 pt low on all seven, so the note-to-standfirst
   gap is 2.48 pt larger — numerically within 0.007 pt of `ZERO-LEADING-SANS`
   2.47375, which is recorded as a coincidence and not as a cause.
   - **Hypothesis A, the absent drop cap inflating the oracle's first-line
     box: refuted.** The *second* standfirst line is offset by the same
     2.2656 pt, so the whole block is displaced and this is not a
     bounding-box artifact of the first line.
   - **Hypothesis B, the opener tick and meta rule laid out as inline `rect`s
     inside a paragraph, whose line box would be taller than the 1 pt and
     2.4 pt rules: refuted by substitution.** Both were changed to block-level
     `block`s (which is in any case `.opener-tick { display: block }` at
     :1509) and the PDF came back **byte-identical**, `0c137d27...`. The
     block-level spelling is kept because it is the CSS's, not because it
     changed anything.
   - Ink only, on nine pages, below the fold of the opener; it moves no page
     boundary, since the opener page is filled to its foot either way.
2. **The Typst-side title fit is derived, not transcribed, and this file says
   so rather than presenting 9-of-9 agreement as a transcription.** The
   template mirrors `_fitted_display`'s **algorithm** exactly — step down from
   32.5 pt (compact 30) by 0.5 pt until the title fits two lines and the 64 pt
   box — but its line count comes from Typst's `measure()` where the adapter's
   comes from Pango's `_wrap`. **One asymmetry is worth recording as a latent
   oracle defect neither engine can see (class C):** the adapter measures the
   title **without** the `letter-spacing: -.045em` that the CSS then applies at
   layout, so a title that `_wrap` puts on two lines could reach three under
   tracking and overflow the box unnoticed. The template mirrors the adapter
   (fit without tracking, render with it) so that the two agree; matching the
   oracle here means matching its blind spot, which is what rule 6a's class C
   describes.
3. **The verbatim page cap has no template-side warning.** `render.py:2085-2091`
   prints a warning for a verbatim overrun and raises for every other mode;
   Typst 0.15.1 has `assert` and `panic` and no warning channel, so the
   template enforces the hard branch and is silent on the advisory one.
   Edition 010 exercises this: `dario-amodei-we-must-pace-the-frontier` spans
   **13 pages against the verbatim cap of 10 on both legs** — the same overrun
   `edition-10-intake` recorded — and neither leg refuses it. The warning
   belongs with `layout.article_pages`, which is **WP-2.3**'s.
4. **`piece` gained no `density` parameter, deliberately.** An earlier draft
   added `density: "standard"` so the emitter could pass the adapter's decision
   later. It was removed: an unused parameter with a default is the exact shape
   rule 10c warns about, since a template that ignored the argument entirely
   would behave identically to one that honoured it on every 010 opener. The
   emitter contract is recorded as PENDING instead.
5. **`entry-label`'s 0.45 pt tracking was removed, and that is a change to
   WP-2.2a's transcription rather than a new value.** Re-derived at the point
   of citation per rule 9: `grep -n "letter-spacing"` over `weasyprint-a5.css`
   returns 12 sites; `.contents-kicker` (:325) is one and `.entry-label`
   (:354) is not.
6. **The `mag-piece` metadata mark serves three consumers** — the running
   head's `first-except`, the contents entry folio's `target-counter`, and the
   page cap's span — and a fourth, `mag-piece-end`, closes the span. They are
   invisible content, so WP-2.1's projection is unaffected; the mark lives
   inside `column()` so its page is the page the piece's first content reaches,
   which is what `first-except` resolves against.
7. **Three test totals are quoted at two commits and not one.** 22 binaries
   and 209 tests are the measurement at `1ed37df` with this diff; the landing
   commit's totals are re-derived under `## Landing`, because other WPs landed
   between the two and a total is a measurement with a timestamp.
8. **Edition 010 cannot falsify three of this slice's mechanisms**, and each
   is therefore carried by a synthetic or fixture case rather than by the
   corpus: the 25 pt clearance (page-count-neutral here), the page cap (no 010
   article reaches 7 pages except the verbatim one, which is advisory), and
   `doc-code`'s ruled block (010 carries no fenced code). The first two have
   committed discriminating tests; the third is **WP-3.3**'s fixture.

## Landing

Base captured before rebasing, the rebase performed onto that captured value,
and the branch swapped compare-and-set against it rather than against a tip
re-read at update time.

- `B` captured before the first rebase: **`f127381`** (`docs(plans): typst
  parity plan revision 58`). Rebased onto it with
  `git rebase --onto $B 1ed37df HEAD` and the rebased commit's parent verified
  equal to `$B`.
- **The compare-and-set then REFUSED**, and this file records that rather than
  eliding it: `git update-ref refs/heads/art_directed <new> f127381` reported
  *is at `096e163` but expected `f127381`*. `096e163`
  (`docs(verification): WP-0.2k accepted`) had landed in the interval. **The
  response was to rebase again, not to re-read the tip and retry**: a swap
  against a tip re-read at update time succeeds precisely in the case it
  exists to refuse, which is the case where someone else's work is between
  you and the branch.
- `B2` captured before the second rebase: **`096e163c2b57a8c55780336827a75b9c55e617d0`**.
  Rebased onto it, parent verified equal to `$B2`, swapped
  `git update-ref refs/heads/art_directed <new> $B2`.
- **Did the newly-landed commit change what must be re-verified?** `096e163`
  adds one file, `meta/verification/evidence/WP-0.2k.verify.md`, and no code;
  `git diff --stat f127381..096e163` is `1 file changed, 463 insertions(+)`.
  Nothing this slice measures is downstream of it, so the re-verification
  table below stands as measured at the first landing commit.

**Re-verified at the landing commit, not only at the measurement commit**,
because `a911ff1` (WP-5.4c cover PDF writer) landed in between and a total is
a measurement with a timestamp:

| quantity | at `1ed37df` (measurement) | at the landing commit |
| --- | --- | --- |
| `cargo test` binaries / tests | 22 / 209 | **23 / 221** |
| `cargo fmt --check`, `clippy --all-targets -D warnings` | clean | **clean** |
| typst leg pages | 55 | **55** |
| typst leg `reader.pdf` sha256 | `0c137d27...` | **`0c137d27...`, identical** |
| page boxes / rotations compared, mismatches | 159 / 53, 0 | **159 / 53, 0** |
| worst single-coordinate box delta | 0.000000 pt | **0.000000 pt** |

The twelve tests and one binary `a911ff1` added are the cover writer's; the
PDF hash is unchanged, so nothing it landed reaches this slice's output.
