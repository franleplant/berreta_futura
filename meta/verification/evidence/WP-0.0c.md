# WP-0.0c opener-fit attribution

## Base

5504e5a (art_directed), which is WP-1.5's hyphenation switch. Plan revision 9
(4b887f6 + 5f16548).

Owns as briefed: `src/magazine/html_edition.py`. **Extended by orchestrator
decision to `src/magazine/web_edition.py`**, for the detection fix described
below and nothing else; the plan's next revision records the extension.

An earlier submission of this WP (commit 7026d45) reported `blocked` because
the attribute silently removed every source QR from the web edition and the
fix lay outside the then-current Owns. This evidence supersedes it: the same
measurements are redone from scratch at 5504e5a, and the detection defect is
fixed.

All work was done in a detached worktree at 5504e5a
(`/Users/franguijarro/.claude/jobs/7d99e27f/tmp/wp00c2`), so every leg shares
one CSS and Python state and concurrent agents' in-progress files in the main
tree could not contaminate a render. The earlier legs, taken at 7d79b9d before
the hyphenation switch landed, are discarded rather than reused: WP-1.5
rebreaks 428 lines, so a comparison straddling it would attribute those
rebreaks to this attribute.

## Commands

    git worktree add <WT> 5504e5a
    cp -R editions/010/run-2026-09-13T01-34-51 <WT>/editions/010/
    cd <WT>/mag && cargo build

Renders, from the repo root, all at 5504e5a:

    ./mag/target/debug/mag render 010 --no-model --run editions/010/run-2026-09-13T01-34-51

- leg B (baseline)          -> editions/010/render-2026-09-14T17-23-47
- leg A (both changes)      -> editions/010/render-2026-09-14T17-25-29
- leg F (false-fit fixture) -> editions/010/render-2026-09-14T17-29-06

The two changes. `src/magazine/html_edition.py`:

    -        '  <header class="article-opener">',
    +        f'  <header class="article-opener" data-article-id="{_attr(article.id)}">',

`src/magazine/web_edition.py`, module scope beside the other patterns:

    +_ILLUSTRATED_OPENER_HEADER = re.compile(r'<header\b[^>]*\bclass="article-opener"')

and in `_install_illustrated_source_codes`:

    -        if '<header class="article-opener">' in line:
    +        if _ILLUSTRATED_OPENER_HEADER.search(line):

Checks:

    uvx ruff format --check src/magazine/html_edition.py src/magazine/web_edition.py
    uvx ruff check src/magazine/html_edition.py src/magazine/web_edition.py
    ./mag/target/debug/mag parity 010 --pre-rendered <B> <A>
    pdftotext -raw <leg>/en/reader.pdf ; pdfinfo -box <leg>/en/reader.pdf
    for g in $(cd <B>/en/web && ls *.html); do diff <B>/en/web/$g <A>/en/web/$g; done
    grep -c 'opener-source-link' <leg>/en/web/edition.html

Regex discrimination test, run inline and recorded in Metrics:

    python3 -c "import re; p=re.compile(r'<header\b[^>]*\bclass=\"article-opener\"'); ..."

False-fit fixture (leg F): the first block of
`editions/010/run-2026-09-13T01-34-51/articles/government-rails-site-hit-hours-after-cve-patch/final.md`
was inflated from 617 to 3017 characters by appending eight copies of a filler
sentence, then rendered and reverted. That run directory copy is scratch inside
the worktree; no tracked file was touched.

## Tool versions

python 3.9.6 (renders run through `uv`), uv 0.8.17, weasyprint 69.0, poppler
25.08.0 (pdfinfo/pdftotext/pdftoppm), rustc 1.96.0.

## Metrics

**The manifest target is met.** `edition-manifest.json` gains exactly nine
leaves under `layout.article_opener_fits`, with zero leaves removed and zero
changed. The nine ids equal `layout.toc`'s ids exactly. All nine values are
`true`.

**The web edition is correct.** Every web HTML difference between leg B and
leg A is a header line and nothing else: nine `article-*.html` at 2 diff lines
each (one `<`, one `>`), `edition.html` at 18 (the same nine headers), and
`index.html` byte-identical. Classified across all eleven files, the diff is 18
removed header lines and 18 added header lines, each addition carrying its
article's id. The QR survives: `opener-source-link` appears 9 times in
`edition.html` and 9 times across the article files in BOTH legs, and
`class="source-qr"` appears 18 times in both. Before the detection fix, those
counts fell to zero and the QR assets were written but unreferenced.

**The regex is discriminating**, not merely permissive. Eight cases, all as
expected: it matches the bare header, the header with the attribute after the
class, and the header with the attribute before the class; it rejects
`<figure class="article-opener-art">`, `<header class="article-opener-art">`,
a bare `<header>`, `<header class="edition-header">`, and
`<span data-class="article-opener">`. The quoted class value is what excludes
`article-opener-art`, and `\bclass=` is what excludes `data-class=`.

