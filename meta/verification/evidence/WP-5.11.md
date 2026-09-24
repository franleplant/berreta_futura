# WP-5.11 critic JPEG decode, pen-end word gaps, 010 body-line pin

## Base

`art_directed` `e7c7670`, detached worktree `.../tmp/wp511`, its own `mag/target`.
Tracked runs `editions/010/run-2026-09-13T01-34-51` and `editions/008/run-2026-08-30T13-59-32`,
`--langs en`. `uv run python tools/sourcecodes.py 008` (exit 0) was run in the worktree only, as in
WP-5.4g.

## What changed

1. **JPEG decode** (`mag/src/critic/metrics.rs`): `decode_rgb` sniffs `FF D8` and decodes JPEG
   through zune-jpeg (already a dependency, `parity/streams.rs`) to RGB; EXIF orientation other than
   1 still bails, as on the PNG path; CMYK/YCCK input bails. The PNG path is unchanged
   (`check_orientation` is shared).
2. **Pen end** (`mag/src/parity/streams.rs`): `Element::Text` gains `pen: [i64; 2]` (serde-skipped,
   so no display-list or canon output changes), the pen displacement after the show (glyph advances,
   Tc, Tw and trailing TJ numbers) in the same quanta as `offs`. `canon.rs` gives each split glyph the
   next glyph's start as its pen; the test constructors in `critic.rs`, `critic/text.rs`,
   `parity/display.rs`, `parity/canon.rs` and `tests/critic_text.rs` fill it.
   `critic/text.rs` measures word gaps from the previous run's pen end instead of an extrapolated
   width, and `WORD_GAP_FRACTION` drops from 0.25 to 0.15 em.
3. **Gate** (`mag/src/parity/critic.rs`, one print line in `mag/src/parity.rs`): `text_characters`
   now joins the critic clause's pass condition and its differing pages are listed;
   `parity.yaml tiers.s.critic.text_check` says so, replacing the `reported_not_gated` argument.
4. **Pin** (`mag/tests/critic_text.rs`): total body lines 1117 -> 1126.

## Item 1: JPEG against PIL

PIL 12.3.0 with libjpeg-turbo 3.1.1 (`PIL.features`). All 43 tracked library JPEGs are YCbCr
4:2:0, 19 progressive, orientation absent or 1. **Not pixel-equal.** On 008's figure
(`how-warp-...-9e96ce55/media/001.jpg`, 3600x2526) zune's RGB matches PIL's `convert("RGB")` on
27102076 of 27280800 samples (99.34%), the rest off by 1 (115734), 2 (62607), 3 (380), 4 (3).
Decoding both to YCbCr without colour conversion (`PIL draft("YCbCr")`) isolates the cause: Y differs
on 3873 samples (zune's stb-derived IDCT descales pass 1 by 10 bits, libjpeg islow by 11 with
PASS1_BITS 2), Cb on 53544 and Cr on 58433 (zune's chroma upsampler versus libjpeg-turbo's h2v2
fancy upsampling). Colour conversion itself matches: applying libjpeg's integer YCC tables to
zune's YCbCr gives the same histogram as zune's RGB. Pixel equality needs a libjpeg-exact IDCT and
upsampler, which zune cannot supply (no coefficient API), i.e. a new decoder or a linked
libjpeg-turbo; not done here.

Tolerance the Python value implies: every metric is a count of thumbnail pixels over thresholds
(ratios at 1/N, N = thumbnail pixels, 5.4e-6 at 512x363) and a median contrast rounded to 3 places.
New test group `jpeg_figures` (`tests/critic_metrics_expected.json`, generated from
`magazine.image_contrast` on all 43 JPEGs) checks size, thumbnail size, `needs_treatment` before and
after, `adjusted` and `unresolved` exactly, and the ratios within 100 thumbnail pixels and contrast
within 0.01. Measured worst: paper ratio 92 pixels (`the-new-rules-of-context-engineering...
/002.jpg`, 0.833984 vs 0.834405), mark ratio 30 pixels, contrast 0.005. 41 of 43 differ in some
rounded value, **0 of 43 differ in any decision**; one (`uber .../008.jpg`) exercises the
contrast-strengthening path and matches. Positive control: the group at zero tolerance fails on 41
files (126 failure lines). 008's four figures: paper/mark within 0.000062 and contrast within
0.003 (011.jpg 4.217 vs 4.22). `preflight.json` is not a compared leaf in the comparator
(`parity.yaml json_leaves` only normalizes its paths), so this tolerance is not gated anywhere.

## Item 2: pen end

Same-line gaps between non-space shows, measured from the pen end on the staged 010 legs (scratch
tracer dump, both readers): oracle 126, typst 139; every gap is below 0.055 em (drop caps, "O" +
"n July") or at 0.217 em and above (word spaces), none between, so 0.15 em splits them with room.
The 13 extra typst gaps are the gap-encoded spaces WP-5.4g found (0.235 em, "us" + "wisely.").
Reader page texts are then identical on both legs, and the oracle text itself improves: two spaces
the 0.25 threshold dropped on BOTH legs appear ("efforts tostudying" p18, "consistentlyadvocated"
p26, gaps 0.234 and 0.233 em), so the old equality was partly equal-and-wrong. Known residue, equal
on both legs: gaps of 0.30-0.31 em before a comma after inline code ("verification) , which" p6)
read as a space; that is inline-code padding, not a word space.

