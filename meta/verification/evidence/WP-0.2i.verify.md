# WP-0.2i verification

Verifier for WP-0.2i (per-glyph positions), protocol rule 3, fourth pass.
Worker rework commit `0ec67a9`, replayed in a worktree created for this
verification at that commit and in no other directory. This is the GATE, so
the standard is higher than elsewhere, and rule 3d binds me to re-read the
THIRD verification (`521ab79`) rather than only the new evidence. I did.

## Verdict

**Verdict: ACCEPTED.**

The three rejections were, in order, the MECHANISM, the RECORD, and three
overstated claims. The mechanism was cleared by the previous verifier, who
attacked it across seven orders of magnitude and could not break it; I did not
re-derive it. What I tested is what the third rejection demanded: whether the
floor can now be rebuilt by someone holding only this repository, and whether
the restated claims are true.

**The floor is rebuildable. I rebuilt it.** `mkfixtures.py` ran in a worktree
the author never touched, resolved every path against that checkout, built all
24 fixtures including `stairdrift`, and the gate reproduced: floor 0.2500 at 0
violations, ceiling 10.2500, margin 4.00x. **25 of the 26 verdict digests in
`## Verdicts` reproduce exactly.** The 26th is `glyphsub`, and the finding
there is that its digest is not reproducible by ANYONE, for a cause I isolated
and can fix in one line (finding 1).

Eight errata follow. **None of them touches the floor, the ceiling, the margin,
the commensurability law, the detection-floor bracket, the reconciliation
arithmetic, or the irreproducibility of 69,071.** Every load-bearing figure
reproduced. The errata are descriptive slips, and under rule 9 a corrected
figure propagates, so they are stated here in the form the plan should carry.

Acceptance rests on reproduction, not on an argument, with the four items
labelled under rule 10 in `## What I could not discriminate`, none of which
is load-bearing.

## The record is replayable, and the proof is not an argument

The third rejection's core was that `mkdrift.py` built the floor, appeared zero
times in the evidence, lived only at an absolute job path, and `exec`'d a
second scratch file. Each part is now answered by execution rather than by
prose:

- **Zero absolute paths**, verified by grep and not by reading:
  `grep -nE '/Users/|/home/|/tmp/'` over the committed generator and the
  evidence file exits **1**. The absence claim rests on that exit status and
  not on the empty output, because a failed grep and an empty grep print the
  same nothing: grep is three-way, 0 present, 1 absent, 2 or more unknown, and
  only 1 supports "none".
- **Paths resolve against the running checkout.** The generator announced
  `checkout /Users/.../vwp02i4`, which is MY worktree, not the author's, and
  `render tree ... (checkout default)`, `output root ... (checkout default)`.
  Rule 2b's announcement obligation is met in the executed output.
- **The env gate works and fails loud.** With `MAG_PARITY_RENDER_A` set to a
  nonexistent path it printed `render tree /nonexistent/tree (env)`, then
  `missing render tree: /nonexistent/tree/en/reader.pdf` and exited 1. An
  unknown fixture name exits 1 listing all 24 known names.
- **Seven scratch scripts, three of which `exec`'d a fourth from an absolute
  job path.** Confirmed exactly: `mkfix2.py`, `mkfix6.py` and `mkdrift.py` each
  carry
  `exec(open("/Users/franguijarro/.claude/jobs/7d99e27f/tmp/mkfix.py").read()...)`.
  Three, not two, not four.

**And the vindication is sharper than the evidence claims.** The author's
`mkfix.py` in that job directory has since been OVERWRITTEN by an unrelated
script: its mtime is 2026-09-18 08:03, later than `mkdrift.py`'s 09-17 12:08,
and it no longer contains the `# 1. drift` marker the three `exec` lines split
on. **The floor could no longer be rebuilt from the author's own scratch
directory either.** The scratch corpus did not merely fail to travel; it
decayed in place, inside the window between the rejection and the rework.
Committing the generator was not hygiene, it was recovery.

## Run loop against the registry, re-derived at the point of citation

Rule 9 binds me here, so I parsed both sides rather than counting by eye: the
`for f in ...` list out of the extracted `## Commands` block, and the
`BUILDERS` dict out of the generator's AST.

| direction | result |
| --- | --- |
| names in the run loop | 24, no duplicates |
| keys in `BUILDERS` | 24, no duplicates |
| in loop, not in registry | none |
| in registry, not in loop | none |

**24 both ways, set-equal, no asymmetric members.** `stairdrift` and
`smoothdrift` are both present, which was rejection item 3. With the four
determinism runs the block is 28 runs, as the brief states.

## The gate reproduces

All at base `0ec67a9`. Digest head is the first 16 hex of
`shasum -a 256 output/parity/010/verdict.json`.

