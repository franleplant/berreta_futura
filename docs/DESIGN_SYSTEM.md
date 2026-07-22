# BERRETA FUTURA design system

BERRETA FUTURA is a small-format reading magazine, not a stack of web pages printed to PDF. Its production direction is **O / Monument**, selected from the archived studies in `prototypes/design-directions/`. Monument makes exact language the interior artwork: scale, pacing, circles, and white space provide delight without recycling the cover image.

## Design position

The system combines literary reading typography with the visual confidence of an art and graphic-design journal. It is deliberately sparse rather than minimal for its own sake: hierarchy is emphatic, provenance remains unmistakable, and long-form pages stay calm.

The issue artwork appears exactly once, on the front cover. It is not repeated, cropped into interior pages, used as a watermark, or treated as a source for the interior palette. Each issue interprets its theme through a shared synthetic cover grammar; layout typography remains deterministic and independent.

## Cover artwork

Cover art is a compact graphic proposition, not a miniature narrative scene. Each issue gets one dominant abstract construction made from a few exact shapes. The composition changes with the editorial theme, while its restraint makes the series recognizable.

- Use one central proposition with a thumbnail-readable silhouette.
- Use three to seven geometric components, including any line or signal point.
- Preserve at least one large, uninterrupted field of negative space.
- Build from large, hard-edged color fields. Restrained tonal movement inside a field is acceptable; texture, grain, glow, pictorial lighting, and fussy surface rendering are not.
- Avoid people, hands, robots, rooms, machinery, circuit boards, scattered cubes, and literal diagrams.
- Use the cover ink set: warm paper `#F1EADB`, near-black `#11131A`, ultraviolet `#5332C8`, and a small signal-orange accent `#FF5A1F`.
- Keep signal orange below five percent of the artwork area.
- Keep every letter in layout code. Artwork contains no masthead, title, issue number, caption, logo, or watermark.
- Whether generated or code-native, production art must reduce to a few intentional shapes and survive at thumbnail size without relying on incidental detail.

Edition 2 establishes the first motif: one oversized input crosses a severe gate and becomes a disciplined sequence of outputs. The diagonal, full-bleed composition carries pressure and multiplicity without drawing a literal factory.

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

The permanent publication wordmark is a compact, uppercase Inter Bold lockup: `BERRETA` in near-black followed immediately by `FUTURA` reversed from a violet block, with a short signal-orange register rule beneath the left edge. Tight spacing makes the two words read as one name; the block supplies the deliberate rupture between improvised present and designed future. The wordmark is always rendered by layout code from `publication.name`, never embedded in issue art, translated, or combined with issue metadata.

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

The cover opens with the permanent BERRETA FUTURA wordmark at full live width, followed by a display title, circular issue medallion, single centered 250 × 250 pt framed artwork placement, complete deck, and private-edition metadata. It does not repeat the subtitle or turn topics into a decorative rail. Edition 2's 1254 × 1254 px production artwork resolves at 361.2 ppi in this placement. Layout code owns every letter; the raster asset contains no masthead or cover lines.

### Contents

Contents use staggered rows, oversized violet folios, restrained rules, and a circular issue mark. Six entries fit on one page; additional entries paginate into further Monument contents pages. Folios come from the renderer's deterministic probe, planned draft, and final layout passes.

### Opening editorial

The opening sentence is split from the first source block and rendered once at monumental scale. The remainder flows immediately into the reading frames without duplication or omission. The editorial title, byline, `ORIGINAL EDITORIAL` label, and `AN ORIGINAL ARGUMENT` treatment remain visible, and the complete editorial may occupy at most two reader pages.

### Feature openers

Each opener combines the exact localized title around one curated Monument word. Three controlled arrangements—`edge_medallion`, `split_axis`, and `stepped_title`—vary alignment, rule structure, and medallion treatment while sharing one collision-safe title, credit, and body architecture. A numbered medallion, author, author note, and exact content-mode label remain explicit. `FAITHFUL EDIT`, `FAITHFUL SYNTHESIS`, `SELECTED EXTRACTS`, and `ORIGINAL SYNTHESIS` are provenance facts, never interchangeable decorations.

### Continuation pages

Copy flows left frame, right frame, then the next page. When greedy flow would strand a lightly occupied terminal page, a probe redistributes the unchanged final four continuation frames to a shared, leading-quantized depth while preserving text order, page count, and page caps. Exact short running titles and separate continuation markers replace mechanical ellipses; the secondary marker keeps a 21 pt baseline clearance above continuation copy. Violet section bridges, circular outer-margin signals, running matter, and generous white space carry the O identity without interior imagery. Quotations, bullets, headings, and code retain distinct deterministic treatments. Display headings add 10–16 pt of space before (except at a fresh frame) so a new section never appears attached to the preceding paragraph.

### Backmatter and back cover

Backmatter uses the same opener and continuation system. The back cover renders the configured issue statement, visibly labels it as editor-owned text, and closes with a localized END/FIN medallion. It never substitutes an unattributed source quotation.

## Guardrails

- Do not draw the cover artwork anywhere after page 1.
- Keep reader page 2 and the penultimate reader page completely blank as the inside covers.
- Do not infer palette colors from an edition's artwork.
- Do not choose a production Monument word with an unreviewed heuristic when localized metadata is available.
- Do not truncate a running title; require a localized short title that fits its measured header zone.
- Scope tracked-letter labels so character spacing cannot leak into reading text.
- Do not shrink body copy to solve page budgets; edit or synthesize faithfully.
- Do not let a running head cross an opener composition.
- Preserve the two-page editorial and seven-page source-article limits.
- Generate every configured language on validation and build.
- Run the render critic for every configured language; structural errors block the build.
- Inspect every numbered render-review contact sheet after layout changes and before delivery.
- Record independent approval with `mag review record`; release requires hashes matching every current language PDF.
- Do not call an edition press-ready without a named printer profile and a passing studio preflight.
