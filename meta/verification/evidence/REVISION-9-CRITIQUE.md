# Adversarial critique of plan revision 9

Base: f044b99 (plan at 4b887f6 + 5f16548).
Read: the plan in full, evidence and verify files WP-0.0 through WP-1.4,
parity.yaml, and `mag/src/parity/{streams,display,geometry,raster}.rs`.

## Verdict: SOUND WITH FIXES

The two-sided bound is the right shape and the right answer to what WP-0.2d
measured. Bounding the guard from below by what the display list certifies as
invisible, and from above by what the display list cannot see at all, is a
real construction rather than a tuned tolerance, and making a collapsed window
`blocked` keeps it honest.

The gate's strength rests entirely on one premise: that the set of things the
display list cannot see is completely enumerated. Revision 9 states that set
as "intra-show TJ kerning, after WP-0.2e closes the transforms". That
enumeration is incomplete, and one of the missing items is the only blind spot
this project has actually observed in the wild. Fix that and the claim holds.

## Must fix before the gate is trusted

### 1. Glyph identity is an unlisted blind spot, and it corrupts WP-0.2f's ceiling

`Element::Text` in `streams.rs:57` records `{s, font, size, fill, m, clip}`.
`show()` (streams.rs:363) decodes the codes only to build the Unicode string
and accumulate the advance, then discards them: one element per show operator,
carrying the string and the text matrix AT SHOW START. Nothing records which
glyphs were drawn.

So two different glyph sequences that decode to the same Unicode string, drawn
from the same font at the same origin, are display-list EQUAL. The canonical
case is a ligature against its components, and WP-1.1 measured exactly that
between the two engines: "rustybuzz formed the `ft` ligature and Pango did
not: Pango suppresses ligatures when letter-spacing is applied"
(WP-1.1.md:137). Both decode to "ft". It was fixed by aligning feature flags,
and the Typst template must reproduce that alignment, but the GATE cannot
currently detect a regression of it: the template drifts, a headline renders
with a ligature the oracle does not have, and every clause except the raster
guard passes.

What it permits: a visibly different glyph on the page passing Tier E.

Worse, it breaks the plan's own reasoning. The Tier E text says "After WP-0.2e
the only display-list blind spot left is intra-show kerning, so the fixture is
a TJ array...". WP-0.2f would therefore derive its meaningfulness ceiling from
a fixture set missing an entire fault class, which is precisely the
incomplete-enumeration failure that produced the 241 in the first place.

Smallest fix: WP-0.2e also records the GLYPH COUNT per show. It is already
computed (the code loop in `decode_show`), it is exact, and it has no rounding
to false-fail on. A ligature shows one glyph where its components show two, so
count alone catches this class. Do NOT record raw CID codes: the two engines
subset independently and assign codes independently, so raw codes would
false-fail everywhere. If a stronger check is wanted later, map codes to GIDs
in the shared vendored face (the font-file digests are already proven
identical), but count is the cheap correct move now. Then the Tier E sentence
about the remaining blind spot becomes true again, and WP-0.2f's fixture set
is complete.

### 2. The reachability floor is a random sample, not a bound

Tier E derives the floor from a fixture that moves every coordinate "to a
random position INSIDE ITS OWN QUANTIZATION BUCKET". Two display-list-equal
renders can place every coordinate anywhere in its bucket independently, so the
worst legitimate case is every coordinate at the far edge of its bucket, not a
random draw from it. A random draw over 24452 operands yields a sample
statistic that underestimates the maximum and varies with the seed, which also
makes the bound irreproducible by anyone who re-derives it.

What it permits: nothing unsafe, but it sets the bound too low, so a future
legitimate sub-quantum difference fails the gate and burns a WP on a
non-problem. It also makes "derived, never chosen" untrue in practice, since
the number depends on a seed.

Smallest fix: WP-0.2f perturbs each coordinate to the extreme of its own
bucket rather than a random point, in both directions (two deterministic runs,
floor = max of the two), and asserts display-list equality as it already does.
No seed, reproducible, and an actual bound.

### 3. The kerning-containment argument is overstated, which raises the stakes on the bound

Tier E argues the kerning blind spot is narrow because "a kern difference moves
every later show in the same text object and surfaces there", leaving hidden
only "a kern difference in a show nothing follows, or one whose adjustments
cancel". `show()` does update `self.tm` by the accumulated advance, so that is
true for a following show positioned RELATIVELY. But the plan's own divergence
table states the opposite layout fact: "each line is its own show with its own
absolute position" (Known divergence sources, glyph advance quantization row).
If each line re-establishes position absolutely, no later show inherits the
shift, and the hidden set is not a corner case: it is every line.

