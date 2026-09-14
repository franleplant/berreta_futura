# WP-1.7 the safe body-measure interval

## Base

`6e8abb8` (art_directed; plan revision 10 at `6c13738`, WP-0.0c at `6e8abb8`).
Measured under the tracked CSS **after** WP-1.5 (`5504e5a`), i.e. English
prose hyphenation off via the `html:lang(en)` block at
`src/magazine/assets/weasyprint-a5.css:680-688`. Renders predating `5504e5a`
are not comparable.

## Summary

Widening the Typst body column compensates the one-sided advance drift
WP-1.6 measured (WeasyPrint breaks on integer 1/1024 px Pango units, Typst
sums exact font units). The safe interval is the set of column widths that
reproduces WeasyPrint's break set EXACTLY: wide enough that every line
WeasyPrint kept still fits, narrow enough that no line pulls its next unit
up.

- lower bound = max over lines of `measure(line)`
- upper bound = min over lines of `measure(line + " " + next breakable unit)`, exclusive

**No interval is empty. A single widening constant serves all three
measures: delta in [+0.010000, +0.040000) pt, recommended +0.025000 pt.**

## Metrics

Population: the 149 `p` blocks of edition 010 (968 lines), the same
population WP-1.2 compared. The 6 `span` blocks (6.8 pt, 444.0107 px) are
not body paragraphs and are excluded, as in WP-1.2.

| measure | blocks | lines | lower bound (binding line) | upper bound (binding line) | interval | midpoint |
|---|---|---|---|---|---|---|
| 325.0000 pt | 124 | 812 | **325.010000** (block 135 line 0) | **325.040000** (block 137 line 1) | 0.030000 pt | 325.025000 |
| 311.0000 pt | 24 | 154 | 310.640000 (block 46 line 8) | 311.200000 (block 58 line 7) | 0.560000 pt | 310.920000 |
| 312.1614 pt | 1 | 2 | 302.140000 (block 3 line 0) | 323.510000 (block 3 line 0) | 21.370000 pt | 312.825000 |

The 325 pt lower bound reproduces WP-1.6's independently measured
325.010000 for block 135 line 0 exactly.

### One constant or three

As deltas from each base measure:

| measure | admissible delta |
|---|---|
| 325.0000 | [+0.010000, +0.040000) |
| 311.0000 | [-0.360000, +0.200000) |
| 312.1614 | [-10.021400, +11.348600) |

Intersection: **[+0.010000, +0.040000)**, set entirely by the 325 pt group.
One constant serves all three; the template needs one number, not three.
Recommended **delta = +0.025000 pt**, the midpoint of the intersection:
325.025000, 311.025000, 312.186400.

A midpoint rather than an edge because the binding interval is only
0.030000 pt wide and both edges are live: +0.005 and +0.045 each break a
real line (below). The midpoint leaves 0.015000 pt of clearance on each
side.

### Empirical confirmation (the Verify clause)

Both engines rendered per measure group, breaks compared block by block.
Comparison is space-insensitive to neutralize a `pdftotext` word
segmentation artifact at font changes (block 4 only; all 12 of its lines are
space-insensitively identical at every delta, and WP-1.2 recorded the same
artifact).

