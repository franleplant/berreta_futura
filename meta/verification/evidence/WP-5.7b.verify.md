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
