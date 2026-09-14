# WP-0.0c opener-fit attribution, verification

## Verdict

**ACCEPTED.** Every claim in `WP-0.0c.md` reproduced from a clean worktree.
The target is met, the reader PDF is provably untouched, and the web-edition
regression the first submission blocked on is fixed at its cause rather than
dodged.

Two findings are recorded below. Neither changes behaviour for any input the
generator can produce, so neither blocks acceptance; the first is an incorrect
justification in the evidence that a later reader could rely on, and the second
sharpens an obligation the WP hands to WP-3.2.

## Base and scope

- WP commit `6e8abb8`, parent `4f0828f`. Verified in a detached worktree at
  `6e8abb8`, with `editions/010/run-2026-09-13T01-34-51` copied in.
- `git merge-base --is-ancestor 5504e5a HEAD` is true, so WP-1.5's hyphenation
  switch is applied to BOTH legs. The worker's legs were taken at `5504e5a`;
  mine at `6e8abb8`. Neither comparison straddles the switch.
- Legs rendered here: A (changed, as committed) `render-2026-09-14T17-36-45`;
  B (baseline, the two Python files restored from `4f0828f`)
  `render-2026-09-14T17-38-02`.

## Owns

`6e8abb8` touches exactly `src/magazine/html_edition.py`,
`src/magazine/web_edition.py`, `meta/verification/evidence/WP-0.0c.md`. No
verify file, no `baseline.json`, no comparator territory, no Rust. The
`web_edition.py` entry is the orchestrator's mid-WP extension, granted because
the WP blocked on a coupling and recorded in plan revision 10; it is legitimate
and is not held against the diff.

## Replay

| claim | observed |
|---|---|
| manifest gains exactly nine leaves | added 9, removed 0, changed 0 |
| fit ids equal `layout.toc` ids | equal, both the same nine |
| all nine fits `true` | true, value set is `{True}` |
| web diff is header lines only | 18 added, 18 removed, non-header diff lines 0 |
| nine article files at 2 diff lines | each exactly 2 (one `<`, one `>`) |
| `edition.html` at 18 diff lines | 18 |
| `index.html` byte-identical | identical |
| `opener-source-link` 9 + 9 both legs | baseline 9/9, changed 9/9 |
| `class="source-qr"` 18 both legs | baseline 18, changed 18 |
| `mag parity` exit 0 | exit 0 |
| Tier S page_count / boxes / text | pass 56 vs 56 / 0 mismatches / 0 pages differ |
| Tier S color / navigation | pass 0 pages differ / 0 mismatches |
| Tier E display list | pass, 0 pages differ |
| Tier G | max dx 0.000 pt, max dy 0.000 pt, 0 structure mismatches |
| Tier V | dims pass, worst fraction 0.000000, max channel delta 0 |
| Tier E raster | `not_evaluated` (WP-0.2f), as expected at this commit |
| `pdftotext -raw` identical | identical for reader, booklet-a4, booklet-a4-interior |
| `pdfinfo -box` identical | identical for all three |
| critic/preflight whitelist only | 2 `.visual_review.*_sha256` + 4 scratch `.path`, nothing else |
| critic result | `pass` on both legs |
| ruff format/check clean | 2 files already formatted, all checks passed |

Verdict digest here is
`e22093b281dde849101070acc618e8a3e54a98252cb3f73a5569f67845851725`, against the
evidence's `c81b46ad...`. The difference is expected and not a discrepancy: the
verdict records the input PDFs' sha256, and independently produced PDFs differ
in dates and trailer ID. Every clause outcome matches.

## The regression, proven analytically

The old detection was `'<header class="article-opener">' in line`. That literal
ends in `>`, and the new header line is
`<header class="article-opener" data-article-id="...">`, so the substring is
absent: the old test returns False on every changed header, `in_illustrated_opener`
never becomes true, the source link is never upgraded, and
`_drop_print_only_lines` then removes it. The QR assets are still written and
left unreferenced. The new pattern returns True on both the old and the new
header line, so the fix is backward compatible as well as correct.

