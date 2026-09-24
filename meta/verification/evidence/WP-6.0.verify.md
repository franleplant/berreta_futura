# WP-6.0 verify

Verdict: **ACCEPTED**.

Tip `41ea889`, worktree `<scratch>/v6`. Python loader = the tree's
`src/magazine` under `uv run` (CPython 3.12.11).

## Replay of the translation-loader oracle

| Command | Exit | Result |
|---|---|---|
| `uv run python <scratch>/regen.py > v6-cases-regen.json` (WP-6.0's generator, run fresh at the tip) | 0 | 101 cases; `cmp` against `mag/tests/model_manifest_cases_expected.json`: byte-equal |
| `uv run python tr_oracle.py regen.py mag tests/typeset_fixtures/corpus:906:es` | 0 | `cmp` against `model_manifest_translations_expected.json`: byte-equal |
| `cargo test --test model_manifest` | 0 | 11 passed, 0 failed (`cases_match_the_python_loader`, `real_translations_match_the_python_loader` included) |
| `MAG_TRANSLATION_ORACLE=<scratch>/tr_extra.json cargo test --test model_manifest real_` | 0 | 1 passed (the two 004 es entries) |

The three fixed cases, as Python produces them today and Rust matches:
- `translation_casefold_sharp_s`: `closing_plate_titles must be unique`
- `translation_strip_information_separators`: `article a1 author cannot be blank`, `closing_plate_titles cannot be blank`
- `translation_heading_split_at_separator`: loads OK, extract anchor `Presupuestos`

So Python still says what the committed file says, and Rust still agrees: the
fixes hold at the tip.

## Injected defect

`manifest.rs:1466` translation plate-title fold changed from `py_casefold` to
`to_lowercase` (re-introducing mismatch 1 at a single site).
`cargo test --test model_manifest`: `cases_match_the_python_loader` FAILED,
`1 cases diverge`. Restored.

## Not proven

As WP-6.0 states: equality with Python on built cases only; 004 never loads OK.
