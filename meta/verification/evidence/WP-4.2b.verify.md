# WP-4.2b verify

Verdict: **ACCEPTED**.

Tip `41ea889`, worktree `<scratch>/v6`, release build.

## Replay

| Command | Exit | Result |
|---|---|---|
| magazine.toml with the `engine = "typst"` line deleted (`grep -c '^engine'` = 0 as control), `mag render 010` | 0 | log `typst source tree (en, ...)`, no uv/CPython, `totalPages=56`, `criticResult: "pass"`. magazine.toml restored, `git status` clean |
| `mag render 010` (default) and `--engine weasyprint` | 0, 0 | both print the same `next:` line naming `mag translate <run dir>`; typst passes `render-.../en`, weasyprint the render dir (see WP-4.2.verify.md) |

## Injected defect

Config-over-flag precedence swap in `select_engine` (render.rs): caught by
`engine_defaults_to_typst_without_a_config_key` (1 failed). This is a different
defect from WP-4.2b's own control (fallback reverted to weasyprint).

## Residual

The magazine.toml comment contradicts the new fallback (WP-4.2.verify.md,
finding 1): WP-4.2b changed the code without the config text that describes it.
The measure operations' next-step line and the render_edition `println!` are
unguarded by any test (WP-4.2.verify.md, finding 3).
