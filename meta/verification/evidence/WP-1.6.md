# WP-1.6 locate the 0.01 pt measure disagreement

## Base

`f044b99` (branched from this commit; `art_directed` moved under me while
concurrent agents committed, so the replay below pins paths rather than a
worktree commit). Plan revision 9, `4b887f6` + `5f16548`.

## Result in one line

The whole disagreement is candidate (1): Pango reports a laid-out line width
quantized to integer 1/1024 px units, systematically **narrower** than the
exact sum of glyph advances that rustybuzz and Typst both use. Candidates (2)
and (3) contribute exactly zero.

## Metrics

### The decomposition, block 135 line 0

The line is `The Causal Encoder-Decoder handles the other half. The lower
twenty`, 67 characters, 67 glyphs, no inline styling, Source Serif 4 SmText
Regular at 10 pt, in the 325 pt body column.

| quantity | measured | source |
|---|---|---|
| Typst `measure().width.pt()` | 325.01000000000005 pt | typst 0.15.1 CLI |
| rustybuzz advance sum | 325.0100000000 pt (32501 font units, upem 1000) | rustybuzz 0.20.1 |
| WeasyPrint/Pango `LineBox.width` | 324.9990234375 pt | instrumented render |
| WeasyPrint block content width | 433.3333333333333 px = 325.0 pt exactly | instrumented render |

| candidate | contribution | how it was isolated |
|---|---|---|
| (1) rustybuzz vs Pango advances | **0.0109765625 pt** | rustybuzz sum minus Pango `LineBox.width` |
| (2) Typst `measure()` vs advance sum | **0.0000000000 pt** | Typst measure minus rustybuzz sum |
| (3) column width transcription | **0.0000000000 pt** | WeasyPrint content width is 325.0 pt exactly, which is what the template declares |
| **sum** | **0.0109765625 pt** | |
| observed disagreement | 0.0109765625 pt | Typst measure minus Pango line width |
| **residual** | **0.0000000000 pt** | inside the 0.001 pt the Verify clause allows |

The fit decision follows directly: Typst sees 325.0100 against a 325.0000
column and overflows by 0.0100 pt, so it moves `twenty` to the next line;
WeasyPrint sees 324.9990 against the same column and fits with 0.0010 pt to
spare. Both breakers are behaving correctly on the width each was given.

Candidate (2) being exactly zero is worth stating plainly: with upem 1000 at
10 pt every glyph advance is an exact multiple of 0.01 pt, the sum is an
integer count of font units (32501), and Typst's `measure()` reproduces it
without rounding of its own.

### The same measurement across the edition

Every single-run body line in edition 010 (Magazine Serif 400 normal, 10 pt,
text identical between the two dumps so the comparison is like for like): 899
lines, 69 skipped as mixed-run or other faces.

| drift (rustybuzz sum minus Pango line width) | pt |
|---|---|
| min | -0.000566 |
| p50 | 0.011055 |
| p95 | 0.014414 |
| max | 0.017432 |
| mean | 0.010476 |

| | lines |
|---|---|
| drift >= 0.0100 pt | 604 of 899 |
| drift >= 0.0050 pt | 833 of 899 |
| **rustybuzz exceeds the column while Pango fits** | **1 of 899** |

That single line is block 135 line 0, the exact miss WP-1.2 reported. An
independent instrument, a different render and a different quantity predict
precisely the one divergence WP-1.2 observed, which is the strongest
cross-check available here.

The drift is systematic, not noise: it correlates with glyph count at 0.807
and runs at 0.000173 pt per glyph (0.233 Pango units per glyph). It is
positive on 898 of 899 lines.

### The mechanism

`weasyprint/text/line_break.py` `line_size()` reads
`pango_layout_line_get_extents(line, NULL, logical_extents)` and returns
`logical_extents.width * FROM_UNITS`, where `FROM_UNITS` is
`pango_units_to_double(1)` = 1/1024. `PangoRectangle.width` is an integer, so
the width that drives WeasyPrint's line breaking is an integer count of
1/1024 px = 0.000732 pt, accumulated from advances already resolved onto that
grid. Verified empirically: every one of the 899 line widths is an integer
count of Pango units (block 135 line 0 is exactly 443732).

Typst takes the other road: it sums exact font units and scales once, so its
width carries no per-glyph grid. The gap is the accumulation of what Pango's
grid discards, which is why it grows with glyph count and why it is one-sided.

### Why this does not contradict WP-1.1's shaping result, and where it does contradict its target

