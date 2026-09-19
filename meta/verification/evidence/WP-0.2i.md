# WP-0.2i per-glyph positions and glyph identity

## Base

Measured at `20adcfb` (`feat(critic): WP-5.3b-ii PIL-exact page inspection and
the 144 dpi rasterisations`), named per revision 49's rule that a parity figure
is only meaningful against a named commit. Landed on `5bd0c4d` (plan revision
52) after a compare-and-swap refused the earlier base, which is revision 50's
guard working: nothing between the two commits touches `mag/src/parity*`, so no
figure here moves across the rebase (`git diff --name-only 20adcfb 5bd0c4d`
lists `mag/src/model/shared.rs`, `mag/src/typeset/content.rs`, five
`mag/tests/model_shared_*` files and four documents).

The mechanism landed at `be15d6c` and is unchanged by this rework: no file under
`mag/src/` is touched. What changed is the record and the fixture corpus, which
is now committed. The rework was measured once at `e2ebc90` and once again at
`20adcfb` after WP-0.2g landed; every ratio, violation count and excess is
identical at both, and only the verdict digests moved.

## Three rejections, and what each one was

| verify commit | what was rejected | fixed by |
| --- | --- | --- |
| `2f4d443` | the MECHANISM: quantum 0.0001 pt is incommensurate with a Pango tick | `GLYPH_QUANTUM = GLYPH_DRIFT_PT / 8.0` |
| `521ab79` | the RECORD: the floor's generator existed only in a job scratch directory | `mag/tests/parity_glyph_fixtures/mkfixtures.py`, committed |
| `521ab79` | three claims stated more strongly than they measure | restated below, each against a measurement |

The second verifier's finding is the one that shapes this file: *for the gate
specifically, the artifact IS the evidence*, because the gate is the one thing
in this plan nobody can re-derive from the code alone. So the whole fixture
corpus now builds from the checkout by one committed script, and every number
below was re-measured from fixtures that script built.

## The mechanism, unchanged and restated once

`offs` rounds each leg's ABSOLUTE position before differencing, so the recorded
difference is `round(x + d) - round(x)`. With the quantum at 0.0001 pt, one
Pango tick is 0.000732421875 pt = **7.32421875 quanta, not an integer**, so a
constant `d` records as a value alternating between `floor(d/q)` and `ceil(d/q)`
as the fractional part of `x` varies. A FLAT region of the true difference
therefore recorded as a sawtooth, `|v|` decreased, and `axis_shape` rejected it.

That is fatal rather than cosmetic because real drift is mostly flats:
WeasyPrint advances in whole ticks, so at WP-1.6's measured 0.000173 pt per
glyph a tick lands every ~4.2 glyphs and roughly three glyphs in four are flat.

The fix sets the quantum to **one eighth of a tick, 9.1552734375e-05 pt**, so a
tick is an integer number of quanta and `round(x + Nq) = round(x) + N` holds
exactly, making a flat record as flat. It is written as the expression
`GLYPH_DRIFT_PT / 8.0` (`mag/src/parity/streams.rs:40`) so the commensurability
is visible rather than buried in a constant. The new quantum is **1.09x finer**
than the old one, not eight times finer: the 8 is tick/quantum, not old/new.
It therefore tightens and loosens nothing, and `axis_shape`
(`mag/src/parity/display.rs:419`) carries no epsilon. A tolerance on the
monotonicity test would also have made `stairdrift` pass, but that is a
loosening under rule 4 and it would dissolve the property that gives the ceiling
its size-independence; it was not taken.

## The fixture corpus is committed

`mag/tests/parity_glyph_fixtures/mkfixtures.py` builds all **24** fixtures named
in the run loop below, from one rendered edition tree. It replaces **seven**
scratch scripts, counted from this list: `mkfix.py`, `mkfix2.py`, `mkfix6.py`,
`mkdrift.py`, `advkern.py`, `advstep.py`, `vsweep.py`. Three of those seven
`exec`'d a fourth out of an absolute job path, so the floor could not be rebuilt
by anyone but that one job.

- Paths are resolved against the checkout that contains the script
  (`Path(__file__).resolve().parents[3]`), never against an absolute corpus.
