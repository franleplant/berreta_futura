# WP-0.2k seed the baseline and make the ratchet operative

## Base

`8a03c1a` (`docs(verification): retrospective provenance audit of parity-derived
numbers`), measured against plan revision 53. The measurements below were
taken at `20adcfb`, which is also `baseline.json`'s `seeded_at_commit`.

Work began on `be5258d` and was rebased three times, onto `20adcfb`, `62e665a`
and `8a03c1a`. Nothing that landed in any interval touches `mag/src/parity*`. The
rebases are recorded because this WP SEEDS a digest over the staged corpus, so a
landing in between could have invalidated the seed silently. Neither did, and
that is measured rather than assumed: the 57 staged inputs of the seeding render
were intersected with the changed-file list of each interval,
`git diff --name-only be5258d 20adcfb` (57 files),
`git diff --name-only 20adcfb 62e665a` (13 files) and
`git diff --name-only 62e665a 8a03c1a` (1 file), and ALL THREE intersections are
EMPTY. The re-run after the first rebase reproduces `e48eb5c6...` and reports
`fresh`, and the evidence replay at `20adcfb` re-derives the same digest from an
independent render in a separate worktree.

## Status

`done`

## The seed, and the commit it is anchored to

`meta/verification/baseline.json` now carries

- `staged_input_digest: e48eb5c638a0f25bfdfbb5e26bc989d56c1ecbac3ef85f103e90ed1ac8aac5fa`
- 54 page entries, pages 2 through 55, each `tier: none` with no passing Tier S
  clauses.

**Seeded at commit `20adcfb`**, recorded in the file itself as
`seeded_at_commit: 20adcfb81cc866cd26870c5cac0623868c75c324` rather than only in
this evidence (the named-commit rule). Every future ratchet comparison inherits
that base: the digest is over the 57 staged inputs of edition 010 as they stand
at `20adcfb`, and a later WP that quotes a per-page tier without naming this base
is quoting an unanchored figure. The commit is deliberately left at the point the
digest was MEASURED rather than bumped to the landing base; whether it is still
current at any later commit is answered by running `mag parity`, which now says
`fresh` or refuses.

**Why the pages are seeded at `none` rather than at what the seeding run
measured.** The seeding run is `mag parity 010 --oracle-only`, which compares the
WeasyPrint leg against itself. A first implementation proposed `tier: E` with five
passing clauses for all 54 pages, which is what an identity comparison always
yields, and recording it would have put the plan's terminal claim into the
baseline before any typst leg exists. That is the vacuity class of rule 10 written
into a file, so the comparator now REFUSES to measure page entries from a
self-comparison at all (`ratchet: self_comparison`, `pages_measured: 0`, no
proposal written), and the 54 rows were authored at `none`: the engine pair has
achieved nothing yet, because there is no pair. `mag/src/typeset/mod.rs` still
bails on `--engine typst`, which is what a bare `mag parity 010` reports.

## Commands

Every block runs from `$PWD` = the root of a git worktree checked out at this
WP's commit. `mag parity` reads `meta/verification/parity.yaml`, `editions/` and
`meta/verification/baseline.json` relative to the working directory and refuses
to run outside a repository root, so an isolated run directory must be a
worktree, not a bare directory. The untracked run directory is NOT needed:
`editions/010/run-2026-09-13T01-34-51` is tracked (21 files), so a fresh worktree
carries it. A full replay renders edition 010 three times, about 90 s each.

### Lints and the suite

```sh
set -e -o pipefail
cd "$PWD/mag"
cargo fmt --check
cargo clippy --all-targets -- -D warnings
cargo test 2>&1 | grep -E '^test result' | \
  awk '{gsub(/\./,"",$4); n+=$4; b++} END {print b" binaries, "n" tests"}'
```

### The seed, re-derived independently of the comparator

```sh
set -e -o pipefail
R=$PWD
MAG=$R/mag/target/debug/mag
cd "$R/mag" && cargo build && cd "$R"

MAG_PARITY_OUT_DIR=$R/output/parity/010 "$MAG" parity 010 --oracle-only | \
  grep -E '^(mode|self-comparison|staged inputs|page sets|ratchet)'

uv run python - "$R" <<'PY'
import hashlib, json, sys
from pathlib import Path
root = Path(sys.argv[1])
cache = json.loads((root / "output/parity/010/oracle-cache.json").read_text())
rows = json.loads((Path(cache["render_dir"]) / "request.json").read_text())["inputs"]
entries = sorted(
    f"{r['targetPath']}\x1f{hashlib.sha256(Path(r['sourcePath']).read_bytes()).hexdigest()}"
    for r in rows
)
digest = hashlib.sha256("\x1e".join(entries).encode()).hexdigest()
seeded = json.loads((root / "meta/verification/baseline.json").read_text())
print("staged inputs:", len(rows))
print("re-derived digest:", digest)
print("committed digest:", seeded["staged_input_digest"])
print("agree:", digest == seeded["staged_input_digest"])
print("page entries:", len(seeded["pages"]),
      sorted({(p["tier"], tuple(p["s_clauses_passing"])) for p in seeded["pages"].values()}))
PY
```

