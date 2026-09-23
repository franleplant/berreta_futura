# WP-2.3 layout result and measure operations

## Base

`art_directed` `c58864d`, detached worktree at `.../tmp/wp23`, with the tracked
010 content run `editions/010/run-2026-09-13T01-34-51`.

**Status: target NOT met, measured gap committed (rule 6).** `article_pages`
and `editorial_pages` equal the oracle; `article_opener_fits` differs on 5 of 9
articles, and the typst side is the correct one to report false: on those five
opener pages the typst standfirst really runs past the content bottom (poppler
agrees to 0.001 pt, below). The defect is in the template's opener fitting,
owned by WP-3.2 ("opener-fit booleans exact"); this WP measures it and does not
fix it.

## What changed

- `mag/src/typeset/layout.rs` (new, owned): walks the typst introspector for the
  template's existing marks (`<mag-piece>`, `<mag-piece-end>`, `<mag-flow>` of
  kind figure, and `opener-parts` state updates) and builds:
  - `article_pages`, `editorial_pages`, `toc` from piece head/foot pages;
  - `article_opener_fits` for illustrated openers: the opener block is the first
    frame group after the piece mark on the head page, and it fits iff its INK
    bottom (deepest glyph descender or group bottom) is at or above the content
    bottom, `page height - MARGIN-BOTTOM` read from `template.typ` (540.276 pt);
  - `figures` (id, article, page, path, pixels, caption, credit; `box_points`
    and `effective_ppi` null, because the template draws an empty block and
    places no raster), `tail_arts` (declared, never printed), and the
    edition-derived fields (caps, modes, maxima);
  - the adapter-shaped `layouts` row (`totalPages`, `editorialPages`,
    `articlePages`, `articleOpenerFits`, `figureCount`, `criticResult`).
  Writes `<render>/<lang>/layout.json` (`{"layout": ...}`, the manifest's
  RenderLayout keys) for every operation, and `reader.pdf` for `render_edition`
  only. `measure_article` refuses an article the typst document did not place.
