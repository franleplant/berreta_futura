# WP-5.2 verification

## Verdict

ACCEPTED.

## Base

Verified state `ac443b0` (the re-land), which carries `07508f3` (the port)
unchanged. Pre-land HEAD at the time of this verification: `3a7e625`.

## Re-land completeness

The re-land is byte-identical to the original commit, which is the check that
matters when content has been deleted and restored.

- `git diff 07508f3 ac443b0 -- mag/src/impose.rs mag/tests/impose.rs
  mag/tests/impose_plan_expected.json mag/tests/impose_fixtures/
  meta/verification/evidence/WP-5.2.md` is EMPTY.
- Both commits report the same shape: 39 files, 12048 insertions.
- At HEAD, 37 tracked paths match `impose` (34 fixtures plus `impose.rs`,
  `tests/impose.rs`, `impose_plan_expected.json`); the remaining two of the
  39 are `mag/src/main.rs` and the evidence file, which do not carry the
  string. `git diff 07508f3 HEAD` over those paths is empty.

The deleting commit was `aa4bc01`, a VERIFY commit for a different WP, which
landed from a stale base and removed `mag/src/impose.rs` (437 lines),
`mag/tests/impose.rs` (474 lines), `mag/src/main.rs`'s registration and every
fixture. This is confirmed by `git show --stat aa4bc01`.

## The oracle design

The Phase 5 preamble forbids `mag parity` in oracle tests, so this WP built
its own display-list comparison: each page's content stream is decoded with
lopdf and emitted as one line per operation, with every resource NAME operand
replaced by the SHA256 of the object it resolves to (`tests/impose.rs:241`,
`:251`).

Judged sound. The digest substitution is what lets the comparison see through
pypdf's resource-renaming scheme without becoming blind to what is drawn: a
changed font, image or form still changes the digest, while a rename does
not. Operator identity and order are preserved verbatim, so a reordering or a
dropped operation fails. Raster and text legs use the pinned poppler 25.08.0,
asserted at test start.

One limit, which the WP records itself at evidence line 216 rather than
leaving it to be discovered: the comparison formats numeric operands at six
decimals (`tests/impose.rs:253-254`), so it cannot see a difference finer
than 1e-6. That is exactly the blindness that hid the f32 defect below. Under
rule 10 the instrument's resolution is stated where it is offered, which is
what the rule asks; the raster leg is what covers the gap, and it did.

## The f32 finding, confirmed independently

The most consequential result here, and it holds at the source.

- `lopdf::Object::Real(f32)` at
  `~/.cargo/registry/src/*/lopdf-0.45.0/src/object.rs:42`. Every real lopdf
  parses is f32, and `impose.rs:393` casts back with `value as f32`.
- Numerically, via `uv run python`: `419.527559` becomes
  `419.5275573730469` as f32, while `419.5276` becomes `419.527587890625`.
  The two MediaBox values that must stay distinct move toward each other, and
  the derived ratio changes in the eighth significant figure
  (`0.9999999022710305` against `0.9999999272572794`).
- The recovery (`authored_boxes`, `impose.rs:87`) regexes the raw file bytes
  for object headers and `/MediaBox`/`/CropBox` arrays, attributing each box
  to the nearest preceding header by offset, and `page_box` (`:170`) prefers
  the authored text when present.
- The refusal is correct and loud: when a box carries an `Object::Real` and
  no authored text was recovered, it bails with "carries a real that lopdf
  parsed as f32 and no authored text was recoverable; imposition would place
  it at reduced precision" (`:185`). It refuses rather than degrading, which
  is the right direction.

Object streams: a PDF storing page dictionaries in an `/ObjStm` yields no
plain `N G obj` header, so no authored text is recoverable and the refusal
fires. The evidence states this at lines 297-300 and notes WeasyPrint emits
none today. Acceptable, and correctly a loud stop rather than a silent
degradation, but it is a latent block if either engine ever emits object
streams.

## Perturbations reproduced

Two, both run in place and restored afterwards (`git status` clean).

**A. Scale height taken from CropBox** (`impose.rs:236`, `source.media[3] -
source.media[1]` to `source.crop[...]`).
- `imposition_matches_the_python_oracle` FAILED on `crop all`: the display
  list shows `cm 1.003378 ...` against the expected `cm 1.000000 ...`.
