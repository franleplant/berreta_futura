# WP-0.0e reader.pdf keeps /Lang, /Title and the outline (sanctioned oracle change)

## Base

`art_directed` `c58cc78`, rebased onto `c7ff204` before landing (WP-5.5d touched `semantic.rs` and `web_port.rs`, WP-0.2s the comparator; after the rebase `cargo test` gave 637 passed, 0 failed, and the staged parity run gave identical tier lines at the same digest), detached worktree `.../tmp/wp00e`, its own
`mag/target`, tracked run `editions/010/run-2026-09-13T01-34-51`, `--langs en`.
Oracle BEFORE `render-2026-09-24T01-09-59`, oracle AFTER
`render-2026-09-24T01-16-22` (final tree, reused as the cached leg by the
AFTER parity run). Typst BEFORE `render-2026-09-24T01-11-07`, typst AFTER
`render-2026-09-24T01-32-02`.

## Why

WP-3.5 evidence ("document title/lang/outlines differ"): WeasyPrint 69.0
writes `/Lang`, Info `/Title` and `/Outlines`, and `cover.py`
`replace_outer_pages` rebuilt the reader with `PdfWriter().add_page(...)`,
which drops all three. The oracle reader.pdf had none of them, so Tier S
navigation compared 0 outlines, 0 title, 0 lang.

## What changed

- `src/magazine/cover.py` `replace_outer_pages`: the writer now clones the
  WeasyPrint interior (`PdfWriter(clone_from=source)`), so the catalog
  (`/Lang`, `/Outlines`, named dests) and the Info `/Title` come across as
  WeasyPrint wrote them. The first and last page objects are kept and their
  keys (all but `/Parent`) are replaced by the cover faces', so any outline
  entry or link that targets a cover page still resolves.
  `compress_identical_objects(remove_identicals=False, remove_orphans=True)`
  drops the interior's replaced cover content. The header is the highest of
  the three inputs, as `add_page` did before (without that line the clone
  wrote `%PDF-1.3`, caught by `pdfinfo`). `/Creator` and `/Producer` stay
  `magazine-compiler`.
- `src/magazine/html_edition.py:83`: the document title is
  `"{publication}: {title}"` (orchestrator decision; was joined with U+2014,
  which repo rules forbid authoring). This is the `<title>` WeasyPrint turns
  into `/Title`, and it is also the `<title>` of `en/web/edition.html` and
  `en/web/index.html`.
- `mag/src/web/semantic.rs:204`, **outside this WP's Owns line**: the Rust
  web port byte-mirrors that title, and 10 tests in `mag/tests/web_port.rs`
  (`edition_010_matches_html_edition_byte_for_byte`,
  `edition_010_web_tree_is_byte_identical`, 8 more) failed at 560 passed /
  10 failed until the same one-line separator change was made there.
- `meta/verification/baseline.json`: `staged_input_digest` rebased (below).

