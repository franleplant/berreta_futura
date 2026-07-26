# BERRETA FUTURA design system

BERRETA FUTURA is a small-format reading magazine, not a stack of web pages printed to PDF. Its production interior is **A / Quiet Standard**, selected on 2026-07-22 from the retained A/B study in `prototypes/interior-reading-prototype/`. Quiet Standard uses book typography, a single calm reading measure, useful images, and white space without turning navigation into ornament. **B / Signal Manual** remains in that study as a future technical alternative.

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
| Display | Source Serif 4 Display Semibold | Article and section titles, editorial title, section headings |
| Reading | Source Serif 4 Small Text Regular | Body and standfirsts |
| Emphasis | Source Serif 4 Small Text Italic/Bold | Quotations and emphasis |
| Navigation | Inter Regular/Medium/Semibold/Bold | Running matter, credits, mode labels, folios |
| Code | Courier | Source code only, always in a full-width frame |

Body copy is 10/13 pt by default in Source Serif 4 Small Text. A visually dense feature with dedicated landscape plates may use 10/12.2 pt and 4 pt paragraph spacing so its prose remains continuous around the plates without shrinking the type. Standfirsts use 12/16.4 pt. Captions and navigation use 6.8 pt Inter at A5, while the image itself must remain legible at print size. Feature manifests retain localized short titles and legacy opener metadata for compatibility, but Quiet Standard deliberately renders one consistent opener rather than decorative per-article variants.

The permanent publication wordmark is the **Corte bruto** lockup: `BERRETA` in tightly compressed near-black Inter Bold, with `FUTURA` dropped across it in a skewed black printer's slug. A deliberately misregistered orange impression remains visible beneath the reversed white letters. The mark behaves like an exact paste-up rather than a polite masthead. The cover compiler outlines it from the bundled font into the canonical SVG; it is never embedded in issue art or translated.

The cover's **Canto vivo** is a full-height signal-orange fore-edge tab. It carries the issue number at the head and `BERRETA FUTURA / BUENOS AIRES` at the foot, so orange functions as navigation when editions are stacked or shelved. The only footer metadata is the publication date in `YYYY MM DD` form. Do not add format, distribution, repeated issue/date, proof labels, or generic `COVER` metadata to the front cover.

The reader sets real punctuation, not ASCII substitutes: curly quotation marks in English, `« »` in Spanish, a true ellipsis, a true arrow, and en and em dashes. The rule is the bundled faces' own repertoire — a character every shipped face can set reaches the page unchanged, and one that no face can set becomes a visible `?` rather than a silent host-font glyph in the middle of Source Serif.

The bundled font files and SIL Open Font License texts live under `src/magazine/assets/fonts`. Deterministic builds must not use system font lookups. Cover geometry and inks live in `design/covers/canto-vivo/design.toml`; the materialized SVG contains named slots for the wordmark, headline, art, deck, footer, and both tab labels.

## Color

| Token | RGB intent | Use |
| --- | --- | --- |
| Ink | near-black blue | Reading text and principal display type |
| Violet | deep process violet | Provenance labels, figure numbers, end marks, restrained navigation |
| Slate | neutral gray | Secondary metadata |
| Cool gray | light neutral | Contents separators and quiet structure |
| Pale violet | very light tint | Code panels only |
| White | unprinted sheet | Every page background, including the front cover |
| Signal orange | muted vermilion | Canto vivo tab and wordmark underprint; tiny continuation and end signals inside |

The cover artwork does not determine the interior colors. Violet is a publication-level navigation color and stays a minority of each interior page. Signal orange is the exact Canto vivo vermilion: inside the magazine it appears only as a short tick at the start of continuation rules and as the line in an article end mark. It never becomes a panel, heading color, or decorative wash. The Canto vivo cover retains the white sheet and calibrates only its artwork-matched violet, near-black, and muted vermilion inks to the approved cover proof.

## A5 page architecture

- Trim: A5 portrait, imposed two-up on A4 landscape for home printing.
- Inside covers: reader page 2 and the penultimate reader page are completely blank. Ordinary imposition keeps their shared A4 booklet side completely blank.
- Mirrored margins: 44 pt inner and 15 mm (42.52 pt) outer.
- Grid: six columns with 9.45 pt gutters.
- Live vertical range: 45–543 pt for single-column pages and 40–551 pt for continuation frames.
- Continuations: one centered 325 pt reading measure; double-column text is prohibited.
- Opener copy: the same reading measure beneath a full-width title and byline.
- Figures: full live measure when their aspect ratio remains useful at A5, otherwise contained without cropping. Label-dense panoramic diagrams use a dedicated sideways landscape plate so their internal type survives A5 printing; a plate may open or close its anchored section. Adaptive bands may reduce an uncomplicated chart only to a declared minimum, while compact bands reserve room for the conclusion on the same page. Figures stay at their semantic anchor and may appear at the top, middle, or on an opener.
- Running matter: publication at left and curated short title at right above one quiet gray rule, begun by a 14 pt signal-orange tick.
- Folios: publication at the lower left and the page number at one invariant lower-right baseline on every ordinary interior page.
- Headlines keep following copy with them when pagination allows.
- Fenced code moves to a full-width frame rather than becoming unreadably narrow.

## Page types

### Front cover

The cover opens with the permanent Corte bruto wordmark and Canto vivo edge tab. The issue title is a tightly compressed sans construction with staggered violet lines; no generic display serif or circular badge remains. Beneath it sit the approximately 250 × 249 pt framed artwork, a contributor register derived from the rendered articles' author records, and the date-only footer. Never substitute generic promotional deck copy for the actual contributors. Edition 2's 1254 × 1254 px production artwork resolves above 361 ppi in this placement. The canonical SVG owns every outlined visible letter; the generated PDF adds an invisible bundled-font text layer so the masthead, title, contributors, and date remain searchable and selectable. The raster asset contains no masthead or cover lines.

