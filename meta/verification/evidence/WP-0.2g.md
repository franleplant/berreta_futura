# WP-0.2g compared cardinality and page rotation

## Base

`521ab79` (`verify(parity): WP-0.2i rework rejected`). Measured against plan
revision 41. The WP-0.2g section itself is unchanged since revision 35; revision
39 added work to this WP by withdrawing WP-0.2f (see the `raster_bound` section
below), and revisions 36 and 38 bind its evidence.

**This WP was rebased twice mid-flight, both times because another WP landed in
`mag/src/parity.rs`, a file two WPs own.** The rebases are recorded because each
one was a near-miss of the clobber class the landing protocol exists to catch,
and because the second changes what a reader should trust about the first:

1. Work began on `022d9d4`. WP-5.3b-i landed `26391ab`, consuming the tracer seam re-exports and taking the `#[allow(unused_imports)]` count from 2 to 1. The stale block was re-synced from HEAD. The shared index was at that point found staging a reversion of WP-5.3b-i in both `mag/src/critic.rs` (dropping `pub mod text;`) and `mag/src/parity.rs`; `git reset` cleared it.
2. WP-5.3b-i then landed `80b7b62`, adding `GLYPH_QUANTUM` to the same re-export line. Rather than re-adding that one line to this WP's copy, this WP's changes were extracted as a patch, `mag/src/parity.rs` was reset to HEAD's blob, and the patch re-applied on top, so that anything else `80b7b62` changed in that file survives whether or not it was noticed. The applied result was checked for the specific failure: `git diff HEAD -- mag/src/parity.rs` contains no line removing `GLYPH_QUANTUM`.

Nothing in this WP reads `Show.x` or `Show.width`, the two fields whose unit
mismatch `80b7b62` repaired, so the rebase carries no semantic dependency on
which side of that fix it landed. See the units paragraph under Metrics.

## Status

`complete`

## Tool versions

- poppler 25.08.0 (`pdfinfo`, `pdftotext`, `pdfimages`), pinned in `parity.yaml tools.poppler`
- rustc / cargo 1.96.0
- display tracer lopdf 0.45.0, unchanged
- pypdf 6.14.2, Python 3.12.11 (`uv run python`), used only to build rotation fixtures

## Commands

Every comparison runs from an isolated working directory, because five other
agents were running concurrently and `out_dir` is hard-coded to
`output/parity/<edition>` with no override flag (see Residual 3). The isolated
directory holds a real `output/` and symlinks to the repository's `editions`,
`meta`, `prompts` and `src`, which is the minimum `mag parity` reads.

The fixture builder writes one `reader.pdf` back through pypdf, applying
`page.rotate(180)` to the named page (`0` means no rotation), so **both** legs of
every pair pass through the identical rewrite and the only difference between
them is `/Rotate`. The block below is the whole replay: run it from the
repository root with the branch checked out and `mag` built.