| fixture | exit | ratio | viol | digest (head) | recorded? |
| --- | --- | --- | --- | --- | --- |
| A-vs-A run 1 | 0 | 0.0000 | 0 | `468eac3c32c8a4e2` | matches |
| A-vs-A run 2 | 0 | 0.0000 | 0 | `468eac3c32c8a4e2` | matches |
| A-vs-B run 1 | 0 | 0.0000 | 0 | `09626f78981b6819` | matches |
| A-vs-B run 2 | 0 | 0.0000 | 0 | `09626f78981b6819` | matches |
| control | 0 | 0.0000 | 0 | `494e4e1e46ad1698` | matches |
| **stairdrift (floor)** | 0 | **0.2500** | **0** | `df9909eeb8c68057` | matches |
| drift | 0 | 0.2500 | 0 | `bb6dc69d643f933d` | matches |
| smoothdrift | 0 | 0.6250 | 0 | `cf7376d833853612` | matches |
| **kern02 (ceiling)** | 1 | **10.2500** | 5 | `40d61b72f0daa2b9` | matches |
| kern005 | 1 | 2.5625 | 5 | `c768f28a0a19fed0` | matches |
| kern001 | 1 | 0.5625 | 1 | `b627c661ed777326` | matches |
| kern00001 | 1 | 0.0625 | 1 | `984c7ea44dd54011` | matches |
| linmatrix | 1 | 2.8542 | 9 | `372f53f82cb29adc` | matches |
| glyphsub | 1 | 0.0000 | 0 | `65bf9e73f3bc022e` | **differs**, finding 1 |
| ocmember | 1 | n/a | n/a | none | matches |
| annotap | 1 | n/a | n/a | none | matches |
| advstep | 1 | 0.6406 | 1 | `0c12d7a62f688784` | matches |
| advmid | 1 | 0.6406 | 1 | `a0b0f44deb108a4e` | matches |
| advtail02 | 1 | 10.2500 | 9 | `52c02c4c28aaeebd` | matches |
| advtail_small | 1 | 0.5625 | 1 | `4b54c1f0e2606289` | matches |
| advtail_late | 1 | 0.6406 | 1 | `c3756e274c23e606` | matches |
| vq_2q | 1 | 0.0250 | 40 | `3c3479b0ae488b99` | matches |
| vq_1q | 1 | 0.0125 | 40 | `c408a87501e26373` | matches |
| vq_half | 1 | 0.0125 | 40 | `ceddd179c6dc58f5` | matches |
| vq_quarter | 1 | 0.0125 | 40 | `37c2531a3999b6e9` | matches |
| vq_e2 | 1 | 0.0125 | 40 | `34fbab168991eae9` | matches |
| vq_e3 | 0 | 0.0000 | 0 | `eec4fa1a6a137b4e` | matches |
| vq_e4 | 0 | 0.0000 | 0 | `cbcaba0d705305a1` | matches |

**Floor `stairdrift` 0.2500 at 0 violations, ceiling `kern02` 10.2500, margin
1 / 0.25 = 4.00x against the required 2x. Met.** Worst excess on the ceiling
0.013550 pt, on `kern005` 0.002289 pt, on `linmatrix` 0.011169 pt, all as
recorded.

**This measurement ESTABLISHES the floor's provenance rather than corroborating
it**, and the distinction matters enough to state plainly, because a replay
that creates the record it appears to verify reads as corroboration a year
later. Until now the 4.00x margin carried no digest and rested on two agents
agreeing. It now carries one, at a named commit, with its inputs:

```
floor    stairdrift   digest df9909eeb8c68057   base 0ec67a9
  inputs.a_reader_sha256  b9f35d55f01933dbda6fa731e5ad95208e886768db016dc9bb33d601a302ccbe  (control)
  inputs.b_reader_sha256  7826a83303fbbdc00ba9b669683eee96a4f544b1ce59b9834060bac123084751  (stairdrift)
ceiling  kern02       digest 40d61b72f0daa2b9   base 0ec67a9
  inputs.b_reader_sha256  0966ae8fc2c064038d59a25f0dcfc59653c6be032863759d0184f446982c16cb  (kern02)
oracle leg A (identifies the run, not checkable: the WeasyPrint leg is not
byte-reproducible)
  editions/010/render-2026-09-14T01-47-59/en/reader.pdf
  7b39d11271e335e4928d403a5bfcf6eeca27b6757d5d26a0822f0121527f9156
```

The fixture hashes ARE checkable: 23 of 24 fixtures rebuilt byte-identically
from the committed generator, which is what makes the floor's digest mean
something. `glyphsub` is the exception, and that is finding 1.

## The restated claims, each checked against a measurement

