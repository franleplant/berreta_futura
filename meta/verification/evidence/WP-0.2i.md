# WP-0.2i per-glyph positions and glyph identity

## Base

b12a2a3 (`test(model): WP-5.1c cover remaining py_repr escape branches`), plan
revision 15 (`3892298`). Rebased onto current `art_directed` before landing.

## Commands

Fixtures are scratch PDFs, not committed, built by two inline scripts. Both run
from the repository root so `uv run` resolves the project environment.

Inputs: two matched pre-`5504e5a` render trees copied to `$T/rA` and `$T/rB`
(`editions/010/render-2026-09-14T01-47-59` and `...T01-49-02`). All fixtures are
derived from `rA`, and every fixture run compares against `control`, the same
tree rewritten by pypdf with no edits, so pypdf's rewrite is never mistaken for
a fault.

```sh
T=/Users/franguijarro/.claude/jobs/7d99e27f/tmp
cp -R editions/010/render-2026-09-14T01-47-59 $T/rA
cp -R editions/010/render-2026-09-14T01-49-02 $T/rB
```

`mkfix.py` (control, drift, kern02, kern005, kern001, linmatrix, ocmember,
annotap) and `mkfix6.py` (glyphsub) are reproduced verbatim in ## Residuals.
Run them with `uv run python <script>` from the repository root.

```sh
M=./mag/target/debug/mag
B=$T/fix
$M parity 010 --pre-rendered $T/rA $T/rA     # A-vs-A, twice
$M parity 010 --pre-rendered $T/rA $T/rB     # A-vs-B, twice
for f in control drift kern02 kern005 kern001 kern00001 linmatrix glyphsub ocmember annotap; do
  $M parity 010 --pre-rendered $B/control $B/$f
done
cd mag && cargo fmt --check && cargo clippy --all-targets -- -D warnings && cargo test
```

## Tool versions

poppler 25.08.0 (asserted at startup), tracer `lopdf-0.45.0` (asserted),
ttf-parser 0.25 (already a dependency; no crate added, so `mag/Cargo.toml` and
`mag/Cargo.lock` are untouched), rustc 1.96.0, pypdf 6.14.2 and fontTools from
the project environment for fixture construction only.

## Metrics

### Determinism and the corpus

| run | exit | glyph clause | ratio | verdict digest (head) |
|---|---|---|---|---|
| A-vs-A, run 1 | 0 | pass | 0.0000 | `0e21644ee602ff8a` |
| A-vs-A, run 2 | 0 | pass | 0.0000 | `0e21644ee602ff8a` |
| A-vs-B, run 1 | 0 | pass | 0.0000 | `6e932ea43678b91a` |
| A-vs-B, run 2 | 0 | pass | 0.0000 | `6e932ea43678b91a` |
| control (pypdf rewrite, no edits) | 0 | pass | 0.0000 | `e4e388042c68272c` |

Both digests reproduce byte-identically across consecutive runs, so the verdict
stays byte-deterministic with the clause added. 010 A-vs-A and A-vs-B remain
Tier E equal. The corpus carries 68,800 glyphs across 1,488 shows over the 54
compared interior pages.

### Floor, ceiling and margin

`worst_ratio` is the maximum over all glyphs of (measured device-space offset
difference) / (k x 0.000732421875 pt). It replaces `worst_excess_pt` as the
margin metric because the maximum EXCESS always lands at glyph 0, where the
bound and the difference are both zero, which says nothing about headroom.

