# WP-5.7 capture's PDF transcription

## Base

b153353 (`verify(parity): WP-1.5 and WP-1.6 accepted`), branch art_directed.

## Status

**blocked**

The mandated first step is answered: `tools/pdf2md.py` IS deterministic. The
oracle the plan then prescribes, byte-identical markdown on three
captured-PDF fixtures, cannot be met by any port this WP could legitimately
write, for two independent reasons measured below: the repository holds only
one real captured-PDF fixture, and byte-identity requires reproducing
pypdf 6.14.2's text extraction exactly, which is a library port rather than a
script port. No code was written. Recommendations for the plan are at the end.

## Commands

Determinism, three runs each at both levels (markdown, and the raw
`extract_text()` the markdown is derived from):

```
P=.magazine/capture/deepseek-v4-1-flash-pushing-the-limits-of-kv-cac-737d50c2.pdf
for i in 1 2 3; do uv run python tools/pdf2md.py $P | shasum -a 256; done
for i in 1 2 3; do uv run python -c "
from pypdf import PdfReader
import sys
r=PdfReader('$P')
sys.stdout.write(''.join((p.extract_text() or '') for p in r.pages))
" | shasum -a 256; done
```

Executed-surface trace (which pypdf code a real extraction reaches):

```
uv run python -c "
import sys, collections
from pypdf import PdfReader
hits=collections.Counter()
def tr(frame,event,arg):
    if event=='call':
        f=frame.f_code.co_filename
        if 'pypdf' in f:
            hits[(f.split('site-packages/')[-1], frame.f_code.co_name)]+=1
    return None
r=PdfReader('$P')
sys.settrace(tr)
t=''.join((p.extract_text() or '') for p in r.pages)
sys.settrace(None)
mods=collections.Counter()
for (f,n),c in hits.items(): mods[f]+=1
print('distinct pypdf functions executed:', len(hits))
print('distinct pypdf modules executed:', len(mods))
for m,c in mods.most_common(12): print(f'  {c:4d} fns  {m}')
"
```

Independent-extractor divergence (poppler against pypdf, same PDF):

```
uv run python -c "
from pypdf import PdfReader
r=PdfReader('$P')
open('/tmp/wp57_pypdf.txt','w').write(''.join((p.extract_text() or '') for p in r.pages))
"
pdftotext $P /tmp/wp57_poppler.txt
wc -c /tmp/wp57_pypdf.txt /tmp/wp57_poppler.txt
wc -l /tmp/wp57_pypdf.txt /tmp/wp57_poppler.txt
diff <(head -20 /tmp/wp57_pypdf.txt) <(head -20 /tmp/wp57_poppler.txt)
```

Font surface of the one real fixture, and the port surface:

```
uv run python -c "
from pypdf import PdfReader
r=PdfReader('$P')
fonts={}; tou=0; tot=0; subtypes={}
for p in r.pages:
    res=p.get('/Resources',{})
    fd=res.get('/Font',{}) if res else {}
    try: items=fd.items()
    except Exception: continue
    for k,v in items:
        o=v.get_object(); bf=str(o.get('/BaseFont'))
        if bf in fonts: continue
        fonts[bf]=1; tot+=1
        if '/ToUnicode' in o: tou+=1
        st=str(o.get('/Subtype')); subtypes[st]=subtypes.get(st,0)+1
print('distinct fonts:',tot,' with ToUnicode:',tou)
print('subtypes:',subtypes)
"
wc -l .venv/lib/python3.12/site-packages/pypdf/_text_extraction/__init__.py \
      .venv/lib/python3.12/site-packages/pypdf/_text_extraction/_text_extractor.py \
      .venv/lib/python3.12/site-packages/pypdf/_cmap.py \
      .venv/lib/python3.12/site-packages/pypdf/_font.py
wc -l .venv/lib/python3.12/site-packages/pypdf/_codecs/adobe_glyphs.py \
      .venv/lib/python3.12/site-packages/pypdf/_codecs/core_font_metrics.py
```

Fixture inventory:

```
ls .magazine/capture/*.pdf
find . -name "*.pdf" -not -path "./output/*" -not -path "./editions/*/render-*" \
       -not -path "./.git/*" -not -path "./mag/target/*"
grep -rl "url:.*\.pdf" library/sources/*/record.yaml
```

## Tool versions

