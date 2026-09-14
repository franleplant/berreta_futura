# WP-1.2 verification

## Scope of this verification

Protocol rule 3, Phase 1 preamble: verification for spikes is DOWNGRADED to an
evidence-consistency audit. The instrumentation was uncommitted and the spike
worktree was removed, so the measurement cannot be replayed end to end. What
follows is an audit of the record plus the stylesheet spot-checks that were
still available.

## Subject

- WP commit: `7283125` (`spike(parity): WP-1.2 line-break parity measurement`)
- Evidence: `meta/verification/evidence/WP-1.2.md`
- Declared base: `0bd7cc0`
- Declared Status: `awaiting-fran`, 148 of 149 paragraphs

## Owns check: PASS

`git show --stat 7283125` lists exactly one file,
`meta/verification/evidence/WP-1.2.md` (475 insertions). No tracked source
changed, no `*.verify.md`, no `baseline.json`. `git status --short` in the main
tree carries nothing belonging to this spike, so the CSS switch and the adapter
patch were genuinely reverted.

## Evidence completeness: PASS

All mandatory sections present, plus a dedicated `## Ragged-right confirmation`
section and an appendix reproducing the comparison script in full.

## Internal consistency: PASS

- 148/149 = 99.328 percent, recorded as 99.33. Correct.
- 963/968 = 99.483 percent, recorded as 99.48. Correct.
- Coverage adds up: 149 compared plus 6 excluded equals the 155 keyed prose
  blocks stated.
- The line arithmetic is consistent with the single miss: 968 - 963 = 5 differing
  lines, and the miss is described as a 5-line paragraph with all 5 lines
  differing after the cascade.
- The column-ladder bisection (no at 325.000 and 325.005, yes at 325.010 and
  325.020) is consistent with the stated 325.01 pt measurement and bounds the
  disagreement rather than asserting it.
- The two self-reported instrument artifacts are disclosed with their effect on
  the result (147/149 improving to 148/149 once styled runs were preserved),
  which is the honest direction to report them in.

## Reproducibility of method: PASS

`## Commands` uses absolute paths, carries both instrumentation patches inline
(the one-line CSS switch as a diff and the `_dump_prose_lines` function in
full), names the Typst CLI install command and version, and the appendix
reproduces the entire comparison script. This is replayable.

## Spot-checks against the stylesheet

**Ragged-right, the WP's headline structural claim: CONFIRMED.**

`grep -n text-align src/magazine/assets/weasyprint-a5.css` returns exactly one
hit, line 156, and `sed -n '148,160p'` shows it sitting inside the
`@bottom-right` page-margin box whose `content` is
`counter(page, decimal-leading-zero)`, the folio. The quoted block in the
evidence matches the file. Body text therefore inherits the initial value and
the design is ragged-right, as claimed and as the plan's known-divergence table
assumes.

**Finding 1, wording precision.** The evidence states "No `justify` appears
anywhere in the file". Taken literally this is false: `justify` occurs 4 times,
at lines 294 and 709 as `justify-content: space-between` (flexbox, unrelated to
text alignment) and at lines 742 and 968 inside comment prose. The substantive
claim, that no `text-align: justify` exists and the design is ragged-right,
holds and is confirmed. The sentence overstates what a plain grep shows, and a
later reader checking it would see a contradiction where none exists. Recorded
as a precision defect in the record, not as a measurement error. Note also that
the `justify-content` rows at 294 and 709 are the same `.content-label` flex
rows WP-1.1 identifies as the only width-dependent positions in the design, so
they are not merely incidental.

## Cross-spike coherence: two findings

**Finding 2, a line-count discrepancy against WP-1.3.** This WP reports 149
compared blocks carrying 968 lines and 6 excluded blocks carrying 34 lines,
which totals 1002 lines across the 155 keyed prose blocks. WP-1.3, measuring
the same edition in the same hyphenation-off configuration and agreeing exactly
on the 155-block population, independently counts 976 prose lines in total.

968 + 8 = 976 reconciles the two exactly, so the arithmetic points at this
file's parenthetical "(34 lines)" being the incorrect figure and the 6 excluded
span blocks carrying 8 lines. I could not settle which file is wrong without
the dumps, both of which are gone, so it is recorded rather than adjudicated.
Neither WP's headline result depends on it: this WP's match rates are computed
within its own 149-block corpus, and WP-1.3's page and cap findings do not use
an absolute line total.

**Finding 3, the miss attribution is not corroborated by WP-1.1.** This WP
assigns its single miss to WP-1.1, on the basis that Typst measures the
67-character line at exactly 325.01 pt against a 325 pt column, so the two
engines disagree about that line's width by at least 0.0100 pt. WP-1.1 reports,
for normal letter-spacing, a maximum residual of 0.009897 pt with ZERO lines
exceeding 0.01 pt, so no line it measured disagrees by as much as this miss
requires.

The two are not in contradiction, because the corpora differ (WP-1.1 rendered
with hyphenation on, this WP with it off), because the compared quantities
differ (WP-1.1 compares a raw rustybuzz advance sum against Pango, while this
WP compares Typst's `measure()`, which adds Typst's own layout and rounding,
against WeasyPrint's fit decision), and because WeasyPrint's exact width for
the line is unknown beyond being at most 325 pt.

The consequence matters for the decision this WP defers. Recommendation 2,
gating on WP-1.1 closing the advance gap and then expecting 149 of 149, assumes
a gap that WP-1.1's own numbers do not show; WP-1.1 reports itself already
inside 0.01 pt on every normal-spacing line and recommends go without further
shaping work. If the residual actually lives in Typst's `measure()`, that
gating would change nothing and the miss would survive into WP-3.1, where
this WP's own residual 1 correctly predicts it would fail loudly at Tier E.

## Assessment of the residuals

The five recorded residuals are substantive and carry real work forward: the
necessary-but-not-sufficient nature of a 0.01 pt advance tolerance, the three
distinct body measures (325 pt, 311 pt for 24 blocks, 312.1614 pt for one) that
WP-2.2a must transcribe, per-run size for inline-code paragraphs, the
hyphenation dependency on WP-1.3 and WP-1.5, and the six unmeasured span
blocks. Residual 2 in particular is the kind of finding that would otherwise
surface as a Phase 3 failure on 25 paragraphs.

## Verdict

**ACCEPTED** as a consistent evidence record, with findings 1, 2 and 3 above
recorded.

Finding 1 is a wording defect that does not affect the result. Findings 2 and 3
are cross-spike inconsistencies that neither this WP nor its siblings can
resolve alone; they are carried forward for whoever resolves the Phase 1 gates
and for WP-3.1. The `awaiting-fran` status is the plan's designed outcome for a
result between a structural miss and 100 percent, not a defect, and the
decision is out of this audit's scope.
