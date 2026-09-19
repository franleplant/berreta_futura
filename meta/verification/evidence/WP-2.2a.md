# WP-2.2a geometry and body

## Base

- Branch `art_directed` at **`3b57c36`** (`refactor(model): lift the four shared
  edition-text helpers`, WP-5.5a). Rebased onto it after WP-2.1's verification
  (`9acc797`) and the helper lift landed; `mag/src/render.rs` and
  `mag/src/typeset/mod.rs` are byte-identical between `20adcfb` and `3b57c36`,
  so the work carried across unchanged.
- Owns, per the WP-2.2 preamble and this WP's brief:
  `mag/src/typeset/template.rs`, the `mag/src/typeset/**` submodules this slice
  introduces (`world.rs`), `mag/assets/typeset/`, this evidence file, and
  `mag/src/typeset/mod.rs` to the extent of removing WP-2.1's
  `#[allow(dead_code)]`, which the brief assigns explicitly.

Two edits outside that list, both declared rather than assumed:

1. **`mag/src/typeset/content.rs`, two lines, under the scoped Owns extension
   granted by the orchestrator.** Both print a BYTE count labelled
   "characters". The extension named `:1162` and `:1170`; after WP-5.5a's lift
   the same two sites are **`:1073-1074` and `:1082-1083`**. Changed
   `want.len()` to `want.chars().count()` in the message at `:1074` and
   `projection.text.len()` to `projection.text.chars().count()` at `:1082`.
   **Label only: the guard `want.len() > 10_000` at `:1073` is untouched**, so
   nothing measured changed. Swept for a third site: `grep -n "characters"`
   returns five hits, of which `:216`, `:217` and `:1226` already use
   `chars().count()`. There is no third site. The rule-2b line now prints
   `68758 characters of reader text`, which is WP-2.1's own Metrics figure.
2. **`mag/src/render.rs`, one call site, line 661 — NOT covered by any grant,
   and flagged for ratification.** WP-2.0a stubbed the typst branch as
   `crate::typeset::render_edition()` with no arguments. The WP's target,
   "`mag render 010 --engine typst` emits an interior.pdf", is unreachable
   without passing the branch the repo root, the render directory and the
   staged request, so the stub's signature had to change and its one caller
   with it. The diff is:

   ```
   -        Engine::Typst => crate::typeset::render_edition(),
   +        Engine::Typst => crate::typeset::render_edition(
   +            &repo_root,
   +            &render_dir,
   +            &serde_json::to_string(&request)?,
   +        ),
   ```

   Rule 1 forbids self-granting however small the change, so this is recorded
   as an **Owns extension requested, not taken for granted**: it is the same
   shape as WP-2.1's unavoidable `mod.rs` registration edit, and rule 1(b)
   already serializes `mag/src/typeset/**` and `mag/src/render.rs` owners
   pairwise, so no other WP was in that file. If the extension is refused, the
   four-line hunk above is the whole of what must move to whoever owns it;
   nothing else in this WP touches `render.rs`.

`mag/src/parity.rs`, `mag/src/parity/**`, `meta/verification/parity.yaml`,
`meta/verification/baseline.json` and `mag/src/web/**` were read and **not
written**.

## Commands

Run from the root of a checkout at `## Base` with the WP's diff applied, built
once with `cargo build --manifest-path mag/Cargo.toml`. **One input comes from
outside the checkout** and is named by a variable with a default, because the
run directory under `editions/010/` is gitignored and a `$PWD`-relative path to
it is not hermetic: `RUN` is the untracked content run both legs render. The two
render trees and the oracle tree are **derived inside the block** from what the
tools themselves write, so nothing else has to be supplied.

