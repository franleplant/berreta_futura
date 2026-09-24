# WP-6.0b source codes in Rust

Base: `art_directed` `3b48029`, detached worktree `.../tmp/wp60b`, its own
`mag/target`. segno 1.6.6 (`.venv`), qrcodegen 1.8.0, rqrr 0.11.0 (dev only).

## What changed

- `mag/src/sourcecodes.rs` (new): the port of `tools/sourcecodes.py`.
  `mag source-codes NNN` writes `editions/NNN/source-codes/` (one web SVG per
  source plus `codes.json` with the print fit) and prints `next: mag render NNN`;
  `--check` regenerates in memory and compares, like the Python `--check`.
- The steps before render now lead to it: `mag art` prints
  `3. mag source-codes NNN` before `4. mag render NNN`, and `mag produce`
  lists it as step 4 (after picking opener art, since the room depends on
  `opener_art`). The codes are a pure function of edition.yaml plus the
  records, so the step belongs after the picks.
- QR route. WP-5.5a measured that segno writes a non-ISO extra zero byte at a
  codeword boundary (`segno/encoder.py:330`), and the plan's fallback (a)
  names that deviation as a requirement. The port owns only the data
  codewords: it builds segno's bitstream (mode, count, data, terminator,
  segno's `8 - len % 8` padding, pads, truncated to capacity) and hands it
  to `qrcodegen::QrCode::encode_codewords`, which does the Reed-Solomon ECC, the
  interleaving and the placement. The mask is chosen by segno's own penalty
  (N1 to N4, N3 checking only the 1:1:3:1:1 at unit width with 4 light or edge
  modules on one side) on the matrix with format, version and dark-module cells
  light, as segno evaluates it. Version and boosted level come from
  `encode_segments_advanced(..., boostecl=true)`, which follows the same rule as
  segno's boost. Capacity comes from qrcodegen's own table through its
  `DataOverCapacity` error.
- The SVG writer and `codes.json` writer (sorted keys, indent 2,
  `ensure_ascii`) are reproduced byte for byte.
- `mag/tests/sourcecodes.rs`, `mag/tests/sourcecodes_oracle.py` (drives the
  Python `generate` with `ROOT` set to a given root), and
  `mag/tests/sourcecodes_expected/{008,010,900..906}/` (the Python output,
  committed so the test still means something after Python is deleted).

## Commands and results

- Oracle generation: `uv run python .../gen.py <root> <edition> <dest>` for 008,
  010 (repo root) and 900-906 (`mag/tests/typeset_fixtures/corpus`). Every run
  exited 0 with 0 print declines. 36 files in total: 008 has 8, 010 has 10, and
  the fixtures have 18.
- `cargo test --test sourcecodes`: 6 passed, 0 failed.
  - `rust_writes_every_committed_expected_file_byte_for_byte`: Rust `build` against
    all 9 expected trees. The file set and every byte are equal.
  - `committed_expected_files_are_what_the_python_tool_writes`: the Python tool is
    shelled into a temp dir and compared against the same trees. It skips once
    `tools/sourcecodes.py` is gone.
  - `segno_deviation_adds_a_zero_byte_at_a_codeword_boundary`: for
    `cursor.com/blog/third-era` (v2-M, 28 data codewords), the codewords end
    `26 10 00`, with `00` where ISO puts `EC`. The resulting matrix differs from
    qrcodegen's spec-correct one at the same version, level and mask.
  - `print_declines_above_78_characters_at_the_illustrated_room`: 78 chars give 41
    modules, 79 give `null` at 41.0 pt, and 79 still fit at 55.5. The Python
    `fitted` gives the same answers: 77 and 78 fit, 79 is None.
  - `every_code_decodes_to_its_payload`: this one is correctness, not equality.
    Every payload in the 9 trees, at all four levels, is decoded by an independent
    decoder (rqrr) back to its payload: 112 decodes, all equal.
  - `payload_strips_scheme_and_www_only`, including the non-ASCII refusal.
- Negative control: one byte edited in an expected 008 SVG makes both oracle
  tests fail with `content differs: source-code-inference-will-eat-the-world-...svg`.
  After the restore, `cmp` matches the oracle again.
- `./mag/target/debug/mag source-codes 010 --check` prints
  `10 files reproduce byte-for-byte` and exits 0.
- `cargo fmt --check`, `cargo clippy -q --all-targets -- -D warnings`: clean.
  Full `cargo test -q` in `mag/`: exit 0, 33 test binaries, 962 passed, 0
  failed. `python3 tools/nocomments.py`: exit 0.

## Finding for the orchestrator

The committed fixture `mag/tests/typeset_fixtures/corpus/editions/906/source-codes/`
is **stale**: current `tools/sourcecodes.py` output for 906 lists
`example.invalid/d` first where the committed file lists `example.invalid/a`,
so `tools/sourcecodes.py 906 --check` would fail on it. Fixtures 900-905 and
010 match the Python output byte for byte. The expected tree for 906 is
Python's fresh output. The fixture corpus is not this WP's path, so it was
left as is. Its owner should regenerate it with `mag source-codes`, run from
the corpus root, or confirm that the typst leg does not depend on the stale
order.

## What is and is not proven

- Proven: byte-identical output to `tools/sourcecodes.py` for 008, 010 and
  900-906 (36 files), and that every matrix the port draws is a valid QR code
  that decodes to its payload.
- Proven only by construction, not by corpus: the numeric and alphanumeric
  segment paths (every real payload is byte mode) and the capacity-truncation
  branch (no payload fills a symbol exactly). The mask penalty is exercised
  across 28 payloads × 4 levels × 8 masks through the byte-equal matrices.
- Deliberately not ported, and failing loud instead: non-ASCII payloads. segno
  falls back from latin-1 to Shift_JIS to UTF-8, and Shift_JIS or Kanji mode
  would need tables. Here the port is stricter than its oracle. URLs are ASCII by
  RFC 3986, so this matters only for IRIs.
- The Python `_opener_credit_code` 55.5 vs 41.0 inconsistency (plan, WP-5.5a)
  is untouched, since this WP reproduces `codes.json` only.
