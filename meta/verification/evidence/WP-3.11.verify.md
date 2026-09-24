# WP-3.11 verify: ACCEPTED

Verifier (WP-4.1 gate), tip `fa3fe15`, clean clone `.../tmp/g41/v`.
`uv run python tools/sourcecodes.py 008` (exit 0) was run in the clone only and not
committed, as the worker did.

## Replay

```sh
MAG_PARITY_OUT_DIR=.../g41/a008 mag parity --adhoc 008 --run editions/008/run-2026-08-30T13-59-32   # exit 0
```

page_count 44/44. Critic pass (1676 leaves, 804 excluded, 0 differ; Rust text fields 87
pages, 0 differ; text_characters 0). Boxes, text, colour (36915), navigation (38 links,
37 outlines) pass. G max dx 0.000, dy 0.006. E glyph positions 36794 glyphs, 0
violations. Display list 36969 vs 36969, 0 pages. V worst 0.000336. These equal
WP-3.11.md's numbers, p4 (the editorial) included. Readers: oracle `91cf4163...`, typst
`5041f005...`. 010 has no editorial and stays green at E (gate). The typst readers of 906
en/es are `4427b8cd`/`a5594d73`, the values WP-3.11.md lists for the base binary, so no
regression on the fixtures checked.

## Injected defect

The editorial field floor was raised (`typeset/estimate.rs:36`, 390.0 -> 400.0).
`cargo test an_editorial_title_is_fitted` exit 101:
`an_editorial_title_is_fitted_on_the_live_width_over_a_clamped_field` FAILED. Restored.

## Not proven

Any editorial other than 008's (no other edition loads on the bridge, WP-3.11.md).
A Spanish editorial. Section openers.