```sh
set -e
R=$PWD
T=${T:-$(mktemp -d)}
mkdir -p "$T"
A=$R/editions/010/render-2026-09-14T01-47-59
B=$R/editions/010/render-2026-09-14T01-49-02
MAG=$R/mag/target/debug/mag

cat > "$T/rotfix.py" <<'PY'
import sys
from pathlib import Path

from pypdf import PdfReader, PdfWriter

src, out, rotate_page = sys.argv[1], Path(sys.argv[2]), int(sys.argv[3])
reader = PdfReader(src)
writer = PdfWriter()
for n, page in enumerate(reader.pages, start=1):
    if n == rotate_page:
        page.rotate(180)
    writer.add_page(page)
out.parent.mkdir(parents=True, exist_ok=True)
with out.open("wb") as fh:
    writer.write(fh)
PY

mkdir -p "$T/iso/output"
for d in editions meta prompts src; do ln -sfn "$R/$d" "$T/iso/$d"; done

echo "### page 2 carries no text and no images, page 3 carries body text"
pdftotext -f 2 -l 2 "$A/en/reader.pdf" - | tr -d '[:space:]' | wc -c
pdfimages -f 2 -l 2 -list "$A/en/reader.pdf" | tail -n +3 | wc -l
pdftotext -f 3 -l 3 "$A/en/reader.pdf" - | tr -d '[:space:]' | wc -c

uv --directory "$R" run python "$T/rotfix.py" "$A/en/reader.pdf" "$T/rot-control/en/reader.pdf" 0
uv --directory "$R" run python "$T/rotfix.py" "$A/en/reader.pdf" "$T/rot-180/en/reader.pdf"     3
uv --directory "$R" run python "$T/rotfix.py" "$A/en/reader.pdf" "$T/rot-blank/en/reader.pdf"   2

echo "### /Rotate 180 leaves every box identical on the rotated page"
pdfinfo -f 3 -l 3 -box "$T/rot-control/en/reader.pdf" | grep -E 'rot:|MediaBox'
pdfinfo -f 3 -l 3 -box "$T/rot-180/en/reader.pdf"     | grep -E 'rot:|MediaBox'

cd "$T/iso"
V=$T/iso/output/parity/010/verdict.json

echo "### control: identical rewrite both sides, every clause passes"
"$MAG" parity 010 --pre-rendered "$T/rot-control" "$T/rot-control" | tail -13

echo "### page 3 (body text) turned 180"
"$MAG" parity 010 --pre-rendered "$T/rot-control" "$T/rot-180" | tail -13

echo "### page 2 (blank) turned 180: boxes is the only clause that fails"
"$MAG" parity 010 --pre-rendered "$T/rot-control" "$T/rot-blank" | tail -13
python3 -c "import json,sys; print(json.dumps(json.load(open(sys.argv[1]))['tier_s']['boxes']))" "$V"

echo "### A-vs-A, twice, for outcomes and byte determinism"
"$MAG" parity 010 --pre-rendered "$A" "$A" | tail -13
shasum -a 256 "$V" | cut -c1-16
"$MAG" parity 010 --pre-rendered "$A" "$A" > /dev/null
shasum -a 256 "$V" | cut -c1-16

echo "### A-vs-B, twice"
"$MAG" parity 010 --pre-rendered "$A" "$B" | tail -13
shasum -a 256 "$V" | cut -c1-16
"$MAG" parity 010 --pre-rendered "$A" "$B" > /dev/null
shasum -a 256 "$V" | cut -c1-16
```

Suite and lints, from `mag/`:

```sh
cargo fmt && cargo clippy --all-targets -- -D warnings
cargo test
cargo test --test parity_faults
```

`tiers.e.raster_bound` is now optional (see Metrics). That is checked by
physically removing the key from a copy of the spec and running against it,
rather than by reading the branch:

```sh
set -e
R=$PWD
N=${N:-$(mktemp -d)}
mkdir -p "$N/output"
for d in editions prompts src; do ln -sfn "$R/$d" "$N/$d"; done
cp -R "$R/meta" "$N/meta"

uv --directory "$R" run python - "$N/meta/verification/parity.yaml" <<'PY'
import sys, yaml
doc = yaml.safe_load(open(sys.argv[1]))
print("raster_bound removed:", doc["tiers"]["e"].pop("raster_bound", None) is not None)
print("tiers.e keys now:", sorted(doc["tiers"]["e"]))
yaml.safe_dump(doc, open(sys.argv[1], "w"), sort_keys=False)
PY

cd "$N"
"$R/mag/target/debug/mag" parity 010 \
  --pre-rendered "$R/editions/010/render-2026-09-14T01-47-59" \
                 "$R/editions/010/render-2026-09-14T01-47-59" | tail -3
```

## Metrics

### Compared cardinality on 010

Every Tier S and Tier E clause that compares a collection now records what it
compared. The navigation counts are derived from the run, not written down
(rule 9): `links_compared` counts `/Link` subtypes in the annotations actually
collected, and matches the 84 the plan predicted without hard-coding it.

| clause | cardinality reported on 010 A-vs-A |
|---|---|
| `boxes` | 162 boxes, 54 rotations |
| `navigation` | 84 annotations, of which **84 links**, **0 outlines**, **0 title**, **0 lang** |
| `color` | 1720 colour-sequence entries |
| `glyph_positions` | 68800 glyphs over 1488 shows (already reported before this WP) |
| `display_list` | elements per leg (already reported before this WP) |
| `page_count` | 56 vs 56 (a scalar, not a collection) |

The navigation number is the point of the WP: three of its four sub-checks
compare **zero** items on 010, so the clause was reporting `pass` on evidence
that could not discriminate. It still passes, correctly, and now says why.

`text` is not in this WP's Owns. Its compared domain is already reported by
`domain.first_page`, `domain.last_page` and `page_count`, so it is not silent;
no edit was made to `mag/src/parity/text.rs`.

**Every field this WP adds is a dimensionless count, not a length.**
`boxes_compared`, `rotations_compared`, `entries_compared` and navigation's five
counters are `usize` cardinalities; `rotation_mismatches[].a` and `.b` are
degrees, an enumerated quarter-turn. The only lengths the boxes clause reports
are the pre-existing `tolerance_pt` and the box coordinates, both already in
points and both named for it. This matters because WP-5.3b-i's verification
found `mag/src/critic/text.rs` carrying two coexisting quantisations in one
struct, `Show.x` in hundredths of a point against `Show.width` in
`GLYPH_QUANTUM` units, 109.2267 of the latter to one of the former. Nothing
added here derives from `Show.x` or `Show.width`, and nothing added here is in
quanta, so that defect has no path into this verdict.