- `mag/src/render.rs` (owned): `--engine typst` now runs all three operations,
  writes `<render>/result.json` (the adapter's stdout shape), prints the summary
  and an operation-specific next step. **Defect fixed on the way:**
  `print_summary` read `layouts` as an object while the adapter emits a list,
  so every weasyprint render printed "(no 'layouts' field in adapter output)";
  it now prints the rows for both engines.
- **Outside Owns, disclosed, minimal and behaviour-preserving:**
  `mag/src/typeset/template.rs` splits `compile` into `document` + `pdf`
  (`compile` kept, test-only) so the layout reads the same compiled document the
  PDF is exported from; `mag/src/typeset/mod.rs` declares `pub(crate) mod layout;`,
  drops the `render_edition`-only refusal whose message named this WP, and hands
  the compiled document to `layout::report` (renamed `render_edition` to
  `run_request` since it now serves three operations). The typst reader PDF is
  byte-identical before and after (sha256 `02417ef3...0e0a` at base render
  `20-21-18` and at final render `20-44-26`).
- No template, emitter, parity or Python change.

## Commands

```sh
unset TYPST_ROOT; RUN=editions/010/run-2026-09-13T01-34-51
(cd mag && cargo build)
./mag/target/debug/mag render 010 --engine weasyprint --no-model --langs en --run $RUN  # -> render-2026-09-23T20-21-20, exit 0
./mag/target/debug/mag render 010 --engine typst --no-model --langs en --run $RUN       # -> render-2026-09-23T20-44-26, exit 0
shasum -a 256 editions/010/render-2026-09-23T20-44-26/en/reader.pdf                     # 02417ef38b39...d40e0a
# THE VERIFY CLAUSE: the field-by-field table under cargo test
(cd mag && MAG_LAYOUT_ORACLE=$PWD/../editions/010/render-2026-09-23T20-21-20/en/edition-manifest.json \
  MAG_LAYOUT_TYPST=$PWD/../editions/010/render-2026-09-23T20-44-26/en/layout.json \
  cargo test --bin mag the_live_field_by_field_table -- --nocapture)                    # exit 101: 5 target cells differ
# measure operations, both engines
./mag/target/debug/mag render 010 --operation measure_edition --engine weasyprint --no-model --langs en --run $RUN
uv run mag-render-adapter $PWD/editions/010/render-2026-09-23T20-34-51/request.json <scratch>/omeasure > oracle-measure.json  # exit 0
./mag/target/debug/mag render 010 --operation measure_edition --engine typst --no-model --langs en --run $RUN  # exit 0, result.json
./mag/target/debug/mag render 010 --operation measure_article --article towards-self-driving-codebases --engine typst ...  # exit 0
./mag/target/debug/mag render 010 --operation measure_article --article nope --engine typst ...  # refused: article 'nope' not found
# independent opener check: lowest word bottom (yMax) above the folio on each opener page
for pg in 4 7 11 17 31 36 40 46 50; do pdftotext -f $pg -l $pg -bbox <leg>/en/reader.pdf - \
  | grep "<word" | awk -F'"' '$4<569{print $8}' | sort -n | tail -1; done
# suite
(cd mag && cargo fmt --check && cargo clippy --all-targets -- -D warnings && cargo test)  # all exit 0
python3 tools/nocomments.py                                                                # "no comments", exit 0
```

Tool versions: rustc 1.96.0, uv 0.8.17, typst crates 0.15.1, poppler as in
WP-2.2c.

## Metrics

**Suite:** `cargo test` 272 passed, 0 failed across 25 test binaries (summed
from the `test result` lines); fmt and clippy clean. The first full run failed
`rust_helpers::no_helper_is_defined_in_two_modules` on a `pages` helper name
shared with `critic/rules.rs`; renamed to `span`, re-run green.

**Measure rows (oracle adapter stdout vs typst `result.json`, measure_edition):**
`totalPages` 56 = 56, `editorialPages` 0 = 0, `figureCount` 3 = 3,
`criticResult` not_run = not_run, `articlePages` 9 entries 0 differing,
`articleOpenerFits` 9 entries **5 differing**.

**Opener ink bottoms, typst leg** (layout measure; content bottom 540.276 pt)
against poppler's lowest word bottom on the same page, and the oracle's:

| page | article | typst measure | typst poppler | oracle poppler | fits (typst / oracle) |
|---|---|---|---|---|---|
| 4 | government-rails | 550.4308 | 550.4308 | 522.34 | false / true |
| 7 | countering-misuse | 521.65 | 521.63 | 519.37 | true / true |
| 11 | alignment-assessment | 570.1108 | 570.1108 | 528.25 | false / true |
| 17 | dario-amodei | 447.15 | 446.94 | 446.71 | true / true |
| 31 | scenarios | 550.4308 | 550.4308 | 534.97 | false / true |
| 36 | third-era | 478.35 | 478.14 | 477.91 | true / true |
| 40 | self-driving | 550.4308 | 550.4308 | 521.77 | false / true |
| 46 | deepseek | 554.9908 | 554.9908 | 526.33 | false / true |
| 50 | habitat | 537.25 | 537.23 | 521.77 | true / true |

On the fitting pages the measure is the block's frame bottom, slightly below
the last glyph, hence the 0.02 to 0.21 pt excess over poppler. On page 11 the
standfirst's last line bottoms at 570.11, 7 pt above the folio line.

**Why ink and not the block frame.** The typst unbreakable opener block's frame
is CLAMPED to the region: on page 4 its frame bottom is exactly 540.276 while
its last baseline sits at 547.21. A frame-height measure therefore reports all
nine as fitting. Perturbation, run: replacing the ink bottom by the frame
bottom makes `the_opener_fit_flips_between_two_standfirsts_one_word_apart` fail
("the sweep bounds must straddle the fit"), because a 1000-word standfirst then
"fits". Restored, green.

**Why the end mark could not be the state update's position.** Typst holds
pending introspection tags until the next frame is pushed, so the
`opener-parts.update(_ => none)` after the opener lands at y 42.0004 on the
NEXT page on all nine (measured). The measure uses the piece mark's tag and the
next sibling group instead.

## The field-by-field table

Output of `the_live_field_by_field_table` (oracle = WeasyPrint manifest
`layout`, typst = `layout.json`). Owners: WP-3.1 body flow, WP-3.2 openers and
TOC, WP-3.4 figures, plates and ornaments; WP-2.3 for edition-derived fields
(all equal).

| field | key | oracle | typst | verdict |
|---|---|---|---|---|
| article_content_modes | an-alignment-assessment-of-recent-cybersecurity | "article" | "article" | equal |
| article_content_modes | countering-misuse-of-ai-september-2026-anthropic | "article" | "article" | equal |
| article_content_modes | dario-amodei-we-must-pace-the-frontier | "verbatim" | "verbatim" | equal |
| article_content_modes | deepseek-v4-1-flash-pushing-the-limits-of-kv-cac | "article" | "article" | equal |
| article_content_modes | government-rails-site-hit-hours-after-cve-patch | "article" | "article" | equal |
| article_content_modes | rapidly-scaling-online-storage-to-serve-over-1-b | "article" | "article" | equal |
| article_content_modes | scenarios-for-our-economic-future | "article" | "article" | equal |
| article_content_modes | the-third-era-of-ai-software-development | "verbatim" | "verbatim" | equal |
| article_content_modes | towards-self-driving-codebases | "article" | "article" | equal |
| article_opener_fits | an-alignment-assessment-of-recent-cybersecurity | true | false | DIFFERS, owner WP-3.2 |
| article_opener_fits | countering-misuse-of-ai-september-2026-anthropic | true | true | equal |
| article_opener_fits | dario-amodei-we-must-pace-the-frontier | true | true | equal |
| article_opener_fits | deepseek-v4-1-flash-pushing-the-limits-of-kv-cac | true | false | DIFFERS, owner WP-3.2 |
| article_opener_fits | government-rails-site-hit-hours-after-cve-patch | true | false | DIFFERS, owner WP-3.2 |
| article_opener_fits | rapidly-scaling-online-storage-to-serve-over-1-b | true | true | equal |
| article_opener_fits | scenarios-for-our-economic-future | true | false | DIFFERS, owner WP-3.2 |
| article_opener_fits | the-third-era-of-ai-software-development | true | true | equal |
| article_opener_fits | towards-self-driving-codebases | true | false | DIFFERS, owner WP-3.2 |
| article_page_caps | an-alignment-assessment-of-recent-cybersecurity | 7 | 7 | equal |
| article_page_caps | countering-misuse-of-ai-september-2026-anthropic | 7 | 7 | equal |
| article_page_caps | dario-amodei-we-must-pace-the-frontier | 10 | 10 | equal |
| article_page_caps | deepseek-v4-1-flash-pushing-the-limits-of-kv-cac | 7 | 7 | equal |
| article_page_caps | government-rails-site-hit-hours-after-cve-patch | 7 | 7 | equal |
| article_page_caps | rapidly-scaling-online-storage-to-serve-over-1-b | 7 | 7 | equal |
| article_page_caps | scenarios-for-our-economic-future | 7 | 7 | equal |
| article_page_caps | the-third-era-of-ai-software-development | 10 | 10 | equal |
| article_page_caps | towards-self-driving-codebases | 7 | 7 | equal |
| article_pages | an-alignment-assessment-of-recent-cybersecurity | 6 | 6 | equal |
| article_pages | countering-misuse-of-ai-september-2026-anthropic | 3 | 3 | equal |
| article_pages | dario-amodei-we-must-pace-the-frontier | 13 | 13 | equal |
| article_pages | deepseek-v4-1-flash-pushing-the-limits-of-kv-cac | 4 | 4 | equal |
| article_pages | government-rails-site-hit-hours-after-cve-patch | 3 | 3 | equal |
| article_pages | rapidly-scaling-online-storage-to-serve-over-1-b | 4 | 4 | equal |
| article_pages | scenarios-for-our-economic-future | 4 | 4 | equal |
| article_pages | the-third-era-of-ai-software-development | 4 | 4 | equal |
| article_pages | towards-self-driving-codebases | 5 | 5 | equal |
| article_terminal_balance |  | {} | {} | equal |
| cover_art_size_points |  | null | null | equal |
| design_direction |  | "WeasyPrint / A5 fold proof" | "Typst / A5 fold proof" | DIFFERS, owner none: engine identity label, by design |
| editorial_pages |  | null | null | equal |
| figures | 0.article_id | "an-alignment-assessment-of-recent-cybersecurity" | "an-alignment-assessment-of-recent-cybersecurity" | equal |
| figures | 0.box_points | [64.454,248.276,289.14,205.0] | null | DIFFERS, owner WP-3.4 |
| figures | 0.caption | "The four incidents in which a Claude model, told it had no  | "The four incidents in which a Claude model, told it had no  | equal |
| figures | 0.credit | "Figure by Anthropic; source: An alignment assessment of rec | "Figure by Anthropic; source: An alignment assessment of rec | equal |
| figures | 0.effective_ppi | 498.0 | null | DIFFERS, owner WP-3.4 |
| figures | 0.id | "four-incidents" | "four-incidents" | equal |
| figures | 0.page | 12 | 12 | equal |
| figures | 0.path | "library/sources/an-alignment-assessment-of-recent-cybersecu | "library/sources/an-alignment-assessment-of-recent-cybersecu | equal |
| figures | 0.pixel_dimensions.0 | 2000 | 2000 | equal |
| figures | 0.pixel_dimensions.1 | 1418 | 1418 | equal |
| figures | 1.article_id | "the-third-era-of-ai-software-development" | "the-third-era-of-ai-software-development" | equal |
| figures | 1.box_points | [44.0,80.259,333.008,187.317] | null | DIFFERS, owner WP-3.4 |
| figures | 1.caption | "Agent usage in Cursor has grown over 15x in the last year,  | "Agent usage in Cursor has grown over 15x in the last year,  | equal |
| figures | 1.credit | "Chart by Cursor; source: The third era of AI software devel | "Chart by Cursor; source: The third era of AI software devel | equal |
| figures | 1.effective_ppi | 518.9 | null | DIFFERS, owner WP-3.4 |
| figures | 1.id | "agent-usage-growth" | "agent-usage-growth" | equal |
| figures | 1.page | 37 | 37 | equal |
| figures | 1.path | "library/sources/the-third-era-of-ai-software-development-73 | "library/sources/the-third-era-of-ai-software-development-73 | equal |
| figures | 1.pixel_dimensions.0 | 2400 | 2400 | equal |
| figures | 1.pixel_dimensions.1 | 1350 | 1350 | equal |
| figures | 2.article_id | "towards-self-driving-codebases" | "towards-self-driving-codebases" | equal |
| figures | 2.box_points | [42.52,213.959,333.008,187.317] | null | DIFFERS, owner WP-3.4 |
| figures | 2.caption | "The design that held, a root planner spawning subplanners s | "The design that held, a root planner spawning subplanners s | equal |
| figures | 2.credit | "Diagram by Cursor; source: Towards self-driving codebases." | "Diagram by Cursor; source: Towards self-driving codebases." | equal |
| figures | 2.effective_ppi | 518.9 | null | DIFFERS, owner WP-3.4 |
| figures | 2.id | "recursive-planners" | "recursive-planners" | equal |
| figures | 2.page | 42 | 42 | equal |
| figures | 2.path | "library/sources/towards-self-driving-codebases-3fd7b9ca/med | "library/sources/towards-self-driving-codebases-3fd7b9ca/med | equal |
| figures | 2.pixel_dimensions.0 | 2400 | 2400 | equal |
| figures | 2.pixel_dimensions.1 | 1350 | 1350 | equal |
| maximum_article_pages |  | 7 | 7 | equal |
| maximum_editorial_pages |  | 2 | 2 | equal |
| tail_arts | 0.article | "government-rails-site-hit-hours-after-cve-patch" | "government-rails-site-hit-hours-after-cve-patch" | equal |
| tail_arts | 0.declared | true | true | equal |
| tail_arts | 0.drop_reason | "the article's last page leaves -15.7pt of open tail room be | "the typst template sets no tail art" | DIFFERS, owner WP-3.4 |
| tail_arts | 0.height_points | null | null | equal |
| tail_arts | 0.printed | false | false | equal |
| tail_arts | 1.article | "countering-misuse-of-ai-september-2026-anthropic" | "countering-misuse-of-ai-september-2026-anthropic" | equal |
| tail_arts | 1.declared | true | true | equal |
| tail_arts | 1.drop_reason | null | "the typst template sets no tail art" | DIFFERS, owner WP-3.4 |
| tail_arts | 1.height_points | 108.3333 | null | DIFFERS, owner WP-3.4 |
| tail_arts | 1.printed | true | false | DIFFERS, owner WP-3.4 |
| tail_arts | 2.article | "an-alignment-assessment-of-recent-cybersecurity" | "an-alignment-assessment-of-recent-cybersecurity" | equal |
| tail_arts | 2.declared | true | true | equal |
| tail_arts | 2.drop_reason | null | "the typst template sets no tail art" | DIFFERS, owner WP-3.4 |
| tail_arts | 2.height_points | 108.3333 | null | DIFFERS, owner WP-3.4 |
| tail_arts | 2.printed | true | false | DIFFERS, owner WP-3.4 |
| tail_arts | 3.article | "dario-amodei-we-must-pace-the-frontier" | "dario-amodei-we-must-pace-the-frontier" | equal |
| tail_arts | 3.declared | true | true | equal |
| tail_arts | 3.drop_reason | null | "the typst template sets no tail art" | DIFFERS, owner WP-3.4 |
| tail_arts | 3.height_points | 108.3333 | null | DIFFERS, owner WP-3.4 |
| tail_arts | 3.printed | true | false | DIFFERS, owner WP-3.4 |
| tail_arts | 4.article | "scenarios-for-our-economic-future" | "scenarios-for-our-economic-future" | equal |
| tail_arts | 4.declared | true | true | equal |
| tail_arts | 4.drop_reason | null | "the typst template sets no tail art" | DIFFERS, owner WP-3.4 |
| tail_arts | 4.height_points | 108.3333 | null | DIFFERS, owner WP-3.4 |
| tail_arts | 4.printed | true | false | DIFFERS, owner WP-3.4 |
| tail_arts | 5.article | "the-third-era-of-ai-software-development" | "the-third-era-of-ai-software-development" | equal |
| tail_arts | 5.declared | true | true | equal |
| tail_arts | 5.drop_reason | null | "the typst template sets no tail art" | DIFFERS, owner WP-3.4 |
| tail_arts | 5.height_points | 108.3333 | null | DIFFERS, owner WP-3.4 |
| tail_arts | 5.printed | true | false | DIFFERS, owner WP-3.4 |
| tail_arts | 6.article | "towards-self-driving-codebases" | "towards-self-driving-codebases" | equal |
| tail_arts | 6.declared | true | true | equal |
| tail_arts | 6.drop_reason | null | "the typst template sets no tail art" | DIFFERS, owner WP-3.4 |
| tail_arts | 6.height_points | 108.3333 | null | DIFFERS, owner WP-3.4 |
| tail_arts | 6.printed | true | false | DIFFERS, owner WP-3.4 |
| tail_arts | 7.article | "deepseek-v4-1-flash-pushing-the-limits-of-kv-cac" | "deepseek-v4-1-flash-pushing-the-limits-of-kv-cac" | equal |
| tail_arts | 7.declared | true | true | equal |
| tail_arts | 7.drop_reason | null | "the typst template sets no tail art" | DIFFERS, owner WP-3.4 |
| tail_arts | 7.height_points | 108.3333 | null | DIFFERS, owner WP-3.4 |
| tail_arts | 7.printed | true | false | DIFFERS, owner WP-3.4 |
| tail_arts | 8.article | "rapidly-scaling-online-storage-to-serve-over-1-b" | "rapidly-scaling-online-storage-to-serve-over-1-b" | equal |
| tail_arts | 8.declared | true | true | equal |
| tail_arts | 8.drop_reason | null | "the typst template sets no tail art" | DIFFERS, owner WP-3.4 |
| tail_arts | 8.height_points | 108.3333 | null | DIFFERS, owner WP-3.4 |
| tail_arts | 8.printed | true | false | DIFFERS, owner WP-3.4 |
| toc | an-alignment-assessment-of-recent-cybersecurity | 11 | 11 | equal |
| toc | countering-misuse-of-ai-september-2026-anthropic | 7 | 7 | equal |
| toc | dario-amodei-we-must-pace-the-frontier | 17 | 17 | equal |
| toc | deepseek-v4-1-flash-pushing-the-limits-of-kv-cac | 46 | 46 | equal |
| toc | government-rails-site-hit-hours-after-cve-patch | 4 | 4 | equal |
| toc | rapidly-scaling-online-storage-to-serve-over-1-b | 50 | 50 | equal |
| toc | scenarios-for-our-economic-future | 31 | 31 | equal |
| toc | the-third-era-of-ai-software-development | 36 | 36 | equal |
| toc | towards-self-driving-codebases | 40 | 40 | equal |
cells: 126, equal: 89, differing: 37

Non-equal cells, by owner:
- **WP-3.2, `article_opener_fits`, 5 cells: THE TARGET GAP.** The typst opener
  overflows its page on those five (above). Equality with the oracle is the
  target; the oracle's `true` is also the correct value, so the fix is the
  template's opener fitting, not the measure.
- **WP-3.4, `figures.*.box_points` and `effective_ppi`, 6 cells:** null on
  typst because `figure-image` is an empty block; no raster box exists to
  measure. Figure `page` equals the oracle on all 3 (12, 37, 42).
- **WP-3.4, `tail_arts`, 25 cells:** the template's `tail-art()` is `none`, so
  typst prints no tail art; the oracle prints 8 of 9 (article 0 dropped for
  -15.7 pt of room, and typst agrees it is unprinted).
- **`design_direction`, 1 cell, NO Phase 3 owner:** "Typst / A5 fold proof"
  against "WeasyPrint / A5 fold proof". It names the engine, has no consumer in
  `src/magazine` or `mag/src` (grep, exit 0 with only the producer lines), and
  I did not make typst claim to be WeasyPrint. Needs an orchestrator decision
  (accept as identity, or pick a shared label).

Equal and correct by construction: `toc` (4, 7, 11, 17, 31, 36, 40, 46, 50,
the same starts WP-2.2c located by title text), `article_pages` (sum 46),
`editorial_pages` null (010 has none), caps, modes, maxima,
`cover_art_size_points` null, `article_terminal_balance` {}.

## Tests added (all in `mag/src/typeset/layout.rs`)

- `the_live_field_by_field_table`: the Verify clause. Env-gated
  (`MAG_LAYOUT_ORACLE`, `MAG_LAYOUT_TYPST`), prints "skipped, env not set" in
  the hermetic suite. Asserts the oracle's opener fits are NON-EMPTY before
  comparing (WP-0.0c), that every non-equal field has an owner, and that the
  three target fields are equal. Today it fails on the 5 cells above.
- `the_verdict_discriminates_each_rule`: self-compare passes; owned
  differences pass; a one-cell change in each of the three target fields fails
  naming the field; an unowned field fails; an empty oracle opener map fails
  naming WP-0.0c.
- `the_opener_fit_flips_between_two_standfirsts_one_word_apart`: binary search
  on a synthetic illustrated piece; fits at 70 words, spills at 71. A
  THRESHOLD-DISCRIMINATING pair one input step apart.
- `the_fixture_pieces_measure_as_emitted` (900: editorial, plain openers,
  figure, section, declared tail art) and
  `the_illustrated_fixture_opener_fits_its_page` (901, bottom 447.15).

## What is and is not proven

- Proven: `--engine typst` emits the full RenderLayout key set (the manifest's
  13 `layout` keys, including `tail_arts`) and runs `measure_article` and
  `measure_edition` natively; on 010 `article_pages` (9/9) and `editorial_pages`
  equal the oracle; `article_opener_fits` is compared against a non-empty
  oracle (9 entries) and differs on 5, each confirmed as a real overflow by
  poppler independently of the introspector.
- Proven: the ink measure is load-bearing (perturbation above) and the fit
  guard has a one-word straddling pair.
- Not proven: fit on PLAIN openers. They carry no opener-end mark and the
  template gives no block boundary to read, so plain-opener articles are left
  out of `article_opener_fits` with a warning naming WP-3.2 (fixture 900 shows
  it). 010 has none. On such an edition the table shows each as a differing
  `article_opener_fits` cell (typst null) and the target assertion fails, so
  the gap cannot pass silently.
- Not proven: ink bottom ignores frame transforms and shape geometry (only
  groups and glyph descenders); the opener block has neither transforms nor
  shapes below its text, and poppler agrees on all nine pages.
- Not proven: figure boxes and PPI, tail arts (no raster is placed, WP-3.4).
- Branches 010 cannot reach, covered by fixture: editorial and section pieces,
  plain openers, undeclared tail art (900); a spilling illustrated opener
  (synthetic). Not covered: an editorial over its cap (the typst side reports
  the span and enforces no cap), a piece missing its end mark (bails, untested).
