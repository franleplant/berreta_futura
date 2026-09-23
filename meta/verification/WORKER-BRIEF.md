# Worker brief (read this instead of the plan's Protocol section)

You own ONE work package (WP) of `meta/plans/typst-parity-and-rust-migration.md`.
Read your WP's section in that plan and the evidence files your brief names.
Do NOT read the plan's changelogs or the whole Protocol section; this page
is the protocol. Keep your context small: grep and read line ranges, not
whole large files.

## Rules that matter

1. Touch only the paths your WP owns (its "Owns:" line). Evidence goes to
   `meta/verification/evidence/<WP>.md` (verifiers: `<WP>.verify.md`).
2. Done = the WP's Verify clause executed and green, plus `cargo test` in
   `mag/` green, `cargo fmt --check` and `cargo clippy -D warnings` clean.
   Never `--no-verify`.
3. Evidence file, short: what changed, the exact commands run with their
   real exit status and the key numbers, and a `## What is and is not
   proven` section. Every number you cite from elsewhere names its source.
4. Equality is not correctness. If both engines agree on something wrong,
   say so; a test pins the CORRECT value, never "equals Python".
5. An absence claim (grep found nothing, test didn't fire) needs proof the
   command ran: exit status, plus a positive control where cheap.
6. Fail loud: if the target cannot be met, commit the measured gap in the
   evidence file and report it. Do not widen scope to make it pass.
7. Repo rules: no code comments (tools/nocomments.py), no U+2014, fewest
   readable lines.
8. Run long commands in the foreground. Never `rm -rf`, never `git
   checkout --` on paths you don't own. Use your worktree's own target dir.

## Working and landing

- Work in a fresh worktree:
  `git -C /Users/franguijarro/code/magazine worktree add --detach <scratch>/<wp> art_directed`
- Commit there (the pre-commit hook runs fmt/clippy/ruff/nocomments).
- Land by fast-forward FROM THE MAIN TREE, which keeps its index honest:
  `git -C /Users/franguijarro/code/magazine merge --ff-only <your-sha>`
  If it refuses, the branch moved: `git rebase art_directed` in your
  worktree, re-run the tests if the new commits touch anything you depend
  on, and retry. Never edit files in the main tree directly.
- Then `git worktree remove --force <your worktree>` and report.

## Report (your final message, <= 15 lines)

WP id, landed sha (or "not landed" and why), verify status, anything the
orchestrator must act on (defects found in other areas, blockers). No
restating of this brief.
