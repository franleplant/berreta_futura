# WP-5.5b verification

Verdict: **ACCEPTED**

Worker commit `d5d23a2` (preflight port). Verified in a fresh worktree at that
commit. Critique folded in per the orchestrator's brief.

## Owns

`git show --stat d5d23a2` lists exactly five paths, all additions, no
deletions: `mag/src/main.rs` (+2), `mag/src/package.rs` (+1),
`mag/src/package/preflight.rs` (+461), `mag/tests/preflight.rs` (+545),
`meta/verification/evidence/WP-5.5b.md` (+206). No `*.verify.md`, no
`baseline.json`, no other WP's territory. Clean.

## Baseline

`cargo test` green: 13 preflight tests plus the duplicate audit's two, exit 0.
`cargo fmt --check` clean. `cargo clippy --all-targets -- -D warnings` clean.

## Dependencies imported, not copied

`preflight.rs` imports `crate::critic::metrics::{prepare_print_image,
round_places, PreparedPrintImage}` and `crate::impose::{section_reader_pages,
A4_LANDSCAPE_POINTS}`. Grepped for local definitions of `round_places`,
`section_reader_pages`, `prepare_print_image` and a local
`A4_LANDSCAPE_POINTS` constant: none. No copies.

## Banker's rounding: confirmed by measurement

The claim was that `round_places` supplies Python's rounding, which `round(x,
1)` and `round(x, 3)` need. `round_places` is
`format!("{value:.places$}").parse()`. Rather than reason about whether Rust's
`{:.N}` and Python's `round` agree, I measured both on 18 cases chosen to
include genuine binary-exact ties.

**18 of 18 identical.** At one place: `0.25→0.2`, `0.75→0.8`, `1.25→1.2`,
`1.75→1.8`, `2.25→2.2`, `2.75→2.8`, plus the near-ties `0.05→0.1`,
`0.15→0.1`, `0.35→0.3`. At three places: `0.0625→0.062`, `0.1875→0.188`,
`0.3125→0.312`, `0.4375→0.438`, `0.5625→0.562`, `2.0625→2.062`, plus
`0.0005→0.001`, `0.0015→0.002`.

These cases **discriminate**: a naive round-half-up gives `0.25→0.3`,
`1.25→1.3`, `2.25→2.3`, `0.0625→0.063`, `0.3125→0.313`, `0.5625→0.563` —
seven of the eighteen would differ. The agreement is therefore evidence, not
coincidence on a tie-free corpus.

## Edition 010 oracle: reproduced independently

I did not reuse the worker's artefacts. I rebuilt the spec from
`render-2026-09-14T01-49-02/en`, generated the Python oracle myself through
`magazine.preflight.inspect_package`, and ran the Rust comparison against my
own file: **pass**.

Leaf count reconciles exactly at **153** (my first count of 157 counted empty
lists as one; there are four). The evidence's byte figure of 4,018 does not
reconcile with my 5,299 — most likely absolute-path length, since the oracle
embeds resolved `cover_art.path` and `figures[*].path` and my worktree path is
longer than the main tree's. The test asserts leaves and field equality, not
bytes, so this is an erratum rather than a defect. Recorded below.

### On the shared-spec method

The orchestrator asked whether driving both sides from one spec weakens the
oracle. It does not, with one narrowing worth stating.

The spec encodes **inputs** — PDF paths, image paths, and per-figure
placement metadata — not intermediate results and not expected outputs. Both
implementations then compute independently. A shared misunderstanding would
have to live in the inputs, and the inputs are exactly what the renderer
passes to `inspect_package` in production, so the spec is faithful to the
real interface.

The narrowing: `pixel_dimensions`, `box_points`, `effective_ppi`, `caption`
and `credit` are drawn from the archived Python output and echoed to both
sides, so for those fields the comparison tests pass-through fidelity rather
than computation. That is inherent — they are inputs in production too — but
it means the oracle's strength rests on the **computed** fields: the PDF
facts, the image analysis, the geometry and collision analysis, the
resolution thresholds and the blockers. My mutations targeted those
deliberately.

Driving from the archived `preflight.json` directly was not available: its
staged temp paths no longer exist. The worker's choice was the only honest
option, and it says so.

## Non-vacuity: my own mutations, on computed fields

The worker mutated `figures[1].effective_ppi`, which is an **echoed** field. I
used three **computed** ones instead, each requiring Rust to derive the value:

| mutation | caught |
|---|---|
| `reader.page_count` 56 → 55 (from the PDF) | yes |
| `cover_art.effective_ppi_at_placement` 247.1 → 247.2 (from image + placement) | yes |
| `home_booklet.sheets` 14 → 13 (booklet arithmetic) | yes |

All three fail the test. The second is a 0.1 change in a computed float, so
the comparison is tight on derived values and not only on integers.

## `studio.ready` is genuinely unreachable

Confirmed in the Python. `preflight.py:231` seeds
`studio_blockers = [messages["pdfx"], messages["bleed"]]` **unconditionally**,
and lines 233/235/237/239 only ever `append`. Nothing between the seeding and
its use empties or filters it. Therefore at line 242
`"result": "home_ready_studio_blocked" if studio_blockers else "ready"` can
never take `"ready"`, and at line 270 `"ready": not studio_blockers` is always
`False`.

Two fields the pipeline reports can never take one of their values. The
worker's rule-10 label is correct, and its test
`the_result_field_is_constant_because_two_blockers_are_unconditional` asserts
it explicitly rather than leaving it as prose. This is a finding about the
Python worth knowing beyond this WP: it is a product question (should a
PDF/X-4 and bleed blocker be permanent?) rather than a port defect, and the
port reproduces it faithfully.

## f32 enumeration: complete

Exactly one site converts a parsed PDF real:
`preflight.rs:134`, `Object::Real(value) => f64::from(*value)`, inside
`inherited_media_box`. Integers take `*value as f64` and are exact.

Those values reach only `Pdf { sizes }`, which is private. `Pdf` exposes
`page_count() -> usize` and `all_near(expected) -> bool`; `all_near` delegates
to `near`, a 0.75 pt tolerance comparison returning a boolean. No parsed real
reaches a numeric output field. Image dimensions come from PNG IHDR and JPEG
SOF headers (integers), `box_points` come from the caller's typed placement,
and `is_encrypted` is a boolean. The enumeration is complete and the
conclusion holds.

## Env gating announces its mode

`edition_010_matches_the_python_oracle` is env-gated on `MAG_PREFLIGHT_SPEC`
and `MAG_PREFLIGHT_ORACLE`, and satisfies protocol rule 2b: run without them
it prints `SKIPPED edition_010_matches_the_python_oracle: ... cargo test alone
does NOT prove edition 010.` Verified with `--nocapture`. The both-or-neither
guard fires as designed — setting exactly one panics at `preflight.rs:543`
with `set both MAG_PREFLIGHT_SPEC and MAG_PREFLIGHT_ORACLE, or neither`.

This is the improvement WP-5.2's verification asked for, implemented.

## Fixture coverage

Spot-checked `every_box_invalidity_condition_is_detected` against
`preflight.py:168-179`: the Python has exactly eight conditions and the
fixture names all eight individually (`page_below_one`, `page_above_count`,
`width_zero`, `height_zero`, `negative_x`, `negative_y`, `overflows_width`,
`overflows_height`) plus `not_four_values`, asserting both the invalid-box
count and the geometry blocker per case.

`_png_dimensions` confirmed dead: `grep -rn "_png_dimensions" src/magazine/`
returns one hit, its own definition at `preflight.py:39`. Correctly not
ported.

I found no branch of `preflight.py` reached by neither 010 nor a fixture.

## Residuals assessed

- **PNG-only contrast decoder.** Python's `_raster_dimensions` accepts JPEG
  and PIL decodes it; `metrics.rs::decode_rgb` is PNG-only, so a JPEG figure
  would be measured by Python and fail loud here. This is the
  **stricter-than-oracle** class revision 23 names, and the evidence describes
  the situation accurately without using that name. It is inherited from
  WP-5.3a rather than introduced here, it fails loud rather than computing
  something wrong, and 010 is all PNG so it is latent. Recording it is the
  right disposition for this WP; naming it as that class would give it an
  owner instead of leaving it a note. Not a rejection cause.
- `_placement_value`'s dict-versus-attribute branch: a Python affordance, not
  behaviour. Rust takes one typed struct and the real caller always passes the
  dataclass. Correct.
- `mod package` carries `#[allow(dead_code)]` for WP-5.5c to remove, matching
  the `mod model` precedent. Correct.

