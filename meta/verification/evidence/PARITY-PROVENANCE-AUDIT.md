# Retrospective provenance audit of parity-derived numbers

## Base

`ba9c3ea` (plan revision 45). Method designed by the sub-planner in plan
revision 44. Read-only with respect to source: this audit changed no file
under `mag/`, `src/` or `meta/verification/parity.yaml`. All comparator runs
were made from isolated working directories, because the hazard under audit
is still live until WP-0.2k lands.

**The enumeration is pinned at `ba9c3ea` and the tree moved under it.** Main
advanced to `6366eb3` during this audit, adding `WP-0.2g.verify.md`,
`WP-1.8.verify.md`, `WP-2.1.md` and `WP-5.4b-i.md`, and revising `WP-5.5a.md`
by 132 insertions and 75 deletions. Where the delta changes a conclusion it is
recorded against the live tree and labelled; the counts in section 3 are
`ba9c3ea`'s. This is itself an instance of the audit's own finding: a figure is
only meaningful against a named base.

## Status

`complete`

## The premise, corrected twice, then measured

The brief first said every verdict records **`a_reader_sha256`,
`b_reader_sha256` and `staged_input_digest`**. A correction then said the
third field does not exist. A second correction said it is mode-dependent.
**Recorded as a falsified premise and its two corrections rather than quietly
fixed, because it is the load-bearing assumption of the whole method.**

Rule 9's citation clause binds briefs as well as evidence, so none of the three
versions was adopted. The field list below is enumerated from **two real
emitted verdicts, one per mode**, not from the struct and not from anyone's
description.

| | `--pre-rendered` (at `521ab79`) | `--oracle-only` |
|---|---|---|
| top-level keys | 8 | 12 |
| `inputs.a_reader_sha256` | yes | yes |
| `inputs.b_reader_sha256` | yes | yes |
| `staged_input_digest` | **no** | **yes** (`ac856f9f4b827d5e...`) |
| `staleness` | **no** | **yes** (`stale`, baseline 64 zeros) |
| `self_comparison` | no | yes |
| `page_sets_refused` | no | yes |

Set difference, derived: keys present only in `oracle_only` are
`page_sets_refused, self_comparison, staged_input_digest, staleness`; keys
present only in `pre_rendered`, **none**. The `pre_rendered` key set is a
strict subset.

**The second correction is the right one: the field is mode-dependent, not
absent.** `stage_legs()` returns `digest: None` for `opts.pre_rendered`, and
the field is `skip_serializing_if = "Option::is_none"`, so the staging modes
emit it and `--pre-rendered` does not. The name also belongs to two other
files, which is the confusion that produced the first two versions: it is a key
of `meta/verification/baseline.json` (read by `baseline_digest()`, compared by
`staleness()`) and of `output/parity/<edition>/oracle-cache.json` (written by
`store_oracle()`).

**The key set moves with the base too.** The `--pre-rendered` verdict has 8
keys at `521ab79` and **9** at `ba9c3ea`, because WP-0.2g added
`self_comparison`. So even "which fields exist" is a claim that needs a named
commit. That is the audit's headline rule appearing in its own instrument.

**What this means for the method.** The two reader hashes exist in **both**
modes and identify the two PDFs compared. The tested conclusion holds: **they
catch a verdict wholly replaced by a run over different artifacts, the
dangerous case, and they cannot pin the staged inputs those PDFs came from.**
Section 4 re-cuts the buckets on the mode axis, since mode is a property of the
run recoverable from the verdict itself rather than of what an author
remembered to quote.

**An operational note where the brief and this audit disagree, recorded
because it matters for the worklist.** The brief and WP-5.5a hold that `mag
parity` refuses to run outside a repo root, so isolation must be a worktree.
Measured otherwise: every comparator run behind sections 5b, 5c and 5f was made
from an ordinary scratch directory holding a real `output/` and symlinks to
`editions`, `meta`, `prompts` and `src`, and all of them completed. The
requirement appears to be that the cwd **present the repo-root markers**, which
a worktree satisfies and a symlink farm also satisfies. A worktree is the
simpler and safer route and the worklist assumes it; the symlink farm is
WP-0.2g's recorded method and it works.

## The hazard, restated

`out_dir` is hard-coded to `output/parity/<edition>` with no override
(`mag/src/parity.rs`, `run()`). Six to nine agents have run concurrently for
days; two `mag parity 010` processes were **observed** writing the same
`verdict.json` (WP-0.2g Residual 3). Interleaved bytes are harmless, because
invalid JSON fails loudly. The dangerous outcome is **one write wholly
replacing another**, leaving a complete, valid verdict from the wrong run.
Eyeballing cannot find that.

## Headline

**At the audited base, revision 44's method could not be applied to a single
figure, because no evidence file quoted a reader hash. One file has since
become its first and only subject, and the check passes.** A stronger method,
digest reproduction, was available for the rest and was applied: the four
most-cited digests in the corpus are provenance-confirmed against the exact
artifacts their WPs claim to compare.

**No mismatch was found anywhere.** Counted: 4 verdict digests reproduced
exactly, 1 `staged_input_digest` recomputed exactly, and 1 quoted reader-hash
pair matched to its two artifacts. Five digests and one pair, all to the byte.

**The more useful result is a partition, not a clean bill of health.** Five
different renders of edition 010, five different `reader.pdf` hashes, compared
at one fixed base, all report the identical glyph corpus, domain and page count
(section 5f). So the corpus figures do **not** move with the render, only with
the base, and a disagreement between two of them cannot be a render artefact.
The pair this audit could check, 68,800/1,488 at `521ab79` and 68,530/1,501 at
`c1253d8`, are both provenance-confirmed at their own bases: **individually
sound, collectively unanchored.** One standing hypothesis is retired outright,
since 68,800 is measured over a 54-page domain from a 56-page PDF in the same
verdict.

Two things are not confirmed and should not be read as if they were: the
plan's headline Tier E margin `4.00x` has no recorded digest at all and rests
on two independent measurements rather than a replayable record, and WP-2.0b's
worker and verifier record different oracle-only digests for what both call
the same run, unresolvably from the record.

---

## 1. Why the designed method barely applies

Revision 44's method: a verdict records `a_reader_sha256`, `b_reader_sha256`
and `staged_input_digest`, so a crossed-over verdict carries the wrong
artifacts' hashes; evidence quoting a digest **and** its input hashes is
checkable without a re-run.

The third field exists only in the staging modes (see the premise section
above), so it is unavailable to all but two runs in this corpus. Two further
findings, each measured rather than read:

### 1a. At `ba9c3ea`, no evidence file quoted any reader hash.

