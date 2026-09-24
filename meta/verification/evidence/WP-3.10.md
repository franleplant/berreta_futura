# WP-3.10 non-primary languages on the typst engine

## Base

Built on `art_directed` `9bcc6a8` (queue after WP-5.6), rebased onto `06b5dc4`
(WP-0.2y and WP-5.4g/5.3g: comparator domain 1..n, critic clause in Tier S) before
landing. Every gate below was re-run on the rebased tree. The step table is
history from the pre-rebase comparator. Detached worktree `.../tmp/wp310`, its own
`mag/target`.

**Status: met on the Spanish fixture.** `--engine typst` renders every requested
language the way the bridge does. The es interior compares green on every
evaluated clause, including Tier E. The cover faces are pixel-equal at 300 dpi in
both languages. The package file sets and web trees are equal. 010 en does not
regress: staged parity exits 0, ratchet target E, 0 regressions.

## Which edition

No committed edition from 005 to 010 has a Spanish translation. Nothing in the
current pipeline writes `editions/NNN/translations/es/edition.yaml`, which is what
both engines load: `mag translate` writes `run/translations/es/articles/*.md`
only. The newest edition that does carry one is 004. The current bridge refuses
it (`mag render 004 --engine weasyprint --no-model --run
editions/004/run-2026-08-05T19-35-30`, exit 1): its content modes
`faithful_synthesis`/`faithful_edit` are no longer valid, and one tail repeats its
opener art. The other 004 runs need model anchor patching. So the WP is measured
on a new fixture, **906**
(`mag/tests/typeset_fixtures/corpus/editions/906`). It has two illustrated
articles, an evidence-band figure, eight plates, `footer_caption` cover art, and
an es translation (`locale: es-AR`) with parallel castellano text. That text
includes long words, «», ¿?, a translated figure caption and anchor, and plate
titles.

## What changed

- **Language loop** (`typeset/mod.rs`). `run_request` stages once, then renders
  each language in request order, as `_render` does. The primary language comes
  from `load_edition`, the others from `load_translation`. Each language gets its
  own `render/<lang>/` output and its own typst work dir (`typst/` for the primary,
  `typst-<lang>/` for the others). The per-language `layouts` and `files` are
  concatenated. The refusal WP-5.6 added is gone. `layout::report` takes the
  Edition instead of reloading it. `content::compose` (settable set + metrics +
  build) is the production entry, and `pipeline`/`Inputs` are now test-only.
- **Web alternates** (`typeset/release.rs`). `alternates` is
  `{other: ../../other/web/}`, as in the bridge. The en and es web trees are
  byte-equal to the bridge's.