Use `uv run --locked mag cover-proof <edition-id>` for the fast primary-language design loop and add `--all-languages` before final build. The command writes the canonical SVG, exact production cover PDF, PDF-derived proof PNG, comparison overlay/diff, and a hash manifest without typesetting the interior. A full build splices that exact PDF into page 1.

### Contents

Contents use a simple serif title, oversized violet folios, restrained rules, and deliberate negative space. The redundant circular issue medallion is prohibited; the tracked kicker already identifies the issue. Folios come from the renderer's deterministic probe, planned draft, and final layout passes.

### Opening editorial

The editorial uses the same title, byline, standfirst, and single-column reading grammar as the features. `ORIGINAL EDITORIAL` and `AN ORIGINAL ARGUMENT` remain explicit, and the complete editorial may occupy at most two reader pages. Its first-page frame is intentionally shallower so the second page receives a meaningful continuation rather than a stranded final line.

### Feature openers

Each opener uses one consistent structure: provenance kicker, large serif title, author and author note, then a standfirst in the reading measure. An opener-anchored figure may use the available lower field; prose begins on the next page when the figure consumes that depth. `FAITHFUL EDIT`, `FAITHFUL SYNTHESIS`, `SELECTED EXTRACTS`, and `ORIGINAL SYNTHESIS` are provenance facts, never interchangeable decorations.

### Continuation pages

Copy flows down one reading measure and then to the next page. Exact short running titles, a quiet header rule, consistent folios, and generous white space carry the identity. Quotations, bullets, headings, and code retain distinct deterministic treatments. Display headings add deliberate space before them except at a fresh frame; a heading that anchors a full-width evidence band is the one exception, and a known open defect — it currently follows its paragraph on 2.65pt of clearance where every other heading has 17.65pt (see `docs/RENDERER_MIGRATION.md`). The final prose paragraph stays together when it fits on one page, making article endings read as intentional conclusions rather than split scraps. A paragraph never ends on a single short word stranded on its own line: the last two words are bound so they wrap together whenever that final word would take less than a seventh of the measure.

### Source codes

A printed page cannot be followed, so every article ends with a QR square carrying the canonical URL of its **first** source id — one code per article, never one per source, because the opener already prints the whole source list. There is no printed URL label; the code is the whole of it. An article whose first source records no canonical URL prints nothing, and the editorial, which has no source, never does.

The code is drawn in the house inks — INK modules, VIOLET finder patterns, over the paper — as vector SVG, so it is exact at any print density. Its size is computed from the URL, not chosen: the module is 0.85mm wherever the page has room, and the square is simply as wide as that URL's symbol needs.

Where it stands is the page's decision and not the author's. The same open-space test that used to earn an article its tail motif now earns its code the large slot at the foot of the reading measure; the motif itself no longer prints and `tail_art_path` is vestigial. An article whose last page has no such room drops its code into the foot margin instead, between the two ends of the folio, at whatever module that band can carry. Both slots are out of flow and can never move a line or open a page. A cramped code gives back error correction rather than cell width, because cell width is what a phone camera needs; below a 0.35mm module the build refuses outright.

Every code is then read back off the rasterized page at 300 ppi by an independent barcode reader, and a build whose code does not decode to its own canonical URL is refused before the PDF is written. A code that looks right and does not scan is worse than no code at all, and nothing but a decode can tell the two apart.

### Backmatter and back cover

Backmatter uses the same opener and continuation system. The selected Signal fold back cover is a full-bleed orange closing poster with giant localized LOOP CLOSED / CICLO CERRADO display type, a protected vertical identity corridor, and a white statement insert. The insert renders the configured editor-written closing statement without a redundant ownership caption; the lower slug closes with localized END/FIN and the numeric date. It never substitutes an unattributed source quotation.

The back face is compiled through `uv run --locked mag back-cover-proof <edition-id>` using the same outlined SVG -> one-page PDF -> PDF-derived PNG contract as the front. The generated PDF includes an invisible bundled-font text layer so every word remains searchable and selectable. A full build replaces both outer reader pages in one splice, and A4 imposition consumes that exact reader.

## Guardrails

- Do not draw the cover artwork anywhere after page 1.
- Keep inside covers and their shared imposed booklet side completely blank; do not add an imposition-only ornament layer.
- Do not infer palette colors from an edition's artwork.
- Do not truncate a running title; require a localized short title that fits its measured header zone.
- Scope tracked-letter labels so character spacing cannot leak into reading text.
- Do not shrink body copy to solve page budgets; edit or synthesize faithfully.
- Do not let a running head cross an opener composition.
- Do not reintroduce double-column prose.
- Do not pin every figure to a page edge; keep it in semantic flow and preserve a useful printed size.
- Keep every ordinary folio on the shared lower-right baseline.
- Do not print a source code the build has not decoded back off its own rasterized page.
- Do not set a source URL as type; the reading measure cannot break one, and the code is the link.
- Preserve the two-page editorial and seven-page source-article limits.
- Generate every configured language on validation and build.
- Run the render critic for every configured language; structural errors block the build.
- Inspect every numbered render-review contact sheet after layout changes and before delivery.
- Record independent approval with `mag review record`; release requires hashes matching every current language PDF.
- Do not call an edition press-ready without a named printer profile and a passing studio preflight.
