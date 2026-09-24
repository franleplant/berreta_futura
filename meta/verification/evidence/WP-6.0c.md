# WP-6.0c: cargo test with no Python toolchain

Base: art_directed at fddd676. Worktree target dir. Python 3.9.6 (`/usr/bin/python3`,
the one `tools/nocomments.py` runs under), uv at `~/.local/bin/uv`.

## What changed

Every test that shelled out to Python now compares against a committed
expectation. `MAG_ORACLE=live` runs the old Python oracle, compares the port
against it where it did before, and asserts the committed file equals the live
output. `MAG_ORACLE=write` regenerates the file. Each run prints
`ORACLE MODE: committed expectation | live python | live python, rewriting`.
Shared helper: `mag/tests/oracle/mod.rs`.

| Test (source of the inventory: WP-6.0.md section 3) | Committed expectation |
|---|---|
| highlight.rs `tables_are_generated_from_the_locked_pygments` | sha256 of `mag/src/highlight/tables.json` pinned in the test (`adbcb031...a3a9`); live mode also regenerates via pygments and compares bytes |
| highlight.rs `every_corpus_block_matches_pygments` | `highlight_corpus_expected.json` (344 KB, 315 blocks): code and files in full, `html` as sha256, tokens as `[char count, class]` runs over the code (write mode asserts the runs cover the code exactly) |
| web_port.rs, 11 tests via `python()` / `python_web()` | `web_port_html_expected.json` (14 specs: html as sha256 of the stage-normalised html, assets and errors in full); `web_port_web_expected.json` (9 specs: sha256 per written file, or the refusal text). The stage path is replaced with `$STAGE` before hashing so the file holds in any worktree |
| critic_faults.rs `rust_decides_every_fault_by_the_rule` (already gated on `MAG_CRITIC_FAULTS_RENDER_DIR`) | `critic_faults_expected.json`: per fault the sha256 of the five staged inputs Python read, plus Python's result, issues and every probed cell. Committed mode asserts the freshly staged inputs hash to the recorded ones, so the verdict is bound to the exact bytes |
| critic/metrics.rs `thumbnail_matches_pillow...` | already pinned (`PINNED`); the Pillow call now runs only when `MAG_ORACLE` is set |
| nocomments.rs | Rust port of `tools/nocomments.py` inside the test (same targets, `nocomments.py` skip, suffix rules incl. pathlib's `suffix`, `#!/bin/sh` detection, universal newlines, pragma regex, shebang, `///` under clap derives, `__doc__` exemption for the module's first statement, docstrings only in `body` lists (not `else`/`finally`), output order = comments then docstrings in `ast.walk` order). Crafted cases in `nocomments_cases.txt`, expectation `nocomments_cases_expected.txt` (46 offenses). `tools/nocomments.py` is kept |

Grep for other callers: `grep -rnE '"uv"|python3|"python"|Command::new' mag/tests mag/src`
(exit 0): the only Python spawns were the ones above plus `render.rs:937`
(the weasyprint rollback, not reached by any test; not owned here). The
stripped-PATH baseline below confirms nothing else needed Python.

## Commands and results

PATH stripping: `mknopy.sh` symlinks every executable on `$PATH` into one
directory, skipping names `python*`, `uv`, `uvx`, `pip*`, `pydoc*`, `2to3*`,
`idle*` and any file whose first 200 bytes mention `python` (shebang scripts
such as `pyftsubset`); 1789 links.

