# WP-5.7a the PDF fixture corpus and the fidelity spec

## Base

57e192f (`test(critic): WP-5.3c fault suite`), branch art_directed.

## Status

**done**. Five real PDFs committed with pinned hashes, a ground truth per
fixture built by disagreement review, the fidelity checks as a Rust
checker, and the checks run against pypdf and poppler on all five with the
868 verdicts recorded. Neither extractor passes; both fail on real defects,
differently. No extractor was chosen and no production code changed.

## What changed

Everything lives under `mag/tests/pdf_fixtures/` (this WP's Owns):

- `<fixture>/source.pdf`: the real PDF, byte-for-byte as downloaded.
- `<fixture>/truth.md`: the ground truth passages, verbatim as the page
  prints them, one passage per paragraph, code in fences with its printed
  indentation. A line-end hyphen is written joined and kept (`archi-tecture`).
- `<fixture>/spec.yaml`: source URL, retrieval date, sha256, producer,
  shape, the hyphen lists, forbidden strings, the reading-order anchors, and
  `review`: one entry per disagreement with what pypdf says, what poppler
  says, and what the page shows.
- `<fixture>/{pdf2md.md,pypdf.txt,poppler.txt,poppler-layout.txt}`: the
  extractor outputs the verdicts are computed from, regenerable (below).
- `checks.rs`: the checker, `load(dir)` and `verdicts(&fixture, text)`.
  WP-5.7b reuses it with `#[path = "pdf_fixtures/checks.rs"] mod checks;`.
- `main.rs`: the `pdf_fixtures` test target (5 tests, below).
- `verdicts.tsv`: fixture, tool, check, PASS/FAIL for every combination.

## The corpus

All retrieved 2026-09-23 except deepseek (captured 2026-09-12 by
`mag capture`, copied from `.magazine/capture/`, sha256 matching WP-5.7's
file). Producers and pages from `pdfinfo`/`pdffonts`.

| fixture | shape | producer | pages | bytes |
|---|---|---|---|---|
| bert | two-column paper (arXiv 1810.04805v2) | pdfTeX-1.40.17, Type1 + TrueType | 16 | 775,166 |
| fsr | report with tables, sidebar box, footnotes (Fed Financial Stability Report 2023-10) | InDesign 17.4, Type 1C + TrueType | 70 | 2,962,109 |
| pytorch | code blocks, one side-by-side listing (arXiv 1912.01703v1) | pdfTeX-1.40.17, Type1 | 12 | 380,838 |
| tarpit | ligature-heavy body, no ToUnicode on most fonts (Out of the Tar Pit) | Quartz PDFContext re-save of LaTeX, MacRoman Type1 | 66 | 532,006 |
| deepseek | the existing 51-page /Type1 sample | pdfTeX, Type1 with ToUnicode | 51 | 1,809,802 |

Four producers, three font technologies, and one fixture (tarpit) without
`/ToUnicode` on its ligature fonts. 6,459,921 bytes of PDF in total.

## The checks

Normalisation (`norm`) applied to both truth and output: collapse every
whitespace run to one space, then drop the space after a hyphen, en dash or
em dash that follows a word character (a line break after a dash is not a
space). No case folding, no NFKC: ligature codepoints are NOT normalised
away.

| family | assertion | plan clause |
|---|---|---|
| `passage:i` | each truth passage occurs in the output exactly once | no text dropped, none duplicated |
| `order:g.i` | anchor i+1 of group g first occurs after anchor i | reading order |
| `code:i` | the block's non-blank lines appear as a contiguous run (whitespace-trimmed) | fenced code survives intact |
| `code-exact:i` | a contiguous run of output lines, dedented, equals the block exactly, blank lines and relative indentation included | fenced code survives intact |
| `hyphen:i` | a discretionary line-end hyphen is kept attached (`archi-tecture`) | a line-end hyphen is never silently deleted |
| `real-hyphen:i` | a compound hyphen survives, including one that fell at a line end (`input-heavy`, `left-to-right`) | real hyphens survive |
| `absent:i` | a named corruption never appears (`DeepSeek-V4.1Flash`, U+21B5) | word corruption |
| `chars:*` | no C0/C1 control except \t \n \r \f, no U+FB00-FB06, no U+FFFD, no U+00AD | dropped/garbled glyphs |

`order` uses explicit anchors (short, defect-free strings) rather than the
passages, so a passage lost to a hyphen weld does not also count as an order
failure; the first version derived order from passages and conflated the two,
failing 146 order checks of which almost none were ordering errors. Groups
separate flows whose relative order is not defined (FSR's sidebar).

## Commands

Regenerate the outputs (run from the repository root; exit 0; the rerun left
`git diff` empty, so all four extractors are deterministic on this corpus):

```
for d in mag/tests/pdf_fixtures/*/; do
  uv run python tools/pdf2md.py ${d}source.pdf > ${d}pdf2md.md
  uv run python -c "import sys; from pypdf import PdfReader; sys.stdout.write(''.join((p.extract_text() or '') + '\n' for p in PdfReader(sys.argv[1]).pages))" ${d}source.pdf > ${d}pypdf.txt
  pdftotext ${d}source.pdf ${d}poppler.txt
  pdftotext -layout ${d}source.pdf ${d}poppler-layout.txt
done
```

Verify (in `mag/`):

```
cargo test --test pdf_fixtures              # 5 passed, exit 0
MAG_PDF_FIXTURES_BLESS=1 cargo test --test pdf_fixtures   # rewrites verdicts.tsv
cargo test                                  # every target ok, exit 0
cargo fmt --check                           # exit 0
cargo clippy -q --all-targets -- -D warnings   # exit 0
```

Negative control on the recorded table: flipping line 1 of `verdicts.tsv`
from PASS to FAIL made `recorded_verdicts_match` FAIL; restored, green.

The five tests:

- `fixtures_are_the_pinned_real_pdfs`: at least five, each `%PDF-`, sha256
  equal to spec, source URL, producer, shape and non-empty review entries.
- `ground_truth_passes_every_check`: the positive control; the truth text
  itself passes every check on every fixture (so every anchor and hyphen
  string is actually in the truth, in order).
- `recorded_verdicts_match`: the 868 verdicts equal `verdicts.tsv`.
- `every_check_family_discriminates_on_real_output`: every family has at
  least one PASS and one FAIL across the real outputs.
- `each_defect_trips_its_check`: mutations of the truth (drop a passage,
  duplicate it, swap two anchors, delete an anchor, weld each line-end
  hyphen, put a space before it, append each forbidden string, a U+FB01,
  a NUL, a U+00AD, a U+FFFD, shift one code line by a space, delete one)
  each fail exactly the check they target, and the space shift leaves
  `code:i` passing while failing `code-exact:i`.

Tool versions: pypdf 6.14.2, poppler 25.08.0 (`pdftotext`), python 3.12.11,
rustc 1.96.0.

## Results

PASS/total per family (from `verdicts.tsv`). `pdf2md` is what `mag capture`
writes today (pypdf plus the paragraph wrapper); `pypdf` is the raw library;
`poppler-layout` is informational, a third extractor mode.

| fixture | tool | passage | order | code | code-exact | hyphen | real-hyphen | absent | chars | total |
|---|---|---|---|---|---|---|---|---|---|---|
| bert | pdf2md | 8/12 | 8/8 | - | - | 5/5 | 7/9 | 2/2 | 3/4 | 33/40 |
| bert | pypdf | 8/12 | 8/8 | - | - | 5/5 | 7/9 | 2/2 | 3/4 | 33/40 |
| bert | poppler | 4/12 | 8/8 | - | - | 0/5 | 4/9 | 0/2 | 4/4 | 20/40 |
| bert | poppler-layout | 1/12 | 6/8 | - | - | 2/5 | 5/9 | 2/2 | 4/4 | 20/40 |
| deepseek | pdf2md | 8/11 | 10/10 | - | - | 2/2 | 8/8 | 3/3 | 3/4 | 34/38 |
| deepseek | pypdf | 8/11 | 10/10 | - | - | 2/2 | 8/8 | 3/3 | 3/4 | 34/38 |
| deepseek | poppler | 4/11 | 10/10 | - | - | 0/2 | 4/8 | 0/3 | 3/4 | 21/38 |
| deepseek | poppler-layout | 11/11 | 10/10 | - | - | 2/2 | 8/8 | 3/3 | 3/4 | 37/38 |
| fsr | pdf2md | 12/22 | 15/16 | - | - | 1/6 | 4/4 | 1/1 | 3/4 | 36/53 |
| fsr | pypdf | 12/22 | 15/16 | - | - | 1/6 | 4/4 | 1/1 | 3/4 | 36/53 |
| fsr | poppler | 10/22 | 15/16 | - | - | 0/6 | 2/4 | 0/1 | 2/4 | 29/53 |
| fsr | poppler-layout | 14/22 | 16/16 | - | - | 4/6 | 3/4 | 1/1 | 2/4 | 40/53 |
| pytorch | pdf2md | 11/17 | 12/13 | 0/3 | 0/3 | 3/3 | 5/5 | 0/2 | 3/4 | 34/50 |
| pytorch | pypdf | 11/17 | 12/13 | 1/3 | 0/3 | 3/3 | 5/5 | 0/2 | 3/4 | 35/50 |
| pytorch | poppler | 11/17 | 12/13 | 2/3 | 0/3 | 0/3 | 2/5 | 2/2 | 4/4 | 33/50 |
| pytorch | poppler-layout | 15/17 | 12/13 | 1/3 | 1/3 | 3/3 | 5/5 | 2/2 | 4/4 | 43/50 |
| tarpit | pdf2md | 1/11 | 8/10 | - | - | 4/6 | 3/3 | 0/2 | 2/4 | 18/36 |
| tarpit | pypdf | 2/11 | 10/10 | - | - | 5/6 | 3/3 | 0/2 | 2/4 | 22/36 |
| tarpit | poppler | 4/11 | 10/10 | - | - | 0/6 | 2/3 | 1/2 | 4/4 | 21/36 |
| tarpit | poppler-layout | 9/11 | 10/10 | - | - | 6/6 | 3/3 | 1/2 | 4/4 | 33/36 |

Totals: pdf2md 155/217, pypdf 160/217, poppler 124/217, poppler-layout
173/217. Per family over all rows: passage 164 pass / 128 fail, order 217/11,
code 4/8, code-exact 1/11, hyphen 48/40, real-hyphen 92/24, absent 24/16,
chars 62/18.

**Two false passes found and fixed during review.** The hyphen checks are
document-wide substring matches, so their context must be unique to the
break. `to down-|stream tasks` passed poppler because p5 prints `transferred
to down-stream tasks` mid-line; `functional pro-|gramming` passed pypdf because
the phrase breaks the same way elsewhere in tarpit, while at the reviewed break
pypdf actually emits `onfunctional pro- grammingandCodd’s`. Both entries were
lengthened (`representations to down-|stream tasks:`, `based on functional
pro-|gramming`); three verdicts flipped to FAIL. A scan of every hyphen entry
and order anchor across the four outputs then found no string occurring more
than once in any output. The rule for WP-5.7b and anyone extending the
corpus: a hyphen or anchor string must occur once in the document.

## What the disagreement review found

Each is recorded, with the page's reading, in the fixture's `review`.

- **poppler welds every line-end hyphen**, confirmed on all five: `inputheavy`,
  `DeepSeek-V4.1Flash`, `left-toright`, `objectoriented`, `price-toearnings`:
  `hyphen` 0/22 across its rows. `pdftotext -layout` does NOT weld.
- **pypdf emits ligature codepoints** (U+FB01/FB02) on every pdfTeX and
  InDesign fixture: `ﬁne-tuned`, `classiﬁcation`, `efﬁcient`.
- **tarpit: pypdf decodes the ffi ligature as NUL** (`di\0culty`, three
  letters lost), and drops spaces at italic runs (`accidentalfromessentialdi\0culty`).
- **tarpit: both extractors AGREE and are both WRONG** on the ff ligature,
  `o↵ers` for `offers` (U+21B5, a downwards arrow). Agreement is not
  correctness; `absent:0` fails every row, `poppler-layout` included.
- **pdf2md drops text pypdf extracted**: tarpit p3's paragraph `. . . and the
  Economist devoted a whole article` is in `pypdf.txt` and missing from
  `pdf2md.md`, because `pdf2md.py` discards any paragraph containing `. . .`,
  which is how pypdf spells a leading ellipsis. A wrapper defect that
  silently deletes source text in today's capture path.
- **FSR (InDesign)**: pypdf puts a space before each line-end hyphen
  (`understand - ing`) and inside words in small type (`Residential r eal
  estate`, `Gr o wth rates ar e mea sur ed`); poppler splices the sidebar into
  the main column mid-sentence and moves table labels (`Item`, `Leveraged
  loans`) away from their cells, and emits U+00AD; pypdf emits Figure 1.1
  (page bottom) before Table 1.1 (page top).
- **pytorch**: the side-by-side Listing 1 fails `order` for all four rows
  (pypdf interleaves the two code columns line by line and case-folds
  `LinearLayer` to `linearlayer`; poppler moves `def forward(self,
  activations)` out of its class). Listing 2's indentation is lost by both
  pypdf and poppler; only `-layout` keeps it (the single `code-exact` pass).
- **deepseek**: pypdf drops spaces around bold runs (`theruntime KVfootprint`,
  `(b)Global`); every row emits C0 control characters for unmapped math glyphs.

## What is and is not proven

Proven:
- The checks discriminate: every family passes and fails on real output, the
  truth passes all of them, and each mutation trips exactly its check.
- The plan's named defect is real and caught: poppler 25.08.0 welds line-end
  hyphens on every fixture, pypdf 6.14.2 does not.
- Neither pypdf nor poppler meets the spec, and neither does today's capture
  path (`pdf2md`, 155/217). WP-5.7b's bar, every check on every fixture, is
  therefore higher than what `mag capture` does now; that is the intent of the
  revision-12 re-scope, not an accident of the corpus.
- The outputs are regenerable and were byte-identical on regeneration.

Not proven, and why:
- **Duplication has no wild example.** No passage occurs twice in any real
  output (scan over all 20 outputs, exit 0, zero hits); the duplicate half of
  `passage:i` is shown only by the mutation test. The shingle scan did find
  poppler-only repeats in bert, fsr and deepseek, but each was text the PDF
  genuinely prints twice, which pypdf had mangled in one copy.
- The truth is passages, not a full transcription: 73 passages and 67 order
  anchors across five documents. Text outside them is unconstrained, so a
  defect in an unreviewed region can pass. `chars:*` and `absent:*` are the
  only whole-document checks.
- Ground truth was read by me from page renders (`pdftoppm`) of bert p1 and
  p5, deepseek p1 and p4, fsr p5, p13 and p14, pytorch p1 and p4, tarpit p1
  to p3. Passages outside those pages (pytorch p5 onward) rest on agreement
  between pypdf and `poppler -layout`, two independent extractors, as the WP
  allows, not on a render.
- Soft versus compound hyphens: the text layer cannot tell a discretionary
  hyphen from a real one, and the plan says never delete, so the spec
  requires `represen-tation` to stay hyphenated. Markdown written this way
  keeps typesetting hyphens in the middle of words, which is the verbatim
  choice and a readability cost.
- Branches the corpus cannot reach, to be covered by WP-5.7b's fail-loud
  tests rather than by these fixtures: encrypted PDFs, CID fonts without a
  usable mapping, Type3 fonts, rotated pages, right-to-left scripts, and
  scanned (image-only) pages. The corpus has no RTL text and no encryption.
- I authored fixtures and checks and have not implemented an extractor; the
  WP's separation rule requires WP-5.7b's implementer to be someone else.
