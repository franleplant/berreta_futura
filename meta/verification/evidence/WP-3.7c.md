# WP-3.7c Tier E burn-down, last slice (WeasyPrint text serialization)

## Base

`art_directed` `3cb8ced` (WP-3.7a evidence), rebased onto `8965f1b` before landing
(QUEUE.md only). Detached worktree `.../tmp/wp37c`, target `.../tmp/wp37c-target`.
BEFORE legs come from the same worktree before any edit (010) and from a second
worktree at `8965f1b` (`.../tmp/wp37c-base`, fixtures). Every score below uses one
comparator; full violation counts come from a scratch build of the same
comparator with `violations.truncate(40)` lifted (`.../tmp/wp37c-tfull`, not
committed; the committed verdict prints the first 40).

**Status: blocked on one comparator decision, measured below.** 010 E display list
7 pages -> **0 (pass)**, navigation 2 -> **0 (pass)**, V2 fail -> **pass**, glyph
clause 23244 violations (worst excess 4.0383 pt) -> **90, worst excess 0.000000 pt**.
Every one of the 90 is a +-1 quantum (0.0000916 pt) blip that the typst leg
cannot remove (residual ledger). 56 = 56, WP-2.1 projection equal, staged ratchet
pass with 0 regressions, fixtures 902-905 improve on every tier and regress on none.

## What changed (owned files only)

1. **`typeset/text_shim.rs`, switch `WEASYPRINT_69`** (the declared compatibility
   shim; one call site in `template::pdf`, first of the frame passes). Per
   `TextItem`, from Typst's own glyphs and the font's `hmtx`:
   - written advance per glyph: `wid - trunc(wid + off - W)` in 1/1000 em of the
     Tf size, with `wid = round_half_even(pango(nominal) * 1000 / 1024 / px)`,
     `W` = Pango's glyph width, and `pango(v)` harfbuzz's `em_mult` scaling
     (`(v * ((units << 16) / upem) + 32768) >> 16`); nominal and kern scaled
     separately (WP-3.7b's model; the half-even rounding and `em_mult` close the
     last 1-unit misses, e.g. italic `ve` 494 -> 493 on p28).
   - `Tf` at `floor(px * 1024) / 1024` px (10 pt -> 9.999756 pt).
   - letter spacing (tracked runs, labelled `mag-track:<pt>` by the template):
     `ls = int(px * 1024)`, Pango's split `L = ls / 2`, `R = ls - L` (first glyph
     `+R`, middle `+L+R` with `x_offset L`, last `+L`), and the writer's offset
     `L / px` per mille (1.024 x the true value, as WeasyPrint 69 writes it). A run
     end in flow carries the box's trailing `letter-spacing`.
   - item positions on Pango's layout grid: every item after a text run on the
     same baseline moves by the accumulated `pango width - typst width`
     (`place` regions reset it), link rects grow with their text, `<mag-flush-right>`
     keeps the right edge, `<mag-spread>` redistributes `1fr` gaps as flexbox does.
2. **Template** (`template.typ`):
   - contents entry label untracked, as `.entry-label` is (it carried the kicker's
     0.45 pt: this was the page 3 "FEATURE glyphs paired with folio 0" 4.04 pt);
   - `pango-half` / `pango-center`: `edges()`, the contents folio and title offsets
     and the drop initial (`0.7 * 18.7 / 2 + pango-center`, replacing the fitted
     13.0992 pt) use Pango-rounded ascent/descent; the plain byline adds the same
     shift at 7.4 pt;
   - plain label box `100% - MEASURE-DELTA` (the header rail is 325 pt: the
     "label items sized by Inter /W" fixture entry was this 0.025 pt, distributed
     over three gaps);
   - illustrated label parts are their own runs (`own-run`, `h(0pt)`), as the
     spans are separate boxes in WeasyPrint;
   - tracked bodies, flush-right folio/running head and the spread label carry
     the labels the shim reads.
