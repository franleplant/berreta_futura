# WP-5.3d the critic's text source

## Base

`b12a2a3` (`test(model): WP-5.1c cover remaining py_repr escape branches`),
plan revision 15 (`3892298`).

## Status

`done`. **Path B.** The criterion fixed in advance was exact reproduction of
every page row and the whole spread table; the tracer reproduces neither, on
three independent grounds, so path B is taken by the rule rather than by
preference.

The nuance that matters for the re-cut brief: path A fails **not because the
tracer is worse but because it cannot reproduce pypdf's mistakes**. On the
one field where the two disagree about something a reader would notice, the
tracer is right and pypdf is wrong; on the field poppler failed worst, the
tracer is near perfect.

## Commands

Corpus: `editions/010/render-2026-09-14T01-47-59/en/`, the same tree WP-5.3b
measured, so the numbers here are directly comparable to its. Per rule 9 this
is the hyphenation-ON tree (it predates `5504e5a`), 56 reader pages, 28
booklet sides, 54 traceable interior pages.

Spike instrumentation, uncommitted and removed at WP end, was one test file
`mag/tests/wp53d_probe.rs` declaring

    mod parity {
        #[path = "<abs>/mag/src/parity/streams.rs"] pub mod streams;
        #[path = "<abs>/mag/src/parity/display.rs"] pub mod display;
    }

and calling `streams::trace_page` per page (NOT `display::extract`, which
also resolves annotations and fails on the booklet, see Residuals), writing
per page the ordered `Element::Text` shows as `{s, size, x: m[4], y: m[5],
glyphs}`. Run as

    WP53D_PDF=<pdf> WP53D_FIRST=<n> WP53D_LAST=<n> WP53D_OUT=<json> \
      cargo test --test wp53d_probe -- --nocapture

The pypdf oracle, inline:

    uv run python -c '
    import json
    from pypdf import PdfReader
    r=PdfReader("editions/010/render-2026-09-14T01-47-59/en/reader.pdf")
    out={}
    for n in range(2,56):
        t=r.pages[n-1].extract_text() or ""
        lines=[l.strip() for l in t.splitlines()]
        body=sum(1 for l in lines if l and any(c.islower() for c in l))
        out[n]={"body_text_lines":body,"text_characters":len(t.strip()),
                "raw":t,"norm":" ".join(t.split())}
    json.dump(out,open("pypdf_reader.json","w"))'

The field definitions this WP reproduces are `render_critic.py:989` and
`:1007` (`body_text_lines`, `text_characters`), `:903` (`text_order_matches`)
and `_PageTexts.normalized` at `:113`, which is `" ".join(raw.split())`.

## Metrics

Reconstruction rule measured: group `Element::Text` shows into lines by
quantized y origin (`m[5]`), concatenate each line's shows in paint order,
join lines with a newline. For the spread table, join shows with a space,
which is sound because `normalized()` collapses whitespace.

| field | tracer reproduces | pypdf/poppler baseline |
|---|---|---|
| `text_order_matches` | **27 of 27** traceable sides | poppler 7 of 28 |
| `body_text_lines` | 47 of 54 interior pages | poppler 16 of 56 |
| `text_characters` | 7 of 54 interior pages | poppler 9 of 56 |
| cover pages (1, 56) | **0 of 2**, untraceable | pypdf reads both |

`text_order_matches`, the field poppler failed worst: with shows joined by
whitespace the tracer reproduces every one of the 27 traceable sides, against
poppler's 7 of 28. Side 1 is untraceable because it carries reader pages 56
and 1, both covers. My first attempt scored 6 of 27 and the cause was my own
reconstruction, not the tracer: joining shows with the empty string welds
page 4's last token to page 53's first (`BERRETA FUTURA04objects`) where the
reader side has a page boundary. Recorded because the naive rule looks
plausible and is wrong.

`body_text_lines`, the 7 divergences, **one cause for all seven**: pypdf
merges a two-line article headline into a single line. Every divergent page
is an article opener and the merge is visible as a missing space at the join.

