# WP-5.3b critic rules

## Base

`17eb66b` (plan revision 14, `b8bd499`). No code was written: this WP blocks
on a structural finding, measured below, that no choice inside the WP can
resolve.

## Commands

Oracle artifact inspected (untracked, pre-`5504e5a`, used only to read
committed critic output and to measure extractor agreement on one fixed
PDF; the hyphenation state is irrelevant to every measurement here because
both extractors read the same file):

    editions/010/render-2026-09-14T01-47-59/en/render-critic.json
    editions/010/render-2026-09-14T01-47-59/en/reader.pdf
    editions/010/render-2026-09-14T01-47-59/en/booklet-a4.pdf

Oracle field survey:

    python3 -c "
    import json
    d=json.load(open('editions/010/render-2026-09-14T01-47-59/en/render-critic.json'))
    print('result:',d['result'],'issues:',len(d['issues']),'pages:',len(d['pages']))
    print('issue codes:',sorted({i['code'] for i in d['issues']}))
    print('page row keys:',sorted(d['pages'][30].keys()))
    print('spread keys:',sorted(d['home_booklet']['spreads'][0].keys()))
    "

Extractor agreement on the text-derived page fields, pypdf vs poppler,
every page of the 56-page reader:

    uv run python -c "
    import subprocess, re
    from pypdf import PdfReader
    P=re.compile(r'^[,.;:!?…]+$')
    pdf='editions/010/render-2026-09-14T01-47-59/en/reader.pdf'
    r=PdfReader(pdf)
    def fields(t):
        lines=[l.strip() for l in t.splitlines()]
        return (sum(1 for l in lines if l and any(c.islower() for c in l)),
                len(t.strip()),
                [l for l in lines if P.fullmatch(l)],
                not t.strip())
    db=dc=dp=dblank=0; n=len(r.pages)
    for i in range(1,n+1):
        a=fields(r.pages[i-1].extract_text() or '')
        b=fields(subprocess.run(['pdftotext','-f',str(i),'-l',str(i),pdf,'-'],
                 capture_output=True,text=True).stdout)
        db+=a[0]!=b[0]; dc+=a[1]!=b[1]; dp+=a[2]!=b[2]; dblank+=a[3]!=b[3]
    print(f'of {n} pages, differing: body_text_lines={db} text_characters={dc} '
          f'standalone_punctuation={dp} empty-text={dblank}')
    "

Spread-table reproducibility, poppler on both sides of the same comparison:

    uv run python -c "
    import json, subprocess
    d=json.load(open('editions/010/render-2026-09-14T01-47-59/en/render-critic.json'))
    base='editions/010/render-2026-09-14T01-47-59/en/'
    reader=base+'reader.pdf'; booklet=base+'booklet-a4.pdf'
    def norm(pdf,i):
        t=subprocess.run(['pdftotext','-f',str(i),'-l',str(i),pdf,'-'],
                         capture_output=True,text=True).stdout
        return ' '.join(t.split())
    spreads=d['home_booklet']['spreads']; agree=0
    for row in spreads:
        l,r=row['left_reader_page'],row['right_reader_page']
        exp=' '.join(x for x in [norm(reader,p) for p in (l,r) if p] if x)
        agree += ((norm(booklet,row['side'])==exp)==row['text_order_matches'])
    print(f'reproduced: {agree}/{len(spreads)}')
    "

Dependency inspection:

    grep -n "from .booklet" -A 6 src/magazine/render_critic.py
    wc -l src/magazine/booklet.py src/magazine/render_critic.py

## Tool versions

python 3.12.11, pypdf 6.14.2, pillow 12.3.0, poppler (pdftotext) 25.08.0,
rustc 1.96.0.

## Metrics

Oracle scope per the plan: `{result, issue codes, severities, pages, spread
tables}`. Edition 010's committed report: `result: pass`, 56 page rows, 28
spread rows, 4 issues, all severity `review`, codes `article-page-cap`,
`article-stub-last-page`, `tail-art-dropped`, `whitespace-void`.