- Input and output are overridable by `MAG_PARITY_RENDER_A` and
  `MAG_PARITY_FIXTURES`, and the script ANNOUNCES both, each labelled `env` or
  `checkout default`, as rule 2b requires of an env-gated artifact.
- The render tree is untracked build output (`.gitignore` excludes
  `editions/*/render-*`), so a verifier stages it once; the script fails loud
  naming the exact path it wanted if it is absent, rather than silently
  producing nothing.

What a verifier must stage, and from where: the two matched pre-`5504e5a`
render trees `editions/010/render-2026-09-14T01-47-59` (leg A, and the base of
every fixture) and `editions/010/render-2026-09-14T01-49-02` (leg B), copied
into the checkout at those same paths. They are reproducible by re-rendering
edition 010, and the untracked run directory `editions/010/run-2026-09-13T01-34-51`
is what a re-render needs; that directory is tracked, so it is already present.
The last command block, which tests the base-mismatch hypothesis, reads every
`editions/010/render-*` tree that happens to be staged and reports how many
distinct files it compared, so its conclusion is as wide as what the verifier
staged and says so. Seven were staged here.

Nothing else is needed: no absolute path appears in this file, in the generator,
or in any recorded command, and the whole block below was replayed in a worktree
other than the one it was developed in, which is the only test that separates a
hermetic instruction from one that looks hermetic.

## Commands

Run from the checkout root, with the two render trees staged as above. Every
path is relative to the checkout.

```sh
set -o pipefail
unset TYPST_ROOT
F=.magazine/parity-fixtures
R=editions/010
M=./mag/target/debug/mag
V=output/parity/010/verdict.json
(cd mag && cargo build)
uv run python mag/tests/parity_glyph_fixtures/mkfixtures.py
mkdir -p .magazine/parity-log
run() {
  test -f $V && mv $V $V.prev
  $M parity 010 --pre-rendered "$2" "$3" > .magazine/parity-log/"$1".log 2>&1
  code=$?
  digest=$(test -f $V && shasum -a 256 $V | cut -c1-16 || echo none)
  echo "$1 exit=$code digest=$digest"
  grep -h 'tier E' .magazine/parity-log/"$1".log
}
run AvA1 $R/render-2026-09-14T01-47-59 $R/render-2026-09-14T01-47-59
run AvA2 $R/render-2026-09-14T01-47-59 $R/render-2026-09-14T01-47-59
run AvB1 $R/render-2026-09-14T01-47-59 $R/render-2026-09-14T01-49-02
run AvB2 $R/render-2026-09-14T01-47-59 $R/render-2026-09-14T01-49-02
for f in control drift stairdrift smoothdrift kern02 kern005 kern001 kern00001 \
         linmatrix glyphsub ocmember annotap advstep advmid advtail02 \
         advtail_small advtail_late vq_2q vq_1q vq_half vq_quarter vq_e2 vq_e3 vq_e4; do
  run $f $F/control $F/$f
done
(cd mag && cargo fmt --check && cargo clippy --all-targets -- -D warnings && cargo test)
```

The count reconciliation is one measurement over the same PDF, and needs no
fixtures:

```sh
uv run python - <<'PY'
import re
from pypdf import PdfReader
TJ = re.compile(rb"\[(.*?)\]\s*TJ", re.S)
TJ1 = re.compile(rb"(\([^)]*\)|<[0-9A-Fa-f]*>)\s*Tj")
HEX = re.compile(rb"<([0-9A-Fa-f]*)>")
r = PdfReader("editions/010/render-2026-09-14T01-47-59/en/reader.pdf")
arrays = singles = nibbles = literal = 0
for i, p in enumerate(r.pages):
    d = p.get_contents().get_data()
    for m in TJ.finditer(d):
        arrays += 1
        nibbles += sum(len(h.group(1)) for h in HEX.finditer(m.group(1)))
    hits = list(TJ1.finditer(d))
    if hits:
        singles += len(hits)
        literal += sum(len(m.group(1)) - 2 for m in hits)
        print("page", i + 1, "Tj shows", len(hits), "bytes",
              sum(len(m.group(1)) - 2 for m in hits),
              "render modes", set(re.findall(rb"([0-9]+)\s+Tr", d)))
print("TJ shows", arrays, "glyphs", nibbles // 4, "odd tokens", nibbles % 4)
print("Tj shows", singles, "string bytes", literal)
print("document-wide shows", arrays + singles)
PY
```

