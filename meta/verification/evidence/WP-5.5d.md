# WP-5.5d evidence: highlighted code in the web port, python/c/http lexers, JPEG plates

## What changed

- `mag/src/web/semantic.rs` `fenced_code`: the refusal for fenced code with a
  language is gone; the body is `highlight::html(fold_reader_characters(code),
  language)`, which is `_highlight_code` (`html_edition.py:681`): fold, then
  pygments or the `escape(quote=False)` fallback. A name pygments knows but
  mag does not implement still fails loud (`Err`), now from the highlighter.
- `mag/src/highlight/`: three lexers from the locked pygments 2.21.0 through
  the same generator (`mag/tests/highlight_tables.py`):
  - PythonLexer (aliases python, py, python3, py3, pyi, sage, bazel,
    starlark). Needed `using(this)` (soft keyword `_`); `combined` states come
    through pygments' own `_tmp_N` states.
  - CLexer (alias c). Needed `using(this)` and `using(this, state=...)`
    (sub-lexing the group text with stack `root`+state), and
    CFamilyLexer's `get_tokens_unprocessed` retag: a `Name` whose text is in
    the stdlib/c99/c11/linux type sets becomes `Keyword.Type`; the sets are
    dumped into `tables.json` as `retype`.
  - HttpLexer (alias http). Its three callbacks ported: `header_callback`
    (records Content-Type up to `;`, stripped), `continuous_header_callback`,
    `content_callback` (body lexed by `get_lexer_for_mimetype(type)`, then the
    `a/b+c` -> `a/c` general type, else Text). The mimetype table (541
    entries, first match in LEXERS order, as pygments resolves) is dumped too;
    a body whose mimetype resolves to an unimplemented lexer (e.g. text/html)
    fails loud.
- Closing plates: `png_dimensions` removed; `closing_plates` uses the
  existing `crate::typeset::media::pixels` (PNG and JPEG by magic bytes, not
  extension, as PIL does). No file outside this WP's paths was edited;
  `web_port.rs` now `#[path]`-includes `typeset/media.rs` and
  `highlight/mod.rs`, so media.rs's own 2 unit tests also run in that binary.
- Fixtures: `wfx/try.md` gains fenced python (with info-string words),
  c, http (JSON body), ts, `YAML` (upper-case name) and `jsonc` (unknown to
  pygments, fallback). Three JPEG plates made by PIL: `plate-baseline.jpg`
  120x100 with an EXIF APP1 before the SOF, `plate-progressive.jpg` 100x117
  (SOF2), `plate-sliver.jpg` 100x250. `mag/tests/highlight_snippets/`: 11
  hand-written snippets (4 python, 2 c, 5 http: request with charset and a
  continuation header, `application/problem+json` response, text/plain,
  unknown mimetype, no body).

## Commands and results

- `cargo test --test highlight -- --nocapture`: exit 0, 15 passed.
  `blocks 312 spans 10283 classes 50`; per language (blocks, spans):
  python (11, 802), c (3, 385), http (8, 249); `refused (scratch only) []`.
  312 = WP-3.3a's 301 corpus blocks + 11 snippets. The 11 editions/004
  run-draft blocks WP-3.3a refused (python 7, http 3, c 1) now match
  `_highlight_code` byte for byte, as do all 11 snippets.
- Positive controls, each applied to `engine.rs` alone and restored (diff
  against the backup empty): retag off -> fails on `system.c`; `using`
  emitting the raw group -> fails on the editions/004 C block; Content-Type
  never recorded -> fails on the editions/004 http blocks; general-type
  fallback removed -> fails on `response.http`. All exit 101.
- Hand-written unit tests (python f-string, C `size_t` -> `kt`, http JSON
  body). The python one was first written wrong (I expected `w` for the
  indent and one `f"` token); pygments' own tokens (printed with
  `get_tokens`) are `""` for the indent and `sa`+`s2` split, and the test
  now pins those.
- `cargo test --test web_port`: exit 0, 15 passed (13 WP-5.5a tests, one
  renamed, plus media.rs's 2). The fixture semantic HTML and the whole wfx
  web tree are byte-identical to Python with the highlighted blocks in
  (`section-1.html` carries `<span class="kt">size_t</span>`); 010 and every
  other WP-5.5a comparison still byte-identical. Positive control: calling
  `highlight::html` with `""` fails 8 of the 15 tests.
- Plates: `plate_jpeg` and `plate_progressive` render and equal Python;
  `plate_sliver` refuses with Python's exact message, `has aspect 0.40`
  (a width/height swap would read 2.50).
- Unported language still refuses: `go` fence -> error naming `"go"`
  (`fenced_code_in_an_unported_lexer_refuses_rather_than_diverging`).
- Full `cargo test` in `mag/`: exit 0, 31 result lines, 0 failed.
  `cargo fmt`, `cargo clippy --all-targets -- -D warnings`: clean.
  `uvx ruff format --check` / `ruff check` on the two scripts: clean.
  `tools/nocomments.py`: exit 0.

## What is and is not proven

- Proven: on 312 blocks (all renderer and scratch corpus code plus 11
  snippets) Rust's highlight HTML equals pygments 2.21.0's byte for byte;
  the web port renders fenced code exactly as `_highlight_code` does on the
  wfx fixture, semantically and in the written web tree; JPEG plates
  (baseline with EXIF, progressive) are measured as PIL measures them.
- Equality is with pygments, not with correct syntax (e.g. HTTP headers are
  Text/Literal, Python indentation is Text, not Whitespace).
- Not proven: Python/C/HTTP lexer paths the snippets do not reach; the
  Python `re` vs fancy-regex margins WP-3.3a lists apply here too (the
  Python lexer's `xid_start` classes compile and the snippets' `café`,
  `naïve` match, but most of the Unicode ranges are unexercised).
- Plates narrower than PIL: formats other than PNG and JPEG (GIF, WebP,
  BMP, TIFF) are refused where PIL would open them; a zero-width raster
  refuses as unreadable in Rust where Python would report aspect 0.00. No
  edition uses either (all 109 `art_path` values end `.png`, per
  WP-5.5a.md).
- HTTP bodies whose Content-Type maps to a pygments lexer mag lacks (html,
  xml, css...) refuse rather than highlight.