**The law is `ratio = n/(8k)`.** Verified from a fixture rather than by
accepting the table. `linmatrix` writes its per-glyph violations with the raw
difference and bound, so I recovered n and k directly: the worst offender is
**n = 137 quanta at glyph k = 6**, and 137/48 = 2.8541666..., which is exactly
the verdict's `worst_ratio` of 2.8541666666666665. The bound sequence in those
violations is k x 0.000732421875 pt exactly (0.000732, 0.001465, 0.002197, ...).
Every recorded ratio decomposes to an integer n over 8k with the stated k:
2/8, 5/8, 1/16, 9/16, 41/16, 164/16, 41/64, 137/48, 2/80, 1/80. Sixteenths is
the k=2 case, as claimed. The strengthening is real.

**The detection floor is between 9.16e-08 and 9.16e-07 pt.** All seven
magnitudes reproduce: 2Q, Q, Q/2, Q/4 and Q/100 each fail with **40 violations**
and `worst_excess_pt` exactly **0.000000**, so every one is caught on SHAPE
ALONE with the magnitude bound contributing nothing; Q/1000 and Q/10000 pass
with 0. The supporting datum holds in the form that matters: **Q, Q/2, Q/4 and
Q/100 all record as the same one quantum at k=10, ratio 1/80, with the same 40
violations**, while 2Q records 2/80. The magnitude stopped mattering; only the
shape did. That is the evidence that the mechanism is quantisation rather than
magnitude, and it reproduced. (The factor spanned is 100, not 200; erratum 3.)

**Flats.** The generator printed `stairdrift flat steps 52549/68800 = 76.3794%`
on its own run, and I re-derived the same figure independently from the
staircase definition, with the first 24 offsets in ticks reading
`0 0 0 1 1 1 1 2 2 2 2 3 3 3 3 4 4 4 4 4 5 5 5 5`. Third independent
derivation. See erratum 5 for what the number is a property OF.

**The CTM-composing recommendation is discharged, and I checked the mechanism
rather than accepting it.** `display_list` reports **pass** for `stairdrift`,
`drift` and `smoothdrift` in the same runs where `glyph_positions` passes, so
the pypdf-built floor IS display-list equal and the plan's premise is false for
the TJ-kern class. The stated mechanism is that a TJ kern changes no field the
display list records. Reading `mag/src/parity/streams.rs`, the serialized
fields of `Element::Text` are `s, font, size, fill, glyphs, gids, m, tr, clip`,
with `offs` under `#[serde(skip)]`; `m` is computed from `self.tm` BEFORE the
item loop, and `glyphs`/`gids`/`s` come from string items only. So a kern
touches none of them. **One precision the evidence omits**: the kern DOES
accumulate into `tx`, and the show's last act is
`self.tm = mul(translate(tx, 0.0), self.tm)`, so a kern would move the NEXT
show's `m` if any show inherited. I measured that it does not:
**0 of 1,488 interior shows follow another show without an intervening
`Td`/`TD`/`T*`/`Tm`/`BT`/`ET`.** The mechanism holds, and it holds BECAUSE of
that corpus property, which the plan already records. Stated so the next reader
does not generalise it to a corpus where shows chain.

## The count reconciliation, scrutinised hardest

**Block 2 reproduced exactly**: `TJ shows 1488 glyphs 68800 odd tokens 0`,
`Tj shows 15 string bytes 537`, `document-wide shows 1503`, with page 1 at 5
shows / 166 bytes and page 56 at 10 shows / 371 bytes.

**I enumerated the 15 as members rather than inferring them from a total**, per
the brief. All 15, with the font resolved through each page's `/Font` resource
dict and the render mode taken from the last `Tr` before each show:

| pg | count | operator | font resource | subtype | Tr | bytes |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 5 | `Tj`, literal string | `/F2+0` | `/TrueType` | 3 | 166 |
| 56 | 10 | `Tj`, literal string | `/F2+0` | `/TrueType` | 3 | 371 |

Confirmed member by member: all 15 are `Tj` not `TJ`; all 15 are at render mode
`3 Tr`; all 15 are literal `(...)` strings with **zero backslash escapes**; all
15 are in a SIMPLE font, none `/Type0`; both cover pages carry **zero TJ
arrays**; and **no page in 2..55 carries a `Tj`**. 1,488 + 15 = 1,503, and the
gap is the two covers and nothing else. **The show half reconciles exactly and
the plan's hypothesis is CONFIRMED.** One member attribute is misstated in the
evidence; that is erratum 1.

The domain is not interpretive: my own verdict carries
`"interior: reader.pdf pages 2..n-1"`, `first_page 2`, `last_page 55`,
`page_count a 56 b 56` and `glyphs 68800` **in one document**, so 68,800 is a
54-page interior count and cannot be a 56-page count. That retires the
hypothesis independently of the cover measurement.