| page | tracer | pypdf | the line pypdf emits |
|---|---|---|---|
| 4 | 10 | 9 | `Government Rails Site HitHours After CVE Patch` |
| 11 | 11 | 10 | `An Alignment Assessment ofRecent Cybersecurity Incidents` |
| 31 | 11 | 10 | `Scenarios for Our EconomicFuture` |
| 36 | 4 | 3 | `The third era of AI softwaredevelopment` |
| 40 | 10 | 9 | `Towards Self-DrivingCodebases` |
| 46 | 11 | 10 | `DeepSeek-V4.1-Flash: The Limits ofKV Cache Compression` |
| 50 | 10 | 9 | `Scaling Online Storage to Over1 Billion Users` |

The tracer is geometrically correct in all seven: the two shows sit at
distinct y origins (page 4: 30011 and 27131, a 28.8 pt leading), and the
headline is set over two lines. Reproducing pypdf's number means
reimplementing its `crlf_space_check` line-merge threshold.

`text_characters`, 7 of 54, deltas from -3 to +8. The cause is pypdf's
synthetic spaces: it decomposes `TJ` into `Tj` calls injecting a space when
`abs(op) >= _space_width * 0.95`, so a letter-spaced run yields `BY  FRANK
RIETTA` and `BERRETA FUTURA 04` where the tracer's shows carry `BY FRANK
RIETTA` and `BERRETA FUTURA04`. Reproducing the count means reimplementing
that rule and its half-a-space `_space_width`.

**Zero threshold flips.** `article-stub-last-page` fires on
`body_text_lines < 5` and is the only text-derived decision boundary in the
critic. Across all 54 interior pages, no page changes side under the tracer's
count. Page 36 is the near-threshold case the plan warned about: tracer 4,
pypdf 3, both below, so the issue fires either way. 010's committed issue set
is `whitespace-void`, `article-stub-last-page`, `tail-art-dropped`,
`article-page-cap`, result `pass`.

## Verdicts

No `mag parity` verdict is produced by this WP; it is a measurement spike.

## Residuals

**The tracer cannot read the cover pages at all**, and this binds whichever
path is taken. Reader pages 1 and 56 and booklet side 1 fail loud with
`operator Tf: loading font F1: font Helvetica lacks ToUnicode`. They are not
empty: the committed rows give page 1 `text_characters` 170 and page 56
`text_characters` 380 with `body_text_lines` 6. The covers are compiled by a
different toolchain and embed Helvetica without a `ToUnicode` map. WP-5.3b
needs a named decision. One principled option: for a non-embedded standard-14
face the PDF specification determines code to Unicode through
StandardEncoding or WinAnsiEncoding, so supporting it is reading the spec
rather than guessing, and would not weaken the fail-loud rule that exists to
stop the tracer inventing text for fonts it genuinely cannot resolve.

**`display::extract` is the wrong entry point for a critic text source.** It
resolves annotations, and on `booklet-a4.pdf` that fails with `resolving
named destination: missing required dictionary key "Names"`. The text path
`streams::trace_page` works on the same file. Whatever WP-0.2h lifts into a
shared module should expose the text path without the navigation path.

**The `glyphs` field is already recorded per show** (WP-0.2e), so a future
consumer needing a glyph count per line gets it without another traversal.

Not measured, and out of scope: whether the tracer's line grouping survives
an edition whose body text uses superscripts or inline vertical shifts, which
would place shows of one visual line at different y origins. 010 has none.

## Recommendation for WP-5.3b's re-cut brief

1. **Oracle: the critic's decisions**, `{result, issue codes, severities,
   pages}`, each implementation using its own text source.
2. **Text source: the tracer, not poppler.** This spike is the evidence for
   the plan's "not worse" requirement, and it is measurement rather than
   assertion: 27 of 27 against 7 of 28 on reading order, and correct line
   segmentation on the seven headlines pypdf merges. Poppler additionally
   welds hyphenated line breaks (WP-5.7's finding), which the tracer cannot
   do because it never joins lines.
3. **The fault suite carries the weight**, per the plan's binding caveat, and
   this spike makes that tractable rather than open-ended: there is exactly
   ONE text-derived decision boundary, `body_text_lines < 5`, so WP-5.3c
   needs near-threshold cases on both sides of that one threshold, plus the
   raster- and manifest-derived boundaries which are unaffected by the text
   source.
4. **Record the seven merges as a known, single-cause difference** rather
   than discovering them again: pypdf's line merge on two-line headlines.
5. **Decide the cover pages** before porting, per the residual above.
