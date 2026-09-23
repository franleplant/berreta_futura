# WP-0.2l verification

## Verdict

**ACCEPTED.** Every Verify clause replayed green at the `art_directed` tip
`a0e2085`, three tampers the worker did not try were refused, and the digest
`d92eca1d...` was re-derived by an independent enumeration. `baseline.json`'s
`staged_input_digest` is rebased in this commit (below).

## Base

Detached worktree at `a0e2085` (WP-0.2l landed on top of WP-2.2c). No commit
between the worker's base `0494017` and `a0e2085` touches `src/magazine/` or
`uv.lock` (`git diff --stat 0494017 a0e2085 -- src uv.lock` empty), so the
worker's digest was expected to survive, and it did.

`vbaseline.json` below is `baseline.json` with only `staged_input_digest`
replaced by `d92eca1d...` (diff: one line), passed through
`MAG_PARITY_BASELINE`. Restores used saved copies, not `git checkout`; after
each restore `git status --porcelain -- src uv.lock` was empty.

## Runs

| # | tree | command | exit | result |
|---|---|---|---|---|
| 0 | unaltered | bare `mag parity 010`, committed baseline | 1 | refused: run `d92eca1d...`, baseline `e48eb5c6...` |
| 1 | unaltered | bare, vbaseline | 1 | guard passed (the refusal line is absent, the typst leg rendered); then `tracing page 3 of .../render-2026-09-23T20-02-16/en/reader.pdf: operator cs: unsupported operator cs`, no verdict |
| 2 | unaltered | `--oracle-only`, vbaseline | 0 | `staged inputs: fresh (d92eca1d...; 57 edition inputs, 43 renderer files)`, all evaluated clauses pass; counts equal the worker's run 2 (162 boxes/54 rotations, 54 text pages, 1733 colour entries, 85 annotations, 2189 vs 2189 elements, tier G and V 54 pages) |
| t1 | **new**: one `\n` appended to `src/magazine/weasyprint_adapter.py` (a Python adapter file, no output effect) | bare, vbaseline | 1 | refused, run `383edbcf...` |
| t2 | **new**: one space appended to `uv.lock` (survived the run: file tail `]\n `, so uv did not rewrite it) | bare, vbaseline | 1 | refused, run `bba8e6f6...` |
| t3 | **new**: untracked `src/magazine/zz_stray.txt` | bare, vbaseline | 1 | refused, run `dc5e78b8...` |
| t4 | replay: one byte appended to `weasyprint-a5.css` | bare, vbaseline | 1 | refused, run `757a230f...` (equal to the worker's run 3) |
| t5 | replay: `Inter-Regular.ttf` copied over `SourceSerif4SmText-Regular.ttf` | bare, vbaseline | 1 | refused, run `cb8590e3...` (equal to the worker's run 4) |
| 3 | restored, plus junk `src/magazine/__pycache__/zz_control.pyc` (negative control for the skip) | `--oracle-only`, vbaseline | 0 | re-rendered (new dir `render-2026-09-23T20-11-43`, not a cache hit), fresh at `d92eca1d...` |

Before each run the previous `verdict.json` was moved aside; after t1 to t5 the
out dir `output/parity/010` listed only `oracle-cache.json report report.html`,
so "no verdict" is observed. After run 3 it listed `verdict.json` again
(positive control).

The 56-to-60 letter-spacing perturbation was not replayed: t4 and t5 reproduce
the worker's digests exactly, and a letter-spacing edit is the same class (a
stylesheet byte change) as t4.

## Independent digest derivation

A separate script (`vdigest.py` in the job scratch) enumerates the renderer set
with `git ls-files src/magazine uv.lock` instead of the comparator's directory
walk, hashes each `sourcePath` of the render's `request.json`, sorts
`target\x1fsha256` and `renderer:<path>\x1fsha256` rows and joins by `\x1e`:

- both render dirs of this verification: 57 + 43 rows, digest
  `d92eca1df8acd98237c74be376884ca5bfa90c0e38ab4e37b63816feec5f412d`, equal to
  the comparator's; edition-only rows give `e48eb5c6...`, the committed seed.
- with t2's tampered `uv.lock`: `bba8e6f6...`, equal to the comparator's t2.

The two enumerations agree only because the tree has no untracked non-dot
files under `src/magazine/`; t3 shows the walk counts untracked files, which
errs toward refusal.

## Typst leg page count at the tip

Bare `mag parity 010` at `a0e2085` does not print a summary (run 1: the tracer
bails on `cs` before any tier is scored). Measured directly with `pdfinfo`:
typst leg `render-2026-09-23T20-02-16/en/reader.pdf` **56 pages**, oracle
`render-2026-09-23T20-00-10/en/reader.pdf` **56 pages**. So WP-2.2c's 56 = 56
holds, but no comparator verdict states it. The `cs` refusal is the defect
WP-2.2c's evidence already reports (typst-pdf fills through `/c0 cs ... scn`,
`streams.rs:327` supports only `rg`; owner named there as WP-3.0g, to be
scheduled ahead of WP-3.1). Not a WP-0.2l defect.

## Lints and suite at `a0e2085`, `mag/`

`cargo fmt --check` exit 0, `cargo clippy --all-targets -- -D warnings` exit 0,
`cargo test` exit 0, 25 binaries, 267 passed, 0 failed (267, not the worker's
260: WP-2.2c's tests landed in between).

## Baseline rebase

`meta/verification/baseline.json` `staged_input_digest`:
old `e48eb5c638a0f25bfdfbb5e26bc989d56c1ecbac3ef85f103e90ed1ac8aac5fa`,
new `d92eca1df8acd98237c74be376884ca5bfa90c0e38ab4e37b63816feec5f412d`,
measured from fresh runs 2 and 3 at `a0e2085`. No other field changed.

## What is and is not proven

Proven: at the tip, edits to a Python adapter file, `uv.lock`, the stylesheet,
a font, and an untracked file added to the package each make a bare
`mag parity 010` refuse with exit 1 and no verdict; `__pycache__` content does
not move the digest; the unaltered and restored trees pass the guard at one
reproducible digest, which an independent enumeration reproduces.

Not proven: the system libraries and interpreter the worker lists as outside
the digest remain outside it. A bare run cannot yet produce a verdict at the
tip (the `cs` tracer defect), so the guard's "fresh" line on a bare run is
inferred from run 1 reaching the tracer, and observed directly only in
`--oracle-only` runs.