The base-mismatch test compares the seven render trees as populations rather
than as totals:

```sh
uv run python - <<'PY'
import glob
import hashlib
import re
from pypdf import PdfReader
TJ = re.compile(rb"\[(.*?)\]\s*TJ", re.S)
HEX = re.compile(rb"<([0-9A-Fa-f]*)>")
vectors = {}
for path in sorted(glob.glob("editions/010/render-*/en/reader.pdf")):
    digest = hashlib.sha256(open(path, "rb").read()).hexdigest()[:16]
    per = []
    for page in PdfReader(path).pages:
        data = page.get_contents().get_data()
        shows = glyphs = 0
        for m in TJ.finditer(data):
            shows += 1
            glyphs += sum(len(h.group(1)) for h in HEX.finditer(m.group(1))) // 4
        per.append((shows, glyphs))
    vectors[path] = (digest, per)
    print(digest, path, "shows", sum(s for s, _ in per), "glyphs", sum(g for _, g in per))
first = next(iter(vectors.values()))[1]
print("distinct files:", len({d for d, _ in vectors.values()}))
print("per-page vectors all identical:", all(v == first for _, v in vectors.values()))
print("interior pages carrying text:", sum(1 for s, _ in first if s))
PY
```

## Tool versions

poppler 25.08.0 (asserted at startup), tracer `lopdf-0.45.0` (asserted),
ttf-parser 0.25 (already a dependency; no crate added, so `mag/Cargo.toml` and
`mag/Cargo.lock` are untouched), rustc 1.96.0, pypdf 6.14.2 and fontTools from
the project environment, Python 3.12.11 through `uv run`.

## Metrics

### Determinism and the corpus

Every parity figure below was measured at base `20adcfb`, by the command block
above, replayed in a worktree that is not the one it was developed in. The two
exceptions are labelled where they appear: the peak-RSS range is carried from
the first submission, and the flat count is derived analytically from the
generator rather than from a run.

| run | exit | glyph clause | ratio | verdict digest (head) |
| --- | --- | --- | --- | --- |
| A-vs-A, run 1 | 0 | pass | 0.0000 | `468eac3c32c8a4e2` |
| A-vs-A, run 2 | 0 | pass | 0.0000 | `468eac3c32c8a4e2` |
| A-vs-B, run 1 | 0 | pass | 0.0000 | `09626f78981b6819` |
| A-vs-B, run 2 | 0 | pass | 0.0000 | `09626f78981b6819` |
| control (pypdf rewrite, no edits) | 0 | pass | 0.0000 | `494e4e1e46ad1698` |

Both digests reproduce byte-identically across consecutive runs, so the corpus
comparison is deterministic. **They are NOT the digests the first submission
recorded** (`0e21644ee602ff8a` and `6e932ea43678b91a`), and that is expected
rather than a discrepancy: those were taken at `e2ebc90`, and WP-0.2g has since
landed compared cardinality and comparison mode into `verdict.json`, so the
document being hashed has more fields. Re-measured at `e2ebc90` during this
rework, the old digests reproduce exactly. This is the named-commit rule making
itself useful: a verdict digest is meaningless without the commit it was taken
at, and both are recorded here.

68,800 glyphs across 1,488 shows over 54 interior pages, unchanged at both
bases. Of those 54, 47 carry text and 7 are full-page plates with no show at
all.

### Floor, ceiling and margin

`worst_ratio` is the maximum over all glyphs of (measured device-space offset
difference) / (k x 0.000732421875 pt), with k reset per show. It is the margin
metric because the maximum EXCESS always lands at glyph 0, where bound and
difference are both zero.

| fixture | what it injects | flats | ratio | viol | result |
| --- | --- | --- | --- | --- | --- |
| **stairdrift** | `tick * round(k * 0.000173 / tick)`, the real staircase | yes, 76.38% | **0.2500** | 0 | **pass, the floor** |
| drift | linear ramp `k * 0.000173` | no | 0.2500 | 0 | pass (control) |
| smoothdrift | linear ramp `k * 0.0005` | no | 0.6250 | 0 | pass (control) |
| kern02 | compensating kern 0.02 pt | - | 10.2500 | 5 | fail (magnitude) |
| kern005 | compensating kern 0.005 pt | - | 2.5625 | 5 | fail (magnitude) |
| kern001 | compensating kern 0.001 pt | - | 0.5625 | 1 | **fail (shape alone)** |
| kern00001 | compensating kern 0.0001 pt | - | 0.0625 | 1 | **fail (shape alone)** |

