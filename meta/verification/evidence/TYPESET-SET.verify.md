# TYPESET-SET verify (Phase 2/3 typesetting WPs and sanctioned oracle changes)

Verifier. I checked the end state at `art_directed` `5f73d8d`, from a detached
worktree `.../7d99e27f/tmp/tsv` with its own release target. A second worktree,
`.../tmp/tsv2` at `78e28d3`, held the oracle reverts; that commit touches only
`parity/streams.rs` tests and verify evidence. Every output is under
`.../tmp/tsv-out/`. I did not replay any WP's history. The only code edits were
throwaway mutations in the worktrees. Each was restored, `git status` was checked
afterwards, and none was committed.

## Verdicts

| WP | verdict | end-state basis (sections below) |
|---|---|---|
| WP-2.2c | **ACCEPTED** | 56 = 56, figures and plates on the oracle's pages (text, G and display list all equal). Its one blocked clause ("a verdict with every tier evaluated") is resolved at the tip: every gating clause is evaluated and passes (1) |
| WP-2.3 | **ACCEPTED** | Its measured gap (opener fits 4/9) is closed. `the_live_field_by_field_table` on the tip legs gives `cells: 134, equal: 134, differing: 0`. Positive control: the 008 layout against the 010 manifest gives 143 of 167 differing, FAILED |
| WP-3.1 | **ACCEPTED** | Body set at the tip: S text 0 of 54, G max dy 0.006, colour 0 pages, display list 0 pages (1) |
| WP-3.2 | **ACCEPTED** | Opener fits in the 134/134 table. The 9 opener pages pass every clause (1). Defect 2 shows those pages are really compared: a 1-step grey is caught on exactly those 9 (6) |
| WP-3.2b | **ACCEPTED** | Navigation passes with 51 outlines, 1 title and 1 lang compared, 0 mismatches. Colour 0 pages (1) |
| WP-3.3b | **ACCEPTED** (end state) | Code fixture 902 passes every clause with a fresh oracle, including colour over 4109 entries (3). The 903 Tier S text gap it reported is closed at the tip (WP-3.8) |
| WP-3.4 | **ACCEPTED** | Display list 0 pages, and it includes image elements (008 shows it flags an image difference, (2) and (4)). The field table is equal. The 3 figure pages pass on 010 |
| WP-3.5 | **ACCEPTED** | Furniture set passes. Navigation is down from its 3 residuals to 0 (1) |
| WP-3.7a | **ACCEPTED** | Links and navigation 0 mismatches. 902-905 pass every clause at the tip (3) |
| WP-3.7c | **ACCEPTED** | Display list 0, glyph clause 0 violations. The shim is load-bearing and scoped as listed (5) |
| WP-3.8 | **ACCEPTED** (end state) | 903/904/905 pass every clause (3). The 905 pp. 6-7 gap it reported is closed at the tip. 900/901 status holds (3) |
| WP-3.9 | **ACCEPTED** | `--adhoc 008` exits 0. Display list differs only on p4, the editorial (2) |
| WP-0.0d | **ACCEPTED** | Oracle before/after: exactly B+1 on rule pixels, 38 pages, 131732 px (4) |
| WP-0.0e | **ACCEPTED** | Oracle before/after: 0 differing px on 56 pages and text identical. /Lang, /Title and 51 outlines appear. The web change is only `<title>` (4) |
| WP-0.0f | **ACCEPTED** | 008 oracle before/after: pixels differ only inside the three EXIF figures (pp. 16, 17, 19). The tip embeds the source bytes (`cmp` equal), the pre-change oracle does not (4) |
| WP-0.2w | **ACCEPTED** | Its named tests are present and green in the suite (`the_tier_s_gate_fails_on_each_clause_failing_or_missing_alone`, `a_reader_whose_pages_live_in_an_object_stream_imposes_at_authored_precision`). I did not re-mutate them; WP-3.0g.verify.md did |
| WP-5.1h part 2 | **ACCEPTED** | The typeset copies of `anchor_key`/`is_reference_heading`/`article_opener_format` are gone and `inline_text` lives in `model/doc.rs`. `ALLOWED` has 23 rows. My mutant (the `scalar_label` call at `content.rs:867` removed) makes `a_container_label_refuses_the_edition_instead_of_printing_brackets` fail. The typst leg is byte-identical (`6709dc15...`) |

Suite at `5f73d8d`: `cargo fmt --check`, `cargo clippy --all-targets -- -D warnings`
and `cargo test` all exit 0, with 32 result lines, 872 passed, 0 failed.

## 1. `mag parity 010`, staged, clean output dir

```sh
MAG_PARITY_OUT_DIR=.../tsv-out/s1 mag parity 010 --run editions/010/run-2026-09-13T01-34-51   # exit 0, 112 s
```

The out dir started empty, so the oracle was not cached and was rendered fresh
(`render-2026-09-24T10-16-54`). Typst leg `render-2026-09-24T10-18-20`,
reader.pdf `6709dc151c875df1`, the same sha as WP-3.9 and WP-0.0f.

