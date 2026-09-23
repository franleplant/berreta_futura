# Orchestration queue (since the 2026-09-23 restart)

Landed, awaiting a verifier: WP-2.2c, WP-2.3, WP-0.2m, WP-0.2n, WP-3.2, WP-0.2o, WP-0.2p, WP-5.3h.
Accepted since the restart: WP-5.4c, WP-5.4b-i, WP-5.4b-ii, WP-0.2l,
WP-5.3c, WP-5.7a.
Running: WP-5.5a increment 2, verifier for WP-5.7b + WP-5.3h, WP-3.4
landing (+ 300 ppi refusal, fixture 900 figure).
Next: WP-0.2r = land branch wp-0.2q-full (acad53b) under contract (b).

New WPs opened outside the plan text (each brief is its section, the
evidence file records it):
- WP-0.2m tracer colour spaces (landed bdbcebf)
- WP-0.2n effective page boxes, 8-bit colour quantization (landed 917aff1)
- WP-0.2o per-glyph colour clause, display-list triage (landed e5e3498)
- WP-0.2p five representation-only normalizations, mkfixtures
  determinism, per-page difference counts (landed 066b58d)
- WP-0.2q display-list text at glyph level (spaces dropped), glyph
  positions paired on it, even-odd accent strip. Partly landed 45fc32a
  (accent strip, loop direction, ICCBased images); glyph-level text on
  branch wp-0.2q-full, see WP-0.2r.
- WP-5.3h spread order by page position, not paint order, in the Rust
  critic (class C: Python has the same defect; WP-5.3c pins it as a
  declared gap). Landed 7d652a3; Python keeps the defect until WP-6.1
  deletes it.
- WP-0.0d sanctioned oracle change: rule-colour token 0.9 -> 230/255
  exact (WP-0.2o.md: typst can only write 230, pixels differ 229 vs 230).
  Queued after WP-3.4 lands (re-seeds the baseline digest).
- WP-3.2 follow-up: draw opener art rasters; opener-art border typst
  strokes (23,25,28) where WeasyPrint fills.
- Typst leg must enforce the same 300 ppi figure refusal as the Python
  leg; fixture 900's 14 ppi figure needs replacing (WP-3.4 follow-up).
- WP-3.5 carries: running-head paint order via `page.foreground`.
- WP-3.1 carries: inline `code` padding/background (page 4, 6), `END / NN`
  marks 5.4 pt off (WP-3.2.md).

Orchestrator decisions:
- Colours compare at 8-bit resolution on both legs (typst-pdf rounds).
- `design_direction` is an engine label, excluded from layout comparison.
- What renders is the glyph (face, size, id, position, fill), not the
  engine's grouping into show operators; outline-less glyphs paint nothing.
- Tier E contract (b), matching the plan's stairdrift floor that must
  pass: the display list pins which glyphs appear, their order and each
  line's start; positions within a line belong to the glyph-position
  clause and its drift allowance.
- WP-5.7b departures accepted: Type3 fonts with ToUnicode are read;
  invisible text on a page that also prints text is skipped.
- WP-6.1 also deletes tools/pdf2md.py (unused since WP-5.7b, 4727939).
- Bullets: template changes to WeasyPrint's control points (0.01 pt off,
  not normalizable within the quantum). Owner WP-3.1.

For Fran (product questions, nothing blocks on them):
- tools/pdf2md.py's ". . ." paragraph filter silently drops real text
  (WP-5.7a.md, tarpit fixture); may affect article.md files captured from
  PDFs. WP-5.7b replaces it.
- `cover-booklet-inside-not-blank` is unreachable in both critics.
- `label: false` prints "False" in both engines.
- The verbatim ten-page cap has no refusal on either leg (Dario 13 pp).
