# WP-1.4 verification

## Scope of this verification

Protocol rule 3, Phase 1 preamble: verification for spikes is DOWNGRADED to an
evidence-consistency audit. Unusually for a spike, most of this one WAS
independently reproducible: the throwaway cargo project survives at
`/Users/franguijarro/.claude/jobs/7d99e27f/tmp/wp14`, so the pin, the
dependency claims, the MSRV and the determinism result were checked directly
rather than audited on the page. That is recorded below claim by claim.

## Subject

- WP commit: `227dfb2` (`spike(parity): WP-1.4 typst measurement interface and
  version pin`)
- Evidence: `meta/verification/evidence/WP-1.4.md`
- Declared base: `0bd7cc0`
- Declared Status: `done`

## Owns check: PASS

`git show --stat 227dfb2` lists exactly one file,
`meta/verification/evidence/WP-1.4.md` (655 insertions). No tracked source
changed, no `*.verify.md`, no `baseline.json`, and `mag/Cargo.toml` is
untouched, which matters because this WP determines a pin that it is
explicitly not allowed to write (WP-2.0a owns that). `git status --short` in
the main tree carries nothing of this spike.

## Evidence completeness: PASS

All mandatory sections present, plus `## The API path` and
`## RenderLayout field mapping`. `src/main.rs` is reproduced in full.

## Claims verified directly against the surviving spike project

| claim | result |
|---|---|
| five direct deps, all `=0.15.1` | CONFIRMED: `Cargo.toml` lists exactly `typst`, `typst-layout`, `typst-library`, `typst-pdf`, `typst-syntax`, each `"=0.15.1"` |
| every typst-family crate resolves to 0.15.1 | CONFIRMED in `Cargo.lock`: all 12 named crates plus `typst` itself at 0.15.1 |
| `comemo` is not needed as a direct dependency | CONFIRMED: absent from `Cargo.toml`, and the project builds as committed |
| edition 2021, no bump needed for `mag` | CONFIRMED: `Cargo.toml` declares `edition = "2021"` |
| MSRV 1.92 | CONFIRMED: `rust-version = "1.92"` in both `typst-0.15.1` and `typst-pdf-0.15.1` manifests in the cargo registry |
| PDF export is byte-reproducible | CONFIRMED: `cmp out1.pdf out2.pdf` is byte-identical and both hash to `80eb42c4c651c082ed4fe1e5efffed6d5fed35edb3e3c40b3d190d7db7a047ea`, the exact sha256 recorded in the evidence |
| frame-walk output is deterministic | CONFIRMED: `run1.txt` and `run2.txt` are identical |

The PDF hash matching the recorded value exactly is the strongest single result
in this audit: it means the number in the evidence was produced by the artifact
that still exists, not transcribed or approximated.

**One numeric nit.** The evidence says the five deps resolve to "295 packages
total"; `Cargo.lock` carries 296 `[[package]]` entries. The difference is the
root crate `wp14_spike` itself, so 295 dependencies is correct and the phrasing
"packages total" is loose by one. No consequence.

## Internal consistency: PASS, and unusually strong

The derived metrics are not merely stated, they recompute from the file's own
geometry:

- A5 is given as 419.528 x 595.276 pt. 148 mm x 72/25.4 = 419.5276 and 210 mm x
  72/25.4 = 595.2756. Correct.
- The vertical margin implied by the query anchor (45.354 pt) is 16 mm, which
  matches the residual's own admission that the margin constant is hardcoded to
  the fixture's 16 mm.
- `frame_usage` reproduces exactly from `content_bottom` and that geometry.
  Body height is 595.276 - 2 x 45.354 = 504.568. Page 1: (360.964 - 45.354) /
  504.568 = 0.6255. Page 2: (293.634 - 45.354) / 504.568 = 0.4921. Page 3:
  (111.734 - 45.354) / 504.568 = 0.1316. All three match the recorded values.
- `terminal_gap` likewise: body bottom is 549.922, so 549.922 - 360.964 =
  188.958, - 293.634 = 256.288, - 111.734 = 438.188, matching the recorded
  188.957 / 256.287 / 438.187 to within the printed rounding.
- Body leading is self-consistent: the three baselines 68.934, 79.634, 90.334
  sit exactly 10.700 pt apart, as stated.
- The figure placement is centred as a full-width A5 figure should be:
  (419.528 - 170.079) / 2 = 124.7245, matching the recorded x of 124.724.

An evidence file whose aggregate metrics can be rederived from its own
primitives is materially harder to fake than one that only reports totals.

## Assessment of the target

The WP's target has two halves and both are met by a running program rather
than by documentation:

1. Per-element positions sufficient for `RenderLayout`, from Rust, without
   parsing the PDF. The frame walk yields one `TextItem` per laid-out line with
   its baseline origin and per-glyph advances, `FrameItem::Image` yields the
   figure placement rect directly, `FrameItem::Shape` covers rules and
   ornaments, and `FrameItem::Link` yields navigation before PDF export. The
   sub-0.1 pt requirement is comfortably met (`Abs` is an f64 internally).
2. The exact versions to pin, with three corrections that change what WP-2.0a
   must write: `typst-layout` and `typst-syntax` are required direct
   dependencies, and `comemo` is not.

The `RenderLayout` mapping table marks each field proven or derivable and
flags `article_opener_fits` as not exercised, with the reason (it needs the
real opener template) rather than omitting it. That is the behaviour rule 6
asks for.

The observation that the query anchor and the text baseline give different y
for the same heading (45.354 against 54.734), with both correct and the
consumer obliged to choose deliberately, is exactly the kind of trap that would
otherwise have surfaced as an unexplained Phase 3 offset.

## Carried-forward note

The file correctly repeats WP-0.0b's finding that the oracle side of
`article_opener_fits` is currently vacuous, so any future comparison of that
field would compare real Typst values against an empty oracle dict until that
is resolved. That cross-reference is accurate and belongs in whatever plan
revision handles the opener-fits gap.

## Minor record defects

1. `## Base` states the spike lived under
   `/Users/franguijarro/.claude/jobs/7d99e27f/tmp/wp14`, while `## Commands`
   instructs `mkdir -p /tmp/wp14 && cd /tmp/wp14`. The surviving project is at
   the former. A replay from the commands would work (it builds from scratch),
   but the two paths disagree.
2. The "295 packages total" nit recorded above.

Neither affects a result.

## Verdict

**ACCEPTED**, and the `done` status is justified rather than merely asserted:
the pin, the dependency corrections, the MSRV and the determinism claim were
all reproduced independently from the surviving artifact, and the derived
layout metrics recompute from the file's own primitives.

WP-2.0a can write the pin from this evidence as it stands, including the three
corrections (add `typst-layout`, add `typst-syntax`, do not add `comemo`).
