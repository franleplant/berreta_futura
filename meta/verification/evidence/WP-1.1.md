# WP-1.1 shaping parity

## Base

0bd7cc0 (feat(parity): WP-0.2d fault suite, raster bound and critic tolerances)

Phase 1 spike: all instrumentation was uncommitted and lives outside the
repository (the worktree's `.venv`, which is untracked). The spike worktree
ended `git status` clean and was removed. This file is the only owned path.

## Commands

Spike worktree and inputs:

```
git worktree add /Users/franguijarro/.claude/jobs/7d99e27f/tmp/spike-wp11 0bd7cc0
cd /Users/franguijarro/.claude/jobs/7d99e27f/tmp/spike-wp11
cp -R <main tree>/editions/010/run-2026-09-13T01-34-51 editions/010/
DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib:/usr/local/lib uv run python -c "import weasyprint"
```

`DYLD_FALLBACK_LIBRARY_PATH` reproduces `_configure_macos_library_path`
(`weasyprint_adapter.py:473`); without it the import fails, as WP-0.1 recorded.

Instrumentation, applied to the worktree's
`.venv/lib/python3.12/site-packages/weasyprint/draw/text.py`:

```python
import sys, pathlib
target = pathlib.Path(sys.argv[1])
src = target.read_text(encoding="utf-8")
anchor = "    utf8_text = textbox.pango_layout.text.encode()\n    stream.set_text_matrix(*matrix.values)\n"
if anchor not in src:
    raise SystemExit("anchor not found")
block = '''    utf8_text = textbox.pango_layout.text.encode()
    if __import__("os").environ.get("WP11_DUMP"):
        import hashlib as _hl, json as _json, os as _os
        _recs = []
        _r = first_line.runs[0]
        while _r != ffi.NULL:
            _gi = _r.data
            _r = _r.next
            _gs = _gi.glyphs
            _n = _gs.num_glyphs
            _pf = _gi.item.analysis.font
            _fnt, _fsize = stream.add_font(_pf)
            _w = [_gs.glyphs[_i].geometry.width for _i in range(_n)]
            _xo = [_gs.glyphs[_i].geometry.x_offset for _i in range(_n)]
            _gid = [_gs.glyphs[_i].glyph for _i in range(_n)]
            _off = _gi.item.offset
            _len = _gi.item.length
            _fc = _fnt.file_content
            _recs.append({
                "font_sha256": _hl.sha256(_fc).hexdigest() if _fc else None,
                "family": _fnt.family,
                "font_size_px": _fsize,
                "text": utf8_text[_off:_off + _len].decode("utf-8", "replace"),
                "glyph_ids": _gid,
                "widths_pango": _w,
                "x_offsets_pango": _xo,
                "advance_pango": sum(_w),
            })
        with open(_os.environ["WP11_DUMP"], "a", encoding="utf-8") as _fh:
            _fh.write(_json.dumps({
                "line_text": utf8_text.decode("utf-8", "replace"),
                "letter_spacing": textbox.style["letter_spacing"],
                "word_spacing": textbox.style["word_spacing"],
                "font_size_style_px": textbox.style["font_size"],
                "lang": textbox.style["lang"],
                "runs": _recs,
            }) + "\\n")
    stream.set_text_matrix(*matrix.values)
'''
target.write_text(src.replace(anchor, block, 1), encoding="utf-8")
```

Dump and compare:

```
cd mag && cargo build
cd .. && WP11_DUMP=<tmp>/wp11/pango.jsonl \
  ./mag/target/debug/mag render 010 --no-model --run editions/010/run-2026-09-13T01-34-51
<tmp>/wp11/shaper/target/release/wp11shaper <tmp>/wp11/pango.jsonl \
  <main tree>/src/magazine/assets/fonts > deltas2.json
```

The rustybuzz comparator (`<tmp>/wp11/shaper`, throwaway crate, `rustybuzz =
"0.20"`, `serde_json = "1"`, `sha2 = "0.10"`) maps each run's font by SHA256 to
the vendored file, shapes the run text with `Direction::LeftToRight`,
`script::LATIN` and the record's `lang`, and reports both the unquantized
advance sum and the per-glyph advances rounded to Pango units
(`round(x_advance * size_px * 1024 / upem)`). Runs whose style carries
letter-spacing are shaped with `liga off, clig off` (see Metrics).

## Tool versions

- weasyprint 69.0, pango 1.56.4, python 3.12.11, uv 0.8.17
- rustybuzz 0.20.1, rustc 1.96.0
- fonts: the 12 vendored files under `src/magazine/assets/fonts/`

## Metrics

### What was tapped, and why it is authoritative

`draw/text.py:draw_first_line` is where WeasyPrint walks the `PangoLayoutLine`
runs it is about to write into the PDF: per run it reads
`glyph_item.item.analysis.font` and every glyph's `geometry.width`, and
`stream.add_font()` yields the `Font` whose `file_content` is the exact font
file HarfBuzz shaped from. This is the final laid-out text, after line
breaking, so it is the authoritative dump. `_string_width` in the adapter is a
separate metrics-only estimator and was deliberately not used.
`line_break.py:72` sets `pango_context_set_round_glyph_positions(..., False)`,
so Pango is already in its subpixel mode.

010 produced **1488 laid-out lines, 1488 runs** (no line required font
fallback). All 9 fonts used resolve by SHA256 to vendored files:
SourceSerif4SmText-Regular 1094 runs, Inter-Medium 202, SourceSerif4Display-
Semibold 74, Inter-SemiBold 51, SourceSerif4SmText-Bold 22, Inter-Bold 18,
SourceSerif4SmText-It 14, Inter-Regular 9, GeistMono-Medium 4.

### Glyph-level agreement

| measure | result |
|---|---|
| glyph-id sequences identical (rustybuzz vs Pango) | **1488 / 1488** |
| per-glyph advance, max difference (normal-spacing runs) | **1 Pango unit = 0.0007324 pt** |
| max summed per-glyph unit difference | 8 units = 0.0059 pt |

Ligature and kerning cases are included: the sequences agree glyph for glyph,
so `kern`, `liga`, `clig` and `calt` resolve identically.

### OpenType feature alignment (the plan's stated fallback, and it was needed)

Two runs initially disagreed in glyph count, both letter-spaced display
headlines: `'Hours After CVE Patch'` (Pango 21 glyphs, rustybuzz 20) and
`'The third era of AI software'` (28 vs 27). In both, rustybuzz formed the
`ft` ligature and Pango did not: Pango suppresses ligatures when letter-spacing
is applied. Shaping letter-spaced runs with `liga off, clig off` aligned them,
and **all 86 letter-spaced runs then matched glyph for glyph**. This is the
flag alignment the Typst template must reproduce: ligatures off wherever
`letter-spacing` is set.

### Cumulative line advance

Pango applies letter-spacing after shaping, adding it to glyph advances. The
measured model is exact: the added width is `(n_glyphs - 1) * letter_spacing`,
i.e. spacing between glyphs only, never after the last one (82 of 86 runs match
to within 1%, the other 4 differ only by accumulated unit rounding).

Residual per line, after modelling letter-spacing, in points:

| letter-spacing | runs | mean | max | over 0.01 pt |
|---|---|---|---|---|
| normal | 1402 | 0.002908 | 0.009897 | 0 |
| 1.3867 px (.16em) | 39 | 0.003816 | 0.006973 | 0 |
| 0.3333 px (.25pt) | 12 | 0.001770 | 0.001953 | 0 |
| 0.3947 px (.04em) | 9 | 0.001146 | 0.001480 | 0 |
| 1.24 px | 9 | 0.000557 | 0.000557 | 0 |
| -1.8 px | 9 | 0.002865 | 0.005127 | 0 |
| -1.95 px (.045em @43.3px) | 3 | 0.012646 | 0.016553 | **2** |
| -1.59 px | 2 | 0.002798 | 0.003662 | 0 |
| -1.53 px (.045em @34px) | 2 | 0.013711 | 0.017402 | **2** |
| 0.6 px (.45pt) | 1 | 0.005273 | 0.005273 | 0 |
| **total** | **1488** | 0.002933 | **0.017402** | **4** |

### Worst offenders

All four are display headlines carrying negative tracking:

| residual | line |
|---|---|
| 0.017402 pt | `DeepSeek-V4.1-Flash: The Limits of` (34 glyphs, -1.53 px) |
| 0.016553 pt | `The third era of AI software` (28 glyphs, -1.95 px) |
| 0.014795 pt | `We Must Pace the Frontier` (25 glyphs, -1.95 px) |
| 0.010020 pt | `KV Cache Compression` (20 glyphs, -1.53 px) |

The residual is not shaping disagreement. It is Pango's fixed-point
quantization: every glyph advance and every letter-spacing gap is rounded to an
integer Pango unit (1/1024 px = 0.0007324 pt), and the error accumulates with
glyph count and with the magnitude of the tracking. It scales exactly that way
in the data (0-9 glyphs: max 0.0013 pt; 60-69 glyphs: max 0.0099 pt), and when
rustybuzz's advances are rounded the same way the two agree to within one unit
per glyph.

## Verdicts

No `mag parity` verdict is produced by this WP; it compares shaper output, not
PDFs.

## Residuals

1. **The literal target is missed on 4 of 1488 lines** (max 0.017402 pt against
   a 0.01 pt bar). Cause identified and bounded above; no OpenType feature flag
   can change it, because it is Pango's fixed-point rounding, not shaping.
2. **It cannot propagate to a Tier E coordinate in this design.** A line-width
   error only moves a recorded x-position when a position is derived from the
   measured width. `weasyprint-a5.css` contains **zero** `text-align: center`
   and **zero** `text-align: justify` (the only `text-align: right` is the
   `@bottom-right` page counter, 2 glyphs, letter-spacing normal). The four
   affected headlines are left-aligned blocks, so their width feeds no
   coordinate. The only width-dependent positions are the `.content-label`
   flex rows (`justify-content: space-between`, letter-spacing .45pt and
   .16em), whose worst residual is 0.006973 pt, inside the 0.01 pt quantum.
3. **Carry into Phase 2/3**: the Typst template must disable `liga`/`clig`
   wherever letter-spacing is set, and must apply tracking between glyphs only
   (`n-1` gaps). If a future edition introduces centered or right-aligned
   display text, this quantization residual becomes a live Tier E risk and the
   Typst engine would have to reproduce Pango's 1/1024 px rounding.
4. WeasyPrint embeds the full original font file (`Font.file_content` from the
   HarfBuzz face), so font identification by SHA256 is exact and needs no
   subset handling.

## Status

awaiting-fran

**Recommendation: go.** Shaping parity itself is proven at the strongest
available standard: identical glyph-id sequences on 1488 of 1488 runs and
per-glyph advances agreeing to within one Pango quantization unit, once the
`liga`/`clig` flags are aligned with Pango's letter-spacing behaviour. The
plan's numeric bar (0.01 pt cumulative, every line) is missed on 4 display
headlines by at most 0.0074 pt, from Pango's own fixed-point rounding rather
than from shaper disagreement, and residual 2 shows it cannot reach any
coordinate Tier E compares in this design. Recorded as `awaiting-fran` rather
than `done` because the stated threshold was not met literally and protocol
rule 6 forbids relaxing it here.
