# WP-3.3a verification

Verdict: **ACCEPTED**

Verified at art_directed `01ca472` (after WP-5.5d extended the same code),
fresh worktree. Worker commit `cfafc9b`: highlight module, tables, tests,
two generator scripts, Cargo.toml/lock (fancy-regex made direct), main.rs.

## Replay

- `cargo test --release --test highlight -- --nocapture`: exit 0, 15 passed,
  `blocks 312 spans 10283 classes 50`, `refused (scratch only) []`. The 301
  WP-3.3a blocks are a subset (312 = 301 + WP-5.5d's 11 snippets); the
  WP-3.3a languages all compare byte for byte.
- `tables_are_generated_from_the_locked_pygments` green (regenerated ==
  committed). Full `cargo test`, fmt, clippy green.

## Fresh snippets, not in the corpus

45 snippets I wrote for this verify, 5 per language: ts, js, sh, toml,
rust, sql, yaml, json, text (files in the job scratch `tmp/v4/snip/`).
They cover paths the evidence lists as unreached: TS decorators, generics,
enums, `satisfies`, regex literals; JS private fields, BigInt, generators,
labels; bash heredoc, `case`, `(( ))`, arrays, `$ ` prompts; TOML
multi-line and literal strings, datetimes, hex, array tables, dotted keys;
Rust lifetimes, raw strings, macros, attributes, byte literals; SQL DDL,
CTE, upsert, lower-case keywords, `::` casts; YAML block and folded
scalars, anchors/aliases, flow mappings, tags, directives, document
markers; JSON unicode escapes and surrogate pairs, big ints, exponents.
None equals a corpus block (checked against the corpus script's output).

Driver: Python computes `_highlight_code(code, lang)` and the folded code;
a throwaway test binary (not committed) calls `highlight::html(folded,
lang)`. Result: **45 of 45 byte-identical**, 0 mismatches, 36 to 140 spans
each (text 0, as pygments emits none). Together with the WP-5.5d set, 52
distinct classes appear.

Regex-dialect probes (the margin the evidence names):
- SQL `ſELECT` (U+017F, Python IGNORECASE folds it to `s`): identical.
- Python identifier `KKY` with U+212A, Rust `été`, YAML with U+000B: identical.
- Python code containing U+001C: **MISMATCH**. Pygments treats it as
  whitespace (Python `\s`), mag emits `<span class="err">\x1c</span>`.
  This is exactly the margin the evidence predicted; `fold_reader_characters`
  keeps control characters below U+0020, so it reaches the lexer. No
  captured source contains it. Recorded as a known divergence, not a
  rejection.

## Injected defects (mine)

1. `json.rs`: queued strings before `:` retagged `String.Double` instead of
   `Name.Tag`: `json_keys_become_tags` and the corpus test FAIL.
2. `engine.rs` dialect fix `\Z` -> `\z` removed (keep `\Z`): SURVIVES, also
   on four extra HTTP probes ending with and without a final newline. The
   only `\Z` uses are the four HTTP patterns of the form `(\r?\n|\Z)`,
   where the `\r?\n` branch is tried first, so fancy-regex's `\Z` and `\z`
   cannot differ there. Equivalent mutant.

Restored, `git status` clean.

## What is and is not proven

Proven: byte identity with pygments 2.21.0 on the corpus and on 45 fresh
realistic snippets across all nine WP-3.3a lexers. Not proven: Unicode
`\s` parity (U+001C to U+001F diverge, measured), other unexercised
Unicode ranges, and anything about PDFs (WP-3.3b).
