# WP-0.0c opener-fit attribution

## Base

7d79b9d (art_directed). Plan revision 9 (4b887f6 + 5f16548).

All work was done in a detached worktree at 7d79b9d
(`/Users/franguijarro/.claude/jobs/7d99e27f/tmp/wp00c`) so that concurrent
agents' in-progress Rust in the main tree could not break the renders, and so
that both comparison legs came from one frozen CSS and Python state.

## Commands

Setup (the run directory is untracked and must be copied in):

    git worktree add <WT> 7d79b9d
    cp -R editions/010/run-2026-09-13T01-34-51 <WT>/editions/010/
    cd <WT>/mag && cargo build

Three renders, all from the same worktree, run from the repo root:

    ./mag/target/debug/mag render 010 --no-model --run editions/010/run-2026-09-13T01-34-51

- leg B (baseline, unchanged code)  -> editions/010/render-2026-09-14T17-11-27
- leg A (changed code)              -> editions/010/render-2026-09-14T17-12-52
- leg C (baseline again, control)   -> editions/010/render-2026-09-14T17-15-15

The change under test, the only edit, in `src/magazine/html_edition.py`:

        -        '  <header class="article-opener">',
        +        f'  <header class="article-opener" data-article-id="{_attr(article.id)}">',

Lint:

    uvx ruff format --check src/magazine/html_edition.py
    uvx ruff check src/magazine/html_edition.py

Manifest leaf diff (B vs A), file-set and byte diff of the whole trees, and
per-file web HTML diffs:

    diff <(cd B && find . -type f | sort) <(cd A && find . -type f | sort)
    for f in $(cd B && find . -type f | sort); do cmp -s "B/$f" "A/$f" || echo "DIFF $f"; done
    for g in $(cd B/en/web && ls *.html); do diff B/en/web/$g A/en/web/$g; done

PDF comparisons:

    pdftotext -raw <leg>/en/<pdf>.pdf out.txt   # reader, booklet-a4, booklet-a4-interior
    pdfinfo -box <leg>/en/<pdf>.pdf | grep -v "Date\|File size\|ID:"
    ./mag/target/debug/mag parity 010 --pre-rendered B A

Determinism control, the decisive test (leg B vs leg C, both baseline):

    for g in $(cd B/en/web && ls *.html); do diff B/en/web/$g C/en/web/$g; done

## Tool versions

python 3.9.6 (system; renders run through `uv`), uv 0.8.17, weasyprint 69.0,
poppler 25.08.0 (pdfinfo/pdftotext/pdftoppm), rustc 1.96.0.

## Metrics

The target is met. `edition-manifest.json` gains exactly nine leaves, zero
removed, zero changed:

    .layout.article_opener_fits.an-alignment-assessment-of-recent-cybersecurity = true
    .layout.article_opener_fits.countering-misuse-of-ai-september-2026-anthropic = true
    .layout.article_opener_fits.dario-amodei-we-must-pace-the-frontier = true
    .layout.article_opener_fits.deepseek-v4-1-flash-pushing-the-limits-of-kv-cac = true
    .layout.article_opener_fits.government-rails-site-hit-hours-after-cve-patch = true
    .layout.article_opener_fits.rapidly-scaling-online-storage-to-serve-over-1-b = true
    .layout.article_opener_fits.scenarios-for-our-economic-future = true
    .layout.article_opener_fits.the-third-era-of-ai-software-development = true
    .layout.article_opener_fits.towards-self-driving-codebases = true

The nine ids equal `layout.toc`'s ids exactly. All nine fits are `true`, so
every 010 opener occupies a single page and the comparison WP-2.3 and WP-3.2
perform is no longer `{}` against `{}`.

The reader PDF is untouched. `mag parity 010 --pre-rendered B A` exits 0 with
Tier S page_count 56 vs 56, boxes 0 mismatches, text 0 pages differ, color 0
pages differ, navigation 0 mismatches, Tier E display list 0 pages differ,
Tier G max dx/dy 0.000 pt with 0 structure mismatches, Tier V dimensions pass
with worst page fraction 0.000000 and max channel delta 0. Tier E raster is
`not_evaluated` pending WP-0.2f, as expected at this commit. Independently:
`pdftotext -raw` is byte-identical for reader.pdf, booklet-a4.pdf and
booklet-a4-interior.pdf, and `pdfinfo -box` is identical for both PDFs.