### `/Rotate`, and whether anything else catches it

`/Rotate` is parsed from the `Page N rot: R` lines that `pdfinfo -f N -l M -box`
already emits alongside the box lines, so it costs no extra invocation. It is
compared **exactly**, not within `box_tolerance_pt`: it is an enumerated
quarter-turn, not a length. `boxes()` asserts it parsed one rotation per page in
the requested range, so a poppler output change cannot silently reduce the
comparison to nothing.

Three fixture runs, each differing from its control by exactly one 180 degree
turn on one page:

| comparison | boxes | text | tier G | color | nav | glyphs | display list | tier V |
|---|---|---|---|---|---|---|---|---|
| `rot-control` vs `rot-control` | pass (0 box, 0 rot) | pass | 0.000 / 0.000 | pass | pass | pass | pass | dims pass, V1/V2 pass, delta 0 |
| `rot-control` vs `rot-180` (page 3, body text) | **fail** (0 box, **1 rot**) | **fail** (1 page) | 325.839 / 551.325 | pass | pass | pass | pass | dims pass, **V1/V2 fail**, delta 241 |
| `rot-control` vs `rot-blank` (page 2, blank) | **fail** (0 box, **1 rot**) | pass | 0.000 / 0.000 | pass | pass | pass | pass | dims pass, V1/V2 pass, **delta 0** |

The recorded mismatch is exactly one entry and names both sides:

```json
"boxes": {
  "status": "fail", "tolerance_pt": 0.05,
  "boxes_compared": 162, "rotations_compared": 54,
  "mismatches": [],
  "rotation_mismatches": [ { "page": 3, "a": 0, "b": 180 } ]
}
```

The control row matters: `rot-control` against itself passes every clause with
the same cardinalities as the untouched pair (162 boxes, 1720 colour entries,
84 annotations, 68800 glyphs), so the pypdf rewrite is inert with respect to
everything the comparator measures, and the failures above are attributable to
`/Rotate` alone rather than to the fixture construction.

**The blank-page row is the one that justifies the clause, and it also corrects
the plan.** Revision 15's wording is that a 180 degree difference "leaves page
dimensions equal, so nothing else would catch it now that rasters are meters".
Measured, that is true for a page whose content is invisible under the turn and
false for a content page: on page 3, `text` and Tier G caught the rotation too,
because `pdftotext` reports rotated coordinates. On the blank inside front
cover, where there is no text to reposition and no image to move, **`boxes` is
the only clause that fails**: text, colour, navigation, per-glyph positions and
the display list all pass, Tier V dimensions agree and the max channel delta is
0. So the blind spot the clause closes is real but narrower than stated: it is
pages whose rendered content is unchanged by the turn, not all pages.

### Comparison mode and self-comparison

`mag parity 010 --pre-rendered X X` previously printed a full green clause list
with nothing to say that both sides were the same bytes. Two lines now precede
the clauses:

```
mode: pre_rendered
self-comparison: both legs hash identically (WARNING: both sides are the same bytes, so no engine comparison happened)
```

`mode` is printed on every run. `self_comparison` is computed from the two legs'
`reader.pdf` SHA-256 values, not from the paths, so a byte-identical copy under
a different path is caught as well; it is a verdict field, so it survives into
`verdict.json` rather than existing only on stdout. Under `--oracle-only`, where
comparing a leg against itself is the intent, the same line reads `(deliberate
for this mode)` instead of the warning.

A-vs-B prints `mode: pre_rendered` and no self-comparison line, as it should.

### Determinism and digests

`verdict.json` (SHA-256, first 16 hex):

| comparison | before this WP | after this WP | repeat run |
|---|---|---|---|
| A-vs-A | `0e21644ee602ff8a` | `468eac3c32c8a4e2` | `468eac3c32c8a4e2` |
| A-vs-B | `6e932ea43678b91a` | `09626f78981b6819` | `09626f78981b6819` |

