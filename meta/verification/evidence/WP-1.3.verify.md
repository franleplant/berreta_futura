# WP-1.3 verification

## Scope of this verification

Protocol rule 3, Phase 1 preamble: verification for spikes is DOWNGRADED to an
evidence-consistency audit. The instrumentation was uncommitted and the spike
worktree is gone, so the two renders cannot be replayed end to end here. What
follows is an audit of the record plus the stylesheet spot-checks that were
still available.

## Subject

- WP commit: `103d8a9` (`spike(parity): WP-1.3 hyphenation measurement and
  recommendation`)
- Evidence: `meta/verification/evidence/WP-1.3.md`
- Declared base: `0bd7cc0`
- Declared Status: `awaiting-fran`, recommending option (b)

## Owns check: PASS

`git show --stat 103d8a9` lists exactly one file,
`meta/verification/evidence/WP-1.3.md` (317 insertions). No tracked source
changed, no `*.verify.md`, no `baseline.json`. `git status --short` in the main
tree is clean, so the `sed -i ''` CSS switch was genuinely reverted rather than
left behind. This matters more here than for the sibling spikes, because this
spike edited a tracked stylesheet in place.

## Evidence completeness: PASS

All mandatory sections present, with the analysis script reproduced in full
inside `## Metrics`.

## Internal consistency: PASS

Every derived figure recomputes from the file's own numbers.

- Soft-hyphen breaks: 141 hyphen-ended lines with hyphenation on minus 15 with
  it off equals the stated 126.
- Reclaimed lines: 976 off minus 967 on equals the stated 9.
- The per-article table shows on equal to off in all nine rows, consistent with
  "Articles with a changed page count: 0".
- The Dario row, 13 pages against a cap of 10, is identical in both columns,
  consistent with the violation being called pre-existing rather than
  introduced.
- The caps are consistent with the plan's content modes: 7 for ordinary
  articles, 10 for the two `verbatim` ones.
- The plan's own definition of negligible (zero page-count changes and zero cap
  violations) is met by these numbers, and the file applies that definition
  rather than inventing one.
- The comparator cross-check is quoted with its exit code (1) and its verdict
  sha256, and the file correctly states that this verdict measures a switch
  against itself on one engine and gates nothing. That is the right framing: it
  is not a parity verdict.

The conclusion does not exceed the measurement. The recommendation is argued
from the recorded numbers (126 breaks across 81 of 155 blocks as the cost of
option (a), zero pagination change as the cost of option (b)) rather than from
preference.

## Reproducibility of method: PASS

`## Commands` carries the worktree setup, the run-directory copy with an
explicit note that it is untracked, the instrumentation function in full, the
exact `sed` switch with its line number, both render invocations with their
environment variables, and the analysis script in full. The `pdfinfo` and
comparator cross-checks are given as commands rather than as assertions.

## Spot-checks against the stylesheet: all CONFIRMED exactly

- Line 639 is `  hyphens: auto;` and line 640 is
  `  hyphenate-limit-chars: 6 3 3;`, inside the selector group that ends at
  line 638 with `.editorial li, article li, main > section li {`. Both cited
  line numbers are exact.
- Line 645 is `ul[data-reference-list] li { hyphens: manual; }`, line 652 is
  `p[data-name-roster] { hyphens: manual; }`, line 655 is
  `code { hyphens: manual; }`. All three carve-outs confirmed at the exact
  lines cited, so the claim that 639 is the only live `hyphens: auto` is sound.
- The Spanish cost claim is confirmed near-verbatim in the stylesheet comment:
  "Spanish pays the most: its words run longer than English's, so the same
  manuscripts set about four pages longer (edition 003 measured en 36 / es 40
  total pages before this rule) and es article 3 sits exactly on the
  seven-page cap."
- The mitigation's premise is confirmed in the same sentence: "`html lang` is
  set per language (html_edition.py)", so a `:lang(en)` qualifier is in fact
  available.

## One completeness note on the Spanish residual

The residual is accurately sourced, and the cap risk it raises is real, since
an article sitting exactly on its cap has zero margin. For whoever takes the
WP-1.5 decision, the same comment block carries a second measurement the
residual does not quote, and it cuts the other way:

"Edition 003, both languages, before -> after: pagination is IDENTICAL -- 36/40
total pages, every article's span and the closing-plate arithmetic unchanged
[...] The es factories article stays exactly on its 7-page cap."

So on the one edition where this was measured in both languages, turning
hyphenation on did not move Spanish pagination, which is evidence that turning
it off would not either. That does not dissolve the risk (the stylesheet itself
warns against trusting these numbers across manuscript edits, and 010 is a
different edition), but it means the residual's worst case is less likely than
the quoted half of the comment alone suggests. Recorded as a completeness note
for WP-1.5, not as a defect in this spike: the residual explicitly hands the
decision to WP-1.5 rather than resolving it.

## Cross-spike coherence: one finding, recorded

This WP counts 155 prose blocks and 976 prose lines in the hyphenation-off
configuration. WP-1.2, measuring the same edition in the same configuration,
agrees exactly on the 155-block population but reports 149 compared blocks
carrying 968 lines plus 6 excluded blocks carrying 34 lines, which totals 1002.

968 + 8 = 976 reconciles the two exactly, so the arithmetic points at WP-1.2's
"(34 lines)" being the incorrect figure rather than anything here. Both dumps
are gone, so this is recorded rather than adjudicated. Neither WP's conclusion
depends on it: this WP's page, cap and incidence findings do not use an
absolute cross-block line total.

## Verdict

**ACCEPTED** as a consistent, well-sourced evidence record whose citations
survive direct checking against the stylesheet.

The `awaiting-fran` status is mandated by the WP's own verify clause ("Ends
`awaiting-fran`"), so it is the designed outcome rather than a defect, and the
option (a) against option (b) decision is out of this audit's scope. The
completeness note on the Spanish residual and the line-count finding are
carried forward for WP-1.5.