**69,071 is not reproducible, and I tried harder than the evidence did.** The
gap to close is 271. Cover countings:

| counting | cover total | document-wide |
| --- | --- | --- |
| string bytes | 537 | 69,337 |
| non-space bytes | 450 | 69,250 |
| alphanumeric | 430 | 69,230 |
| alphabetic | 411 | 69,211 |
| front cover alone | 166 | 68,966 |
| back cover alone | 371 | 69,171 |

Six countings, none yields 271 and none yields 69,071. **69,071 should be
DROPPED rather than re-cited or corrected to 69,337.** Correcting it would
assert that 69,337 is what WP-0.2f meant, which no artifact supports; dropping
it says only what is known. 68,800 / 1,488 travels with "54 interior pages";
1,503 travels with "whole document"; 69,337 is available if a document-wide
glyph figure is ever wanted.

**The base-mismatch alternative is dead, and the file-identity argument is the
decisive one.** I confirmed it at the source: WP-0.2f's own `## Commands` block
sets `R=editions/010/render-2026-09-14T01-47-59/en/reader.pdf` and calls it
"the oracle leg used as the base of every fixture". My verdict's
`a_reader_sha256` is `7b39d112...`, the same file. No commit, render or asset
difference can sit between two numbers taken from one artifact. I also
confirmed WP-0.2f states 69,071 / 1,503 exactly once, in prose, with no
producing command, and has no `.verify.md`.

Tested anyway, as populations: block 3 reproduced exactly. Seven DISTINCT
sha256 over `editions/010/render-*/en/reader.pdf` (sizes 87,139,111 to
87,139,128), all giving 1,488 shows and 68,800 glyphs, and
`per-page vectors all identical: True` over all 56 pages elementwise,
`interior pages carrying text: 47` against 54 interior pages, leaving 7 plates.
An aggregate can coincide; a 56-element vector does not.

**WP-5.5a's 68,530 / 1,501 is correctly NOT folded in.** I agree, and the
reason is stronger than parsimony: it is a different render pair at a different
base, `c1253d8`, after the source-codes asset landed, so it is an independent
measurement rather than a citation of this one. Folding it in would be picking
the story that accounts for the most numbers, which is what rule 11 forbids.

## Finding 1: the `glyphsub` digest is not reproducible by anyone

The one digest that did not match. My run gives `65bf9e73f3bc022e` against the
recorded `d6a545a433a25c6b`. **The substance reproduced exactly**: exit 1,
`tier S text: pass`, `glyph_positions: pass (ratio 0.0000, 0 violations)`,
`display_list: fail (12 pages differ)`, and the generator printed the same
choice, `CID 0089 (F) now draws A; widths and ToUnicode intact`. The blind spot
is caught by `gids` alone, exactly as claimed.

I isolated the cause by removing it and measuring:

- Building `glyphsub` in ONE environment, same Python, same fontTools 4.63.0,
  at 00:39 and again at 11:31 gives **two different sha256**. The fixture is
  not byte-reproducible across runs.
- The differing bytes (`cmp -l`) lie in exactly **three 4-byte fields** of the
  embedded font, 9 to 12 bytes depending on the pair: the `head` entry's
  checksum in the table directory, `head.checkSumAdjustment`, and the low word
  of `head.modified`. That is the signature of fontTools stamping the current
  time into `head.modified` on `save()` and recomputing the two checksums that
  depend on it.
- With `SOURCE_DATE_EPOCH=1000000000` pinned, two builds are **byte-identical**
  (`848d02715e540e7a...`), twice, on separate occasions. Remove the cause and
  the effect goes.
- The apparent counterexample confirms it: two UNPINNED builds run back to
  back were also identical to each other. Their mtimes were one second apart
  and `head.modified` has one-second resolution, so a sub-second build pair
  shares a timestamp. Builds hours apart do not.

So `d6a545a433a25c6b` was never reproducible by anyone more than a second away
from the author's run, and no fontTools version pin would have rescued it. **Recommended,
one line in the generator**: pin `head.modified` (or honour `SOURCE_DATE_EPOCH`)
before `face.save()`, and re-record the digest. Until then `## Verdicts` should
mark the `glyphsub` row as non-reproducible rather than leaving a digest that
fails on every replay. Not a rejection ground: it is the fixture for glyph
IDENTITY, not a threshold fixture, it sets neither floor nor ceiling, and its
clause outputs are stable.

## Errata

Corrections, not rejection grounds. Stated in the form the plan should carry,
because rule 9 makes a corrected figure propagate and nine plan sites are held
pending this verdict.