- python 3.12.11, uv 0.8.17
- pypdf 6.14.2 (the behaviour any byte-identical port must reproduce)
- poppler 25.08.0 (`pdftotext`), the pinned comparator toolchain
- rustc 1.96.0

## Metrics

**Determinism: YES.** Three consecutive runs, byte-identical at both levels.

| level | sha256 (all three runs) |
|---|---|
| `tools/pdf2md.py` markdown | `200d3b8eaf9133dbe4200dd9614ef56962adf8b793a725fdfb9bbc960277aea9` |
| raw `extract_text()` concatenation | `2fed1c19d1ad744d016d9aff7bb5b0dffe1af7a862388921eadc4415bd0ab592` |

The wrapper in `pdf2md.py` is pure: a regex, `splitlines`, `strip`, and
joins, with no clock, randomness, set iteration or filesystem order. All
variability would have to come from `pypdf.extract_text()`, and it does not,
for a fixed pypdf version. Determinism is therefore version-scoped: it is a
property of pypdf 6.14.2, not of the script.

**Fixture inventory: 1 real captured PDF, not 3.** The repository holds
exactly one: `.magazine/capture/deepseek-v4-1-flash-pushing-the-limits-of-kv-cac-737d50c2.pdf`
(1,809,802 bytes, 51 pages). No `library/sources/*/record.yaml` carries a
`.pdf` URL, and no other PDF exists outside `output/` and render directories.
The plan's "three captured-PDF fixtures" cannot be assembled from real
captures today; two of three would have to be synthetic, and synthetic
fixtures constructed by me would exercise the code paths I chose to
implement, which is precisely the masked-defect pattern that WP-5.1a and
WP-5.1b were rejected for (both had oracles that passed while diverging on
constructs the corpus happened not to contain).

**Byte-identity requires a library port, not a script port.** A real
extraction executes **90 distinct pypdf functions across 12 modules**:

| functions | module |
|---|---|
| 16 | `pypdf/_text_extraction/_text_extractor.py` |
| 11 | `pypdf/generic/_data_structures.py` |
| 9 | `pypdf/generic/_base.py` |
| 9 | `pypdf/_font.py` |
| 8 | `pypdf/_cmap.py` |
| 7 | `pypdf/_page.py` |
| 7 | `pypdf/_reader.py` |
| 5 | `pypdf/_utils.py` |
| 5 | `pypdf/filters.py` |
| 5 | `pypdf/_text_extraction/__init__.py` |
| 4 | `pypdf/_doc_common.py` |
| 4 | `pypdf/generic/_utils.py` |

`lopdf` 0.45.0 (already a dependency) covers the object model, the reader and
the stream filters, which accounts for `generic/*`, `_reader.py`, `filters.py`
and `_utils.py`. What remains genuinely unported is the text layer:
**1,701 lines** across `_text_extraction/__init__.py`, `_text_extractor.py`,
`_cmap.py` and `_font.py`, plus **18,452 lines** of data tables
(`_codecs/adobe_glyphs.py`, `_codecs/core_font_metrics.py`) that those modules
index into, plus the four smaller encoding tables (`std`, `symbol`,
`zapfding`, `pdfdoc`, ~1,040 lines).

The behaviour to reproduce is not generic PDF text extraction but pypdf's
specific heuristics, several of which are arbitrary constants rather than
spec-derived:

- `crlf_space_check` emits a newline when `abs(moved_height) > 0.8 * min(str_height * scale_prev_y, font_size * scale_y)`, and a space when `moved_width >= (spacewidth + str_widths) * scale_prev_x`. The `0.8` is pypdf's, not the PDF specification's.
- `_handle_tf` sets `_space_width = font.space_width / 2`, commented in the source as "Actually the width of _half_ a space...".
- `TJ` is not an operator in the extractor at all: `_page.py:1865` decomposes each array element into synthetic `Tj` operations and injects a literal space when `abs(float(op)) >= _space_width * 0.95` and the accumulated text does not already end in one. The `0.95` is pypdf's.
- `'` and `"` are likewise decomposed at `_page.py:1857-1864`, and `TD` is rewritten into `TL` + `Td`.
- `get_display_str` reorders characters by Unicode range for RTL handling, with `xx <= 0x2F`, `0x3A <= xx <= 0x40`, `0x2000 <= xx <= 0x206F` and `0x20A0 <= xx <= 0x21FF` kept in insertion order.

A port that reproduces the text but not these exact thresholds produces
different line breaks, and `pdf2md.py` derives its paragraphs from
`splitlines()` of that output, so a line-break difference is a markdown
difference. Byte-identity is all-or-nothing here.

