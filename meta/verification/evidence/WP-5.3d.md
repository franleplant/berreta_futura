# WP-5.3d the critic's text source

## Base

`b12a2a3` (`test(model): WP-5.1c cover remaining py_repr escape branches`),
plan revision 15 (`3892298`).

## Status

`done`. **Path B.** The criterion fixed in advance was exact reproduction of
every page row and the whole spread table; the tracer reproduces neither, on
three independent grounds, so path B is taken by the rule rather than by
preference.

Resubmitted. The first submission was rejected at `6c24379` for understating
the text-derived decision surface: it claimed one decision boundary where
there are five fields and eleven sites. The decision was upheld and the
enumeration is corrected under Metrics, which also changes what WP-5.3c must
fault.

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

### The text-derived decision surface

An earlier revision of this file claimed `article-stub-last-page` was the
only text-derived decision boundary. That was wrong and it was the
load-bearing claim, so it is corrected here with the enumeration behind it.
`body_text_lines < 5` (`STUB_BODY_LINE_MINIMUM = 5`, `render_critic.py:62`)
is the only numeric THRESHOLD, but **five text-derived fields feed eleven
issue sites emitting eleven distinct codes**:

| field | sites | issue codes |
|---|---|---|
| `text_order_matches` | `:152`, `:176`, `:198` | `booklet-page-order`, `interior-booklet-page-order`, `cover-booklet-page-order` |
| `blank` | `:291`, `:452`, `:476` | `inside-cover-reader-not-blank`, `inside-cover-booklet-not-blank`, `cover-booklet-inside-not-blank` |
| `ink_free` | `:299`, `:460`, `:484` | `blank-page`, `blank-booklet-side`, `blank-cover-booklet-side` |
| `standalone_punctuation_lines` | `:309` | `orphan-punctuation` |
| `body_text_lines` | `:380` | `article-stub-last-page` |

`blank` and `ink_free` are conjunctions whose text half is `not
text.strip()`; their raster halves (`pure_white`, `ink_pixels == 0`) are
unaffected by the text source. `sparse` is ink-ratio only and is correctly
not in this table. **`text_characters` is consumed by NO issue**: it appears
only at its definition (`:1007`) and is a reported metric, which is why the
field with the worst agreement in this spike drives no decision.

So the argument for path B is not that only one decision consumes text. It
is that **the tracer agrees with pypdf on every field feeding ten of the
eleven sites, and on the eleventh it disagrees without changing the
outcome**:

| field | sites | tracer vs pypdf |
|---|---|---|
| text-emptiness (`blank`, `ink_free`) | 6 | **54 of 54** interior pages |
| `standalone_punctuation_lines` | 1 | **54 of 54** interior pages |
| `text_order_matches` | 3 | **27 of 27** traceable sides |
| `body_text_lines` | 1 | 47 of 54, and **zero threshold flips** |

Zero threshold flips: across all 54 interior pages no page changes side of
`body_text_lines < 5` under the tracer's count. Page 36 is the near-threshold
case the plan warned about, tracer 4 against pypdf 3, both below, so the
issue fires either way. 010's committed issue set is `whitespace-void`,
`article-stub-last-page`, `tail-art-dropped`, `article-page-cap`, result
`pass`.

## Verdicts

No `mag parity` verdict is produced by this WP; it is a measurement spike.

## Residuals

**The tracer cannot read the cover pages at all**, and this binds whichever
path is taken. Reader pages 1 and 56 and booklet side 1 fail loud with
`operator Tf: loading font F1: font Helvetica lacks ToUnicode`. They are not
empty: the committed rows give page 1 `text_characters` 170 and page 56
`text_characters` 380 with `body_text_lines` 6. The covers are compiled by a
different toolchain and embed Helvetica without a `ToUnicode` map.

**The consequence, which the measurement shows and the first revision of
this file failed to draw: one issue cannot be computed AT ALL.**
`cover_spread_checks` (`render_critic.py:186`) is built over
`cover_wrap_plan`, and `cover_wrap_plan(56)` is `((56, 1),)` exactly the two
pages the tracer cannot read. So under a tracer-fed critic
`cover-booklet-page-order` (`:198`) is not computed differently, it is not
computable. That is a missing decision rather than a divergent one, and it
is why the 27 of 27 above is stated over TRACEABLE sides.

**The forward gap is wider than the critic.** WP-5.4g makes `reader.pdf`
compared end to end, so pages 1 and 56 enter the Tier E compared domain. A
tracer that fails loud on them is then a gap in THE GATE, not only in the
critic, and it arrives on a schedule nobody chose. Revision 16 has created
**WP-0.2h** to fix the decode; this WP does not re-propose a fix, it records
that WP-0.2h is a prerequisite for both the cover-bearing critic sites and
WP-5.4g's domain switch.

**`display::extract` is the wrong entry point for a critic text source.** It
resolves annotations, and on `booklet-a4.pdf` that fails with `resolving
named destination: missing required dictionary key "Names"`. The text path
`streams::trace_page` works on the same file. Whatever WP-0.2h lifts into a
shared module should expose the text path without the navigation path.

**The `glyphs` field is already recorded per show** (WP-0.2e), so a future
consumer needing a glyph count per line gets it without another traversal.

**The corrected join rule has a bounded mirror failure**, stated because the
rule is the deliverable. Joining shows with a space gives a word split
across two adjacent shows a spurious space that `normalized()` cannot
remove, which is the exact inverse of the welding defect the empty-string
join produced. It is reachable in principle, since adjacent shows on one
line do occur here (`BERRETA FUTURA04` is one show sequence), and it did not
fire on this corpus. A rule keyed on the gap between a show's end and the
next show's origin would decide it geometrically instead of assuming; that
is work for whoever implements the seam, not a defect measured here.

**Reproducibility is adequate but thin in one place.** The pypdf oracle
above reruns verbatim. The probe is given by shape and interface (the module
declaration, the call, the emitted fields) rather than in full, so a
reimplementation is required to rerun the tracer side. The crux is explicit
and is the part that matters: the line grouping is by quantized y origin
with shows concatenated in paint order, and the join rule is a newline
between lines for the page fields and a space between shows for the spread
comparison.

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
   it must cover ALL FIVE text-derived fields, not the one numeric
   threshold. WP-5.3c's brief should require, per the table above:
   - `body_text_lines`: near-threshold cases on both sides of
     `body_text_lines < 5`, the only numeric boundary.
   - `text_order_matches`: a swapped spread (already in WP-5.3c's scope) for
     each of the three sites, interior AND cover, noting the cover site
     cannot currently be computed at all (see the cover residual).
   - `blank` and `ink_free`: a page that is text-empty but not ink-free and
     one that is ink-free but not text-empty, so the conjunction is faulted
     on its text half rather than only its raster half. Six sites depend on
     this and a raster-only fault leaves the text half unexercised.
   - `standalone_punctuation_lines`: a page ending in an orphaned
     punctuation line.
   The agreement measured here (54 of 54, 54 of 54, 27 of 27) is evidence
   that the text source is sound on this edition, NOT a substitute for
   faulting each field: 010 exercises none of these issues except
   `article-stub-last-page`.
4. **Record the seven merges as a known, single-cause difference** rather
   than discovering them again: pypdf's line merge on two-line headlines.
5. **Decide the cover pages** before porting, per the residual above.
6. **`text_characters` needs no fault**, since no issue consumes it, but the
   port must still emit it for report parity; its 7 of 54 disagreement is
   therefore a reporting difference and not a decision risk.
