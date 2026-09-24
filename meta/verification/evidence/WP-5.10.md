# WP-5.10 evidence: cleanup batch from WP-5.5c, WP-5.5d, WP-3.3a, WP-0.0e verifications

## What changed

1. `mag/tests/package.rs`: the live package test now rasterizes every page of
   each PDF entry with `pdftoppm -r 110` (the dpi WP-5.5c.verify.md used) and
   asserts per-page PPM byte equality against the Python oracle, plus raster
   count equal to page count on both sides (`pdf_pages_match`, `rasters`).
   This matches the package-equality rule in QUEUE.md (PDFs page-count and
   page-raster equal).
2. `mag/tests/web_port_fixtures/wfx/try.md`: added `    unit: str = "k<U+00A0><U+2603>"`
   to the python block (the line WP-5.5d.verify.md measured).
3. `mag/src/highlight/engine.rs` `translate`: `\s` becomes `[\s\x1c-\x1f]` and
   `\S` becomes `[^\s\x1c-\x1f]`. Python `re` `\s` (str patterns) matches
   exactly Unicode White_Space plus U+001C..U+001F (enumerated over all code
   points with `python3 -c "re.match(r'\s', chr(c))"`: 29 code points, the
   four extras are 0x1c-0x1f); Rust regex `\s` is White_Space only. Inside a
   class the replacement is a nested class, which fancy_regex/regex treat as a
   union, so `[^\S\n]` keeps its meaning. New snippets
   `mag/tests/highlight_snippets/separators.{python,c,http}` carry
   U+001C..U+001F in code, strings, comments, preprocessor lines, HTTP
   headers and a JSON body.
4. Per-piece web `<title>` joins publication and heading with ": " in both
   `src/magazine/web_edition.py:691` and `mag/src/web/edition.rs:957` (was
   U+2014).

## Commands (worktree, CARGO_TARGET_DIR private)

- Before the engine fix, with the snippets added: `cargo test --test highlight`
  FAILED 1 of 15 (`c html in ["separators.c"]`: mag `<span class="err">\x1c`,
  pygments `<span class="w">\x1c`). After the fix: 15 passed.
- `cargo test --test web_port`: 15 passed with the fold line and the new
  title (Rust vs live Python byte-identical). Mutant `highlight::html(code, ...)`
  instead of `&folded` in `semantic.rs`: FAILED 7 of 15 (same count as
  WP-5.5d.verify.md); reverted with `git checkout`.
- Live package test, `MAG_PACKAGE_SPEC/ORACLE/TRACER_ORACLE` = the verifier's
  `tmp/v4/{spec.json,py-out,py-tracer-out}`, `cargo test --release --test
  package -- --test-threads 1 --nocapture`: exit 0, 51 passed;
  `RASTER booklet-a4-cover.pdf: 1`, `booklet-a4-interior.pdf: 26`,
  `booklet-a4.pdf: 28` pages equal at 110 dpi; `CLASSES {"bytes": 90, "pdf": 3,
  "pixels": 28, "report": 1}`. The spec names paths under
  `tmp/verify4/` (a removed worktree); I pointed a symlink `tmp/verify4` at
  the main tree, because rewriting the paths makes `preflight.json` differ
  (it records absolute paths).
- Positive control: comparing page i with oracle page i+1 FAILED at
  `booklet-a4-interior.pdf page 1 raster`; reverted.
- `cargo fmt --check` 0, `cargo clippy --all-targets -D warnings` 0,
  `cargo test` 637 passed, 0 failed across 31 binaries (skipped mode for the
  live package test). `uvx ruff format --check` and `ruff check` on
  `web_edition.py`: clean.

## What is and is not proven

Proven: the live test now compares every PDF page raster at 110 dpi and fails
on a mismatched page; the fold step is pinned by the wfx fixture (no-fold
mutant fails 7/15); U+001C..U+001F in c, python and http snippets highlight
byte-identically to the locked pygments; per-piece titles use ": " in both
engines and stay byte-identical. Not proven: other Python-vs-Rust class
differences (`\w`, `\d`, case folding beyond the WP-3.3a probes) and lexers
the snippet corpus does not load; the nested-class rewrite is exercised only
where corpus patterns run. The live package check depends on the verifier's
oracle and the symlink above; it is not a committed fixture.