### What the guard does in each mode, read off real verdicts

```sh
set -e -o pipefail
R=$PWD
MAG=$R/mag/target/debug/mag
D=$(uv run python -c "import json,sys;print(json.load(open(sys.argv[1]))['render_dir'])" \
      "$R/output/parity/010/oracle-cache.json")

MAG_PARITY_OUT_DIR=/tmp/wp02k-pre "$MAG" parity 010 --pre-rendered "$D" "$D" | \
  grep -E '^(mode|self-comparison|staged inputs|ratchet)'

for v in "$R/output/parity/010/verdict.json" /tmp/wp02k-pre/verdict.json; do
  uv run python - "$v" <<'PY'
import json, sys
d = json.load(open(sys.argv[1]))
print(sys.argv[1], "mode:", d["mode"])
print("  keys:", list(d))
print("  staged_input_digest present:", "staged_input_digest" in d)
print("  staleness:", json.dumps(d["staleness"]))
print("  ratchet:", json.dumps(d["ratchet"]))
PY
done
```

### Determinism, and what a recorded verdict digest is worth

```sh
set -e -o pipefail
R=$PWD
MAG=$R/mag/target/debug/mag
OLD=$(uv run python -c "import json,sys;print(json.load(open(sys.argv[1]))['render_dir'])" \
        "$R/output/parity/010/oracle-cache.json")

for i in 1 2; do
  MAG_PARITY_OUT_DIR=/tmp/wp02k-aa "$MAG" parity 010 --pre-rendered "$OLD" "$OLD" > /dev/null
  shasum -a 256 /tmp/wp02k-aa/verdict.json | cut -c1-16
done

mv "$R/output/parity/010/oracle-cache.json" /tmp/wp02k-cache-kept.json
MAG_PARITY_OUT_DIR=$R/output/parity/010 "$MAG" parity 010 --oracle-only | \
  grep -E '^(staged inputs|ratchet|tier)'
NEW=$(uv run python -c "import json,sys;print(json.load(open(sys.argv[1]))['render_dir'])" \
        "$R/output/parity/010/oracle-cache.json")
shasum -a 256 "$OLD/en/reader.pdf" "$NEW/en/reader.pdf" | cut -c1-20

for i in 1 2; do
  MAG_PARITY_OUT_DIR=/tmp/wp02k-ab "$MAG" parity 010 --pre-rendered "$OLD" "$NEW" > /tmp/wp02k-ab.out
  shasum -a 256 /tmp/wp02k-ab/verdict.json | cut -c1-16
done
grep -E '^(mode|self-comparison|tier)' /tmp/wp02k-ab.out
```

### The stale corpus: refused in every staged mode, with no verdict written

```sh
set -e -o pipefail
R=$PWD
MAG=$R/mag/target/debug/mag
F=editions/010/run-2026-09-13T01-34-51/articles/an-alignment-assessment-of-recent-cybersecurity/final.md
printf '\n' >> "$R/$F"

mkdir -p /tmp/wp02k-stale
refused () {
  set +e
  MAG_PARITY_OUT_DIR=/tmp/wp02k-stale "$MAG" parity 010 "$@" > /tmp/wp02k-stale.out 2> /tmp/wp02k-stale.err
  echo "mag parity 010 $* -> exit $?"
  set -e
  tail -1 /tmp/wp02k-stale.err
}
refused
refused --oracle-only
refused --oracle-only --set body
echo "files written: $(ls /tmp/wp02k-stale)"

git -C "$R" show "HEAD:$F" > "$R/$F"
git -C "$R" status --porcelain -- editions
```

The three modes are invoked through a function taking `"$@"` rather than through
a loop over a string, because the loop form is a REAL defect this evidence's own
rule-12 replay caught: `zsh` does not word-split an unquoted `$mode`, so
`--oracle-only --set body` reached clap as a single argument and the third case
exited 2 on a usage error while the caption claimed three refusals. The command
worked when typed by hand and broke when transcribed into a loop, which is the
shape rule 12 names. Counting the failures against the caption, per revision 52,
is what surfaced it.

### The base commit's behaviour on the same stale corpus (rule 11)

Builds `be5258d` in its own worktree and runs THAT binary against THIS
worktree's seeded baseline, which is the configuration WP-0.2g could not
reach because the baseline was unseeded.