Result lines:
- Staged inputs fresh `bc49b2aa...` (57 inputs, 43 renderer files).
- `ratchet: pass (target E, 54 committed entries checked, 54 recorded, 54 measured, 0 regressions)`.
- S page_count 56 vs 56. S boxes: 162 boxes, 54 rotations. S text: 54 pages, 0 differ.
- G: max dx 0.000, dy 0.006. S colour: 58800 entries, 0 pages.
- S navigation: 85 links, 51 outlines, 1 title, 1 lang.
- E glyph positions: 58623 glyphs, 1514 shows, 0 violations. E display list: 58850 vs 58850, 0 pages.
- V1/V2 pass, worst 0.000336. Raster not_evaluated (withdrawn, as the plan says).

**The verdict is not vacuous:**
- Per-page G block counts are 7-40 on every text page. They are 0 only on
  pp. 2, 10, 30, 35, 45, 54 and 55 (blank inside cover and plate pages).
- Independent counts, taken without the comparator: `pdftotext` finds 58848
  non-space characters on pp. 2-55 on each leg. The display list compares 58850
  elements and the glyph clause 58623 glyphs (ligatures make the glyph count the
  lower one). pypdf finds 85 link annotations on each leg, which equals the
  clause's count.

**Rasters at 300 dpi** (`pdftoppm -r 300`, scratch numpy diff; A5 is 4339269 px):