**The reader PDF is untouched.** `mag parity 010 --pre-rendered B A` exits 0:
Tier S page_count pass (56 vs 56), boxes pass (0 mismatches), text pass (0
pages differ), color pass (0 pages differ), navigation pass (0 mismatches),
Tier E display list pass (0 pages differ), Tier G max dx 0.000 pt and max dy
0.000 pt with 0 structure mismatches, Tier V dimensions pass with worst page
fraction 0.000000 and max channel delta 0. Tier E raster is `not_evaluated`
pending WP-0.2f, as expected at this commit. Independently, `pdftotext -raw`
is byte-identical for reader.pdf, booklet-a4.pdf and booklet-a4-interior.pdf,
and `pdfinfo -box` is identical.

`render-critic.json` and `preflight.json` differ only on WP-0.1's whitelist:
the two `.visual_review.*_sha256` leaves and the four scratch-stage `.path`
leaves. Critic result `pass` on both legs. Ruff clean on both touched files.

### Can a fit boolean be false?

All nine values are `true`, and a clause whose every value is `true` is weak
evidence that the comparison works. What a `false` requires is precise:
`_measure_layout` collects, per article id, the set of pages on which a box
for the opener `header` element appears (`weasyprint_adapter.py:2303`), and
reports `len(value) == 1` (`:2387`). So `false` means the opener header BOX
fragments across two or more pages.

I tried to force one and could not, and the attempt bounds the difficulty
rather than merely failing. Leg F inflated one article's standfirst, which is
rendered inside the header, by roughly five times (617 to 3017 characters).
The edit demonstrably took effect: the filler text is present in the rendered
PDF, that article's span grew from 3 pages to 4, and the following articles'
toc pages all shifted by one (an-alignment 11 to 12, countering-misuse 7 to 8,
dario 17 to 18, scenarios 31 to 32). Yet all nine fits stayed `true`.

The cause is in the stylesheet: `article[data-article-opener=
"illustrated_paper_spots_v1"] > header.article-opener` sets `break-inside:
avoid` together with `break-after: page` (`weasyprint-a5.css:1436`). The design
holds the opener whole and forces a page break after it, so under content
growth the overflow flows past the opener instead of fragmenting it. A `false`
therefore requires header content that cannot fit one A5 page even with
`break-inside: avoid` (which is a preference, not a guarantee), not merely a
longer standfirst.

Recorded as an obligation on WP-3.2 per the orchestrator: before that WP treats
"opener-fit booleans exact" as a gate, it needs one fixture in which a boolean
is `false` on the oracle leg, or the clause remains true-by-construction for
this design and proves only that both engines agree about a constant.

### Web HTML determinism, a finding in its own right

Two baseline renders produce byte-identical web HTML across all eleven files.
This was measured at 7d79b9d during the first submission (legs B and C there,
0 diff lines on every file) and is what proved the QR regression was caused by
the change rather than by run-to-run variance. WP-0.1 never established this:
it compared pdftotext dumps, layout JSONs and critic results only. The property
is worth keeping because the web tree is otherwise unguarded by any clause in
the parity ladder.

## Verdicts

`mag parity 010 --pre-rendered <B> <A>`, exit 0, verdict.json sha256
`c81b46adbea85b9c22eb1cbe5541d18cb061d827d989fe73a64e7d7ed04a810e`. Every
evaluated clause passes; Tier E raster `not_evaluated` (WP-0.2f).

## Residuals

- `web_edition.py` carries the same brittleness elsewhere, deliberately NOT
  fixed here: `_PRINT_ONLY_LINE` and `_SOURCE_LINK_LINE` are regexes keyed to
  exact attribute order and spelling, and `_PIECE_OPENING` is anchored to a
  four-space indent. Any future attribute added to a figure, source link or
  closing plate will silently drop content from the web edition exactly as this
  WP's attribute did. I fixed only what this change breaks; widening the repair
  would be scope creep against output I am trying to hold constant. WP-5.5
  ports `web_edition.py` to Rust and should port structural matching, not these
  string patterns.
- The plain (non-illustrated) article header at `html_edition.py:244` is
  deliberately untouched: `_note_box` counts a header only when it carries the
  `article-opener` class, which that header lacks, so the attribute would be
  inert. Editions not using `illustrated_paper_spots_v1` still report no opener
  fits; 010 uses it (edition.yaml line 19), so the 010 gate is non-vacuous in
  the sense that entries exist, subject to the true-by-construction caveat
  above.
- Every consumer of `data-article-id` was audited before the change: no CSS
  selector anywhere uses the attribute, and every Python read is guarded by
  `element_tag == "article"` except the `_note_box` branch this WP targets.
  That audit is why the reader PDF is bit-identical and why the only fallout
  was in the web serialization path, which reads the HTML as text rather than
  as a tree.

## Status

done