```sh
set -e -o pipefail
R=$PWD
B=${B:-$R-base}
[ -d "$B" ] || git -C "$R" worktree add "$B" be5258d
(cd "$B/mag" && cargo build)
F=editions/010/run-2026-09-13T01-34-51/articles/an-alignment-assessment-of-recent-cybersecurity/final.md
printf '\n' >> "$R/$F"

set +e
"$B/mag/target/debug/mag" parity 010 --oracle-only > /tmp/wp02k-base.out 2>&1
echo "base binary exit: $?"
set -e
grep -E '^(mode|staged inputs|page sets|verdict)' /tmp/wp02k-base.out
uv run python -c "import json;d=json.load(open('$R/output/parity/010/verdict.json'));print('page_sets_refused:', json.dumps(d.get('page_sets_refused')))"

git -C "$R" show "HEAD:$F" > "$R/$F"
```

### The concurrency hazard, measured on the base commit and on this one

```sh
set -e -o pipefail
R=$PWD
B=${B:-$R-base}
(cd "$R/mag" && cargo test --test parity_concurrent -- --nocapture)
E=$R/output/parity-concurrent/equal
D=$R/output/parity-concurrent/differing
status () { uv run python -c "import json,sys;print(json.load(open(sys.argv[1]))['tier_e']['display_list']['status'])" "$1"; }

echo "### base commit: one hard-coded out dir, two concurrent runs of one edition"
for i in 1 2 3; do
  set +e
  "$B/mag/target/debug/mag" parity conc-demo --pre-rendered "$E" "$E" > /tmp/p1.out 2>&1 &
  P1=$!
  "$B/mag/target/debug/mag" parity conc-demo --pre-rendered "$E" "$D" > /tmp/p2.out 2>&1 &
  P2=$!
  wait $P1; R1=$?; wait $P2; R2=$?
  set -e
  echo "round $i: A-vs-A exit=$R1 printed $(grep -o 'tier E display list: [a-z]*' /tmp/p1.out); A-vs-B exit=$R2 printed $(grep -o 'tier E display list: [a-z]*' /tmp/p2.out); the one verdict.json holds $(status "$R/output/parity/conc-demo/verdict.json")"
done

echo "### this commit: one shared out dir, two concurrent runs"
for i in 1 2 3; do
  set +e
  MAG_PARITY_OUT_DIR=/tmp/shared-out "$R/mag/target/debug/mag" parity conc-demo --pre-rendered "$E" "$E" > /tmp/q1.out 2>&1 &
  P1=$!
  MAG_PARITY_OUT_DIR=/tmp/shared-out "$R/mag/target/debug/mag" parity conc-demo --pre-rendered "$E" "$D" > /tmp/q2.out 2>&1 &
  P2=$!
  wait $P1; R1=$?; wait $P2; R2=$?
  set -e
  echo "round $i: exits $R1/$R2, refusals $(grep -l 'another mag parity run holds' /tmp/q1.out /tmp/q2.out | wc -l | tr -d ' '), lock left $(ls /tmp/shared-out/run.lock 2>/dev/null || echo none)"
done

echo "### this commit: one out dir each, two concurrent runs"
for i in 1 2 3; do
  set +e
  MAG_PARITY_OUT_DIR=/tmp/out-a "$R/mag/target/debug/mag" parity conc-demo --pre-rendered "$E" "$E" > /dev/null 2>&1 &
  P1=$!
  MAG_PARITY_OUT_DIR=/tmp/out-b "$R/mag/target/debug/mag" parity conc-demo --pre-rendered "$E" "$D" > /dev/null 2>&1 &
  P2=$!
  wait $P1; R1=$?; wait $P2; R2=$?
  set -e
  echo "round $i: A-vs-A exit=$R1 verdict=$(status /tmp/out-a/verdict.json); A-vs-B exit=$R2 verdict=$(status /tmp/out-b/verdict.json)"
done
```

### The ratchet against the committed baseline

```sh
set -e -o pipefail
cd "$PWD/mag"
cargo test --test parity_ratchet -- --nocapture 2>&1 | grep -E 'MODE|test result'
cargo test --bin mag ratchet_rules -- --nocapture 2>&1 | grep -E '^test |test result'
cargo test --bin mag measured_pages -- --nocapture 2>&1 | grep -E '^test |test result'
```

## Tool versions

- rustc / cargo 1.96.0
- poppler 25.08.0 (`pdfinfo`, `pdftotext`, `pdftoppm`), pinned in `parity.yaml tools.poppler`
- display tracer lopdf 0.45.0, unchanged
- Python 3.12.11 through `uv run python`; no new crate or package

## Metrics

### What each mode does about staleness, read off emitted verdicts

The coordinator's finding is confirmed from real files rather than from the
struct: `staged_input_digest` is `skip_serializing_if = "Option::is_none"` and is
populated only by the modes that stage their own inputs, so a `--pre-rendered`
verdict carries no such key. Before this WP the `staleness` field was optional in
the same way, so `--pre-rendered`, the mode most WPs use, emitted NOTHING about
the guard. It now always emits a status.

