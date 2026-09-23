# WP-0.2o per-glyph colour clause, display-list triage on 010

## Base and ownership

- Base `art_directed` `917aff1` (WP-0.2n), detached worktree, rebased onto
  `85d1d4c` before landing (see the tip section). Written:
  `mag/src/parity/display.rs`, `mag/src/parity/streams.rs`, one line in
  `mag/src/parity.rs` (a test fixture of the colour clause), and one line
  each in two critic tests that build a parity `Element::Text` by hand
  (`mag/src/critic.rs` test module `parity_seam_is_reachable_from_critic`,
  `mag/tests/critic_text.rs::text_show`): adding a field to the element
  does not compile otherwise. Neither critic test's assertions changed.

## Part 1: what changed

1. **The tracer records each glyph's Unicode unit.** `Element::Text` gains
   `units: Vec<String>` (one entry per shown code, from ToUnicode), marked
   `#[serde(skip)]` so the display list JSON, its comparison and every
   detail string are byte-identical; `s` is now `units.concat()`.
2. **Tier S colour compares per glyph, in reading order.** Per page, every
   inked glyph becomes `(unit, fill)`; the page's glyphs are ordered by
   device position, baseline top to bottom then left to right
   (`(-y, x)` at the 0.01 pt quantum from show origin plus the glyph's own
   device offset, stable in paint order for ties). The sequences must be
   equal, so a colour difference on any glyph fails, and a missing or extra
   glyph fails as a count difference. Segmentation into shows and the paint
   order of shows no longer matter. **Reading order is geometric, not paint
   order**, because paint order is not engine independent on 010: typst
   paints the running head first, WeasyPrint last (first run of this change
   in paint order failed 47 pages at glyph 0, "I" vs "B" of BERRETA).
3. **Which glyphs are compared.** A glyph whose embedded outline is empty
   (tracer `BLANK_GID`) paints nothing and is skipped; for a font without
   glyph identity (`UNRESOLVED_GID`, the non-Type0 path) a whitespace unit
   is skipped. A whitespace code that maps to an outline IS compared (test).
   Render mode 3 (invisible) is recorded as `invisible`, not as its fill, so
   visible vs invisible differs. **Stroke**: the tracer already fails loud
   on every text render mode except 0 and 3 (`render_mode`), so text is
   never stroked in an accepted PDF and has no stroke colour to compare.
4. **Rule/background paint** (path fill and stroke colours) is kept as a
   second per-page sequence in paint order, as before but no longer
   interleaved with text.
5. **The clause names its first difference per page** (`details`), so a
   colour difference is distinguishable from a character difference.

Tests (6 new): `colour_tests::the_same_glyph_colours_pass_whatever_the_segmentation_or_paint_order`
(one show vs three shows in another paint order, plus a running head);
`one_glyph_in_another_colour_fails_and_names_it` (one glyph VIOLET vs INK;
invisible vs INK); `a_missing_or_extra_glyph_fails` (14 vs 13 and 14 vs 15);
`only_a_glyph_without_an_outline_goes_uncompared`;
`a_rule_in_another_colour_still_fails` (229 vs 230);
`streams::tests::a_show_records_one_unicode_unit_per_glyph_in_order`
(Helvetica `[(ab) -250 (c)] TJ` gives units a, b, c).

## Commands and results

```sh
cd mag && cargo fmt --check && cargo clippy --all-targets -- -D warnings && cargo test
```
All exit 0. `cargo test`: 25 binaries, **362 passed, 0 failed**; 30 of the
passing runs are the 6 new tests (the parity sources compile into 5 crates).

Binaries in `/Users/franguijarro/.claude/jobs/7d99e27f/tmp/wp02o-bin/`:
`mag-base` = `917aff1`, `mag-new` = this diff.

### WeasyPrint floor

