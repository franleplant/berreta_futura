# WP-6.0c verify

Verdict: **ACCEPTED**.

Tip `41ea889`, worktree `<scratch>/v6`, its own target dir.

## Replay

PATH stripped with WP-6.0c's `mknopy.sh` into a fresh `<scratch>/v6-nopy`
(1789 links). Controls: `command -v` finds none of python3, python, uv, uvx;
cargo, git, pdftoppm, mutool resolve. No test spawns Python by absolute path
(`grep -rnE '/usr/bin/python|homebrew/bin/python|\.venv/bin|local/bin/uv'`
over `mag/src mag/tests`: no match), so PATH stripping covers every spawn.

| Command | Exit | Result |
|---|---|---|
| positive control: `env PATH=v6-nopy MAG_ORACLE=live cargo test --test highlight tables` | 101 | `uv runs: Os { code: 2, kind: NotFound }` |
| `env -u MAG_ORACLE PATH=v6-nopy cargo test --no-fail-fast` | 0 | 33 result lines, 965 passed, 0 failed, 0 ignored |
| `MAG_ORACLE=live cargo test --no-fail-fast -- --nocapture` (Python present) | 0 | 965 passed, 0 failed; `ORACLE MODE: live python` x4, `live pillow` x10; `ORACLE CHECK ... equals the live oracle` for highlight_corpus, web_port_html, web_port_web, nocomments_cases; nocomments port agrees with the script (4 lines) |

## Injected defect

In the Rust nocomments port (`tests/nocomments.rs:176`) the shebang exemption
was widened from line 1 to any line. Under the stripped PATH,
`crafted_cases_flag_what_the_script_flags` FAILED. Restored.

## Residual (pre-existing, not this WP's)

"100% pass" includes env-gated tests that return early and report ok: with no
env set, the live-oracle run printed 10 skip lines (critic_faults, critic_text,
critic_inspect, critic_rules x2, package x3, layout, typeset root). They are declared, but a green count does not mean
they compared anything.