Across all 76 files in `meta/verification/evidence/`, counted per field:
`a_reader_sha256` **2** occurrences (`WP-2.0b.verify.md:86`, `:154`);
`b_reader_sha256` **4** (`WP-0.2a.md:60`, `WP-0.2a.verify.md:40`,
`WP-2.0b.verify.md:87`, `:155`); `staged_input_digest` **2**
(`WP-0.2g.md:342`, `WP-2.0b.md:30`). Summing the three: **8** occurrences.

**Every one of the eight is a bare field name with no hex value.** The single
staged-input-digest value in the corpus is quoted in prose at `WP-2.0b.md:64`
without the field name beside it, which is why it does not appear in this
count.

An earlier draft of this section said "seven" and "five" and claimed one of the
`staged_input_digest` occurrences carried a value. Both were wrong, and the
replay of section 9 is what caught them: its derived total of 8 did not match
the prose. Recorded rather than silently corrected, since it is the fourth
count disagreement in this execution found by re-deriving rather than by the
author.

The consequence at the audited base is flat: **zero figures fell into
bucket 1.**

### 1b. That changed during the audit, by exactly one file.

`WP-5.5a.md` was revised after `ba9c3ea` and now quotes both reader hashes in a
table (`A, before (segno)` `0460c081226ea530...`; `B, after (committed asset)`
`15d3bd5aef0dfb1f...`), stating they are the two the comparator recorded in its
`verdict.json` `inputs` block. It is the corpus's **first and only** bucket-1
member. The check is run in section 5a.

It also records that "there is no `staged_input_digest` field yet, so that half
of the provenance claim cannot be quoted from this comparator". Correct for its
run, which was `--pre-rendered`; the field does exist in the staging modes.

Every parity run in the corpus except WP-2.0b's two `--oracle-only` runs is
`--pre-rendered`, so for practically the whole corpus the third hash was never
written even where the mode could have written it.

### 1c. Where it does exist, it cannot discriminate render legs anyway.

The one quoted value, WP-2.0b's
`ac856f9f4b827d5eeaa54039c0c56f581c628a41b9262115d16dd14e4d10661a`, was
recomputed from `request.json` by reimplementing `staged_digest()`. It is
**confirmed**, and it is confirmed against **seven different render
directories**:

| render dir | input rows | recomputed staged digest |
|---|---|---|
| `render-2026-09-13T12-50-59` | 46 | `b658a781eff0bc7e...` |
| `render-2026-09-13T12-51-19` | 46 | `b658a781eff0bc7e...` |
| `render-2026-09-13T12-51-44` | 46 | `b658a781eff0bc7e...` |
| `render-2026-09-13T12-57-21` | 47 | **`ac856f9f4b827d5e...`** |
| `render-2026-09-14T01-32-52` | 47 | **`ac856f9f4b827d5e...`** |
| `render-2026-09-14T01-33-59` | 47 | **`ac856f9f4b827d5e...`** |
| `render-2026-09-14T01-40-18` | 47 | **`ac856f9f4b827d5e...`** |
| `render-2026-09-14T01-41-32` | 47 | **`ac856f9f4b827d5e...`** |
| `render-2026-09-14T01-47-59` | 47 | **`ac856f9f4b827d5e...`** |
| `render-2026-09-14T01-49-02` | 47 | **`ac856f9f4b827d5e...`** |

`staged_digest()` hashes `targetPath` plus the **content** of each staged
input. It identifies the edition's inputs, not the render. Seven renders of
edition 010 share one value, so **`staged_input_digest` has no power to tell a
crossed-over verdict from a correct one on this edition.** Revision 44 counts
it as one of three discriminators; measured, it is zero of three.

That leaves the method resting entirely on two hashes that no evidence file
quotes.

---

## 2. The substitute method, and why it is stronger

The verdict digest is `sha256(verdict.json)`, and `verdict.json` **embeds**
`inputs.a_reader_sha256` and `inputs.b_reader_sha256`. So reproducing a
published digest from the render trees the WP names proves more than the
designed check: it proves the published number came from a run over exactly
those artifacts, and that every clause figure in that verdict is the one that
run produced. A crossed-over verdict would not reproduce.

The check costs one build plus about 90 s per comparison, and requires that
the comparator's code and spec be at the commit the digest was taken at, since
the verdict's **shape** changes when a WP adds a field.

Two windows were used:

