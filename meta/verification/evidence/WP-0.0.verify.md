# WP-0.0 verification

Verifier rerun per protocol rule 3, from a fresh worktree at the WP commit.

## Base and commit

- Base: e127cb0de2fc371d63b76d18f41baf230c2bcb12
- WP commit: 06bc764 (sole commit past base)
- Worktree: fresh checkout of 06bc764 under the job scratch root, with the
  untracked run directory `editions/010/run-2026-09-13T01-34-51` copied in.

## Owns check

`git diff --name-only e127cb0..06bc764` lists exactly `mag/src/main.rs`,
`mag/src/render.rs`, `meta/verification/evidence/WP-0.0.md`. No
`*.verify.md`, no `baseline.json`. PASS.

## Replayed commands

- `cargo fmt --check`, `cargo clippy --all-targets -- -D warnings`,
  `cargo test`: all exit 0 in the worktree. Matches claim.
- Fixture clause (scratch edition `zz-wp00fx`, one figure anchored to a
  heading absent from the manuscript): exit 1, stderr
  `--no-model: 1 figure anchor(s) need model patching:` and
  `a1:fig-x (anchor 'Missing Heading')`; no `render-*` directory created.
  Matches claim. Fixture moved to scratch after, worktree clean.
- 010 renders with and without `--no-model` (run
  `editions/010/run-2026-09-13T01-34-51`): both print
  `pending anchors: 0`, exit 0. Outputs
  `render-2026-09-14T01-40-28` (flag) vs `render-2026-09-14T01-41-36`.
- `pdftotext` dumps and `pdfinfo` boxes/pages: byte-identical for
  reader.pdf, booklet-a4.pdf, booklet-a4-interior.pdf,
  booklet-a4-cover.pdf. Matches claim.
- `request.json` and `en/edition-manifest.json`: byte-identical. Matches
  claim.
- Leaf comparison of `en/render-critic.json` (2 differing leaves) and
  `en/preflight.json` (4 differing leaves): every differing leaf ends in
  `_sha256` or is a `.path` under `mag-engine-render-stage-*`; none
  outside the whitelist shape. Matches claim, confirming the Residuals
  noted for WP-0.1.

## Verdict digests

Evidence declares none (comparator does not exist yet). Consistent.

## Verdict

ACCEPTED.