1. **"every one in the simple font `F1`" is FALSE.** All 15 cover shows use
   `/F2+0`, which is `/TrueType` `AAAAAA+Inter-Regular`. `/F1` is `/Type1`
   Helvetica, and it appears only as `BT /F1 12 Tf 14.4 TL ET`, a text object
   that shows nothing at all. Read: *every one in the simple font `F2+0`
   (Inter-Regular); the other simple font, Helvetica `F1`, is declared but
   draws no show.* This matters downstream because WP-5.4g is briefed off this
   passage and would go looking at the wrong resource.
   **It is also a rule-12 caption failure, the fourth instance**: the recorded
   command prints the render modes but never the font, so the caption claims
   something the block cannot show, and no replay would catch it. The other two
   named attributes, `Tj` and `3 Tr`, ARE covered.
2. **"Four distinct denominators appear (8, 16, 48, 64, 80)"** lists five. A
   count beside its own enumeration, the exact shape rule 9's last clause
   names. Read: *five distinct denominators.*
3. **"Q/2, Q/4 and Q/100 span a factor of 200"** is 50, not 200; 200 is the
   span of the whole failing set including 2Q, which records 2/80 rather than
   1/80. The accurate vivid form: *Q, Q/2, Q/4 and Q/100 span a factor of 100
   and all four record as the same one quantum at k=10, ratio 1/80, with the
   same 40 violations.* Still the right point, at the right size.
4. **"at 300 dpi it is 4e-5 of a pixel"** is off by 100x. One pixel at 300 dpi
   is 0.24 pt, so 1e-7 pt is **4.2e-07** of a pixel. The error is conservative
   (the floor is further below a pixel than claimed) and it was **inherited
   verbatim from the third verify file**, which is the failure mode rule 3c
   names: nothing checks a verifier but its own next pass, and here the next
   pass was a different agent reading the sentence forward. The companion
   figures are right: 7,324x below a tick, 1,730x below a glyph's drift.
5. **"52,549 of 68,800 glyph steps are flat"** is a property of a single
   staircase over k = 0..68,799, which is what `flat_fraction` computes. The
   BUILT fixture resets k per show (`rebuild` restarts at 0 for each TJ array,
   mean show length 46.2), and its true flat count is **52,561 / 68,800 =
   76.3968%**. The evidence labels the figure analytic, so it is honest about
   its method, but the sentence claims a property of the corpus's actual steps.
   Difference 12 steps, 0.017 percentage points; "roughly three glyphs in four
   do not move" is accurate either way.
6. **"four of the seven scratch scripts used `%.6f` and two used `%.9f`"**
   cannot be verified and is not what a grep shows: `%.6f` appears in
   `advkern.py` and `advstep.py` only, `%.9f` in `mkdrift.py` and `vsweep.py`
   only. The other three emit no kern format of their own because they
   delegate to the overwritten `mkfix.py`. See rule 10 below.
7. **The `glyphsub` digest**, finding 1 above.
8. **Owns.** The commit's two files are
   `mag/tests/parity_glyph_fixtures/mkfixtures.py` and its own evidence file.
   The evidence file is implicitly owned; the generator path is NOT in
   WP-0.2i's Owns list (`mag/src/parity/streams.rs`,
   `mag/src/parity/display.rs`, `meta/verification/parity.yaml`), and the
   evidence records no Owns extension. No collision exists: nothing else owns
   `mag/tests/parity_glyph_fixtures*` (WP-0.2d owns `mag/tests/parity_faults*`,
   which does not match), the third verification explicitly directed committing
   the generators, and the coordinator's brief names this exact path. Recorded
   as an unrecorded extension to be ratified in the plan, not as a defect.

## What I could not discriminate (rule 10)

- **Erratum 6.** The author's `mkfix.py` was overwritten on 2026-09-18, so the
  kern format of `mkfix.py`, `mkfix2.py` and `mkfix6.py` is unrecoverable. I
  can show 2 and 2, not 4 and 2. The claim is immaterial (it explains why
  fixture BYTES differ from the first submission while every ratio is
  unchanged, and the ratios did reproduce), but it cannot be checked and should
  be softened rather than carried.
- **69,071's impossibility.** Six countings fail to produce it. That is
  strong evidence it is not derivable from that file, and it is not a proof of
  impossibility. Neither the evidence nor I claim more, which is the right
  shape: the recommendation is to DROP the figure, which needs only that nobody
  can reproduce it, not that nobody ever could.
- **Runtime.** The evidence records 80 to 83 s per run. My runs took roughly 93
  to 110 s, with other agents' `mag parity` processes visible on the host
  throughout and, later, a disk-full event. I cannot separate the artifact's
  cost from host contention, so I neither confirm nor dispute the figure. The
  order of magnitude, seconds against the 9 to 15 minutes supersampled
  rasterization would have cost, is not in doubt.