Page-row fields and their source:

| field | source | portable without pypdf |
|---|---|---|
| `pixel_dimensions`, `ink_ratio`, `ink_bbox` | raster | yes |
| `presence_ratio`, `presence_bbox`, `sparse` | raster | yes |
| `largest_void`, `voids`, `tail_band` | raster | yes |
| `body_text_lines` | `extract_text()` | **no** |
| `text_characters` | `extract_text()` | **no** |
| `standalone_punctuation_lines` | `extract_text()` | in practice |
| `blank`, `ink_free` | raster + `extract_text()` | in practice |

Measured pypdf vs poppler over all 56 reader pages:

- `body_text_lines` differs on **40 of 56** pages (agree 16)
- `text_characters` differs on **47 of 56** pages (agree 9)
- `standalone_punctuation_lines` differs on 0 of 56
- emptiness of the extracted text (the input to `blank` and `ink_free`)
  differs on 0 of 56

Examples: page 4 gives 9 body lines against 10; page 5 gives 29 against 25;
page 6 gives 33 against 28; page 1 gives 170 characters against 173.

Spread tables: `text_order_matches` reproduces on only **7 of 28** sides.
The comparison is self-consistent (it compares one extractor's booklet-side
text against the same extractor's reader-page texts), so it was the
candidate most likely to survive an extractor swap. It does not: poppler
applies layout analysis to the two-up landscape side and recovers a reading
order that is not the concatenation of the two A5 pages, while pypdf walks
the content stream. All 28 committed values are `true`; poppler makes 21 of
them `false`.

Issue sensitivity on 010: `article-stub-last-page` fires on
`body_text_lines < STUB_BODY_LINE_MINIMUM` (5). Every page that sits below
5 sits below it for both extractors on this edition, so the issue set
happens not to flip. That is a property of this edition, not of the check:
pages 4, 5 and 6 differ by 1, 4 and 5 lines respectively, and any page
landing near the threshold would flip. The other three issue codes are
manifest-derived or raster-derived and are not text-sensitive.

Module scale: `render_critic.py` is 1596 lines. `booklet.py`, which it
imports from, is 94.

## Verdicts

No verdict.json is produced by this WP; the oracle is `render-critic.json`
equality and no Rust critic was written.

## Residuals

**1. The oracle requires byte-exact pypdf text extraction, which is a
library port.** `_PageTexts.raw()` calls `page.extract_text()`, and its
output feeds `body_text_lines`, `text_characters`,
`standalone_punctuation_lines`, `blank` and `ink_free` in every page row,
`text_order_matches` in every spread row, and the `cover-placeholder-copy`
regex. Page rows and spread tables are both inside the plan's oracle scope,
so the oracle cannot be met by any extractor that is not pypdf, and the
measurements above show poppler is not it by a wide margin.

This is the blocker WP-5.7 hit, reached by a second, independent route.
WP-5.7 established the cost: pypdf's text layer is 1701 lines over four
modules plus 18452 lines of data tables, and what would be reproduced is
pypdf's heuristics rather than the PDF specification.

**WP-5.7's re-scope reasoning does not transfer to this WP, and that is the
important part.** WP-5.7 could re-scope from byte-identity to fidelity
because every committed `article.md` is never re-derived, making
byte-identity a counterfactual about future captures. The critic is the
opposite: it is a repeated comparison for as long as both implementations
exist. WP-5.3g puts the Typst leg's critic verdict into Tier S, WP-5.3c
requires both critics to emit the same issue codes on seeded faults, and
WP-5.6 has the Rust critic replace the Python one in the shipped pipeline.
A port that agrees with the original only approximately is a port whose
disagreements surface as gate failures later, at the point where they are
most expensive to diagnose.

**2. An undeclared dependency on `booklet.py`, which WP-5.2 owns and has not
run.** `render_critic.py` imports `A4_LANDSCAPE_POINTS`, `cover_wrap_plan`,
`imposed_reader_page_plan` and `section_reader_pages`. The dependency graph
records `WP-5.3a -> WP-5.3b -> WP-5.3c -> WP-5.3g` and lists WP-5.2 as
parallel, so it does not express this edge. The four functions are pure
page-plan arithmetic and small, which makes copying them tempting and
wrong: the Phase 5 duplicated-helper rule would be violated the moment
WP-5.2 lands, and that rule exists because copying a helper has already
shipped a defect in this execution. Either WP-5.2 precedes WP-5.3b, or
WP-5.3b's Owns extends to the shared plan arithmetic.

**3. What is reachable, for whoever scopes the next attempt.** The raster
half of this module ports cleanly and WP-5.3a has already proved the
technique: PIL-exact grayscale, thresholding, histograms, `getbbox`,
`getextrema`, `reduce` and LANCZOS all reproduced pixel-for-pixel there,
and its LANCZOS is importable rather than copyable. That covers every
raster page field, `_largest_empty_rectangle`, `_locate_tail_band`,
`_abuts_tail_band`, `_annotate_void_geometry`, `_declared_editorial_cap`,
`_all_a4_landscape`, and the issue codes `whitespace-void`, `blank-page`,
`sparse-page`, `article-page-cap`, `editorial-page-cap`,
`tail-art-dropped`, `signature-page-count` and the raster and side-count
checks. Three of edition 010's four issue codes are in that set. What is
not reachable is the text half, listed in finding 1.

**4. Two further raster surfaces that are in the module but outside the
oracle scope**, noted so the next attempt scopes them deliberately rather
than meeting them mid-flight, which is the failure revision 14 warned
about for this WP specifically. `_write_contact_sheets` calls
`ImageDraw.text` with Pillow's default bitmap font, so byte-identical
contact sheets require reproducing that font's glyph bitmaps;
`_write_review_crops` shells `pdftoppm` at 300 dpi and re-crops. Neither
appears in `{result, issue codes, severities, pages, spread tables}`, but
both write artifacts the report references by path, and WP-5.6 makes the
Rust critic responsible for producing them.

## Status

`blocked`.

The WP cannot meet its stated oracle, and the reason is not a defect in the
port or a choice available to it: `render-critic.json` equality over `pages`
and `spread tables` requires reproducing pypdf's text extraction exactly,
which is the library port WP-5.7 already declined as out of proportion, and
the re-scoping that unblocked WP-5.7 is unavailable here because the critic
is a repeated comparison rather than a one-way capture step. Per protocol
rule 6 this is reported as a measured gap rather than worked around: the
alternatives available to a WP acting alone would all be a narrowing of the
oracle, which rule 4 reserves to a plan revision.

Three dispositions exist, and choosing between them is a plan decision:

- **(a) Port pypdf's text layer** as the 2 to 3 WPs WP-5.7 already named as
  its fallback, then complete this WP against the oracle as written. This is
  the only path that keeps the oracle intact, and its cost is shared with
  WP-5.7b rather than borne by this WP alone, which materially changes the
  arithmetic that led WP-5.7 to decline it.
- **(b) Re-scope this WP's oracle** to the extractor-independent surface,
  porting the raster and manifest halves now and deferring the text-derived
  fields. This needs an explicit answer to what WP-5.3c's "both critics emit
  the same issue codes" means for `article-stub-last-page`, and an
  acknowledgement that a re-scope here is weaker than WP-5.7's because the
  comparison is live rather than counterfactual.
- **(c) Split the WP** along the same seam: land the raster and manifest
  half against a correspondingly scoped oracle, and make the text half a
  named successor blocked on (a). This is (b) with the deferral made
  explicit and time-boxed rather than left as a residual.

I have not chosen between them, and no code is committed.
