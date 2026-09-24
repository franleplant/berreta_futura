# WP-3.10 verify: ACCEPTED

Verifier (WP-4.1 gate), tip `fa3fe15`, clean clone `.../tmp/g41/v`. Fixture 906 was
copied into `editions/` and its sources into `library/sources/` for the run, then moved
out.

## Replay

```sh
MAG_PARITY_OUT_DIR=.../g41/a906es mag parity --adhoc 906 --lang es   # exit 0
```

page_count 16/16. Critic pass (643 leaves, 288 excluded, 0 differ; Rust text fields 31
pages, 0 differ). Boxes, text (16 pages), colour (3539), navigation (10 links, 8
outlines) pass. G max dy 0.006. E glyph positions 3513 glyphs, 0 violations. Display
list 3557 vs 3557. V worst 0.000237. These are the numbers WP-3.10.md and WP-5.12.md
recorded. The es readers were compared: the verdict's `a_reader_sha256` `04023351...`
equals the oracle render's `es/reader.pdf`, and `b` is `a5594d73...`, the typst es
reader (its en reader is `4427b8cd...`, a different file).

## Injected defect

Pyphen's left minimum changed from 3 to 2 (`typeset/hyphen.rs:13`).
`cargo test hyphen` exit 101:
`spanish_words_divide_at_their_syllables_leaving_three_letters_each_side` FAILED. Restored.

## Not proven

No real Spanish edition exists (WP-3.10.md). The step-3 rule is exact for plain text only.
