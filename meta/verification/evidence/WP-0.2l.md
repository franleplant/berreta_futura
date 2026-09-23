# WP-0.2l the digest does not cover the RENDERER

## Base

`0494017` (`docs(verification): one-page worker brief ...`). Every measurement
below was taken in a detached worktree at that base plus this WP's diff.

## Status

`done`, pending the verifier's one-time rebase of `baseline.json` (see below).

## What changed

- `mag/src/parity.rs`: the staged-input digest now hashes, beside the 57 edition
  inputs of `request.json`, every file under `src/magazine/` (recursively,
  skipping `__pycache__/` and dot files) and `uv.lock`, each keyed
  `renderer:<repo path>`. The verdict's `staleness` carries `edition_inputs` and
  `renderer_inputs`, and the summary prints both counts next to the digest.
- The cardinality half: `tier S text` reports pages compared, `tier G` and
  `tier V` report pages compared, `tier E display list` reports elements
  compared on each leg. `code_blocks` and `critic`, previously absent from the
  summary, now print `not_evaluated` with a `reason` (new JSON field) and their
  owner. When page counts differ, every interior clause prints
  `not_evaluated (page counts A vs B: the interior domain needs equal counts of
  at least 3)` instead of printing nothing. `tier E raster` names why
  (`parity.yaml tiers.e.raster_bound has no value`).
- `mag/src/parity/text.rs`: `TextClause.pages_compared`, one field. This file
  is outside the brief's named `parity.rs` but inside the plan's serial
  `mag/src/parity*` set; the sweep cannot report a count the struct does not
  carry.
- Where the fix lives: the plan's Owns line says "the staging path in
  `mag/src/render.rs`", but the digest is computed in `parity.rs`
  (`staged_digest`), not in `render.rs`, so `render.rs` is untouched.
  Residual 2 of WP-0.2k (refusal costs a render) is not addressed.

## What the digest covers, and what it deliberately does not

The adapter's reads were enumerated from `src/magazine/weasyprint_adapter.py`
(`resources.files("magazine")` for `assets/weasyprint-a5.css`, the `@font-face`
URLs under `assets/fonts/`, `_advance_widths` reading the TTFs directly),
`reader_text.py` (the fonts folder) and `cover.py` (Inter, Archivo, Source
Serif by path). The import graph from the entry point
`magazine.engine_render_bridge:main` (pyproject `mag-render-adapter`), walked
with `ast`, reaches every module in the package, so the whole package is in.

Included (43 files, measured): the 42 tracked files of `src/magazine/`
(`git ls-files src/magazine | wc -l` = 42), of which 19 are under `assets/`
(2 stylesheets, 12 TTFs, 4 font licences and a README), plus `uv.lock`, which pins
WeasyPrint and its Python dependencies.

Deliberately NOT included, each a known gap rather than an oversight:

- System libraries WeasyPrint loads through cffi (pango, harfbuzz, cairo,
  fontconfig) and the Python interpreter build: not in the repository, so no
  file to hash. A Homebrew upgrade can move the render with the digest `fresh`.
- `pyproject.toml`: its dependency constraints are resolved into `uv.lock`,
  which is hashed; its other content does not reach the output.
- The `mag` binary (`render.rs` staging and the typst engine). What staging
  CHOOSES shows in the 57 hashed rows; non-input request fields do not. The
  typst engine is the leg under measurement, which the per-page ratchet exists
  to judge, so hashing it would make every typst change "stale".
- Licence/README files under `assets/fonts/` ARE included although they do not
  reach the output: the walk takes the directory whole rather than a curated
  list, so an edit there costs a rebase, never a silent pass.

## Commands and results

All from the worktree root. `T=/Users/franguijarro/.claude/jobs/7d99e27f/tmp`.
`$T/baseline-d0.json` is `baseline.json` with only `staged_input_digest`
replaced by the new digest, passed through `MAG_PARITY_BASELINE`; the committed
file is not modified.

