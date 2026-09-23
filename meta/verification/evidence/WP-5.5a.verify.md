# WP-5.5a verification (increments 1 and 2)

Verifier worktree at 9c65b66 (art_directed head; contains d0bb66b and
d2789ec), own `CARGO_TARGET_DIR`, fresh target so the test stage and the
Python oracle trees were built by this run, not reused. No code changed:
every mutation and scratch fixture row was restored (`cmp` exit 0 against a
saved copy, `git status --short` empty before this file was written).

## Verdict: ACCEPTED

The byte-equality claims replay exactly, both of my own mutations that the
worker did not list are caught, and the remaining gaps are real, listed, and
fail loud where they can. Two notes below (one unpinned boundary, one
inaccurate sentence about translations) are not grounds for rejection.

## Replay

| command (in `mag/`) | exit | observed |
| --- | --- | --- |
| `cargo test --test web_port` | 0 | 13 passed, the same 13 names as the evidence |
| `cargo test` (full) | 0 | 29 binaries, all `ok`, 476 passed, 0 failed |
| `cargo fmt --check` | 0 | |
| `cargo clippy -q --all-targets -- -D warnings` | 0 | no output |
| `diff -rq editions/010/render-2026-09-23T22-57-54/en/web <stage>/rust-web/010` | 0 | 51 files in the Rust tree; render dir is the main tree's production render (gitignored, not written by the test) |
| same diff against `<stage>/rust-web/010_chrome` (negative control) | 1 | 13 lines of differences |

The oracle is the real Python: `PYTHON` and `WEB_PYTHON` in
`mag/tests/web_port.rs` import `magazine.html_edition.render_html_edition`
and `magazine.web_edition.write_web_edition` via `uv run` in the worktree,
and `compare_tree` asserts equal file sets and then equal bytes per file, so
`wfx` and `010` are whole-tree byte comparisons rather than spot checks.

## Mutations of my own (not in the worker's lists), each restored

| file | mutation | result |
| --- | --- | --- |
| semantic.rs | hard break `<br>` to `<br/>` | caught: 7 of 13 tests fail |
| edition.rs | colophon `here` on the cover page `index.html` to `edition.html` (alternate-language links point at the wrong sibling) | caught: `chrome_options_are_byte_identical` fails |
| edition.rs | colophon `lang` attribute uppercased (`lang="ES"`) | caught: 1 test fails |
| semantic.rs | ordered-list start test `*start != 1` to `*start > 1` | SURVIVED |

The survivor is a boundary with no straddle: no fixture list starts at 0,
so the `start="0"` branch is unpinned. I checked the real behaviour with a
scratch row (`0. Zeroth.` / `1. First.` appended to
`wfx/articles/keyed.md`, not committed): the unmutated port stays green and
both trees carry `<ol start="0">` twice, so the port is right; with the row
present the mutant is caught (7 tests fail). The row is cheap and worth
adding, but its absence hides no divergence today.

## Are the remaining gaps honestly scoped

- Not wired into the binary (WP-5.6's `render.rs`): true.
  `engine_render_bridge.py:347` still calls `write_web_edition` and
  `weasyprint_adapter.py:411` calls `render_html_edition`.
- Fenced code with a language refuses: true and tested
  (`fenced_code_with_a_language_refuses_rather_than_diverging`).
- PNG-only closing plates: true and harmless today; `grep -h art_path
  editions/*/edition.yaml` gives 109 rows, 0 not ending in `.png`.
- Unfixtured refusals: the listed reasons (unreachable while the semantic
  renderer keeps its shape) are plausible; not independently exercised.
- **Translations: the gap is listed, but one sentence is inaccurate.** The
  evidence says "nothing in either module branches on language beyond
  `ui`". Language also reaches the web tree through
  `<html lang="{edition.locale}">` (`html_edition.py:94`) and through the
  imported cover helpers (`cover_tab_issue` gives `NÚMERO` for non-English,
  `mag/src/cover/text.rs:34`, used in the colophon). Those helpers are
  WP-5.4a's and have their own oracle, and the gap stays "not proven", so
  the scope is honest; the sentence understates what a Spanish oracle run
  would exercise.
- Shared-design caveat (illustrated articles carry no web provenance line)
  is correctly framed as equality, not correctness.

## What is and is not proven

Proven: on this head, the Rust semantic HTML, asset inventory, and full web
tree equal the Python modules byte for byte for 010 and every `wfx`
variant, the 010 tree equals a production `en/web` render, and three of four
independent mutations are caught; the fourth exposed an unpinned but
correct boundary (`start="0"`).

Not proven: anything about a translated edition, fenced code with a
language, non-PNG plates, or the binary producing this tree.
