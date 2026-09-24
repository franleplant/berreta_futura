# Orchestration queue (since the 2026-09-23 restart)

Comparator verify (WP-0.2m-r.verify.md): 0.2m/n/o ACCEPTED; 0.2p, 0.2q,
0.2r REJECTED (adversarial pairs pass); rework WP-0.2s landed d7c970c.
Re-verify (WP-0.2s.verify.md): 0.2p, 0.2q ACCEPTED; 0.2r, 0.2s REJECTED
(blank counts on both legs buy drift; link /C and /F defaults). Rework
WP-0.2t landed 3efaf3c. Verify WP-0.2j.verify.md: 0.2r, 0.2s, 0.2t and
0.2j's exact-number path ACCEPTED; 0.2j span cap REJECTED (off-page
glyphs; 0.477 pt in-page); plus two older tracer holes. Rework WP-0.2u
landed fe1bd56 (MIN_ADVANCE_PT 1.25, strict decode, operand counts, no
#[ignore] left). Final adversarial comparator verify runs with WP-3.0g.
Landed, awaiting a verifier: WP-0.2w, WP-5.1h part 2; WP-0.0e, WP-3.5, WP-0.0d, WP-3.1, WP-3.4, WP-2.2c, WP-2.3, WP-3.2 (typeset set: one verifier after WP-3.7).
Accepted since the restart: WP-5.4c, WP-5.4b-i, WP-5.4b-ii, WP-0.2l,
WP-5.3c, WP-5.7a, WP-5.3h, WP-5.5a (1+2), WP-5.7b (after rework), WP-5.5c, WP-5.9, WP-3.3a,
WP-5.5d, WP-4.0g, WP-5.10, WP-5.1h part 1.
MILESTONE: WP-0.2x landed e1822cf; `mag parity 010` exits 0, every
evaluated Tier E clause green (raster not_evaluated, WP-0.2f withdrawn).
WP-3.0g landed 4c3697b: ratchet target E, all 54 pages at E, two clean
staged runs identical.
Running: final adversarial comparator verify (+ baseline raise
re-derivation), WP-0.0f (oracle passes JPEG bytes through; WP-3.9
landed 0508801: `--adhoc 008` exits 0, display list differs only on p4
editorial + the oracle's JPEG re-encodes).
WP-3.7c landed cbe1629: 010 display list 0 pages, navigation 0; glyph
clause 90 single-quantum blips (comparator artifact, WP-0.2x).
Next: typeset-set verifier, WP-5.6, WP-4.1, WP-4.2, WP-4.3, WP-6.1.
Phase 2/3 typeset WPs (2.2c, 2.3, 3.1, 3.2, 3.2b, 3.3b, 3.8, 3.7a, 3.7c, 3.9, 3.4, 3.5, 0.0d, 0.0e)
get one verifier after WP-3.7, since each later WP re-measures them.
Next: WP-3.3b, WP-3.0g, WP-3.7; WP-5.1h helpers; verifier batches.
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
- cover.py replace_first_page is dead (WP-6.1 deletes it anyway).
- WP-3.9 (after WP-3.7): generalize past 010 with `--adhoc 008`
  (WP-4.0g.md: headings break at different words, text order differs on
  pp. 16-20; figure JPEGs on pp. 16/17/19 are re-encoded by one leg,
  7-13% of samples differ, WP-0.2v.md). Pre-010 editions lack committed source-codes/; 009 refuses
  on a repeated closing-plate art (edition data, for Fran).
- WP-5.6 must add the cover step to the typst path (it has none; the
  parity domain excludes cover pages today).
- WP-5.1h part 2 (after the typeset WPs): typeset adopts shared.rs's
  anchor_key/is_reference_heading/article_opener_format and
  scalar_label (content.rs:889 prints `[]` for a list label); delete the 4
  ALLOWED rows in tests/rust_helpers.rs; inline_text moves to doc.rs;
  shared::load_structured accepts !!null as doc.rs does (WP-0.2w.md).
- WP-5.6 wires the Rust web port into render.rs.
- WP-3.2b: draw opener art rasters; opener-art border typst strokes
  (23,25,28) where WeasyPrint fills; opener QR/credit block colour at
  paint 1 on 9 opener pages (WP-3.5.md); typst document /Title ("<pub>:
  <title>", matching WP-0.0e) and outline to match the oracle.
- WP-3.5 carries: running-head paint order via `page.foreground`.
- WP-3.7 carries: typst links must write the oracle's `/BS <</W 0>>`
  (typst writes `/Border [0 0 0]`; raw link keys since WP-0.2t).
- WP-3.7 carries: outline entries open collapsed on typst (krilla 0.8.2
  hard-codes it; WeasyPrint opens them expanded): post-process /Count in
  template::pdf like the link-rect pass.
- WP-3.7 carries: pages 21/27 link x off ~0.01 pt (glyph-advance drift,
  WP-3.5.md names the test).
- WP-3.7 carries: page 6 inline-code chip that breaks across lines (bg
  runs 3 pt past the text at the break; chip corner radius 0.0046 pt off)
  per WP-3.1.md.

- Tier V stays a meter, as the plan says (rasters are Tier V meters only,
  plan ~3917); the adversarial verifiers' pixel diffs are what back each
  normalization. Decided at WP-3.0g, no change.

Orchestrator decisions:
- `cap_dots_125pt_100_tick` (one tick per step, inside the k-step bound)
  passes by design: it is the drift allowance's accepted limit, not a
  hole (WP-0.2x.md). Link rects compare within 0.25 pt, half their
  0.5 pt quantum; borders are zero-width so only the click area moves.
- Cross-leg coordinates compare as |a-b| <= 0.005 pt in f64 (half the
  quantum), not bucket equality after rounding: tighter in its maximum,
  and immune to sub-quantum edge flips (WP-3.7c.md). Glyph positions are
  quantized relative to their line start, as a difference.
- Compatibility shim `WEASYPRINT_69` (typeset/text_shim.rs) writes
  WeasyPrint 69's advances; `pango-center`/`own-run` template parts are
  outside the switch (WP-3.7c.md).
- Glyph advances (WP-3.7b.md): WeasyPrint 69 truncates each kern to an
  integer 1/1000 em (`int(kerning)`), writes Inter widths as integers and
  sets 10 pt text at 9.999756 pt; Typst writes harfbuzz's exact values.
  To keep the claim "renders the same" exact rather than loosening Tier
  E, the Typst leg reproduces WeasyPrint's written advances in a
  template::pdf post-pass (option 1), letter-spacing term included. It is
  a declared compatibility shim: the flip keeps it, and removing it later
  is an intended output change like WP-4.3, not a regression.
- Glyph drift residual accepted as the Tier E allowance's limit: a word at
  reach R may move R/1.25 ticks (0.186 pt at 318 pt), and only when every
  advance errs one tick the same way (WP-0.2u.md). MIN_ADVANCE_PT is
  calibrated on 010; re-derive it if an edition uses smaller type.
- WP-0.3 (absence-check helper) WITHDRAWN: it served the four landing
  checks, which the ff-only landing in WORKER-BRIEF.md removed; the
  brief's rule 5 carries the absence discipline.
- The live package test depends on an uncommitted oracle (tmp/v4, and
  preflight.json records absolute paths); WP-4.1 regenerates the package
  oracle fresh instead of relying on it.
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
- The printed edition has been re-encoding every EXIF-carrying figure
  JPEG at Pillow's default quality (WeasyPrint exif_transpose); WP-0.0f
  makes it pass the source bytes through.
- The editorial opener (editions 001-009 only) is a stub on the Typst
  path, out of the plan's scope: after WP-6.1 those editions cannot be
  re-rendered with their editorial.
- 008's source-codes/ were generated locally for `--adhoc 008` and not
  committed (edition data: commit them if you want 008 reproducible).
- Edition 009 no longer renders: one closing plate repeats another's art
  (the no-repeat rule). Editions before 010 have no committed
  source-codes/.
- Oracle quirks Typst now reproduces (WP-3.8): contents rows 98.25 pt
  apart although the stylesheet comment wants the six-row cap (WeasyPrint
  ignores max-height there); plates sharing a slot print in reverse order.
- The Python render critic falsely fails booklet page order on some
  highlighted code lines (its paint-order defect, fixed in Rust by
  WP-5.3h), which blocks oracle renders of such fixtures.
- PDF document title separator changed from U+2014 to ": " (repo rule
  forbids authoring U+2014 in copy); WP-0.0e.
- tools/pdf2md.py's ". . ." paragraph filter silently drops real text
  (WP-5.7a.md, tarpit fixture); may affect article.md files captured from
  PDFs. WP-5.7b replaces it.
- `cover-booklet-inside-not-blank` is unreachable in both critics.
- `label: false` prints "False" in both engines.
- The verbatim ten-page cap has no refusal on either leg (Dario 13 pp).