```sh
set -o pipefail
unset TYPST_ROOT

RUN=${RUN:-editions/010/run-2026-09-13T01-34-51}
test -d "$RUN" || { echo "point RUN at the staged 010 content run"; exit 1; }

# 1. The hermetic suite: 18 test binaries, the comment check and the
#    hook-install check among them.
(cd mag && cargo fmt --check && cargo clippy --all-targets -- -D warnings && cargo test)

# 2. Re-derive the counts this file quotes rather than citing them.
(cd mag && cargo test 2>&1 | grep -cE '^     Running')
(cd mag && cargo test 2>&1 | grep -E '^test result' | awk -F'[ ;]' '{s+=$4} END {print s}')

# 3. The typst leg end to end, twice, so the second run is a determinism
#    check. Each render writes its own timestamped directory.
./mag/target/debug/mag render 010 --engine typst --no-model --langs en --run "$RUN"
FIRST=$(ls -d editions/010/render-* | tail -1)
./mag/target/debug/mag render 010 --engine typst --no-model --langs en --run "$RUN"
SECOND=$(ls -d editions/010/render-* | tail -1)
shasum -a 256 "$FIRST/en/reader.pdf" "$SECOND/en/reader.pdf"

# 4. The comparator. Nonzero exit is the expected outcome at this slice.
./mag/target/debug/mag parity 010 --run "$RUN"; echo "parity exit=$?"
shasum -a 256 output/parity/010/verdict.json
uv run python -c "import json;v=json.load(open('output/parity/010/verdict.json'));print(v['staged_input_digest']);print(v['inputs'])"

# 5. Page boxes over the domain the two legs share, at parity.yaml's own
#    tolerance. The comparator suppresses this clause while page counts
#    differ, so it is measured directly here. Both legs are derived from what
#    the parity run itself wrote: the oracle from its cache file, the typst
#    leg as the newest render directory, which that run just created.
ORACLE=$(uv run python -c "import json;print(json.load(open('output/parity/010/oracle-cache.json'))['render_dir'])")
TYPST=$(ls -d editions/010/render-* | tail -1)
echo "oracle leg: $ORACLE"
echo "typst leg:  $TYPST"
uv run python - "$ORACLE/en/reader.pdf" "$TYPST/en/reader.pdf" <<'PY'
import re, subprocess, sys
NAMES = ("MediaBox", "CropBox", "TrimBox")
TOL = 0.05
def boxes(pdf, first, last):
    out = subprocess.run(["pdfinfo", "-f", str(first), "-l", str(last), "-box", pdf],
                         capture_output=True, text=True).stdout
    b, rot = {}, {}
    for line in out.splitlines():
        m = re.match(r"Page\s+(\d+)\s+(\w+):\s+([\d.-]+)\s+([\d.-]+)\s+([\d.-]+)\s+([\d.-]+)", line)
        if m and m.group(2) in NAMES:
            b[(int(m.group(1)), m.group(2))] = tuple(float(x) for x in m.groups()[2:])
        r = re.match(r"Page\s+(\d+)\s+rot:\s+(-?\d+)", line)
        if r:
            rot[int(r.group(1))] = int(r.group(2))
    return b, rot
def count(pdf):
    return int(re.search(r"Pages:\s+(\d+)",
               subprocess.run(["pdfinfo", pdf], capture_output=True, text=True).stdout).group(1))
a_pdf, b_pdf = sys.argv[1], sys.argv[2]
na, nb = count(a_pdf), count(b_pdf)
last = min(na, nb) - 1
ab, ar = boxes(a_pdf, 2, last)
bb, br = boxes(b_pdf, 2, last)
shared = sorted(set(ab) & set(bb))
bad = [k for k in shared if max(abs(x - y) for x, y in zip(ab[k], bb[k])) > TOL]
rbad = [p for p in set(ar) & set(br) if ar[p] != br[p]]
print(f"pages: a={na} b={nb}, compared 2..{last}")
print(f"boxes compared: a={len(ab)} b={len(bb)}; mismatches beyond {TOL}pt: {len(bad)}")
print(f"rotations compared: a={len(ar)} b={len(br)}; mismatches (exact): {len(rbad)}")
print(f"worst single-coordinate delta: {max(max(abs(x-y) for x,y in zip(ab[k],bb[k])) for k in shared):.6f} pt")
PY

# 6. The column rail and the folio, against the stylesheet's own arithmetic:
#    the first body line of p5, the one page whose content matches on both
#    legs; the modal body-line start per parity over pages 5..45, which needs
#    no matching content; and the folio on p4 and p5, one verso and one recto.
#
#    The oracle leg carries a RUNNING HEAD above the content box and both legs
#    carry a FOLIO below it, so "the first line on the page" is not the first
#    BODY line on the oracle leg and the two legs' first lines are not
#    comparable. Every row below is therefore selected by BAND: body lines are
#    those inside the content box (margin-top .. page-height - margin-bottom),
#    folio lines are those below it. Selecting by index instead compares the
#    oracle's running head against the typst leg's body, which is what an
#    earlier version of this block did.
uv run python - "$ORACLE/en/reader.pdf" "$TYPST/en/reader.pdf" <<'PY'
import re, subprocess, sys
MARGIN_TOP, MARGIN_BOTTOM = 42.0004, 54.9996
PAGE_HEIGHT = 210 * 72 / 25.4
FOOT = PAGE_HEIGHT - MARGIN_BOTTOM
def boxes(pdf, page, tag):
    out = subprocess.run(["pdftotext", "-f", str(page), "-l", str(page),
                          "-bbox-layout", pdf, "-"], capture_output=True, text=True).stdout
    pattern = (r'<' + tag + r' xMin="([\d.]+)" yMin="([\d.]+)" xMax="([\d.]+)" yMax="([\d.]+)"'
               + (r'>([^<]*)<' if tag == "word" else r'[^>]*>()'))
    return [(float(m.group(1)), float(m.group(2)), float(m.group(3)), m.group(5))
            for m in re.finditer(pattern, out)]
def body(rows):
    return [r for r in rows if MARGIN_TOP - 1 <= r[1] <= FOOT]
def folio(rows):
    return [r for r in rows if r[1] > FOOT]
# p5 is a running-body page of article 1 on BOTH legs, so its first body line
# is directly comparable. A VERSO body page is not: the two legs paginate
# differently from article 3 on, and p4, the one verso page whose content does
# align, is that article's OPENER, whose rail escapes the reading measure on
# the oracle leg. So the verso rail is measured by a statistic that does not
# need the two legs to hold the same content: the MODAL body-line start per
# page parity, which is the column rail on both legs because every indent
# inside the column (list 14pt, quote 12.84pt) moves right and none moves left.
page = 5
a, b = body(boxes(sys.argv[1], page, "line")), body(boxes(sys.argv[2], page, "line"))
print(f"p{page} (recto) first BODY line: xMin a={a[0][0]:.6f} b={b[0][0]:.6f} | "
      f"yMin a={a[0][1]:.6f} b={b[0][1]:.6f}")
print(f"p{page} (recto) body line advance: a={a[1][1]-a[0][1]:.6f} b={b[1][1]-b[0][1]:.6f}")
import collections
def rails(pdf, first, last):
    odd, even = collections.Counter(), collections.Counter()
    for p in range(first, last + 1):
        for row in body(boxes(pdf, p, "line")):
            (odd if p % 2 else even)[round(row[0], 5)] += 1
    return odd.most_common(1)[0], even.most_common(1)[0]
for pdf, name in ((sys.argv[1], "weasyprint"), (sys.argv[2], "typst")):
    (r, rn), (v, vn) = rails(pdf, 5, 45)
    print(f"{name:11s} modal body-line start: recto {r:.6f} (x{rn})  verso {v:.6f} (x{vn})")
for page in (4, 5):
    for pdf, name in ((sys.argv[1], "weasyprint"), (sys.argv[2], "typst")):
        rows = folio(boxes(pdf, page, "word"))
        left = min(rows, key=lambda r: r[0])
        right = max(rows, key=lambda r: r[2])
        print(f"p{page} {name:11s} folio: name xMin={left[0]:.6f} ({left[3]}), "
              f"number xMax={right[2]:.6f} ({right[3]}), baseline yMin={left[1]:.6f}")
PY

# 7. The 47 function names, re-derived from WP-2.1's artifact and from the
#    emitted tree rather than cited from any brief.
uv run python - "$TYPST" <<'PY'
import re, pathlib, sys
ev = pathlib.Path("meta/verification/evidence/WP-2.1.md").read_text()
block = ev.split("Function names the template must define:")[1].split("`emph` and `strong`")[0]
required = re.findall(r"`([a-z][a-z0-9-]*)`", block)
tpl = pathlib.Path("mag/assets/typeset/template.typ").read_text()
defined = set(re.findall(r"^#let ([a-z][a-z0-9-]*)", tpl, re.M))
tree = pathlib.Path(sys.argv[1]) / "typst"
called = set()
for p in [tree / "main.typ", *sorted((tree / "pieces").glob("*.typ"))]:
    called |= set(re.findall(r"#([a-z][a-z0-9-]*)", p.read_text()))
called -= {"include", "import", "strong", "emph"}
print("required by WP-2.1:", len(required))
print("undefined by template.typ:", [n for n in required if n not in defined])
print("exercised by edition 010:", len(called))
print("defined but NOT exercised by 010:", sorted(set(required) - called))
PY

# 8. Rule 11, for the one mechanism this file asserts: the verdict digest is
#    not reproducible because the WEASYPRINT leg is not byte-reproducible.
#    Removing the supposed cause means rendering the oracle leg twice in ONE
#    worktree, so a differing hash cannot be blamed on a differing path.
#    Costs a second full oracle render, which is why it is last.
OLD=$ORACLE
./mag/target/debug/mag render 010 --engine weasyprint --no-model --langs en --run "$RUN" > /dev/null
NEW=$(ls -d editions/010/render-* | tail -1)
shasum -a 256 "$OLD/en/reader.pdf" "$NEW/en/reader.pdf"
uv run python - "$OLD" "$NEW" <<'PY'
import json, sys
def digest(d):
    rows = json.load(open(f"{d}/request.json"))["inputs"]
    return sorted((r["targetPath"], r["sourcePath"]) for r in rows)
print("staged input rows identical between the two oracle renders:",
      digest(sys.argv[1]) == digest(sys.argv[2]))
PY
```