- **The f32 residual.** The code claims check out exactly: lopdf 0.45.0 has
  `Real(f32)`, `num()` does `f64::from(*r)` once, and `tx`, `starts` and `qo`
  are f64. The conclusion that f32 terms enter as relative scale errors and so
  add a monotone ramp is an ARGUMENT, corroborated by a discriminating
  measurement (zero violations across 68,800 glyphs on both ramp controls) but
  not proven by it. WP-0.2j owns the definitive answer. Not a prerequisite for
  this clause, as the evidence says.

## Environment failures during this replay, reported not worked around

Both are host conditions, not artifact defects, and both were caught by the
rule-12 replay rather than by rereading.

1. **The host filled to 100% disk mid-run.** Nine runs died:
   `advtail_small` and `advtail_late` at exit 101, and all seven `vq_*` at
   exit 1 with **no log file created at all**, because the shell could not
   open the redirect target. `block1.err` carries the proof:
   `No space left on device (os error 28)`. After the coordinator reclaimed
   space I re-ran exactly those nine through the same recorded `run()`
   function, and **all nine then reproduced their recorded digests**. Reported
   rather than silently retried.
2. **My worktree's `mag/target/debug/` was removed mid-`cargo test`**,
   consistent with the reclamation reaching this worktree. It surfaced as
   `could not execute process .../parity_text_seam-... (never executed)`,
   exit 101, after 16 result lines. **That is rule 12's abort clause in its
   runner form**: the run stopped at the first failing BINARY, so those 16
   lines evidenced only part of the suite and would have understated the total
   had I reported them. I rebuilt and re-ran to completion. All 28 parity runs
   and the three violation probes completed BEFORE this removal, against a
   binary built in this worktree at `0ec67a9`.

**My own recorded command failed replay, and I record it because it is the
class the plan tracks.** Rule 12 binds verifiers, so before landing I
extracted every block of THIS file and executed it. Block 4, the run-loop
against-registry check, reported `26 24 False ['\\']`: I had transcribed the
list extraction without the `.replace("\\\n", " ")` that the version I actually
ran carried, so the two shell line-continuation backslashes counted as fixture
names. The block in the file now is the corrected one and prints
`24 24 True []`. The number I reported was right and the command I recorded for
it was wrong, which is the transcription failure exactly as rule 12 describes
it, caught by replay and not by rereading. Blocks 3 to 9 were then executed from
the extracted text and reproduce every figure they are cited for; block 2 is
the staging recipe, syntax-checked with `bash -n` and not re-run, since the
staged trees it produces are the ones every other block read.

**A hazard for the next agent**, since the protocol is telling everyone to set
it: `set -o pipefail` plus `set -e` will abort on an expected-empty `grep`,
which exits 1 when it matches nothing. The recorded block survives this only
because it sets `pipefail` WITHOUT `set -e`, so the `grep -h 'tier E'` inside
`run()` returning 1 for `ocmember` and `annotap`, which write no tier lines,
costs nothing. Guard such greps with `|| true` if `set -e` is ever added.

## Commands

Run from a worktree created at `0ec67a9` and used for nothing else. The two
render trees are staged as the evidence directs; here only `en/reader.pdf` and
`request.json` were copied per tree, which is all `--pre-rendered` reads, and
all seven `render-*` trees carrying a `reader.pdf` were staged so block 3's
population test spans the same seven.

```sh
MAIN=$PWD
WT=$(mktemp -d)/wt
git worktree add "$WT" 0ec67a9
cd "$WT"
for d in editions/010/render-2026-09-13T12-57-21 editions/010/render-2026-09-14T01-32-52 \
         editions/010/render-2026-09-14T01-33-59 editions/010/render-2026-09-14T01-40-18 \
         editions/010/render-2026-09-14T01-41-32 editions/010/render-2026-09-14T01-47-59 \
         editions/010/render-2026-09-14T01-49-02; do
  mkdir -p "$d/en"
  cp "$MAIN/$d/en/reader.pdf" "$d/en/"
  cp "$MAIN/$d/request.json" "$d/"
done
mkdir -p .magazine/vfy
uv run python - <<'PY'
import re, pathlib
src = pathlib.Path("meta/verification/evidence/WP-0.2i.md").read_text()
for i, (lang, body) in enumerate(re.findall(r"^```(\w*)\n(.*?)^```", src, re.S | re.M), 1):
    pathlib.Path(f".magazine/vfy/block{i}.{lang or 'txt'}").write_text(body)
    print("block", i, lang, len(body.splitlines()), "lines")
PY
bash .magazine/vfy/block1.sh
bash .magazine/vfy/block2.sh
bash .magazine/vfy/block3.sh
```

Hermeticity and the env gate, executed rather than read:

```sh
grep -nE '/Users/|/home/|/tmp/' mag/tests/parity_glyph_fixtures/mkfixtures.py \
  meta/verification/evidence/WP-0.2i.md; echo "exit=$?"
MAG_PARITY_RENDER_A=/nonexistent/tree MAG_PARITY_FIXTURES=.magazine/vfy/f2 \
  uv run python mag/tests/parity_glyph_fixtures/mkfixtures.py control; echo "exit=$?"
MAG_PARITY_FIXTURES=.magazine/vfy/f2 \
  uv run python mag/tests/parity_glyph_fixtures/mkfixtures.py nosuchfixture; echo "exit=$?"
```

Run loop against the registry, both sides parsed:

```sh
uv run python - <<'PY'
import re, pathlib, ast
loop = re.search(r"for f in (.*?); do",
                 pathlib.Path(".magazine/vfy/block1.sh").read_text(),
                 re.S).group(1).replace("\\\n", " ").split()
tree = ast.parse(pathlib.Path("mag/tests/parity_glyph_fixtures/mkfixtures.py").read_text())
keys = [k.value for n in ast.walk(tree) if isinstance(n, ast.Assign)
        and getattr(n.targets[0], "id", "") == "BUILDERS" for k in n.value.keys]
print(len(loop), len(keys), set(loop) == set(keys),
      sorted(set(loop) ^ set(keys)))
PY
```

