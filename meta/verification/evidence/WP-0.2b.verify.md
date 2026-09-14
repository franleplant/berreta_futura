# WP-0.2b verification

## Scope

- Worker commit: 1483f04 (diff base e9c6953)
- Critiquer amendment: f015859 (display.rs outline and text-string fixes,
  evidence critique section)
- Intervening commit cabd49d touches only WP-0.2a.verify.md (not part of
  this WP's diff)
- Verified state: f015859, fresh worktree, detached

## Owns check

Per-commit diffs: 1483f04 touches mag/Cargo.lock, mag/Cargo.toml,
mag/src/parity.rs, mag/src/parity/display.rs, mag/src/parity/streams.rs,
meta/verification/evidence/WP-0.2b.md, meta/verification/parity.yaml;
f015859 touches mag/src/parity/display.rs and the evidence file. All within
Owns. The parity.yaml hunk is limited to the font_name_map key and the
tools display-tracer entry (replacing the pending mutool placeholder), as
sanctioned. No *.verify.md, no baseline.json. PASS.

## Replayed commands (worktree at f015859, render trees A/B copied from the
main tree: render-2026-09-14T01-47-59, render-2026-09-14T01-49-02)

- 010 A vs A: exit 0, sha256(verdict.json)
  710878fb3f6453f6d7dee26a82a3b1af646c08050a62fd988310ab2877a2e891 --
  matches evidence exactly.
- 010 A vs B twice: exit 0 both, sha256
  a195f86db2d4b5ae3e6efeb78e8ba95ba784d924fc679e2c1d60ad34c9dd9ea7 both
  times -- byte-deterministic, matches evidence exactly.
- Element metric: 2176 = 2176, display_list pass. Matches.
- ExtGState probe on A: {'/ca 1': 108, '/CA 1': 54} = 162 entries, all
  alpha 1. Matches the claim.
- Fixture suite regenerated from the evidence's inline scripts: f4 bytes
  differ (cmp exit 1) yet fx4 passes wholly; matrix 15 OK / 0 BAD; failing
  fixtures fx1/fx2/fx3/fx5/fx6/fx7/fx8 all exit 1, fx4 exit 0. Matches.
- Critiquer regression demos, fixed build: nav-base vs nav-outl fails
  navigation, exit 1; title-plain vs title-utf16 passes, exit 0. Matches.
- Pre-fix confirmation: rebuilt the worktree at 1483f04; nav demo exit 0
  (false pass, outline silently dropped) and title demo exit 1 (false
  fail on UTF-16BE). Both claimed defects were real; both are fixed at
  f015859. Worktree returned to f015859 afterward.
- cargo fmt --check, cargo clippy -- -D warnings, cargo test: all green in
  the worktree.

## Audit

- No `sort` appears anywhere in display.rs or streams.rs: comparison is in
  paint order as Tier E requires.
- font_name_map: 11 alias pairs each carry file + sha256; spot-checked
  SourceSerif4SmText-Regular.ttf and GeistMono-SemiBold.ttf digests against
  the vendored files -- both match.
- tools.display_tracer = lopdf-0.45.0 recorded; asserted at startup per
  Reference stability.
- Residuals record the DCTDecode fail-loud boundary, the intra-show TJ
  kerning granularity (raster guard is WP-0.2c), the computed color
  normalization with color_space_map left empty and unowned (gap already
  on record), and the provisional typst-side face names.

## Verdict

ACCEPTED.
