# BERRETA FUTURA design system

BERRETA FUTURA is a small-format reading magazine, not a stack of web pages printed to PDF. Its production direction is **O / Monument**, selected from the archived studies in `prototypes/design-directions/`. Monument makes exact language the interior artwork: scale, pacing, circles, and white space provide delight without recycling the cover image.

## Design position

The system combines literary reading typography with the visual confidence of an art and graphic-design journal. It is deliberately sparse rather than minimal for its own sake: hierarchy is emphatic, provenance remains unmistakable, and long-form pages stay calm.

The issue artwork appears exactly once, on the front cover. It is not repeated, cropped into interior pages, used as a watermark, or treated as a source for the issue palette. Every issue may supply unrelated artwork; layout typography remains deterministic and independent.

## Typography

| Role | Typeface | Default use |
| --- | --- | --- |
| Monument | Inter Semibold | One curated word on each feature opener, issue medallions |
| Display | Source Serif 4 Display Semibold | Covers, surrounding title language, editorial sentences, section bridges |
| Reading | Source Serif 4 Small Text Regular | Body and standfirsts |
| Emphasis | Source Serif 4 Small Text Italic/Bold | Quotations and emphasis |
| Navigation | Inter Regular/Medium/Semibold/Bold | Running matter, credits, mode labels, folios |
| Code | Courier | Source code only, always in a full-width frame |

Body copy is 9.55/12.6 pt by default. The opening editorial uses 9.55/12 pt within its hard two-page cap. Captions and navigation never fall below 7 pt. Feature manifests provide a localized `display_emphasis`, a source-faithful `short_title`, and one of three controlled `opener_variant` values. The compiler validates all three rather than choosing display or navigation language heuristically.

The bundled font files and SIL Open Font License texts live under `src/magazine/assets/fonts`. Deterministic builds must not use system font lookups.

## Color

| Token | RGB intent | Use |
| --- | --- | --- |
| Ink | near-black blue | Reading text and principal display type |
| Violet | deep process violet | Monument words, medallions, labels, rules, navigation |
| Slate | neutral gray | Secondary metadata |
| Cool gray | light neutral | Contents separators and quiet structure |
| Pale violet | very light tint | Code panels only |
| White | unprinted sheet | Every page background |

The cover artwork does not determine these colors. Violet is a publication-level navigation color and stays a minority of each interior page. The renderer never prints a fake cream paper field.

## A5 page architecture

- Trim: A5 portrait, imposed two-up on A4 landscape for home printing.
- Mirrored margins: 44 pt inner and 15 mm (42.52 pt) outer.
- Grid: six columns with 9.45 pt gutters.
- Live vertical range: 45–543 pt for single-column pages and 40–551 pt for continuation frames.
- Continuations: two balanced text frames on the six-column grid.
- Opener copy: a narrower centered frame beneath the display composition.
- Running matter: curated short titles at 7 pt with a separate localized continuation marker; folios at the outer foot with a 0.8 pt violet register rule.
- Headlines keep following copy with them when pagination allows.
- Fenced code moves to a full-width frame rather than becoming unreadably narrow.

## Page types

### Front cover

The cover uses a single 250 × 250 pt framed artwork placement, a display title, a circular issue medallion, a rotated subject rail, the complete deck, and private-edition metadata. The current 1054 × 1492 px artwork resolves at about 303.6 ppi in this placement. Layout code owns every letter; the raster asset contains no masthead or cover lines.

### Contents

Contents use staggered rows, oversized violet folios, restrained rules, and a circular issue mark. Six entries fit on one page; additional entries paginate into further Monument contents pages. Folios come from the renderer's deterministic probe, planned draft, and final layout passes.

### Opening editorial

The opening sentence is split from the first source block and rendered once at monumental scale. The remainder flows immediately into the reading frames without duplication or omission. The editorial title, byline, `ORIGINAL EDITORIAL` label, and `AN ORIGINAL ARGUMENT` treatment remain visible, and the complete editorial may occupy at most two reader pages.

### Feature openers

Each opener combines the exact localized title around one curated Monument word. Three controlled arrangements—`edge_medallion`, `split_axis`, and `stepped_title`—vary alignment, rule structure, and medallion treatment while sharing one collision-safe title, credit, and body architecture. A numbered medallion, author, author note, and exact content-mode label remain explicit. `FAITHFUL EDIT`, `FAITHFUL SYNTHESIS`, `SELECTED EXTRACTS`, and `ORIGINAL SYNTHESIS` are provenance facts, never interchangeable decorations.

### Continuation pages

Copy flows left frame, right frame, then the next page. When greedy flow would strand a lightly occupied terminal page, a probe redistributes the unchanged final four continuation frames to a shared, leading-quantized depth while preserving text order, page count, and page caps. Exact short running titles and separate continuation markers replace mechanical ellipses. Violet section bridges, circular outer-margin signals, running matter, and generous white space carry the O identity without interior imagery. Quotations, bullets, headings, and code retain distinct deterministic treatments.

### Backmatter and back cover

Backmatter uses the same opener and continuation system. The back cover renders the configured issue statement, visibly labels it as editor-owned text, and closes with a localized END/FIN medallion. It never substitutes an unattributed source quotation.

## Guardrails

- Do not draw the cover artwork anywhere after page 1.
- Do not infer palette colors from an edition's artwork.
- Do not choose a production Monument word with an unreviewed heuristic when localized metadata is available.
- Do not truncate a running title; require a localized short title that fits its measured header zone.
- Scope tracked-letter labels so character spacing cannot leak into reading text.
- Do not shrink body copy to solve page budgets; edit or synthesize faithfully.
- Do not let a running head cross an opener composition.
- Preserve the two-page editorial and seven-page source-article limits.
- Generate every configured language on validation and build.
- Render and inspect every reader page and every imposed booklet side after layout changes.
- Do not call an edition press-ready without a named printer profile and a passing studio preflight.
