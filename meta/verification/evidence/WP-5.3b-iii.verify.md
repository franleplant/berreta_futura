# WP-5.3b-iii the checks, verification

**Verdict: ACCEPTED**, with four findings, none of them a code defect and
none live on the branch. WP-5.3c, WP-5.3g and WP-5.5c may build on `2a57ebf`
as it stands.

## What was verified, and where

Commit under test `2a57ebf`, parent `f7361c2` (the evidence's `## Base`).
Worktree `git worktree add <scratch>/vwp53biii 2a57ebf`, not the directory
the work was developed in (rule 12). `art_directed` read `2a57ebf` at the
start of this pass. Every count below was re-derived here and is stated with
what it counts over; all of them were measured at `2a57ebf`.

The eight `## Commands` blocks were extracted programmatically from
`meta/verification/evidence/WP-5.3b-iii.md` with the evidence's own recorded
extractor (877 / 5 / 8 / 120 / 16 / 154 / 40 / 29 lines) and each run as
`env -i HOME PATH TMPDIR bash <block>` from the worktree root, serially,
because blocks 6 to 8 mutate `mag/src/critic/rules.rs`. No command was
retyped from this shell. Wall times: 197 / 60 / 44 / 219 / 247 / 407 / 410 s
for blocks 2 to 8.

Tool versions, all matching `## Tool versions`: pdftoppm 25.08.0, `uv run
python` 3.12.11, Unicode 15.0.0, Pillow 12.3.0, pypdf 6.14.2, cargo and rustc
1.96.0. `render_critic.py` is blob `0356bb88…` at `f7361c2`, at `2a57ebf`
and at the tip, so no oracle drift sits between the WP's base and its land.

## Owns diff

`git diff --name-only f7361c2 2a57ebf` outside `mag/tests/critic_rules*` is
exactly four paths: `mag/src/critic/rules.rs` (Owns), `mag/src/critic.rs`,
`mag/src/critic/metrics.rs` and the evidence file. The grep for
`verify.md|baseline.json` in that list exited 1 (ran, found nothing).
`mag/tests/critic_rules.rs`, `critic_rules_expected.json` and 39 PNGs under
`critic_rules_fixtures/` are the Phase 5 preamble's `mag/tests/<wp-slug>*`.

**Extension 1**: the whole diff to `metrics.rs` is `-fn resize` /
`+pub(crate) fn resize` on one line, one word, as granted.
**Extension 2**: the whole diff to `critic.rs` is `+pub mod rules;`, one
insertion, under revision 61's mod-line rule. The consumer for the `resize`
extension is `rules.rs:10 use crate::critic::metrics::{… resize …}`, used at
`rules.rs:508`, compiled into the binary by that mod line; `rules.rs` carries
no `#[cfg(test)]` module, so no `crate::` test breaks the `#[path]` include.

## The headline claims, each reproduced

| claim | reproduced |
| --- | --- |
| block 1: positive control reports CHANGED, regeneration reports UNCHANGED, exit 0 | yes, in that order; `git status --porcelain` empty after |
| `critic_rules_expected.json` sha256 `bbd77dc6…f11d2e` | exact |
| 191 fixture cases in 20 groups | **re-derived**: 21 keys in the oracle summing to 222; minus the 31-row `issue_sites` list gives 20 groups and 191 cases |
| 31 issue sites, 30 distinct codes | **re-derived independently** with `ast` over `render_critic.py`: 31 `issue(...)` calls, 30 codes, `article-opener-offset-shadow` twice; per function 11 + 2 + 6 + 2 + 1 + 4 + 5 = 31; my string scan agrees as a multiset; the oracle's `issue_sites` rows equal my parse line for line |
| block 2: fmt, clippy `-D warnings`, nocomments clean; `cargo test` all ok | 25 `test result` lines, every one `ok`, 255 passed in total (24 `.rs` files in `mag/tests/` plus the `mag` binary's in-crate tests) |
| block 3: tracer dump, MODE full | traced 56 / 28 / 26 / 1 pages |
| block 4: live oracle sha256 `d7fdb44a…915c45` | exact, 87352 bytes |
| Python-with-pypdf reproduces the shipped `render-critic.json` (issues, result, pages, crops) | all four `True` |
| decision set and geometry equal across the text swap | both `True`; both runs `pass` with 4 issues |
| block 5: MODE full, `COMPARED: 4 issues, result pass`, `COMPARED: 22 crops pixel for pixel`, 26 passed | exact; the both-or-neither refusal fires with its message |
| 56 void rows, 28 + 26 + 1 spread rows, 22 crop rows, 9 fidelity rows | asserted inside `decides_edition_010_like_python` in that order; cardinalities cross-checked against the shipped `render-critic.json`: 56 pages, 22 crops, 9 fidelity rows, 0 offsets, 28 / 26 / 1 spreads, 8 located bands, 5 zero-area pages |
| block 6: 49 probes, 47 fail | **re-derived**: 49 `PROBE` lines, 47 containing `FAILED` (8 at 1 failed, 24 at 2, 12 at 3, 3 at 4), the same two passing, zero Python assertion tracebacks (so every probe was applied), `RESTORED` |
| block 7: the two fixture-passing probes plus the spread-text rule fail live | all three panic at `tests/critic_rules.rs:271`, which is the `decision set` assertion |
| block 8: `CROP_MARGIN_POINTS` fails at `crop plan`, `TAIL_BAND_SYMMETRY` at `void geometry`, `VOID_MIN_HEIGHT` at `decision set` | exact |

The worktree was clean (`git status --porcelain` empty, exit 0) after the
chain and after my own probe.

## The five points scrutinised

**1. The decision level is blind to 27 of 31 sites.** The two blindness
probes reproduce: with `CROP_MARGIN_POINTS` at 25.0 the live test passes
`decision set` and fails first at `crop plan`; with the symmetry tolerance at
0.0 it passes `decision set` and fails first at `void geometry`. Since the
test asserts `decision set` first (line 271) and those fail at later lines,
L1 passed with the defect present, as claimed. The 27/31 figure follows from
the shipped `render-critic.json`, which carries exactly four issues
(`whitespace-void` p17, `article-stub-last-page` p29, `tail-art-dropped`,
`article-page-cap`), each a distinct code.

**2. `mask_cells` is pinned to Python, not to itself.** Block 1's
`mask_case` records `presence.crop(box).reduce(VOID_DOWNSAMPLE).tobytes()`,
PIL's actual reduced bytes, and `mask_reduction_matches_pil` asserts the Rust
grid's size, its per-cell occupancy against those bytes thresholded at zero,
and a digest of the same, on five masks including a ragged 37x29 and a crop
past the image edge; it also refuses an all-empty fixture set. The divergence
argument checks out against the Python: the reduced grid is read only for
truth (`:1313 any(data[...])`, `:1364 0 if data[...]`) and written only as
255 (`:1289`), so a 0/255 mask agreeing on truth is agreeing on everything
Python reads. Both `mask_cells` probes (`div_ceil` dropped, occupancy
inverted) fail in block 6.

**3. The two extension lines** are exactly as declared; see Owns diff.

**4. Rule 10c on both limbs.** Provenance is disclosed correctly: every
expected value is transcribed from Python's output, and the evidence names
what that cannot see (a Python defect) with the partial offset (24 thresholds
and the 31-site set read from the source). I checked the refusing sides of
the straddles against the fallback paths in the oracle: `height_below_threshold`
and `width_below_threshold` keep a non-null `largest_void` (92 pt, 0.85) with
`voids: []`, so they are not the skip path's annotation;
`trailing_past_tolerance` keeps its void with `trailing: false`;
`offset_outside_tolerance` carries `offset_pixels [6, 6]`, not the no-frame
refusal; `run_at_minimum` fails on the orange leg with a frame bbox where
`run_below_minimum` fails without one. `height_past_tolerance` expects `None`,
which is also `no_run`'s and `no_match`'s value; that IS the correct
destination for a mismatched run (revision 67's precision), and the pair is
pinned from both sides by the 11.9 and 12.2 probes. My own probe, `<=` to `<`
at `rules.rs:316`, fails exactly `symmetry_at_tolerance`, so the symmetry pair
sits on the boundary rather than near it.

**5. The two NOT COVERED branches are honestly bounded.** `render_crop_page`
maps a spawn failure to Python's `DependencyError` text via `.context` and
falls to the same `stderr / stdout / "unknown Poppler error"` chain on a
non-zero status or no output; nothing asserts it, as stated. It inherits
WP-5.3b-ii's disclosed `shutil.which` versus spawn difference. `manifest_json`
returns `Null` where Python returns `{}` / `()` for a missing, unreadable or
non-dict manifest and both callers then produce the empty value, so the
untested arms are the same shape as the tested missing-file path, which is
exactly why the evidence says a fixture would be a 10c coincidence. One edge
the bound does not name: `json.loads` accepts `NaN` and `Infinity`,
`serde_json` does not, so a manifest carrying them parses in Python and reads
as absent in Rust. Unreachable from the pipeline's own writer.

## Findings

**Finding 1 (caption drifts from the command, rule 12): block 5's first
command is not the skipped mode it is captioned as.** The block exports
`MAG_CRITIC_RULES_ORACLE` before its first `cargo test`, so that run hits the
both-or-neither refusal and reports `FAILED. 25 passed; 1 failed`, not a
clean skip; the fourth command then demonstrates the same refusal
deliberately. The clean skipped mode is real: I ran the suite with no
environment and got `MODE: skipped` twice and `26 passed`, and block 2's bare
`cargo test` runs it too. Rule 2b asks that the evidence RECORD the skipped
result, and this block does not print it. Evidence defect only.

**Finding 2 (overclaim, corrected two paragraphs later in the same file):**
`## Metrics` says each of the 15 straddle pairs in its table "is asserted to
differ" by `straddle_pairs_differ_from_each_other_and_from_the_fallback`; the
test names 9 pairs plus the offset and minimum-run pairs, 11. The other four
(`TAIL_GAP_MIN_LIVE_FRACTION`, `STUB_BODY_LINE_MINIMUM`, `GEOMETRY_TOLERANCE`,
`DEFAULT_EDITORIAL_PAGE_CAP`) are not asserted; I read them from the oracle and
all four pairs differ (`[] `against one issue each), and their groups are
covered by `no_fixture_group_expects_only_the_fallback`. The evidence's own
10c section states the 11 correctly.

**Finding 3 (the 26 in "fixture-only suite (26 tests)")**: 25 `#[test]`
functions in `mag/tests/critic_rules.rs` plus one carried in through the
`#[path]` include of `metrics.rs`, revision 62's inflation. Both numbers are
right; the domain is worth naming beside the figure.

**Finding 4 (inherited, restated per rule 10g): `SPARSE_INK_RATIO` remains
the one loose constant** behind these sites, and the evidence labels it per
constant as -ii's; no fixture here tightens it, and none claims to.

## What this verification does and does not establish

ESTABLISHES: the evidence replays from a directory it was not developed in,
on the recorded tool versions, with every digest and every count reproduced;
the 31-site enumeration is independent of the WP's own; 47 of 49 fixture
probes and 3 of 3 live probes discriminate; the decision-level blindness is
measured, not argued; `mask_cells` answers to PIL; the two Owns extensions are
one word and one line.

DOES NOT ESTABLISH: anything outside 010 English on this host and poppler
build; that any decision is correct (equality is not correctness, every value
except thresholds and codes is transcribed); the poppler-failure and
malformed-manifest arms; `WORD_GAP_FRACTION`, `SPARSE_INK_RATIO` and the five
text fields, which belong to -i and -ii. No search is offered here as proof
of absence.

## What the moving branch changes

`art_directed` moved from `2a57ebf` to `5ba6f1c` during this pass, adding
WP-0.2h-i (`bce8caa`) and WP-2.2b's rejection. Rule 5b: what arrived was
read, not assumed. WP-0.2h-i touches `mag/src/critic.rs` (a `#[cfg(test)]`
module only, below the four `pub mod` lines, which stay as verified) and one
re-export line in `mag/src/parity.rs` (`qc`, `qo`). Neither changes runtime
behaviour of `rules.rs`, the tracer or the inspection, so the live comparison
was not re-run; on the rebased tree `cargo fmt --check`, `cargo clippy
--all-targets -D warnings`, the fixture suite (`26 passed`, both `MODE:
skipped` lines printed) and the in-crate tests (`110 passed`, 107 at
`2a57ebf` plus the three seam tests) are green. This commit is rebased onto
`5ba6f1c` and swapped against it.

## Is anything live on the branch?

No defect. Nothing must be quarantined. WP-5.5c's finding 1 (the contact
sheets, the report dict and PNG bytes) stands as escalated by the WP and is
WP-5.5c's to cost.