**Substituting a different extractor fails the oracle by a wide margin, and
degrades fidelity.** Poppler 25.08.0 against pypdf 6.14.2 on the same PDF:

| | pypdf | poppler |
|---|---|---|
| bytes | 162,308 | 163,821 |
| lines | 2,487 | 3,790 |

The divergence is not cosmetic. Poppler welds words across hyphenated line
breaks: pypdf yields `input-\nheavy` and `DeepSeek-V4.1-\nFlash`, poppler
yields `inputheavy` and `DeepSeek-V4.1Flash`. `pdf2md.py`'s paragraph joining
preserves the hyphen and the following text, so the captured article keeps the
author's word; poppler's output would silently corrupt it. Since
`mag capture` writes this text into `library/sources/<id>/article.md` as the
source's substantive text verbatim, and CLAUDE.md requires exactly that, a
change of extractor is a change to captured source fidelity, not an
implementation detail.

**Font surface of the one real fixture:** 16 distinct fonts, all
`/Type1`, and all 16 carry `/ToUnicode`. A port restricted to
ToUnicode-bearing fonts would cover this fixture completely, which is
precisely why passing an oracle built on it would prove little about the next
PDF.

## Verdicts

No verdict.json is produced by this WP; `mag parity` is not involved (Phase 5
oracle-equality tests shell the pinned tools directly and do not use the
comparator). The measured digests are in ## Metrics.

## Residuals

- Determinism is scoped to pypdf 6.14.2. Nothing in the repository pins
  pypdf, so a `uv` resolution that moves pypdf changes `mag capture`'s output
  for PDF sources silently. That is true today, before any port, and is worth
  a pin regardless of how this WP is resolved.
- `mag/src/capture.rs:642-667` (`pdf_to_extraction`) also derives the synopsis
  by splitting on the literal `"Abstract"` and taking 40 words, and
  `pdf_title` reads the article text. Any change to extraction output changes
  those too; they are in this WP's Owns and would move with it.
- The `.magazine/capture/` directory is untracked, so the one real fixture is
  not in version control and would not survive a fresh clone. Whatever
  fixtures this WP eventually uses must be committed or regenerable.

## Recommendation

The plan's own escape hatch ("else `awaiting-fran` with the variance and a
proposed structural oracle") was written for the non-deterministic branch. The
script is deterministic, so that branch does not apply, but the byte-identical
oracle is unreachable for a different reason, and the decision belongs to the
plan rather than to this WP. Three options, with what each costs and licenses:

1. **Port pypdf's text layer faithfully, bounded by fail-loud.** 1,701 lines
   of algorithm plus the reachable subset of 18,452 lines of tables, refusing
   loudly on any construct outside the ported subset (fonts without
   `/ToUnicode`, unhandled encodings, orientations outside `(0, 90, 180, 270)`).
   This is the only option that satisfies both the stated oracle and
   CLAUDE.md's verbatim rule. It is 2 to 3 WPs, not one, and it permanently
   pins the magazine's capture quality to pypdf's heuristics including the
   `0.8`, `0.95` and half-space constants.
2. **Re-scope the oracle deliberately, and choose extraction on quality.**
   Accept that no shipped artifact and no parity clause depends on reproducing
   pypdf's bytes: past captures are already committed as `article.md` and never
   re-derived, so byte-identity only governs future captures. Then pick the
   extractor that transcribes best, require it to preserve hyphenated line
   breaks (poppler as configured does not), and make the oracle a stated
   fidelity property plus a human read of one real capture. This is cheaper and
   honest, but it is a deliberate behaviour change to source capture and needs
   Fran, since CLAUDE.md governs capture fidelity.
3. **Keep `tools/pdf2md.py` as a scoped exception to WP-6.1.** Cheapest, and
   contradicts WP-6.1's target that no Python runs anywhere. Only defensible if
   PDF capture is rare enough to carry a documented Python dependency.

My recommendation is **2**, with the hyphen-preservation requirement written
into the plan as a named check, and **1** if Fran wants byte-identity retained;
**3** should be rejected because it leaves a Python toolchain in the pipeline
for one script. Either of 1 or 2 also needs the fixture problem solved first:
one real captured PDF exists, so the plan should either require capturing two
more real PDF sources before this WP runs, or state plainly that the oracle
rests on one real fixture plus synthetic ones and accept what that proves.
