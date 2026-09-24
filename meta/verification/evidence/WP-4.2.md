# WP-4.2 the flip

Base `cfcff9a` (art_directed). Worktree build: `cargo build --release`.

## Gate

WP-4.1 verdict hash in `meta/verification/evidence/WP-4.1.md`: normalized
verdict sha256 `172444721bb321f4d0a55a7b6431ec425c4a283760dae518bb830d580313c3ab`
on two clean-checkout runs, Gate: PASS. Present, so the flip proceeds.

## What changed

- `magazine.toml`: `[render] engine = "typst"` (was `"weasyprint"`); the
  comment now names typst as the default and weasyprint as the rollback.
  The code fallback when the key is absent stays `Weasyprint`
  (`mag/src/render.rs` `select_engine`, not owned by this WP).
- `CLAUDE.md`: the pipeline bullet says `mag render` typesets through Typst
  in Rust, with `src/magazine/` kept as the rollback; the verification line
  says "Python rollback".
- `docs/RENDERER_MIGRATION.md`: rewritten as the current transition record
  (the old text described the deleted TypeScript engine).
  `docs/ARCHITECTURE.md`: the `mag render` bullet, the Python section header,
  and the verification paragraph now describe the Typst default; one
  pre-existing U+2014 removed.

## Commands (worktree, release build)

In-flight edition: the highest-numbered `editions/NNN` with a `plan.yaml` is
**010** (`ls editions/*/plan.yaml`: 004..010, no 011). So the in-flight
render is the 010 render; 010 declares only `en`.

1. `mag render 010` (no `--engine`) exit 0. Log prints
   `typst source tree (en): 10 files, 68758 characters`, `totalPages=56`,
   `criticResult: "pass"`, and the next step (`next: read the PDF in
   editions/010/render-2026-09-24T14-43-30/en; ... mag parity 010 ...`).
   reader.pdf sha256 `6c03dda9...40bc4290`, equal to WP-4.1's typst
   `b_reader_sha256`.
2. `mag parity --adhoc 010` exit 0. Tier S: page_count 56 vs 56, critic pass
   (1999 leaves, 0 differ), boxes pass (168, 0 mismatches), text pass (56
   pages), color pass (59252), navigation pass (85 links, 51 outlines).
   Tier E (informational in ad hoc): glyph positions pass (59073 glyphs, 0
   violations), display list pass (59304 vs 59304). G max dy 0.006 pt. V
   worst page fraction 0.000336. `code_blocks` and `E raster`
   not_evaluated by design (as in WP-4.1). Normalized verdict sha256 (drop
   `inputs.a_reader_sha256`) `74ec197ff3258bae4ce6aa3cb077933a2081c102dbe66b91cb429a35faa2f3b5`.
   No template gap exposed.
3. Rollback control: `mag render 010 --engine weasyprint` exit 0,
   `totalPages=56`, `criticResult: "pass"`, next step printed.
4. `cargo fmt --check` 0; `cargo clippy --all-targets -- -D warnings` 0;
   `cargo test` 0 (32 result lines, 953 passed, 0 failed, 0 ignored).

## What is and is not proven

PROVEN: with the committed config, `mag render 010` selects typst without a
flag, passes its critic, prints the next step, and produces the same reader
bytes the WP-4.1 gate measured. `--engine weasyprint` still renders 010 as
the rollback. Ad hoc parity on 010 passes Tier S with Tier E clean.

NOT PROVEN: any edition other than 010 on the typst default (010 is the only
in-flight edition); Spanish on the typst default (010 is en-only); the
shipping hyphenation setting (WP-4.3). A checkout whose `magazine.toml`
lacks the key still falls back to weasyprint in code. The typst leg's
next-step line does not mention `mag translate`, which the weasyprint leg
does; harmless for 010, a gap for a bilingual edition.