3. **`template.rs`**: chips pad `CHIP_PAD_X` (3 pt, `CODE-PAD-X`) past their run on
   each padded side instead of reading the typst bbox (the closing pad has zero
   advance at a line end); link runs merge within 1e-6 pt (shifted segments are
   float-equal, not bit-equal).

## Commands (exit status, key numbers)

```sh
M=../wp37c-target/debug/mag; F=../wp37c-tfull/debug/mag   # F: full-count comparator
$M parity 010 --run editions/010/run-2026-09-13T01-34-51          # BEFORE, exit 1
#   navigation 2 mismatches, E display 7 pages, glyph 40 (full count with $F: 23244, worst 4.0383 pt), V2 fail 0.008865
$M parity 010 --run editions/010/run-2026-09-13T01-34-51          # AFTER (final code), exit 1 (glyph clause only)
#   oracle leg cached editions/010/render-2026-09-24T06-38-07, typst leg render-2026-09-24T08-05-27 (reader.pdf 6709dc15...)
#   staged inputs fresh ae9d6daf..., ratchet: pass (54 checked, 54 recorded, 54 measured, 0 regressions)
#   S page_count 56 vs 56, boxes/text/color pass, navigation pass (0), G max dx 0.000 dy 0.006
#   E display list pass (58850 vs 58850, 0 pages), glyph positions fail (40 printed), V1 pass, V2 pass 0.000336
$F parity 010 --pre-rendered editions/010/render-2026-09-24T06-38-07 editions/010/render-2026-09-24T08-05-27
#   exit 1: 90 violations, worst excess 0.000000 pt, all "not one-signed and monotone", every nonzero entry |1| quantum, x only
uv run python mag/tests/typeset_oracle.py stage --request editions/010/render-2026-09-24T08-05-27/request.json --into $ST/live --artifact-root .   # exit 0, 57 inputs
uv run python mag/tests/typeset_oracle.py project --root $ST/live --edition 010 --publication-name "Berreta Futura" --out $ST/oracle-010.json    # exit 0
(cd mag && MAG_TYPESET_ROOT=$ST/live MAG_TYPESET_ORACLE=$ST/oracle-010.json MAG_TYPESET_PUBLICATION="Berreta Futura" cargo test --bin mag the_live_edition)
#   "68758 characters of reader text, 0 verbatim runs", ok
# fixtures: 3.7a's store copied in, typst leg rendered, scored with $F against 3.7a's oracle renders, moved out (scr/fx.sh)
(cd mag && cargo fmt --check && cargo clippy --all-targets -- -D warnings && cargo test)   # exit 0; 848 passed, 0 failed
```

Re-rendering the final tree twice gives the same reader.pdf bytes (`6709dc15...`).

## Fixtures (base `8965f1b` typst leg vs this WP, same oracle renders, full counts)

| fixture | E display list | E glyph violations (worst excess) | V2 |
|---|---|---|---|
| 902 | 1 page -> **pass** | 1897 (4.0383 pt) -> 18 (0.000000) | fail -> **pass** |
| 903 | 4 pages -> **1** | 1194 (4.0383) -> 15 (0.000000) | fail -> **pass** |
| 904 | pass -> pass | 689 (4.0383) -> 9 (0.000000) | fail -> **pass** |
| 905 | 2 pages -> **1** | 741 (4.0383) -> 6 (0.000000) | fail -> **pass** |

S text, color, navigation, page count pass on all four before and after; G max dx
0.021 -> 0.000 pt on 903/905. All 48 fixture glyph violations are the +-1 quantum
class. 900 and 901 have no oracle render (3.7a), so unit tests only.

## Residual ledger

