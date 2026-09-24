# WP-5.5d verification

Verdict: **ACCEPTED** (one test-coverage advisory, below)

Verified at art_directed `01ca472`, fresh worktree. Worker commit
`9b3befa`: highlight engine/tables/mod, `web/semantic.rs`, tests, snippets,
wfx fixture and three JPEG plates.

## Replay

- `cargo test --release --test highlight -- --nocapture`: exit 0, 15
  passed, `blocks 312 spans 10283 classes 50`, python (11, 802), c (3, 385),
  http (8, 249), `refused (scratch only) []`. Matches the evidence.
- `cargo test --release --test web_port`: exit 0, 15 passed.
- Full `cargo test` exit 0 (637 passed), fmt, clippy green.

## Fresh snippets, not in the corpus

15 snippets I wrote, 5 each for python, c, http (`tmp/v4/snip/`): Python
dataclasses, decorators, async and walrus, `!r:>10` f-string spec, bytes,
docstrings, try/except/finally, comprehensions, metaclass, raw/byte/unicode
prefixes, complex literals; C includes, typedef struct, pointers,
preprocessor conditionals and variadic macros, ULL suffix, `size_t` and
`uint32_t` retags, enum/union, goto labels, char literals; HTTP GET with
bearer header and blank body, POST with `application/json; charset=utf-8`,
a 200 JSON response, an HTTP/2 402 with `text/plain`, a PUT with
`application/x-yaml`. Plus four HTTP probes ending with no final newline.

Result: **15 of 15 byte-identical** to `_highlight_code` (11 to 127 spans
each), and 4 of 4 probes identical.

## Injected defects (mine)

1. `engine.rs` `header_callback`: Content-Type no longer cut at `;`
   (`let value = value;`): the corpus test FAILS (the `charset` request).
2. `semantic.rs`: `highlight::html(code, ...)` instead of `&folded` (the
   fold step skipped): **SURVIVES**, web_port 15/15. No fenced block in the
   wfx fixture or in 010 contains a character the fold changes (the curly
   quotes and ellipsis in `try.md` are settable). Measured fix: adding one
   line `    unit: str = "k<U+00A0><U+2603>"` to the python block of
   `wfx/try.md` keeps the unmutated port byte-identical to Python (15
   passed) and makes the no-fold mutant fail 7 of 15. Not applied (verifier
   changes no code).

Restored, `git status` clean.

## Advisory (not blocking)

The "fold, then pygments" claim is true (the code does it and the probe
above shows Python agreeing with a folded line), but no committed test pins
it. The one-line fixture addition above closes it; owner WP-5.5d's
successor or whoever next touches the wfx fixture.

## What is and is not proven

Proven: highlight byte identity on the corpus plus 15 fresh
python/c/http snippets; web fenced code equal to Python on the fixture;
JPEG plates as claimed (tests green). Not proven: the fold step under test
(advisory), HTTP bodies whose mimetype maps to an unimplemented lexer
(refuse by design), the Unicode `\s` margin (see WP-3.3a.verify.md: U+001C
diverges).
