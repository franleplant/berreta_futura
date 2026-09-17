# WP-5.4 verification

## Verdict

ACCEPTED for the work package's own content at commit `01975a3` (landed as
`c084e16`).

BLOCKING REPOSITORY-STATE FINDING, not attributable to WP-5.4: the accepted
content is NOT in the tree at HEAD. Commit `4f20801` reverted it. The tree must
be repaired before WP-5.4 can be considered done. See "The clobber" below.

## History

- `5a3fa71`, `78711a5` rejected at `06d5cf63`: `art.rs::grey` was unfaithful to
  `cover.py`'s `convert("L")`, and the fill/stroke divergence was misattributed.
- `e639b32` fixed the code, rejected at `5c1eb65` on the evidence record only:
  `cover_zone_expected.json` had no recorded provenance and no command producing
  it, and a replay hazard reported as recorded was absent.
- `01975a3` (landed `c084e16`) is the evidence fix verified here.

## Scope

Narrow. Evidence-only; no code changed. Carried forward from `5c1eb65` and not
re-checked: the one-line `metrics.rs` visibility change with `art.rs` importing
`luma601`; WP-5.3a's expectation blob `39be9e81...` across the prior commits;
both halves of the discriminating proof; the deleted fill/stroke framing; the
honesty section's accuracy.

## Owns

`c084e16` touches exactly one file, `meta/verification/evidence/WP-5.4.md`
(65 insertions, 16 deletions). No code, no other evidence file, no verify file,
no `baseline.json`. `mag/src/**` untouched. Clean.

## Claim 1: zone oracle provenance. VERIFIED, reproduced.

The full inline `uv run python -c '...'` is present in `## Commands` at
`c084e16`. It mirrors `_art_zones` at `src/magazine/cover.py:482` including the
`int()` truncations and the floor-divided crop offsets, and it reads
`editions/010/art/rounds/2026-09-13T01-40-20/cover-wildcard-sign-punched-v3.png`,
which `git ls-files` confirms is TRACKED, so it needs no run directory.

Run verbatim, it reproduces the committed file byte for byte:

    before  303e2e66aedddc073b55b56821ee836d6556dab87ad2eb821d0f2fb6cdfc0990
    after   303e2e66aedddc073b55b56821ee836d6556dab87ad2eb821d0f2fb6cdfc0990
    cmp     clean

The numbers are PIL's own `ImageStat` output rather than Rust output committed
as an expectation, which is what the rejection required establishing.

ERRATUM, not a defect: the evidence quotes the digest as
`303e2e66aedddc073b55b56821ee836d6556dab8`, which is the first 40 hex characters
of the sha256 rather than the whole 64. The prefix is correct.

## Claim 2: replay hazard. VERIFIED present at `c084e16`.

Present once, as its own paragraph above the spy command: `compile()` SKIPS
regeneration when its outputs already exist, so a second run into the same
destination captures nothing through a spy on `Tree.from_str` and reads as a
broken method rather than a skipped step; use a fresh destination directory for
every capture.

This is distinct from the pre-existing line at 174 ("the spy on `Tree.from_str`
is the only reliable way to get the post-rewrite document"), which the previous
verification correctly identified as a different point.

## Claim 3: the dual generalization. VERIFIED present at `c084e16`, accurate.

Section "A defect can be invisible to any given oracle level". The old wording
"same lesson in a second form" is absent at `c084e16`.

The section is accurate rather than merely reworded, and the two directions are
stated with their evidence:

- The transposed `horizontal_scale`/`stroke_width` pair was invisible to
  structure and visible to pixels: the markup skeleton diffed clean on every
  transform, translate and scale, while the raster differed on 10,768 pixels.
- The zone-statistics luma formula was invisible to pixels and visible only to a
  direct numeric assertion: it disagreed with `convert("L")` on 540 of 3,110,400
  pixels and moved the zone means by 1.238e-04 and 5.652e-05, but the thresholds
  it feeds sit far away (`bottom_mean < 105` against 128.22, `bottom_std > 46`
  against 28.66), so nothing flipped and the raster hash matched.

The generalization drawn is that a defect can be invisible to any given oracle
level, and which level blinds you is not predictable from the defect's kind.
That is stronger than either example and is correctly presented as the argument
for holding more than one level at once.

## All three edits present

Confirmed at `c084e16`. The worker's earlier failure (reporting an edit as made
when it had silently no-op'd) did not recur in this commit.

## The clobber

The three fixes are NOT in the tree at HEAD.

    at c084e16   "cover_zone_expected"        2 occurrences
                 "same lesson in a second form"  0 occurrences
    at 4f20801   "cover_zone_expected"        0 occurrences
                 "same lesson in a second form"  1 occurrence

`4f20801` ("docs(plans): typst parity plan revision 29, rule 12 and the WP-5.3b
re-cut") has `c084e16` as its DIRECT PARENT and reverted
`meta/verification/evidence/WP-5.4.md` by exactly the inverse diff: 16
insertions and 65 deletions against `c084e16`'s 65 and 16. The working tree
matches HEAD, so the reverted content is what is live.

Three observations:

1. It is an Owns violation. The plan revision owns
   `meta/plans/typst-parity-and-rust-migration.md`. It does not own any
   evidence file. Rule 1 makes a diff touching an evidence file it does not own
   rejectable before a verifier is spawned.
2. It is the third instance of the same landing failure, after `aa4bc01` (itself
   a verify commit) deleted WP-5.2's 39 files. The mechanism is the same: a
   commit written from a copy of a file read before someone else's change
   landed, then written back wholesale.
3. IT DEFEATS THE CURRENT FIX. Revision 25 requires confirming the files you
   expect are PRESENT in the resulting tree. `WP-5.4.md` IS present. It is
   present and reverted. Presence is not content. The check has to compare
   content, or at minimum confirm that the specific change you landed is still
   in the file, which is what a grep for one's own added text would do.

## What this verdict does and does not establish

Establishes: WP-5.4's evidence at `c084e16` records the zone oracle's
provenance with a command reproducing it byte for byte, carries the replay
hazard, and states the dual generalization accurately.

Does not establish: that the repository currently contains any of it. It does
not. Restoring `c084e16`'s version of `meta/verification/evidence/WP-5.4.md` is
required, and is the orchestrator's to sequence since it spans two work
packages' commits.

Not re-checked here, carried from `5c1eb65`: everything listed under Scope.