Script `/Users/franguijarro/.claude/jobs/7d99e27f/tmp/wp02o-floor.sh`
(WP-0.2n's, paths changed, run under bash), fixtures rebuilt from
`editions/010/render-2026-09-14T01-49-02` (self-check `stairdrift flat
steps 52549/68800 = 76.3794%`).

| row | base exit / digest | new exit / digest | verdict minus `tier_s.color` | colour base / new |
| --- | --- | --- | --- | --- |
| A-vs-A | 0 / `4af43e9bb160c9e4` | 0 / `2d6bbf37da806432` | identical | pass 1720 / pass 58987 |
| control | 0 / `dedacd632bef4888` | 0 / `e2e974f132df31b5` | identical | pass / pass |
| stairdrift | 0 / `27b196e4ec67cd90` | 0 / `043e45f673fef59c` | identical | pass / pass |
| kern001 (must fail) | 1 / `222691abb386631d` | 1 / `7d41dfa3488e3208` | identical | pass / pass |
| glyphsub (must fail) | 1 / `1264648922ffee54` | 1 / `7e1fde7684a4bcd9` | identical except `b_reader_sha256` | pass / pass |

Base digests for the first four equal WP-0.2n.md's. Digests move only
because the colour clause now carries `details` and counts glyphs. The
glyphsub fixture PDF differs between two `mkfixtures.py` runs (its input
hash is the only other changed field); that is why WP-0.2n's glyphsub
digest is not reproduced either. Flagged, not investigated: owner of
`mkfixtures.py`.

### `mag parity 010` (typst leg), before and after

`MAG_PARITY_OUT_DIR=output/parity-wp02o/typst-<bin> <bin> parity 010 --run editions/010/run-2026-09-13T01-34-51`
from the main tree; both exit 1; staged inputs fresh `d92eca1d...`.
Verdict sha256 prefixes: base `03749d703a6efad6`, new `7e2a60812f365510`;
field diff of the two with `tier_s.color` and `inputs` removed: identical.

| tier | before (`mag-base`) | after (`mag-new`) |
| --- | --- | --- |
| S page_count | pass 56 vs 56 | same |
| S boxes | pass (162 boxes, 54 rotations) | same |
| S text | fail, 30 of 54 pages | same |
| G | max dx 328.844, dy 367.872, G1 118, G2 201, 141 structure | same |
| **S color** | fail, 1733 entries, 47 pages (segmentation and colour mixed) | **fail, 58855 entries, 47 pages**, split below |
| S navigation | fail, 85 links, 22 mismatches | same |
| E glyph positions | fail, 3295 glyphs, worst ratio 8285.875, 40 violations | same |
| E display list | fail, 2189 vs 1629 elements, 52 pages | same |
| V | dims pass, V1 fail, V2 fail, worst 0.624220 | same |

New colour tier, by first difference (from `tier_s.color.details`):

| first difference | pages | meaning |
| --- | --- | --- |
| same glyph, other fill | 4, 7, 11, 17, 31, 36, 40, 46, 50 (9) | opener first letter or byline VIOLET `(49, 93, 140)` in WeasyPrint, INK in typst. Genuine, template |
| different character | 5, 8, 9, 12-16, 32, 33, 41-44, 47-49, 51-53 (20) | page content differs (pagination); Tier S text territory |
| glyphs all equal, paint 0 differs | 6, 18-29, 34, 37-39 (17) | WeasyPrint's first paint is a white content-area fill typst lacks; behind it every one of these pages also carries the rule colour below |
| glyphs all equal, rule 229 vs 230 | 3 (1) | see class h below |

On 18 pages every inked glyph now matches in character and colour. Before
this change the clause could not show that for any page.

## Part 2: display-list triage (evidence only, no clause change)

The display list reports only the FIRST difference, checked in the order
boxes, annotations, elements. Its three classes are therefore not classes
of page: an "annotations differ" page hides its element differences. The
triage below dumps both legs' full display lists (throwaway build of this
tree writing `PageDump`s, not committed; legs
`editions/010/render-2026-09-23T21-15-26` WeasyPrint and
`editions/010/render-2026-09-23T21-28-04` typst, which reproduce the
`--run` figures exactly: 2189 vs 1629, 52 pages) and flags every class on
every page. Scripts: `/Users/franguijarro/.claude/jobs/7d99e27f/tmp/wp02o-dump/tri2.py`, `tri3.py`.

First-difference split as reported: 26 `element 0` (pages 5, 6, 8, 9,
12-16, 24, 29, 32-34, 37, 38, 41-44, 47-49, 51-53), 21 `annotations
differ` (3, 4, 7, 11, 17-23, 25-28, 31, 36, 39, 40, 46, 50), 5 `element
count 2 vs 0` (10, 30, 35, 45, 54). Pages 2 and 55 pass.