| # | tree | command | exit | result |
|---|---|---|---|---|
| 0 | unaltered | `mag parity 010` (committed baseline `e48eb5c6...`) | 1 | refused: run `d92eca1d...`, baseline `e48eb5c6...` |
| 1 | unaltered | `MAG_PARITY_BASELINE=$T/baseline-d0.json mag parity 010` | 1 | `staged inputs: fresh (d92eca1d...; 57 edition inputs, 43 renderer files)`, verdict written; exit 1 is `tier S page_count: fail (56 vs 55)`, the typst leg, not the guard |
| 2 | unaltered | same, `--oracle-only` | 0 | fresh, all evaluated clauses pass |
| 3 | `printf ' ' >> weasyprint-a5.css` (one byte) | bare, d0 baseline | 1 | refused, run `757a230f...`; no `verdict.json` in the out dir |
| 4 | `Inter-Regular.ttf` copied over `SourceSerif4SmText-Regular.ttf` | bare, d0 baseline | 1 | refused, run `cb8590e3...` |
| 5 | `p { letter-spacing: 0.37pt; }` appended (WP-0.2k verifier's perturbation) | bare, d0 baseline | 1 | refused, run `a2754182...`; that render's `reader.pdf` has **60 pages** (pdfinfo) |
| 6 | restored (`git status --porcelain -- src uv.lock` empty) | `--oracle-only`, d0 baseline | 0 | re-rendered (no cache hit), fresh at `d92eca1d...` again |

Before each perturbed run the previous `verdict.json` was moved to `$T`, and
after runs 3 to 5 the out dir listed only `oracle-cache.json report
report.html`, so "no verdict" is observed, not assumed.

Control for run 5: the pre-WP algorithm (edition rows only), re-implemented in
Python over the 60-page render's own `request.json`, gives `e48eb5c6...`, equal
to the committed baseline. So the old code would have reported `fresh` on the
60-page render (as the WP-0.2k verifier measured at `b271911`); the refusal is
this WP's change.

Independent re-derivation of the new digest: a Python script (sorted
`target\x1fsha256` rows for the 57 inputs plus `renderer:<path>\x1fsha256` for
the walked files, joined by `\x1e`) produced
`d92eca1df8acd98237c74be376884ca5bfa90c0e38ab4e37b63816feec5f412d`, equal to
the comparator's, with 57 + 43 rows; the same script's edition-only digest is
still `e48eb5c6...`, so the corpus itself has not moved since WP-0.2k's seed.
Runs 1/2 and run 6 are two independent renders giving the same digest.

Cardinality summary of run 2 (oracle-only, so both legs are one render):
boxes 162 and 54 rotations, text 54 pages, tier G 54 pages, color 1733
entries, navigation 85 annotations (85 links, 0 outlines, 0 title, 0 lang),
glyphs 68530 in 1501 shows, display list 2189 vs 2189 elements, tier V 54
pages. The zeros for outlines/title/lang are now visible counts: those parts of
the navigation clause compared nothing on edition 010.

Lints and suite, `mag/`: `cargo fmt --check` exit 0,
`cargo clippy --all-targets -- -D warnings` exit 0, `cargo test` exit 0,
25 binaries, 260 passed, 0 failed. New unit tests `renderer_digest`: the walk
lists `.py`, css and nested font files and skips `__pycache__/` and `.DS_Store`;
a missing renderer input fails loud at hashing.

## The baseline digest: not rebased by this WP

The plan says the seeded digest "is rebased once, by a verifier, from a fresh
run", so `meta/verification/baseline.json` is untouched and still reads
`e48eb5c638a0f25bfdfbb5e26bc989d56c1ecbac3ef85f103e90ed1ac8aac5fa`. The digest
measured here for the unaltered tree at `0494017` + this diff is
`d92eca1df8acd98237c74be376884ca5bfa90c0e38ab4e37b63816feec5f412d`. **Until the
verifier rebases, every staged `mag parity 010` refuses as stale (run 0).**
Any commit touching `src/magazine/` or `uv.lock` between this landing and the
rebase moves the value; the verifier must take it from a fresh run.

## What is and is not proven

Proven: a one-byte stylesheet edit, a font substitution and the 56-to-60
letter-spacing perturbation each make a bare `mag parity 010` refuse with exit
1 and no verdict; the unaltered and the restored tree pass the guard at one
reproducible digest; the old algorithm would have passed the 60-page render.
Every evaluating clause in the summary now prints a compared count, and every
non-evaluating one prints a reason.

Not proven: that the included set is complete for the machine (system
libraries and interpreter are outside it, listed above); that a verdict's
`not_evaluated` reasons are exhaustive beyond the paths exercised (page-count
mismatch in run 1, raster bound, code blocks, critic). Nothing here says the
engines agree: run 1's typst leg is 55 pages against the oracle's 56.