- `rasters_and_text_match_the_python_oracle` FAILED on `crop-all`, both
  sheets differing by digest at identical byte length.
- `imposition_matches_python_on_the_live_edition` PASSED. This is the
  finding worth recording: edition 010's CropBox equals its MediaBox on every
  page, so the live corpus cannot discriminate this defect at all, and the
  `crop` fixture is the only thing that can. It is a direct demonstration of
  the corpus rule.

**B. `authored_boxes` returning an empty map** (`impose.rs:130`).
- Both imposition tests FAILED with the fail-loud refusal verbatim:
  "MediaBox on object (3, 0) carries a real that lopdf parsed as f32 and no
  authored text was recoverable; imposition would place it at reduced
  precision".

## Public surface

Genuinely importable, not buried: `pub const A4_LANDSCAPE_POINTS` (`:8`),
`pub const BOOKLET_SECTIONS` (`:10`), `pub fn booklet_spreads` (`:30`),
`pub fn section_reader_pages` (`:40`), `pub fn imposed_reader_page_plan`
(`:61`), `pub fn cover_wrap_plan` (`:70`), `pub fn impose_a5_on_a4` (`:133`).
WP-5.3b and WP-5.5c can consume these without copying, which the duplicated-
helper rule requires of them.

## Baseline

In a fresh worktree at `ac443b0`: `cargo fmt --check` clean, `cargo clippy
--all-targets -- -D warnings` clean, `cargo test` 13 suites / 117 tests / 0
failures, with `tests/impose.rs` 4 passed in 23.60 s.

## Findings not blocking acceptance

1. `imposition_matches_python_on_the_live_edition` is env-gated on
   `MAG_IMPOSE_READER` and `MAG_IMPOSE_ORACLE_DIR`, returning early when
   neither is set and panicking when exactly one is (`tests/impose.rs:371`).
   That both-or-neither shape matches the precedent WP-5.1a set and its
   verifier accepted, and the evidence records the invocation at line 137
   with the real run timed at 1527 s. But in a bare `cargo test` the test
   passes VACUOUSLY, and the evidence does not label that mode. Under rule 10
   it should say so, since a reader seeing "4 passed" would reasonably
   believe the live edition was compared.
2. The f32 hazard is not local to this WP. Every WP doing arithmetic on
   lopdf-parsed numbers inherits it, including WP-5.4, WP-5.5c and the
   comparator itself, whose display list quantises coordinates it obtained
   through the same parser. The raw-byte recovery here is per-WP and scoped
   to page boxes; a shared exact-number path is the right shape and is
   outside this WP's Owns. The worker flagged this and I confirm it.
3. The display list's six-decimal resolution is recorded but its consequence
   could be stated more directly: the display-list leg is not a superset of
   the raster leg, and a sub-1e-6 placement difference is caught only by
   rasters. That is now demonstrated rather than theoretical.

## Commands

```
git diff 07508f3 ac443b0 -- mag/src/impose.rs mag/tests/impose.rs \
  mag/tests/impose_plan_expected.json mag/tests/impose_fixtures/ \
  meta/verification/evidence/WP-5.2.md --stat
git show --stat --format="%h %s" aa4bc01
git worktree add <wt> ac443b0
cd <wt>/mag && cargo fmt --check && cargo clippy --all-targets -- -D warnings && cargo test
grep -n "Real(f32)" ~/.cargo/registry/src/*/lopdf-0.45.0/src/object.rs
uv run python -c "import struct; v=419.527559; print(repr(struct.unpack('f',struct.pack('f',v))[0]))"
# perturbation A
sed -i '' '236s/source\.media\[3\] - source\.media\[1\]/source.crop[3] - source.crop[1]/' mag/src/impose.rs
cd mag && cargo test --test impose
# perturbation B
sed -i '' '130s/^    Ok(out)$/    Ok(Authored::new())/' mag/src/impose.rs
cd mag && cargo test --test impose
```

## Tool versions

rustc 1.96.0, lopdf 0.45.0, poppler 25.08.0 (asserted by the suite),
`uv run python` 3.12.11.

## Status

done