Both digests changed, and the change is legitimate and expected: `verdict.json`
gained `self_comparison` plus the cardinality fields (`rotations_compared`,
`rotation_mismatches`, `entries_compared`, and navigation's five counters), and
`page_sets_refused` when present. **No clause outcome moved.** Every clause that
passed before passes now, and `tier E raster` remains `not_evaluated`. Each
comparison was run twice and produced a byte-identical verdict, so the file
stays deterministic: it carries no timestamp, duration, hostname or absolute
path.

### `tiers.e.raster_bound`, a key nobody authors

Added to this WP by the coordinator, because revision 39 left a live
inconsistency across two files this WP already owns. Revision 39 withdrew
WP-0.2f **wholly**, and WP-0.2f was the key's owner since revision 9, so
`tiers.e.raster_bound` is now authored by nobody. The comparator nonetheless
still *required* it: `fn raster_bound` resolved the node with
`.context("parity.yaml tiers.e.raster_bound missing")?`, so deleting an
ownerless, decision-free key would have failed every parity run with an error
implying something was wrong with the spec.

Resolved by taking both halves of the coordinator's choice rather than one:

- The code no longer requires the key. A missing node now returns `Ok(None)`, exactly as a present-but-valueless node already did.
- The yaml says, at the top of the key, that it is `status: withdrawn`, `gates: nothing`, `authored_by: nobody`, with the measurements kept as a historical record so they are not repeated, and an explicit instruction not to add a `value` to revive the guard.

**This loosens no threshold** (rule 4). `raster_bound` carries no `value` and
did not carry one before; present-without-value and absent both yield `None`,
and `None` makes the Tier E raster clause report `not_evaluated`. The only
behaviour that changed is that absence is no longer a hard error.

Measured rather than asserted, by removing the key from a copy of the spec and
running against that copy (command above). The run succeeds and prints a clause
list identical to the one with the key present, ending:

```
tier E raster: not_evaluated (WP-0.2d raster_bound derivation)
```

Both the withdrawn-clause record and WP-0.2f's section survive, as revision 39
intended.

### WP-0.2d's fault suite

`cargo test --test parity_faults` passes: `seeded_faults_are_detected ... ok`.
The expected-detections matrix and `clause_vocabulary` in `parity.yaml` are
**unchanged** (`git diff` touches neither key). This is by construction rather
than luck: `assert_vocabulary_observable` enumerates clauses by looking for
nested objects under `tier_s`/`tier_e` that carry their own `status` string, and
the rotation comparison was deliberately folded into the existing `boxes` clause
without a nested `status` of its own, so no new evaluated clause name appears.
`self_comparison` and `page_sets_refused` are top-level verdict fields, outside
both tier objects.

Full suite, on the rebased base `521ab79`: 17 test binaries reporting
`1, 1, 1, 2, 3, 3, 4, 4, 5, 5, 6, 6, 8, 9, 11, 13, 71` passing, which sums to
**153**, and `0 failed` across all 17. Per revision 38's sharpening of rule 9,
that 153 is derived by summing the per-binary list printed above rather than
carried beside it; the list and the total come from the same
`cargo test` output, parsed rather than transcribed. `cargo clippy
--all-targets -- -D warnings` is clean, and `cargo fmt` is a no-op.

## Verdicts

- Compared cardinality is reported by every collection clause in this WP's Owns, and 010's navigation clause now states that it compared 0 outlines, 0 Title and 0 Lang against a link count derived from the run.
- `/Rotate` is compared exactly in Tier S, parsed from the existing `pdfinfo -box` call, and a `/Rotate 180` fixture fails the boxes clause with exactly one recorded mismatch.
- On a page whose content the turn does not move, the boxes clause is the only clause that catches it, so the clause is load-bearing.
- A self-comparison announces itself, and the run's mode is always printed.
- `verdict.json` remains byte-deterministic; its digests changed because its shape changed, and no clause outcome moved.
- WP-0.2d's fault suite passes with its matrix and vocabulary intact.
- `tiers.e.raster_bound` no longer forces a run to fail when a key nobody authors is absent, and the yaml now states that it is withdrawn and gates nothing. No threshold moved.

## Residuals

1. **`page_sets_refused` is implemented but NOT reached by any run in this WP,
   and could not be.** The branch sits behind `legs.digest.is_some()`, which is
   `None` in `--pre-rendered` mode, so only `--oracle-only` and `--run` can
   reach it; and it additionally requires `staleness()` to return `stale`, which
   requires a **seeded** baseline. `meta/verification/baseline.json` currently
   carries `"staged_input_digest": null`, which `staleness()` maps to
   `unseeded`, and `unseeded` counts as fresh. Reaching the branch therefore
   needs either a real oracle render (which writes a new directory into the
   shared 5.9 GB `editions/010` while five other agents are running, and
   `render_leg` fails if it sees more than one new render directory, so a
   concurrent render would break it) or a verifier seeding `baseline.json`,
   which is not this WP's Owns under rule 3. The change is still a strict
   improvement over the previous behaviour, which wrote nothing at all, but it
   is asserted from reading the branch, not measured. **A verifier with a
   seeded, mismatching baseline should run `mag parity 010 --oracle-only` and
   confirm the summary prints `page sets: refused (...)`.** Classified under
   revision 36 as **MESSAGE-ONLY**: the guard tests digest equality, there is no
   numeric threshold to get wrong, so no straddling fixture pair is owed.
2. **`--oracle-only`'s verdict digest was not re-measured**, for the same
   reason: it stages a leg and this WP had no safe way to render one. Its clause
   outcomes are covered indirectly, since `--oracle-only` compares the oracle
   leg against itself and `--pre-rendered A A` performs the identical
   comparison, which is green. The previously recorded `38f91a94...` will change
   for the same shape reason as the other two digests and should be re-recorded
   by whoever next runs that mode.
3. **`out_dir` is hard-coded to `output/parity/<edition>` with no override.**
   Two `mag parity 010` processes were observed running concurrently from
   different agents during this WP, both writing the same `verdict.json`, which
   silently corrupts any digest taken by either. This WP worked around it with
   an isolated working directory; it is not fixed, and it is not in this WP's
   Owns. It is a live hazard for every parity measurement taken while other
   agents run.
4. The rotation assertion compares `a.rotations` against `b`'s map, so a page
   present in A and missing from B records `b: -1`. `-1` is not a legal
   `/Rotate` value, so it is unambiguous, but it is a sentinel rather than a
   typed absence.
5. **The Tier E raster clause's `not_evaluated` reason still reads
   `WP-0.2d raster_bound derivation`**, from `mag/src/parity/raster.rs:106`.
   After revision 39 that owner no longer exists in the sense the string
   implies: nobody is going to derive the bound, because the guard is withdrawn
   rather than pending. `raster.rs` is not in this WP's Owns, so the string is
   left alone and recorded here. Whoever owns `raster.rs` next should make it
   say `withdrawn (revision 39)` rather than naming a derivation that will never
   happen; until then `parity.yaml` carries the correction and the verdict does
   not.
6. This WP was executed in the MAIN working tree rather than a private git
   worktree, against the standing policy that every code-writing worker gets its
   own worktree. By the time the policy was restated the work was already in
   flight and moving it risked losing it. Two index contaminations were found in
   that tree during this WP, neither authored by it, and both were cleared
   before they could be committed. The commit was made with an explicit pathspec
   for exactly this reason.

## What is and is not proven

**Proven.**

- Every collection-comparing clause in `geometry.rs` and `display.rs` reports the cardinality it compared, and those numbers are derived from the data each run actually collected rather than written into the source.
- On 010 specifically, the navigation clause compares 84 annotations of which 84 are links, and 0 outlines, 0 Title and 0 Lang. Two of its three non-link sub-checks are vacuous on this edition and now say so.
- `/Rotate` is read for every page in the compared range, compared exactly, and a single-page 180 degree difference makes the boxes clause fail with one mismatch naming the page and both values.
- There exists a page in the real edition (the blank inside front cover) where that rotation is invisible to every other clause in the ladder, including both raster meters at max channel delta 0. The new comparison is therefore not redundant with any existing clause.
- The fixture construction is inert: the same pypdf rewrite applied to both legs, with no rotation, passes every clause at the same cardinalities as the untouched pair.
- Two runs of the same comparison produce byte-identical `verdict.json`.
- Adding these fields moved no clause outcome, and left WP-0.2d's expected-detections matrix and clause vocabulary untouched.
- A parity run succeeds with `tiers.e.raster_bound` physically absent from the spec, producing the same clause list as with the key present. Measured against a spec copy with the key deleted, not read from the branch.

**Not proven.**

- That `page_sets_refused` ever appears in a real run. See Residual 1: unreachable in `--pre-rendered`, and unreachable anywhere today because the baseline is unseeded. Read from the branch, not measured.
- That `--oracle-only` still reports green, and its new digest. See Residual 2.
- That the plan's claim generalises. It does **not**: on a content-bearing page, `text` and Tier G also catch a 180 degree turn. The claim holds only for pages whose rendered content is unchanged by the turn, and the evidence above states which of the two cases each fixture exercises.
- That `/Rotate` values other than 0 and 180 behave correctly. Only the 0-versus-180 pair was exercised, chosen because it is the case that leaves every box identical; 90 and 270 change the effective page dimensions and would be caught by other clauses anyway.
- Nothing here says the two engines agree on rotation, only that the comparator would notice if they did not. 010's two legs are both WeasyPrint renders.
