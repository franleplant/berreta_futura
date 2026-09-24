# WP-4.2b evidence: follow-ups to the typst flip

## What changed

- `mag/src/render.rs`: `select_engine` falls back to `Engine::Typst` when
  `magazine.toml` has no `[render] engine` key (was Weasyprint).
- `mag/src/render.rs`: both legs print one shared `next_step(pdf_dir)` line,
  which names `mag translate <run dir>`. The typst leg used to print a
  `mag parity` hint on `render_edition` and a `mag render --engine typst`
  hint on measure operations; it now prints what the weasyprint leg prints,
  in every operation, as the weasyprint leg does. The typst leg passes
  `<render dir>/<primary language>` (where its reader.pdf lives); the
  weasyprint leg keeps passing the render dir.
- Tests: `engine_defaults_to_typst_without_a_config_key` (no key -> typst,
  key weasyprint -> weasyprint, flag overrides) and
  `next_step_points_to_translate`.
- `docs/DESIGN_SYSTEM.md`, `docs/WEB_DEPLOY.md`: the stale TypeScript/XState
  and Python-renderer engine paragraphs now state typst as the default engine
  with `--engine weasyprint` as the rollback. Other lines untouched.

## Commands (worktree)

1. `cargo fmt --check` exit 0; `cargo clippy --all-targets -- -D warnings`
   exit 0; `cargo test` exit 0 (32 result lines, 955 passed, 0 failed; 953
   before per WP-4.2 evidence, plus the 2 new tests).
2. Positive control: with the fallback reverted to Weasyprint,
   `cargo test --bin mag engine_defaults` FAILED (1 failed); restored, passes.
3. `mag render 010` (release build, no `--engine`) exit 0, `totalPages=56`,
   `criticResult: "pass"`, and printed
   `next: read the PDF in editions/010/render-2026-09-24T15-14-44/en; ...
   \`mag translate <run dir>\` for the Spanish edition`. reader.pdf sha256
   `6c03dda9ae2714977522d6405e8e23eae6fefc7317c0fe66a7b6e9b440bc4290`, equal
   to the WP-4.2 value (WP-4.2.md, command 1).
4. No U+2014 in the three edited files (`grep -c` 0 each).

5. Rebased onto 511a9fb (WP-4.3, touches render.rs and typeset) and re-ran:
   fmt 0, clippy 0, `cargo test` 0 (32 result lines, 956 passed, 0 failed),
   `mag render 010` exit 0, 56 pages, critic pass, same next-step line,
   reader.pdf sha256 unchanged (`6c03dda9...40bc4290`).

## What is and is not proven

PROVEN: a config without the engine key selects typst; the typst leg's
render_edition output names `mag translate`; the 010 reader bytes did not
change.

NOT PROVEN: the measure operations' new next-step line was not exercised by a
live run (same function, covered by the unit test). The `mag parity` hint the
typst leg used to print is gone; parity is now reachable only from the docs
and the plan. The docs' remaining paragraphs (npm viewer, `RunEngine`,
`inputs/`/`durable/`) still describe a retired setup; out of scope here.
