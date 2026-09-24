# WP-6.0d: tests independent of Python and of the live library/editions

Base: art_directed at 03771ac, detached worktree, its own `mag/target`.

## What changed

1. `mag/tests/sourcecodes.rs`: `committed_expected_files_are_what_the_python_tool_writes`
   now runs only when `oracle::live()` (`MAG_ORACLE=live|write`). Before, it ran
   whenever `tools/sourcecodes.py` existed. It still only compares in write mode
   and does not rewrite anything.
2. `mag/tests/typeset_fixtures/corpus/editions/906/source-codes/codes.json`
   was regenerated with `mag source-codes 906`, run in a scratch copy of the
   corpus because mag needs a `./prompts` dir. Only `codes.json` changed (the
   `example.invalid/d` entry now comes first). The two SVGs were already equal.
   The result is byte-equal to `mag/tests/sourcecodes_expected/906/`.
3. Snapshot of the live inputs. Text inputs are copied into
   `mag/tests/repo_snapshot/`, which has the repo layout. Binary inputs that
   are too large to copy are pinned by sha256 in
   `mag/tests/pinned_inputs.sha256` (`shasum -a 256 -c` format, repo-relative
   paths). They are read from the repo only through `oracle::pinned(test, path)`,
   which fails with `<test>: pinned input <path> changed (found X, pinned Y);
   its committed expectation was recorded from the pinned bytes`.
   The new helpers `snapshot()`, `pinned_paths()` and `pinned()` live in
   `mag/tests/oracle/mod.rs`.

| Test | Input before | Input now |
|---|---|---|
| web_port.rs (19 tests, both expectation files) | hard-link stage of all of `library/sources` (49 MB), `editions/010/art` (396 MB), `editions/010/source-codes`, `edition.yaml` and the run finals | stage = snapshot (96 record.yaml, the claude-of-duty article.md the wfx extracts read, 3 figure PNGs, 010 edition.yaml, the 9 run finals at their manuscript paths, the 10 source-code files) + the 24 pinned art PNGs (90,081,431 bytes; the web edition copies them byte for byte, so the pin digest is the value the expectation holds) |
| sourcecodes.rs, 008 and 010 | `..` (live repo) | snapshot (`editions/008/edition.yaml`, `editions/010/edition.yaml`, records) |
| cover_text.rs `live_010` | `editions/010/edition.yaml` | snapshot copy |
| model_records.rs (3 tests on `library/sources`) | live `library/sources` | snapshot's 96 record.yaml |
| critic_metrics.rs figures + jpeg_figures | live library media | figures (3 PNGs, 401,883 B) from the snapshot; the 43 JPEGs (8,384,735 B) pinned |
| cover_modes.rs, cover_pdf.rs, cover_footer_caption.rs | live cover PNG | pinned (`cover-wildcard-sign-punched-v3.png`, 3,602,052 B) |

Added bytes: snapshot 577,777 B in 122 files (`du` 956 KB), pins 9,981 B (67 lines).

## Commands and results

| Command | Exit | Result |
|---|---|---|
| `mag source-codes 906 --check` on the stale committed fixture (scratch copy) | 1 | `content differs: codes.json` |
| `mag source-codes 906`, then `--check` | 0, 0 | `3 files reproduce byte-for-byte` |
| `uv run python <copy>/tools/sourcecodes.py 906 --check` on the regenerated tree / on the stale tree | 0 / 1 | `3 files reproduce byte-for-byte` / `content differs: ['codes.json']` |
| 906 staged into editions/ + library/sources (as WP-5.12), `mag render 906 --engine weasyprint --no-model`, `--engine typst --no-model` (release) | rendered | W = render-2026-09-24T16-33-05, T = render-2026-09-24T16-33-24 (the status was read through a pipe; parity below consumed both) |
| `mag parity 906 --pre-rendered W T` (en) | 0 | glyphs 3144 violations 0, display list 3188/3188 (same numbers as WP-3.10.md) |
| `mag parity 906 --pre-rendered W T --lang es` | 0 | glyphs 3513 violations 0, display list 3557/3557 |
| `mag parity --adhoc 906 --lang es` | 0 | display list 3557/3557; staging moved back out afterwards |
| `MAG_ORACLE=live cargo test --test web_port --test sourcecodes -- --nocapture` | 0 | `web_port_html_expected.json equals the live oracle`, `web_port_web_expected.json equals the live oracle`, sourcecodes python vs expected OK. So Python reading only the snapshot + pins reproduces every committed expectation, which means the snapshot holds its whole input set |
| independence: retitle 010 and 008 `edition.yaml`, change an 010 article author, retitle and re-URL one 010 record, add `library/sources/zz-new-capture/`; run web_port, sourcecodes, cover_text, model_records | 0 | all pass with this WP's tests |
| same mutations, with this WP's `mag/` changes stashed (the old tests) | 101 | cover_text 1, model_records 3, web_port 13, sourcecodes 2 failures. So the old tests did read those inputs |
| pin control: append one byte to the cover PNG; `cargo test --no-fail-fast --test cover_modes --test web_port` | 101 | 12 + 13 failures, each with the `pinned input ... changed (found dd4442f7..., pinned 48750f4a...)` message; restored (`cmp` equal), all live files restored, `git status` clean outside `mag/` |
| positive control: `env PATH=nopy-bin MAG_ORACLE=live cargo test --test sourcecodes committed_expected_files` | 101 | `uv runs: NotFound` (python3, python, uv, uvx unreachable; cargo, git resolve; nopy-bin built by WP-6.0c's method, 1789 links) |
| `env -u MAG_ORACLE PATH=nopy-bin cargo test --no-fail-fast` | 0 | 33 binaries, 965 passed, 0 failed |
| `cargo test --no-fail-fast` (normal PATH) | 0 | 33 binaries, 965 passed, 0 failed |
| `cargo test --test critic_metrics` before and after | 0 | 106 s both times: hashing the pins costs nothing measurable |
| `cargo fmt`, `cargo clippy -q --all-targets -- -D warnings` | 0 | clean |

## What is and is not proven

- Proven: `cargo test` passes with no python3 or uv on PATH. The listed
  tests no longer read the live `library/` or `editions/` text: when those
  files change, these tests still pass, and the old tests failed on the
  same change.
- The 24 art PNGs, the 43 JPEGs and the cover PNG are still read from the live
  repo. The pin binds them. If one is edited or deleted, a clear failure names
  the test and the path. It is not a bare mismatch. Deleting `editions/010/art`
  or those library media would still break these tests, and after WP-6.1 the
  expectation cannot be regenerated. The files would have to be restored.
- Snapshot equality to the live repo holds only as of 03771ac. From here on
  they are meant to drift apart.
- Not changed, outside `mag/tests/**`: `mag/src/typeset/cover.rs:684`, a unit
  test that still reads the live `editions/010/edition.yaml`. `critic_faults`
  stays gated on the untracked `MAG_CRITIC_FAULTS_RENDER_DIR` render and already
  asserts its input digests (WP-6.0c). `highlight` reads the library only in
  live mode. The committed corpus holds the code in full.
- The 906 parity reruns show that the corrected `codes.json` keeps both legs
  identical. They do not show that the typst leg reads the code order, because
  both legs read the same file.