| fixture | fault | ratio | violations | result |
|---|---|---|---|---|
| drift | every glyph displaced k x 0.000173 pt (WP-1.6's measured rate) | 0.2731 | 0 | **pass, the floor** |
| kern02 | compensating kern 0.02 pt | 10.2400 | 5 | fail (magnitude) |
| kern005 | compensating kern 0.005 pt | 2.5941 | 5 | fail (magnitude) |
| kern001 | compensating kern 0.001 pt | 0.5461 | 1 | **fail (shape alone)** |
| kern00001 | compensating kern 0.0001 pt | 0.0683 | 1 | **fail (shape alone)** |

**Margin: 1 / 0.2731 = 3.66x, against the required 2x. Met.** Legitimate drift
consumes 27.31% of its bound at the worst glyph in the edition.

The two shape-only rows are the result that matters. A compensating kern of
0.0001 pt is 1% of the coordinate quantum and 200x smaller than the smallest
ceiling fixture the plan asked for, sits at 6.83% of the magnitude bound, and
still fails, because the difference sequence rises and returns toward zero
instead of accumulating. The ceiling therefore does not depend on fault size,
which is precisely what inverted WP-0.2f's window and what the raster guard
could not deliver at any resolution.

### The five must-fail fixtures

| fixture | must fail on | observed |
|---|---|---|
| compensating kern 0.02 pt | shape | fail, exit 1, ratio 10.2400 |
| linear-matrix below half a quantum over a full-measure line | per-glyph magnitude | fail, exit 1, ratio 2.8672, 9 violations |
| equal-advance glyph substitution | glyph identity | fail, exit 1, display list on 12 pages |
| optional-content membership | fail-loud stop | `error: tracing page 4 ...: operator BDC: optional content membership unsupported (fail loud per Tier E): <</Type /OCG/Name /Hidden>>` |
| annotation carrying `/AP` | fail-loud stop | `error: annotations page 3: annotation Link carries an appearance stream, which the display list does not compare (fail loud per Tier E)` |

The glyph-substitution fixture is fully isolated, which took three attempts and
is worth recording because the first two were not. Patching the PDF's `W` array
and `ToUnicode` to make one CID impersonate another changed the advance (ratio
1242) and, because every CID in a subset is used somewhere, changed the decoded
text on 12 pages. The isolated fixture instead patches the EMBEDDED FONT so CID
`0x0089` (`F`) draws `A`'s outline, leaving the content stream, the `W` widths
and the `ToUnicode` map untouched. The result is exactly the blind spot the
plan names:

- `tier_s text`: **pass** (the decoded string is unchanged)
- `glyph_positions`: **pass, ratio 0.0** (the advance is unchanged)
- `display_list`: **fail on 12 pages**, caught by `gids` alone

Glyph count cannot see it (same count), the string cannot see it, and the
offsets cannot see it. Only the mapping to the shared vendored face does.

### Cost

Full run 87 s (debug build) against 82 s before this WP, so the per-glyph work
costs about 5 s, against the 9 to 15 minutes WP-0.2f measured for supersampled
rasterization. Added dump data is 68,800 glyphs x (two `i64` offsets plus one
`u32` gid) = about 1.4 MB per leg; peak RSS across the suite ranged 246 MB to
779 MB. The comparison is O(n) in glyphs.

## Verdicts

A-vs-A `0e21644ee602ff8a...` (pass, twice), A-vs-B `6e932ea43678b91a...` (pass,
twice), control `e4e388042c68272c...` (pass), drift `237d5ad34dc9777e...`
(pass), kern02 `b94c0b91cafdd218...`, kern005 `2e8b4ad70af55f6a...`, kern001
`a33876235e00e7ca...`, kern00001 `e1dc7db51cd5dffe...`, linmatrix
`016658ec8e188318...`. `ocmember` and `annotap` write no verdict because they
fail loud during tracing, which is the required behaviour; their evidence is the
error text and exit 1.

## Residuals

**Glyph identity is resolved through the shared vendored face, as the plan
directs, by outline rather than by code.** Character codes are not comparable
between engines (independent subsetting renumbers them), and mapping code to
Unicode to the vendored face's default GID would NOT catch a stylistic
alternate, because both engines' lookups would agree on the default. So the
embedded subset's outline for each code is hashed and looked up in an
outline-to-GID table built once per vendored face file, giving the GID that
glyph occupies in the shared face. The font-file digests in `font_name_map` are
what make that comparable, exactly as the plan states. Glyphs with no outline
(spaces) map to a reserved blank sentinel; a blank-for-blank substitution with a
different advance is caught by the offsets instead. A glyph absent from the
vendored face fails loud.

**Simple (non-Type0) fonts get no glyph identity.** `pdffonts` shows edition
010's body text is entirely CID TrueType Identity-H; the only simple fonts are
Helvetica (not embedded) and `Inter-Regular`, and both appear solely on cover
pages 1 and n, outside the compared domain, as `font_name_map`'s
`cover_faces_note` already records. Their `gids` are the unresolved sentinel on
both legs, so they compare equal rather than false-failing. WP-5.4g, which
brings the covers into the compared domain, must revisit this.

**`3 Tr` (invisible text), for WP-0.2h.** The coordinator asked whether the
render mode should be recorded, skipped, or kept fail-loud. This WP did not
touch render-mode handling and it remains fail-loud. The recommendation is that
if it is ever supported, the render mode be RECORDED as a field of the text
element rather than skipped: invisible text draws nothing a reader can see, but
`pdftotext` extracts it, so Tier S text already compares it, and silently
equating invisible with visible text would let a real difference through. That
is a WP-0.2h decision, not this WP's.

**Cross-WP edit, forced by design.** `fault_suite.clause_vocabulary` in
parity.yaml is WP-0.2d's key, and its `assert_vocabulary_observable` guard
failed with `evaluated clauses absent from clause_vocabulary: ["glyph_positions"]`
until `glyph_positions` was added. WP-0.2d's re-verifier predicted exactly this
handoff for any WP adding a clause. The addition is one line; the
expected-detections matrix is unchanged, since all eight seeded faults are
display-list-visible and none exercises intra-show spacing.

**`worst_excess_pt` is retained but is not the margin metric.** Its maximum is
structurally pinned at glyph 0. `worst_ratio` is the number to read.

**Offsets are excluded from the exact JSON comparison** (`#[serde(skip)]`)
because they require the bound and the shape test rather than equality; `gids`
ARE part of it, because glyph identity is exact. A consequence is that offsets
do not appear in `report.html`.

**Fixture scripts.** `mkfix.py` builds control/drift/kern02/kern005/kern001/
linmatrix/ocmember/annotap by rewriting TJ arrays (inserting per-glyph kerns
computed from the `Tf` size in scope) and by patching resources; `mkfix6.py`
builds glyphsub with fontTools by assigning one glyph's `glyf` entry to
another's. Both are reproduced in the job scratch directory at
`/Users/franguijarro/.claude/jobs/7d99e27f/tmp/`. They are scratch by the
established comparator-WP pattern (WP-0.2e), not committed. A verifier
rebuilding them needs only pypdf and fontTools from the project environment.

**Not attempted, and why.** WP-0.2f could not build bucket-extreme or TRM
fixtures as display-list-EQUAL, because `Td`/`TD` are relative, `cm` composes,
and the display list quantizes device space while operand perturbation happens
in operand space. This WP did not need them: the drift fixture is
display-list-equal by construction (TJ kerns change no recorded field), which is
the floor the plan asks for, and the linear-matrix fixture is a must-FAIL case
rather than a floor case.

## Status

done
