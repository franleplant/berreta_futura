# Orchestration queue (since the 2026-09-23 restart)

## Status

- `mag parity 010` staged: exit 0, ratchet target E, pages 1..56, critic
  clause passing (WP-5.4g/5.3g e7c7670). `mag render --engine typst` runs
  natively without uv (WP-5.6 2ea64da). `--adhoc 008`: display list equal
  except p4 (editorial, out of scope); exit 1 until WP-5.11 (critic JPEG
  decode).
- Comparator: every 0.2 WP accepted after adversarial rounds
  (WP-0.2m-r, 0.2s, 0.2j, 3.0g verify files) except WP-0.2y (rework of
  0.2v, landed a5aadc9, verified at the WP-4.1 gate).
- Typeset set (17 WPs): accepted, TYPESET-SET.verify.md.
- Accepted since the restart: WP-5.4c, 5.4b-i, 5.4b-ii, 0.2l, 5.3c, 5.7a,
  5.3h, 5.5a (1+2), 5.7b, 5.5c, 5.9, 3.3a, 5.5d, 4.0g, 5.10, 5.1h part 1,
  0.2u, 0.2w, 0.2x, 3.0g, and the typeset set.
- Awaiting the WP-4.1 gate verifier: WP-5.6, 0.2y, 5.4g, 5.3g, 3.10,
  5.11; it also raises cover rows 1 and 56 to E.
- Running: WP-3.10 (Spanish on typst), WP-5.11.
- Next: WP-4.1 full gate, then WP-4.2 flip, WP-4.3 post-flip hyphenation,
  WP-6.1 delete Python.

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
- Workers may rebase baseline.json's staged digest when their own oracle
  change moved it and they prove the delta; a verifier re-derives it
  (WP-3.0g.verify.md confirmed bc49b2aa).
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
- `cover_art_size_points` is null on both legs, so preflight never checks
  cover-art size (WP-5.6.md).
- The printed edition re-encoded EXIF-carrying figure JPEGs (3 in 008)
  at Pillow's default quality; WP-0.0f passes the source bytes through.
  JPEGs with EXIF orientation != 1 now refuse on both legs (rotate them
  losslessly with jpegtran); none exist today.
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
