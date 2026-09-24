# WP-3.7b spike: why in-line glyph x differs on 010

Evidence only. No code under `mag/src` or `mag/assets` changed. Base
`art_directed` `8afd7d0`. Scratch (scripts, rewritten PDFs, verdicts):
`/Users/franguijarro/.claude/jobs/7d99e27f/tmp/wp37b-scr/`.

## Verdict

The in-line x difference is **not** Pango's 1/1024 px advance grid.
WeasyPrint's PDF writer (`weasyprint/draw/text.py` `draw_first_line`, v69.0)
throws that grid away. The cause is how the writer puts kerning into `TJ`:

```python
logical_width = font.widths[glyph_id]            # round(pango logical width * 1000 / font_size)
kerning = logical_width + offset - width * 1000 * FROM_UNITS / font_size
if kerning:
    string += f'>{int(kerning)}<'                 # int() truncates toward zero
```

So every glyph's written advance is `wid - trunc(wid - e)` in 1/1000 em. Here
`wid` is the glyph's integer `/W` width and `e` is Pango's real kerned advance.
A kerned pair therefore loses up to one 1/1000 em unit **toward the glyph's
nominal width**: 0.01 pt at 10 pt, 0.0185 pt at 18.5 pt. Typst writes the
exact font-unit kerned advance. The error adds up along a line to the
observed 0.06-0.14 pt, and its sign changes with the sign of each kern.

**Typst's values are the correct ones** (rule 4). `harfbuzz` shaping of the
vendored Source Serif 4 SmText gives `nt` = 626, `Py` = 630, `ve` = 537,
`ge` = 531 font units (upem 1000). Typst writes exactly those. WeasyPrint writes 627, 629, 538, 532.
WeasyPrint's PDF also disagrees with WeasyPrint's own layout, which
accumulates the unrounded float `x_advance`.

Two smaller mechanisms are real too:
- (d) **font size.** WeasyPrint sets `Tf` to `int(size_px * 1024) / 1024` px.
  That is `13.333008` px, so 10 pt text is set at 9.999756 pt (a factor of
  1 - 2.44e-5), and 18.5 pt at 18.49951. The end of a 350 pt line lands 0.0085 pt
  short. Per glyph that is about 0.00012 pt, below the 0.000732 pt tick, so it
  stays inside the glyph clause.
- **upem != 1000 faces (Inter, upem 2048).** WeasyPrint's `/W` is an integer
  (`round(pango width in 1/1000 em)`). Typst writes exact fractional widths
  (`656.7383` for B). Every Inter glyph can differ by up to 0.5/1000 em
  (0.0034 pt at 6.8 pt), even unkerned ones. This is what fails the running
  heads and folios.

## Measurements (the real 010 legs)

`mag parity 010 --run editions/010/run-2026-09-13T01-34-51` with
`MAG_PARITY_OUT_DIR=output/parity-wp37b`, binary built from `8afd7d0`, exit 1.
It wrote the WeasyPrint leg `editions/010/render-2026-09-24T04-35-49` and the typst
leg `editions/010/render-2026-09-24T04-37-08`. Tier S text passes (0 of 54 pages
differ), and tier G max dx is 0.003 pt. Glyph clause: fail, 58623 glyphs, 40 violations
(truncated).

Per-glyph advances in 1/1000 em, from `pymupdf` `get_texttrace` (1.28.2),
pairing lines by baseline y and matching char sequences (`decomp.py`,
`kern.py`). Both legs' advances are integers in 1/1000 em on every body
page (fraction 1.00 on both legs).

| page | glyph advances | differ | min / max diff | space advances | differ |
| --- | --- | --- | --- | --- | --- |
| 8 | 1307 | 120 | -0.0185 / +0.0185 pt | 223 | 2 |
| 13 | 1320 | 114 | -0.0185 / +0.0100 pt | 298 | 0 |
| 14 | 1360 | 90 | -0.0100 / +0.0100 pt | 298 | 1 |
| 15 | 1280 | 106 | -0.0185 / +0.0185 pt | 289 | 0 |
| 33 | 1322 | 115 | -0.0185 / +0.0185 pt | 304 | 4 |