## On renaming to dodge the audit false positive

WP-5.1e's widened `no_helper_is_defined_in_two_modules` fired on `load`
defined in both `cover/outline.rs` and this module — same name and signature,
unrelated bodies and domains. The worker renamed its own to `Pdf::read`.

I judge that correct here. `Pdf::read` is at least as idiomatic as
`Pdf::load` for a function that reads a file into a struct, so the rename
costs nothing in clarity, and forcing an allowlist entry into a file this WP
does not own would have been an Owns violation. It did not distort the code
to satisfy the tool.

The underlying concern is real and correctly escalated rather than absorbed: a
(name, signature) key will keep firing on `load`, `open`, `read`, `from_path`
and similar, so either the allowlist grows without bound or the key needs
refining. The right test for the future is whether a rename ever produces a
*worse* name — that is the signal the key is wrong, and flagging it now rather
than after three more renames is the correct call.

## Errata

- The evidence states 4,018 bytes for the 010 oracle; my independent
  generation gives 5,299. The leaf count matches exactly at 153 and the test
  asserts fields, not bytes. Most likely absolute-path length in the embedded
  `path` values. Worth a one-line correction, not a defect.

## What is and is not proven

Proven, by tests I ran or reproduced: the 010 oracle equality against a Python
oracle I generated myself (not the worker's); non-vacuity on three computed
fields; Python-identical rounding on 18 cases including 11 binary-exact ties,
7 of which discriminate against round-half-up; `studio.ready` unreachable, read
from the Python source; the f32 enumeration complete, read from the Rust; the
eight `_box_invalid` conditions individually covered; `_png_dimensions` dead.

Not proven and not claimed: JPEG figure behaviour (no JPEG in 010, and the
path fails loud); the archived production `preflight.json` byte-for-byte (its
staged paths are gone, so the comparison is input-equivalent rather than
artefact-equivalent); and the echoed placement fields, which test pass-through
rather than computation.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01E6ATvPwrSFQPyq3AtsB9bE