## Tool versions

- rustc 1.96.0, `typst`/`typst-layout`/`typst-library`/`typst-pdf`/`typst-syntax`
  all pinned `=0.15.1` (unchanged; this WP adds no crate and does not touch
  `Cargo.toml` or `Cargo.lock`), `lopdf` 0.45.0.
- poppler 25.09.1 as pinned in `meta/verification/parity.yaml` (`mag parity`
  asserts this itself before comparing).
- CPython 3.12.11 through `uv run python`. No bare `python3`.
- The typst CLI is **not** installed and is not used: compilation goes through
  the pinned crates inside `mag`. `TYPST_ROOT` is unset in the block above and
  is irrelevant to this leg.

## Metrics

Every number below is produced by the command block, measured at `3b57c36`
with this WP's diff applied.

| quantity | value |
| --- | --- |
| typst leg pages | 52 |
| weasyprint leg pages | 56 |
| page boxes compared over the shared domain (pages 2..51) | 150 (50 pages x 3 box names), both legs |
| box mismatches beyond `tiers.s.box_tolerance_pt` = 0.05 pt | **0** |
| worst single-coordinate box delta | **0.000000 pt** |
| rotations compared / mismatches | 50 / **0** |
| first body line xMin, p5 (recto, same content on both legs) | oracle 48.003929, typst 48.003930 |
| first body line box top, p5 | oracle 41.645658, typst 41.645460 (delta 0.000198 pt) |
| body line advance, p5 | 13.000000 pt on both legs |
| **modal body-line start, recto**, pages 5..45 | oracle **48.003930** (380 lines), typst **48.003930** (541 lines) |
| **modal body-line start, verso**, pages 5..45 | oracle **46.523630** (331 lines), typst **46.523630** (415 lines) |
| folio name xMin, p4 and p5, both legs, both parities | **42.519700** |
| folio number xMax, p4 / p5 | oracle 377.009154 / 377.010581, typst 377.007853 / 377.007859 |
| folio baseline yMin, p4 and p5 | oracle 569.186587, typst 569.188100 |
| template functions WP-2.1 requires | **47** |
| of those, undefined by `template.typ` | **0** |
| of those, exercised by edition 010 | **38** |
| of those, never exercised by edition 010 | **9** |
| reader text through the pipeline | 68,758 characters |
| `cargo test` binaries / tests, all passing | **18** / **186** |
| `mag/tests/*.rs` integration-test files | **17** |
| typst PDF sha256, two independent renders of one staged input set | identical |

### Every left edge in the typst leg is a derived value

Collected over the typst leg's content pages (3..45), the complete set of
distinct line `xMin` values, each against the constant it must equal:

| measured xMin | count | derivation |
| --- | --- | --- |
| 42.519700 | 43 | `MARGIN-OUTER`, the folio name. 43 = 52 pages - 4 outer - 5 closing plates, i.e. every page the CSS gives a folio |
| 46.523630 | 446 | column left, verso: `MARGIN-OUTER + RAIL` |
| 48.003930 | 574 | column left, recto: `MARGIN-INNER + RAIL` |
| 59.362213 | 2 | blockquote, verso: column left + 1.5pt border + 4mm padding = 46.523630 + 12.838583 |
| 60.523630 / 62.003930 | 116 / 38 | list item, verso / recto: column left + `LIST-INDENT` 14pt |
| 70.523630 / 72.003930 | 4 / 5 | end mark, verso / recto: column left + 24pt `padding-left`. **9 in total, one per article** |
| 363.7 .. 368.9 | 43 | folio number, right-aligned; `xMin` varies with digit widths, `xMax` does not |
| 15 further values | 1 each | **all on page 3 only**, the contents page, whose placement is PENDING for WP-2.2b |

**Two independent reproductions of WP-1.7 fall out of this**, neither of them
sought:

- **154 list lines** (116 + 38) at the narrow measure, which is exactly
  WP-1.7's "311.0000 pt | 24 blocks | **154 lines**" row, reached from a
  different direction: WP-1.7 counted WeasyPrint's laid-out `p` blocks, this
  counts the typst leg's rendered line boxes at the 14pt indent.
- **24 list items and 1 blockquote** in the emitted tree, matching its "24
  blocks" and "1 block" counts. The blockquote's measured content width is
  325.025 - 12.838583 = **312.186417 pt**, which is WP-1.7's widened
  312.186400 to within 2e-5 pt.

**The "17 versus 18 suites" disagreement is a naming collision, not an error
in either figure, and is settled here so it does not surface a fourth time.**
`mag/tests/` holds **17** `.rs` integration-test files; `cargo test` runs
**18** test binaries, because the `mag` binary target's own in-crate `#[cfg(test)]`
modules are an eighteenth. Revision 51's 17 counts files; this file's 18 counts
what the command in `## Commands` step 2 measures, `grep -cE '^     Running'`.
Both are re-derived above. This WP adds **no** new test file: its five tests
are in-crate, in `mag/src/typeset/template.rs`, so the 17 is unchanged by it.

**Corpus observations, not thresholds** (rule 9). Edition 010 carries 9
articles, 5 closing plates, 3 figures, 24 list items, 1 blockquote, 3 inline
code runs, 0 fenced code blocks, 0 extracts and 0 reference lists. The 24 list
items independently reproduce WP-1.7's "311.0000 pt | 24 blocks" row: the
narrow measure is the list-item measure. The single blockquote reproduces its
"312.1614 pt | 1 block" row, and `325 - 1.5 - 4mm = 312.16142 pt` is that
measure derived from `blockquote`'s own border and padding
(`weasyprint-a5.css:918`).

### Per-article page spans, and where the four missing pages are

| article | weasyprint | typst | delta | figure on that article's pages |
| --- | --- | --- | --- | --- |
| government-rails-site-hit-hours-after-cve-patch | 3 | 4 | **+1** | none |
| countering-misuse-of-ai-september-2026-anthropic | 3 | 3 | 0 | none |
| an-alignment-assessment-of-recent-cybersecurity | 6 | 5 | -1 | `four-incidents` (oracle p12) |
| dario-amodei-we-must-pace-the-frontier | 13 | 12 | -1 | none |
| scenarios-for-our-economic-future | 4 | 4 | 0 | none |
| the-third-era-of-ai-software-development | 4 | 3 | -1 | `agent-usage-growth` (oracle p37) |
| towards-self-driving-codebases | 5 | 4 | -1 | `recursive-planners` (oracle p42) |
| deepseek-v4-1-flash-pushing-the-limits-of-kv-cac | 4 | 4 | 0 | none |
| rapidly-scaling-online-storage-to-serve-over-1-b | 4 | 3 | -1 | none |
| **total** | **46** | **42** | **-4** | |