**Floor 0.2500 on the representative fixture, ceiling 10.2500. Margin
1 / 0.25 = 4.00x against the required 2x. Met.**

**The flats are real rather than nominal**, which is the property the floor
fixture exists to have and the one the linear ramp lacked. Derived analytically
from the generator, which needs no corpus, and printed by the generator itself
on every run:

- **52,549 of 68,800 glyph steps are flat: 76.3794%**, against the predicted
  `1 - rate/tick` = 1 - 0.2362 = 0.7638.
- Moving steps 16,251, or 23.62%.
- "Roughly three glyphs in four do not move" is accurate.

**Rule 11 isolation, and the lesson.** `drift` (no flats) passes; `smoothdrift`
(no flats, HIGHER ratio 0.6250) passes; `stairdrift` (has flats, LOWEST ratio)
failed before the fix and passes after. Remove the flats and the effect goes, at
higher magnitude. **Ratio is not the variable; flatness is.** The lesson for the
record: *a linear ramp is not representative of tick-quantised drift*, and using
one as the floor is what let an unrepresentative fixture certify a broken gate.

### The commensurability law is `n/(8k)`, not sixteenths

The previous submission offered "ratios land on exact sixteenths" as evidence
that the quantum is commensurate with the tick. **That claim is FALSE as
written** and does not survive the fixtures below. The law that fits every
observation is

> ratio = n / (8k)

with `n` the offset difference in quanta and `k` the glyph index of the worst
offender: a recorded offset is an integer count of quanta, and the bound at
glyph `k` is `k` ticks, which is `8k` quanta. Sixteenths is the `k = 2` case,
and it held across the fixtures first tabulated only because their worst
offender happened to sit at k=2.

| fixture | ratio | as `n/(8k)` | k | sixteenth? |
| --- | --- | --- | --- | --- |
| stairdrift, drift | 0.2500 | 2/8 | 1 | yes, coincidentally |
| smoothdrift | 0.6250 | 5/8 | 1 | yes, coincidentally |
| kern00001 | 0.0625 | 1/16 | 2 | yes |
| kern001, advtail_small | 0.5625 | 9/16 | 2 | yes |
| kern005 | 2.5625 | 41/16 | 2 | yes |
| kern02, advtail02 | 10.2500 | 164/16 | 2 | yes |
| advstep, advmid, advtail_late | 0.6406 | **41/64** | 8 | **no** |
| linmatrix | 2.8542 | **137/48** | 6 | **no** |
| vq_2q | 0.0250 | **2/80** | 10 | **no** |
| vq_1q, vq_half, vq_quarter, vq_e2 | 0.0125 | **1/80** | 10 | **no** |

Four distinct denominators appear (8, 16, 48, 64, 80), and the three
counterexample families would each have read as a broken claim to anyone who
checked "sixteenths" against them.

This **CONFIRMS commensurability more strongly than the sixteenths claim did**,
and is a strengthening rather than a retreat: an exact `n/(8k)` for every
fixture at every k is precisely what an integer tick/quantum ratio predicts,
whereas sixteenths covered only the subset whose worst offender sat at k=2. Had
the quantum stayed incommensurate, no such law would hold at any k.

### Size-independence, and its measured detection floor

The previous submission carried "a compensating kern fails on shape whatever its
magnitude". **That is not literally true, and rule 10 requires saying so rather
than rounding it up.** The `vq_*` family measures where it stops: a mid-show
compensating bump that displaces at glyph 10 and returns at glyph 20, applied to
every TJ array of 25 or more glyphs across all 54 interior pages, at seven
magnitudes counted from this list: 2Q, Q, Q/2, Q/4, Q/100, Q/1000, Q/10000,
**seven**, where Q is `GLYPH_QUANTUM` = 9.1552734375e-05 pt.

