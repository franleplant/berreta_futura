# WP-5.4 verification

## Verdict

REJECTED, narrowly and on the evidence record only. The code fix is correct and
I proved it independently; two things the rework reported as recorded are not in
the evidence, and one of them is the same defect class that caused this WP's
first rejection.

## History

Commits `5a3fa71` and `78711a5` were rejected at `06d5cf63` for two material
findings: `art.rs::grey` was unfaithful to `cover.py:495`'s `convert("L")`
(per-mille against PIL fixed-point, disagreeing on 540 of 3,110,400 pixels and
passing only because the statistics feed a threshold a 1e-4 shift does not
flip), and the fill/stroke divergence was misattributed. The rework is
`e639b32`.

## Owns

`e639b32` touches six paths: `mag/src/cover/art.rs`, `mag/src/cover/outline.rs`,
`mag/src/critic/metrics.rs`, `mag/tests/cover_footer_caption.rs`,
`mag/tests/cover_zone_expected.json`, `meta/verification/evidence/WP-5.4.md`.
All within WP-5.4's Owns (`mag/src/cover/` except `text.rs`, its tests, its
evidence) plus the recorded orchestrator grant on `metrics.rs`. No `text.rs`, no
`mag/src/model/**`, no `*.verify.md`, no `baseline.json`.

## Claim 1: the fix uses luma601, not a third copy. CONFIRMED