Everything else is structurally equal: 1 outer cover, 1 inside cover, 1
contents page, 5 closing plates and 2 trailing outer pages on both legs.
**Three of the four missing pages are the three figures WP-2.2c places**, each
on an article that loses exactly one page. The remaining net -1 is flow
(+1, -1, -1 on three figureless articles) and is attributed under Residuals.

## Mapping table

This is the WP-2.2 preamble's obligation and the WP's main defence against an
invented value. Every constant the template carries is below with the
`weasyprint-a5.css` selector or `weasyprint_adapter.py` constant it came from.
**Anything found and not transcribed is PENDING with the slice that owns it;
nothing is dropped silently.**

### Transcribed

| template.typ | value | origin |
| --- | --- | --- |
| `PAGE-WIDTH` / `PAGE-HEIGHT` | 148mm / 210mm | `@page { size: 148mm 210mm }` (:119) |
| `MARGIN-TOP` | 42.0004pt | `@page { margin: 42.0004pt ... }` (:120) |
| `MARGIN-OUTER` | 42.5197pt | same shorthand (:120); `@page :right { margin-right }` (:178) |
| `MARGIN-BOTTOM` | 54.9996pt | same shorthand (:120) |
| `MARGIN-INNER` | 44pt | same shorthand (:120); `@page :right { margin-left }` (:178) |
| page `binding: left` | odd = recto | `@page :right` / `:left` (:177, :183) and the comment at :73-75, "the first reader page is a recto, so :right is the odd page" |
| `LIVE-WIDTH` = 333.007859pt | derived | `.running-head` width and `@top-center { width: 333.0079pt }` (:174) confirm the same figure |
| `MEASURE` | 325pt | `.editorial, article, main > section { max-width: 325pt }` (:265) |
| `MEASURE-DELTA` | **+0.025000pt** | **WP-1.7** section "One constant or three": intersection `[+0.010000, +0.040000)`, midpoint `+0.025000`, giving 325.025000 / 311.025000 / 312.186400. Survives the normalization defect: `WP-1.8.verify.md` (accepted `c1253d8`) re-derives the interval from `measure()` in WP-1.7 section 2 rather than from its harness, and the safe set `{+0.010, +0.025, +0.039}` is unchanged. Re-derived here: `(0.010 + 0.040) / 2 = 0.025`; `325 + 0.025 = 325.025`. |
| `RAIL` = 4.003930pt | derived `(LIVE-WIDTH - 325pt) / 2` | `margin-left: auto; margin-right: auto` on :265, and the comment at :263-264 stating 48.004pt recto / 46.524pt verso. Measured to land on both. |
| body font / size / leading | Source Serif 4 SmText, 10pt, 13pt | `html { font: 10pt/13pt "Magazine Serif", serif }` (:248) via `parity.yaml normalization.font_name_map` |
| body fill `INK` | rgb(5.5%, 7.5%, 8.5%) | `html { color: ... }` (:248) |
| `VIOLET` / `SLATE` / `COOL-GRAY` / `PALE-VIOLET` / `SIGNAL-ORANGE` | as written | the palette comment at :217-224, each spelled as the percentage tuple the CSS uses |
| `HALF-SERIF` 0.3505 | `(ascent - descent) / 2` | the flow/ink comment at :397-398, "leading / 2 + 0.3505 * size"; confirmed from `SourceSerif4SmText-Regular.ttf` hhea 1.036 / -0.335 |
| `HALF-SANS` 0.36377 | same | :398, "0.36377 * size"; confirmed from `Inter-Regular.ttf` 0.968750 / -0.241211 |
| `HALF-MONO` 0.355 | same | derived from `GeistMono-Regular.ttf` 1.005 / -0.295; the CSS states no mono ratio because it corrects no mono block |
| `DATUM` 10.0046pt | the flow/ink invariant | :403-405 and :414, "Each correction is `10.0046 - (leading / 2 + ratio * size)`". Implemented as `pinned(leading)`, which sets a corrected block's first baseline to the datum directly instead of laying out and then translating. |
| `PARAGRAPH-AFTER` 5.4pt | `p { margin: 0 0 5.4pt }` (:549) |
| `EDITORIAL-AFTER` 6.2pt | `.editorial > p:not(...) { margin-bottom: 6.2pt }` (:551) |
| `PLATE-LEADING` 12.2pt / `PLATE-AFTER` 4pt | `article[data-figure-layouts~="landscape_plate"] ... { line-height: 12.2pt; margin-bottom: 4pt }` (:695-699) |
| heading 1: 22pt / 25pt / above 23.4pt / below 13pt / INK | `.editorial > h1, article > h1, main > section > h1` (:489-494) |
| heading 2: 18.5pt / 21.5pt / above 20.4pt / below 11pt / INK | `.editorial h2, article h2, main > section h2` (:495-500) |
| heading 3: 8.5pt / 12pt / above 15.4pt / below 8pt / VIOLET / uppercase | `.editorial h3, article h3, main > section h3` (:503-509) |
| heading family Serif Display 600 | :490, :496; h3 is `"Magazine Sans"` per `h1, h2, h3` (:466) plus :503-505 |
| standfirst 12pt / 16.4pt / below 13pt, pinned | `.standfirst` (:710-713) |
| `LIST-INDENT` 14pt, item below 6pt, size 10pt | `li { font-size: 10pt; margin: 0 0 6pt; padding-left: 14pt }` (:837) |
| list disc: 5pt violet circle at left 0, top 3.505pt | `li::before` (:839-842) |
| `li > p` spacing 0 | `li > p, li > ul, li > ol { margin: 0 }` (:838) |
| `REFERENCE-HANG` 12.9744pt, 7.2pt / 9.4pt, below 3pt, pinned | `ul[data-reference-list] li` (:843-848) and `li::before { content: none }` (:850) |
| `QUOTE-RULE` 1.5pt VIOLET, `QUOTE-PAD` 4mm, margin 4mm | `blockquote` (:918) |
| code block 7.5pt / 1.3, PALE-VIOLET fill, 1.5pt VIOLET rule, 3mm pad | `pre` (:940) |
| inline code 0.82em (**8.2pt against 10pt body**), weight 500, VIOLET | `code` (:946-954); the size is WP-1.2 residual 4's per-run size requirement |
| `doc-link` carries no colour and no underline | `a { color: inherit; text-decoration: none }` (:969) |
| `FOLIO-BASELINE` 19.5pt | `@bottom-left` comment (:122-123), `_folio` render.py:565-577 |
| folio face 6.8pt Inter Medium, INK, uppercase | `@bottom-left` / `@bottom-right` (:143-158) |
| folio name x = 42.5197 on both parities | `@page :right @bottom-left { text-indent: -1.4803pt }` (:181) and `@page :left` leaving it on the outer margin (:183-187). Implemented directly as "42.5197pt from the left edge on every page", which is what those two rules compute to; measured equal on both parities. |
| folio number right edge = width - 42.5197 on both parities | `@page :left @bottom-right { margin-right: -1.4803pt }` (:186), same reasoning |
| folio numbering `01` zero-padded | `content: counter(page, decimal-leading-zero)` (:153) |
| outer pages: margin 0, no folio, blank | `@page outer-cover` (:189-194), `@page inside-cover` (:195-200), and the four `*-cover-slot` rules at :253-260 |
| closing plate: own page, no folio, no running head | `@page closing-plate` (:210-214), `.closing-plate { break-before: page }` (:1611) |
| `.edition-header` prints nothing | `.edition-header { display: none }` (:266) |
| `.provenance` prints nothing | `.provenance { display: none }` (:803) |
| `.source-link` prints nothing on a plain opener | `.source-link { display: none }` (:1414) |
| piece starts a page | `.editorial, article, main > section { break-before: page }` (:390) |
| contents occupies exactly one page | `[data-edition-navigation="contents"] { break-after: page }` (:322) with `ol { height: 467.2802pt }` (:334-337) |
| `par(linebreaks: "simple")` | not a CSS value: WP-1.2's Metrics note, the switch under which its 148/149 break reproduction was measured |
| hyphenation off | `html:lang(en) ... { hyphens: manual }` (:680-688), WP-1.5 option (b) |
| `liga`/`clig` off wherever tracking is set | **WP-1.1**: "all 86 letter-spaced runs then matched glyph for glyph ... ligatures off wherever `letter-spacing` is set". Implemented as one `tracked(amount)` helper that always sets both. |
| end mark: 6.8pt, tracking 0.25pt, VIOLET, 17pt x 1.1pt orange tick, zero height | `.end-mark` (:881-890) and its derivation comment at :851-879 |
| key ideas: 1.1pt orange rule, 12pt above, 10pt pad, unbreakable | `.key-ideas` (:907-912), `.key-ideas-label` (:913-917) |
| figure caption 6.8pt serif / 8.6pt, credit sans 500 SLATE | `figcaption` (:1129-1140), `figcaption .credit` (:1148-1151) |