| amount | pt | ratio | violations | result |
| --- | --- | --- | --- | --- |
| 2Q | 1.83e-04 | 0.0250 | 40 | **fail** |
| Q | 9.16e-05 | 0.0125 | 40 | **fail** |
| Q/2 | 4.58e-05 | 0.0125 | 40 | **fail** |
| Q/4 | 2.29e-05 | 0.0125 | 40 | **fail** |
| Q/100 | 9.16e-07 | 0.0125 | 40 | **fail** |
| Q/1000 | 9.16e-08 | 0.0000 | 0 | pass, invisible |
| Q/10000 | 9.16e-09 | 0.0000 | 0 | pass, invisible |

**So there IS a detection floor, between 9.16e-08 and 9.16e-07 pt.** The
accurate statement is: a compensating kern fails on shape at **every physically
reachable magnitude**, with a measured detection floor at about 1e-7 pt. That
floor is ~7,000x below one Pango tick and ~1,700x below one glyph's legitimate
drift of 0.000173 pt; at 300 dpi it is 4e-5 of a pixel. The gate is
size-independent across every magnitude that can physically exist, and is not
size-independent across all reals. The evidence says the former.

**The mechanism, which is why size-independence holds and which must stay beside
the number.** The naive prediction is that a bump below half a quantum rounds to
zero everywhere and goes invisible. **That prediction is wrong.** Base offsets
are spread across the quantum grid, so among 68,800 glyphs some always sit near
a rounding boundary and cross it. The table shows it directly: Q/2, Q/4 and
Q/100 span a factor of 200 in magnitude, every one records as the SAME one
quantum at k=10 (ratio 1/80), and every one produces the same 40 violations.
The magnitude of the fault has stopped mattering; only its shape has. This is
the same mechanism WP-0.2f found on the raster side, where any nonzero shift
crosses a rounding boundary for some glyph, now working FOR the gate instead of
against it. A bare number without this reasoning invites the next reader to
simplify back to the overclaim.

**Size-independence at larger magnitudes, from the inherited adversarial
family.** All five variants still fail under the new quantum, three of them on
SHAPE ALONE with `worst_excess_pt` exactly 0.000000, meaning the magnitude bound
contributed nothing and the shape constraint did all the work:

| variant | ratio | violations | caught by |
| --- | --- | --- | --- |
| advstep | 0.6406 | 1 | shape alone |
| advmid | 0.6406 | 1 | shape alone |
| advtail02 | 10.2500 | 9 | magnitude |
| advtail_small | 0.5625 | 1 | shape alone |
| advtail_late | 0.6406 | 1 | shape alone |

`kern00001` is the same point at the small end: a compensating kern of 0.0001 pt
sits at 6.25% of the magnitude bound, is about one quantum, is 200x smaller than
the smallest ceiling fixture the plan asked for, and is still caught on shape
alone.

### The five must-fail fixtures

| fixture | must fail on | observed |
| --- | --- | --- |
| `kern02`, compensating kern 0.02 pt | shape | fail, exit 1, ratio 10.2500, 5 violations, worst excess 0.013550 pt |
| `linmatrix`, linear matrix below half a quantum over a full-measure line | per-glyph magnitude | fail, exit 1, ratio 2.8542, 9 violations, worst excess 0.011169 pt |
| `glyphsub`, equal-advance glyph substitution | glyph identity | fail, exit 1, display list on 12 pages |
| `ocmember`, optional-content membership | fail-loud stop | `error: tracing page 4 ...: operator BDC: optional content membership unsupported (fail loud per Tier E): <</Type /OCG/Name /Hidden>>` |
| `annotap`, annotation carrying `/AP` | fail-loud stop | `error: annotations page 3: annotation Link carries an appearance stream, which the display list does not compare (fail loud per Tier E)` |

The glyph-substitution fixture is fully isolated, which took three attempts and
is worth recording because the first two were not. Patching the PDF's `W` array
and `ToUnicode` to make one CID impersonate another changed the advance (ratio
1242) and, because every CID in a subset is used somewhere, changed the decoded
text on 12 pages. The committed generator implements the third approach: it
patches the EMBEDDED FONT so CID `0x0089` (`F`) draws `A`'s outline, leaving the
content stream, the `W` widths and the `ToUnicode` map untouched, and it prints
which CIDs it chose. The result is exactly the blind spot the plan names:

- `tier_s text`: **pass** (the decoded string is unchanged)
- `glyph_positions`: **pass, ratio 0.0000, 0 violations** (the advance is unchanged)
- `display_list`: **fail on 12 pages**, caught by `gids` alone

Glyph count cannot see it (same count), the string cannot see it, and the
offsets cannot see it. Only the mapping to the shared vendored face does.

### Cost

Full run 80 to 83 s (debug build, measured across the 28 runs of the block above) against 82 s before this WP, so the
per-glyph work costs a few seconds, against the 9 to 15 minutes WP-0.2f measured
for supersampled rasterization. The finer quantum changes neither runtime nor
dump size, only the integer magnitudes. Added dump data is 68,800 glyphs x (two
`i64` offsets plus one `u32` gid) = about 1.4 MB per leg. The comparison is O(n)
in glyphs.

Labelled rather than carried silently (rule 10): the peak-RSS range of 246 MB to
779 MB comes from the FIRST submission and was not re-measured here, because
nothing in this rework changes allocation.

## The inherited count, reconciled

Revision 42's clause: a CITED count is re-derived at the point of citation. Both
figures are re-derived here from the artifact they are cited from, which is one
PDF, `editions/010/render-2026-09-14T01-47-59/en/reader.pdf`, by the command
block above.

| domain | shows | glyphs | how derived |
| --- | --- | --- | --- |
| compared domain: 54 interior pages, `TJ` shows in Type0 Identity-H | **1,488** | **68,800** | the clause itself, and independently 275,200 hex nibbles / 4, with zero odd-length hex tokens and zero literal strings inside any TJ array |
| whole document, 56 pages, both covers added | **1,503** | 69,337 | the above plus 15 `Tj` shows carrying 537 string bytes, which in a simple font is 537 glyph codes, no escape sequences appearing in any of them |
| the plan's figure, inherited from the withdrawn WP-0.2f | 1,503 | 69,071 | not reproducible, see below |

**The show count reconciles exactly, and the plan's hypothesis is CONFIRMED.**
The 15-show gap is the two covers and nothing else: 5 shows on page 1 and 10 on
page 56, every one of them a `Tj` rather than a `TJ`, every one in the simple
font `F1`, and every one at render mode `3 Tr`, invisible. 1,488 + 15 = 1,503,
and no other page in the document carries a `Tj`. The compared domain is not a
matter of interpretation either: `verdict.json` records it as
`"interior: reader.pdf pages 2..n-1"`, first page 2, last page 55. So both show
figures are correct for their own domain, and each must be written with that
domain attached.

**The glyph count does NOT reconcile, and that half is a real divergence.** The
same covers that supply the 15 shows supply 537 string bytes, 166 on the front
and 371 on the back, so the document-wide total under the counting that yields
1,503 is 69,337, not 69,071. 69,071 sits between the interior figure and the
document-wide figure and equals neither. I could not reproduce it from the cited
artifact under any counting I could construct: not string bytes (537 gives
69,337), not non-space bytes (450 gives 69,250), not either cover alone (166
gives 68,966, 371 gives 69,171). WP-0.2f records no producing command for the
figure, WP-0.2f is withdrawn, and it has no verification file, so there is no
second artifact to check it against.

**A base mismatch is ruled out for this pair, by the strongest available test:
the two figures come from the SAME FILE.** WP-0.2f's own `## Commands` block
names `R=editions/010/render-2026-09-14T01-47-59/en/reader.pdf` as the oracle
leg every one of its fixtures was built from, and that is the file measured
above. No difference of commit, render or asset can stand between two numbers
taken from one artifact, so only the domain, or an error, is left.

Tested anyway, since "a parity figure is only meaningful against a named commit"
is a good rule and worth removing as a cause rather than arguing away: the seven
010 render trees present in the checkout are seven DISTINCT files (seven distinct
sha256, sizes 87,139,111 to 87,139,128 bytes, spanning 2026-09-13T12:57 to
2026-09-14T01:49 and therefore several bases). All seven give 1,488 shows and
68,800 glyphs on the interior, and 1,503 shows document-wide.