WP-1.1 is correct on shaping itself and I reproduce its premise: glyph-id
sequences agree and per-glyph advances agree within 1 Pango unit. Its table
reports a normal-spacing residual of mean 0.002908 pt, max 0.009897 pt, zero
lines over the quantum. That number is a comparison of rustybuzz **after
rounding into Pango's grid** against Pango (its own line records "max summed
per-glyph unit difference 8 units = 0.0059 pt", which is a unit-by-unit
comparison), and per run rather than per laid-out line.

Both measurements are right about different quantities:

- WP-1.1 answers "do the two shapers agree once both are on Pango's grid?"
  Yes, within 8 units.
- WP-1.6 answers "does the width Typst actually breaks on match the width
  WeasyPrint actually breaks on?" No, by 0.0105 pt on a median body line.

The second is the quantity that decides line breaks, and it is the quantity
WP-1.1's target sentence names ("cumulative line advances agreeing within
0.01 pt on every line of edition 010"). Measured per laid-out line against
Pango's unrounded line width, that target is missed on 604 of 899 body lines,
not on zero.

This also means WP-1.1's stated fallback, aligning OpenType feature flags,
cannot address it. The features already agree; nothing about `liga`/`clig` is
involved. (WP-1.1's ligature-under-letter-spacing finding stands on its own
and is unaffected.)

### Lower bound for a widened Typst measure, for whoever fixes this

If the fix is to give Typst a slightly wider measure, every line WeasyPrint
fitted must still fit:

| column | lines | max Pango width | max rustybuzz width | Typst measure must be at least |
|---|---|---|---|---|
| 325.0000 pt | 770 | 324.999023 | 325.010000 | **325.010000 pt** |
| 311.0000 pt | 127 | 310.629639 | 310.640000 | 310.640000 pt |
| 312.1614 pt | 2 | 302.126221 | 302.140000 | 302.140000 pt |

This is a lower bound only. The upper bound needs the width of the next word
on each line, which this dump does not carry: widening the column far enough
could let Typst pull a word up where WeasyPrint did not. Establishing the
safe window is work for whoever owns the fix, not for this spike.

## Commands

```sh
T=/Users/franguijarro/.claude/jobs/7d99e27f/tmp
W=$T/spike-wp16
git -C /Users/franguijarro/code/magazine worktree add $W HEAD
cp -R /Users/franguijarro/code/magazine/editions/010/run-2026-09-13T01-34-51 $W/editions/010/
```

Typst leg, exact measure of the offending string:

```sh
cat > $T/wp16-measure.typ <<'EOF'
#set page(width: 400pt, height: 200pt, margin: 0pt)
#set text(font: "Source Serif 4 SmText", size: 10pt, hyphenate: false)
#let s = "The Causal Encoder-Decoder handles the other half. The lower twenty"
#context [
MEASURE_PT #repr(measure(text(font: "Source Serif 4 SmText", size: 10pt, s)).width.pt())
]
EOF
$T/typst-install/bin/typst compile \
  --font-path /Users/franguijarro/code/magazine/src/magazine/assets/fonts \
  $T/wp16-measure.typ $T/wp16-measure.pdf
pdftotext -layout $T/wp16-measure.pdf - | grep MEASURE
```

Two uncommitted patches in the worktree. First, WP-1.2's hyphenation switch,
so the configuration matches the render WP-1.2 measured (WP-1.5 had not
landed its `:lang(en)` switch at the time of this spike, so the tracked CSS
still carried `hyphens: auto`):

```diff
 .editorial li, article li, main > section li {
-  hyphens: auto;
+  hyphens: manual;
   hyphenate-limit-chars: 6 3 3;
 }
```

Second, a full-precision width dump in `weasyprint_adapter.py`: a call added
after `_report_hyphen_ladders(document, edition)` and a function added above
`_walk_boxes`. Unlike WP-1.2's dump this records `repr()` of the floats and
adds per-`LineBox` widths, which is the quantity the line breaker uses:

```python
    _report_hyphen_ladders(document, edition)
    _dump_line_widths(document)
```