## Adversarial probe of `_ILLUSTRATED_OPENER_HEADER`

Twenty-one cases. The worker's eight all behave as documented. Thirteen of mine
were new; the generator emits exactly one form,
`  <header class="article-opener" data-article-id="...">` (double quotes, one
class, one line, lowercase), so only cases reachable from that form can be
defects.

Correctly rejected, all unreachable from the generator: single-quoted
attributes, `class="foo article-opener"` and `class="article-opener foo"`,
uppercase tag or attribute, a header split across two lines, `<headerfoo ...>`.
Correctly matched: extra whitespace inside the tag.

**Finding 1, evidence inaccuracy, not a behaviour defect.** The evidence states
that "`\bclass=` is what excludes `data-class=`". That is wrong. `\b` matches
between `-` and `c`, so `\bclass=` matches inside `data-class=`, and
`<header data-class="article-opener">` DOES match the pattern. What actually
rejected the worker's case 8 was the tag name: it was a `<span>`, not a
`<header>`. The behaviour is correct for every reachable input, since
`data-class` appears nowhere in `src/magazine/`, but the stated reason is not
the operative one and should not be relied on by a later change.

**Finding 2, narrowed brittleness, recorded not fixed.** The pattern requires
the class attribute to be exactly `"article-opener"`, so adding a second class
to that header would silently drop the QR again, which is this WP's own failure
mode one step removed. The adapter side is safe (`_note_box` uses
`_element_classes`, a real class-set test), and the generator emits a single
class today. This is a specific instance of the brittleness the worker already
recorded for WP-5.5, and it is worth naming because it lives on the very line
this WP repaired.

## Critique

**The three brittle patterns are unreachable from this change, as claimed.**
`_PRINT_ONLY_LINE`, `_SOURCE_LINK_LINE` and `_PIECE_OPENING` were each tested
against the old and the new header line: none matches either, so this change
cannot break them. Leaving them alone followed the orchestrator's guidance and
was the right call; widening the repair would have risked the output the WP was
holding constant.

**The unreachable-`false` analysis is correct, and the disposition is right,
but the obligation needs sharpening.** I confirmed the mechanism directly:
`weasyprint_adapter.py:2303` records an opener page only when the box is a
`header` carrying `article-opener` with a `data-article-id`, and `:2387`
computes `len(value) == 1`, so `false` requires the opener header box to span
two or more pages; `weasyprint-a5.css:1436` sets `break-inside: avoid` with
`break-after: page` on exactly that element.

I went further than the worker and tried to force a `false` with much larger
inflations of the same standfirst. Both attempts failed for a reason the
evidence does not mention: at 6,062 characters and again at 26,357, the render
aborts with `Edition needs 6 closing plates to close the signature but
configures 5`, so no manifest is produced at all. The worker's 3,017-character
leg rendered; mine did not. The reachable band in edition 010 between "no effect
on the fit" and "the render refuses" is therefore narrow and contains no `false`.

Consequence for WP-3.2, stated more strongly than the evidence does: a false-fit
fixture cannot be built by inflating prose in 010, because the signature guard
fires first. It needs a purpose-built fixture edition with its own closing
plates configured, or a non-textual mechanism such as an oversized opener image.
Until one exists, the clause compares nine `true`s against nine `true`s. That is
a real improvement on `{}` against `{}` (entries now exist and are attributed
per article), but it is not yet a gate that can fail, and WP-3.2 should treat
producing that fixture as blocking rather than advisory.

**The web tree is outside the gate, and the evidence records it honestly.**
Confirmed: `mag/src/parity.rs` compares `en/reader.pdf` pages 2..n-1 and nothing
else; no clause in the ladder reads `en/web/`. Grepping the comparator for
`web`, `/web/` or `edition.html` returns nothing. So the only thing that caught
this regression was the worker's own control render, and the only standing guard
on the web tree is render determinism. That is a gap in the gate rather than in
this WP, and the evidence is right to raise it. It is worth the plan's attention
that a change can be Tier E green on every compared page while silently breaking
a shipped artefact.

## Status

accepted