**Compared as populations, not as aggregates** (revision 45): the test is not
that the seven totals agree, which two different populations can do by
coincidence, but that the per-page `(shows, glyphs)` vector over all 56 pages is
elementwise IDENTICAL across all seven renders. It is. Vary the base and neither
the aggregate nor the population moves. The scope of that test is stated rather
than overclaimed: it covers the seven renders in this checkout, and not
`c1253d8`, which is not here.

**Cause, named.** The two figures were derived over different domains from one
file; the show halves differ by exactly that and reconcile exactly; the glyph
half of 69,071 is not a domain difference but an unreproducible number. What
should be carried forward is **68,800 glyphs and 1,488 shows over the compared
domain of 54 interior pages**, which is exact and independently derived twice
above. 1,503 is correct for the whole document and should always be written with
that domain. 69,071 should be dropped rather than re-cited; 69,337 is the
document-wide glyph figure if one is ever wanted.

**WP-5.5a's 68,530 glyphs / 1,501 shows is a third population and is NOT folded
in.** It was measured over a different render pair at base `c1253d8`, after the
source-codes asset landed, and WP-5.5a correctly declined to reconcile it
against either figure because it is an independent measurement rather than a
citation. Folding it in would be exactly the error rule 11 warns about: picking
whichever story accounts for the most numbers. It does carry the useful lesson,
which this WP endorses and which its own reconciliation does not need: a parity
cardinality should travel with the commit it was taken at, as well as with its
domain.

## Inherited obligations from revision 39

Revision 39 withdrew WP-0.2f wholly and made this WP the sole owner of the
gate's floor, handing down the `drift` fixture and the CTM-composing
recommendation. Both are named here rather than left silent, which is what the
previous submission failed to do.

**The CTM-composing recommendation: DISCHARGED, and its premise FALSIFIED.**
The plan instructs deriving the floor with a CTM-composing perturbation applied
in device space through the Rust tracer, on the stated premise that perturbing
raw operands through pypdf cannot produce display-list-equal fixtures. This WP
did not follow the recommendation and did not need to, because the
recommendation exists in order to obtain a display-list-equal floor and the
pypdf-built floor already is one: `display_list` reports **pass** for
`stairdrift`, `drift` and `smoothdrift` alike, in the same runs as
`glyph_positions` pass, tabulated above.

The premise is therefore false for the TJ-kern class, and mechanically rather
than luckily so: a TJ kern changes no field the display list records. It moves
glyphs inside a show, while the display list records the show's origin and its
text, neither of which a kern touches. The premise does hold for the
perturbations WP-0.2f actually attempted, where `Td`/`TD` are relative and `cm`
composes. Recorded as a rule-11 falsification of a plan claim rather than left
as an argument.

**The inherited `drift` fixture is demoted to a control; `stairdrift` is the
floor.** `drift` is a linear ramp, and a linear ramp is not representative of
tick-quantised drift: it never goes flat, so it never exercises the identity the
quantum defect broke. That is what let an unrepresentative fixture certify a
broken gate, and it is the lesson worth carrying. The demotion is still prose
rather than test code, because no `parity_glyphs` cargo target exists and the
corpus is produced by a generator rather than asserted by a test. What has
changed since the last verification is that the generator is committed, so the
demotion now names artifacts any checkout can rebuild; binding the corpus into
`cargo test` is left to whichever WP brings a staged render tree under rule 2b's
env gate.

## Verdicts

All at base `20adcfb`, digest head being the first 16 hex of
`shasum -a 256 output/parity/010/verdict.json`, exit 0 = pass and 1 = fail.

