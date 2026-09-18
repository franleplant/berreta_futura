# WP-0.2g verification

## Verdict: ACCEPTED

Every claim in `meta/verification/evidence/WP-0.2g.md` was replayed
independently and reproduced. Two claims the evidence marked NOT PROVEN
(`--oracle-only` stays green and announces itself; `page_sets_refused` is ever
reached) were MEASURED here and also hold. One evidence defect was found and is
recorded below as a finding rather than a rejection ground: the recorded
`## Commands` blocks are not hermetic, and fail immediately when replayed from a
checkout that is not the tree the WP was developed in.

## What was verified, and where

- Subject: `be5258d` on `art_directed`, checked out as a detached worktree at
  `/Users/franguijarro/.claude/jobs/7d99e27f/tmp/vwp02g`. Verified the LANDED
  commit rather than `## Base` + diff, which is the stronger check: the evidence
  discloses two mid-flight rebases, so the landed tree is the artifact other WPs
  build on. `521ab79` (the evidence's `## Base`), `022d9d4`, `26391ab` and
  `80b7b62` are all ancestors of `be5258d`, so the disclosed rebase history is
  consistent with the branch.
- Baseline for the before/after comparison: a second worktree at `be5258d^`
  (`d8bc6ef`), built independently.
- **Concurrency.** `out_dir` is hard-coded to `output/parity/<edition>` with no
  override. Every `mag parity` invocation in this verification ran from its own
  isolated working directory (`iso-base`, `iso-perturb`, `iso-oracle`, the
  evidence block's `$T/iso`, and block 3's `$N`), each holding a real `output/`
  and symlinks to `editions`, `meta`, `prompts`, `src`. The hazard is live and
  was observed: during the replay, `ps` showed another agent's
  `mag parity fault-body_ink_pure_black` from
  `.../tmp/wp54bi/mag/target/debug/mag` and two `./mag/target/debug/mag parity
  010` processes invoked from a repository root, concurrent with mine. No
  verdict digest below was taken from a shared `output/`.
- `mag/src/parity.rs` was read but never written; WP-0.2k holds it.

## Commands

The evidence's `## Commands` blocks were extracted PROGRAMMATICALLY from
`meta/verification/evidence/WP-0.2g.md` (rule 12) and executed as files, not
retyped:

```sh
uv --directory /Users/franguijarro/code/magazine run python - <<'PY'
import re, pathlib
src = pathlib.Path('.../vwp02g/meta/verification/evidence/WP-0.2g.md').read_text()
sec = src[src.index('\n## Commands'):src.index('\n## Metrics')]
for i, b in enumerate(re.findall(r'```sh\n(.*?)```', sec, re.S), 1):
    pathlib.Path(f'.../replay/block{i}.sh').write_text(b)
PY
```

Three blocks were extracted. Block 1 (fixtures + six parity runs), block 2
(suite and lints), block 3 (`raster_bound` deleted from a spec copy).

```sh
git worktree add /Users/franguijarro/.claude/jobs/7d99e27f/tmp/vwp02g be5258d
git worktree add /Users/franguijarro/.claude/jobs/7d99e27f/tmp/vwp02g_base be5258d^
(cd /Users/franguijarro/.claude/jobs/7d99e27f/tmp/vwp02g/mag && cargo build)
(cd /Users/franguijarro/.claude/jobs/7d99e27f/tmp/vwp02g_base/mag && cargo build)

cd /Users/franguijarro/.claude/jobs/7d99e27f/tmp/vwp02g
T=$(mktemp -d) bash .../replay/block1.sh          # FAILED, see Finding 1
for d in render-2026-09-14T01-47-59 render-2026-09-14T01-49-02; do \
  ln -sfn /Users/franguijarro/code/magazine/editions/010/$d editions/010/$d; done
T=.../verify-0.2g-run1 bash .../replay/block1.sh   # passed after that one edit
N=.../rb-1789730182   bash .../replay/block3.sh

cd /Users/franguijarro/.claude/jobs/7d99e27f/tmp/vwp02g/mag
cargo fmt --check && cargo clippy --all-targets -- -D warnings
cargo test 2>&1 | tee .../cargo-test.log
```

Block 2's first line is `cargo fmt` (which rewrites); `cargo fmt --check` was
run instead, and it is clean, which proves the rewrite is a no-op.

Independent checks not in the evidence:

```sh
# independent annotation census, pypdf, on the oracle leg
cd .../vwp02g && uv run python -  # counts /Annots and /Subtype /Link per page
# annotation perturbation fixtures (all stripped / page-3 stripped / untouched)
uv run python .../vwp02g_perturb.py <src> <out>/en/reader.pdf {all,page3,none}
# four perturbation runs, from .../iso-perturb
mag parity 010 --pre-rendered <noannot-all> <noannot-all>
mag parity 010 --pre-rendered <noannot-p3>  <noannot-p3>
mag parity 010 --pre-rendered <ctl> <ctl-copy>        # identical bytes, different paths
mag parity 010 --pre-rendered <A> <noannot-p3>
# oracle-only WITHOUT rendering: seed out_dir/oracle-cache.json with the
# staged digest recomputed in python from request.json, then
mag parity 010 --oracle-only                          # baseline unseeded
# then, with meta/ a real copy, set baseline.json staged_input_digest to 0*64
mag parity 010 --oracle-only                          # baseline stale
# base-vs-new structural verdict diff
uv run python .../cmp_verdicts.py base-AA.json new-AA.json
uv run python .../cmp_verdicts.py base-AB.json new-AB.json
```

## Tool versions

poppler 25.08.0; rustc/cargo 1.96.0; pypdf 6.14.2 under `uv run python`
3.12.11. Same as the evidence records.

## Claim 1: compared cardinality on 010

Reproduced exactly, from `rot-control` against itself and from the untouched
A-vs-A pair:

```
tier S boxes: pass (162 boxes, 54 rotations compared; 0 box, 0 rotation mismatches)
tier S color: pass (1720 entries compared, 0 pages differ)
tier S navigation: pass (84 annotations of which 84 links, 0 outlines, 0 title, 0 lang compared; 0 mismatches)
tier E glyph positions: pass (68800 glyphs, 1488 shows, ...)
```

Independently derived rather than taken from the evidence:

- pypdf census of `render-2026-09-14T01-47-59/en/reader.pdf`: 56 pages; 84
  `/Annots` entries spread over 21 pages, every one of them `/Subtype /Link`;
  all 21 pages lie in the interior domain 2..55, so the interior total is 84.
  This is the same 84 from a different tool and a different code path.
- The catalog carries `['/Names', '/Pages', '/Type']` only: no `/Outlines`, no
  `/Lang`. `/Info` has `/Producer` and `/Creator` and no `/Title`. `pdfinfo`
  prints no Title and no Lang line. So `0 outlines, 0 title, 0 lang` is the
  true state of the corpus, and the evidence's point stands: two thirds of the
  navigation clause compares empty against empty.
- 162 boxes = 54 pages x the 3 names in `BOX_NAMES`, and 54 rotations = the
  54 interior pages; `boxes()` asserts one rotation per page in the range, so
  the 54 cannot silently shrink.

**Derived, not hard-coded, by perturbation.** `grep` for `84`, `1720`, `162`,
`68800` in `mag/src/parity/display.rs` and `mag/src/parity/geometry.rs` returns
nothing, and the code reads `annots().filter(|x| x.subtype == "Link").count()`.
The measurement, three points rather than one:

| fixture (both legs) | annots_compared | links_compared | nav status |
|---|---|---|---|
| all `/Annots` arrays emptied | 0 | 0 | pass |
| page 3's 27 annotations emptied | 57 | 57 | pass |
| untouched | 84 | 84 | pass |

57 = 84 - 27 is exactly what the independent pypdf census predicts. A hard-coded
84 would have survived all three.

A fourth run, A against the page-3-stripped leg, gives
`navigation: fail (84 annotations of which 84 links ...; 1 mismatches)`: the
clause discriminates, and the reported cardinality is the A leg's. That is what
rule 9 asks for ("derive it from the oracle leg of the same run") but it is
worth a reader knowing: on a FAILING navigation clause the printed count
describes the oracle side only, not an agreed population. Recorded as an
observation for whoever next owns `display.rs`.

The zero row is itself the demonstration the WP is about: a navigation clause
reporting `pass` having compared nothing, and now saying so.

## Claim 2: the `/Rotate` finding, all three legs

Fixtures rebuilt from the evidence's own `rotfix.py`, extracted from the
evidence file. Preconditions re-measured on the FIXTURES, not only on the source
render: `rot-control` and `rot-blank` both have 0 text characters and 0 images
on page 2, identical MediaBox `0.00 0.00 419.53 595.28`, and differ on that page
only in `rot: 0` against `rot: 180`. Page 3 of the source carries 555 text
characters.

| comparison | boxes | text | tier G | colour | nav | glyphs | display list | tier V |
|---|---|---|---|---|---|---|---|---|
| control vs control | pass (0 box, 0 rot) | pass | 0.000 / 0.000 | pass | pass | pass | pass | dims pass, V1/V2 pass, delta 0 |
| control vs rot-180 (page 3, body text) | **fail** (0 box, **1 rot**) | **fail** (1 page) | 325.839 / 551.325, 40 beyond G1, 40 beyond G2 | pass | pass | pass | pass | dims pass, **V1/V2 fail**, delta 241 |
| control vs rot-blank (page 2, blank) | **fail** (0 box, **1 rot**) | pass | 0.000 / 0.000 | pass | pass | pass | pass | dims pass, V1/V2 pass, **delta 0** |

Every number in that table is mine, from my own runs, and every one matches the
evidence.

The recorded mismatch on the blank-page fixture, read out of my own
`verdict.json`:

```json
{"status": "fail", "tolerance_pt": 0.05, "boxes_compared": 162,
 "rotations_compared": 54, "mismatches": [],
 "rotation_mismatches": [{"page": 2, "a": 0, "b": 180}]}
```

**The third leg holds, and it is the one that makes the clause load-bearing.**
On the blank inside front cover the boxes clause is the only clause in the
ladder that fails. `page_count`, `text`, `color`, `navigation`,
`glyph_positions` and `display_list` all pass; Tier G reports 0.000 pt on both
axes with zero structure mismatches; Tier V reports dimensions equal, V1 and V2
pass, worst page fraction 0.000000 and max channel delta 0. `code_blocks`,
`critic` and Tier E `raster` are `not_evaluated` and were before. So the
correction the WP makes to revision 15 is right in both directions: the
"nothing else would catch it" claim IS too broad on a content page, and IS true
on a page whose rendered content the turn does not move.

The max channel delta of 0 on that fixture is also the proof that page 2 is
genuinely blank in the artifact under test: if any mark were on it, a 180 degree
turn would have moved pixels.

The control row is the fixture-inertness check and it reproduces: the same pypdf
rewrite applied to both legs with no rotation passes every clause at the same
cardinalities as the untouched pair (162 / 54 / 1720 / 84 / 68800 / 1488). See
`## What this verification cannot discriminate` for the limit of that argument.

## Claim 3: self-comparison announces itself

`mode: <mode>` printed on every run I made, in all three modes observed
(`pre_rendered` on both identical and differing legs, `oracle_only`).

**Computed from content hashes, not paths, and measured as such.** A
byte-identical copy of one fixture was placed at a different path
(`.../perturb/ctl/en/reader.pdf` and `.../perturb/ctl-copy/en/reader.pdf`, both
`3a599874139595889672eeefbce57cf542747c01de07170eac97dc0c0ddab406`) and
compared. Result:

```
mode: pre_rendered
self-comparison: both legs hash identically (WARNING: both sides are the same bytes, so no engine comparison happened)
```

The code backs this: `self_comparison: inputs.get("a_reader_sha256") ==
inputs.get("b_reader_sha256")`, with both keys unconditionally inserted in
`run()`, so there is no both-absent case that would compare `None` to `None`.

A-vs-B prints `mode: pre_rendered` and no self-comparison line.

**`(deliberate for this mode)` measured, which the evidence could not do.**
`--oracle-only` was reached WITHOUT rendering, by seeding
`output/parity/010/oracle-cache.json` in an isolated out_dir with the existing
oracle render directory and its staged-input digest. The digest
(`ac856f9f4b827d5eeaa54039c0c56f581c628a41b9262115d16dd14e4d10661a`) was
recomputed in Python from `request.json` by reimplementing `staged_digest`
(sort `targetPath\x1f sha256(sourcePath)` rows, join on `\x1e`, sha256), and
`cached_oracle` accepted it, which independently confirms the reimplementation.
The run printed:

```
oracle leg: cached .../editions/010/render-2026-09-14T01-47-59
mode: oracle_only
self-comparison: both legs hash identically (deliberate for this mode)
staged inputs: unseeded (ac856f9f...)
page sets: body 34, code 0, furniture 54, openers 9, placement 11
tier S boxes: pass (162 boxes, 54 rotations compared; 0 box, 0 rotation mismatches)
```

So Residual 2's "`--oracle-only` was not re-measured" is now measured: it is
green and it announces its mode correctly.

## Claim 4: digests, and the causal claim tested rather than read

All four digests reproduce, from builds and directories that are not the
worker's:

| comparison | before (`be5258d^`, my build) | after (`be5258d`, my build) | repeat |
|---|---|---|---|
| A-vs-A | `0e21644ee602ff8a` | `468eac3c32c8a4e2` | `468eac3c32c8a4e2` |
| A-vs-B | `6e932ea43678b91a` | `09626f78981b6819` | `09626f78981b6819` |

`468eac3c32c8a4e2` was produced a THIRD time, from an unrelated isolated
directory: block 3's run against a spec copy with `tiers.e.raster_bound`
physically deleted produces a byte-identical `verdict.json`.

**The "no clause outcome moved" claim is a hypothesis (rule 11), so it was
tested structurally rather than by reading the diff.** Both verdicts were
flattened to leaf paths and set-compared:

| pair | keys added | keys removed | shared keys whose value changed | clause-outcome keys | outcomes differing |
|---|---|---|---|---|---|
| base A-vs-A vs new A-vs-A | 10 | 0 | 0 | 13 | none |
| base A-vs-B vs new A-vs-B | 10 | 0 | 0 | 13 | none |

The 10 added keys are exactly `self_comparison`, `boxes.boxes_compared`,
`boxes.rotations_compared`, `boxes.rotation_mismatches` (length 0),
`color.entries_compared` and navigation's five counters. **Zero shared keys
changed value**, which is a stronger statement than "no clause outcome moved":
nothing that existed before has a different value now. The 13 outcome keys
(`tier_s.*.status` x7, `tier_e.*.status` x3, `tier_v.status`, `tier_v.v1`,
`tier_v.v2`) are pairwise identical, `not_evaluated` included. So the digest
movement is fully accounted for by the added fields.

`self_comparison` is `true` on A-vs-A and `false` on A-vs-B, as it should be;
`page_sets_refused` is absent from both, correctly, since `--pre-rendered`
carries no digest.

## Claim 5: `raster_bound` resolved both ways

Reproduced by deletion, not by reading the branch. Block 3, run verbatim from
the extracted evidence file:

```
raster_bound removed: True
tiers.e keys now: ['coordinate_quantum_pt', 'glyph_positions', 'link_rect_quantum_pt']
...
tier E raster: not_evaluated (WP-0.2d raster_bound derivation)
```

exit code 0, and the resulting `verdict.json` hashes `468eac3c32c8a4e2`, byte
for byte the same as the run with the key present. That is stronger than the
evidence claimed: not merely "the same clause list", but the identical verdict.

The yaml leads with `status: withdrawn`, `gates: nothing`, `authored_by:
nobody`, then `measurements_recorded_by`, then the `withdrawal` prose, then the
historical measurements. Confirmed by reading the landed file.

**No threshold moved (rule 4).** `raster_bound` carried no `value` before and
carries none now; `match node.get("value") { None => Ok(None), ... }` means
present-valueless and absent both yield `None`, and `None` makes the Tier E
raster clause `not_evaluated`. The byte-identical verdict is the measurement of
that. One behavioural change worth stating plainly: the key's absence used to
be a hard error and is now silent. Since the key gates nothing, that removes a
fail-loud over a decision nobody is making, and the yaml records why.

## Claim 6: WP-0.2d's matrix is intact, and the suite count

`fault_suite.expected_detections` and `fault_suite.clause_vocabulary` were
parsed out of `parity.yaml` at `be5258d^` and `be5258d` and hashed as canonical
JSON: `49fcc08316907366` and `5cd2c3ec1039ca20` respectively, identical on both
sides. The file's top-level key set is unchanged; the diff touches only
`tiers.s` (two new rotation keys) and `tiers.e.raster_bound`.

By construction, as the evidence argues and as I confirmed by reading
`assert_vocabulary_observable` and `clause_states`: the enumerator walks direct
children of `tier_s`/`tier_e` that carry their own `status` string. The rotation
data lives inside `boxes`, which already had a status, and `self_comparison` and
`page_sets_refused` are top-level verdict fields outside both tier objects, so
no new evaluated clause name can appear.

`cargo test --test parity_faults` passes (`1 passed`, 45.50 s).

**Suite count re-derived from the enumeration, not accepted (rule 9).** Parsing
`cargo test` output: 17 test binaries, each `ok`, per-binary passed counts

```
71, 3, 11, 9, 6, 5, 1, 4, 3, 6, 8, 1, 1, 4, 13, 2, 5
```

which sums to **153**, with 0 failed and 0 ignored across all 17. Sorted, that
multiset is `1,1,1,2,3,3,4,4,5,5,6,6,8,9,11,13,71`, exactly the list the
evidence prints, and the total agrees. `cargo fmt --check` clean;
`cargo clippy --all-targets -- -D warnings` exits 0. No U+2014 anywhere in the
commit's diff.

## Owns and landing hygiene of the reviewed commit

`git show --stat be5258d` lists exactly five files: `mag/src/parity.rs`,
`mag/src/parity/display.rs`, `mag/src/parity/geometry.rs`,
`meta/verification/parity.yaml`, `meta/verification/evidence/WP-0.2g.md`. No
verify file, no `baseline.json`, no test file, no engine file. The first four
are the WP's Owns; the `tiers.e.raster_bound` edit sits outside the literal
"the boxes clause key" wording of Owns but inside the same file, and the plan's
own WP-0.2d Owns line now says the key "is authored by nobody", so taking it was
closing a dangling consequence rather than reaching. The evidence records the
reassignment.

## Disclosed residuals, assessed

1. **`mag/src/parity/raster.rs:106` still says `not_evaluated (WP-0.2d
   raster_bound derivation)`.** Confirmed present at that location, naming an
   owner who by revision 39 will never derive anything. `raster.rs` is not in
   this WP's Owns. Honestly scoped, correctly left alone, correctly handed on.
2. **`page_sets_refused` implemented but unreachable.** The disclosure is
   accurate in every particular: the branch sits behind `legs.digest.is_some()`,
   which `--pre-rendered` leaves `None`; `staleness()` maps a null
   `staged_input_digest` to `unseeded`; and `fresh = status != "stale"` counts
   `unseeded` as fresh. `baseline.json` does carry `"staged_input_digest":
   null`. The residual asks a verifier with a seeded, mismatching baseline to
   run `--oracle-only` and confirm the line prints. **Done, and it prints.**
   With `meta/` copied and `staged_input_digest` set to 64 zeros:

   ```
   mode: oracle_only
   self-comparison: both legs hash identically (deliberate for this mode)
   staged inputs: stale (ac856f9f...)
   page sets: refused (staged inputs differ from the baseline digest; page sets not derived)
   ```

   Judged under rule 10: the disclosure was adequate and is now discharged. The
   worker could not have measured it without seeding `baseline.json`, which
   rule 3 reserves to a verifier, and it said exactly that, named the
   obstruction, classified the guard as MESSAGE-ONLY, and told a verifier what
   to run. That is the correct shape for an unmeasurable branch, and the
   prescribed check reproduces on the first try.
3. **`out_dir` concurrency hazard.** Real, live, and observed again during this
   verification. Honestly scoped and correctly flagged as not in Owns. My own
   handling is recorded at the top of this file.
4. The `b: -1` sentinel for a page present in A and missing from B: confirmed in
   `compare_boxes`, and unreachable on any pair that passes `page_count`, since
   both legs are read over the same page range and `boxes()` asserts one
   rotation per page. Honest and minor.
5. Residual 6, that the WP ran in the MAIN tree rather than a private worktree,
   is a real process deviation and is disclosed. It is also the proximate cause
   of Finding 1 below.

## Findings

**Finding 1 (EVIDENCE, not code): the recorded `## Commands` blocks are not
hermetic.** Extracted programmatically and run verbatim from a fresh worktree
root, block 1 fails on its first command:

```
I/O Error: Couldn't open file '.../vwp02g/editions/010/render-2026-09-14T01-47-59/en/reader.pdf'
FileNotFoundError: .../vwp02g/editions/010/render-2026-09-14T01-47-59/en/reader.pdf
```

The block sets `R=$PWD` and then `A=$R/editions/010/render-2026-09-14T01-47-59`.
`editions/*/render-*/` is gitignored, so those directories exist only in the
main tree, which is where this WP was developed (its own Residual 6). The
instruction "run it from the repository root with the branch checked out" is
therefore true of exactly one checkout. Block 3 inherits the same dependency.
This is rule 12's relocation clause: the corpus path did not migrate into the
test, it stayed in the recorded command, and only replaying from a different
directory exposes it.

Not a rejection ground, for three reasons: the clause was added to the plan
AFTER this WP landed, and rule 1's no-mid-flight-rebriefing principle should not
be inverted to punish it retroactively; the corpus genuinely lives outside the
repository, so no command in this plan can be hermetic in the strong sense; and
the repair is one line. The fix for the next comparator WP:
`A=${A:-$R/editions/010/render-2026-09-14T01-47-59}`, so a replayer can point
the legs at the corpus wherever it lives, and say so in a sentence.

**My adaptation, disclosed.** I symlinked the two gitignored render directories
into my worktree's `editions/010/` and then re-ran the extracted blocks
UNMODIFIED. Every number above comes from that run. The symlinks are the only
deviation from the recorded replay.

**Finding 2 (observation, for WP-0.2k or whoever owns `display.rs` next):
reported cardinalities are the A leg's.** `boxes_compared`, `rotations_compared`,
`entries_compared` and all five navigation counters are computed from leg A
only. On a passing clause the two sides agree, so it does not matter. On a
FAILING clause it does: my A-versus-stripped-annotations run prints
`fail (84 annotations of which 84 links ... 1 mismatches)` while leg B holds 57.
Rule 9 does prescribe deriving corpus figures from the oracle leg, so this is
the sanctioned choice, but the printed line reads like an agreed population and
is not one.

## What this verification cannot discriminate

- **The fixture-inertness argument is cardinality-level.** Neither the evidence
  nor I compared the untouched oracle leg directly against `rot-control`. What
  is shown is that the pypdf rewrite preserves the six cardinalities the clauses
  report (162 / 54 / 1720 / 84 / 68800 / 1488) and that `rot-control` against
  itself is green at zero delta everywhere. A rewrite that perturbed something
  identically in both legs would be invisible to that. The rotation attribution
  does not depend on it: `rot-control` and `rot-180`/`rot-blank` pass through
  the same writer and differ only in `page.rotate(180)` on one page, so anything
  the writer does cancels. I state the limit rather than assert inertness.
- **Only the 0-versus-180 pair was exercised**, by me as by the WP. 90 and 270
  are untested here.
- **Nothing here says the two engines agree on rotation.** Both legs of every
  comparison are WeasyPrint renders; there is no Typst leg yet. What is shown is
  that the comparator would notice a disagreement.
- **A-vs-B is a second all-green pair.** Every clause passes at zero delta on
  both A-vs-A and A-vs-B, so the two digest comparisons prove that no PASSING
  clause's serialization moved. A hypothetical regression in how a FAILING
  clause serializes would not be caught by those two pairs alone; it is covered
  instead by the three rotation fixtures and by the fault suite, which do
  exercise failing clauses.
- **`--oracle-only`'s verdict digest is still not recorded.** I reached the mode
  through a seeded `oracle-cache.json` in an isolated out_dir rather than
  through a real render, which is enough to prove the mode line, the green
  clause list and the refusal message, but the digest from that run is not
  comparable to the `38f91a94...` the plan carries, because that one came from a
  real staging. Residual 2 stands, narrowed.
- **The `--run` mode was not exercised at all**, by either of us.
- I did not re-verify the two mid-flight rebases line by line; I verified the
  stronger property that all four named commits are ancestors of `be5258d` and
  that the landed tree passes everything.

## Status

`complete`. Verdict **ACCEPTED**. No defect is live on the branch; consumers may
build on `be5258d`.
