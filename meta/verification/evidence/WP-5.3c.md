# WP-5.3c critic faults

## Base

Worktree `git worktree add --detach <scratch>/wp53c art_directed` at
`3061854`. Owns `mag/tests/critic_*`: the only files added are
`mag/tests/critic_faults.rs` and this evidence. No `src/`, Cargo, or
`critic_rules*` file changed, so WP-5.3b-iii's regenerating block 1 is still
safe to replay and is NOT marked superseded.

Rebased once, onto `917aff1`, before landing. The new commits changed
`mag/src/parity/display.rs` and `streams.rs` (WP-0.2n), which this test
includes as the tracer. So the commands below were re-run on the rebased tree:
clippy exit 0, `cargo test` exit 0 (26 binaries, 347 passed, 0 failed), full
mode exit 0 with the same 7 variants, the same issue counts and 42 of 42
probes. The discrimination probes ran before the rebase, on `3061854`.

## What was built

`mag/tests/critic_faults.rs` (830 lines, sha256 `bf1cca26...414e6`). It
takes the four PDFs and the manifest of the live 010 render, applies faults
with byte-level `lopdf` edits, runs BOTH critics on each variant (Python
`inspect_render` with its own pypdf text, run through `uv run python -c` in
parallel child processes; the Rust `rules::inspect_render` with the tracer),
and checks three things for each variant:

1. Python and Rust give the same `{result, issues}`, compared on whole rows:
   code, severity, page and message.
2. The issue set `(code, severity, page)` matches an expectation AUTHORED
   FROM THE RULE: the 010 baseline plus the codes the fault must add. Only the
   four baseline rows are copied from the shipped `render-critic.json`; every
   delta is derived from the rule each site enforces.
3. Field probes (42 in total) show each fault LANDED as designed, on both
   critics: `body_text_lines`, `blank`, `ink_free`, `ink_ratio`,
   `text_characters`, `standalone_punctuation_lines`, `tail_band` and
   `text_order_matches` on the pages and sides that were faulted.

It is env-gated on `MAG_CRITIC_FAULTS_RENDER_DIR` and prints its mode. A
second, ungated test (`authored_expectations_follow_the_imposition_plan`)
checks the imposition premises the expectations depend on, and that every
declared gap is consistent with the rule set.

| variant | edit | added by the rule |
| --- | --- | --- |
| resaved | none; all four PDFs load and save through lopdf | nothing (control for the surgery itself) |
| swapped-sheets | booklet sides 5 and 7 exchanged, interior sides 3 and 5 exchanged, cover side re-imposed as (1, 56) | `booklet-page-order`, `interior-booklet-page-order`, `cover-booklet-page-order` |
| half-swaps | booklet side 5 and cover side MIRRORED (halves swap position, paint order kept); interior side 3 REPAINTED (paint order swapped, position kept) | `booklet-page-order`, `cover-booklet-page-order` (the mirrored sides are wrong on paper); nothing for the repainted side (it looks correct) |
| missing-tail-band | the tail image `Do` removed from p44, manifest still says printed | `article-tail-gap` p44 (trailing blank from 338 pt to the live bottom at 576 pt, about 238 pt, over the 196.5 pt threshold of 0.35 x 561.5) |
| low-ppi-figure | the p42 figure and its SMask box-averaged 16x to 150x84 (about 32 ppi), manifest `effective_ppi` and `pixel_dimensions` updated | nothing: no render-critic site reads resolution |
| text-fields | see below | 9 direct rows plus the 3 order codes as consequences |
| raster-halves | ink mark on booklet side 2; cover side emptied and given 6 characters of invisible text | `inside-cover-booklet-not-blank` s2 (raster half); `cover-booklet-page-order` as a consequence; `blank-cover-booklet-side` must stay SILENT (text half) |

text-fields, per site:

| site | fires | stays silent (the straddle) |
| --- | --- | --- |
| `inside-cover-reader-not-blank` | p2 invisible text (text half), p55 ink mark (raster half) | |
| `blank-page` | p13 emptied | p14 emptied plus invisible text (text half of the conjunction) |
| `orphan-punctuation` | p19 line `.`, p21 line U+2026 | p20 line `a.` |
| `article-stub-last-page` | p49 cut to its first 4 text lines | p44 cut to its first 5 lines, one line away |
| `inside-cover-booklet-not-blank` | side 2 invisible text (text half) | |
| `blank-booklet-side` | side 9 emptied | side 11 emptied plus invisible text |
| `blank-cover-booklet-side` | cover side emptied | |

Injected text uses a standard-14 Helvetica resource in render mode 3
(invisible), so it adds text without adding ink and cannot shift the live area.

## Commands

From the worktree root, with `CARGO_TARGET_DIR` set to a scratch target:

```sh
cargo fmt --manifest-path mag/Cargo.toml --check
cargo clippy --manifest-path mag/Cargo.toml --all-targets -- -D warnings
uv run python tools/nocomments.py
cargo test --manifest-path mag/Cargo.toml
cargo test --manifest-path mag/Cargo.toml --test critic_faults both_critics -- --nocapture
MAG_CRITIC_FAULTS_RENDER_DIR="$HOME/code/magazine/editions/010/render-2026-09-14T01-49-02/en" \
  cargo test --release --manifest-path mag/Cargo.toml --test critic_faults both_critics -- --nocapture
```

The full mode is run with `--release` because the debug-build Rust critic
made a seven-variant run take over nine minutes. Release takes about 131 s.

