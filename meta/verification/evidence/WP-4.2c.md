# WP-4.2c evidence

Acts on WP-4.2.verify.md findings 1-3 and the cover.rs live-input note.

## What changed

- `mag/src/typeset/layout.rs`: `cap_warnings(layout)` returns one
  `WARNING: verbatim article past the page cap, rendering anyway: <id> (<n> pages, cap <c>)`
  line per verbatim article whose measured pages exceed `article_page_caps`,
  the same text `weasyprint_adapter.py:2522` prints. `report` puts them in its
  result under `warnings` (both the measure and the render_edition returns);
  `typeset/mod.rs` merges them across languages like `layouts`/`files`.
  Non-verbatim overruns stay refusals in the typst template
  (`template.rs` `the_page_cap_refuses_an_article_past_seven_reader_pages`).
- `mag/src/render.rs`: `close_typst(value, out_dir, out, err)` writes each
  warning to stderr and the next-step line to stdout; `run_typst` calls it with
  the real streams. `result.json` now carries `warnings`.
- `magazine.toml`: the `[render]` comment says typst is what mag picks when
  `engine` is absent.
- `mag/src/typeset/cover.rs`: `the_010_back_cover_rasterizes...` reads
  `mag/tests/repo_snapshot/editions/010/edition.yaml` (byte-equal to the live
  file at the time of the change, `cmp` exit 0).

## Warnings inventory (item 1)

Diff of the two legs on `mag render 010` at 383c093 (before the change):
typst stderr 0 bytes; weasyprint stderr = uv setup lines plus exactly one
`WARNING: verbatim article past the page cap, rendering anyway:
dario-amodei-we-must-pace-the-frontier (13 pages, cap 10)`. Stdout differs
only in paths, the typst `typst source tree`/`staged` lines and the review
image list. So the cap warning is the only warning 010 exercises.
`weasyprint_adapter.py:928` also prints `hyphen ladder: ...` lines; they did
not fire on 010 and the typst leg has no equivalent report (grep `ladder` in
`mag/src/typeset`: no match). Not ported: out of this WP's owned paths and no
edition exercises it; flagged for the orchestrator.

## Commands

| Command | Exit | Result |
|---|---|---|
| `mag render 010` before (typst default) | 0 | stderr empty; reader.pdf `6c03dda9...40bc4290` |
| `mag render 010 --engine weasyprint` before | 0 | stderr has the one cap WARNING |
| `mag render 010` after | 0 | stderr = the cap WARNING line, identical text to weasyprint; `next:` line printed; reader.pdf `6c03dda9...40bc4290` (unchanged; equal to WP-4.2.verify.md's sha); result.json `warnings` holds the line |
| `cargo fmt --check` / `cargo clippy --all-targets -- -D warnings` | 0 / 0 | clean |
| `cargo test --no-fail-fast` | 0 | 33 binaries, 967 passed, 0 failed |
| `env -u MAG_ORACLE PATH=nopy-bin cargo test --no-fail-fast` (WP-6.0c method; 1789 links, `command -v python3 python uv uvx` all empty) | 0 | 33 binaries, 967 passed, 0 failed |

## Injected defects (each restored after)

| Defect | Test | Result |
|---|---|---|
| drop the warning `writeln!(err, ..)` in `close_typst` | `the_typst_leg_prints_its_warnings_and_the_next_step` | FAILED |
| replace the next-step `writeln!(out, ..)` with `Ok(())` | same | FAILED |
| `count > cap` to `count >= cap` | `only_a_verbatim_article_past_its_cap_warns` | FAILED |
| warn for every mode, not only verbatim | same | FAILED |
| live `editions/010/edition.yaml` moved away | `the_010_back_cover_rasterizes...` | passed (no longer reads it) |

## What is and is not proven

PROVEN: the typst leg prints the weasyprint cap warning text on 010 and the
next-step line; the printing and the cap rule are each guarded by a test that
fails when removed; reader.pdf bytes unchanged; the cover test no longer
depends on live edition files.
NOT PROVEN: the one-line wiring in `layout::report` that puts `cap_warnings`
into the result is covered only by the live 010 run, not by a unit test.
Hyphen-ladder reporting is absent from the typst leg (see above). Editions
other than 010 not rendered.