The 15 cover shows enumerated as members, with font and render mode resolved
per show (this is what the evidence's own block does NOT cover):

```sh
uv run python - <<'PY'
import re
from pypdf import PdfReader
TJ1 = re.compile(rb"(\([^)]*\)|<[0-9A-Fa-f]*>)\s*Tj")
TF = re.compile(rb"/([A-Za-z0-9_.+-]+)\s+([0-9.]+)\s+Tf")
TR = re.compile(rb"([0-9]+)\s+Tr")
r = PdfReader("editions/010/render-2026-09-14T01-47-59/en/reader.pdf")
rows = []
for i, p in enumerate(r.pages):
    d = p.get_contents().get_data()
    fonts = p.get("/Resources", {}).get("/Font", {})
    for m in TJ1.finditer(d):
        tf = [x for x in TF.finditer(d, 0, m.start())][-1:]
        tr = [x for x in TR.finditer(d, 0, m.start())][-1:]
        res = tf[0].group(1).decode() if tf else None
        fd = fonts.get("/" + res) if res else None
        rows.append((i + 1, res, str(fd.get_object().get("/Subtype")) if fd is not None else None,
                     int(tr[0].group(1)) if tr else 0, len(m.group(1)) - 2,
                     m.group(1)[:1] == b"(", b"\\" in m.group(1)))
for row in rows: print(row)
print("members", len(rows), "| all Tr==3", all(x[3] == 3 for x in rows),
      "| all F1", all(x[1] == "F1" for x in rows),
      "| all simple", all(x[2] != "/Type0" for x in rows),
      "| all literal", all(x[5] for x in rows),
      "| any escape", any(x[6] for x in rows),
      "| bytes", sum(x[4] for x in rows),
      "| interior Tj pages", sorted({x[0] for x in rows if 2 <= x[0] <= 55}))
PY
```

Countings that do not produce 69,071, and the `n/(8k)` recovery from a
fixture's own violation records:

```sh
uv run python - <<'PY'
import json, pathlib, re
from fractions import Fraction
Q = 0.000732421875 / 8
g = json.loads(pathlib.Path("output/parity/010/verdict.json").read_text())["tier_e"]["glyph_positions"]
best = (0, None)
for s in g["violations"]:
    m = re.match(r"page \d+ element \d+ glyph (\d+): ([\d.]+) pt exceeds bound ([\d.]+) pt", s)
    if not m: continue
    k, d, b = int(m[1]), float(m[2]), float(m[3])
    if d / b > best[0]: best = (d / b, (round(d / Q), k))
n, k = best[1]
print("worst offender n =", n, "quanta at k =", k, "->", Fraction(n, 8 * k), "=", n / (8 * k))
print("verdict worst_ratio", g["worst_ratio"], "| equal:", abs(g["worst_ratio"] - n / (8 * k)) < 1e-12)
PY
```

Whether any show inherits a previous show's advance, which is what makes the
TJ-kern mechanism hold:

```sh
uv run python - <<'PY'
import re
from pypdf import PdfReader
OPS = re.compile(rb"(\]\s*TJ|\)\s*Tj|>\s*Tj|\bTd\b|\bTD\b|\bT\*\b|\bTm\b|\bBT\b|\bET\b)")
r = PdfReader("editions/010/render-2026-09-14T01-47-59/en/reader.pdf")
inherit = shows = 0
for i in range(1, 55):
    prev = False
    for m in OPS.finditer(r.pages[i].get_contents().get_data()):
        t = m.group(1)
        if t.endswith(b"TJ") or t.endswith(b"Tj"):
            shows += 1; inherit += prev; prev = True
        else:
            prev = False
print("interior shows", shows, "| inheriting", inherit)
PY
```

`glyphsub` reproducibility, cause isolated by removing it:

```sh
MAG_PARITY_FIXTURES=.magazine/vfy/gsA uv run python mag/tests/parity_glyph_fixtures/mkfixtures.py glyphsub
MAG_PARITY_FIXTURES=.magazine/vfy/gsB uv run python mag/tests/parity_glyph_fixtures/mkfixtures.py glyphsub
shasum -a 256 .magazine/vfy/gs[AB]/glyphsub/en/reader.pdf
cmp -l .magazine/vfy/gsA/glyphsub/en/reader.pdf .magazine/vfy/gsB/glyphsub/en/reader.pdf | wc -l
for i in A B; do SOURCE_DATE_EPOCH=1000000000 MAG_PARITY_FIXTURES=.magazine/vfy/gs$i \
  uv run python mag/tests/parity_glyph_fixtures/mkfixtures.py glyphsub; done
shasum -a 256 .magazine/vfy/gs[AB]/glyphsub/en/reader.pdf
```

Build and suite, run to completion after the target directory was rebuilt:

```sh
(cd mag && cargo fmt --check && cargo clippy --all-targets -- -D warnings && cargo test)
```

## What the branch moving since `0ec67a9` does and does not change

`art_directed` advanced from `0ec67a9` to `3449552` while this verification
ran, and WP-0.2k landed in `mag/src/parity.rs` along the way. Considered under
the landing rule rather than assumed: `mag/src/parity/streams.rs`,
`mag/src/parity/display.rs`, the committed generator and the evidence file are
untouched across that range (`git diff --stat` between the two commits on
those paths is empty), so every ratio, violation count, excess and fixture
hash above carries to the tip unchanged. The verdict DIGESTS are not claimed to
carry: `parity.rs` gained 788 lines in that range, and if any of them changes
what `verdict.json` records, as WP-0.2g did between `e2ebc90` and `20adcfb`, a
replay at the tip hashes differently. I did not replay at the tip, so whether
the digests move is stated as untested rather than as either outcome. Every digest in this file is bound to
`0ec67a9`, which is the commit under verification.

## Tool versions

rustc 1.96.0, Python 3.12.11 through `uv run`, pypdf 6.14.2, fontTools 4.63.0,
lopdf 0.45.0 and ttf-parser 0.25.1 from `mag/Cargo.lock` (the evidence writes
"0.25"), poppler 25.08.0 (`pdftotext -v`). `mag/Cargo.toml` and
`mag/Cargo.lock` are untouched by the commit, as the evidence states.

## Metrics

Observations, not thresholds. All measured at commit `0ec67a9`, which is the
configuration a total travels with.

- Floor `stairdrift` **0.2500**, 0 violations, digest `df9909eeb8c68057`.
- Ceiling `kern02` **10.2500**, 5 violations, worst excess 0.013550 pt, digest
  `40d61b72f0daa2b9`. **Margin 4.00x.**
- 68,800 glyphs, 1,488 shows, 54 interior pages of which 47 carry text.
- Flats: 52,549 / 68,800 = 76.3794% for the global staircase; **52,561 /
  68,800 = 76.3968%** for the fixture as built, which resets k per show.
- Detection floor between 9.16e-08 and 9.16e-07 pt; 2Q, Q, Q/2, Q/4, Q/100 all
  fail at 40 violations with `worst_excess_pt` 0.000000; Q/1000 and Q/10000
  pass.
- Ratio law `n/(8k)`, recovered from `linmatrix` as n=137 at k=6; five distinct
  denominators observed, 8, 16, 48, 64, 80.
- Cover shows: 15, on pages 1 and 56 only, `/F2+0` `/TrueType`, `3 Tr`, 537
  string bytes, zero escapes. 1,488 + 15 = 1,503.
- 25 of 26 recorded verdict digests reproduced; `glyphsub` is not reproducible
  by any party.
- 23 of 24 fixtures rebuild byte-identically; `glyphsub` differs by 9 bytes per
  build, and is stable under `SOURCE_DATE_EPOCH`.
- `cargo fmt --check` clean, `cargo clippy --all-targets -- -D warnings` clean,
  `cargo test` **20 result lines, 188 passed, 0 failed**, exit 0. The evidence
  records 18 / 181 at its base `20adcfb`; the difference is exactly the two
  test binaries that landed in between, `model_shared_label.rs` (3) and
  `model_shared_roster.rs` (4), so **188 - 7 = 181 and 20 - 2 = 18**. Both
  totals are right for their own commit.
- Per-run wall clock 93 to 110 s under host contention; not comparable to the
  recorded 80 to 83 s.

## Status

accepted