## Results

- fmt exit 0; clippy exit 0, no warnings; nocomments exit 0.
- `cargo test` (debug, gate unset): exit 0, 26 binaries, 324 passed, 0
  failed.
- Skipped mode prints `MODE: skipped, MAG_CRITIC_FAULTS_RENDER_DIR unset`.
- Full mode: exit 0, `MODE: full`, 7 of 7 variants have identical Python and
  Rust decisions (4, 7, 5, 5, 4, 16 and 6 issues), all 42 probes equal on both
  critics, and every issue set equals the authored expectation, with the
  declared gaps in half-swaps.
- The faults were checked by eye on the Python-side rasters: the mirrored
  booklet side 5 and cover show their halves exchanged, p44 in text-fields
  keeps five lines above its tail band, p44 in missing-tail-band has no tail
  art and its text is intact, and the p42 figure is visibly degraded.

Tool versions: pdftoppm 25.08.0, pypdf 6.14.2, Pillow 12.3.0.

### Discrimination probes

Each probe mutated one source line in the worktree, ran the full mode and
restored the line from a pristine copy. `git status` showed only the new test
file afterwards.

| mutation | caught as |
| --- | --- |
| Rust `inspect.rs` `ink_free` drops `&& stripped.is_empty()` | Rust only: `blank-page` p14, `blank-booklet-side` s11 (text-fields), `blank-cover-booklet-side` s1 (raster-halves), plus the probes |
| Rust `STUB_BODY_LINE_MINIMUM` 5 -> 6 | Rust only: `article-stub-last-page` p44, the silent side of the straddle |
| Python `"blank": pure_white` (text half dropped) | Python loses `inside-cover-reader-not-blank` p2 and `inside-cover-booklet-not-blank` s2 |
| Python `_STANDALONE_PUNCTUATION` loses U+2026 | Python loses `orphan-punctuation` p21, and the p21 probe fails |

The first three ran together in one run (exit 101) and had separate
signatures; the fourth ran alone (exit 101).

## Findings for the orchestrator

1. **Both critics read spread order in PAINT order, not in position on the
   page.** A side whose halves are exchanged on paper but painted in the
   original order passes `booklet-page-order` and `cover-booklet-page-order`
   (MISSED). A side that is correct on paper but painted right half first
   fails `interior-booklet-page-order` (FALSE ALARM). Python and Rust agree
   exactly, so this is a defect in the rule's implementation, not in the port
   (rule 4: agreement is not correctness). The test records these as declared
   gaps (`missed`, `spurious`). It fails if either critic starts deciding by
   the rule, so fixing the defect forces the gap entries to be removed. Where
   to fix it: the spread-text join in `rules.rs::spread_text` and pypdf
   extraction in Python. A geometric order (by x within the side) would close
   both.
2. **`cover-booklet-inside-not-blank` is dead code in both critics.**
   `cover_wrap_plan` keeps only the outside side, so the set
   `cover_booklet_inside_sides` is empty for every page count. The ungated
   test proves this for 4 to 64 pages. No PDF fault can reach the site, since
   it is keyed on the plan and not on the file. Of the eleven text-fed sites,
   ten are faulted here and this one cannot be.
3. **"Low-ppi figure" is not a render-critic fault.** No render-critic site
   reads resolution; the check lives in `preflight.py`
   (`low_resolution_figures`, WP-5.5b). The variant only proves that both
   critics stay silent on such a figure.
4. **The tracer refuses two inputs that are valid PDF**, found while building
   the faults: an SMask whose size differs from its image ("SMask geometry
   mismatch"), and a standard-14 font with no `/Widths` ("standard-14 AFM
   metrics are not implemented"). Both fail loudly, which is correct. The fault
   suite works around them by shrinking the SMask too and by writing
   `/Widths`. Production 010 has neither case. This belongs to comparator
   territory (`parity/streams.rs`).

## What is and is not proven

PROVEN, on edition 010 English with its faults:

- Python and Rust give identical decisions, including messages, on 7 variants
  and 47 issue rows (19 beyond the baseline).
- Each of the three `text_order_matches` sites fires on a real imposition
  fault (swapped sheets, and a re-imposed cover).
- `blank` and `ink_free` are faulted on BOTH halves of each conjunction:
  - text half: p2, p14, side 2, side 11 and the cover side;
  - raster half: p55, side 2, p13, side 9 and the cover side.
- `standalone_punctuation_lines` is exercised for the first time with a
  non-empty value, on both sides, including the U+2026 member. This is the
  only evidence for this field (see revision 20).
- `body_text_lines` is straddled one line apart (5 stays silent, 4 fires),
  with both counts probed on both critics. The threshold mutation proves the
  straddle discriminates.
- A missing tail band produces `article-tail-gap` on both critics.
- Surgery artifacts: the resaved control reproduces the baseline exactly.

NOT PROVEN:

- The paint-order gaps above: the rule is NOT met there, and this is measured
  rather than hidden.
- `cover-booklet-inside-not-blank`: unreachable (finding 2).
- The Python and Rust text sources on the injected Helvetica text are shown
  only for ASCII and U+2026, and only as single-line shows.
- The fault expectations are authored from the rule, but the baseline four are
  transcribed from the shipped report.
- As WP-5.3b-iii's blindness table warns, a code-level suite cannot see crop
  geometry, `centered` or crop rasters. This suite adds field probes, not
  those.
- Anything outside 010 English.