| mode | `staged_input_digest` key | `staleness.status` | stale corpus | ratchet page comparison |
|---|---|---|---|---|
| `--pre-rendered` | absent | `not_staged` | cannot arise: nothing was staged | `not_evaluated` |
| `--oracle-only` | present | `fresh` / `stale` / `unseeded` | run REFUSED | `self_comparison` (both legs are one dir) |
| bare / `--run` | present | `fresh` / `stale` / `unseeded` | run REFUSED | `pass` / `fail` once a typst leg exists |
| `--set <name>` | present | as above | run REFUSED | as above |

The `not_staged` status is a real constraint stated, not a defect papered over:
`--pre-rendered` is handed two finished trees and never sees an input, so no
digest exists for it to check. The summary now says so in words:

```
staged inputs: not_staged (the comparator did not stage these inputs, so no digest exists and the baseline vouches for nothing)
```

The committed-baseline half of the ratchet is NOT mode-dependent: it runs before
staging, so `--pre-rendered` reports `ratchet: not_evaluated (54 committed entries
checked, ...)` and a lowered working-tree baseline refuses that mode too.

Top-level verdict keys, enumerated from the two emitted files:

- `--oracle-only`: `edition, mode, staged_input_digest, staleness, page_sets, ratchet, self_comparison, inputs, domain, tier_s, tier_g, tier_v, tier_e`
- `--pre-rendered`: `edition, mode, staleness, ratchet, self_comparison, inputs, domain, tier_s, tier_g, tier_v, tier_e`

### The three defects, before and after, both measured

| | base commit `be5258d` | this commit |
|---|---|---|
| stale corpus, bare `mag parity 010` | writes a verdict, prints `page sets: refused (...)`, **exits 0** | **exits 1**, error on stderr, no `verdict.json` written |
| stale corpus, `--oracle-only` | same, exit 0 | exit 1, no verdict |
| stale corpus, `--set body` | refuses the scoring only | exit 1, no verdict |
| `staleness()` on the shipped baseline | `unseeded` on every run, guarding nothing | `fresh` against a seeded digest |
| per-page ratchet | does not exist anywhere in `mag/src/parity.rs` | recorded, compared, and refused on a lowering |
| two concurrent runs of one edition | one `verdict.json`, winner varies per round | one refused by name, or one out dir each |

**`page_sets_refused` is now MEASURED, and WP-0.2g's Residual 1 is discharged.**
WP-0.2g asserted the branch from reading the source because it needed a seeded
baseline it was not licensed to write. With the baseline seeded and one staged
input altered, the `be5258d` binary reaches it:

```
mode: oracle_only
staged inputs: stale (dc11b707a7a017bc001b4fce5c3c853fead9b49f504b0ca4d4ff6b50817e9fe0)
page sets: refused (staged inputs differ from the baseline digest; page sets not derived)
base binary exit: 0
```

and its verdict carries
`"page_sets_refused": "staged inputs differ from the baseline digest; page sets not derived"`.
So the branch works exactly as WP-0.2g wrote it, and the defect was never in that
branch: it is that the run CONTINUES and exits 0 on a corpus the baseline cannot
vouch for. **This is live on `art_directed` for anyone running a binary built
before this commit**, and the consumers who must not trust such a run are any WP
taking a parity measurement on a moved corpus. Under this commit the field is
gone from the struct: with an unconditional refusal there is no state in which
page sets are refused and the run goes on, so keeping the field would be a value
that can never be set.

### The concurrency hazard, reproduced and then removed

WP-0.2g's Residual 3 reported two agents' runs writing one `verdict.json`.
Reproduced here deliberately, with two runs of one edition label whose correct
answers DIFFER (an equal pair, which passes, against a differing pair, which
fails), so a cross-write is visible rather than inferred:

| round | A-vs-A printed | A-vs-B printed | the single `verdict.json` held |
|---|---|---|---|
| 1 | pass | fail | **fail** |
| 2 | pass | fail | **pass** |
| 3 | pass | fail | **fail** |

(This evidence's own replay, run in a second checkout, got `fail, fail, fail` for
the same three rounds. The race decides which answer survives, so the column is
not reproducible and the property being measured is not that column: it is that
one verdict file holds one of two contradictory answers while both runs believe
they wrote it.)

Each round one of the two agents would have digested the other's verdict, and
nothing in either run's output says so. The fix is two parts:

- `MAG_PARITY_OUT_DIR` overrides the hard-coded `output/parity/<edition>`.
- A run takes an exclusive `run.lock` in its output directory, created with
  `create_new`, released on every exit path including the error paths. A second
  run sharing the directory is refused by name and told about the override.

