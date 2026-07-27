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

Copy flows down one reading measure and then to the next page. Exact short running titles, a quiet header rule, consistent folios, and generous white space carry the identity. Quotations, bullets, headings, and code retain distinct deterministic treatments. Display headings add deliberate space before them except at a fresh frame; a heading that anchors a full-width evidence band mid-page keeps that clearance in paint — its box stays on the paragraph's space-after so pagination cannot move, and its ink is set down by the dropped space-before so it stands 17.65pt clear like every other heading (see `docs/RENDERER_MIGRATION.md`). The final prose paragraph stays together when it fits on one page, making article endings read as intentional conclusions rather than split scraps. An article's end mark stands one point below the flow it closes on every page, and never rises into it: a last page that over-runs so far that the mark would reach the folio's own line is refused, not resolved by squeezing the mark up into the descenders above it. A paragraph never ends on a single short word stranded on its own line: the last two words are bound so they wrap together whenever that final word would take less than a seventh of the measure — unless the bind would cost the penultimate line more than a third of the measure, in which case two short lines in a row is the worse defect and the runt is left standing. A third and not a fifth: the column is set unjustified, so a penultimate line a quarter short of the measure is rag and not a fault, while a last line of one short word is a runt whatever stands above it.

A reference list is the one list whose items carry their own marker inside the text (`4 — …`), so it hangs that marker: an entry's turn line is indented by the marker's own width and stands under the entry's first letter, never on the same left edge as the entry numbers.

### Source codes

A printed page cannot be followed, so every article ends with a QR square carrying the canonical URL of its **first** source id — one code per article, never one per source, because the opener already prints the whole source list. The URL itself is never set as type. The square is named instead: `SOURCE / nn` (`FUENTE / nn`) in the same tracked violet caps as `END / nn`, standing on the symbol's own bottom edge one gap to its right, in both slots. That label is what makes the code furniture rather than a sticker applied after printing, and it is a name and not an address. An article whose first source records no canonical URL prints nothing, and the editorial, which has no source, never does.

The code is drawn in one ink — INK modules over the paper — as vector SVG, so it is exact at any print density. The finder patterns were violet and are not: on a monochrome printer a 0.18 gray is halftoned rather than printed solid, and a halftone cell the width of the module puts holes through a finder ring one module thick. The house violet lives in the label instead, which is type. Size is computed from the URL, not chosen: the module is 0.85mm wherever the page has room, and the square is simply as wide as that URL's symbol needs.

Where it stands is the page's decision and not the author's. An article that ends high enough on its last page earns the large slot and the code hangs from the slot's **head**, flush left on the reading measure, directly under the end mark — never dropped to the slot's foot, which used to leave 84–93mm between the end mark and the square. The test is the code's and not the retired tail motif's: room for a square at least twice the foot slot's, so the two printed sizes stay two classes. It is also a ceiling and not only a floor — an article that ends *very* high leaves the most room and is the page least able to absorb what the room buys, so where the square would hang with more than 60mm of empty sheet under it the code takes the small slot instead and joins the folio's line, where the page's other chrome already lives. That preference yields to legibility: a URL whose symbol cannot be set in the foot band above the 0.35mm module floor keeps the large slot its page earned. An article whose last page has no room at all drops its code into the foot margin, between the two ends of the folio, with the symbol's first dark module landing exactly on the folio baseline so the code reads as the third item on that line. Both slots are out of flow and can never move a line or open a page.

Flush and clear are measured to the **ink**, never to the element. A symbol's four-module quiet zone lives inside its own box, so the large square is set one quiet zone left of the reading measure and its first dark module lands on the same origin as the end mark's rule and every line of prose above it; and the label stands 7pt from the last dark module, the same gap the end mark's rule gives `END / nn`.

Error correction is chosen for cell width and not for redundancy: the level taken is whichever leaves the widest module in the room available, and only a tie — every slot roomy enough to set the house module — goes to the higher correction. Below a 0.35mm module the build refuses outright. On the imposed A4 booklet the page foot is the sheet's physical edge, so the small code's box stops 5.4mm above it and its first dark module 6.9mm, clear of a domestic printer's trailing margin and of duplex feed skew.

Every code is then read back off the rasterized page at 300 ppi by an independent barcode reader, and a build whose code does not decode to its own canonical URL is refused before the PDF is written. A code that looks right and does not scan is worse than no code at all, and nothing but a decode can tell the two apart.

A tail code may also be **authored**: `uv run --locked mag source-art <edition-id>` asks an image model to compose hard-edged cover-grammar shapes around each article's true symbol, and every candidate is judged by machines before an editor ever sees it. The acceptance gate decodes the artwork to the exact canonical URL at full resolution and again at the sizes the tail slot actually prints — including in grayscale, because the magazine is made on a monochrome device — measures the whole canvas against the cover ink set with signal orange held under its five percent, and requires the symbol's own dark modules to stay INK on light ground, spanning 55–85% of the square canvas at no less than the largest tail square's 300 ppi. The artwork's **ground is the sheet**: the canvas borders must read as unprinted white (warm paper survives only as a shape colour), so the printed artwork dissolves into the page instead of sitting on it as a tinted pasted rectangle. The symbol may stand anywhere the composition wants it — its position is measured, never assumed — as long as its full four-module **quiet zone** (a measured ring, its width derived from the ink span over the symbol's own module count) stays clear paper inside the canvas, and the **label band** right of the symbol on its bottom edge stays paper too, because the build sets `SOURCE / nn` there and type never prints over artwork ink. A candidate that fails anything is discarded and regenerated up to a bounded number of attempts (`--attempts`, default 3), each in a freshly cleared working directory, and a generator crash or timeout costs one attempt rather than the session; an article whose attempts run out simply keeps the plain vector code, because a build never waits on aesthetics. Accepted files land in `editions/<id>/art/source-codes/<article-id>.png` and the command prints pastable `source_code_art_path` YAML to add — it never edits `edition.yaml`, which is authored space. This is the publication's one nondeterministic step and it runs at author time only: the build consumes the committed PNG byte for byte, exempt from figure contrast preparation, its hash recorded beside the edition's other inputs and its declaration part of the copy hash every translation pins.

The build trusts none of it twice. On every layout pass the print adapter re-measures the committed PNG with the same independent decoder — payload, footprint, module count, density — and re-runs the whole ink review (palette, orange budget, INK-only modules, quiet ring, ground, label band), because ink discipline is the one thing the final decode cannot re-check: a violet module still decodes off a colour raster and then halftones into holes on the monochrome printer. There is no sidecar to go stale; the placed square grows from the plain code's own side so the symbol never prints smaller than the page fitted it (`plain side / measured span`, capped at the slot's room), and the label reads its position off the measured ink. Where the cap would betray that — the artwork's symbol printing with less ink span than the fitted plain code, or its measured module under the 0.35mm floor (a tight slot fits the plain code at ECC-L while the artwork carries the roomy reference's ECC-H, so the two module counts genuinely differ) — the page keeps the plain vector code, which is proven to fit; a declared artwork that no longer honours its own contract is instead a loud refusal, never a silent fallback. The slot stays the page's decision: only an article whose page earned the tail slot wears its artwork, the empty-sheet ceiling is judged under the element that actually prints, and the foot slot always sets the plain vector code. The Spanish overlay reuses the same file automatically, because the code is provenance and the URL is language-free. And the final gate is unchanged and non-negotiable: the finished page is rasterized and decoded exactly as for the plain code, so an artwork passes the build only the way everything else does — by scanning.

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