Every difference is ±1 unit of 1/1000 em at the run's size. On page 13, all
16 of 16 `nt` pairs differ (W 627, T 626), 12 of 12 `ve` pairs, and 12 of 12 `ge` pairs.

Whole edition (`kern.py all`, same-font pairs inside matched lines):

| class | pairs | W = T | W off by 1 unit toward nominal | other |
| --- | --- | --- | --- | --- |
| kerned (T != hmtx advance) | 15299 | 10234 | **4818 (31.5%)** | 247 |
| unkerned | 30775 | 30762 | 0 | 13 |

Answer per candidate cause:
- (a) Pango 1/1024 px rounding: **0 effect in the PDF**. Unkerned advances
  match on 30762 of 30775 pairs. The 13 misses are size-changed or
  letter-spaced glyphs. The writer's integer `/W` plus `int()` drops the
  sub-unit residue. The effect only survives inside `int()`, where it decides
  which kerned pairs lose a unit. WP-1.6's drift still governs line breaking,
  a different quantity.
- (b) kerning: **the cause**. The writer truncates the kern. The features
  themselves agree (identical glyph sequences, WP-1.1).
- (c) justification/word spacing: **none**. Space advances match: 0-4 of about
  300 differ per page, and those are letter-spaced runs.
- (d) font size: real, -2.44e-5 relative, at most 0.0087 pt per line, inside the clause.

### Exact model of WeasyPrint's written advance

I tapped Pango directly, with `DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib`
and a monkeypatched `draw_first_line` (`pango.py`). At 10 pt, `n` = 8615 and
`nt` = 8547, 4738 Pango units. The model:

```
xs  = floor(size_pt * 4/3 * 1024)          # pango absolute size, WeasyPrint's int()
sc  = v -> round(v * xs / upem)            # nominal and kern scaled separately
e   = (sc(nominal) + sc(kern)) * 1000 / xs
wid = round(sc(nominal) * 1000 / xs)       # the /W entry
advance = wid - trunc(wid - e)
```

It predicts **14540 of 14765** kerned pairs and 30738 of 30739 unkerned
pairs, where the WeasyPrint advance is an integer (`model3.py`). The 225
misses are letter-spaced Inter runs, where Pango adds letter spacing that the
model leaves out. With `xs` unfloored, or with the kern scaled together with
the nominal width, the model misses 1366 to 4538 pairs.

## Prototype (scratch only, not landed)

`rewrite.py` post-processes the typst `reader.pdf` with pikepdf. For every
glyph in every Type0 `TJ`, it takes the nominal width from the embedded
subset's `hmtx` and the kern from Typst's exact advance, then rewrites the
adjustment so that the advance equals the model's. `size` also rewrites `Tf`
to `floor(px*1024)/1024*0.75`. Each variant ran through
`mag parity 010 --pre-rendered <weasyprint render> <rewritten copy>`. The
binary was temporarily built without `violations.truncate(40)` so that every
violation was counted, and that edit was reverted. Tier S text passes on every
variant. "Drift class" means violations of 0.2 pt or less, plus shape
violations. Violations above 0.2 pt (about 15.6k in every variant) are index
misalignment in the glyph clause. They are unrelated to advances, and pages
23, 27, 28 and 42 carry them.

| variant | glyph advances changed | drift-class violations, all pages | on the 23 pages whose lines pair exactly | of those 23, pages clean |
| --- | --- | --- | --- | --- |
| orig | 0 | 20035 | 10095 | 0 |
| size (Tf only) | 0 | 22977 | 11419 | 0 |
| kern (kerned glyphs, upem-1000 approximation) | 5292 | 3354 | 1627 | 0 |
| both (kern + Tf) | 5292 | 3460 | 1694 | 0 |
| all (every glyph, true hmtx, + Tf) | 7596 | **2022** | **1023** | **6** (14, 15, 18, 19, 33, 43) |