Measured under real concurrency, three rounds each, not read from the code:

| configuration | result |
|---|---|
| one shared out dir | exactly 1 of 2 refused every round; `run.lock` left behind: none |
| one out dir each | A-vs-A exit 0 verdict `pass` and A-vs-B exit 1 verdict `fail`, every round |

`mag/tests/parity_concurrent.rs` commits both halves. Its discrimination is
deliberate: both processes use the SAME edition label, so before the fix they
would share `output/parity/conc`, and the test compares each concurrent verdict
against the verdict the same comparison produced when run alone.

### The per-page ratchet

`baseline.json` records, per interior page, the best tier the ENGINE PAIR has
reached and which Tier S clauses pass there. The tier is a CUMULATIVE ladder,
`none < G1 < G2 < V1 < V2 < E`: a page holds a tier only when every lower rung
also holds, so a page whose display list is equal while its raster is not records
`V1`, not `E`. The five rungs come from the run: G1 and G2 from that page's
`tier_g` entry (equal block and line counts, `max_dx_pt` and `max_dy_pt` within
the `parity.yaml` limits), V1 and V2 from that page's `tier_v` differing
fraction, E from that page having no display-list diff and the glyph clause
passing.

Attribution is per page for `boxes`, `text`, `color` and the display list, which
all report page numbers. It is DOCUMENT-WIDE for `page_count`, `navigation` and
the glyph clause, which report one status for the whole run: `NavClause` and
`GlyphClause` carry no per-page vector, and the glyph clause's `violations` list
is truncated at a cap inside `display.rs`, so parsing page numbers out of it
would silently lose pages once the cap is hit. `mag/src/parity/display.rs` is not
in this WP's Owns. The consequence is stated rather than hidden: a navigation or
glyph failure anywhere marks every page as not passing that clause, which refuses
more than strictly necessary and never less. Making those two per-page belongs to
whoever next owns `display.rs`; it is listed as Residual 4.

Two refusals, which are different things:

1. **The working tree against `HEAD`** (protocol rule 1's `git show <base>:...`
   check). Runs before staging, in every mode. A page whose committed tier is
   lowered, or whose entry is removed, or which loses a committed Tier S clause,
   refuses the run with the page named. A raise is accepted.
2. **The run against the recorded baseline.** Runs when the inputs were staged
   and the digest is fresh. Regressions are listed in `verdict.ratchet.regressions`
   and make the run exit nonzero.

The comparator NEVER writes `baseline.json`. A measuring run writes
`baseline-proposed.json` beside its verdict, containing the recorded entries
merged upward with the measured ones, so a verifier commits a file rather than
hand-editing tiers. The merge is upward-only by construction, and a unit test
asserts that its output never regresses against the input.

### Digests, and what an oracle-mode verdict digest is worth

| comparison | verdict.json sha256, first 16 | repeat |
|---|---|---|
| `--pre-rendered OLD OLD` (render `2026-09-19T02-54-41`) | `dc5d3a2772a6d577` | `dc5d3a2772a6d577` |
| `--pre-rendered OLD NEW` (two independent renders) | `9c871ef1aa37fe7a` | `9c871ef1aa37fe7a` |
| `--oracle-only`, cached render `02-54-41` | `6b94d4133968d32e` | `6b94d4133968d32e` |
| `--oracle-only`, fresh render `03-02-14` | `45efe0ea83a77fe1` | n/a |

Every clause passes in all four, and the two `--oracle-only` rows report
`staged inputs: fresh`, `ratchet: self_comparison`, exit 0.

**A finding worth carrying, because it bounds what a recorded oracle-mode digest
proves.** The last two rows differ, and the cause is measured rather than
guessed: two WeasyPrint renders of the IDENTICAL staged inputs produce different
`reader.pdf` BYTES (`9e0ae8946388d7a3b2ce` against `6c207f617a8a56eaa0eb`), and
the verdict carries those bytes in `inputs.a_reader_sha256`. Comparing the two
renders against each other is green at every compared level, including Tier E
display list, Tier S text, colour and navigation, and Tier V at max channel
delta 0, and the run prints no `self-comparison` line, so the two legs really are
different bytes. So the oracle is deterministic at the level the ladder compares
and not at the byte level, and an `--oracle-only` verdict digest is replayable
only against a FIXED render directory. A verifier replaying the oracle-only
blocks should expect the CLAUSE OUTCOMES and the staged-input digest to
reproduce, and the verdict sha to differ whenever it renders afresh.

### Corpus figures, with their configuration (rule 9)

Observations from the seeding render at `20adcfb`, not thresholds:

