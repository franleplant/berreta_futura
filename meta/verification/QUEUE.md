# Orchestration queue (since the 2026-09-23 restart)

Landed, awaiting a verifier: WP-2.2c, WP-2.3, WP-0.2m, WP-0.2n, WP-5.3c, WP-3.2.

New WPs opened outside the plan text (each brief is its section, the
evidence file records it):
- WP-0.2m tracer colour spaces (landed bdbcebf)
- WP-0.2n effective page boxes, 8-bit colour quantization (landed 917aff1)
- WP-0.2o per-glyph colour clause, display-list triage (running)
- WP-5.3h spread order by page position, not paint order, in the Rust
  critic (class C: Python has the same defect; WP-5.3c pins it as a
  declared gap). Queued.
- Next comparator WP: normalize link `/Rect` corners in
  `parity/display.rs` `page_annots` (WeasyPrint top-first, Typst
  bottom-first; WP-3.2.md). Queued behind WP-0.2o.
- WP-3.1 carries: inline `code` padding/background (page 4, 6), `END / NN`
  marks 5.4 pt off (WP-3.2.md).

Orchestrator decisions:
- Colours compare at 8-bit resolution on both legs (typst-pdf rounds).
- `design_direction` is an engine label, excluded from layout comparison.

For Fran (product questions, nothing blocks on them):
- `cover-booklet-inside-not-blank` is unreachable in both critics.
- `label: false` prints "False" in both engines.
- The verbatim ten-page cap has no refusal on either leg (Dario 13 pp).
