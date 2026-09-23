# WP-5.7b verification

Verifier worktree at 4727939 (the WP's landed commit), own
`CARGO_TARGET_DIR`. No code changed. Scratch tests and mutations lived only
in the worktree and were moved out or restored (`cmp` exit 0 against the
saved original, `git status` clean before this file was written).

## Verdict: REJECTED, on one point

Everything the Verify clause asks for replays green, and the mutations prove
the checks bite. The rejection is the second recorded departure. The
orchestrator accepts it "unless it hides real text loss", and it does: a
scanned page with an OCR layer and any small printed text returns only the
printed text, with no error. Details and the fix are below. The Type3
departure is accepted.

## Replay

| command (in `mag/`) | exit | observed |
| --- | --- | --- |
| `cargo test` (full, after the worker's rebase, which it did not re-run) | 0 | 28 binaries, 445 passed, 0 failed (the evidence's 403 predates the rebase onto WP-0.2p and WP-5.3h) |
| `cargo test --test pdf_text -- --nocapture` | 0 | 11 passed; bert 40/40, deepseek 38/38, fsr 53/53, pytorch 50/50, tarpit 36/36 = 217/217 |
| same, `three_runs_are_byte_identical` | 0 | passed (three in-process runs per fixture compared) |
| `cargo fmt --check` | 0 | |
| `cargo clippy -q --all-targets -- -D warnings` | 0 | no output |

The checks are WP-5.7a's: `git diff f5754b8 4727939 --stat` touches neither
`tests/pdf_fixtures/` nor `checks.rs` (last change d1c8da7, WP-5.7a), and 217
equals the total in WP-5.7a.verify.md line 17.

Call site: `mag/src/capture.rs` declares `#[path = "pdf_text.rs"] mod
pdf_text;` (line 9) and `pdf_to_extraction` calls `pdf_text::transcribe(pdf)`
(line 646). It compiles in the `mag` binary built by the full `cargo test`
above. No `uv run` remains on that path.

## Mutations of pdf_text.rs (each restored, `cmp` exit 0)

1. `expand`: the ligature range `U+FB00..=U+FB06` changed to an empty-effect
   `U+FB7F..=U+FB7F`. `every_fidelity_check...` FAILED: bert 33/40, deepseek
   35/38, fsr 49/53, pytorch 43/50, tarpit 27/36, `chars:ligature` failing on
   all five plus passages.
2. `xycut`: the spanning-rule test `>= 0.8 * (x1 - x0)` changed to `>= 2.0 *`
   (a rule can never outrank a column cut). FAILED: fsr 44/53
   (`passage:15..19`, `order:2.4..2.7`), others unchanged. A layout
   threshold, not only decoding, is pinned by the corpus.

## Crafted fail-loud inputs (a scratch test file, not committed)

- A Form XObject that invokes itself: `Err("page 1: form XObjects nest
  deeper than 16 levels")`. This is the one branch the evidence lists with no
  test, now shown to fire.
- Helvetica with a ToUnicode mapping a code to U+0627: `Err("... right-to-left
  text ("ا") needs bidi reordering, not read")`.
- Held-out `output/print/a-sneak-preview-.../print.pdf`: `Ok`, 1,708 words,
  matching the evidence's held-out number.

## The two departures

**Type3 with `/ToUnicode` is read: accepted.** It is the same trust the WP
already gives an `Identity-H` CID font with a `/ToUnicode`, codes absent from
the map still fail loud (`type3_font_fails_loud` shows both halves), and a
Type3 font without the map still fails. The "lying ToUnicode" caveat in the
evidence applies equally and is recorded there.

**Invisible text on a page that also has printed text is skipped:
rejected.** Crafted page: a full-page image, a printed 8 pt line
`Downloaded from a library`, and an invisible (`3 Tr`) OCR line. Result:
`Ok("Downloaded from a library\n")`, no error. The page is a scan, which the
WP's own table says must fail loud ("OCR is not transcription"), yet it passes
and its body is gone. This is the shape of a real class of input: library and
archive scans that stamp a printed download footer or cover line on every
OCR'd page. Across a multi-page article the capture would clear the 50-word
floor on footers alone and write a near-empty `article.md` as if faithful.

Evidence that the stricter rule costs nothing measured: an `eprintln!` on
every page with `invisible > 0` printed nothing across all five fixtures (the
corpus contains no invisible text at all), and nothing for the held-out
`print.pdf`. The only thing the skip rule does, in corpus, held-out, or
tests, is the synthetic `mixed` assertion in
`skewed_mirrored_and_invisible_text_fail_loud`. So the departure is untested
against any real document and its one observed real-shaped effect is silent
loss.

Required to accept: fail loud on a page that carries invisible text and an
image (or where invisible glyphs outnumber printed ones), with a test built
from the crafted page above; keep the plain mixed case only if a real
document needs it, and name that document.

## Residuals (not grounds for rejection)

- A missing XObject resource returns `Ok(())` silently (`xobject`, first
  `else`). A form whose text was lost this way would not be noticed; a
  missing image only lowers the image count.
- The evidence's own caveats stand: thresholds tuned on the grading corpus,
  no true held-out set, text outside the 73 passages loosely constrained.

## What is and is not proven

Proven: 217/217 on the committed WP-5.7a checks, three runs identical, full
suite green after the rebase, capture routes to `pdf_text`, two independent
mutations each drop checks, the untested nesting guard and the RTL branch
fire on crafted input, and the mixed-page skip silently drops a scan's OCR
body.

Not proven: behaviour on any real scanned PDF (none in corpus; the loss case
is synthetic but built from standard operators); fidelity on documents
outside the five fixtures beyond the one held-out file.

## Re-verify (rework 9c65b66)

Verifier worktree at 9c65b66, own `CARGO_TARGET_DIR`. No code changed;
scratch tests and mutations restored (`cmp` exit 0, `git status` clean).

### Verdict: ACCEPTED

The rejected point is fixed: the crafted scan page fails loud, the positive
controls still read, and the one remaining rule (no image, fewer invisible
glyphs than printed) does not hide loss of printed text.

### Replay

| command (in `mag/`) | exit | observed |
| --- | --- | --- |
| `cargo test --test pdf_text -- --nocapture` | 0 | 14 passed; bert 40/40, deepseek 38/38, fsr 53/53, pytorch 50/50, tarpit 36/36 = 217/217; `three_runs_are_byte_identical` ok |
| `cargo test` (full) | 0 | 29 binaries, 476 passed, 0 failed (matches the rework evidence) |
| `cargo fmt --check`, `cargo clippy -q --all-targets -- -D warnings` | 0, 0 | |
| held-out `output/print/a-sneak-preview-.../print.pdf` (scratch test) | 0 | Ok, 1,708 words, unchanged |

`a_scan_with_a_printed_footer_and_an_ocr_layer_fails_loud` is my original
crafted page verbatim (full-page `/Im1`, 8 pt `Downloaded from a library`,
`3 Tr` body line) and asserts the error; its footer-only positive control
reads `"Downloaded from a library\n"`. `positive_control_reads_a_plain_page`
and the Type3-with-ToUnicode read are green.

### Crafted probes (scratch test, not committed)

| page | result |
| --- | --- |
| scan as an INLINE image (`BI ... ID ... EI`) + footer + OCR | Err, "4 invisible glyphs, 22 printed, 1 images" |
| scan + footer + OCR in `7 Tr` (invisible and clip) | Err, same counts |
| scan image drawn inside a Form XObject + footer + OCR | Err, same counts (images counted through the form) |
| no image, vector fill, 22 printed, 4 invisible | Ok, printed text only (the accepted rule) |
| no image, 4 printed, 4 invisible | Ok, printed only (`>` is strict; equal counts read) |

### Mutations of my own (each restored)

| mutation | result |
| --- | --- |
| drop the `it.images > 0 \|\|` clause | caught: `a_scan_with_a_printed_footer...` fails |
| `invisible > glyphs` to `invisible > 2 * glyphs` | caught: `skewed_mirrored_and_invisible_text_fail_loud` fails |
| inline images (`BI`/`EI`) no longer counted | SURVIVED: no committed test builds an inline image |

### Why the remaining rule is accepted

Everything the rule reads is printed; what it drops is text a reader of the
page cannot see. A scan needs a raster, and every raster path I tried
(XObject, inline, inside a form) is counted and trips the image clause, so
an OCR body is never dropped for being outnumbered by a footer. The rule
can only drop an OCR layer where the scan is not a counted image (a raster
painted through a tiling pattern, or a vector-traced page) AND the hidden
glyphs are fewer than the printed ones; that is contrived, and a real OCR
body outnumbers its stamped footer, which fails loud on the count alone.

### Residuals (not grounds for rejection)

- Inline-image counting is correct today (probe above) but unpinned: the
  mutation that removes it survives. A one-line inline-image variant of the
  scan test would pin it.
- Rasters painted through patterns are not counted as images.
- The missing-XObject fix is tested (`a_missing_xobject_fails_loud`) and
  bites under the worker's mutation; not re-mutated here.
