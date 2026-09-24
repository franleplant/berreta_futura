# WP-5.1h part 1 verification

Verdict: **ACCEPTED**

Verified at art_directed `b7f7791` (contains `3857334`), fresh worktree.
Throwaway probe tests were appended to test files and reverted; no code
changed.

## Label classification (both engines wrong)

- Python through `parse_publication_document` and the
  `html_edition._content_label` expression: `label: []` -> tuple, shown
  `'()'`; `{}` -> mappingproxy `'{}'`; `[a, 1]` -> `"('a', 1)"`; `!!null`
  and `~` -> None, UI fallback. The `_freeze` tuple is confirmed as the
  source of `()`.
- Rust `shared::content_label` (the path typeset still uses): `[]` ->
  `"[]"`, `{}` -> `"{}"`, `[a, 1]` -> `"['a', 1]"`.
- Agreed: neither is a section label; each prints container syntax on a
  reader page. "Both engines wrong" is the right class and refusing is the
  correct value. Typeset still prints `[]` until part 2 (disclosed).
- `serde_yaml` on `label: !!null` and `label: !!null ''`: Err `invalid
  value: string "", expected null`; `label: ~` Ok(Null). The Rust refusal
  is real; its fix site (`model/doc.rs`) is outside this WP, correctly
  reported.

## Strict decode: my own bad streams

Tokens `>>` and `}` (the worker used `@` and `]`):
- At tip, `pdf_text`: both Err `page 1: the content stream holds a token
  lopdf cannot parse`. `impose` (renamed-page reader): both Err `a page
  content stream holds a token lopdf cannot parse`.
- Defect injected: both sites reverted to lenient `Content::decode`.
  `pdf_text` with `>>` returns `Ok("Hello world\n")`, silently dropping
  `Lost line`; `impose` with `>>` returns Ok with 3 of 4 rectangles on the
  sheet. The truncation is real on both, and the committed
  `a_stray_token_*` tests FAIL under the revert (pdf_text 2 failed with my
  probe, impose 1 failed).

## Other injected defects

- `scalar_label` without the `Mapping` arm: `model_shared_helpers` FAILS.
- `scalar_label(&document.metadata)?` removed from `web/semantic.rs`:
  **survives**, full suite 743 passed (740 plus my 3 probes), 0 failed.
  The worker disclosed this (no end-to-end web test with a container
  label). Part 2 should add a web_port fixture manuscript with `label: []`
  so the wiring, not only the helper, is pinned.

## Suite

`cargo test` exit 0, 740 passed, 0 failed, 32 binaries; `cargo fmt
--check` 0; `cargo clippy --all-targets -- -D warnings` 0.

## What is and is not proven

- Proven: the `()`/`[]` divergence and its mechanism on both sides; strict
  decode fails loud on tokens beyond the worker's two, and lenient decode
  truncates on them; the helper refuses both container kinds.
- Not proven: the web refusal end to end (wiring mutant survives); typeset
  still prints `[]`; the `!!null` refusal and the impose exact-decimal and
  `inline_text` moves are open for part 2 / the orchestrator.
