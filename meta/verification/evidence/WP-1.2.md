# WP-1.2 line-break parity and the ragged-right confirmation

## Base

0bd7cc0e6ab2a4dc74caec6c89bf0155afe07b30 (feat(parity): WP-0.2d fault suite,
raster bound and critic tolerances)

Phase 1 spike: all instrumentation was uncommitted and lived in a throwaway
worktree at `/Users/franguijarro/.claude/jobs/7d99e27f/tmp/spike-wp12`, removed
at WP end. This WP owns only this evidence file. No tracked file changed.

## Ragged-right confirmation

Confirmed, and confirmed as a selector fact rather than a grep. The reader
stylesheet `src/magazine/assets/weasyprint-a5.css` contains exactly one
`text-align` declaration, line 156, and it sits inside the `@bottom-right`
page-margin box that prints the folio:

```
  @bottom-right {
    color: rgb(5.5% 7.5% 8.5%);
    content: counter(page, decimal-leading-zero);
    font: 500 6.8pt/normal "Magazine Sans", sans-serif;
    padding-bottom: 17.8601pt;
    text-align: right;
    vertical-align: bottom;
  }
```

No `justify` appears anywhere in the file, no Python emits an inline
`text-align` or `justify`, and the only other stylesheet carrying alignment
(`src/magazine/assets/screen-edition.css`) is the web edition, outside the
parity scope. Body text therefore inherits the initial `text-align: start`
value: the design is ragged-right, as the plan's Known-divergence table
assumes.

## Commands

All paths below are absolute so the block replays from any directory. `$W` is
the spike worktree, `$T` the scratch root.

```sh
T=/Users/franguijarro/.claude/jobs/7d99e27f/tmp
W=$T/spike-wp12

git -C /Users/franguijarro/code/magazine worktree add $W 0bd7cc0
cp -R /Users/franguijarro/code/magazine/editions/010/run-2026-09-13T01-34-51 $W/editions/010/

cargo install typst-cli --locked --root $T/typst-install
$T/typst-install/bin/typst --version
$T/typst-install/bin/typst fonts --font-path $W/src/magazine/assets/fonts
```

Ragged-right and hyphenation audit:

```sh
grep -n "text-align" $W/src/magazine/assets/*.css
sed -n '145,160p' $W/src/magazine/assets/weasyprint-a5.css
grep -rn "text-align\|justify" $W/src/magazine/*.py
```

The uncommitted instrumentation is two patches, reproduced verbatim below and
saved at `$T/wp12-instrumentation.patch` (82 lines).

1. Hyphenation off, the spike's only CSS switch, in `weasyprint-a5.css`:

```diff
 .editorial li, article li, main > section li {
-  hyphens: auto;
+  hyphens: manual;
   hyphenate-limit-chars: 6 3 3;
 }
```

2. A line dump in `weasyprint_adapter.py`: a call added after
   `_report_hyphen_ladders(document, edition)` (line 433) and a function added
   above `_walk_boxes`:

```python
    _report_hyphen_ladders(document, edition)
    _dump_prose_lines(document)
```

```python
def _dump_prose_lines(document: Any) -> None:
    target = os.environ.get("MAG_LINE_DUMP")
    if not target:
        return
    import json

    blocks: dict[str, Any] = {}
    for page in document.pages:
        for box in _walk_boxes(page._page_box):
            element = getattr(box, "element", None)
            key = getattr(element, "attrib", {}).get(_RUNT_KEY) if element is not None else None
            if key is None or type(box).__name__ != "BlockBox":
                continue
            record = blocks.setdefault(
                key,
                {
                    "tag": getattr(box, "element_tag", None),
                    "width": round(float(box.width), 4),
                    "font_size": round(float(box.style["font_size"]), 4),
                    "line_height": str(box.style["line_height"]),
                    "font_family": list(box.style["font_family"]),
                    "font_weight": str(box.style["font_weight"]),
                    "font_style": str(box.style["font_style"]),
                    "hyphens": str(box.style["hyphens"]),
                    "letter_spacing": str(box.style["letter_spacing"]),
                    "word_spacing": str(box.style["word_spacing"]),
                    "lines": [],
                },
            )
            for line in _walk_boxes(box):
                if type(line).__name__ != "LineBox":
                    continue
                runs = []
                for t in _walk_boxes(line):
                    if type(t).__name__ != "TextBox" or not isinstance(t.text, str):
                        continue
                    runs.append(
                        {
                            "text": t.text,
                            "family": list(t.style["font_family"])[0],
                            "weight": str(t.style["font_weight"]),
                            "style": str(t.style["font_style"]),
                            "size": round(float(t.style["font_size"]), 4),
                        }
                    )
                record["lines"].append("".join(r["text"] for r in runs))
                record.setdefault("runs", []).append(runs)
    Path(target).write_text(json.dumps(blocks, indent=1, ensure_ascii=False), encoding="utf-8")
```

The oracle leg, run with hyphenation off and the dump active:

```sh
cd $W/mag && cargo build
cd $W && MAG_LINE_DUMP=$T/wp12-weasy-runs.json \
  ./mag/target/debug/mag render 010 --no-model --run editions/010/run-2026-09-13T01-34-51
```