| figure | this WP, render of `20adcfb` | WP-0.2g, renders of `2026-09-14` |
|---|---|---|
| staged inputs | 57 | not reported |
| interior pages compared | 54 (pages 2 to 55 of 56) | 54 |
| boxes / rotations | 162 / 54 | 162 / 54 |
| colour sequence entries | 1733 | 1720 |
| annotations, of which links | 85 / 85 | 84 / 84 |
| glyphs / shows | 68530 / 1501 | 68800 / 1488 |
| page sets: body, openers, placement, furniture, code | 34, 9, 11, 54, 0 | not reported |

The three glyph pairs now in circulation are the plan's 69,071 / 1,503, WP-0.2i's
floor at 68,800 / 1,488, and this WP's 68,530 / 1,501. Re-derived at the point of
citation (rule 9): the first pair is read from the plan text, the second from
`meta/verification/evidence/WP-0.2i.md`, the third from this run's own stdout.
Their configurations differ along TWO axes and only one is now settled. Plan
revision 53 settles the first by enumeration rather than by subtraction: 1,503 is
1,488 plus 15 named shows on pages 1 and 56, all `Tj`, all font F1, all at
`3 Tr`, so that pair is one corpus measured over two DOMAINS, all 56 pages
against the 54-page interior. This WP's 1,501 is over the same 54-page interior
as 1,488, so the remaining 13 shows are a CORPUS difference between the
`2026-09-14` renders and a render at `20adcfb`, alongside 13 more colour entries
and one more annotation. This WP does not explain that difference and does not
chain any of these figures into a claim; WP-0.2i owns the reconciliation.

Rule 10a's both-legs form does not arise here: this WP adds no clause cardinality.
`ratchet` reports three separately named populations, `pages_committed`,
`pages_recorded` and `pages_measured`, never one number standing for two sets.

### Replay

Rule 12's extraction was performed: the eight `## Commands` blocks were pulled
out of this file programmatically and each was run in a clean shell from
`/Users/franguijarro/.claude/jobs/7d99e27f/tmp/wp02k-replay`, a worktree checked
out at this commit, which is not the directory the work was done in. All eight
run, and the replay independently reproduces the staged-input digest, the
mode-by-mode field lists, the base commit's `page_sets_refused`, the base
commit's shared-verdict corruption, the lock behaviour, and the ratchet tests.

The replay caught one real defect, which is the point of the rule: the stale-
corpus block originally looped over a STRING of flags, and `zsh` does not
word-split an unquoted parameter, so `--oracle-only --set body` reached clap as
a single argument and that case exited 2 on a usage error while the caption
promised three refusals. Counting the failures against the caption surfaced it.
The block now passes the flags through a function taking `"$@"`, and in that form
all three modes exit 1 with the refusal on stderr and write no verdict.

The replay also showed what does NOT reproduce, which is recorded under Verdicts:
the verdict shas, because each replay renders afresh and the oracle is not
byte-reproducible.

### Suite

`cargo fmt --check` clean, `cargo clippy --all-targets -- -D warnings` clean,
`tools/nocomments.py` clean through `cargo test`. On the landing base,
`cargo test` reports 22 test binaries with
`96, 3, 12, 9, 9, 6, 5, 1, 4, 3, 6, 8, 3, 4, 1, 2, 1, 1, 4, 13, 2, 5` passing,
summed from that list rather than carried beside it: **198**, and `0 failed` in
all 22. At `20adcfb`, where every measurement above was taken, the same command
reported 20 binaries and **191**; the two extra binaries and seven extra tests
are WP-5.1f's, which landed in between and are not this WP's. WP-0.2d's `parity_faults` suite passes with its
expected-detections matrix and `clause_vocabulary` untouched (`git diff` touches
neither key): the fields this WP adds, `ratchet` and `staleness`, are TOP-LEVEL
verdict fields outside `tier_s` and `tier_e`, so `assert_vocabulary_observable`
sees no new evaluated clause, and `page_sets_refused`, which it also never saw,
is gone.

One design choice was forced by a repo guard rather than chosen: the lock was
first released by `impl Drop for RunLock`, which `mag/tests/rust_helpers.rs`
rejects as a fourth `drop` helper. That test is not in this WP's Owns and rule 1
forbids self-granting an `ALLOWED` entry, so `run` now holds the lock across an
inner `compare` call and releases it on both paths instead. The behaviour is the
same and the release is still unconditional, but it is explicit rather than
scope-based, and a `std::process::exit` from inside `compare` would leak the lock
where a `Drop` guard would too.

## Verdicts

**Read this before comparing digests.** None of the four verdict digests below
is reproducible in a different checkout, and that is a property of the ORACLE
rather than of the comparator: every comparison here is taken over render
directories this WP produced, and two WeasyPrint renders of identical staged
inputs differ in bytes (measured below and again during this evidence's own
replay, where the same two comparisons produced `565d36e9d3d11ed5` and
`2420370355e73256` against the values recorded here). The verdict carries those
PDF bytes in `inputs.a_reader_sha256`, so the sha moves with the render.