Not changed: `replace_first_page` in the same file has no caller (`grep -rn
"replace_first_page\|replace_outer_pages" src tests mag/tests tools` shows only
its definition and the bridge's use of `replace_outer_pages`). Per-piece web
titles still join with U+2014 in `web_edition.py:691` and its port
`mag/src/web/edition.rs:957`; they are not the PDF title.

Rust cover port check: `mag/src/cover/pdf.rs` writes one cover face; `grep -rn
"pdf::\|cover::" mag/src` shows only `cover::text` used (by `web/edition.rs`),
and the typst engine (`render.rs` `run_typst` -> `typeset::run_request`) has no
cover step. reader.pdf for the oracle is built only by
`engine_render_bridge.py:328` -> `replace_outer_pages`.

## Commands

```sh
unset TYPST_ROOT; M=./mag/target/debug/mag; RUN=editions/010/run-2026-09-13T01-34-51
$M parity 010 --run $RUN   # BEFORE, exit 1 (tiers), staged fresh 12c24234...
#   edit cover.py, html_edition.py; a scratch WeasyPrint synth (7 pages, h1/h2, links) showed the outline
#   and page targets identical in interior.pdf and reader.pdf, Lang en, Title kept
$M parity 010 --run $RUN   # exit 1: refused, run 1a570792..., baseline 12c24234... (final tree)
#   rebase baseline.json
$M parity 010 --run $RUN   # AFTER, exit 1 (tiers); "staged inputs: fresh (1a570792...)", ratchet pass
#   semantic.rs one-liner, cargo build, AFTER re-run: identical tier lines, typst reader.pdf cmp 0 vs BEFORE
pdftoppm -r 300 -png <before>/en/reader.pdf ras/a/p; pdftoppm -r 300 -png <after>/en/reader.pdf ras/b/p   # both exit 0
uv run --no-project --with numpy --with pillow python rasdiff.py ras/a ras/b   # "56 pages, 0 differing pixels", exit 0
#   positive control: ras/a vs a copy with p-02 as p-01 -> "p-01.png 4270670"
diff <(pdftotext -raw before) <(pdftotext -raw after)   # exit 0
diff <(pdftotext before) <(pdftotext after)             # exit 0
diff pdfinfo -box -f 1 -l 56 (both)                     # adds "Title: Berreta Futura: The Speed Limit"; File size 87139292 -> 87148700
cmp edition-manifest.json (both)                        # exit 0
diff render-critic.json (both)                          # only booklet_sha256 and reader_sha256
diff -r en/web (both)                                   # only <title> in edition.html and index.html (U+2014 -> ": ")
cmp <typst before>/en/reader.pdf <typst after>/en/reader.pdf   # exit 0
uv run python nav.py <after>/en/reader.pdf              # scratch pypdf script: Lang, Info, outline with page numbers
(cd mag && cargo fmt --check && cargo clippy --all-targets -- -D warnings && cargo test)   # all exit 0; 31 result lines, 576 passed, 0 failed (637 after the rebase)
```

## The new oracle reader.pdf (`render-2026-09-24T01-16-22/en/reader.pdf`)

- Catalog `/Lang en`; Info `/Title (Berreta Futura: The Speed Limit)`,
  `/Creator` and `/Producer` `magazine-compiler`; header `%PDF-1.7` as before.
- Outline: 51 entries, 10 top level (Contents, then the nine articles), each
  article with its h2 children. Spot checks against `pdftotext -raw` of the
  target page: Contents p3, "The patch is the disclosure" p5, "We Must Pace
  the Frontier" p17 (the opener sets it as `WeMustPacetheFrontier`),
  "Footnotes" p29, "Cloud agents and artifacts" p38, "Rust" p53: all on the
  page the outline names. The first and last pages (covers) are targets of no
  entry.

## Baseline rebase (protocol of WP-0.2l.verify.md)

`meta/verification/baseline.json` `staged_input_digest`:
old `12c24234f8b033860b1b04a3ae66f6c67c0a298b625d1957b0df0411b9375f09`,
new `1a570792e6db0e76fc7a4944be60d0355eafcb82d8054770f5dde987b3e872ae`
(57 edition inputs, 43 renderer files), from the refusal line of a run on the
final Python tree, confirmed "fresh" by both AFTER runs. No other field changed.
(An earlier tree without the header line gave `0fc51719...`.)

## `mag parity 010` staged, before and after

| tier | before | after |
|---|---|---|
| staged inputs | fresh `12c24234...` | fresh `1a570792...` |
| ratchet | pass, 54 measured, 0 regressions | same |
| S page_count / boxes / text | pass / pass / pass | same |
| G | max dx 0.003, dy 0.220, beyond G1 0, G2 0 | same |
| S color | fail, 9 pages | same |
| **S navigation** | fail, 3; 85 links, **0 outlines, 0 title, 0 lang** compared | fail, 3; 85 links, **51 outlines, 1 title, 1 lang** compared |
| E glyph positions | 1802 shows, 40 violations, worst 325.211792 | same |
| E display list | 43 pages | same |
| V | worst 0.281752 | same |

The navigation mismatch list is unchanged in wording (pages 21, 27, and
"document title/lang/outlines differ"), but the document line now reflects a
real typst gap: the oracle carries a title and a 51-entry outline, typst has
neither (owner WP-3.2b). Before, it was the oracle that was empty.

## What is and is not proven

Proven on 010 en: the oracle reader.pdf now carries `/Lang en`, the Info
title and a 51-entry outline whose sampled targets land on the right pages;
all 56 pages rasterize pixel-identical at 300 dpi; text, boxes, manifest are
unchanged; the only web change is the two `<title>` lines; the typst leg is
byte-identical; the ratchet passes at the rebased digest.

Not proven: the outline was not diffed object-for-object against the live
interior.pdf (the bridge deletes it); the synth run and the clone mechanism
(objects copied, not rebuilt) are the evidence that it is WeasyPrint's
outline. Other editions and `es` were not rendered. Rule 4: `/Lang en` is
correct for the English edition; the ": " title is a deliberate departure from
the previous oracle string.