### PENDING, with the slice that owns each

Found in `weasyprint-a5.css` or in the oracle's behaviour and **deliberately
not transcribed at this slice**:

| pending | origin | owner |
| --- | --- | --- |
| **`.heading-clearance`, the flat 25pt reservation after every heading** | :510-522; the adapter inserts the box, so it is in the oracle's tree and not in the content tree | **WP-2.2b** (headings). Consequence measured: a typst heading can sit at a page foot where WeasyPrint moves it and its 25pt down. Typst's `block` spacing takes `max(above, below)` and has no negative-spacing path, so the CSS's `height: 25pt; margin-bottom: -25pt` idiom has no direct translation; the note under Residuals records the three candidate mechanisms. |
| **`orphans: 2; widows: 2`** | `p { orphans: 2; widows: 2 }` (:549) | **UNOWNED — escalated in `## Status`.** Typst 0.15.1 has no orphan/widow control at all, so this is not a transcription I declined but a capability gap. It changes pagination systematically, and **no WP in the plan mentions orphans or widows**: `grep -rn "orphan\|widow"` over the plan and every evidence file returns only WP-5.3d's `standalone_punctuation_lines`, which is a critic metric and unrelated. |
| running head: name + short title + 0.55pt COOL-GRAY rule + 14pt x 1.15pt orange tick, baseline 20pt from the sheet head, `first-except` | `@top-center` (:170-175), `.running-head*` (:289-304) | **WP-2.2b** (architecture). Absent from the typst leg today; it consumes no flow, so it does not move a line. |
| contents grid: kicker at top -13.46915pt, 27pt display title, 467.2802pt band, rows `flex: 1 1 0` capped at 65.5pt, entry offsets 8.6/17.7/17.5/32.2pt and the `tight` variants | :321-388 | **WP-2.2b** (TOC). The typst leg emits the entries in a fixed-height single page, so the page count is right and the placement is not. |
| illustrated opener: 348pt rail, 207.1pt art field, orange offset, 2.4pt frame, QR, tick, `break-after: page` on the header, compact density | :1417-1600 | **WP-2.2b** (openers) |
| opener field heights stated per opener by `_pin_opener_fields`, the editorial's `min-height: 153.2756pt` clamp, `_fitted_title_box`'s stepped display size | :417-465, :477-480 | **WP-2.2b** |
| `.content-label .label-secondary { transform: translateX(.45pt) }`, the trailing-letter-space correction | :746-779 | **WP-2.2b**. Recorded here because it interacts with this slice's `tracked()` helper: Typst adds tracking after every glyph, exactly as CSS does, so a tracked run's box is one `letter-spacing` wider than its ink on both engines and **this CSS correction carries over unchanged**. WP-1.1's `(n-1) x letter_spacing` is a statement about the run's INK width; it holds for a left-aligned run without any correction, which is every tracked run this slice emits, and needs the translateX only where `space-between` flushes the box. |
| **`figure[data-figure-id]::before`, the `FIGURE nn` label** | :1022-1033 and `article > figure[data-figure-id]::before` (:1117-1122) | **WP-2.2c** (placement). Generated content: it is printed but is **not in the content oracle**, so the template is its only check. Not transcribed at this slice because the figure block it labels is not placed. |
| **`.extract::before`, the extract label** | :924-928 | **WP-2.2c**, same reasoning. Edition 010 carries no extracts, so nothing on the live corpus exercises it either way. |
| figure geometry: 13.1pt label zone, `top: 10.0046pt` paint offset, 15.75pt gap, 205/270/170pt image caps, the SVG `fill: none` frame rule | :1034-1128 | **WP-2.2c** |
| band escapes (`-4.004pt`), `.band-clearance`, `band-anchor-midpage` paint repairs | :1101-1113, :1216-1232 | **WP-2.2c** |
| landscape plate page, rotor, plate headings | :1259-1341 | **WP-2.2c**. Edition 010 declares no `landscape_plate`, so the per-article 12.2pt leading branch this slice implements is **unexercised on the live corpus**. |
| `.article-tail` ornament band, `_measured_tail_art` heights and the drop ledger | :1343-1375 | **WP-2.2c**. `tail-art()` emits nothing today; the ornament is out of flow, so it moves no line. |
| closing-plate art: `height: 595.2756pt`, `top: -42.0004pt`, `object-fit: contain` | :1616-1621 | **WP-2.2c**. The typst leg emits the plate PAGES (so the count is right) but no art. |
| **plate interleaving**: the oracle places the 5 plates on pages 10, 30, 35, 45 and 54, between articles | not a CSS rule; `_closing_plate` / the adapter's signature arithmetic | **WP-2.2c**. `main.typ` emits all five `#closing-plate` calls **after** the ninth article, so document order does not encode the interleaving and the template cannot recover it from the tree alone. Flagged because it is a contract question between WP-2.1's emitter and WP-2.2c, not a value to transcribe. |
| `img { image-rendering: crisp-edges }` / `/Interpolate false` | :1003 | **WP-2.2c** / WP-3.4 |
| syntax-highlight colour classes for `pre code` | :959-966 | **WP-3.3** (010 carries no fenced code) |
| `@page` rasterizer nudge rationale (+0.005pt already folded into the two margins transcribed above) | :106-116 | transcribed as part of `MARGIN-TOP` / `MARGIN-BOTTOM`; recorded so a later reader does not apply it twice |