- **Staging** (`render.rs`). `translations/es/source-codes/` is staged when
  present. Both engines look up an opener's QR next to the nearest `edition.yaml`
  above the manuscript, which for a translation is `translations/es/`. Without
  this file the bridge refused 906 es ("No committed source code for article
  hyphenation-article").
- **Spanish hyphenation, as WeasyPrint 69 sets it.** The stylesheet hyphenates
  body prose with `hyphens: auto; hyphenate-limit-chars: 6 3 3` in every language
  but English (`weasyprint-a5.css:557-690`). Typst's own hypher dictionary is not
  Pyphen's, so:
  - `typeset/hyphen.rs` ports Pyphen 0.17.2 (`HyphDict.positions`, `left`/`right`
    3, words shorter than 6 skipped) over the vendored `hyph_es.dic`
    (`mag/assets/typeset/hyph_es.dic`, copied byte for byte from pyphen's
    package). English gets no dictionary. Any other language is refused with a
    message naming the locale: nothing is hyphenated silently with the wrong
    rules. Cross-check: 5348 distinct Spanish words of 6 or more letters from the
    001-004 translations give output identical to `pyphen.Pyphen(lang='es',
    left=3, right=3).inserted` (`diff` exit 0).
  - `content.rs` inserts U+00AD at those points, only where the stylesheet's
    prose selectors hyphenate. That covers body paragraphs, a split standfirst's
    remainder, list items except an unordered reference list, blockquote
    paragraphs, extract quote lines and captions, and key ideas. It excludes
    standfirsts, name rosters, headings, opener furniture, figure captions and
    inline code. Typst breaks at a soft hyphen even with `hyphenate: false`.
  - `runt.rs` reproduces a WeasyPrint 69 defect on purpose. In `split_first_line`
    step 3, `break_point -= len(first_line_text) + 1` subtracts the offset twice.
    When `len(second) + break_point - L - 1 <= 0`, `next_word` is empty and the
    function returns before step 4, so no hyphenation is tried. This happens near
    a paragraph's end, or with a long first line under the 130-character
    `short_text` cut. `attempted()` evaluates that rule after each layout pass. A
    hyphen WeasyPrint would not have tried gets its word's soft hyphens removed,
    and the page is laid out again inside the existing runt-bind loop. Measured
    case: "dividirse legí‐" (typst) vs "dividirse / legítimamente" (oracle).
    **This matches the oracle, and the oracle is wrong here**: the rule only holds
    while the bridge is the reference. WP-4.3 should decide whether to keep it.
  - `text_shim.rs`: typst shapes the break hyphen as its own item, maps it to
    U+00AD and does not kern it. Pango sets `word‐` as one run with the letter
    kerned against U+2010. The shim merges the hyphen into the word's run, adds
    the pair kern (rustybuzz shaping of `<letter>‐` on the same face, new direct
    dependency `rustybuzz = "0.20"`, already in Cargo.lock through typst), and
    rewrites the text to U+2010. Soft hyphens folded into a letter's cluster are
    removed from the item text, so the PDF text reads "tipógrafo", not
    "tipó\u{ad}grafo". `runt.rs` counts a line ending in U+00AD as hyphenated.
- **Fallbacks.** A missing `design.toml` now loads the Python compiler's built-in
  design (`cover.py:184-231`). Missing `[layout.footer_caption]` /
  `[layout.honored_plate]` keys take `cover.py`'s `spec.get` defaults
  (25/0.8/6/26, 17/64/0.5/19). A `framed` cover without art draws the violet
  placeholder rect and circle (`cover.py:423-436`). `footer_caption` and
  `honored_plate` without art refuse, as Python's `_full_art` does. The
  `mag/src/cover/svg.rs` change is `framed` split into `framed` +
  `framed_with(text, art_markup)`.

## Commands and results

```sh
M=mag/target/release/mag; S=<scratch>
# fixture copied into editions/906 + library/sources for the run, moved out after
$M render 906 --engine weasyprint --no-model        # oracle, en + es, exit 0: render-2026-09-24T11-08-24
$M render 906 --engine typst --no-model             # final binary, en + es, exit 0: render-2026-09-24T12-03-38
$M parity 906 --pre-rendered W T                    # en: exit 0
es.sh W T                                           # es: exit 0 (below)
$M parity 010 --run editions/010/run-2026-09-13T01-34-51     # staged, uv on PATH: exit 0
(cd mag && cargo fmt --check && cargo clippy --all-targets -- -D warnings && cargo test)
#   all exit 0; 32 result lines, 942 passed, 0 failed (nocomments included), rebased
```

Rebased comparator (domain 1..n, covers and critic included):
- 906 es: exit 0. page_count 16/16, **critic pass** (643 leaves compared, 0
  differ), text 16 pages, colour, navigation, G, **E glyph positions 3513 glyphs,
  0 violations, E display list 3557 vs 3557**, V worst 0.000237.
- 906 en: exit 0 (critic pass, display list 3188/3188, glyphs 3144, 0
  violations).
- 010 en staged: exit 0. Inputs fresh `bc49b2aa...`, ratchet pass (target E, 56
  measured, 0 regressions), critic pass, display list 59304 vs 59304, glyphs
  59073, 0 violations.

`mag parity --adhoc` cannot cover a non-primary language, and neither can
`--pre-rendered` as written. `parity.rs:476` renders legs with `langs:
Some("en")`, and `parity.rs:875` and `:1028` read `en/reader.pdf`. The es legs
were compared with `--pre-rendered` over alias dirs whose `en` is a symlink to
each leg's `es/` (`es.sh`). **The parity.rs change that would let `--adhoc` cover
it**: a `--lang <code>` option. It would pass `langs: Some("en,<code>")` in
`render_leg`, read `<code>/reader.pdf` at 875/1028 (and the cached-oracle check),
and suffix the out dir with the language. Not edited (not this WP's file).

### 906 es, bridge vs typst, measured along the way (each row a real run)

| step | S text | S colour | E display list | E glyph positions |
|---|---|---|---|---|
| loop only (typst unhyphenated) | fail p10, p11 | fail 3 pages | fail 3 pages | fail 3 |
| + Pyphen soft hyphens | fail p5, p10 | fail (`ó\u{ad}` cluster text) | fail 3 pages | 3 |
| + shim text cleanup, U+2010 | pass | fail p5 (`legíti‐`) | fail p5 | 3 |
| + WeasyPrint step-3 rule | pass | pass | **pass** | 5 (hyphen kern, 0.05-0.24 pt) |
| + merged, kerned hyphen run | **pass** | **pass** | **pass (3356 vs 3356)** | **pass (3316 glyphs, 0 violations)** |

Final es (pre-rebase comparator, interior 2..15): page_count 16/16, boxes pass, G max dy 0.006, navigation pass (10
links, 8 outlines, title, lang), V pass (worst 0.000237), exit 0. The en leg of
906 is also exit 0 (display list 3006/3006, glyphs 2966, 0 violations).

### Outside the comparator's 2..n-1 domain (final binary)

| entry | en | es |
|---|---|---|
| reader.pdf p1 and p16 (cover faces), pdftoppm 300 dpi, cmp | equal | equal |
| file set | equal, 78 | equal, 76 |
| web/ | byte-equal, 28 | byte-equal, 28 |
| edition-manifest.json | equal except `design_direction` | equal except `design_direction` and one path (below) |
| printing instructions, studio/README.md, SHA256SUMS file list | equal | equal |
| preflight.json (stage root normalized) | equal | equal |
| render-critic result | pass / pass | pass / pass |

Positive control: en p1 vs es p1 on the bridge leg, `cmp` exit 1.

Fallbacks, both engines, covers compared at 150 dpi:
- `design.toml` moved out of the worktree: both engines exit 0, en/es p1/p16
  pixel-equal. Control: identical to the with-file render, because the file's
  values equal the built-in ones. This proves the fallback loads, not that its
  numbers differ from the file. The unit test pins the numbers.
- A scratch copy of 906 as `framed` with no `art_path`: both exit 0, en/es p1/p16
  pixel-equal, violet placeholder visible. Before this WP, typst refused both
  cases (WP-5.6 evidence).

## Tests added

- `hyphen.rs`: Spanish division (res-pon-sa-bi-li-dad, inter-na-..., guio-nes,
  Com-puesta, tipó-grafo, «...» boundaries, short words untouched). English gets
  none, and pt-BR is refused.
- `runt.rs` `weasyprint_tries_a_hyphen_only_while_its_negative_word_slice_is_not_empty`:
  the three measured 906 lines (true, true, false), plus the same "glón" line in a
  paragraph over 130 characters, which flips to true.
- `text_shim.rs` `a_soft_hyphen_break_is_one_run_ending_in_a_kerned_u2010_as_pango_sets_it`:
  typst's own U+00AD item is gone, "ser‐" is one item, and r's drawn advance
  carries the r/hyphen kern (445 -> 419 per mille, under Pango truncation).
- `content.rs` `a_translation_sets_its_locale_and_labels_and_breaks_only_body_prose_at_pyphen_points`:
  906 es emits `lang: "es", region: "AR"`, "Artículo 01", soft hyphens in body
  prose, none in the standfirst or headings, none anywhere in 906 en.
- `cover.rs`: built-in design numbers and per-key layout defaults, the framed
  placeholder markup, and refusal of footer_caption/honored_plate without art.

## What is and is not proven

PROVEN: on 906, `--engine typst` renders en and es with the bridge's outputs and
layout per language. The es interior is equal on every evaluated Tier S/G/E
clause, and V passes. The Spanish cover faces are pixel-equal. Pyphen's Spanish
points are reproduced on 5348 words. 010 en is unchanged under staged parity
(target E, 0 regressions). The design.toml and framed-without-art fallbacks
render as Python renders them.

NOT PROVEN:
- **No real Spanish edition was rendered.** None exists that the current
  pipeline can load. 906 covers two articles of plain prose. Lists, blockquotes,
  extracts, key ideas, references and editorials with soft hyphens are wired but
  not compared.
- The step-3 rule treats a paragraph as one text box, which is exact only for
  plain text. When an inline element (emphasis, link, inline code) starts a new
  WeasyPrint text box on the line that breaks, the box's own L, max width and
  130-character cut differ. Links and emphasis are split by style key, but no
  fixture exercises them.
- Break opportunities in that rule are spaces only. Pango's UAX 14 also breaks
  after hyphens and dashes.
- Typst decides line fit with the unkerned hyphen, and Pango with the kerned one.
  A line within the kern (up to 0.24 pt) of the measure could break differently.
  Not observed.
- A paragraph whose hyphenation changes the page count was not exercised.

For the orchestrator:
- **Pipeline gap (not this WP's area):** nothing writes
  `editions/NNN/translations/es/edition.yaml` or `translations/es/source-codes/`.
  Both engines need them to publish Spanish. A Spanish edition with openers that
  carry a source URL fails on both engines until the codes are copied there (or
  until the lookup falls back to the base edition's `source-codes/`, which would
  be the correct behaviour: the QR payload is the same URL).
- **Wrong on both legs:** a translated figure's `edition.articles[].figures[].path`
  in es `edition-manifest.json` is an absolute staging path. The bridge writes a
  deleted temp dir, typst writes `.../staged/...`. The correct value is en's
  source-relative `media/diagram.png`. Owner: `model/manifest.rs`
  `translation_raw` (Python `_translation_raw`).
- parity.rs `--lang` (above) is owned by the parity agent.