```python
def _dump_line_widths(document: Any) -> None:
    target = os.environ.get("MAG_WIDTH_DUMP")
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
                    "block_width_px": repr(float(box.width)),
                    "block_width_pt": repr(float(box.width) * 0.75),
                    "font_size_px": repr(float(box.style["font_size"])),
                    "font_size_pt": repr(float(box.style["font_size"]) * 0.75),
                    "hyphens": str(box.style["hyphens"]),
                    "lines": [],
                },
            )
            for line in _walk_boxes(box):
                if type(line).__name__ != "LineBox":
                    continue
                texts = []
                for t in _walk_boxes(line):
                    if type(t).__name__ != "TextBox" or not isinstance(t.text, str):
                        continue
                    texts.append(t.text)
                record["lines"].append(
                    {
                        "text": "".join(texts),
                        "line_width_px": repr(float(line.width)),
                        "line_width_pt": repr(float(line.width) * 0.75),
                    }
                )
    Path(target).write_text(json.dumps(blocks, indent=1, ensure_ascii=False), encoding="utf-8")
```

The oracle leg. `mag render` takes the repo root from `current_dir()` and
runs the bridge there, so the main tree's already-built binary picks up the
worktree's instrumented Python and no rebuild is needed:

```sh
cd $W && MAG_WIDTH_DUMP=$T/wp16-weasy-widths.json \
  /Users/franguijarro/code/magazine/mag/target/debug/mag render 010 \
  --no-model --run editions/010/run-2026-09-13T01-34-51
```

Block 135 at full precision:

```sh
cd $T && python3 -c "
import json
b=json.load(open('wp16-weasy-widths.json'))['135']
print(b['block_width_px'], b['block_width_pt'], b['font_size_pt'])
for i,l in enumerate(b['lines']): print(i, l['line_width_pt'], repr(l['text']))
"
```

The corpus comparison. Line texts are cross-referenced against WP-1.2's run
dump (`$T/wp12-weasy-runs.json`, which survives) to keep only single-run
regular 10 pt lines, since this dump does not carry per-run faces:

```sh
cd $T && python3 -c "
import json
w=json.load(open('wp16-weasy-widths.json'))
r=json.load(open('wp12-weasy-runs.json'))
out=[]
for k,b in w.items():
    if abs(float(b['font_size_pt'])-10.0)>1e-9: continue
    rb=r.get(k)
    if not rb: continue
    runs=rb.get('runs',[])
    for i,l in enumerate(b['lines']):
        if i>=len(runs): continue
        rr=runs[i]
        if len(rr)!=1: continue
        f=rr[0]
        if f['family']!='Magazine Serif' or f['weight']!='400' or f['style']!='normal': continue
        if abs(float(f['size'])-13.3333)>1e-3: continue
        if rr[0]['text']!=l['text']: continue
        out.append({'block':k,'line':i,'text':l['text'],'pango_pt':float(l['line_width_pt']),'col_pt':float(b['block_width_pt'])})
json.dump(out,open('wp16-lines.json','w'),ensure_ascii=False)
print(len(out))
"
```

The rustybuzz harness, a throwaway crate at `$T/wp16`
(`rustybuzz = "0.20"`, `ttf-parser = "0.25"`, `serde_json = "1"`):

```rust
use std::io::Write;
fn main() {
    let path = "/Users/franguijarro/code/magazine/src/magazine/assets/fonts/source-serif-4/SourceSerif4SmText-Regular.ttf";
    let data = std::fs::read(path).unwrap();
    let face = rustybuzz::Face::from_slice(&data, 0).unwrap();
    let upem = face.units_per_em() as f64;
    let size = 10.0f64;
    let input = std::fs::read_to_string("/Users/franguijarro/.claude/jobs/7d99e27f/tmp/wp16-lines.json").unwrap();
    let v: serde_json::Value = serde_json::from_str(&input).unwrap();
    let mut out = std::fs::File::create("/Users/franguijarro/.claude/jobs/7d99e27f/tmp/wp16-drift.csv").unwrap();
    writeln!(out, "block,line,nglyphs,rb_pt,pango_pt,drift_pt,col_pt,rb_over_col,pango_over_col").unwrap();
    for e in v.as_array().unwrap() {
        let text = e["text"].as_str().unwrap();
        let pango = e["pango_pt"].as_f64().unwrap();
        let col = e["col_pt"].as_f64().unwrap();
        let mut buf = rustybuzz::UnicodeBuffer::new();
        buf.push_str(text);
        let g = rustybuzz::shape(&face, &[], buf);
        let raw: i64 = g.glyph_positions().iter().map(|p| p.x_advance as i64).sum();
        let rb = raw as f64 * size / upem;
        writeln!(out, "{},{},{},{:.6},{:.6},{:.6},{:.4},{},{}",
            e["block"].as_str().unwrap(), e["line"].as_i64().unwrap(),
            g.glyph_positions().len(), rb, pango, rb - pango, col,
            (rb - col) > 1e-9, (pango - col) > 1e-9).unwrap();
    }
}
```