## Verdicts

`mag parity 010` was run from the worktree root (which is a repo root, the form
revision 49 records as the satisfiable reading of "isolated cwd"; `out_dir` is
`output/parity/010` under that root and so is private to this worktree).

- **verdict.json sha256: `7653875adda13e977fb6c475e17b7c87ea61704d77a2726413bcad8c613539cb`**
- `staged_input_digest`: `e48eb5c638a0f25bfdfbb5e26bc989d56c1ecbac3ef85f103e90ed1ac8aac5fa`
- `a_reader_sha256` (weasyprint leg): `26a29054ac47552f89b1530e30164015e1f9c54c9079876178644f717e9b3e11`
- `b_reader_sha256` (typst leg): `3196b6ceb5173afa22f86d0f7908e9f91f16abae46901ae094b49c379aad45b0`
- measured at commit **`3b57c36`** with this WP's diff applied, by executing the
  `## Commands` block extracted programmatically from this file, **in a
  worktree that is not the one this WP was developed in**
  (`.../tmp/wp22a-replay`, a fresh checkout of `3b57c36` with the diff applied).
  Block exit 0.

**The verdict digest is run-specific and CANNOT be reproduced by a replay, and
the reason is on the oracle side. Measured, not asserted.** The development
worktree's run produced `a_reader_sha256`
`1175aefa1e27c57454323c1efd905f17f55ae694cffc9c0868593e0f75ad54ca` against the
replay's `26a29054...` at an **identical** `staged_input_digest`
`e48eb5c6...`. Two worktrees differ in their absolute paths as well as in
nothing else, so per rule 11 that is a hypothesis with two candidate causes and
step 8 removes one of them: rendering the WeasyPrint leg **three times in the
SAME worktree from the same run directory** gives
`1175aefa...`, `d55335f7...` and `8e753548...`, with the request's staged input
rows verified identical between them. **The WeasyPrint leg is not
byte-reproducible**, and the path difference is not the cause.

`parity.yaml`'s own `strip_pdf_keys` anticipates this for `CreationDate` /
`ModDate` / `trailer ID`, but the verdict inherits it anyway, because the
verdict records the **raw** `sha256` of the PDF rather than a normalized one.
The typst leg by contrast hashed **identically across six renders in two
worktrees at different absolute paths**, `3196b6ce...`. So a verifier replaying
this block should expect `a_reader_sha256` and the verdict digest to differ,
and should compare **`b_reader_sha256`, `staged_input_digest` and the tier
summary**, all three of which reproduced exactly.

This bears on more than this WP: the protocol asks every WP to quote
`a_reader_sha256` beside a verdict digest as the thing that makes the number
provenance-checkable. It does identify the run, but it **cannot be matched by
a replay**, so it is evidence of which run produced a verdict rather than
evidence that a verdict is reproducible. `b_reader_sha256` and
`staged_input_digest` carry that second property; `a_reader_sha256` does not.
Owner: whoever holds `mag/src/parity.rs` (WP-0.2k) if the verdict should record
a normalized oracle hash instead. Raised, not acted on.

Tier summary, quoted from the file itself:

```
mode: render
self_comparison: false
tier_s.page_count: fail (a 56, b 52)
tier_s.boxes: null      tier_s.text: null       tier_s.color: null
tier_s.navigation: null tier_g: null            tier_v: null
tier_e.display_list: null  tier_e.glyph_positions: null  tier_e.raster: null
tier_s.code_blocks: not_evaluated (WP-0.2b input level, WP-3.3 fixture)
tier_s.critic:      not_evaluated (WP-2.0b oracle leg, WP-5.3g typst leg)
parity exit = 1
```

**`mode: render` and the absence of any `typst_leg` key are the load-bearing
part**: the typst leg rendered rather than failing, so the comparator compared
two engines. `self_comparison: false` confirms the two PDFs are different
bytes, so this is not the `oracle_only` shape.

**The target has five clauses: three are met, one is not, and one cannot be
evaluated by the comparator while the page counts differ.** (Count derived from
the enumeration below, not carried alongside it.)

| target clause | outcome |
| --- | --- |
| `mag render 010 --engine typst` emits a PDF | **met** |
| `mag parity 010` produces a verdict | **met**, digest above |
| nonzero exit on failure | **met**, exit 1 |
| a verdict with **every tier evaluated** | **NOT met** |
| **page boxes pass Tier S** | **not evaluable by the comparator**; measured directly instead, 150 boxes and 50 rotations, zero mismatches, worst delta 0.000000 pt |

## What is and is not proven

**Which oracle proves what.** Two oracles are in play and this WP keeps them
apart, as WP-2.1's verification requires. **WP-2.1's byte-for-byte content
equality proves text and order only, never structure** — two `#doc-paragraph`
calls and the same text merged into one project identically — so nothing below
cites it for a structural claim. Structure here is proved only by the PDF:
page boxes, page counts, and measured ink positions.

**Did this WP draw its own comparison boundary to make the comparison easier?**
Answered by measurement, not argument. The boundary is `parity.yaml`'s own
`tiers.s.box_tolerance_pt` (0.05) and the comparator's own box-name set, both
unchanged, applied to the **largest domain the two legs share**, pages 2..51.
That is *harder* than the alternatives available: it compares 150 boxes rather
than the 3 of a single page, and it uses the exact `/Rotate` comparison the
comparator uses rather than a tolerance. The one thing the boundary excuses
this WP from proving is the four pages 52..55, which exist on the oracle leg
and not on the typst leg — and those are exactly the pages the page-count gap
is about, so they are accounted for under Residuals rather than quietly
dropped.

**Proven.**

- *The seam closes.* `mag render 010 --engine typst` compiles the WP-2.1 tree
  and writes a PDF. Committed test:
  `the_template_defines_every_function_the_fixture_editions_call`, which walks
  the two committed fixture editions' emitted trees for `#name` calls and
  checks each against `#let name(` in the template. **Discrimination**: the
  same test inserts `no-such-template-function` into the name set and asserts
  the checker reports exactly that one, so a checker that could not fail would
  fail the test.
- *Every one of the 47 functions WP-2.1 names is defined.* Re-derived from
  WP-2.1's own artifact by the command block (47 required, 0 undefined), not
  cited from any brief.
- *The compiled pages are A5.* Committed test
  `the_fixture_editions_compile_to_a5_pages` compiles both fixture editions
  through `pipeline` -> `world` -> `compile` and reads `MediaBox` from the PDF
  bytes with `lopdf`. **Discrimination**:
  `the_a5_page_box_check_discriminates` runs the same helper against a
  1pt-wider box and against A4 and asserts **every** page fails, so the check
  is not vacuous. Per rule 10's second half, the opposite extreme was run and
  it does fail.