What DOES reproduce, and what a verifier should check instead of the shas:

- the staged-input digest `e48eb5c638a0f25bfdfbb5e26bc989d56c1ecbac3ef85f103e90ed1ac8aac5fa`, which reproduced in a fresh worktree from a fresh render;
- pairwise determinism: each comparison run twice over one pair of directories writes a byte-identical file, which held for every pair in both checkouts;
- every clause outcome and every cardinality in the tables below.

- `--pre-rendered OLD OLD`: `dc5d3a2772a6d577`, all clauses pass, Tier E display list pass, exit 0.
- `--pre-rendered OLD NEW`: `9c871ef1aa37fe7a`, all clauses pass, Tier E display list pass, no self-comparison line, exit 0.
- `--oracle-only` on the cached render: `6b94d4133968d32e`, `staleness: fresh`, `ratchet: self_comparison`, all clauses pass, exit 0.
- `--oracle-only` on a fresh render: `45efe0ea83a77fe1`, same clause outcomes and same staged-input digest.
- Stale corpus, all three staged modes: no verdict, exit 1.

## What is and is not proven

**Proven.**

- The seeded digest is the digest of the corpus at `20adcfb`. Proven twice over:
  a `--oracle-only` run reports `fresh`, and a Python re-derivation from the
  render's own `request.json`, written independently of the comparator, produces
  `e48eb5c6...` byte for byte. The same re-derivation run against the MAIN
  checkout's copies of the 57 inputs produces the same digest, so the seed is not
  an artefact of the worktree it was measured in. It discriminates: altering one
  byte of one staged manuscript moves it to `dc11b707...`.
- A stale corpus refuses a bare `mag parity 010`, `--oracle-only` and
  `--set body` alike: exit 1, an error naming both digests, and no `verdict.json`
  in the output directory. Discrimination is the same alteration, applied and then
  reverted, with the reverted run passing the guard and writing a verdict.
- The same alteration on the base commit's binary produces a verdict and exit 0,
  so the difference is this WP's change and not the fixture. That also measures
  WP-0.2g's `page_sets_refused` branch for the first time.
- A working-tree baseline that removes a committed page entry refuses the run,
  and a raised entry is accepted. Committed as `mag/tests/parity_ratchet.rs`,
  which builds both variants from `git show HEAD:meta/verification/baseline.json`
  at test time and announces its mode per rule 2b: it now prints
  `MODE: full, 54 committed page entries, exercising page 10 at tier none`.
- The tier ladder, the regression rule and the upward merge are unit-tested in
  `mag/src/parity.rs` with both extremes: equal entries and raised entries yield
  no regression, while a lowered tier, a dropped clause and a removed entry each
  yield exactly one named regression. An unknown tier name and an unknown clause
  name each fail loud rather than being silently ranked.
- The per-page measurement discriminates, tested with one perturbation at a time
  in `measured_pages`: a display-list diff on page 3 takes that page from `E` to
  `V2` and leaves page 2 at `E`; a text difference removes only `text` from page
  3's clause list and leaves its tier at `E`; a raster fraction of 0.005 gives
  `V1`; a `max_dy_pt` of 1.0 gives `G1`; a line-count mismatch gives `none`; a
  navigation failure removes `navigation` from every page; a glyph failure caps
  every page at `V2`.
- A self-comparison measures no page entries, so no baseline can be seeded from
  an identity run. Tested directly, and visible in the seeding run's own output
  as `ratchet: self_comparison`, `pages_measured: 0`, with no proposal written.
- Two concurrent runs of one edition with separate output directories each keep
  their own verdict, byte-identical to the verdict the same comparison produces
  alone, over three rounds; two sharing one directory refuse exactly one of the
  pair, over three rounds, and leave no lock behind. Proven by running them
  concurrently, and the committed test does the same. It discriminates because
  the two comparisons have OPPOSITE correct answers and share an edition label:
  the base commit's binary, run the same way, leaves ONE verdict holding one of the
  two contradictory answers, so in every round exactly one of the two runs would
  have digested a verdict that was not its own. WHICH one is not stable and must
  not be read as a rule: this WP measured `fail, pass, fail` over three rounds and
  this evidence's replay in a second checkout measured `fail, fail, fail`, against
  a constant `pass` and `fail` printed by the two runs themselves. The invariant is
  that one of the two is always wrong, not which.
- Every mode now states what the staleness guard did, including the
  `--pre-rendered` mode that previously stated nothing. Read off emitted verdict
  files in both modes, not off the struct.
- `verdict.json` remains byte-deterministic for a fixed pair of render
  directories: each of the two `--pre-rendered` comparisons was run twice and
  produced an identical file.
