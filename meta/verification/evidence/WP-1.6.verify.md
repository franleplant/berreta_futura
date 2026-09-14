# WP-1.6 verification

## Verdict

**ACCEPTED**, with one significant finding against a supporting argument, not
against the measurement.

## Verification mode: audit, per the Phase 1 downgrade

WP-1.6 is a Phase 1 spike. Its preamble puts spike code uncommitted in a
throwaway worktree, and that worktree is gone, so rule 3 verification
**downgrades to an evidence-consistency audit**. I did not re-run the
instrumented render or the rustybuzz harness.

Within that downgrade I checked everything cheaply checkable rather than
taking it on trust. What follows separates the two.

## Subject

| item | value |
|---|---|
| WP commit | `784da50` |
| Owns | `meta/verification/evidence/WP-1.6.md` only |
| Status claimed | `awaiting-fran` (dominant term is candidate 1) |

## Owns check

`784da50` touches exactly one file, its own evidence, 412 insertions. No
tracked source, no `*.verify.md`, no `baseline.json`. The spike left nothing
behind in the working tree.

## Checked independently (not audited: verified)

### The WeasyPrint mechanism

Confirmed verbatim in the installed weasyprint 69.0:

- `text/line_break.py:13-22` `line_size()` calls
  `pango_layout_line_get_extents(line, ffi.NULL, logical_extents)` and returns
  `logical_extents.width * FROM_UNITS`. Exactly as claimed.
- `text/ffi.py:500` `FROM_UNITS = pango.pango_units_to_double(1)`, declared at
  `ffi.py:276` as `double pango_units_to_double (int i)`.
- `text/ffi.py:250-256` `typedef struct { int x; int y; int width; int height; }
  PangoRectangle;` - **`width` is an `int`**, which is the whole mechanism.

So the width WeasyPrint breaks on is an integer count of Pango units, and the
claim that it is quantized at 1/1024 px is established from source, not
inferred.

### The arithmetic, recomputed from the evidence's own figures

| claim | recomputed | |
|---|---|---|
| 32501 font units, upem 1000, 10 pt | 325.01 pt exactly | OK |
| 443732 Pango units = 433.33203125 px = 324.9990234375 pt | matches to the bit | OK |
| 433.3333333333333 px content width = 325.0 pt | exact (px to pt is x0.75) | OK |
| candidate (1) = rustybuzz minus Pango | 0.010976562499990905 pt, claimed 0.0109765625 | OK |
| candidate (2) = Typst measure minus rustybuzz | 5.68e-14 pt, claimed 0.0 | OK |
| candidate (3) = column transcription | 0.0 pt | OK |
| sum vs observed disagreement | residual 0.0 | OK |
| fit decision | Typst overflows 325.0 by 0.0100 pt; Pango fits with 0.000977 pt slack | OK |

Two quoted rates are each rounded but mutually consistent: 0.000173 pt per
glyph is the edition-wide slope (mean drift 0.010476 over an implied mean of
60.6 glyphs), not this line's ratio, which is 0.000164 pt per glyph. The
"0.233 Pango units per glyph" figure recomputes to 0.2362 from the rounded
0.000173, and to 0.2321 from 0.000170; both quoted numbers are rounded
presentations of the same quantity. No inconsistency.

### The "1 of 899" window: computed, not asserted

The evidence shows the computation. The rustybuzz harness emits per line
`rb_over_col` as `(rb - col) > 1e-9` and `pango_over_col` as
`(pango - col) > 1e-9`, and the risk set is defined as rows where the first
is true and the second false. The tally is read off that CSV.

The CSV itself is gone, so the *count* is audited rather than reproduced, but
the definition is explicit and the harness source is in the evidence, so it
is reproducible in principle. The proxy is sound in the direction it tests: a
line WeasyPrint fitted whose rustybuzz width exceeds the column is a line
Typst must break earlier.

Its converse is correctly flagged as unmeasured (Residual 3): a wider Typst
measure could pull a word *up*, which needs next-word widths this dump does
not carry. One line does have negative drift (min -0.000566), so the converse
direction is not vacuous. Honest.