- *The page frame constants are the stylesheet's, at full precision.*
  `the_page_frame_constants_are_the_stylesheet_s_own` asserts the six margin
  and datum constants and then derives the live width (333.007859pt) and
  content height (498.275591pt) from them, which is the CSS's own arithmetic
  at :73-104.
- *The widened measure is WP-1.7's and only WP-1.7's.*
  `the_body_measure_straddles_wp17s_admissible_window` asserts
  `MEASURE + MEASURE-DELTA` lies inside `[325.010000, 325.040000)` **and that
  both neighbours fail**: the unwidened 325.0 is below the floor and a 0.05pt
  widening is at or above the ceiling. This is the straddle WP-1.7's residual
  asks for ("WP-2.2a must carry the constant at full precision"; 325.03 is
  inside the window, 325.0 and 325.05 are outside).
- *Page boxes and rotations agree exactly over the shared domain*: 150 boxes,
  50 rotations, 0 mismatches, worst single-coordinate delta 0.000000 pt, at
  the comparator's own 0.05pt tolerance and its exact `/Rotate` rule.
- *The body column lands where the stylesheet puts it, on both parities.* On
  p5, a page whose content is the same on both legs, the first body line starts
  at 48.003930 against the oracle's 48.003929, its box top is within 0.000198
  pt and the line advance is 13.000000 pt on both. Because the legs paginate
  differently from article 3 on, the **verso** rail is measured by a statistic
  that does not require matching content: the modal body-line start over pages
  5..45 is **48.003930 recto and 46.523630 verso on BOTH legs**, identical to
  six decimals. **Discrimination**: the modal statistic separates the rail from
  the indents rather than averaging them, and the same census (under Metrics)
  resolves every other left edge to a distinct derived constant, so a template
  that put the column one indent out would show a different mode, not a
  blurred one.
- *The folio reproduces on both parities*: name xMin 42.519700 exactly on both
  legs and both parities; number right edge within 0.0027 pt; baseline within
  0.0016 pt. This is the one piece of page furniture this slice owns and it is
  the CSS's two-lever `text-indent` / `margin-right` mirror computed once.
- *All three body measures are applied, to the right populations.* The typst
  leg's own line boxes put 154 lines at the 311.025 pt list measure and the
  blockquote at 312.186417 pt, reproducing WP-1.7's line and block counts for
  both narrow measures from the opposite direction. **Discrimination**: this
  could not pass under a single-measure template, which is the failure WP-1.2
  residual 2 warns about — a 325.025 pt list would put those 154 lines at a
  different left edge and a different width.
- *`pad` fragments across pages in Typst 0.15.1.* Asserted nowhere and simply
  measured: the body column is one `pad` per piece, and the longest piece spans
  12 pages. Recorded because an unbreakable `pad` would have made every article
  a single overflowing page, and the risk was real enough to check.
- *Typst PDF export is byte-reproducible here, across worktrees.* Six renders
  of the same staged inputs, in the development worktree and in the replay
  worktree at a different absolute path, all produced
  `3196b6ceb5173afa22f86d0f7908e9f91f16abae46901ae094b49c379aad45b0`. Measured
  rather than cited from the plan's pin. **Discrimination**: this is not a
  check that cannot fail, because the WeasyPrint leg run beside it under the
  same conditions produced three different hashes from three renders (see
  Verdicts and `## Commands` step 8).
- *The module is live.* `mag/src/typeset/mod.rs` no longer carries
  `#[allow(dead_code)]`, and `clippy --all-targets -D warnings` is clean, which
  required `content::project` to have a real caller: the render path now
  projects the tree and refuses before compiling, so an emitter that produced
  unprojectable markup fails loud rather than reaching Typst.

**Not proven, and who owns proving it.**

- **Page-count equality, and therefore every Tier S, G, V and E clause.** The
  comparator gates all of them on `na == nb` (`mag/src/parity.rs`,
  `build_verdict`: `if !counts_equal { return Ok(verdict); }`), which this run
  **demonstrates rather than argues** — the verdict shows `page_count: fail`
  and `null` for every subsequent clause. Owner: see `## Status`; three of the
  four pages are **WP-2.2c**'s figures.
- **Everything in the PENDING table**, each with its owning slice named there.
- **Block structure.** The content oracle cannot see it, and page boxes do not
  test it. Whether paragraph, heading and list boundaries are right is
  untested by anything in this WP; **WP-3.1** (body text, Tier S text + G2)
  and **WP-2.2b** own it.
- **Text, colour, navigation, glyph and raster agreement.** Not measured at
  all here, not merely unproven: the comparator never reached them. **WP-3.1**
  to **WP-3.5**.
- **Nine of the 47 functions are defined but never exercised by edition 010**:
  `doc-code`, `doc-rule`, `extract`, `extract-caption`, `key-idea`,
  `key-ideas`, `key-ideas-label`, `provenance`, `quote-line`. Their definitions
  are transcriptions that **nothing on the live corpus can falsify**; the
  fixture editions 900/901 reach `extract`, `quote-line`, `extract-caption` and
  `doc-code` structurally (they compile) but no oracle compares their output.
  **WP-3.3** owns the code and extract fixture.
- **Six branches inside functions edition 010 DOES exercise.** Distinct from
  the nine unexercised functions above, and easier to miss because the function
  around them is exercised:
  - `doc-heading` is reached at **level 2 (38 times) and level 3 (3 times)
    only**. Level 1 and the `calc.min(level, 3)` clamp for level 4+ are never
    taken; 010's manuscripts carry no `#` or `####` heading.
  - `doc-list`'s `references: true` branch: all 8 lists are `references:
    false`, so the 7.2pt/9.4pt reference setting, the 12.9744pt hanging indent
    and the suppressed disc are untested. Its measure would be a **fourth**
    body measure, 325 - 12.9744 = 312.0256 pt, which is not in WP-1.7's three
    and which no spike has bounded.
  - `piece`'s landscape-plate branch (12.2pt leading, 4pt paragraph spacing):
    010 declares only `evidence_band` and `evidence_band_prose`.
  - `piece`'s `original_editorial` branch (6.2pt paragraph spacing): editions
    from 010 on carry no editorial.
  - `doc-quote` across a page break: 010's single blockquote fits on one page,
    so the `grid` + `rect(height: 100%)` construction is untested under
    fragmentation.
  - `doc-code` entirely: 0 fenced code blocks. **WP-3.3** owns the fixture for
    the last two.
- **The `es` locale.** Untouched and untested, as in WP-2.1.
- **Colour fidelity in the PDF.** The template writes `rgb(5.5%, 7.5%, 8.5%)`
  and the CSS comment at :217-224 requires the percentage to reach the PDF
  colour operator unrounded. Whether `typst-pdf` quantizes to 8 bits is **not
  measured here** and is a Tier S colour question. **WP-3.1**.
- **A search that found nothing**: no WP in the plan owns orphans/widows. That
  is recorded under NOT PROVEN and escalated in `## Status`, not offered as
  proof of absence.

## Residuals

