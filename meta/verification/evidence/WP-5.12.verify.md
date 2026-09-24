# WP-5.12 verify: ACCEPTED

Verifier (WP-4.1 gate), tip `fa3fe15`, clean clone `.../tmp/g41/v`.

## Replay

- `mag parity --adhoc 906 --lang es`: exit 0, with no symlink aliases (numbers in
  WP-3.10.verify.md). The verdict's reader hashes are the es readers of the two legs,
  not the en ones.
- es `edition-manifest.json` figure paths from that run:
  - typst leg: `['media/diagram.png']`.
  - oracle leg: `/private/var/folders/.../mag-engine-render-stage-6cv5w1ub/library/sources/fixture-source-a/media/diagram.png`.

  The oracle path is still wrong, and WP-6.1 is its owner.
- Staged 010 stays en: the gate exits 0 at Tier E.

## Injected defect

`leg_langs` returns the bare language (`parity.rs:520`, en is not rendered alongside it).
`cargo test a_non_english_comparison` exit 101:
`a_non_english_comparison_renders_both_languages_and_never_touches_the_english_baseline`
FAILED. Restored.