| page | px differing (any) | > 24 levels (Tier V's delta) | max delta | per-page `pdftotext` chars A / B |
|---|---|---|---|---|
| 3 contents | 29215 (0.67%), 29191 of them delta 1 | 0 | 11 | 556 / 556 |
| 17 opener (Dario) | 16764, 15300 of them delta 1 | 10 (one pixel column, x 212, y 1385-1394) | 69 | 136 / 136 |
| 37 figure page | 106846, 106559 of them delta 1 | 42 (x 183-247, left edge) | 69 | 1057 / 1057 |

Almost all differing pixels are 1-level antialiasing noise. The > 24 counts
(10 and 42 px) match the verdict's own `differing_fraction` on those pages
(2.3e-6, 9.7e-6) and its max channel delta (11, 69, 69). My first pass
mis-paired files (a glob made it compare p3 against p37) and gave 17.7%. The
exact-name rerun gives the numbers above.

## 2. `mag parity --adhoc 008`

`tools/sourcecodes.py 008` exits 0; its output was generated in the worktree and
not committed, as in WP-3.9. Then `mag parity --adhoc 008 --run
editions/008/run-2026-08-30T13-59-32` **exits 0**:
- S page_count 44/44, text 0 of 42 pages, colour 0 pages over 36472 entries.
- Navigation: 38 links, 37 outlines, title and lang, 0 mismatches.
- E display list: **1 page differs, p4** (1928 text elements).
- Glyph violations, G beyond G2 and the V worst page (0.1103) are all on p4.
- The next-worst V page is 0.000336.

`pdftotext` of p4 reads "EDITORIAL / The Pen Moves Faster Than Review", the
out-of-scope editorial.

## 3. Fixtures 900-905

I copied the committed corpus (`mag/tests/typeset_fixtures/corpus`, identical to
WP-3.7a's store by `diff -rq`) into the worktree, ran the fixtures, then moved it
out again. For each of 902-905, `MAG_PARITY_OUT_DIR=... mag parity --adhoc NNN`
rendered **both legs fresh**, including a post-0.0d/e/f oracle. All four **exit
0**:

| fixture | pages | S text / colour / nav | G max dy | E glyphs (viol.) | E display list | V worst |
|---|---|---|---|---|---|---|
| 902 | 20 = 20 | pass / pass (4109) / pass (20 links, 12 outl.) | 0.006 | 4056 (0) | 4127 = 4127, 0 pages | 0.000364 |
| 903 | 16 = 16 | pass / pass (1750) / pass | 0.006 | 1724 (0) | 1762, 0 pages | 0.000129 |
| 904 | 16 = 16 | pass / pass (833) / pass | 0.006 | 814 (0) | 851, 0 pages | 0.000002 |
| 905 | 12 = 12 | pass / pass (937) / pass | 0.006 | 927 (0) | 947, 0 pages | 0.000002 |

900 and 901 refuse on **both** engines, with the same causes the WPs record:
- 900: `Referenced file does not exist: editions/900/sections/production-note.md`.
- 901: `Edition needs 5 closing plates ... configures 3`.

So they are covered by unit tests only (green in the suite), as WP-3.7a, 3.8 and
3.9 claim. **They have no parity coverage.**

## 4. Sanctioned oracle changes, before/after pixels

Each change was reverse-applied (`git show <sha> -- <python/css> | git apply -R`)
in `tsv2` and the oracle re-rendered with the same binary. The pairs differ in
that one change only.

- **WP-0.0f** (008, adapter reverted vs the tip oracle, 44 pages at 300 dpi).
  - Pixels differ only on **p16, p17 and p19**, inside the figure boxes (e.g.
    p16 x 178-1384, y 549-900), max delta 49-51, on all three channels.
  - Text is identical (`diff` exit 0). Both have the same image count.
  - The tip streams equal `media/005.jpg`, `006.jpg` and `011.jpg` byte for
    byte. The reverted oracle's streams (65555 / 160892 / 128809 bytes) equal
    none of them.
- **WP-0.0d** (010, CSS reverted vs the tip oracle).
  - **38 pages, 131732 px, blue channel only, delta exactly 1.**
  - 37 pages change only in rows 116-117 (the running rule).
  - p3 changes in 24 rows (y 665-1941, the contents rules), 33312 px.
  - This matches WP-0.0d.md exactly.
- **WP-0.0e** (010, cover.py and html_edition.py also reverted vs the
  0.0d-reverted render, so only 0.0e differs).
  - **0 differing px on 56 pages.** `pdftotext -raw` is identical.
  - Reverted: Lang None, Title None, 0 outlines. With 0.0e: Lang `en`, Title
    `Berreta Futura: The Speed Limit`, 51 outlines.
  - `diff -r en/web`: only the `<title>` line of edition.html and index.html.

## 5. The `WEASYPRINT_69` shim

I set `WEASYPRINT_69 = false` (`typeset/text_shim.rs:5`), rebuilt, and ran staged
parity with the cached tip oracle. It **exits 1**:
- **Glyph clause fails**: 58623 glyphs, 40 printed violations ("an advance
  before it differs by 0.0015-0.0063 pt, beyond one tick"), worst excess 4.15 pt
  (p40 glyphs 18..24).
- Ratchet: 108 regressions.
- V2 fails (0.008912).
- The display list differs on 2 pages (p4, p6). The difference is the geometry
  of the inline-code chip path: the right edge is about 0.02 pt wider and the
  left edge about 0.004 pt off. The chip pads from its text run, so it follows
  the unshimmed advances and the shifted item start (the shim's own "items
  after a run" rule).
- **Everything else passes unchanged**: page count, boxes, S text 0 pages,
  colour 0, navigation 0 (85 links, 51 outlines), G max dx 0.003 / dy 0.005.

A typst-vs-typst comparison (shim on vs off) gives the same picture: G dy 0.001,
S all pass. The switch therefore moves only horizontal glyph and item positions,
and changes no line break, page, colour or vertical metric.

The only readers of its labels are in `text_shim.rs`: `mag-track:`,
`mag-flush-right`, `mag-spread`. Grep finds no other consumer. The other `mag-*`
labels (`mag-prose*` in runt.rs, and the layout marks) are not shim labels.
`pango-center`/`pango-half` and `own-run` stay outside the switch, which is what
WP-3.7c.md lists.

**No template dependency beyond that list was found.**

## 6. Injected template defects

Both runs used the cached tip oracle and a rebuilt binary, and both edits were
reverted and rebuilt afterwards. Both defects were caught:

1. `MARGIN-TOP` 42.0004pt -> 42.0204pt (+0.02 pt): **exit 1**. E display list
   fails on 47 pages (every text page: 3-53 minus the blank and plate pages).
   V1 and V2 fail. Ratchet: 94 regressions. G shows max dy 0.026 but gates
   nothing at this size. Navigation passes, because link rects compare within
   0.25 pt by decision.
2. `PAPER-GRAY` rgb(93,96,96) -> rgb(93,96,97) (one step in blue): **exit 1**.
   S colour fails on 9 pages, the 9 openers (4, 7, 11, 17, 31, 36, 40, 46, 50),
   for example `page 4: glyph 77: "F" rgb [93, 96, 96] vs [93, 96, 97]`. The
   display list fails on the same 9 pages. Ratchet: 27 regressions. **Tier V
   passes** (a 1-level change is below its delta), as a meter-only tier should.

## What is and is not proven

- **Proven.**
  - At the tip, staged 010 passes at target E from a fresh oracle, and the
    counts behind every clause are non-zero and match independent counts.
  - 008 ad hoc passes with only p4 differing.
  - 902-905 pass every clause against a fresh oracle.
  - Each sanctioned oracle change alters only what it claims, pixel for pixel.
  - The shim is load-bearing (the glyph clause fails without it) and scoped (no
    other clause moves).
  - A 0.02 pt margin shift and a one-step colour change are each caught.
- **Not proven.**
  - 900/901 have no parity comparison on either engine.
  - Spanish and editions other than 008/010 were not rendered.
  - 0.0d's template constant was not isolated on the typst leg. I did not
    re-render typst with `90%`; the evidence is WP-0.0d.md's byte-identical leg.
  - The glyph clause prints at most 40 violations, so the shim-off total count
    is not known.
  - Rule 4 applies to the shim: with it on, both legs write WeasyPrint 69's
    truncated kerns, so equality here does not show the advances are correct.
- **For the orchestrator (no action required by these verdicts).**
  - Tier V does not catch a one-step colour change. Navigation does not catch a
    0.02 pt geometry shift. Both are by design; the display list and S colour
    carry those checks.