| Command | Exit | Result |
|---|---|---|
| positive control: `env PATH=nopy-bin sh -c 'command -v python3 python uv uvx'` | 1 each | all four unreachable; `cargo`, `git`, `pdftoppm` resolve |
| positive control: `env PATH=nopy-bin MAG_ORACLE=live cargo test --test highlight tables` | 101 | `uv runs: Os { code: 2, NotFound }` |
| baseline before the change: `env PATH=nopy-bin cargo test --no-fail-fast` | 101 | 13 binaries failed: metrics thumbnail (10 binaries include metrics.rs), highlight 2, nocomments 1, web_port 11 |
| `MAG_ORACLE=write cargo test --test web_port / highlight / nocomments` | 0 | files written, Rust side already equal |
| `MAG_ORACLE=write MAG_CRITIC_FAULTS_RENDER_DIR=editions/010/render-2026-09-14T01-49-02/en cargo test --release --test critic_faults` | 0 | 69 passed |
| `MAG_ORACLE=live cargo test --no-fail-fast -- --nocapture` | 0 | 32 binaries ok; `ORACLE CHECK ... equals the live oracle` for highlight_corpus, web_port_html, web_port_web, nocomments_cases; pillow live in all 10 binaries |
| `MAG_ORACLE=live MAG_CRITIC_FAULTS_RENDER_DIR=... cargo test --release --test critic_faults` | 0 | `critic_faults_expected.json equals the live oracle` (staging is deterministic: input digests reproduced), 69 passed |
| `MAG_ORACLE=live MAG_NOCOMMENTS_ROOT=<git archive 0e54179^ of mag/src src/magazine tools> cargo test --test nocomments` | 0 | port equals the script on the current tree (TARGETS: `no comments`; wide targets incl. mag/tests, deploy, meta: 3 lines) and on the tree from before the comment purge: 1981 offense lines, identical text and order |
| `env -u MAG_ORACLE PATH=nopy-bin cargo test --no-fail-fast` | 0 | 957 passed, 0 failed, 32 binaries |
| `env PATH=nopy-bin MAG_CRITIC_FAULTS_RENDER_DIR=... cargo test --release --test critic_faults` | 0 | committed mode, 69 passed |
| `cargo test --no-fail-fast` (normal PATH) | 0 | 957 passed, 0 failed |
| negative controls (committed mode, stripped PATH): flip one hex digit of the `010` html digest; drop a line of `nocomments_cases_expected.txt`; bump one token run length in the corpus | 101 each | `edition_010_matches_html_edition_byte_for_byte`, `crafted_cases_flag_what_the_script_flags`, `every_corpus_block_matches_pygments` fail; files restored (`cmp` identical) and re-run green |
| `cargo fmt --check`, `cargo clippy --all-targets -- -D warnings` | 0 | clean |

## After rebasing onto aaa5362 (WP-6.0b and WP-4.2b landed meanwhile)

| Command | Exit | Result |
|---|---|---|
| `env -u MAG_ORACLE PATH=nopy-bin cargo test --no-fail-fast` | 101 | 964 passed, 1 failed, 33 binaries. The one failure is `sourcecodes.rs::committed_expected_files_are_what_the_python_tool_writes` (`uv runs: NotFound`), added by WP-6.0b in `mag/tests/sourcecodes*`, which this WP does not own. It runs whenever `tools/sourcecodes.py` exists, so it passes again once WP-6.1 deletes the tool, or when its owner gates it on `MAG_ORACLE` like the tests here |
| `cargo test --no-fail-fast` (normal PATH) | 0 | 965 passed, 0 failed |
| `MAG_ORACLE=live MAG_NOCOMMENTS_ROOT=... cargo test --test nocomments` | 0 | port equals the script: current tree wide targets 4 lines (adds `mag/tests/sourcecodes_oracle.py`), pre-purge tree 1981 |
| `cargo fmt --check`, `cargo clippy --all-targets -- -D warnings` | 0 | clean |

The Verify clause (stripped-PATH `cargo test` green) is therefore met for
every test this WP owns and missed by one test outside it.

## What is and is not proven

- Proven: with python3 and uv unreachable, `cargo test` passes, and each
  converted test still compares the Rust port against Python's output as of
  this commit (the live check above ran on the committed files).
- Digests prove equality, not correctness: where both engines agreed on
  something wrong before, the fixture pins the same thing.
- The fixtures freeze inputs taken from the repo at commit time (library
  sources, edition 010, its run manuscripts). A later capture or manuscript
  edit that changes those inputs will fail these tests until the fixture is
  regenerated, and once Python is gone it cannot be regenerated; the corpus
  test then only covers the 315 blocks it holds.
- critic_faults remains gated: without `MAG_CRITIC_FAULTS_RENDER_DIR` it
  skips, as before. Its fixture is bound to the untracked render
  `editions/010/render-2026-09-14T01-49-02/en`; any other render fails the
  input-digest assertion loudly.
- The nocomments port is a token-level reimplementation, not a Python parser.
  It agrees with the script on the crafted cases and on 1981 real offenses,
  but syntax outside those (for example `match` statements, which Python
  3.9's `ast.parse` rejects and so makes the script crash) is not exercised.
- `highlight_corpus_expected.json` is 344 KB; the code of each block is
  stored in full because the extraction (markdown-it plus the reader fold)
  exists only in Python.