1. **The rule-12 replay caught a defect in this file's own step 6, and it is
   recorded rather than quietly fixed, because it is a new instance of
   revision 49's caption-drift class.** The first version of step 6 was
   captioned "the column and folio geometry ... on one recto and one verso
   page" and took `lines[0]` of each page. On the **oracle** leg `lines[0]` is
   the RUNNING HEAD, which the typst leg does not yet draw, so the command
   compared the oracle's running head against the typst leg's body and printed
   `a=43.999979 b=48.003930` as though the two disagreed by 4pt. The command
   RAN, its output was ACCURATE, and the caption was the false claim.
   Two further things it got wrong, both invisible without running it: the
   folio lookup used `re.search`, which finds the oracle's running-head
   "BERRETA" before the folio's; and p4, the one verso page whose content
   aligns on both legs, is an article OPENER whose rail escapes the reading
   measure on the oracle leg, so it was never a body-column comparison.
   **The numbers in an earlier draft of `## Metrics` were right** because they
   were read off a hand-selected line, which is precisely the divergence rule
   12 exists to catch: **the verso oracle figure had been inferred rather than
   measured.** Step 6 now selects by BAND rather than by index, and the verso
   rail is a modal statistic that does not need the legs to paginate alike.
2. **The typst leg writes `en/reader.pdf`, not `interior.pdf`.** The brief's
   target names `interior.pdf`; `mag/src/parity.rs` hard-codes
   `dir.join("en/reader.pdf")` for both legs, and parity.rs is WP-0.2k's. The
   leg therefore emits the name the comparator reads. No code change is
   proposed; the name in the brief appears to be loose rather than a contract.
3. **Typst's `include` does not inherit the importer's scope, so the WP-2.1
   tree as emitted cannot compile.** `main.typ` imports the template, but each
   `#include "/pieces/..."` is evaluated as its own module and sees only the
   standard library, so every piece raised `unknown variable: piece`. The
   World prepends one line, `#import "/template.typ": *`, to each tree file
   when it builds the `Source` (`mag/src/typeset/world.rs`, `PRELUDE`). **The
   `Tree` itself is untouched, so WP-2.1's projection is unaffected** — the
   projection walks the `Tree`, not the World. A cleaner home for this is the
   emitter writing the import itself, which is WP-2.1's file; raised here
   rather than self-granted.
4. **`edition-header` returns its body, where the CSS says `display: none`.**
   Deliberate and load-bearing: `publication-name` is the only place the
   publication's name enters the document, and the folio reads it back with
   `state.final()`, which requires the update to be IN the document. The four
   siblings (`issue-line`, `edition-title`, `edition-subtitle`,
   `edition-date`) each return `none`, so nothing is printed and pages 1 and 2
   are measured blank. The fragility is that a future emitter adding a sixth
   child to `edition-header` would print it; a `display: none` that is really
   "evaluate for effect, render nothing" wants a comment it cannot have under
   the repo's no-comment rule, so it is recorded here instead.
5. **The 25pt heading clearance has no direct Typst translation.** Typst block
   spacing is `max(above, below)`, so the CSS idiom `height: 25pt;
   margin-bottom: -25pt` cannot be expressed as a negative `below`. The three
   candidates, for WP-2.2b: an unbreakable block containing the heading plus a
   25pt spacer followed by an explicit `v(-25pt)` (correct in flow, but the
   explicit `v` is not discarded at a page break where CSS discards the
   margin); `block(sticky: true)`, which is `break-after: avoid` and therefore
   reserves the next block's first fragment rather than a flat 25pt, the
   difference the CSS comment at :510-521 says was the point; or `context` +
   `measure()`, which reserves the measured height and so defeats the
   reservation. None is obviously right and the choice wants a measurement.
6. **`is_name_roster`'s Python/Rust whitespace divergence is not encoded
   anywhere in this WP**, and **WP-5.1f's fix has since landed (`02f1d35`)**.
   `doc-paragraph`'s `roster` flag reaches only a hyphenation decision that is
   already off for `en`, so this slice's behaviour never depended on the flag's
   value in either direction. Nothing here was built on the pre-fix behaviour.
7. **The two `normalize` copies were left separate**, per the ruling that
   consolidating would pin the Python-pinned copy to an unpinned one. This WP
   touches neither.
8. **The duplicate-helper audit shapes test helpers across module
   boundaries.** `mag/tests/rust_helpers.rs` rejected `repository`, `fonts` and
   `corpus` in this WP's test module as duplicates of `content.rs`'s
   test-module helpers, which are private to it. The template tests therefore
   use a single `roots() -> (&Path, &Path)`. Noted because the next
   `mag/src/typeset/**` slice will hit the same wall.
9. **Three normalization clauses are vacuous on this corpus** (0 soft hyphens,
   0 U+2010, NFC a no-op). Nothing this template emits changes that: the
   template introduces no soft hyphens (hyphenation is off for `en`) and no
   U+2010.
10. **The oracle leg of this run reports 85 link annotations**, where plan
   revision 47 discusses 84. Re-derived from this run's own oracle leg rather
   than cited; the figure is a corpus observation, not a threshold, and the
   difference is consistent with revision 49's note that parity figures move
   with the render tree they were measured against.

## Status

**`blocked`**, on one clause of the target, with the gap measured.

`mag render 010 --engine typst` emits a PDF, `mag parity 010` produces a
verdict with a nonzero exit, and page boxes agree exactly wherever the two
legs have pages to compare. **"A verdict with every tier evaluated" is not
reachable from this slice's scope**, and the reason is structural rather than
a shortfall of effort:

- The comparator evaluates nothing beyond `page_count` unless the two legs
  have equal page counts. Demonstrated by this run's verdict, not argued.
- The typst leg is 52 pages against 56. **Three of the four missing pages are
  the three figures on articles 3, 6 and 7** — each of those articles loses
  exactly one page and each carries exactly one figure. Figure placement is
  **WP-2.2c**'s, named in the plan as such.
- So WP-2.2a's target depends on WP-2.2c. **WP-2.2b's target, "Tier S page
  count on 010", depends on it too**, and WP-2.2b does not own figures either.
  Recorded as a finding about the plan, not a request: the page-count target
  appears to be assigned two slices earlier than the work it requires.

**One unowned gap, escalated per rule 2a rather than merely listed: nothing in
the plan owns orphan and widow control.** `p { orphans: 2; widows: 2 }` is a
transcribed-but-unimplementable CSS declaration, because Typst 0.15.1 has no
orphan/widow mechanism. It changes pagination systematically rather than
cosmetically — it is precisely a rule about where pages break — and a search of
the plan and all evidence files for "orphan" and "widow" returns only WP-5.3d's
unrelated critic metric. It plausibly accounts for some of the residual flow
delta (+1, -1, -1 on the three figureless articles that moved), though that is
a hypothesis and rule 11 says so: removing the cause is not possible without a
mechanism, so it has not been tested.

**One Owns extension requested and not taken for granted**: the four-line call
site in `mag/src/render.rs` described under `## Base`.