`render-critic.json` and `preflight.json` differ only on WP-0.1's whitelist:
the two `.visual_review.*_sha256` leaves and the four scratch-stage `.path`
leaves. Critic result is `pass` on both legs with 4 issues each.

`uvx ruff format --check` and `uvx ruff check` are clean on the touched file.

### The blocking finding

The web edition loses every article's source QR link. Ten files differ beyond
the PDFs and their derivatives: the nine `en/web/article-*.html` (3 diff lines
each: the header line changed, plus one deleted line) and `en/web/edition.html`
(27 lines, being the same nine articles). `en/web/index.html` is unchanged.
The deleted line in each is the opener's source link, for example:

    <a class="source-link opener-source-link" data-source-link="primary"
       data-source-id="towards-self-driving-codebases-3fd7b9ca"
       href="https://cursor.com/blog/self-driving-codebases"
       aria-label="..."><img class="source-qr" src="assets/source-code-...svg" alt=""></a>

There is no compensating addition; the QR simply disappears from the web
edition.

Cause, `src/magazine/web_edition.py:262` in `_install_illustrated_source_codes`:

    if '<header class="article-opener">' in line:
        in_illustrated_opener = True

This detects the illustrated opener by exact match on the ENTIRE header tag.
Adding any attribute to that tag makes the test fail, so
`in_illustrated_opener` never becomes true, `_SOURCE_LINK_LINE` never matches,
the plain `<a class="source-link" ...>` is never upgraded to the QR-bearing
`opener-source-link`, and `_drop_print_only_lines` then deletes it because
`_PRINT_ONLY_LINE` classifies a bare `<a class="source-link" ` as print-only.
The QR assets are still written to `en/web/assets/`; nothing references them.

The control render proves this is caused by the change rather than by
run-to-run variance: legs B and C, both baseline, produce byte-identical web
HTML across all eleven files (0 diff lines each). This also establishes web
HTML determinism, which WP-0.1 never covered, since it compared only pdftotext
dumps, layout JSONs and critic results.

No placement of the attribute avoids this: the detector requires the literal
string `<header class="article-opener">`, which cannot survive any added
attribute, whether before or after the class.

## Verdicts

`mag parity 010 --pre-rendered <B> <A>` verdict.json sha256
`3a7e905203917eba136af1deb03cdcfd02b5d534a9ce64d568ae0fcfabdf6e19`, exit 0,
every evaluated clause passing, Tier E raster `not_evaluated` (WP-0.2f).

## Residuals

- The one-line change is NOT committed. Landing it would ship the web-edition
  regression, which is the workaround the WP forbids. The patch is recorded
  verbatim above and the working copy is kept at
  `/Users/franguijarro/.claude/jobs/7d99e27f/tmp/html_edition_CHANGED.py`.
- Recommended resolution, smallest correct change: extend this WP's Owns to
  `src/magazine/web_edition.py` and make line 262 robust to attributes on the
  header tag (match `<header` plus `class="article-opener"`, or a regex
  anchored on the tag name and class, rather than the whole literal tag). The
  rest of this WP is proven green, so with that one line the WP completes.
- `web_edition.py` carries the same brittleness elsewhere: `_PRINT_ONLY_LINE`
  and `_SOURCE_LINK_LINE` are regexes keyed to exact attribute order and
  spelling on the same lines. Any future attribute added to a figure, source
  link or closing plate will silently drop content from the web edition the
  same way. WP-5.5 ports `web_edition.py` to Rust and should port a structural
  test, not these string matches.
- The plain (non-illustrated) article header at `html_edition.py:244` was
  deliberately left alone. `_note_box` counts a header only when it carries
  the `article-opener` class, which that header lacks, so the attribute would
  be inert there. Editions not using `illustrated_paper_spots_v1` therefore
  still report no opener fits; 010 does use it (edition.yaml line 19), so the
  010 gate is non-vacuous either way.
- Every consumer of `data-article-id` was audited before the change: no CSS
  selector anywhere uses the attribute, and every Python read is guarded by
  `element_tag == "article"` except the `_note_box` branch this WP targets
  (`weasyprint_adapter.py:2303`). That audit is why the reader PDF is
  bit-identical; the regression is confined to the web serialization path.

## Status

blocked

The target is achieved and the reader pipeline is provably unaffected, but the
change cannot land as scoped: completing it requires editing
`src/magazine/web_edition.py`, which this WP does not own. Extending the Owns
list is a plan decision, not a worker's, so this stops here rather than
reaching outside its brief or shipping a regression.