```sh
cd $T/wp16 && cargo run --quiet --release
```

The distribution, the risk set and the per-glyph rate are read off
`$T/wp16-drift.csv` with plain `csv` arithmetic (drift percentiles; rows where
`rb_over_col` is true and `pango_over_col` is false; correlation of
`drift_pt` against `nglyphs`).

Mechanism confirmation in the installed WeasyPrint:

```sh
cd $W && sed -n '14,28p' .venv/lib/python3.12/site-packages/weasyprint/text/line_break.py
grep -rn "FROM_UNITS\s*=" .venv/lib/python3.12/site-packages/weasyprint/text/ffi.py
```

Cleanup:

```sh
git -C /Users/franguijarro/code/magazine worktree remove --force $W
```

## Tool versions

| tool | version |
|---|---|
| typst (CLI, spike instrument only) | 0.15.1 |
| rustybuzz | 0.20.1 |
| ttf-parser | 0.25 |
| weasyprint | 69.0 (via the repo's `uv` environment) |
| poppler (`pdftotext`) | 25.08.0 |
| python | 3.12.11 |
| rustc / cargo | 1.96.0 |

This WP pins nothing. WP-1.4 owns the Typst crate pin; the CLI here is a
measuring instrument and the rustybuzz version is the one Typst 0.15.1
resolves to.

## Verdicts

No `mag parity` verdict is produced by this WP: it measures widths, it does
not compare renders. The instrumented render is
`editions/010/render-2026-09-14T17-13-19` in the spike worktree, discarded
with the worktree.

## Residuals

1. **WP-1.1's normal-spacing row is not a per-line statement.** Its
   "max 0.009897 pt, 0 lines over the quantum" is a per-run comparison with
   rustybuzz rounded onto Pango's grid. Nothing in it is wrong, but it should
   not be read as evidence that laid-out line widths agree within the
   quantum, because measured directly they do not on 604 of 899 body lines.
   Whoever revises the plan may want WP-1.1's target sentence reworded so the
   quantity is unambiguous.
2. **The 69 skipped lines.** Mixed-run lines (bold, italic or inline code
   inside a paragraph) and non-body faces were excluded because this dump
   does not carry per-run faces. They are subject to the same mechanism and
   would very likely show the same drift; nothing suggests they behave
   differently, but they are not measured here.
3. **Upper bound not established.** The table above gives only the lower
   bound on a widened Typst measure. Whether a value exists that reproduces
   every break needs next-word widths.
4. **Hyphenation state.** Measured with hyphenation off, matching WP-1.2. If
   WP-1.5's `:lang(en)` switch changes which lines exist, the risk set must
   be recomputed; the mechanism and the per-glyph rate do not depend on it.
5. **The drift is one-sided and grows with line length**, so longer measures
   or larger faces will show more of it. A future edition with a wider column
   is more exposed to this class of miss, not less.

## Status

`awaiting-fran`.

The Verify clause of this WP states: "If the dominant term is (1), WP-1.1's
go recommendation needs revisiting and that is `awaiting-fran`; if (2) or
(3), the fix belongs to WP-2.2a's template transcription and WP-3.1 scores
it." The dominant term is (1), carrying 100% of the disagreement, so this
ends `awaiting-fran` as instructed.

Recommendation, for whoever records the decision:

- **WP-1.1's go verdict should stand on shaping**, which is what it actually
  proved: identical glyph sequences, per-glyph advances within 1 Pango unit,
  and the ligature/tracking rules the Typst template must reproduce. None of
  that is disturbed.
- **What should not stand is the inference that line widths therefore agree
  within 0.01 pt.** They do not, by a systematic 0.000173 pt per glyph, and
  the cause is Pango's 1/1024 px quantization of the width it breaks on, not
  a shaper disagreement. No feature-flag alignment can close it.
- **The consequence is narrow.** Across all 899 single-run body lines of
  edition 010 exactly one lands in the window where the two engines disagree
  about fitting. This is a fit-threshold coincidence, not a pervasive
  divergence, and Tier E will catch any recurrence loudly rather than
  silently.
- **The fix belongs downstream, not to WP-1.1.** The options are a widened
  Typst measure (lower bound 325.010000 pt for the body column, upper bound
  unmeasured), or quantizing Typst's advances onto the same 1/1024 px grid,
  which is engine-level behavior and not reachable from a template. Either
  way it is WP-2.2a's transcription and WP-3.1's scoring, and it needs the
  next-word measurement this spike did not take.