| delta | paragraphs | lines | outcome |
|---|---|---|---|
| +0.000 | 147/149 | 962/968 | block 135 breaks early (WP-1.2's known miss) |
| +0.005 | 147/149 | 962/968 | below lower bound: block 135 still breaks early |
| +0.010 | **149/149** | **968/968** | lower bound reached |
| +0.025 | **149/149** | **968/968** | **recommended midpoint** |
| +0.039 | **149/149** | **968/968** | just inside upper bound |
| +0.045 | 147/149 | 963/968 | above upper bound: block 137 pulls "cost" up |

Restricted to the 122 unstyled blocks (the pure-body subset, 698 lines) at
delta +0.025: **698/698 lines identical, zero divergent blocks**.

The plan's Verify clause names "899/899 body lines". That 899 is WP-1.6's
filter (single-run regular 10 pt lines, which includes single-run lines
inside otherwise styled blocks). This spike scores the wider WP-1.2
population instead: 149 paragraphs / 968 lines, which strictly contains both
WP-1.6's 899 and the 698 unstyled subset, and reports 968/968.

## Commands

Inputs reused rather than re-derived: `wp12-weasy-runs.json` (WP-1.2's
per-run line dump, sha256 `e4ab672cefe221d06d2df1237e7663761a1e7c2f4311cb6d0d6a4f8581a7ac41`).
Their validity under today's tracked CSS was re-established rather than
assumed, see "Input revalidation" below.

Font family mapping (WeasyPrint alias to real family, per parity.yaml
`font_name_map`): Magazine Serif -> Source Serif 4 SmText, Magazine Sans ->
Inter, Magazine Mono -> Geist Mono.

### 1. Generate the Typst measurements

```python
import json

FAM = {"Magazine Serif": "Source Serif 4 SmText", "Magazine Sans": "Inter", "Magazine Mono": "Geist Mono"}
PX2PT = 0.75
NOBREAK = "\u00a0\u202f\u2007\u2011\u2060"
AFTER = "-\u2013\u2014/"

def breakable_space(ch):
    return ch.isspace() and ch not in NOBREAK

def esc(s):
    return s.replace("\\", "\\\\").replace('"', '\\"')

def runexpr(run, text):
    parts = ['font: "%s"' % FAM[run["family"]], "size: %gpt" % round(run["size"] * PX2PT, 3), "weight: %s" % run["weight"]]
    if run["style"] == "italic":
        parts.append('style: "italic"')
    return 'text(%s, "%s")' % (", ".join(parts), esc(text))

def content(runs):
    return " + ".join(runexpr(r, r["text"]) for r in runs if r["text"] != "")

def prefix(runs, tight):
    out, taken = [], 0
    for r in runs:
        t = r["text"]
        cut = len(t)
        for i, ch in enumerate(t):
            if breakable_space(ch):
                cut = i
                break
            if tight and ch in AFTER and taken + i + 1 < sum(len(x["text"]) for x in runs):
                cut = i + 1
                break
        if cut > 0:
            out.append(dict(r, text=t[:cut]))
        if cut < len(t):
            return out
        taken += len(t)
    return out

blocks = json.load(open("wp12-weasy-runs.json"))
items = []
for key, b in blocks.items():
    if b["tag"] != "p":
        continue
    measure = round(b["width"] * PX2PT, 4)
    lines = b["runs"]
    for i, raw in enumerate(lines):
        runs = [r for r in raw if r["text"] != ""]
        if not runs:
            continue
        items.append(("%s:%d:self" % (key, i), measure, content(runs)))
        if i + 1 < len(lines):
            nxt = [r for r in lines[i + 1] if r["text"] != ""]
            sep = dict(runs[-1], text=" ")
            for tag, tight in (("nextw", False), ("nextu", True)):
                unit = prefix(nxt, tight)
                if unit:
                    items.append(("%s:%d:%s" % (key, i, tag), measure, content(runs + [sep] + unit)))

with open("wp17-measure2.typ", "w", encoding="utf-8") as fh:
    fh.write('#set page(width: 4000pt, height: 30pt, margin: 0pt)\n#set text(hyphenate: false)\n#context {\n')
    for ident, measure, expr in items:
        fh.write('  [#metadata((id: "%s", m: %.4f, w: measure(%s).width.pt()))<r>]\n' % (ident, measure, expr))
    fh.write('}\n')
print("items", len(items))
```

```sh
T=/Users/franguijarro/.claude/jobs/7d99e27f/tmp
cd $T && python3 wp17_gen2.py
$T/typst-install/bin/typst query \
  --font-path /Users/franguijarro/code/magazine/src/magazine/assets/fonts \
  --field value wp17-measure2.typ '<r>' > wp17-measures2.json
```

`wp17-measures2.json` sha256
`e96f68d8f055bad5405f329d2b0582c789b81876dd186eaa2c16285e46ee7440`, 2606
measurements (968 self, 819 whole-word next, 819 tight-unit next).

Break opportunities are modelled explicitly, and this matters: a first
attempt splitting the next unit on `str.isspace()` produced impossible
upper bounds (293.30 pt at a 311 pt column), because the adapter binds a
paragraph's last two words with U+00A0. Non-breaking characters
(U+00A0, U+202F, U+2007, U+2011, U+2060) are therefore excluded from the
split. A tight variant additionally breaks after `-`, en dash, em dash and
`/`. Both variants selected the same binding candidate at every measure, so
the upper bound does not depend on that choice.

### 2. Compute the intervals

```sh
cd $T && python3 -c "
import json, collections
d = json.load(open('wp17-measures2.json'))
by = collections.defaultdict(lambda: collections.defaultdict(list))
for r in d:
    key, idx, kind = r['id'].split(':')
    by[r['m']][kind].append((r['w'], key, int(idx)))
for m in sorted(by):
    lo = max(by[m]['self']); up = min(by[m]['nextu'])
    print('%.4f lower %.6f (%s:%d) upper %.6f (%s:%d) width %.6f' % (
        m, lo[0], lo[1], lo[2], up[0], up[1], up[2], up[0]-lo[0]))
"
```

### 3. Verify by rendering both engines and comparing break sets

```python
import json
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

TMP = Path("/Users/franguijarro/.claude/jobs/7d99e27f/tmp")
TYPST = TMP / "typst-install/bin/typst"
FONTS = Path("/Users/franguijarro/code/magazine/src/magazine/assets/fonts")
PX_TO_PT = 0.75
FAMILY = {
    "Magazine Serif": "Source Serif 4 SmText",
    "Magazine Sans": "Inter",
    "Magazine Mono": "Geist Mono",
    "Magazine Serif Display": "Source Serif 4 Display",
}

dump = json.loads((TMP / "wp12-weasy-runs.json").read_text())

blocks = []
for key, b in sorted(dump.items(), key=lambda kv: int(kv[0])):
    if b["tag"] != "p" or "runs" not in b:
        continue
    lines = [ln.strip() for ln in b["lines"]]
    if not all(lines):
        continue
    flat = [r for line in b["runs"] for r in line]
    if not flat:
        continue
    if False:
        continue
    runs = []
    for i, line in enumerate(b["runs"]):
        for r in line:
            runs.append(
                {
                    "text": r["text"],
                    "weight": int(r["weight"]), "font": FAMILY[r["family"]], "size": round(r["size"] * PX_TO_PT, 4),
                    "style": r["style"],
                }
            )
        if i < len(b["runs"]) - 1 and runs:
            runs[-1] = {**runs[-1], "text": runs[-1]["text"].rstrip() + " "}
    merged = []
    for r in runs:
        if merged and merged[-1]["weight"] == r["weight"] and merged[-1]["style"] == r["style"] and merged[-1]["font"] == r["font"] and merged[-1]["size"] == r["size"]:
            merged[-1] = {**merged[-1], "text": merged[-1]["text"] + r["text"]}
        else:
            merged.append(dict(r))
    blocks.append(
        {
            "key": key,
            "width_pt": round(b["width"] * PX_TO_PT, 4),
            "size_pt": round(b["font_size"] * PX_TO_PT, 4),
            "lines": lines,
            "runs": merged,
            "styled": any(r["weight"] != 400 or r["style"] != "normal" for r in merged),
        }
    )

DELTA = float(sys.argv[1]) if len(sys.argv) > 1 else 0.0
widths = sorted({b["width_pt"] for b in blocks})
print("blocks:", len(blocks), "styled:", sum(b["styled"] for b in blocks), "widths:", widths, file=sys.stderr)

results = {}
for w in widths:
    group = [b for b in blocks if b["width_pt"] == w]
    size = group[0]["size_pt"]
    tag = str(round(w + DELTA, 6)).replace(".", "_")
    data_path = TMP / f"wp17v-paras-{tag}.json"
    data_path.write_text(json.dumps([{"runs": b["runs"]} for b in group], ensure_ascii=False))
    typ = f"""#set page(width: {round(w + DELTA, 6)}pt, height: auto, margin: 0pt)
#set text(font: "{FAMILY["Magazine Serif"]}", size: {size}pt, hyphenate: false, lang: "en")
#set par(linebreaks: "simple", justify: false, leading: 3.5pt, spacing: 0pt)
#let data = json("{data_path.name}")
#for item in data {{
  {{
    for r in item.runs {{
      text(font: r.font, size: r.size * 1pt, weight: r.weight, style: r.style, r.text)
    }}
  }}
  pagebreak(weak: true)
}}
"""
    typ_path = TMP / f"wp17v-{tag}.typ"
    typ_path.write_text(typ)
    pdf_path = TMP / f"wp17v-{tag}.pdf"
    subprocess.run(
        [str(TYPST), "compile", "--font-path", str(FONTS), str(typ_path), str(pdf_path)],
        check=True,
    )
    xml_path = TMP / f"wp17v-{tag}.xml"
    subprocess.run(["pdftotext", "-bbox-layout", str(pdf_path), str(xml_path)], check=True)
    nsx = "{http://www.w3.org/1999/xhtml}"
    pages = []
    for page in ET.parse(xml_path).getroot().iter(f"{nsx}page"):
        lines = []
        for line in page.iter(f"{nsx}line"):
            words = [wd.text or "" for wd in line.iter(f"{nsx}word")]
            if words:
                lines.append(" ".join(words))
        if lines:
            pages.append(lines)
    results[w] = (group, pages)


def norm(seq):
    return [" ".join(s.replace(" ", " ").split()) for s in seq]


total = matched = 0
line_total = line_matched = 0
misses = []
for w, (group, pages) in results.items():
    if len(pages) != len(group):
        print(f"PAGE COUNT MISMATCH w={w}: typst {len(pages)} vs weasy {len(group)}", file=sys.stderr)
    for b, tlines in zip(group, pages):
        total += 1
        a, c = norm(b["lines"]), norm(tlines)
        line_total += len(a)
        line_matched += sum(1 for x, y in zip(a, c) if x == y)
        if a == c:
            matched += 1
        else:
            misses.append({"key": b["key"], "width": w, "styled": b["styled"], "weasy": a, "typst": c})

print(f"PARAGRAPHS: {matched}/{total} identical ({100.0 * matched / total:.2f}%)")
print(f"LINES: {line_matched}/{line_total} identical ({100.0 * line_matched / line_total:.2f}%)")
print(f"MISSES: {len(misses)}  (styled among them: {sum(m['styled'] for m in misses)})")
(TMP / "wp17v-misses.json").write_text(json.dumps(misses, ensure_ascii=False, indent=1))
for m in misses:
    print(f"\n--- block {m['key']} w={m['width']}pt styled={m['styled']} weasy {len(m['weasy'])} / typst {len(m['typst'])} lines")
    for i in range(max(len(m["weasy"]), len(m["typst"]))):
        x = m["weasy"][i] if i < len(m["weasy"]) else "<none>"
        y = m["typst"][i] if i < len(m["typst"]) else "<none>"
        if x != y:
            print(f"  L{i} W: ...{x[-58:]!r}")
            print(f"  L{i} T: ...{y[-58:]!r}")
            break
```

```sh
cd $T && for d in 0 0.005 0.010 0.025 0.039 0.045; do
  echo "delta=$d"; python3 wp17_verify.py $d 2>/dev/null | head -3
done
```

### 4. Input revalidation (fresh render at Base)

The measurement inputs came from dumps produced while WP-1.2 and WP-1.6 held
an uncommitted hyphenation switch; WP-1.5 has since landed a differently
scoped one (`html:lang(en)`), so the dumps were revalidated against a fresh
render at `6e8abb8` rather than trusted:

```sh
T=/Users/franguijarro/.claude/jobs/7d99e27f/tmp
git -C /Users/franguijarro/code/magazine worktree add $T/spike-wp17 HEAD
cp -R /Users/franguijarro/code/magazine/editions/010/run-2026-09-13T01-34-51 \
      $T/spike-wp17/editions/010/
# uncommitted instrumentation in the worktree only: add
#   _dump_line_widths(document)
# after _report_hyphen_ladders(document, edition) in
# src/magazine/weasyprint_adapter.py, and define above _walk_boxes:
#   def _dump_line_widths(document):   # writes {block: {tag, block_width_pt,
#       ...                            #   lines: [{text, line_width_pt}]}}
#       target = os.environ.get("MAG_WIDTH_DUMP") ...
# (verbatim body is WP-1.6's, meta/verification/evidence/WP-1.6.md)
cd $T/spike-wp17 && MAG_WIDTH_DUMP=$T/wp17-weasy-verify.json \
  /Users/franguijarro/code/magazine/mag/target/debug/mag render 010 \
  --no-model --run editions/010/run-2026-09-13T01-34-51
cd $T && python3 -c "
import json
old = json.load(open('wp12-weasy-runs.json')); new = json.load(open('wp17-weasy-verify.json'))
p = [k for k, b in old.items() if b['tag'] == 'p']
print('line sets differing:', [k for k in p if [l.strip() for l in old[k]['lines']] != [l['text'].strip() for l in new[k]['lines']]])
print('measures differing:', [k for k in p if abs(round(old[k]['width']*0.75,4) - round(float(new[k]['block_width_pt']),4)) > 1e-6])
"
git -C /Users/franguijarro/code/magazine worktree remove --force $T/spike-wp17
```

Result: **zero** of the 149 `p` blocks differ in line set or in measure.
`wp17-weasy-verify.json` sha256
`3ace3c2d4d644bf10ee0680159318ba31a560d740bff20fef8234d97d11a7abf`.

## Tool versions

- typst 0.15.1 (the pin WP-1.4 established), invoked as the standalone CLI
  from `$T/typst-install/bin/typst`
- poppler 25.08.0 (`pdftotext -bbox-layout`)
- python 3.12.11, weasyprint 69.0 (render leg, via the repo's debug `mag`)
- fonts: the vendored faces at `src/magazine/assets/fonts`, resolved by
  typst as Source Serif 4 SmText, Source Serif 4 Display, Inter, Geist Mono,
  Archivo

## Verdicts

No `verdict.json`: this is a Phase 1 spike and runs no comparator. The
binding artifacts are the two digests above plus the interval table.

## Residuals

- **The recommended number is 325.025000 pt and it needs three decimals.**
  The admissible window is 0.030000 pt wide; 325.03 is inside it, 325.0 and
  325.05 are outside. WP-2.2a must carry the constant at full precision and
  cite this WP, not round it.
- The 312.1614 pt group is a single block of two lines, so its wide interval
  is an artifact of a small sample, not slack that can be relied on. A future
  edition with more content at that measure could bind it much harder. The
  recommended constant sits comfortably inside it either way.
- The upper bound is the first width at which a line pulls its next unit up;
  it is exclusive. +0.040000 itself is NOT safe.
- This compensation is measured against WeasyPrint with English hyphenation
  off. If WP-4.3 re-enables hyphenation, or if the Typst template ever
  enables it for English, the interval must be re-measured: the break set it
  reproduces would be a different one.
- Post-flip the compensation exists only to match an engine that will have
  been deleted. Returning the body column to exactly 325 pt belongs with
  WP-4.3, as revision 10 records.
- The `pdftotext` word-segmentation artifact at font changes (block 4) makes
  a naive string comparison report a false miss on styled paragraphs. Any
  later WP comparing break sets through `pdftotext` should compare
  space-insensitively or use a different instrument. WP-1.2 hit the same
  artifact.
- Typst was driven through the standalone CLI here, not the embedded crates
  WP-2.0a will pin. Both are 0.15.1, but the engine WP should re-confirm the
  constant once the real template exists, since template-level settings
  (leading, spacing, par settings) are not part of a `measure()` call.

## Status

`done`. Every interval is non-empty, a single constant serves all three
measures, and the recommended midpoint reproduces WeasyPrint's break set on
149/149 paragraphs and 968/968 lines, with both bounds confirmed by lines
that actually break outside them.
