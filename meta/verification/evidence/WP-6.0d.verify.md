# WP-6.0d verify

Verdict: **ACCEPTED**; live reads remain, listed below.

Tip `41ea889`, worktree `<scratch>/v6`.

## Replay

| Command | Exit | Result |
|---|---|---|
| `env -u MAG_ORACLE PATH=v6-nopy cargo test --no-fail-fast` | 0 | 965 passed, 0 failed (WP-6.0c.verify.md) |
| `env PATH=v6-nopy MAG_ORACLE=live cargo test --test sourcecodes committed_expected` | 101 | `uv runs: NotFound`: the gated Python test really runs in live mode |
| same test, committed mode, stripped PATH | 0 | 2 passed (skips the Python leg as designed) |
| `MAG_ORACLE=live cargo test --no-fail-fast` | 0 | 965 passed |

## Live-record independence

Edited `library/sources/the-third-era-of-ai-software-development-7395f18d/record.yaml`
(title, author, url; the record is in the 010 edition and in the snapshot).
Positive control: `mag source-codes 010 --check` exit 1 (`content differs` on
that SVG and `codes.json`), so the edit is visible to live consumers.
Full `cargo test --no-fail-fast` (not only the four files WP-6.0d ran): exit 0,
33 result lines, 965 passed, 0 failed. Record restored, `git status` clean.

## Injected defect (a live edit a test must catch)

Changed 010's `cover.back_text` first sentence in the live `editions/010/edition.yaml`.
`cargo test --bin mag the_010_back_cover`: FAILED. This confirms the named
residual `mag/src/typeset/cover.rs:684` still reads live data. Restored.

## Live-data reads left in default tests (fixing nothing)

Found by `grep -rnE` over `mag/tests/*.rs`, `mag/tests/oracle`, `mag/src` for
`editions/`, `library/`, `src/magazine`, `CARGO_MANIFEST_DIR ... ".."`:

1. `mag/src/typeset/cover.rs:684`: live `editions/010/edition.yaml` (proven above).
2. Live binaries bound by `oracle::pinned` (fail loudly with the path, but still
   read from the live tree and die if deleted): `editions/010/art/**` 24 PNGs
   (web_port), the cover PNG `editions/010/art/rounds/2026-09-13T01-40-20/cover-wildcard-sign-punched-v3.png`
   (cover_modes.rs:109, cover_pdf.rs:125, cover_footer_caption.rs:110), and the
   43 library JPEGs (critic_metrics.rs:23).
3. Python-side files that WP-6.1 plans to delete, read unconditionally:
   `src/magazine/render_critic.py` (critic_rules.rs:1098, 1396, 1525, parsed
   for issue sites) and `src/magazine/assets/weasyprint-a5.css`
   (highlight.rs:32, `colour_rules`). These will break `cargo test` when
   `src/magazine` goes; WP-6.1 must move or snapshot them.
4. `src/magazine/assets/fonts` read by many tests (model_doc.rs:20,
   cover_pdf.rs:130, content.rs, layout.rs, template.rs, estimate.rs,
   text_shim.rs): repository assets, not captured data, but they live under the
   directory WP-6.1 deletes.
5. Env-gated only (not default): critic_faults (untracked render dir),
   critic_rules/inspect/text, impose, model_doc, model_manifest MAG_* oracles.