Unit test `critic::text::writer_independent::a_gap_encoded_word_space_counts_from_the_pen_end`
passes at 0.15 and fails at 0.25 ("uswisely.").

## Item 3: 1117 vs 1126

The pin is stale, not a regression. WP-5.3b-i (`evidence/WP-5.3b-i.md` line 187) counted
`editions/010/render-2026-09-14T01-47-59/en/reader.pdf`, rendered before `5504e5a` (WP-1.5,
hyphenation off for en during parity, 2026-09-14 14:22); the pin landed later (`80b7b62`,
2026-09-18) but the PDF predates the switch. With this WP's code, the surviving pre-switch render
`render-2026-09-14T01-49-02` gives 1117 and today's oracle reader gives 1126. Per page, 15 pages move
(p16 7->10, p29 4->14, p44 18->23, others +-1..2): paragraphs reflow without hyphens and the Dario
piece's last lines spill from p28 onto p29. Line endings in "-" fall from 142 to 16. Independent
count, poppler `pdftotext -layout`, lines with a lowercase letter: 1126 on today's reader and 1117 on
the pre-switch one. Repinned to 1126; the page-4 (10) and page-36 (4) pins and the empty-page
partition hold.

## Commands and results

```sh
cargo fmt --check                                   # 0
cargo clippy --all-targets -- -D warnings           # 0
cargo test                                          # 0; 32 result lines, 942 passed, 0 failed
MAG_CRITIC_READER_PDF=editions/010/render-2026-09-24T12-16-24/en/reader.pdf \
  cargo test --release --test critic_text reconstructs   # 0 (MODE: full)
MAG_CRITIC_READER_PDF=.../render-2026-09-14T01-49-02/en/reader.pdf ... # 1: 1117 vs 1126 (control)
MAG_PARITY_OUT_DIR=<s> mag parity 010 --run editions/010/run-2026-09-13T01-34-51       # 0
MAG_PARITY_OUT_DIR=<s> mag parity --adhoc 008 --run editions/008/run-2026-08-30T13-59-32  # 1
```

010 staged (fresh, `bc49b2aa...`): ratchet pass (target E, 56 entries, 0 regressions); critic pass,
1999 leaves compared, 0 differ, Rust text fields on 111 pages 0 differ, **text_characters 0 pages
differ (gated)**; boxes, text, color, navigation pass; G max dy 0.006 pt; E glyph positions pass
(59073 glyphs, 0 violations); E display list pass (59304 vs 59304); V worst 0.000336. The earlier
staged run with the pen end at the old 0.25 threshold reported 32 pages differing, which is how the
threshold was found to need lowering.

After rebasing onto `b9d2085` (WP-3.10, typeset changes): `cargo test` 0 (949 passed, 0 failed),
`mag parity 010` staged 0 with the same numbers (critic 0 differ, text_characters 0 pages, ratchet
pass at E, glyph positions 0 violations, display list 59304 vs 59304). 008 was not re-run after
the rebase.

## Verify clause not met: `--adhoc 008` exits 1

The JPEG failure is gone: the typst leg now renders, packages and runs preflight on 008. It fails
Tier S critic on 59 report leaves, **all caused by reader page 4**: the typst leg sets 008's
editorial opener differently (headline on two lines at a smaller size and tighter leading, byline
jammed under it, dek larger; see `report/a-04.png` vs `b-04.png`), which leaves a 354x160 pt trailing
void the oracle page lacks. That void adds one `whitespace-void` issue on p4 and shifts every later
issue, crop and `summary.review_items` (7 vs 8) by one; every differing leaf is under `.issues`,
`.pages[3]`, `.visual_review.crops` or `.summary.review_items` (grep of the other 0 lines: 0).
Informational tiers agree: G displaces only page 4 (dx 4.0, dy 102.4 pt), E display list differs
only on page 4, V1/V2 fail from page 4 (worst 0.110). Rust text fields and text_characters agree on
all 87 pages. 010 has no editorial (editions from 010 on carry none), which is why 010 passes. This
is a typst editorial-page layout gap in typeset/render, outside this WP's Owns line; not fixed.

## What is and is not proven

PROVEN: the typst leg decodes JPEG figures and 008's pipeline completes on it; on all 43 library
JPEGs the preflight/critic decisions equal Python's and the rounded values sit within 100 thumbnail
pixels / 0.01 contrast. `text_characters` agrees on every page of both legs' four PDFs on 010 (111
pages) and 008 (87 pages) and is now gated; a positive unit control fails at the old threshold. The
010 body-line pin of 1117 came from a pre-WP-1.5 PDF, and 1126 matches an independent poppler count.

NOT PROVEN / open:
- Pixel-equal JPEG decode (not achieved; cause and size of the gap above). An image whose metric sits
  within ~100 thumbnail pixels of a threshold could decide differently from Python.
- `--adhoc 008` exit 0: blocked by the typst editorial opener (page 4), for the typeset owner.
- The 0.15 em threshold is argued from 010's and 008's gap distribution only; a face with a narrow
  word space (under 0.15 em) or a letter-spaced run split into shows would need re-measuring.
- Inline-code padding before punctuation still reads as a space on both legs (equal, not correct).
