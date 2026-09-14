# WP-1.1 verification

## Scope of this verification

Protocol rule 3, Phase 1 preamble: verification for spikes is DOWNGRADED to an
evidence-consistency audit. The spike's instrumentation was uncommitted and
lived in the worktree's untracked `.venv`, which is gone, so the measurement
cannot be replayed end to end. What follows is an audit of the record plus the
source-level spot-checks that were still available.

## Subject

- WP commit: `1299cc4` (`spike(parity): WP-1.1 shaping parity measurement`)
- Evidence: `meta/verification/evidence/WP-1.1.md`
- Declared base: `0bd7cc0`
- Declared Status: `awaiting-fran`, recommendation go

## Owns check: PASS

`git show --stat 1299cc4` lists exactly one file,
`meta/verification/evidence/WP-1.1.md` (226 insertions). No tracked source
changed, no `*.verify.md`, no `baseline.json`. `git status --short` in the main
tree carries nothing belonging to this spike.

## Evidence completeness: PASS

All mandatory sections present: `## Base`, `## Commands`, `## Tool versions`,
`## Metrics`, `## Verdicts`, `## Residuals`, `## Status`.

## Internal consistency: PASS

Every figure that can be recomputed from the file's own numbers checks out.

- Per-font run counts sum to the stated total: 1094 + 202 + 74 + 51 + 22 + 18 +
  14 + 9 + 4 = 1488, matching "1488 laid-out lines, 1488 runs".
- The residual table's run column sums to 1488 (1402 + 39 + 12 + 9 + 9 + 9 + 3
  + 2 + 2 + 1).
- The "over 0.01 pt" column sums to 4, consistent with the stated total of 4
  and with 1484 of 1488 lines inside the bar.
- The worst-offender table lists exactly four lines, two from the -1.95 px row
  and two from the -1.53 px row, matching those rows' per-row counts of 2 and 2.
- The stated maximum, 0.017402 pt, is the maximum of the per-row maxima and the
  top worst-offender entry.
- The Pango quantum is stated as 1/1024 px = 0.0007324 pt. At 0.75 pt per CSS
  px this is 0.75/1024 = 0.000732421875 pt. Correct.
- The Status section's "missed by at most 0.0074 pt" is the overshoot beyond
  the 0.01 pt bar (0.017402 - 0.01 = 0.007402), not the residual itself, and is
  phrased as such.
- The accumulation claim is dimensionally plausible: the worst line carries 34
  glyph advances plus 33 tracking gaps, so 67 roundings of up to half a unit
  bound the error at 0.0245 pt, and the observed 0.0174 pt sits inside that.

No conclusion exceeds the recorded measurement. The file explicitly declines to
call the WP `done` because the literal 0.01 pt target was missed on 4 lines,
which is the correct application of rule 6.

## Reproducibility of method: PASS

`## Commands` carries the worktree setup, the `DYLD_FALLBACK_LIBRARY_PATH`
workaround with its justification, the full instrumentation patch as an inline
Python script including its anchor string and a fail-loud `raise SystemExit` if
the anchor is absent, the render invocation with the environment variable, and
the comparator crate's dependencies and shaping parameters. A reader could
rebuild the measurement. The one gap is that the throwaway rustybuzz crate's
source is described rather than reproduced, so a replay would have to rewrite
it from the description. Recorded, not held against the WP.

## Source spot-checks: PASS, both claims exact

Verified against the installed WeasyPrint at
`.venv/lib/python3.12/site-packages/weasyprint`:

- `draw/text.py` defines `draw_first_line` at line 87, and the instrumentation
  anchor `utf8_text = textbox.pango_layout.text.encode()` is present at line
  137, inside that function. The tap point is real and the patch anchor exists.
- `text/line_break.py` line 72 reads
  `pango.pango_context_set_round_glyph_positions(pango_context, False)`. The
  claim that Pango is already in subpixel mode, at the exact line cited, is
  confirmed.

The claim that this tap is authoritative (final laid-out runs, after line
breaking, with the font file HarfBuzz shaped from) follows from the location
and is accepted.

## Cross-spike coherence: one finding, recorded

WP-1.2 attributes its single break-point miss to this WP: Typst measures a
67-character line at exactly 325.01 pt against a 325 pt column, so the
disagreement between the two engines' measured width of that line is at least
0.0100 pt.

This WP reports, for normal letter-spacing (1402 of 1488 lines), a maximum
residual of 0.009897 pt and ZERO lines over 0.01 pt, with the 60 to 69 glyph
bucket maxing at 0.0099 pt. The disagreement WP-1.2 needs is therefore larger
than any normal-spacing residual measured here.

This is not a contradiction, for three reasons that the two files between them
make clear:

1. The corpora differ. This spike rendered 010 in its shipping configuration
   with hyphenation on; WP-1.2 rendered with hyphenation off, so the line sets
   are not the same and WP-1.2's miss line need not appear among these 1488.
2. The quantities differ. This spike compares a raw rustybuzz advance sum
   against Pango's. WP-1.2 compares Typst's `measure()`, which is rustybuzz
   plus Typst's own layout, rounding and trailing-space handling, against
   WeasyPrint's fit decision.
3. WeasyPrint's actual width for that line is unknown; it is only known to be
   at most 325 pt, so the true gap may exceed 0.0100 pt.

The consequence is for the orchestrator rather than for this WP: WP-1.2's
second recommendation, gating on this WP closing the advance gap and then
expecting 149 of 149, rests on an attribution these numbers do not corroborate.
This WP reports its shaping as already inside 0.01 pt on every normal-spacing
line and recommends go with no further shaping work, so in its own terms there
may be no gap to close. If the residual in fact lives in Typst's `measure()`
rather than in rustybuzz against Pango, closing nothing here would change
WP-1.2's result and the miss would survive into WP-3.1.

## Verdict

**ACCEPTED** as a consistent, honest and well-sourced evidence record.

The `awaiting-fran` status is the plan's designed outcome for a spike that
misses its literal numeric bar, not a defect, and the decision itself is out of
this audit's scope. The cross-spike attribution finding above is recorded for
whoever resolves the Phase 1 gates.
