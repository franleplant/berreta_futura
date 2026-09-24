# Orchestration queue (since the 2026-09-23 restart)

Comparator verify (WP-0.2m-r.verify.md): 0.2m/n/o ACCEPTED; 0.2p, 0.2q,
0.2r REJECTED (adversarial pairs pass); rework is WP-0.2s, then
re-verify adversarially.
Landed, awaiting a verifier: WP-3.3a, WP-5.9, WP-5.5c, WP-0.0d, WP-3.1, WP-3.4, WP-2.2c, WP-2.3, WP-0.2m, WP-0.2n, WP-3.2, WP-5.3h.
Accepted since the restart: WP-5.4c, WP-5.4b-i, WP-5.4b-ii, WP-0.2l,
WP-5.3c, WP-5.7a, WP-5.3h, WP-5.5a (1+2), WP-5.7b (after rework).
Running: WP-3.5 furniture, WP-5.5d web highlighting + python/c/http
lexers + JPEG plates, WP-0.2s comparator rework.
Next: WP-3.2 follow-up (opener art rasters, border), then WP-3.3, 3.0g,
3.7.

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
- WP-0.2r glyph-level display list under contract (b) (landed aad29c1);
  parity.yaml `swapped_words` must_flag gains glyph_positions (ratified).
- WP-5.3h spread order by page position, not paint order, in the Rust
  critic (class C: Python has the same defect; WP-5.3c pins it as a
  declared gap). Landed 7d652a3; Python keeps the defect until WP-6.1
  deletes it.
- WP-0.0d rule-colour token 230/255 exact (landed 0870773; baseline
  digest now 12c24234...).
- WP-3.3b wires mag/src/highlight into the template and WP-3.3's fixture
  edition; WP-5.5d wires it into the web port (fenced code with a
  language refuses there today) and accepts JPEG closing plates.
- WP-5.1h scope: consolidate `anchor_key`, `is_reference_heading`,
  `inline_text`, `article_opener_format` (duplicated in web/ and
  typeset/content.rs) into model/shared.rs; typeset's `anchor_key` uses
  str::trim, wrong on U+001C..U+001F.
- WP-5.6 wires the Rust web port into render.rs.
- WP-3.2 follow-up: draw opener art rasters; opener-art border typst
  strokes (23,25,28) where WeasyPrint fills.
- WP-3.5 carries: running-head paint order via `page.foreground`.
- WP-3.7 carries: page 6 inline-code chip that breaks across lines (bg
  runs 3 pt past the text at the break; chip corner radius 0.0046 pt off)
  per WP-3.1.md.

- Tier V never fails on pixels, so nothing outside Tier S/E backs up a
  normalization (WP-0.2m-r.verify.md); decide at WP-3.0g.

Orchestrator decisions:
- Colours compare at 8-bit resolution on both legs (typst-pdf rounds).
- `design_direction` is an engine label, excluded from layout comparison.
- What renders is the glyph (face, size, id, position, fill), not the
  engine's grouping into show operators; outline-less glyphs paint nothing.
- Tier E contract (b), matching the plan's stairdrift floor that must
  pass: the display list pins which glyphs appear, their order and each
  line's start; positions within a line belong to the glyph-position
  clause and its drift allowance.
- WP-5.5c package oracle (rule 6c, not comparable is not divergent):
  byte-equal SHA256SUMS is unattainable across PNG encoders (Pillow
  zlib-ng vs png crate) and PDF serializers (pypdf vs lopdf). The package
  is equal when JSON/text entries are byte-equal, PNGs pixel-equal, PDFs
  page-count and page-raster equal, archives per entry, and SHA256SUMS
  lists the same files in the same order (hash fields of non-byte-equal
  entries, e.g. render-critic.json booklet_sha256, excepted). Measured on
  010 per WP-5.5c.md; the verifier confirms.
- WP-5.6 uses package::archive::archive_tree for package.zip.
- WP-5.7b: Type3 with ToUnicode read (accepted); skipping invisible text
  beside printed text REJECTED by the verifier (hides scans).
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
