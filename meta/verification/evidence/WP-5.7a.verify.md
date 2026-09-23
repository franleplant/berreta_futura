# WP-5.7a verify

**Verdict: ACCEPTED.**

Verified at art_directed tip `01a7ac6`, fresh detached worktree, own
`CARGO_TARGET_DIR`. No code changed.

## Replayed commands

| command | exit | observed |
| --- | --- | --- |
| `cargo test --test pdf_fixtures` | 0 | 5 passed |
| `cargo test` | 0 | 27 binaries, 392 passed, 0 failed |
| `cargo fmt --check`, `cargo clippy -q --all-targets -- -D warnings` | 0, 0 | |
| the evidence's regeneration loop (pdf2md, pypdf, pdftotext, pdftotext -layout), writing to scratch instead of the tree | 0 | `cmp` byte-identical to the committed file for all 20 outputs |
| `shasum -a 256` of each `source.pdf` against `spec.yaml` | | 5 of 5 equal |
| awk over `verdicts.tsv` | | 868 rows; pdf2md 155/217, pypdf 160/217, poppler 124/217, poppler-layout 173/217; per family order 217/11, passage 164/128, code 4/8, code-exact 1/11, hyphen 48/40, real-hyphen 92/24, absent 24/16, chars 62/18. All equal to the evidence. |

The plan's Verify clause (the checks run against pypdf and poppler on all
five fixtures, with the results recorded) is met, and the recorded table is
pinned by `recorded_verdicts_match`.

## My mutations (in the checker; the worker mutated only the truth and the tsv)

1. `passage:i` changed from `count() == 1` to `count() >= 1`, which removes
   the duplication half of the check. Predicted: `each_defect_trips_its_check`
   fails, and `recorded_verdicts_match` stays green, because the evidence says
   no real output duplicates a passage. Observed: exactly that (panic at
   main.rs:139, other 4 ok). This also independently confirms the
   evidence's "duplication has no wild example".
2. `chars:control` changed to also allow NUL. Predicted: the NUL mutation in
   `each_defect_trips_its_check` fails, and `recorded_verdicts_match` fails
   because tarpit's pypdf and pdf2md outputs contain only NUL controls (I
   counted 31 and 28 NULs, and no other C0/C1 character), while deepseek's
   other C0 characters keep those rows failing. Observed: both tests failed
   (main.rs:173, main.rs:102), and the other 3 passed.

After each run, `checks.rs` was restored from a copy and `git status` was clean.

## Truth spot-checks against page renders (pdftoppm -r 110)

- **pytorch p4, Listing 1 and Listing 2** (`code:0..2`). Listing 1: class
  bodies are indented 3 spaces and methods 6, with one blank line before
  `def forward`. Listing 2: 2-space body indentation, blank line after the
  optimiser setup, and the unbalanced
  `errD_fake = loss(discriminator(fake.detach(), fake_label)` exactly as
  printed. truth.md matches the page line for line.
- **pytorch p6, "The one-pool-per-stream design assumption ... perfor-mance
  ... freed on the CPU before"**. The worker did NOT render this page (their
  evidence says p5 onward rests on extractor agreement). The page prints this
  text exactly, with the line-end `perfor-|mance`; the passage ends at the
  italic *before*. It matches.
- **tarpit p1, "The classical ways ... object-oriented ... be-haviour ... —
  in its pure form — eschews state and side-effects all together."** It
  matches the page, including the line-end compound `object-|oriented` and
  the discretionary `be-|haviour`.

## Notes, not defects

- `norm` drops a space after a dash that follows a word character. So
  `input- heavy` passes the hyphen check. That matches the spec's intent (a
  line break is not a space), but the checks cannot tell a kept line-end
  hyphen with a stray space after it from a clean one.
- The truth covers passages, not the whole text, as the evidence states. A
  defect outside the 73 passages is caught only by `chars:*` and
  `absent:*`.
- The pypdf regeneration command writes to stdout, and pypdf printed no
  warnings. poppler printed "Invalid Font Weight" (fsr) and "wrong pointing
  object" (tarpit) on stderr. Both are harmless, and the outputs were
  identical.