What it permits: nothing by itself, but it means the raster guard is the SOLE
check on all intra-show positioning, not a backstop for a residue. The plan
presents it as the latter, and WP-0.2f will be sized accordingly.

Smallest fix: measure it rather than argue it, on the render that already
exists. Count how many text objects in 010's reader.pdf contain more than one
show with relative positioning between them. State the number in the plan and
restate the containment claim to match it. If it is near zero, say plainly
that intra-show positioning is checked by raster alone, so the bound carries
that weight.

### 4. Reference stability omits WP-0.0c from the sanctioned-oracle-change list

"Behavioral changes to `src/magazine/` are forbidden except in WPs naming it
under Owns (WP-0.0b and WP-1.5)" (Reference stability). WP-0.0c owns
`src/magazine/html_edition.py`. A verifier applying that sentence literally
rejects WP-0.0c's diff.

Smallest fix: add WP-0.0c to that parenthesis.

## Worth doing

**A floor/ceiling margin, stated in advance.** `floor < ceiling` with no
margin makes the gate brittle: floor 7 against ceiling 8 satisfies the rule
while leaving no room for content-dependent variation (a different edition,
a different body size, a figure-heavy page). WP-0.2f should record the ratio
and the plan should name the factor it requires (2x is a defensible starting
point), failing loud below it rather than discovering the squeeze on a real
edition.

**The verdict should report compared cardinality per collection clause.**
Measured on 010's reader.pdf: `/Outlines` 0, and `pdfinfo` reports no Title
and no Lang. So two thirds of the Tier S navigation clause compare empty
against empty on the target edition and pass without checking anything. The
link half is real (84 `/Link`, 21 `/Annots`), and the WP-0.2b fixtures prove
the instrument works, so this is a reporting honesty problem rather than a
hole: the artifact says "navigation: pass" where nothing was compared. The
plan's own Risks section already states the principle ("Every clause that
compares a collection should assert the collection is non-empty before
comparing it") but assigns it to no WP, so nothing implements it. Give it to
WP-0.2e: every collection clause records the count it compared, and the
verdict shows it.

**Name WP-0.2f's fallback now.** The plan says a collapsed window is `blocked`
and another revision. The revision that would follow is predictable, so
writing it down costs nothing and saves a scramble: close the remaining
display-list blind spots (glyph identity per finding 1, and intra-show
positions encoded at the same 0.01 pt quantum) so the raster guard is no
longer load-bearing, and demote raster to meters. Note the catch that makes
this a fallback rather than the primary plan: per-glyph positions at a 0.01 pt
quantum would false-fail on letter-spaced headlines, where WP-1.1 measured
0.0174 pt of Pango rounding drift, so the encoding needs thought before it is
adopted.

**Compare `/Rotate` in Tier S boxes.** `geometry.rs:7` compares MediaBox,
CropBox and TrimBox only. `/Rotate` is print-visible and one key wide. A 180
degree difference keeps page dimensions equal, so it reaches only the raster
guard; 90 or 270 trips the dimension hard fail. Cheap to close properly.

## Noted

- Marked-content operators are no-ops (`streams.rs:251`: `BMC`, `BDC`, `EMC`,
  `MP`, `DP`). Content inside an optional content group that a viewer hides
  would appear in the display list as painted. Neither engine emits OCGs
  today, so this is a latent asymmetry, not a live one.
- Rule 1c makes WP-2.0b serial with WP-0.2e and WP-0.2f (all own
  `mag/src/parity*`), which the graph's parallel presentation hides. Schedule
  accordingly.
- WP-1.4 measured Typst's PDF byte-reproducibility on a small fixture and the
  plan generalises it to the edition. Low risk, but it is a generalisation.
- WP-1.3 measured a GLOBAL hyphenation switch; WP-1.5 applies a `:lang(en)`
  scoped one. WP-1.5's verify already re-measures rather than assuming, which
  is the right shape.

## Checked and clean, so the sweep is on record

- Link destinations are compared exactly, URIs included: `link_dest`
  (`display.rs`) returns `uri:<full url>` for URI actions and resolves
  `/Dest` and `/A GoTo` to a destination page. A wrong or missing hyperlink
  target fails the gate. This was my first suspicion and it is unfounded.
- `page_annots` collects EVERY annotation subtype with rect and destination,
  not only links, which is stronger than the Tier S wording suggests.
- ExtGState fails loud on any key other than `ca`/`CA` equal to 1, and on any
  `SMask` (`streams.rs:321-336`). Blend modes and soft masks cannot slip
  through as no-ops.
- Colour normalization is computed with every unmapped operator failing loud,
  so deleting `color_space_map` removes a promise nothing kept rather than a
  check.
- Images hash decoded RGBA with the SMask composited before hashing, so a
  re-encode passes and a real pixel change fails.