`git diff 78711a5 e639b32 -- mag/src/critic/metrics.rs` is exactly one line:

    -fn luma601(pixel: &[u8]) -> u8 {
    +pub(crate) fn luma601(pixel: &[u8]) -> u8 {

`art.rs` deletes its local `grey` entirely and imports `luma601` from
`crate::critic::metrics`. There is one implementation, not three.

## Claim 2: WP-5.3a's oracle unmoved, by git blob. CONFIRMED

    $ for c in 5a3fa71 78711a5 e639b32; do git rev-parse "$c:mag/tests/critic_metrics_expected.json"; done
    39be9e815b4403a8bcd8b27c07944fe3daa29e31
    39be9e815b4403a8bcd8b27c07944fe3daa29e31
    39be9e815b4403a8bcd8b27c07944fe3daa29e31

I checked the rounding oracle too, also constant at
`9e94ee1055a4264909ce0b2a56e5f5ebe5d33e68`.

The blob-hash method is worth endorsing as method: git is content-addressed, so
an identical blob hash proves byte-identity, and it proves the file never
changed at any point in the range rather than only that it produces the same
result now. It is strictly stronger than re-running, and cheaper.

## Claim 3: the assertion is real and discriminates. CONFIRMED, both halves

First I checked the oracle is genuinely PIL's numbers rather than Rust's own
output committed as expectation. Reconstructing `_art_zones` (`cover.py:482`)
against the same art, band and page height:

    top_mean    109.56689949397071
    top_stddev  40.23238620807911
    bottom_mean 128.22243563122925
    bottom_std  28.66407903976693

Identical to every value in `mag/tests/cover_zone_expected.json`. The oracle is
Python's.

Then the discrimination, reverting `art.rs` to the per-mille formula in place:

    running 3 tests
    test metrics::exif_tests::orientation_is_read_when_present_and_ignored_otherwise ... ok
    test footer_caption_raster_matches_the_python_compiler ... ok
    test zone_statistics_match_the_python_compiler ... FAILED

    top_mean diverged from PIL: 109.56702330964686 against 109.56689949397072

    test result: FAILED. 2 passed; 1 failed

Both halves in one run, exactly as claimed. The zone assertion fails at the
stated numbers, and the raster test PASSES alongside it under the same revert.
That demonstrates the aggregation gap rather than arguing it, and it is why an
assertion was the right answer over a note. Restored: 3 passed, tree clean.

The thresholds confirm the gap's size: `dark_bottom = bottom_mean < 105` against
an observed 128.22, and `bottom_std > 46` against 28.66. Margins of 23.2 and
17.3 against a shift of 1.238e-04, so no threshold could flip.

## Claim 4: the fill/stroke framing withdrawn. CONFIRMED

The evidence records the lineto as COSMETIC with the measurement (SVG 4,234,729
against 4,233,478 bytes, PNG byte-identical, test green, synthetic probes
agreeing), and states the earlier claim and the "fill-only probe is not evidence
about stroked elements" lesson are "both WITHDRAWN as unsupported". It survives
only as a record of the retraction, never as a live claim, which is the right
treatment.

## Claim 5: the second example. CORRECTLY REASONED, and I proved it

"A wrong luma formula that the raster hash also could not see" is exactly what
my own revert demonstrated: the raster test passed while the zone assertion
failed. The section's argument now rests on the transposed constant pair alone
for the structural direction and on the luma defect for the raster direction.

One note on wording rather than substance: the two examples are dual rather
than "the same lesson in a second form". The transposed constant is invisible to
a structural comparison and visible to pixels; the luma defect is invisible to
pixels and visible only to a direct assertion. What generalises is that a defect
can be invisible to any given oracle level, which is a stronger and more useful
statement than either example alone.

## Claim 6: the two smaller items. ONE CONFIRMED, ONE NOT

`#[allow(dead_code)]` now sits on `.width` alone rather than the `Outlined`
struct. Confirmed in the diff.

The replay hazard is NOT in the evidence. See defect 2.

## Claim 7: the honesty section. ACCURATE

PROVEN lists the front cover raster and the four zone statistics, both against
Python-produced numbers and both shown to discriminate; I verified both
independently. NOT PROVEN lists the back cover, the PDF writer, the other layout
modes and `design.toml` loading, and it draws the right distinction on the back
cover: its raster was measured identical during the resvg feasibility work, but
no committed test covers it, so it is not proven. Nothing listed as proven is
merely asserted, and I found nothing material missing from the not-proven list.

## Defect 1: the zone oracle has no recorded derivation

`mag/tests/cover_zone_expected.json` is not mentioned anywhere in the evidence,
and `## Commands` contains no invocation that produces it. Its three Python
blocks compile the covers, capture the SVG and compare the raster; none derives
the zone statistics.

I verified the oracle is genuinely Python's, but only by reading `cover.py:482`
and reconstructing `_art_zones` myself. A verifier replaying `## Commands` would
not reproduce this file, which is the defect class WP-5.1b was rejected for at
`2f1886a`.

It matters more here than it normally would. This WP's first rejection was for
claiming the zone statistics were "proven against Python" when nothing asserted
them. The fix introduces an oracle whose Python provenance is, once again, not
in the record — the assertion is real this time, but its derivation is as
unrecorded as the claim it replaced.

Remedy: add the inline `uv run python -c '...'` that regenerates
`cover_zone_expected.json`, and confirm it reproduces the committed file
byte-identically.

## Defect 2: the replay hazard is not recorded

The rework reported that `## Commands` carries the hazard that `compile()` skips
regeneration when outputs already exist, so a spy on `Tree.from_str` captures
nothing and reads as a broken method. It does not. The only nearby text says the
spy "is the only reliable way to get the post-rewrite document", which is a
different point. `grep -n -i "outputs exist\|already exist\|skip\|hazard"` over
the evidence returns nothing.

Remedy: add it, or drop the claim.

## Baseline

`cargo test --test cover_footer_caption`: 3 passed. `cargo fmt --check`: clean.
`cargo clippy --all-targets -- -D warnings`: clean.

## Commands

    for c in 5a3fa71 78711a5 e639b32; do git rev-parse "$c:mag/tests/critic_metrics_expected.json"; done
    git diff 78711a5 e639b32 -- mag/src/critic/metrics.rs
    uv run python -c "<_art_zones reconstruction, see Claim 3>"
    cd mag && cargo test --test cover_footer_caption
    # revert art.rs to per-mille in place, rerun, restore

## Status

rejected
