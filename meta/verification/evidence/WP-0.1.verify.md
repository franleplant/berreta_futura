# WP-0.1 verification

## Verdict

ACCEPTED

## Base and commits

- Diff base: 8eb087a
- Worker commit: 9b42586
- Critiquer amendment: 86e41b4 (parity.yaml only)
- State verified: 86e41b4, in a fresh worktree at that commit with the
  untracked run dir `editions/010/run-2026-09-13T01-34-51` copied in.

## Owns check

`git diff --name-only 8eb087a..86e41b4` lists exactly
`meta/verification/evidence/WP-0.1.md` and `meta/verification/parity.yaml`.
No verify files, no baseline.json. Pass.

## Replayed commands, observed vs claimed

- `cargo build` then two `mag render 010 --no-model --langs en --run
  editions/010/run-2026-09-13T01-34-51` from the worktree: out dirs
  `render-2026-09-14T01-56-20` (A) and `render-2026-09-14T01-57-23` (B).
  A third render confirmed the `pending anchors: 0` line prints (the claim
  for both runs; a nonzero count aborts under `--no-model`, so both
  successful renders imply 0). Claimed: identical dumps and 0 anchors.
  Observed: match.
- pdftotext raw dumps byte-identical for all four PDFs (reader, booklet-a4,
  booklet-a4-interior, booklet-a4-cover). Claimed: identical. Match.
- pdfinfo -box identical for all four PDFs excluding
  CreationDate/ModDate/File size; `File size` genuinely differs
  (87139114 vs 87139122 bytes on reader.pdf), so the critiquer's added
  strip entry is required, as claimed.
- request.json and edition-manifest.json byte-equal. Match.
- Leaf diff on preflight.json and render-critic.json: exactly the six
  whitelisted leaves and nothing else; the four preflight `.path` leaves
  all satisfy `only_if_both_values_contain: /mag-engine-render-stage-`
  on both sides; the two render-critic `_sha256` leaves are the
  unconditional entries. Claimed whitelist is closed and matches. Match.
- Tool versions replayed from the worktree: weasyprint 69.0, pydyf 0.12.1,
  pyphen 0.17.2, pypdf 6.14.2, pygments 2.21.0, pillow 12.3.0,
  Python 3.12.11, uv 0.8.17, poppler 25.08.0, rustc 1.96.0, macOS 26.6.2.
  All equal `parity.yaml tools:`. Match.

## parity.yaml structural audit

`normalization:` carries strip_pdf_keys (closed whitelist as above),
whitespace and hyphen_rejoin matching the plan's Normalization section,
and declared-empty color_space_map (authored_by: unassigned, plan gap
flagged), merge_rewrite_rules (WP-0.2c), font_name_map (WP-0.2b).
`tools:` complete with pending placeholders for mutool (WP-0.2b) and
typst crates (WP-1.4/2.0a). No threshold or tier definition weakened.

## Notes

- The color_space_map ownership gap is recorded for a plan decision; it
  does not affect this WP's target.
- Render dirs A and B from this verification are left in the (temporary)
  verify worktree only; the worktree is removed after commit.