In body text, with `all`, 64 of 49116 glyphs are 0.01 pt or more off in-line
(orig: 23643), and the last glyph of a line matches to 1e-4 pt. The last
figure comes from pymupdf. MuPDF rounds `/W` to integers, so its numbers for
Inter are unreliable, and the Rust verdict is the authority. Size alone makes
things worse. In orig, WeasyPrint's smaller size (narrower lines) partly
cancels its kern truncation, which widens lines because most kerns are
negative. Shrinking Typst to the same size removes that cancellation.

What remains after `all` on the paired pages is openers. Pages 7, 11, 17, 31,
36, 40, 46 and 50 carry 70 to 119 violations each, and pages 9, 44, 49 and 53
carry about 10 each. All of them are letter-spaced runs (kicker, byline,
`END/02`, and the 30 pt title at -1 unit per glyph). The model has no Pango
letter-spacing term.

## Smallest landable design (a plan decision, not taken here)

1. **Typst side, `template::pdf` post-pass** (Typst exposes no advance hook).
   After typst-pdf writes the PDF, rewrite each Type0 `TJ` so that each
   glyph's advance is `wid - trunc(wid - e)` from the model above. Nominal
   widths come from the embedded subset's `hmtx`, and kerns from Typst's own
   exact advance. `Tf` becomes `floor(px*1024)/1024` px. Add Pango's
   letter-spacing term, measured the same way as in `pango.py`, before
   landing. Size: one pass over content streams, about 80 lines of Rust with
   lopdf. Cost: Typst's PDF then **deliberately carries WeasyPrint's kerning
   error** of at most 1/1000 em per kerned pair, plus the 2.44e-5 size shrink.
   That trades correctness for equality, and rule 4 says to record it as
   exactly that.
2. **Comparator side (Tier E contract change).** Allow an advance to differ by
   less than one 1/1000 em unit when the WeasyPrint advance lies between the
   Typst advance and the glyph's `/W` nominal width. Also allow Inter-class
   `/W` rounding of up to 0.5 unit. The glyph clause's current bound
   (`GLYPH_DRIFT_PT` = 1/1024 px per glyph, `ADVANCE_QUANTA` = 10 glyph quanta)
   was derived from the Pango grid mechanism, and this evidence shows that
   mechanism does not reach the PDF. That is a plan revision (rule 6), so it
   is not proposed as a widening here.

If equality with the oracle stays the goal, option 1 is the smaller change. It
fixes the 010 body pages outright on the pages already in pairing. Option 2
keeps Typst's output exact.

## Commands and exit status

- `cargo build --release` (worktree, own target dir): 0.
- `mag parity 010 --run ...` (above): exit 1, the expected fail.
- `mag parity 010 --pre-rendered ... T-{orig,kern,size,both,exact,all}`: exit 1 each.
  `exact` equals `both`, because refining the upem-1000 kern alone changes
  nothing.
- `uv run --with pymupdf --with uharfbuzz --with fonttools python <scr>/{decomp,kern,model3,stats,pp}.py`: 0.
- `cargo test` in `mag/` on the reverted worktree: 717 passed, 0 failed.

## What is and is not proven

**Proven.**
- Both legs write in-line advances as integers in 1/1000 em on body pages.
  Every in-line difference on those pages is ±1 unit, and every one sits on a kerned pair.
- WeasyPrint 69.0's writer truncates the kern with `int()`. The model built
  from that line and Pango's tapped widths reproduces 98.5% of kerned
  advances, and the remainder is letter-spaced.
- Typst's advances equal harfbuzz's exact kerned advances, so the oracle is
  the leg that is off.
- A Typst-side post-pass implementing the model reduces drift-class
  glyph-clause violations from 20035 to 2022 and cleans 6 of 23 paired pages.

**Not proven.**
- Pango's letter-spacing term is not modelled, and it is the whole residue on
  openers.
- The size rewrite's interaction with the display list's font-size field was
  not examined beyond "display list verdict unchanged" (45 pages differ,
  both before and after).
- Only English 010 was measured. Other sizes and faces follow the same
  formula but were not checked one by one.
- The >0.2 pt misalignment class (pages 23, 27, 28, 42) belongs to glyph
  pairing or text order and is out of this WP's scope.