| class | pages | renders differently? | proof | side |
| --- | --- | --- | --- | --- |
| C: different characters on the page | 27: the 20 above plus openers 4, 7, 11, 31, 40, 46, 50 (typst fits more body lines on the opener) | yes | glyph multisets differ | template (pagination) |
| S: same characters, other style | 17, 36 (byline colour) | yes | colour clause detail | template |
| L: same glyphs, other line breaks | 20, 22, 24, 25, 26, 29, 38 | yes | p38: WeasyPrint breaks before "Composer 1.5.", typst after it | template / line breaking (WP-1.2) |
| Y: same lines, other line positions | 3 (1 quantum, 0.01 pt), 6, 28, 34, 37, 39 (up to 15.52 pt) | yes | line y compared at 0.01 pt | template |
| **element count 2 vs 0** | 10, 30, 35, 45, 54 | **yes** | WeasyPrint draws a clipped 333 x 468 pt plate image, typst's page is empty: p10 raster at 300 dpi differs on 62.35% of pixels, typst page is one colour | template (full-page plates missing) |
| I: image missing in typst, other pages | tail art 325 x 108 pt on 9, 16, 29, 34, 39, 44, 49, 53; figures on 12, 42 and 37 (37 with its frame); opener image on the 9 opener pages (25 pages with the 5 above) | yes | image entries absent | template |
| P: other paints | 22 pages: PALE-VIOLET `(244, 241, 249)` inline-code fills (WP-0.2m finding 3), accent bar at another y (p6 9.65 pt), figure frame | yes | normalized path multisets differ | template |
| h: rule colour | 38 pages | **yes, by one 8-bit step** | WeasyPrint writes `0.88 0.89 0.9 rg`; 0.9 is exactly 229.5/255, typst-pdf can only write 230/255. pdftoppm -r 300 renders the rule `(224, 227, 229)` vs `(224, 227, 230)` (p38, pixels 833,116-117). The tracer's `round(0.9 * 255)` is 229 because 0.9 * 255 = 229.49999999999997 in f64 | oracle token: set the rule colour to an 8-bit-exact value in both (sanctioned oracle change). A comparator rounding change would hide a difference the pinned rasterizer shows |
| b: list bullet | 20-24, 26-29, 39 (10) | shape, no (where positions agree); position, yes on 24, 26, 28, 29 (lines moved) | WeasyPrint fills the 5 pt square clipped by a circle, typst fills the circle path. Circle inside square, so painted region = circle; control points differ by 1 quantum (Bezier constant) | representation, plus a 0.01 pt geometry difference: comparator normalization (a fill clipped to a region inside it = fill of that region) AND template (circle constant) |
| w: white first fill | 46 | no | first paint on the page, opaque `(1, 1, 1)` over an empty white page, alpha 1 (Tier E fails loud otherwise); nothing lies beneath it | representation. Either side: comparator drops an opaque white fill that precedes every other paint, or the template paints the same fill |
| k: clips | all 52 (typst emits no clip at all) | no, where the clip contains the paint | a clip C with painted area P inside C gives P ∩ C = P | representation: comparator drops a rectangular clip from an element's stack when the element's painted box lies inside it; a clip that cuts paint stays |
| O: paint order | the 26 `element 0` pages and others | no, for disjoint paints | running head painted first (typst) vs last (WeasyPrint); regions disjoint, and disjoint paints commute | representation. Preferred fix: template (typst `page.foreground` for the running head/folio) because Tier E forbids sorting; the comparator alternative is a canonical order that swaps only disjoint neighbours |
| R: rect as `re` vs `m l l l h` | every page with rules | no | PDF 32000-1 8.5.2.1 defines `x y w h re` as that closed 4-line subpath; one axis-aligned rectangle fills the same area under either winding rule | representation: comparator canonicalizes an axis-aligned 4-corner subpath |
| A1: annotation rect corner order | 18, 20-23, 25-28, 39 | no (links draw nothing; `/AP` fails loud) | WeasyPrint writes `[x1 ytop x2 ybottom]`; PDF 32000-1 7.9.5 allows any two opposite corners and tells readers to normalize | representation: comparator normalizes rects to `[llx lly urx ury]` |
| A2: link rect 1 unit (0.5 pt) off | 21, 26, 27, 39 | no render, navigation | extents differ after A1 | template |
| A3: links missing in typst | 3 (27 TOC links vs 0), 9 opener pages (2 vs 0), 19 (11 vs 9) | no render, navigation | counts | template |
| T: show segmentation, trailing space glyphs, 1-quantum origins | text pages whose lines match (18, 19, 21, 23, 27 checked) | spaces no (no outline); origins at 0.01 pt | typst `" about "` vs WeasyPrint `" about"`, origin 332.61 vs 332.60 | segmentation/spaces: representation (per-glyph comparison would remove it); origins: Tier E's 0.01 pt rule meeting WP-1.6's drift, not a representation class |

