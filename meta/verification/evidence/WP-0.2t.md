# WP-0.2t comparator rework: glyph steps, raw link keys, annotation fail-louds, hairline

Base `art_directed` `7ee6381`. Answers the rejection in `WP-0.2s.verify.md`.
Owns `mag/src/parity*` and tests.

## What changed

1. **Glyph steps from the drift model** (`canon.rs`, `display.rs`). The
   model (plan, Tier E, per-glyph positions): WeasyPrint places each glyph
   by adding one integer-tick width per glyph, Typst adds exact widths, so
   each ADVANCE (the travel from one glyph's origin to the next glyph's
   origin, kerns included, because Pango carries one width per glyph) is
   rounded once and differs between legs by at most one tick. Two
   consequences, both now enforced:
   - An advance of exactly zero rounds to zero, so it adds nothing to k.
     Blanks and inked glyphs alike count one step only when their advance
     moves the pen on either leg.
   - Each glyph records the advances of its gap (the previous inked glyph
     of its show, then every blank, in show order). When both legs carry
     the same gap (same show-internal structure, same blank count), the
     advances pair one to one: each pair counts a step if either moves, and
     each pair must itself differ by at most one tick plus two quanta (the
     two quanta: every offset is rounded to the quantum on its own, and a
     paired advance difference is built from four offsets). A pair beyond
     that is not a rounding of one advance and is a violation.
   - When the legs do NOT carry the same gap (one leg writes blanks, the
     other a kern; different blank counts; a show boundary), no blank is
     agreed: the gap counts one step for the previous glyph's travel plus
     one for the blank run, and nothing if neither leg's pen moved.
   k is summed along the line in glyph order (keyed by the pair of line
   ids), replacing the per-leg `[inked, blanks, gap]` sums and the
   `min(blanks)` rule. The cumulative bound, the shape rule and the
   reported ratio are unchanged.
2. **Link keys are raw**: `/Border` (spec default `[0 0 1]` when absent),
   `/BS` (raw, `absent` distinct), `/C` (raw, `absent` distinct from `[]`
   and from every colour), and `/F & (Hidden 2 | Print 4 | NoView 32)`.
   Numbers are canonicalized to 0.01 so `1` and `1.0` agree. Equal raw keys
   draw the same, so no visible difference can pass; spec-equivalent
   spellings (`/BS <</W 3>>` vs `/Border [0 0 3]`) now fail, conservatively.
   The `/BS` style fail-loud is dropped: raw equality already covers it.
3. **Annotations**: a Link with `/AP` still fails loud; any other subtype
   WITHOUT `/AP` fails loud (its drawing is viewer-synthesized from `/IC`,
   `/DA`, `/Contents`); another subtype with `/AP` carries a SHA-256 of its
   whole appearance object graph (dictionaries sorted, `/Parent` skipped,
   stream bytes hashed, 32-level cap), and `compare_display` fails loud if a
   page's non-Link annotations are not byte-equal across legs.
4. **Hairline**: `pen(m, 0)` is `[-1, -1, -1]`, so `0 w` differs from any
   positive width however small.

Tests: `blanks_both_legs_carry_buy_no_visible_move` and
`a_link_border_follows_what_poppler_draws` un-ignored. The first gained the
stacked zero-width inked case (7000 on both legs, 5 pt: fail; no shift:
pass). The second's body is rewritten to the raw semantics this brief sets
(absent `/C` is its own value, so it is asserted DIFFERENT from black, not
equal as the verifier wrote; `/F` 2, 32 and 4 differ from no flag, `/F 1`
does not). `a_link_border_compares_what_is_drawn_with_spec_defaults`:
`border({}) == none` flipped to `!=` `/Border [0 0 0]` and `==` `[0 0 1]`;
the `/BS <</W 0>>` and `/BS <<>>` equalities flip to `!=` (raw).
`drift_inside_a_line...`: a 63-quantum jump inside one advance now fails
(it passed under the old cumulative-only rule); 10 quanta pass, 11 fail.
`blanks_on_both_legs_count_each...` replaced by
`a_step_counts_each_advance_both_legs_carry_that_moves_the_pen` (spread
one tick per advance passes, one quantum more fails; 10/11 quanta
concentrated pass/fail; zero-advance blanks count nothing; unagreed gap =
2 steps). New: `an_annotation_other_than_link_is_compared_only_by_byte_equal_appearance`,
`a_zero_width_hairline_is_not_any_positive_width`.

## Commands and results

Binaries: `mag-base` (release at `7ee6381`), `mag-new` (release, this WP),
both under `/Users/franguijarro/.claude/jobs/7d99e27f/tmp/wp02t-run/`.

**Adversarial replay** (`wp02t-run/h/all.py`, the verifier's `run.py` with
ROOT = main tree, over every prebuilt pair in `adv-v/cases`, 158 pairs,
`results-t.jsonl`, `all.txt`; exit 0). Every pair whose previous exit
(`adv-v/results-*.jsonl`) differs:

