# WP-4.2 verify

Verdict: **ACCEPTED**, with two defects outside the Verify clause (below).

Tip `41ea889` (art_directed), detached worktree `<scratch>/v6`, release build.

## Replay

| Command | Exit | Result |
|---|---|---|
| `mag render 010` (committed magazine.toml, no flag) | 0 | log line 6 `typst source tree (en, hyphenation ...): 10 files, 68758 characters`; `totalPages=56`; `criticResult: "pass"`; `next: read the PDF in editions/010/render-2026-09-24T16-56-39/en; ... mag translate <run dir> ...`. Render dir has a `typst/` tree, no uv/CPython lines in the log. reader.pdf sha256 `6c03dda9...40bc4290`, equal to WP-4.1.md `b_reader_sha256 (typst)` |
| `mag render 010 --engine weasyprint` | 0 | log shows `Using CPython 3.12.11` and the uv build of magazine-compiler (so the Python leg ran); `totalPages=56`, `criticResult: "pass"`, next step printed. reader.pdf `3fb1c8e2...ec8e41` |

Engine identification: the typst leg is the only one that logs `typst source tree`
and writes `render-*/typst/`; the weasyprint leg is the only one that spawns uv.

## Injected defect

`select_engine` rewritten so the config key wins over `--engine`.
`cargo test --bin mag engine_defaults` FAILED at render.rs:984 (flag `typst`
over config `weasyprint`). Restored, worktree clean.

## Findings for the orchestrator

1. `magazine.toml` `[render]` comment still says weasyprint "is also what mag
   picks when this key is absent". Since WP-4.2b the fallback is typst
   (`render.rs:245`, confirmed live in WP-4.2b.verify.md). Stale config doc.
2. The weasyprint leg prints `WARNING: verbatim article past the page cap,
   rendering anyway: dario-amodei-we-must-pace-the-frontier (13 pages, cap 10)`;
   the typst default prints nothing about it (`grep -i "warn\|cap"` on the typst
   log: no match). The flip dropped the only cap signal a render emits
   (QUEUE.md line 206 already notes neither leg refuses).
3. The "next step printed" property has only a unit test on the string
   (`next_step_points_to_translate`); `grep -rln "next: read the PDF"` in
   `mag/tests mag/src` finds only render.rs, so deleting the `println!` at
   render.rs:674 would pass `cargo test`. Proven live here, not guarded.

## What is and is not proven

PROVEN at the tip: default config renders 010 through typst, critic pass, next
step printed, bytes equal the gate; weasyprint rollback renders. NOT PROVEN: any
edition other than 010 (as WP-4.2 states).