- `ba9c3ea` (HEAD). Only one commit, `be5258d` (WP-0.2g's own landing), touched
  `mag/src/parity.rs`, `mag/src/parity/` or `meta/verification/parity.yaml`
  between WP-0.2g's base `521ab79` and HEAD. So HEAD's comparator is WP-0.2g's
  measured comparator.
- `521ab79` (WP-0.2g's base, and the base WP-0.2h, WP-0.2i and WP-2.0b's
  re-run were measured against).

---

## 3. Enumeration

### 3a. Scope, and what is excluded

Three fan-out reads covered all 76 evidence files. Two whole groups carry
**no** parity-comparator figure, each saying so in its own text:

- Phase 1 spikes (`WP-1.1`, `WP-1.2`, `WP-1.4` through `WP-1.8`, `WP-2.0a`):
  "No `verdict.json`: this is a Phase 1 spike and runs no comparator."
- Phase 5 ports (`WP-5.1a`-`WP-5.1e`, `WP-5.2`, `WP-5.3a`, `WP-5.3b`,
  `WP-5.3b-i`, `WP-5.3d`, `WP-5.4`, `WP-5.4a`, `WP-5.4b`, `WP-5.5`, `WP-5.5b`,
  `WP-5.7`): the Phase 5 preamble forbids the comparator for oracle tests.
  `WP-5.5a` is the single exception and is audited below.

`WP-0.2f.md` is excluded from **accepted** evidence: status `blocked`, no
`.verify.md` exists, and it states "No verdict digests are recorded as
binding, because no configuration was pinned." Its roughly 30 fixture runs are
therefore out of scope, but they were taken in the same shared-`out_dir`
window and would need re-measurement if ever promoted.

### 3b. The provenance unit

A single verdict is clobbered or not **as a whole**. Every figure in one
passage shares one provenance fate. So the unit enumerated here is the **run
citation**: one evidence file reporting figures from one comparator
invocation. Bucketing is a property of the run, not of each number inside it.

### 3c. Digest-bearing run citations, derived

Extracted programmatically (every 16- or 64-hex token in a non-excluded file,
truncated to 16, with the one `staged_input_digest` value removed). Per file:

| file | digest citations |
|---|---|
| `WP-0.0c.md` | 1 |
| `WP-0.0c.verify.md` | 1 |
| `WP-0.2a.md` | 2 |
| `WP-0.2a.verify.md` | 1 |
| `WP-0.2b.md` | 2 |
| `WP-0.2b.verify.md` | 2 |
| `WP-0.2c.md` | 3 |
| `WP-0.2c.verify.md` | 3 |
| `WP-0.2d.md` | 21 |
| `WP-0.2e.md` | 2 |
| `WP-0.2e.verify.md` | 2 |
| `WP-0.2g.md` | 4 |
| `WP-0.2h.md` | 2 |
| `WP-0.2h.verify.md` | 2 |
| `WP-0.2i.md` | 9 |
| `WP-0.2i.verify.md` | 2 |
| `WP-1.3.md` | 1 |
| `WP-2.0b.md` | 3 |
| `WP-2.0b.verify.md` | 1 |

Summing the column: 1+1+2+1+2+2+3+3+21+2+2+4+2+2+9+2+1+3+1 = **64 digest
citations**, across **19 files**, counted from the rows above. Deduplicating
the hex values gives **47 distinct verdict digests** (four of them re-cited
across files: `0e21644ee602ff8a` and `6e932ea43678b91a` in six files each;
`0d313e67`, `28d7c3a2`, `291485c7`, `710878fb`, `a195f86d`, `bc0da32c`,
`fd6608a2` in two each; the remaining 38 in one each; 2+7+38 = 47).

### 3d. Digest-less run citations

These report clause figures with **no** digest of any kind. Enumerated
first-hand where marked:

| file | runs without a digest | first-hand? |
|---|---|---|
| `WP-5.5a.md` | 4 (before/before floor, before/after, flipped-module control, re-run at landing base) | yes |
| `WP-0.2g.md` | 4 (rot-control self, rot-180, rot-blank, `raster_bound`-absent spec) | yes |
| `WP-0.2i.md` | 10 (stairdrift, smoothdrift, 5 adversarial variants, glyphsub, ocmember, annotap) | yes |
| `WP-0.2i.verify.md` | 3 (stairdrift, drift, smoothdrift, the verifier's own floor table) | yes |
| `WP-0.2e.md` | 10 (base plus 4 blind-spot fixtures, under old and new comparator) | second-hand |
| `WP-0.2e.verify.md` | 14 (the same 10, plus fontsplit, subset_recode, long_aniso, long_rot) | second-hand |
| `WP-0.2b.md` | 12 (fx1-fx8, nav demo pre/post, title demo pre/post) | second-hand |
| `WP-0.2b.verify.md` | 12 (the same replayed) | second-hand |
| `WP-2.0b.verify.md` | 4 (2 page-set perturbations, staleness guard, body-set scoring) | second-hand |
| `WP-0.2c.md` | 1 (raster negative check) | second-hand |
| `WP-0.2c.verify.md` | 1 (the same replayed) | second-hand |

Summing the column: 4+4+10+3+10+14+12+12+4+1+1 = **75 digest-less run
citations**.

**This 75 is a floor, not a total** (rule 10). The four first-hand rows are
exhaustive for their files; the seven second-hand rows come from fan-out reads
and were not each re-counted against the source tables, so the true figure is
75 or more.

### 3e. Total

64 digest-bearing + 75 digest-less = **139 parity run citations** in accepted
evidence, of which 139 is a floor for the same reason.

---

## 4. Buckets, re-cut on the mode axis

### 4a. What provenance each mode makes available

Mode is a property of the run and is recorded in the verdict, so the ceiling on
any figure's provenance is fixed before an author writes anything down.

| mode | hashes emitted | provenance ceiling |
|---|---|---|
| `--pre-rendered` | two reader hashes | The two PDFs compared are pinned. **The staged inputs behind them are not pinned at all**, and neither is staleness, because neither field is emitted. |
| `--oracle-only`, `--run` | two reader hashes plus `staged_input_digest` and `staleness` | Both the PDFs and the staged inputs are pinned, and the run says whether its inputs matched the baseline. |

**Every run in this corpus is `--pre-rendered` except WP-2.0b's two
`--oracle-only` runs.** So for essentially the whole audited population the
ceiling is the two-hash ceiling, and no author could have done better by being
more diligent. That is a property of how the WPs ran parity, not of how they
wrote it up.

### 4b. Bucket definitions

Revision 44's definitions assumed three hashes in every verdict. The corrected
definitions, and a third criterion the audit found it needed:

| bucket | corrected definition |
|---|---|
| 1 | The evidence quotes **both reader hashes** and names a base commit. Checkable with **no re-run**: confirm those two hashes are the sha256 of the two artifacts the WP claims to compare. |
| 2 | The evidence quotes a **verdict digest alone** and names a base commit. Needs a re-run, but a cheap and decisive one: the digest covers a verdict that embeds both reader hashes, so reproducing it at the named commit proves provenance. |
| 3 | The evidence quotes **neither**, **or quotes one but names no base commit**. Needs re-measurement. |

**The base-commit clause is not decoration.** A parity figure is a claim about
a (code, comparator, corpus) triple. Evidence that quotes a hash or a digest
without naming the commit its comparator was at cannot be checked by either
route, because a failure to reproduce is then indistinguishable from a shape
change. Such evidence is bucket 3 regardless of what hashes it carries. This
demoted `WP-1.3` (legs written as `<on-render>` / `<off-render>` placeholders)
in section 6.

Counts at the audited base `ba9c3ea`:

| bucket | count |
|---|---|
| 1 | **0** |
| 2 | 64 |
| 3 | 75 (floor) |

Summing: 0 + 64 + 75 = 139, matching 3e. At live HEAD `6366eb3`, WP-5.5a's
revision moves its four run citations from bucket 3 to bucket 1, giving
1 checkable pair plus 3 still needing re-measurement.

---

## 5. Check results

### 5a. Bucket 1, the only member: WP-5.5a. CHECK PASSES.

This is the first and so far only application of revision 44's designed method
in this execution, and it is the cheap one: no re-run, just confirm the quoted
hashes are the artifacts the WP claims to compare.

WP-5.5a claims a **before** leg rendered in the `wp55a-before` worktree at
`c1253d8` with its three code files reverted to `a3fb35c` content, and an
**after** leg rendered in `wp55a` at `c1253d8`. Both worktrees still exist.
Hashing every `reader.pdf` in each:

| quoted by WP-5.5a | leg | artifact found | result |
|---|---|---|---|
| `0460c081226ea530fcb8431c61f202f18530b7f1d88a865a794502451dd89e83` | A, before (segno) | `wp55a-before/editions/010/render-2026-09-18T11-25-02/en/reader.pdf` | **match** |
| `15d3bd5aef0dfb1f2c989c565686fb992dc9966d517e21414b25db55c0d98200` | B, after (committed asset) | `wp55a/editions/010/render-2026-09-18T11-26-27/en/reader.pdf` | **match** |

Three things corroborate beyond the hashes themselves. Each hash is unique
across the twelve `reader.pdf` files in the two worktrees. The before-leg hash
is in the **before** worktree and the after-leg hash in the **after** one, which
is the assignment WP-5.5a claims and not its reverse. And the two renders are
timestamped 11:25:02 and 11:26:27, eighty-five seconds apart, consistent with
one pair rendered back to back rather than two runs picked from different
sessions.

**No mismatch. WP-5.5a's re-measurement is provenance-confirmed.** Its figures
at `c1253d8` (web tree byte-identical, 0 pages differing, 68,530 glyph
positions across 1,501 shows at 0.000000 pt, Tier V channel delta 0, 162 boxes,
54 rotations, 1,733 colour entries, 85 annotations of which 85 links) are the
figures those two PDFs produced.

The three *earlier* WP-5.5a runs remain bucket 3: they quote no hashes, and
their legs (`a0714c3`, `ee15768`) no longer exist. WP-5.5a re-rendered rather
than defend them, which is the right call and is why only the third pair is
checkable.

**This row is also the audit's clearest illustration of the commit clause.**
WP-5.5a reports 1,733 colour entries and 85 annotations; WP-0.2g reports 1,720
and 84 on the same edition. Both are correct: the source-codes asset landed in
between. Neither number means anything without its base.

### 5b. At HEAD, `ba9c3ea` (WP-0.2g's comparator)

| claim | recorded | reproduced | inputs recorded in the reproduced verdict |
|---|---|---|---|
| WP-0.2g A-vs-A | `468eac3c32c8a4e2` | **`468eac3c32c8a4e2`** | a = b = `7b39d112...` |
| WP-0.2g A-vs-B | `09626f78981b6819` | **`09626f78981b6819`** | a `7b39d112...`, b `4e8906ae...` |

### 5c. At `521ab79` (WP-0.2h / WP-0.2i / WP-2.0b's comparator)

| claim | recorded | reproduced | inputs recorded in the reproduced verdict |
|---|---|---|---|
| A-vs-A | `0e21644ee602ff8a` | **`0e21644ee602ff8a`** | a = b = `7b39d112...` |
| A-vs-B | `6e932ea43678b91a` | **`6e932ea43678b91a`** | a `7b39d112...`, b `4e8906ae...` |

The same run also reproduced WP-0.2i's corpus figure and WP-0.2h's restatement
of it, verbatim from stdout:

    tier E glyph positions: pass (68800 glyphs, 1488 shows,
    worst excess 0.000000 pt, worst ratio 0.0000, 0 violations)

### 5d. Do the input hashes match the artifacts the WPs claim to compare?

Independently, every surviving `editions/010/render-*/en/reader.pdf` was
hashed:

| reader.pdf sha256 | render dir |
|---|---|
| `7b39d11271e335e4928d403a5bfcf6eeca27b6757d5d26a0822f0121527f9156` | `render-2026-09-14T01-47-59` |
| `4e8906ae1beaf58e7d7c1151566b27763327ad3aafefc55af3df9086304865a6` | `render-2026-09-14T01-49-02` |

WP-0.2a, WP-0.2b, WP-0.2c, WP-0.2e, WP-0.2g, WP-0.2h and WP-0.2i all name
`render-2026-09-14T01-47-59` as A and `render-2026-09-14T01-49-02` as B. The
reproduced verdicts' `a_reader_sha256` and `b_reader_sha256` are exactly those
two values.

Corroborating from a second party: `WP-5.3b-i.verify.md:55` independently
records `7b39d11271e335e4928d403a5bfcf6eeca27b6757d5d26a0822f0121527f9156` for
`render-2026-09-14T01-47-59/en/reader.pdf`, matching this audit's hash.

And from a third: `WP-0.2g.verify.md`, which landed on main after this audit's
base, reproduces the same two digests and records that `468eac3c32c8a4e2` "was
produced a THIRD time, from an unrelated isolated" working directory. Counting
the worker, that verifier and this audit, `468eac3c32c8a4e2` has now been
produced by at least three parties from at least three directories. **A
crossover does not survive that.**

### 5e. Mismatches

**No mismatch was found in any figure this audit was able to check.** All four
reproduced digests, both reproduced input hashes and the reproduced glyph
corpus agree with the published record to the byte.

Provenance-confirmed: **4 distinct digests, 14 of the 64 digest citations,
covering WP-0.2g, WP-0.2h, WP-0.2h.verify, WP-0.2i, WP-0.2i.verify and
WP-2.0b.** Confirmed separately: WP-2.0b's one `staged_input_digest`, with the
caveat of 1c.

### 5f. Which figures move with the base, and which do not

The coordinator's standing question, and worth more than a clean bill of
health: are the figures that disagree across WPs **base mismatches** or
**measurement corruption**? A base mismatch means the numbers are individually
sound and collectively unanchored, which is a documentation failure. Corruption
means a number came from the wrong run.

The question is answerable by removing the supposed cause and measuring (rule
11). If a differing render moves the figures, the disagreements could be
render-level. If it does not, they cannot be.

**Measured: five different renders of edition 010, five different `reader.pdf`
sha256 values, all compared A-vs-A at one fixed base (`521ab79`).**

| render | reader.pdf | glyphs | shows | domain pages | page_count |
|---|---|---|---|---|---|
| `render-2026-09-13T12-57-21` | `9aea26d7...` | 68800 | 1488 | 54 | 56 |
| `render-2026-09-14T01-32-52` | `af5cd926...` | 68800 | 1488 | 54 | 56 |
| `render-2026-09-14T01-41-32` | `b9cbbb5a...` | 68800 | 1488 | 54 | 56 |
| `render-2026-09-14T01-47-59` | `7b39d112...` | 68800 | 1488 | 54 | 56 |
| `render-2026-09-14T01-49-02` | `4e8906ae...` | 68800 | 1488 | 54 | 56 |

**Invariant across every one.** All five share one `staged_input_digest`
(`ac856f9f...`, section 1c), so they are five renders of one content base.

**The partition, stated as narrowly as the evidence supports.** The glyph
corpus figure is invariant under **re-rendering at a fixed content base and a
fixed comparator**. It is therefore not sensitive to render identity, and a
disagreement between two glyph figures cannot be explained by "different
render". It can only come from a different content base, a different
comparator, or corruption. This corroborates WP-5.3b-ii's finding that the
critic counts are identical across `01-47-59` and `01-49-02`, by a different
instrument on a different clause.

**What that does and does not license.** It removes the render-level
explanation, which is the one that would have been benign and uninformative. It
does **not** by itself prove the remaining disagreements are base mismatches
rather than corruption, because both survive this test. What it does is make
the base explanation checkable: 68,800/1,488 is confirmed at `521ab79` over the
`01-47-59` corpus (section 5c) and 68,530/1,501 is confirmed at `c1253d8` over
WP-5.5a's corpus (section 5a). **Two figures, two bases, both provenance-
confirmed, neither corrupt.** For that pair the base-mismatch reading is
supported by measurement rather than assumed. The 69,071/1,503 figure is not
audited here; the WP-0.2i rework owns reconciling it and this audit does not
duplicate that.

**One standing hypothesis is retired outright.** The plan has carried the idea
that the larger glyph figures count all 56 pages against a 54-page interior
domain. Measured from a single verdict, so the two numbers cannot be from
different runs: the verdict reporting `glyphs 68800` carries
`domain.first_page 2`, `domain.last_page 55` (**54 pages**) and
`tier_s.page_count.a 56`. **68,800 is a 54-page count taken from a 56-page
PDF**, so the page-count hypothesis does not explain it, and the same holds in
all five rows above.

### 5g. Two discrepancies found that are not crossovers, and one gap

1. **`WP-2.0b.md` and `WP-2.0b.verify.md` disagree on the oracle-only verdict
   digest and neither remarks on it.** The worker records
   `11a9c0a8f256a0de...` "both times"; the verifier, reproducing "the same"
   oracle-only run at the worker's own commit `e5e741a`, records
   `38f91a9493a5a571...` "both times". Both assert byte-determinism; the two
   values are different. WP-0.2g Residual 2 treats `38f91a94...` as the
   standing value. Whether this is a commit-window difference or a crossover is
   **not discriminable from the record**, because oracle-only stages a render
   leg and neither file quotes input hashes. It is the single most suspicious
   pair in the corpus and it is unresolved.

2. **`WP-0.2i`'s floor fixture carries no digest.** `stairdrift` is the floor,
   and the whole plan's Tier E margin is `1 / 0.2500 = 4.00x`. The digest list
   in `WP-0.2i.md:187-191` records control, drift, kern02, kern005, kern001,
   kern00001 and linmatrix, and **omits stairdrift and smoothdrift**. The
   verifier already found this ("What fails is replayability of the floor",
   `WP-0.2i.verify.md:17`; "`mkdrift.py` builds `stairdrift`, which IS the
   floor. It appears **zero times**" in the recorded loop, `:146`).

   What redeems the number is not a record but a second measurement: the
   verifier independently built the fixture and got `0.2500`, `0 violations`,
   `4.00x`, plus `76.38%` flats (`WP-0.2i.verify.md:125-129`). **A crossover
   would have had to produce the same three numbers twice, in two different
   agents' runs.** That is the strongest evidence available for the margin, and
   it is evidence of a different kind than the rest of this audit rests on.

3. **The shared `output/parity/010/verdict.json` is still on disk and is
   nobody's.** It carries `mode: pre_rendered`, `a_reader_sha256`
   `3a599874...`, `b_reader_sha256` `db7ede74...` and digest `fcf7d18c1c4aa7d9`
   (mtime 2026-09-17 23:35). Neither input hash matches any surviving
   `editions/010/render-*`, and at `ba9c3ea` no evidence file quoted either. It
   is a verdict from some agent's run, left in the shared path. It is the hazard
   made visible, not itself a defect.

   **This is the two-hash check doing precisely its job.** The orphan is a
   complete, valid, plausible-looking verdict sitting in the path every agent
   writes to; nothing about its clause figures says it is anyone's or no one's.
   The only thing that identifies it as nobody's is that its two reader hashes
   match no artifact any WP claims to compare. Independently,
   `WP-0.2g.verify.md:210` (post-base) quotes the same
   `3a599874139595889672eeefbce57cf542747c01de07170eac97dc0c0ddab406`, so a
   second party found the same orphan by the same route.

---

## 6. Worklist

Ordered by how load-bearing the number is.

**Tier 1, load-bearing on a gate or a plan decision.**

1. `WP-0.2i` floor `stairdrift` (ratio `0.2500`, 0 violations, margin `4.00x`).
   Bucket 3. Twice-measured but never digest-recorded. **Remedy: record a
   digest for `stairdrift` and `smoothdrift`, and add them to the recorded run
   loop** (already WP-0.2i.verify recommendation 2). Until then the margin is
   corroborated, not replayable.
2. `WP-2.0b` oracle-only digest, `11a9c0a8...` against the verifier's
   `38f91a94...`. Bucket 2, unresolved. **Remedy: one `--oracle-only` run at
   `e5e741a` in isolation** settles which value that commit produces. Needs a
   real render leg, so it is the most expensive item here and the most
   necessary.
3. `WP-0.2d`'s 21 fault-suite and perturbation digests, including the `241`
   max channel delta that revision 9's critique, `WP-1.3` and `WP-5.2` all
   inherit. Bucket 2, unchecked. Each is one isolated `--pre-rendered` run
   against a fixture pair; the fixtures must be rebuilt first.

**Tier 2, quoted by an accepted WP, not currently gating.**

4. `WP-5.5a`'s re-measurement. **DONE, see 5a: the third pair is bucket 1 and
   passes.** What remains is only its three superseded runs at `a0714c3` and
   `ee15768`, whose legs no longer exist; they are bucket 3 and should be left
   superseded rather than re-measured, since WP-5.5a already re-rendered instead
   of defending them. Its corpus is 68,530 glyphs across 1,501 shows where
   WP-0.2i's is 68,800 across 1,488. Both are confirmed at their own bases, and
   section 5f rules out the render as the cause; the specific attribution to the
   source-codes asset landing in between comes from WP-5.5a and the coordinator
   and is **not** measured here.
5. `WP-0.2e`'s `fd6608a2` / `28d7c3a2` pair and `WP-0.2b`'s `710878fb` /
   `a195f86d` pair. Bucket 2. Both are reproducible the same way as section 5,
   at their own commits, against render trees that still exist.
6. `WP-0.2c`'s three digests and `WP-0.0c`'s two. Bucket 2, same route.
   `WP-0.0c`'s legs (`render-2026-09-14T17-*`) no longer exist, so it drops to
   bucket 3 in practice.
7. `WP-1.3`'s `f163755a...` (hyphenation on/off, 26 pages text, 88 structure
   mismatches). Bucket 2, but its legs are written as `<on-render>` /
   `<off-render>` placeholders, so the inputs are not even named. Effectively
   bucket 3.

**Tier 3, fixture and demo runs.**

8. The digest-less fixture and demo runs, counted from section 3d:
   `WP-0.2b` 12, `WP-0.2b.verify` 12, `WP-0.2e` 10, `WP-0.2e.verify` 14,
   `WP-0.2c` 1, `WP-0.2c.verify` 1, `WP-2.0b.verify` 4. Summing those seven:
   **54**. Bucket 3. Individually low-stakes; collectively they are what the
   expected-detections matrix rests on.

**Prerequisite for the whole list.** WP-0.2k. Every item above must be
re-measured after it lands, or with an isolated working directory, or it
re-enters the same window it is meant to escape.

**One change that would retire most of this list.** Every item in tiers 2 and 3
is expensive only because the evidence quotes a digest without the two hashes
that digest covers. A WP that prints its verdict's `inputs` block beside its
digest, and names its base commit, lands in bucket 1 and is checkable by a
reader in seconds with no re-run. WP-5.5a now does exactly that and is the only
figure in the corpus this audit could clear without rebuilding anything. **That
is the cheapest available fix and it is a documentation habit, not code.**

---

## 7. What this audit cannot discriminate (rule 10)

### What a two-hash check cannot discriminate in `--pre-rendered` mode

This is the central question, because `--pre-rendered` is how every run in this
corpus but two was made, and it emits **only** the two reader hashes: no
`staged_input_digest`, no `staleness` (section on the premise). Two hashes
identify the two PDFs compared, and nothing else. Four cases, the first three of
which the check separates sharply:

**Case 0, specific to this mode: the staged inputs behind the two PDFs are
unpinned, and nothing in a `--pre-rendered` verdict can pin them.** The mode is
handed two finished PDFs and never sees what produced them. So a
`--pre-rendered` figure is a claim about two files, not about the edition
content, the manifest, or the render that made them. Where a WP's claim is
really about the edition rather than about two PDFs, the verdict does not
support it, and no amount of care in writing it up would change that. That is
the cost of the mode, paid by roughly the whole corpus.

**Case 1: replaced by a run over different artifacts. CAUGHT.** The verdict
carries hashes that match no artifact the WP claims to compare. This is the
dangerous case and the check finds it, as the orphan in 5g.3 demonstrates in
the live tree.

**Case 2: replaced by a run over the same two PDFs at the same commit.
INVISIBLE, AND HARMLESS.** The replacing verdict is byte-identical to the one
it replaced. Nothing was lost, so the check needs no power here. Concretely,
when several agents all ran `--pre-rendered <01-47-59> <01-49-02>` at the same
commit, they were overwriting each other with identical bytes throughout, and
that is most of what happened in the shared window.

**Case 3: replaced by a run over the same two PDFs at a DIFFERENT commit.
INVISIBLE TO THE HASHES, AND NOT HARMLESS. This is where the check's power
actually stops.** The reader hashes are correct, the verdict is valid and
plausible, and the clause figures belong to a different comparator than the WP
claims. No amount of hash-checking separates it from the real thing, because
the hashes pin the corpus and say nothing about the code that measured it.

Only two things reach case 3. Reproducing the digest at the named commit, which
is why the base-commit clause is in the bucket definitions and why bucket 3
swallows evidence that names no base. Or an independent re-measurement by a
second party, which is what rescues the `4.00x` margin.

Case 3 is not hypothetical. It is the shape of the unresolved WP-2.0b
disagreement in 5g.1, where the worker and verifier were at `443aaa8` and
`e5e741a`, and it is precisely the risk WP-5.5a took seriously enough to
re-render a third time rather than defend earlier numbers. **A parity figure
that does not name its base is not checkable by any method in this audit.**

### Everything else this audit cannot discriminate

- It cannot discriminate anything at all for bucket 3. 75 run citations, more
  than half the corpus, quote a number with no binding of any kind. For those,
  re-measurement is the only route, and re-measurement at a later commit
  answers a different question than the original run asked.
- **Reproduction proves provenance only where the comparator is identical.** At
  HEAD, that was established by `git log 521ab79..ba9c3ea` over
  `mag/src/parity.rs`, `mag/src/parity/` and `meta/verification/parity.yaml`
  returning exactly one commit, WP-0.2g's own. It was not established for any
  other WP's window, so no claim is made beyond the four digests in section 5.
- `staged_input_digest` is emitted only by the staging modes, and where it is
  emitted it is constant across seven render legs of edition 010 (section 1c).
  Any future method counting it as a discriminator is counting a constant in the
  two runs that have it and a missing field in the other 137.
- This audit establishes that four published digests came from the artifacts
  their WPs name. It says **nothing** about whether those artifacts were the
  right ones to compare, nor whether the clauses that passed should have
  passed. Provenance is not correctness.
- The 139 total is a floor (3d, 3e). Seven of the eleven digest-less rows were
  counted from fan-out reads rather than re-counted against the source tables.
  A reader re-deriving them may find more.

- **The partition of section 5f is narrow.** It shows the glyph corpus, domain
  and page count are invariant under re-rendering at one fixed base. It does not
  show that *every* parity figure is. Clauses that read per-page raster or
  per-glyph offsets could in principle move between two byte-different renders;
  they did not here, but five renders of one edition is not a proof about the
  clause family. Which figures move and which do not is now a question with one
  measured answer, not a settled partition.

**A second party is worth more than a second check.** The one figure that
matters most, the `4.00x` margin, has no digest and is nonetheless the
best-evidenced number here, because two agents measured it separately and
agreed. Five count disagreements in this execution were found by re-deriving
rather than by an author, and one of them, in section 1a, was this audit's own.
Provenance records help; an independent re-measurement by someone else helps
more.

---

## 8. Configuration, recorded per rule 9's spirit

**Every parity number taken before WP-0.2k lands was measured while six to
nine agents shared one output path.** That includes every number in this
corpus, every number in this audit, and every number in the worklist above
until WP-0.2k lands and closes the window. It is a property of the whole
population, not of any one measurement, and it does not become false because a
digest reproduces.

The two WPs that worked around it did so by different routes, both recorded
here so a reader can tell them apart: WP-0.2g used an isolated working
directory with symlinks (the route this audit reuses); WP-0.2c used distinct
**edition strings** (`010-selftest`, `010-ab`, `010-merge-cal`) so each run got
its own `out_dir`. Neither is a fix.

**The window was observed open during this audit's own replay.** A process
listing taken while the section 9 replay was running showed three `mag parity`
processes belonging to three different agents at once: this audit's
`--pre-rendered` run, a `--oracle-only` run from `wp02k-replay-base`, and a
`--pre-rendered` fault run from `wp22a-replay`. All three were writing into
their own worktrees, so none collided, which is the point: **isolation is what
kept them apart, not the comparator.** Any run made without it, then or now,
lands in the same file.

## 9. Replay

Run from the repository root with the branch checked out. `T` is an isolated
comparator working directory, because the hazard is live. `TYPST_ROOT` is unset
deliberately: it is the typst CLI's project root, not an install prefix, and an
unrelated value there fails the replay outright.

`E` is where the render artifacts live. They are untracked, so a replay from a
fresh worktree must point `E` at the tree that holds them; `$PWD/editions` is
the default and is correct when replaying from the tree that rendered them.

**This block was extracted programmatically from this finished file and run
from a worktree that is not the one it was developed in** (rule 12). It
reproduced, in one pass: `files 19 citations 64 distinct 47`; the two HEAD
digests `468eac3c32c8a4e2` and `09626f78981b6819` with their `inputs` block;
the two `521ab79` digests `0e21644ee602ff8a` and `6e932ea43678b91a`; the
`68800 glyphs, 1488 shows` clause line; and all five invariance rows. Every
value matches the one recorded above.

Two defects in an earlier version of this block were found by running it rather
than by reading it, and are noted because they are the same class of error the
audit is about: `set -o pipefail` plus a `grep` with no matches aborted the run
at the first check, and the final `git log` ran from outside a repository
because the preceding section had left the cwd in `$T`. Both are fixed here.

```sh
set -e
set -o pipefail
unset TYPST_ROOT
R=$PWD
E=${E:-$PWD/editions}
T=${T:-$(mktemp -d)}

echo "### 1a: no evidence file quotes a reader hash, only field names"
for f in a_reader_sha256 b_reader_sha256 staged_input_digest; do
  echo "$f $(grep -rho "$f" meta/verification/evidence/*.md | wc -l)"
done
echo "values quoted beside a field name (expect none):"
grep -rnoE "(a_reader_sha256|b_reader_sha256)\W{0,6}[0-9a-f]{64}" \
  meta/verification/evidence/*.md || echo "none"

echo "### 1c: the staged digest is constant across render legs"
uv run python - "$E" <<'PY'
import json, hashlib, pathlib, sys
for d in sorted((pathlib.Path(sys.argv[1]) / "010").glob("render-*")):
    r = d / "request.json"
    if not r.exists():
        continue
    rows = json.load(open(r)).get("inputs")
    ents = sorted(
        f"{w['targetPath']}\x1f"
        f"{hashlib.sha256(pathlib.Path(w['sourcePath']).read_bytes()).hexdigest()}"
        for w in rows
    )
    print(d.name, len(rows), hashlib.sha256("\x1e".join(ents).encode()).hexdigest()[:16])
PY

echo "### 5a: bucket 1, WP-5.5a's two quoted reader hashes"
for w in $(git worktree list --porcelain | awk '/^worktree /{print $2}'); do
  for d in "$w"/editions/010/render-*; do
    test -f "$d/en/reader.pdf" && \
      echo "$(shasum -a 256 "$d/en/reader.pdf" | cut -c1-16) ${d#"$(dirname "$w")"/}"
  done
done 2>/dev/null | grep -E "^(0460c081226ea530|15d3bd5aef0dfb1f) " || \
  echo "legs not present in this checkout"

echo "### 5d: hash every surviving render leg"
for d in "$E"/010/render-*; do
  test -f "$d/en/reader.pdf" && \
    echo "$(shasum -a 256 "$d/en/reader.pdf" | cut -c1-16)  $(basename "$d")"
done

echo "### 3c: derive the digest citation count from the enumeration"
uv run python - <<'PY'
import re, pathlib
skip = {
    "WP-5.1e.md", "WP-5.2.verify.md", "WP-5.1a.md", "WP-5.1a.verify.md",
    "WP-5.1b.md", "WP-5.1b.verify.md", "WP-5.1d.md", "WP-5.1d.verify.md",
    "WP-5.3b-i.verify.md", "WP-5.4.md", "WP-5.4.verify.md", "WP-5.4b.md",
    "WP-5.4b.verify.md", "WP-5.5b.md", "WP-5.7.md", "WP-1.4.md",
    "WP-1.4.verify.md", "WP-1.7.md", "WP-1.8.md",
    "PARITY-PROVENANCE-AUDIT.md",
}
rx = re.compile(r"(?<![0-9a-f])([0-9a-f]{64}|[0-9a-f]{16})(?![0-9a-f])")
cit = {}
for f in sorted(pathlib.Path("meta/verification/evidence").glob("*.md")):
    if f.name in skip:
        continue
    for line in f.read_text().splitlines():
        for m in rx.findall(line):
            if m[:16] != "ac856f9f4b827d5e":
                cit.setdefault(m[:16], set()).add(f.name)
per = {}
for k, v in cit.items():
    for f in v:
        per[f] = per.get(f, 0) + 1
for f in sorted(per):
    print(f, per[f])
print("files", len(per), "citations", sum(per.values()), "distinct", len(cit))
PY

echo "### 5b: reproduce WP-0.2g's digests at HEAD, in isolation"
mkdir -p "$T/head/output"
for d in meta prompts src; do ln -sfn "$R/$d" "$T/head/$d"; done
ln -sfn "$E" "$T/head/editions"
(cd mag && cargo build)
A=$E/010/render-2026-09-14T01-47-59
B=$E/010/render-2026-09-14T01-49-02
cd "$T/head"
V=$T/head/output/parity/010/verdict.json
"$R/mag/target/debug/mag" parity 010 --pre-rendered "$A" "$A" > /dev/null
echo "A-vs-A expect 468eac3c32c8a4e2 got $(shasum -a 256 "$V" | cut -c1-16)"
"$R/mag/target/debug/mag" parity 010 --pre-rendered "$A" "$B" > /dev/null
echo "A-vs-B expect 09626f78981b6819 got $(shasum -a 256 "$V" | cut -c1-16)"
uv --directory "$R" run python -c \
  "import json,sys; print(json.load(open(sys.argv[1]))['inputs'])" "$V"
cd "$R"

echo "### 5c: reproduce the most-cited pair at 521ab79"
git worktree add "$T/prev" 521ab79
(cd "$T/prev/mag" && cargo build)
mkdir -p "$T/prevrun/output"
for d in meta prompts src; do ln -sfn "$T/prev/$d" "$T/prevrun/$d"; done
ln -sfn "$E" "$T/prevrun/editions"
cd "$T/prevrun"
V=$T/prevrun/output/parity/010/verdict.json
"$T/prev/mag/target/debug/mag" parity 010 --pre-rendered "$A" "$A" | grep "glyph positions"
echo "A-vs-A expect 0e21644ee602ff8a got $(shasum -a 256 "$V" | cut -c1-16)"
"$T/prev/mag/target/debug/mag" parity 010 --pre-rendered "$A" "$B" > /dev/null
echo "A-vs-B expect 6e932ea43678b91a got $(shasum -a 256 "$V" | cut -c1-16)"

echo "### 5f: the corpus figure is invariant across renders at one base"
for n in 2026-09-13T12-57-21 2026-09-14T01-32-52 2026-09-14T01-41-32 \
         2026-09-14T01-47-59 2026-09-14T01-49-02; do
  D=$E/010/render-$n
  "$T/prev/mag/target/debug/mag" parity 010 --pre-rendered "$D" "$D" > /dev/null
  echo "$n $(uv --directory "$T/prev" run python -c "
import json, sys
d = json.load(open(sys.argv[1]))
g = d['tier_e']['glyph_positions']
print('glyphs', g['glyphs'], 'shows', g['shows'],
      'domain', d['domain']['last_page'] - d['domain']['first_page'] + 1,
      'n', d['tier_s']['page_count']['a'])" "$V")"
done

echo "### section 2: the commit window, from the repository root"
cd "$R"
git log --oneline 521ab79..ba9c3ea -- \
  mag/src/parity.rs mag/src/parity/ meta/verification/parity.yaml
```

## Verdicts

- **The brief's three-field premise is falsified, and so was its first
  correction.** `staged_input_digest` is **mode-dependent**: emitted by the
  staging modes, absent under `--pre-rendered` along with `staleness`. Verified
  from two real emitted verdicts, one per mode, not from the struct.
- Where it does exist, `staged_input_digest` is constant across seven render
  legs of edition 010, so it contributes **zero** discrimination even then.
- Every run in this corpus but two is `--pre-rendered`, so the two-hash ceiling
  is a property of how the WPs ran parity, not of how carefully they wrote it up.
- **The corpus figures do not move with the render.** Five renders, five PDF
  hashes, one base: identical glyphs, shows, domain and page count. Disagreeing
  corpus figures are base differences, not render artefacts.
- The 56-versus-54 page-count hypothesis is **retired**: one verdict carries
  `glyphs 68800`, a 54-page domain and `page_count 56` together.
- Buckets re-derived from the two fields that exist, with a base-commit clause
  added: evidence naming no base is bucket 3 whatever hashes it carries.
- **139 parity run citations** in accepted evidence at `ba9c3ea`
  (64 digest-bearing, 75 digest-less), a floor rather than a total.
- **Bucket 1 had zero members at `ba9c3ea` and has exactly one at `6366eb3`.**
  WP-5.5a's revision put it there, the check was run, and **it passes**: both
  quoted reader hashes are the two artifacts it claims to compare, in the
  worktrees and the order it claims.
- Reproduction is a stronger check than the one designed, and it was applied to
  bucket 2: **4 distinct digests provenance-confirmed**, covering 14 digest
  citations and six evidence files, together with WP-0.2i's
  `68800 glyphs, 1488 shows` corpus figure and both input hashes.
- **No mismatch found in any figure this audit could check.** No published
  number is known to have come from the wrong run.
- One unresolved disagreement (`WP-2.0b` oracle-only, `11a9c0a8` against
  `38f91a94`), not discriminable from the record. It is a case-3 shape.
- The plan's headline Tier E margin `4.00x` has no digest, and rests on two
  independent measurements instead.
- `mag parity` runs from any directory presenting the repo-root markers; a
  worktree is sufficient but not necessary, contrary to the brief and WP-5.5a.

## What is and is not proven

**Proven.**

- `--pre-rendered` verdicts carry two hashes, not three; observed in a verdict
  this audit produced, and traced to `stage_legs()` returning `digest: None`.
- Seven of ten surviving 010 render directories share one staged input digest,
  recomputed independently of the comparator.
- WP-0.2g's two digests reproduce byte-for-byte at HEAD, and WP-0.2h /
  WP-0.2i / WP-2.0b's two reproduce byte-for-byte at `521ab79`, each from the
  render trees those WPs name.
- The reproduced verdicts' input hashes equal the sha256 of
  `render-2026-09-14T01-47-59/en/reader.pdf` and
  `render-2026-09-14T01-49-02/en/reader.pdf`, hashed independently.
- WP-2.0b's quoted `staged_input_digest` recomputes exactly.
- `stairdrift` and `smoothdrift` appear in WP-0.2i's floor table and in no
  digest list in that file.
- WP-5.5a's two quoted reader hashes are the sha256 of
  `wp55a-before/editions/010/render-2026-09-18T11-25-02/en/reader.pdf` and
  `wp55a/editions/010/render-2026-09-18T11-26-27/en/reader.pdf`, each unique
  across the twelve `reader.pdf` files in those two worktrees.
- `mag parity` ran to completion from a scratch directory that is not a git
  worktree, holding a real `output/` and symlinks to `editions`, `meta`,
  `prompts` and `src`.
- Five renders of edition 010 with five distinct `reader.pdf` sha256 values,
  compared A-vs-A at `521ab79`, all report `glyphs 68800`, `shows 1488`, a
  54-page domain and `page_count 56`.
- A single verdict carries `glyphs 68800` together with a 54-page domain and
  `page_count 56`, so 68,800 is not a 56-page count.
- The `--pre-rendered` verdict has 8 top-level keys at `521ab79` and 9 at
  `ba9c3ea`; the `--oracle-only` verdict has 12, a strict superset.

**Not proven.**

- That the orphaned `output/parity/010/verdict.json` belongs to no accepted
  figure at live HEAD. It was checked against the corpus at `ba9c3ea`, and
  `WP-0.2g.verify.md` quotes its `a_reader_sha256` without this audit
  establishing why.
- Anything about the other 43 distinct digests. They are unchecked, not
  cleared.
- Anything about the 75 digest-less run citations.
- Whether WP-2.0b's `11a9c0a8` or the verifier's `38f91a94` is the oracle-only
  digest at `e5e741a`.
- That the digest-less count is 75 rather than more: seven of its eleven rows
  are second-hand.
- That every parity figure is render-invariant. Section 5f measured four
  figures across five renders at one base. It did not test the raster or
  per-glyph-offset clauses for render sensitivity, and it tested one edition.
- That the 68,800 versus 68,530 difference is caused by the source-codes asset.
  Both figures are confirmed at their own bases and the render is ruled out as
  the cause; the specific attribution is someone else's and is not measured
  here. The 69,071/1,503 figure is not audited at all; the WP-0.2i rework owns
  reconciling it.
- That any clause outcome is correct. This audit checks where numbers came
  from, not whether they are right.