| pair | px | before | after | clause |
| --- | --- | --- | --- | --- |
| `blank_both_7000_5000_shift3` | 2661 | 0 | 1 | glyph |
| `blank_both_7000_shift5` | 2833 | 0 | 1 | glyph |
| `blank_both_real_width_7000_shift5` | 2833 | 0 | 1 | glyph (advance) |
| `inked_stack_7000_shift5` | 2833 | 0 | 1 | glyph (advance) |
| `hairline_zero_vs_tiny` | 835 | 0 | 1 | display |
| `square_annot_interior` | 234600 | 0 | 1 | fail loud (no /AP) |
| `freetext_da_colour` | 14335 | 0 | 1 | fail loud (no /AP) |
| `link_no_border_no_c_vs_zero` | 3296 | 0 | 1 | navigation, display |
| `link_c_absent_vs_empty_w1` | 3296 | 0 | 1 | same |
| `link_hidden_flag`, `link_noview_flag` | 9375 | 0 | 1 | same |
| `link_hidden_flag_black_default` | 9339 | 0 | 1 | same |
| `link_c_empty_vs_none_legit` | **9339** | 0 | 1 | same |
| `link_bs_vs_border_same_legit`, `link_bs_w0_vs_border0_legit`, `link_bs_dash_default` | 0 | 0 | 1 | conservative (raw) |

`link_c_empty_vs_none_legit` was filed as legitimate in the 0.2m-r
harness, but poppler draws 9339 px differently (absent `/C` is black, `[]`
is transparent): it was a wrong pass, now closed. Every other pair keeps
its outcome: all 0.2m-r and 0.2s adversarial pairs fail (`blank_inflation`
glyph, the two fail-louds, etc.), and every exit-0 pair is at most 2 px
apart except the two already accepted (`col_subhalf_step`, one level;
`strip_legit`, 126 px edge AA). 46 pairs pass.

**Floor** (`wp02t-run/floor.sh`, the 0.2s script, same legs and
fixtures; `floor.txt`, exit 0):

| row | before | after |
| --- | --- | --- |
| A-vs-A, control | 0, pass ratio 0 | same |
| **stairdrift** | 0, pass **0.2500**, 0 viol | **0, pass 0.2500, 0 viol** |
| drift / smoothdrift | 0 / 0, 0.2500 / 0.6250 | same |
| kern02 | 1, 10.2500, 5 viol | 1, 10.2500, 7 viol |
| kern001 | 1, 0.5625, 1 | same |
| advstep | 1, 0.6250, 1 | 1, 0.6250, 2 |
| advtail02 | 1, 10.2500, 7 | 1, 10.2500, 8 |
| glyphsub | 1, glyph pass, display fail 12 pages | same |

The failing rows gain per-advance violations; no passing row changes.

**`mag parity 010`** `--pre-rendered editions/010/render-2026-09-24T01-56-37
editions/010/render-2026-09-24T01-58-11` (the legs of `WP-0.2s.verify.md`
section 4), both exit 1, verdicts in `wp02t-run/p010-{base,new}/`:

| tier | before | after |
| --- | --- | --- |
| S page_count, boxes, text | pass | pass |
| S colour | fail, 9 pages | fail, 9 pages |
| S navigation | fail, 3 mismatches | **fail, 22 mismatches** |
| E display list | fail 58850 vs 58798, 43 pages | fail, **45 pages** |
| E glyph | fail, 58623 glyphs, 1802 shows, worst ratio 17294.0, 40 viol (capped) | fail, same counts, worst ratio 439077.1, 40 viol (capped) |
| G | max dy 0.220, 0 beyond | same |

Navigation and display move because of item 2: WeasyPrint writes
`/BS <</W 0>>` and typst `/Border [0 0 0]` (WP-0.2s.md item 7), which drew
the same and now compare unequal. **The typst template must write the
oracle's `/BS <</W 0>>` (and no `/C`, no `/F` difference) for 010 to pass
navigation.** The glyph worst glyph is the same page-7 glyph (325.27 pt
off, a different line on the two legs); its k fell from 75 to 4 because k
now restarts where the two legs' lines stop pairing. The first 40
violations now read as per-advance misses (page 3 glyph 1, 0.001465 pt,
which the old rule flagged too).

Gates: `cargo fmt --check` 0; `cargo clippy --all-targets -- -D warnings`
0; `tools/nocomments.py` 0; `cargo test --no-fail-fast` exit 0, 31 result
lines, 665 passed, 0 failed, 0 ignored (`wp02t-run/cargo-test.txt`);
after rebasing onto `a2be1d2` (WP-3.2b, WP-5.10; neither touches
`mag/src/parity*`): exit 0, 668 passed, 0 failed (`cargo-test2.txt`).

## What is and is not proven

**Proven.** Every adversarial pair of `WP-0.2m-r.verify.md` and
`WP-0.2s.verify.md` fails with this binary, including stacked zero-width
glyphs and equal blank counts on both legs; stairdrift is unchanged at
0.2500 with 0 violations; no passing floor row changes; the unit tests pin
the rules at their boundaries.

**Not proven.** The drift model is linear in the number of nonzero
advances, so it still admits, by construction, a line of thousands of
glyphs or blanks with a nonzero advance each whose paired advances differ
by one tick each in the same direction (7000 such advances accumulate
5 pt). That is what the model licenses, not a counting error; closing it
needs a physical cap (glyphs per line, or k bounded by the inked span),
which this WP did not add. The per-advance check covers only gaps both
legs carry identically; a gap that crosses a show boundary or differs in
blank structure is bounded cumulatively only. In paint-order (clash) runs k
sums in paint order rather than x order. The raster evidence is poppler at
300 dpi only. The 0 w marker enlarges a hairline's clip reach from 1 to 3
hundredths of a point, still below poppler's one device pixel (a
pre-existing gap, not measured here).