**No page differs only in representation.** Every one of the 52 carries at
least one rendering class (C, S, L, Y, I, P or h). The nearest are 18, 19,
21, 23, 27 (all glyphs, lines and line positions equal), which still carry
h, and 19/21/27 carry A2 or A3. So no normalization proposed here would
turn any 010 page green on its own; the template has work on every page.

## At the rebased tip (`85d1d4c`, after WP-3.2)

The branch moved while this WP ran (WP-3.2: openers, drop initial, TOC and
QR links). Rebased, `cargo test` 26 binaries **387 passed, 0 failed**, fmt
and clippy clean. `mag parity 010 --run ...` with the tip binary, exit 1:
S text fail 5 pages; G max dx 325.563, dy 167.672, G1 56, G2 141, 9
structure; **S color fail, 58855 entries, 47 pages: 0 glyph-colour, 3
character (42-44), 1 rule (3), 43 paint only**; S navigation 85 links, 22
mismatches; E glyph 2837 glyphs, worst ratio 7878.0, 40 violations; E
display list 2189 vs 1642, 52 pages (26 element 0, 21 annotations, 5 count
2 vs 0); V worst 0.624220.

Triage re-run on the tip legs (`render-2026-09-23T21-46-24` WeasyPrint,
`render-2026-09-23T21-47-23` typst; dumps reproduce 58855 / 2189 vs 1642 /
52): class C drops from 27 pages to 3 (42-44), A3 from 11 pages to 1 (19;
the TOC now has its 27 links and every opener its 2), A1 rises to 16
pages; L 12, Y 19, I 25, P 22, h 38, b 10 unchanged in kind. **Eight pages
(8, 13, 14, 15, 18, 33, 47, 48) now carry no rendering class except h**:
glyphs, lines and line positions equal, no image or other paint
difference. With the rule colour made 8-bit exact in the oracle and the
w, k, O, R and A1 normalizations above, those eight would be left with
only class T (trailing space glyphs, 1-quantum origins); that is the
nearest any 010 page is to Tier E.

## What is and is not proven

**Proven.**
- The colour clause is independent of show segmentation, of show paint
  order and of outline-less glyphs, and fails on one glyph's colour, on
  visible vs invisible, on a missing or extra glyph, and on a rule colour
  (unit tests).
- The WeasyPrint floor holds: A-vs-A, control, stairdrift, kern001 and
  glyphsub verdicts are identical outside the colour clause, which passes
  on all five before and after.
- On 010, 18 pages now match glyph for glyph in character and colour; the
  9 glyph-colour failures are genuine VIOLET vs INK differences; the rule
  colour difference renders (pdftoppm pixel values).
- Each display-list class's render effect as stated in the table, by the
  cited mechanism or measurement; every page carries a rendering class.

**Not proven.**
- The clip, white-fill and paint-order classes are argued from PDF
  semantics and checked on bounding boxes, not by rasterizing a normalized
  page (none exists: no page is representation-only).
- Glyph-level positions inside shows were not re-examined here (Tier E
  glyph positions covers them; its figures are unchanged).
- Geometric reading order assumes glyphs on different baselines never sit
  within 0.01 pt of each other in y; true of 010 (no rotated text, no
  overlapping baselines), stated rather than enforced.
- Nothing about the port's correctness beyond the classes listed.