| where | residual | cause | status |
|---|---|---|---|
| 010 glyph clause, 90 runs on 26 pages (fixtures 48) | a run's x difference sequence has isolated +-1 quantum (0.0000916 pt) entries, e.g. `[0,..,0,1,0,..]`; no glyph beyond its bound | sub-quantum start noise: body line starts differ by 5e-7 pt (pydyf writes px to 6 decimals, krilla writes f32), running heads by 2.05e-5 pt (WeasyPrint lays the 44 pt margin at 58.666639 px); in-line offsets agree to 1e-13 pt on body lines. The comparator quantizes `at` and `start` separately and `axis_shape` rejects a return to 0 | **blocked**: not removable on the typst leg (typst-pdf serializes f32, ulp 3.05e-5 pt at 300 pt, a third of a quantum). Needs a comparator decision (owner `mag/src/parity`): quantize `at - start` in f64, or read a single-quantum blip as 0 |
| 903 p4, 905 p6 display list | plain-opener QR bottom row y 392.864980 vs 392.865103 (903 p4), 373.864980 vs 373.865103 (905 p6): 0.000123 pt low, down from 0.00036; the oracle value sits 0.0001 above a 0.01 edge | byline was 0.00033 low from Pango's rounded half (fixed); left: title baseline 0.000057 low on every plain opener and the QR's own offset from the byline 0.00007 (p4) / 0.00001 (p8) | **blocked, cause not established** |

010 display list and navigation: empty.

## What is and is not proven

- Proven by measurement: every count above, BEFORE and AFTER on one comparator.
  The written-advance model plus letter spacing reproduces WeasyPrint's written
  positions to 1e-13 pt relative on 010 body lines (`scr/diff.py`, pikepdf, 1e-7
  pt print), and 010's display list is equal on every page.
- Rule 4, stated plainly: the shim makes Typst's PDF **carry WeasyPrint's
  errors**. Typst's exact harfbuzz advances, exact `Tf`, correct `x_offset` and
  exact layout positions are the correct values; the shim writes the kern
  truncation, the truncated size, the writer's 1.024x letter-spacing offset and
  Pango's 1/1024 px layout grid on purpose. The Pango-rounded vertical metrics are
  the same kind (template-level, not under the switch). Two template changes are
  real corrections, not emulation: the contents entry label had tracking the
  stylesheet does not set, and the plain label box was 0.025 pt wider than the
  325 pt rail.
- Tests pin the values WeasyPrint 69 writes, each with a control from the
  unshimmed frame: `a_kerned_pair_is_written_as_weasyprint_69_truncates_it` (`n`
  of `nt` at 10 pt: 626 before, 627 after, size 13653/1024*0.75),
  `a_letter_spaced_run_carries_pangos_half_spacing_and_the_writers_offset` (F 622,
  E offset 307/9.06640625 per mille, as the tap PDF writes `<0089>-33<>-33.8613`;
  control offset 0), `an_item_after_a_run_starts_where_pangos_grid_ends_the_run`
  (206.5 -> 206.492431640625, harfbuzz at scale 13653),
  `a_flush_right_item_keeps_its_right_edge`,
  `vertical_offsets_use_pangos_rounded_ascent_and_descent` (23 pt folio
  (30421 - 7575) / 2048 * 0.75; the exact-half control differs by > 2e-4; drop
  initial 13.099077 pt), `a_contents_entry_label_is_set_without_the_kickers_tracking`,
  and the plain-opener test's flush edge now 325.0 (was pinned at 325.025, the
  oracle's rail is 377.0079 - 52.0079).
- Removing the shim: `WEASYPRINT_69 = false` restores Typst's own advances and
  positions; the labels become inert. Two template pieces are not under the
  switch: `own-run` (without the shim, Typst drops tracking at those boundaries,
  1.04 pt each on illustrated labels) and `pango-center`.
- Not proven: the letter-spacing hinting branch (`ls` a multiple of 1024) and
  negative-tracking splitting are ported from Pango's source, not exercised on
  010; the flow rule (reset at `place`, accumulate otherwise) is checked on 010 and
  902-905 only; Spanish was not measured; the spread rule assumes the
  `space-between` label is the only flex line.
- Scratch (tap, extractors, fixture script): `.../tmp/wp37c-scr/`.