- Two WeasyPrint renders of identical staged inputs differ in bytes and are equal
  at every compared level of the ladder.

**Not proven.**

- **That the run-against-baseline half of the ratchet has ever compared real 010
  pages.** It cannot today: it needs a staged run whose two legs differ, and the
  typst leg bails, so every staged run of 010 is a self-comparison. What is proven
  is the comparison logic, by unit test, and the measurement logic, by unit test
  with per-perturbation discrimination. The first end-to-end exercise belongs to
  **WP-3.1**, the first Phase 3 WP to run `mag parity 010` against a real typst
  leg; its evidence should record the first non-`none` proposal.
- **That the 54 seeded rows describe any achievement.** They deliberately do not.
  They record that the engine pair has reached nothing, which is the true state at
  `20adcfb`.
- **That tier-lowering is exercised end to end.** `parity_ratchet` announces that
  it is not, because every seeded row is at the bottom rung and `none` cannot be
  lowered. Entry removal is exercised instead and is a regression of the same
  class. The tier-lowering path is unit-tested, and the end-to-end branch becomes
  live for the first Phase 3 verifier who raises a row above `none`.
- **That the staged-input digest covers everything that determines a render.** It
  does not, and the name is accurate rather than the coverage complete: the 57
  staged inputs are `editions/010/edition.yaml`, 9 manuscripts, 24 art files and
  23 source media files. `src/magazine/assets/weasyprint-a5.css` and the vendored
  fonts are read by `weasyprint_adapter.py` directly from the repository and are
  NOT staged, so editing the stylesheet does not make the digest stale. This is
  Residual 1; it belongs to whoever owns the staging path in `mag/src/render.rs`,
  and it is not this WP's Owns.
- **That navigation and glyph regressions can be attributed to a page.** They
  cannot; see the per-page ratchet section and Residual 4.
- **That a stale corpus is detected before the expensive work.** It is not: the
  digest comes from the render's `request.json`, so the refusal costs one oracle
  render first. Residual 2.
- **That the lock survives every death.** A `SIGKILL` between creating and
  releasing the lock leaves `run.lock` behind; the next run refuses and names the
  file to delete. A search for a way to make the lock OS-advisory without a new
  crate found none, and a search that found nothing is recorded here rather than
  under Proven.
- Nothing here says the two engines agree about anything. Both legs of every
  comparison in this WP are WeasyPrint.

## Residuals

1. **The staged-input digest does not cover the stylesheet or the fonts.** A
   change to `src/magazine/assets/weasyprint-a5.css` changes every page of the
   render and leaves the digest `fresh`, so the guard vouches for the CORPUS and
   not for the RENDERER. The honest fix is to stage those inputs like the rest,
   which is `mag/src/render.rs` territory. Until it lands, a WP that changes the
   stylesheet must reseed the baseline by hand.
2. **The refusal costs a render.** The digest is computed from the render
   directory's `request.json`, so `mag parity 010` renders the oracle leg, about
   90 s, and only then discovers the corpus has moved. Computing the digest from
   the staging plan before rendering would refuse in under a second; it needs the
   staging path to expose its input rows without rendering.
3. **`--oracle-only` is structurally a self-comparison**, so it can never
   contribute a page entry. If a future WP wants the ratchet exercised without a
   typst leg, the shape that would do it is `--oracle-only` rendering TWO
   independent oracle legs rather than comparing one directory with itself, which
   this WP measured to be green at every compared level. That is a change to
   `--oracle-only`'s meaning, which WP-2.0b defined, so it is left as a
   recommendation.
4. **Navigation, page_count and the glyph clause are attributed document-wide.**
   `NavClause` and `GlyphClause` report one status with no page vector, and the
   glyph violations list is truncated at a cap inside `display.rs`, so page
   numbers cannot be recovered from it reliably. Whoever next owns
   `mag/src/parity/display.rs` should add page vectors to both; until then a
   failure in either marks every page.
5. **The Tier E raster clause still says `not_evaluated (WP-0.2d raster_bound
   derivation)`**, carried forward unchanged from WP-0.2g's Residual 5.
   `mag/src/parity/raster.rs` is not in this WP's Owns either.
6. **`git show HEAD:meta/verification/baseline.json` failing is reported, not
   fatal.** Outside a checkout, or before the file is committed, the committed
   half of the ratchet records `committed_check: "unavailable: ..."` and the run
   continues, because absence of a committed baseline is not evidence of a
   lowering. The status is printed on every run and stored in the verdict, so it
   cannot pass silently, but a reader should check it rather than assume the
   comparison happened.
7. **`MAG_PARITY_BASELINE` exists so tests can inject a working-tree baseline.**
   The committed half of the check always comes from `git show HEAD:`, so the
   override cannot be used to fake a passing ratchet against a lowered file; it
   moves only the side being checked.