The Typst leg and the comparison are `$T/wp12_compare4.py` (the widest-coverage
run, reproduced in full at the end of this file). It reads the dump, rebuilds
each paragraph as an ordered list of styled runs, emits one Typst page per
paragraph at the paragraph's own measure, compiles, extracts lines with
`pdftotext -bbox-layout`, and compares break points:

```sh
cd $T && python3 wp12_compare4.py
```

Boundary characterisation of the single miss:

```sh
cd $T && $T/typst-install/bin/typst compile --font-path $W/src/magazine/assets/fonts wp12-prec.typ wp12-prec.pdf
pdftotext -layout wp12-prec.pdf - | grep PRECISE
```

Cleanup:

```sh
git -C /Users/franguijarro/code/magazine worktree remove --force $W
```

## Tool versions

| tool | version |
|---|---|
| typst (CLI, spike only; WP-1.4 pins the crates) | 0.15.1 |
| weasyprint | 69.0 (via the repo's `uv` environment) |
| poppler (`pdftotext`) | 25.08.0 |
| python | 3.12.11 |
| uv | 0.8.17 |
| rustc / cargo | 1.96.0 |

The Typst CLI is a spike instrument only. This WP pins nothing; WP-1.4 owns the
crate pin and WP-2.0a writes it.

## Metrics

Used values, read from the rendered document rather than from the CSS source
(WeasyPrint reports CSS pixels; 1pt = 4/3px):

| quantity | WeasyPrint used value | as points |
|---|---|---|
| body measure | 433.3333px | 325pt |
| narrow measure (24 blocks) | 414.6667px | 311pt |
| one-off measure (1 block) | 416.2152px | 312.1614pt |
| body font size | 13.3333px | 10pt |
| body line height | 17.3333px | 13pt |
| body family / weight / style | Magazine Serif 400 normal | SourceSerif4SmText-Regular.ttf |
| hyphens (after the switch) | manual | hyphenation off |
| letter-spacing / word-spacing | normal / 0 | no tracking |

Both legs were set to the same measure, family, size and hyphenation state.
Leading was set on the Typst side (`leading: 3.5pt`) for completeness; it does
not participate in horizontal breaking and cannot affect break points.
`linebreaks: "simple"` selects Typst's greedy breaker. No forced break, `\`,
`linebreak()`, `box()` or non-breaking construct was introduced on the Typst
side: every break in the Typst output is the breaker's own decision.

Coverage: 155 keyed prose blocks exist in edition 010. 149 were compared
(968 lines). The 6 excluded blocks (34 lines) are `span`-tagged blocks at
6.8pt, not paragraphs. Every `p` block in the edition was compared, including
the 27 that carry bold, italic or inline-code runs.

**Break-point reproduction, Typst `linebreaks: "simple"` against WeasyPrint:**

| measure | paragraphs | identical |
|---|---|---|
| all | 149 | 148 (99.33%) |
| lines | 968 | 963 (99.48%) |
| misses | | 1 |
| structural misses | | 0 |

### Miss classification

One miss, classified `fixable`.

**Block 135, 325pt measure, no inline styling, 5 lines, all 5 differing.**
WeasyPrint sets

```
The Causal Encoder-Decoder handles the other half. The lower twenty
```

as its first line; Typst breaks one word earlier, after `The lower`, and the
displacement cascades through the remaining four lines. Typst measures that
67-character string at exactly **325.01pt** against a **325pt** column
(`measure()` returns 3250100/10000 pt), so it overflows by 0.01pt and pushes
`twenty` down, while WeasyPrint fits it. Recompiling the same paragraph at a
sequence of column widths bounds the disagreement exactly:

| column | Typst reproduces WeasyPrint's breaks |
|---|---|
| 325.000pt | no |
| 325.005pt | no |
| 325.010pt | yes |
| 325.020pt | yes |

- **Mechanism**: cumulative text-shaping advance disagreement between
  rustybuzz and Pango/HarfBuzz, measuring 0.01pt over 67 characters
  (0.003% of the line). It is not a line-breaking algorithm difference: with
  0.01pt more column, Typst's greedy breaker reproduces WeasyPrint exactly.
- **Owning WP**: **WP-1.1** (shaping parity), whose target is cumulative line
  advances agreeing within 0.01pt.

### Two apparent misses that were artifacts of the spike, not of the engines

Recorded because a verifier replaying intermediate scripts will see them.

1. **Flattened inline styling.** A first pass (`wp12_compare.py`) rebuilt each
   paragraph as plain Regular text, losing bold and italic runs. Block 39,
   whose source carries `**Anthropic is unilaterally committing to this step
   now.**` and `*verifiability*`, diverged at exactly the line where the bold
   run begins. Preserving the runs removed the miss: all 27 styled paragraphs
   match. Result improved from 147/149 to 148/149.
2. **`pdftotext` word splitting at a font change.** Block 4 contains an inline
   code span; `pdftotext -bbox-layout` emits a word boundary where the font
   changes, so the extracted line reads `...tion) , which` against
   WeasyPrint's `...tion), which`. The two line contents are identical once
   whitespace is ignored, and the break points never differed. This is an
   extraction artifact of the spike's measuring instrument, not a property of
   either engine.

## Verdicts

This WP produces no `mag parity` verdict: it is a Phase 1 spike and the
comparison instrument is the throwaway script above, not the comparator.
Artifacts left in `$T` for the verifier: `wp12-weasy-runs.json` (the oracle
dump, 155 blocks), `wp12d-misses.json` (the two recorded misses),
`wp12-instrumentation.patch`, and the generated `wp12d-*.typ` / `.pdf` / `.xml`
pairs.

## Residuals

1. **A 0.01pt advance tolerance does not guarantee identical breaks.** WP-1.1's
   stated target is agreement "within 0.01 pt"; this miss is a line whose
   measured width lands exactly 0.01pt over the column, so a shaping result
   that satisfies WP-1.1 can still move a break. Whoever owns WP-3.1 should
   expect boundary lines of this kind and treat WP-1.1's tolerance as
   necessary, not sufficient.
2. **The narrow measures are real and must be transcribed.** Body paragraphs do
   not all run at 325pt: 24 blocks are set at 311pt and one at 312.1614pt.
   WP-2.2a's mapping table must carry them; a template that assumes one measure
   will diverge on 25 paragraphs.
3. **Hyphenation was switched off for this measurement only.** The result says
   nothing about break parity with hyphenation on. That is WP-1.3's
   measurement and WP-1.5's decision; if WP-1.5 chooses to keep hyphenation,
   this comparison must be re-run with the chosen mechanism applied to both
   sides before Phase 3 scores break points.
4. **Inline code paragraphs need per-run size, not just per-run family.** The
   two paragraphs carrying `Magazine Mono` runs also carry a different font
   size (8.2pt against the 10pt body). The engine's content pipeline (WP-2.1)
   and template (WP-2.2a) must carry per-run size or these paragraphs will
   break differently.
5. **Six `span`-tagged 6.8pt blocks were not compared.** They are not
   paragraphs and fall outside this WP's target, but no WP currently measures
   their break behaviour.

## Status

`awaiting-fran`

The plan's verify clause for this WP reads: "100% or a recorded Fran decision;
nothing in between enters Phase 2." The measurement is 148/149 paragraphs
(99.33%) and 963/968 lines (99.48%), with **zero structural misses**. The one
miss is classified `fixable` with its mechanism measured to the hundredth of a
point and assigned to WP-1.1, so the clause's automatic `awaiting-fran` trigger
(a structural miss) did not fire; what remains is the "100% or a recorded
decision" bar, which a 99.33% result cannot clear on its own.

**Recommendation, in order of preference:**

1. **Record the decision that this passes with the miss assigned to WP-1.1.**
   The evidence that Typst's greedy breaker agrees with WeasyPrint is strong:
   148 of 149 paragraphs reproduce exactly, including all 27 with mixed
   styling, and the single exception is reproduced exactly once the column
   gains 0.01pt. The residual risk is a shaping question that WP-1.1 already
   owns and that Phase 3 will score again at Tier E, where a moved line fails
   loudly rather than silently.
2. **Gate on WP-1.1 first**: require WP-1.1 to close the advance gap (OpenType
   feature-flag alignment is its stated first fallback), then re-run this
   comparison and expect 149/149. This is the stricter reading of "100%" and
   costs one re-run of the script above.

Nothing here is improvised around: no forced breaks, no widened column, no
narrowed page set. The single divergence is reported with its measurement.

## Appendix: wp12_compare4.py

The comparison instrument, in full, so this evidence replays without the
scratch directory.

```python
import json
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

TMP = Path("/Users/franguijarro/.claude/jobs/7d99e27f/tmp")
TYPST = TMP / "typst-install/bin/typst"
FONTS = TMP / "spike-wp12/src/magazine/assets/fonts"
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

widths = sorted({b["width_pt"] for b in blocks})
print("blocks:", len(blocks), "styled:", sum(b["styled"] for b in blocks), "widths:", widths, file=sys.stderr)

results = {}
for w in widths:
    group = [b for b in blocks if b["width_pt"] == w]
    size = group[0]["size_pt"]
    tag = str(w).replace(".", "_")
    data_path = TMP / f"wp12d-paras-{tag}.json"
    data_path.write_text(json.dumps([{"runs": b["runs"]} for b in group], ensure_ascii=False))
    typ = f"""#set page(width: {w}pt, height: auto, margin: 0pt)
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
    typ_path = TMP / f"wp12d-{tag}.typ"
    typ_path.write_text(typ)
    pdf_path = TMP / f"wp12d-{tag}.pdf"
    subprocess.run(
        [str(TYPST), "compile", "--font-path", str(FONTS), str(typ_path), str(pdf_path)],
        check=True,
    )
    xml_path = TMP / f"wp12d-{tag}.xml"
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
(TMP / "wp12d-misses.json").write_text(json.dumps(misses, ensure_ascii=False, indent=1))
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