| fixture | exit | digest (head) | fixture | exit | digest (head) |
| --- | --- | --- | --- | --- | --- |
| A-vs-A (x2) | 0 | `468eac3c32c8a4e2` | advstep | 1 | `0c12d7a62f688784` |
| A-vs-B (x2) | 0 | `09626f78981b6819` | advmid | 1 | `a0b0f44deb108a4e` |
| control | 0 | `494e4e1e46ad1698` | advtail02 | 1 | `52c02c4c28aaeebd` |
| drift | 0 | `bb6dc69d643f933d` | advtail_small | 1 | `4b54c1f0e2606289` |
| stairdrift | 0 | `df9909eeb8c68057` | advtail_late | 1 | `c3756e274c23e606` |
| smoothdrift | 0 | `cf7376d833853612` | vq_2q | 1 | `3c3479b0ae488b99` |
| kern02 | 1 | `40d61b72f0daa2b9` | vq_1q | 1 | `c408a87501e26373` |
| kern005 | 1 | `c768f28a0a19fed0` | vq_half | 1 | `ceddd179c6dc58f5` |
| kern001 | 1 | `b627c661ed777326` | vq_quarter | 1 | `37c2531a3999b6e9` |
| kern00001 | 1 | `984c7ea44dd54011` | vq_e2 | 1 | `34fbab168991eae9` |
| linmatrix | 1 | `372f53f82cb29adc` | vq_e3 | 0 | `eec4fa1a6a137b4e` |
| glyphsub | 1 | `d6a545a433a25c6b` | vq_e4 | 0 | `cbcaba0d705305a1` |
| ocmember | 1 | none | annotap | 1 | none |

`ocmember` and `annotap` write no verdict because they fail loud during tracing,
which is the required behaviour; their evidence is the error text and exit 1,
and the command block reports their digest as `none` rather than silently
hashing a stale file from the previous run.

The fixture PDFs themselves differ byte-wise from the first submission's,
because the committed generator emits every kern operand at `%.9f`, where four
of the seven scratch scripts used `%.6f` and two used `%.9f` (the seventh emits
no kerns). Every ratio, violation count and excess is
unchanged by that, which is the check that matters: the finer operand is a
strictly closer approximation of the intended displacement.

`cargo fmt --check` clean; `cargo clippy --all-targets -- -D warnings` clean;
`cargo test` 18 result lines summing to **181 passed, 0 failed**. The whole
extracted command block exits 0.

## Residuals

**The f32 question is CLOSED and this clause does not depend on WP-0.2j.**
lopdf parses `Object::Real` as f32, but `num()` converts once via `f64::from`
and `tx`, `starts` and `qo` are all f64. The f32 terms (font size, `Tm`/`cm`,
widths) therefore enter as RELATIVE SCALE errors proportional to the value, so
they add a monotone ramp rather than per-step noise, which is why `drift` and
`smoothdrift` produce zero violations across 68,800 glyphs. Against the bound
the effect is about 0.13% at k=1 and 0.08% at k=70. WP-0.2j is not a
prerequisite for this clause.

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
brings the covers into the compared domain, must revisit this, and the count
reconciliation above says exactly what it will add: 15 shows on two pages.

**`3 Tr` (invisible text), for WP-0.2h.** The coordinator asked whether the
render mode should be recorded, skipped, or kept fail-loud. This WP did not
touch render-mode handling and it remains fail-loud. The recommendation is that
if it is ever supported, the render mode be RECORDED as a field of the text
element rather than skipped: invisible text draws nothing a reader can see, but
`pdftotext` extracts it, so Tier S text already compares it, and silently
equating invisible with visible text would let a real difference through. That
is a WP-0.2h decision, not this WP's. The reconciliation above shows the whole
of 010's invisible text is the 15 cover shows.

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

**The fixture corpus is committed, which departs from the comparator-WP
pattern.** WP-0.2e established that comparator fixtures stay scratch. That
pattern is right for a fixture that demonstrates a clause and wrong for one that
IS a threshold: `stairdrift` sets the floor that the 4x margin is measured
against, and Phase 3 and Phase 4 are licensed by that margin. The generator is
therefore committed under `mag/tests/`, with the fixture PDFs themselves left
untracked build output because they are large and exactly reproducible. No cargo
test consumes the script yet; it is a generator, not a test, and a
`parity_glyphs` test target that runs it over a staged render tree is the
natural next step for whichever WP brings the corpus under `cargo test`.

**Not attempted, and why.** WP-0.2f could not build bucket-extreme or TRM
fixtures as display-list-EQUAL, because `Td`/`TD` are relative, `cm` composes,
and the display list quantizes device space while operand perturbation happens
in operand space. This WP did not need them: the drift fixtures are
display-list-equal by construction and by measurement, which is the floor the
plan asks for, and the linear-matrix fixture is a must-FAIL case rather than a
floor case.

## Status

done
