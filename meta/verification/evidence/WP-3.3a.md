# WP-3.3a evidence: pygments-equivalent highlighting in Rust

## What changed

- `mag/src/highlight/` (new, `#[allow(dead_code)] mod highlight;` in
  `main.rs`, not wired into typeset or web): `spans(code, language)` returns
  `Ok(None)` when pygments has no lexer for the name (the caller's
  plain-escape fallback), `Ok(Some(Vec<(text, class)>))` with adjacent
  same-class tokens merged, or `Err` when pygments WOULD highlight the name
  with a lexer mag does not implement (fail loud). `html(code, language)`
  reproduces `_highlight_code` after folding (the caller folds, as
  `html_edition.py:684` does before pygments).
- `engine.rs`: pygments' `RegexLexer` and `ExtendedRegexLexer` loops
  (`lexer.py:700-761`, `:800-850`), `bygroups`, `#pop`/`#push`/`#pop:n`, the
  newline reset (`w` for RegexLexer, `""` for Extended), the per-char `err`
  fallback, and YamlLexer's eight context callbacks (`data.py:47-165`),
  ported line for line including Python negative slicing in `save_indent`.
  Patterns run in `fancy-regex` 0.16 (already in Cargo.lock via typst, now a
  direct dependency) as `(?flags)\G(?:pattern)`, which is `re.match(text,
  pos)`: anchored at pos, lookbehind and `^` see the text before it.
  Dialect fixes: `\Z` -> `\z`; `[`, `&`, `~` escaped inside classes.
- `json.rs`: JsonLexer's hand-written state machine (`data.py:436-640`),
  including its queue that retags a string as `nt` when `:` follows.
- `tables.json`: the lexer state tables, token-class strings and the full
  alias list (927 aliases), dumped from the locked pygments 2.21.0 by
  `mag/tests/highlight_tables.py`; a test regenerates and byte-compares it.
- Lexers: TypeScript, JavaScript, Bash, TOML, Rust, SQL, YAML, JSON, Text,
  resolving 19 aliases exactly as `get_lexer_by_name` does (lowercased, first
  match in `LEXERS`, zero plugin lexers, which the generator asserts).

## Measurement 1: the colour equivalence

`weasyprint-a5.css:961-968` has 8 `pre code .x` rules naming 41 classes and 7
distinct values (`rgb(11% 22% 55%)` shared by 966 and 967; `.o`/`.p` are
`inherit`, like every unlisted class). Emitted classes in the matched corpus,
with span counts (8,847 spans, 31 classes, from the corpus test's HTML):

| ink | classes |
|---|---|
| inherit | w 3084, p 2106, nx 1126, o 559, n 154, nv 25, `l l-Scalar l-Scalar-Plain` 11, `p p-Indicator` 8, err 6, ne 1 |
| rgb(240 87 56) | k 649, kd 147, kr 29, ow 18, kc 7, kp 1 |
| rgb(9% 33% 20%) | s2 291, sb 42, si 40, s1 23, se 15, s 13 |
| rgb(46% 45% 48%) | c1 198, cm 10 |
| rgb(11% 22% 55%) | nt 46, nb 52, nc 33 |
| rgb(25% 10% 43%) | kt 129 |
| rgb(45% 12% 16%) | mf 19, mi 3, m 2 |

The equivalence turned out not to be needed: class names match exactly, so
the stricter bar holds.

## Measurement 2: the corpus

Rule: every fence or indented code block in git-tracked
`library/sources/*/article.md` and `editions/**/*.md`, parsed with the
renderer's own markdown-it instance and glyph fallbacks, deduplicated by
(code, language). 383 occurrences, 301 unique blocks.

- Plan reconciliation: library-only, occurrence-counted, language-tagged =
  **106 blocks, 8,559 spans, 31 classes**, the figures in
  `meta/verification/evidence/WP-5.5a.md:84-89`, reproduced exactly.
- Renderer-reachable (not under `run-*`/`render-*` scratch): 240 unique; ts
  46, sh 19, js 12, jsonc 7, toml 6, rust 5, bash 3, yaml 2, json 2, txt 2,
  sql 2, untagged 134.
- Scratch-only languages: python 7, http 3, c 1 (pygments has lexers, mag
  refuses them: `Err`), text 5 (implemented). Their files are run drafts
  (`editions/004/run-2026-08-05*`, `run-2026-08-06*`) no edition.yaml names.

## Result

`cargo test --test highlight -- --nocapture`, exit 0, 12 passed:

- `every_corpus_block_matches_pygments`: all 301 blocks. For 290, Rust's
  `html` equals the oracle's `_highlight_code(code, language)` BYTE FOR BYTE
  and the per-character ink sequences (CSS parsed live, newline excluded)
  are equal; 173 untagged + 9 jsonc/txt take the fallback on both sides; the
  11 python/http/c blocks are refused, and the test asserts each refused one
  is scratch-only and has a pygments lexer.
  `blocks 301 spans 8847 classes 31`.
- Positive control: rewriting every `"t": "kd"` to `"kr"` in tables.json
  (same ink, different class) fails the test at the first js block
  (`<span class="kr">class</span>` vs `kd`), exit 101; restored.
- `tables_are_generated_from_the_locked_pygments`: regenerated == committed.
- Unit tests per language (ts, js, sh, toml, rust, sql, json, yaml) and the
  fallback/refusal test. The expectations were written by hand before the
  first run; two were wrong and were corrected only after reading pygments'
  own tokens: TOML `[a]` is Keyword throughout and Rust `1u8` is
  Integer `1` + Keyword `u8`. Those are pygments' choices, arguably wrong as
  syntax, pinned because print parity is the requirement.

**Web bar decision (plan ~7896-7905): class names match exactly, so web
HTML inside `<pre><code>` is byte-identical on the corpus and NO divergence
is declared.**

Also: full `cargo test` in `mag/` exit 0 (31 test binaries, 0 failed);
`cargo fmt`, `cargo clippy --all-targets -- -D warnings` (no output),
`uvx ruff format`/`ruff check` on the two scripts ("All checks passed!"),
`tools/nocomments.py` exit 0 ("no comments"); the pre-commit hook reran them.

## What is and is not proven

- Proven: on all 290 highlightable corpus blocks, Rust's output equals
  pygments 2.21.0's at HTML byte level, which implies equal classes and
  therefore equal print inks; unknown names fall back exactly (alias table
  from pygments itself), unimplemented known names fail loud.
- Not proven: lexer paths the corpus does not reach (e.g. most of SqlLexer's
  keyword list, YAML block scalars, JSON unicode escapes). Pattern
  semantics differ between Python `re` and fancy-regex at the margins
  (Unicode `\s` includes U+001C-U+001F in Python, not in Rust; IGNORECASE
  folding); no corpus text exercises them, and a future divergence there is
  a new case for this test, not a known gap.
- Not proven: anything about PDFs. Tier S colour parity needs WP-3.3b to
  wire this into typeset; the web tree needs WP-5.5d.
- Equality is with pygments, not with correct syntax: where pygments
  mis-tokenises (the `err` spans, TOML tables as Keyword), Rust does too, on
  purpose.
- Pygments version pinning: tables are frozen at 2.21.0 (uv.lock); a
  pygments upgrade makes the freshness test fail rather than drift silently.