## Finding: the WP-1.1 reconciliation is partly unsupported

This is the claim my brief asked me to probe hardest, and it does not hold as
written.

WP-1.6 states that WP-1.1's normal-spacing residual (mean 0.002908, max
0.009897, zero lines over the quantum) is "a comparison of rustybuzz **after
rounding into Pango's grid** ... and **per run rather than per laid-out
line**".

**The per-run half is contradicted by WP-1.1's own text.** WP-1.1 records
"010 produced **1488 laid-out lines, 1488 runs** (no line required font
fallback)", an explicit 1:1 correspondence, and its letter-spacing table's
run counts sum to 1483 of those 1488. Run granularity and line granularity
are the same thing in that dataset, so it cannot explain any discrepancy.

**The rounding half is an inference, and the evidence points the other way.**
WP-1.1 states (line 91) that its harness reports *both* the unquantized
advance sum and the per-glyph advances rounded to Pango units, but never says
which feeds the residual table. Arithmetically the residual is 0.009897 pt =
13.5 Pango units, while WP-1.1's own "max summed per-glyph unit difference"
is 8 units = 0.0059 pt. A rounded-into-the-grid comparison could not exceed
the summed unit difference, so the residual is more likely the **unquantized**
comparison - the same quantity WP-1.6 measures.

Which leaves the two numbers genuinely unreconciled: max 0.009897 pt over
1402 normal-spacing lines (WP-1.1) against max 0.017432 pt over 899 single-run
body lines (WP-1.6), same edition, overlapping line sets, nominally the same
quantity.

A third variable neither spike controls for is the likely culprit and neither
names it in this context: **WP-1.1 measured a render with hyphenation ON**
(the tracked CSS carried `hyphens: auto` at the time), while **WP-1.6
measured with hyphenation OFF** (an uncommitted switch, matching WP-1.2).
Hyphenation shortens lines, drift accumulates at 0.000173 pt per glyph, so
the two are measuring different line populations. WP-1.6 records the
hyphenation state in Residual 4 but does not connect it to the WP-1.1
comparison.

**What this does and does not affect.** It does not touch WP-1.6's own
measurement, which is self-contained: its harness sums unquantized rustybuzz
advances for line texts taken from its own instrumented render and compares
them against Pango widths from that same render. The decomposition, the
mechanism, the per-glyph rate and the block-135 prediction all stand on that
data and I verified every one of them above. What it affects is the section
arguing *why* WP-1.1 saw a smaller number, and therefore any downstream text
that repeats that explanation. The conclusion WP-1.6 draws from it - that
WP-1.1's target sentence about line advances should not be read as a
per-line guarantee - remains correct, and is in fact better supported by
WP-1.1's own "max summed per-glyph unit difference 8 units" line than by the
per-run argument.

## Cross-instrument agreement, which is the strongest thing here

An independent instrument (full-precision `LineBox` width dump plus a
rustybuzz harness), on a different render, measuring a different quantity
from WP-1.2, predicts exactly the one line of 899 where the engines disagree
about fitting - and it is block 135, the single miss WP-1.2 reported. That is
a genuine independent confirmation and it is the reason this WP's central
result is trustworthy despite the finding above.

## Other observations

- The decomposition rests on a single line. That is appropriate for locating
  a mechanism, and the 899-line distribution generalises it, but the "sum of
  candidates equals observed with residual 0.000000" statement is a one-line
  result, not an edition-wide one.
- Residual 2 (69 lines skipped as mixed-run or non-body faces) is honestly
  scoped: they are excluded because the dump lacks per-run faces, not because
  they were checked and found uninteresting.
- Tool versions are recorded and the WP correctly pins nothing, deferring the
  Typst crate pin to WP-1.4.

## Status

`accepted` as a consistent and largely independently confirmed evidence
record, with the WP-1.1 reconciliation flagged above for whoever carries this
into the plan.
