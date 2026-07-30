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
| Cobalt | muted blue | Illustrated-opener kicker and first-paragraph drop cap |
| Pale violet | very light tint | Code panels only |
| White | unprinted sheet | Every page background, including the front cover |
| Signal orange | muted vermilion | Canto vivo tab and wordmark underprint; illustrated-opener image offset and tick; tiny continuation and end signals |

The cover artwork does not determine the interior colors. Violet is a publication-level navigation color and stays a minority of each interior page. Signal orange is the exact Canto vivo vermilion: inside the magazine it appears as a small navigation signal, including the illustrated-opener image offset and title tick, the start of continuation rules, and the line in an article end mark. It never becomes a panel, heading color, or decorative wash. The Canto vivo cover retains the white sheet and calibrates only its artwork-matched violet, near-black, and muted vermilion inks to the approved cover proof.

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

The editorial uses the same title, byline, standfirst, and single-column reading grammar as the features. `ORIGINAL EDITORIAL` and `AN ORIGINAL ARGUMENT` remain explicit, and the complete editorial occupies one reader page: the standard is a front door the reader takes in whole, in every language. Each edition declares its own budget in `format.max_editorial_pages` — `1` from edition 003 on; editions 001 and 002 keep the older `2`, and edition 001's released artifact actually uses both pages — and two pages remain the ceiling no edition may raise. The opener's frame is a clamp rather than a constant, so a one-page editorial keeps its shallow first-page field and simply ends on it; where an edition does run to a second page, that page must receive a meaningful continuation rather than a stranded final line.

### Feature openers

`format.article_opener: illustrated_paper_spots_v1` is the permanent format for
new editions. It requires a first-class `opener_art` declaration on every
article. The opener is one semantic composition, in this order:

1. a large landscape illustration about the article, featuring the recurring
   boy and robot in a simple, colorful children's science-manga vignette;
2. an inline cobalt provenance kicker such as
   `FEATURE 06 / FAITHFUL SYNTHESIS`;
3. a large Source Serif display title;
4. a short signal-orange tick;
5. author and biography at left with an unlabeled source QR at right;
6. one quiet gray horizontal rule; and
7. the introductory paragraph, beginning with a cobalt drop cap.

The sheet is pure white. The illustration has a near-black square border and a
small signal-orange rectangle translated 4.1pt to the right and below. This is
not an orange border: the orange begins after the black frame's top-right and
bottom-left corners, and extends equally beyond its right and bottom edges. It
has no yellow page panel, decorative side bar, large duplicate feature number,
bottom feature label, visible `SOURCE` wording, visible URL, or second rule. The
QR resolves to the canonical URL of the article's first source. It must scan in
PDF and remains a clickable link on the web. The opener ends after the
introductory paragraph; the remaining article begins on the next print page.
Empty paper below a short intro is intentional.

The art is editorial material rather than a captured evidence figure. Its
palette follows the scene and the edition direction, with muted, grainy color
and no default yellow field. The boy and robot provide continuity, while each
scene must communicate the particular article. `FAITHFUL EDIT`,
`FAITHFUL SYNTHESIS`, `SELECTED EXTRACTS`, and `ORIGINAL SYNTHESIS` remain
provenance facts, never interchangeable decorations.

Historical editions without `format.article_opener` retain the legacy opener.
This compatibility path exists to reproduce them, not as a choice for new
editions.

### Continuation pages

Copy flows down one reading measure and then to the next page. Exact short running titles, a quiet header rule, consistent folios, and generous white space carry the identity. Quotations, bullets, headings, and code retain distinct deterministic treatments. Display headings add deliberate space before them except at a fresh frame; a heading that anchors a full-width evidence band mid-page keeps that clearance in paint — its box stays on the paragraph's space-after so pagination cannot move, and its ink is set down by the dropped space-before so it stands 17.65pt clear like every other heading (see `docs/RENDERER_MIGRATION.md`). The final prose paragraph stays together when it fits on one page, making article endings read as intentional conclusions rather than split scraps. An article's end mark stands one point below the flow it closes on every page, and never rises into it: a last page that over-runs so far that the mark would reach the folio's own line is refused, not resolved by squeezing the mark up into the descenders above it. A paragraph never ends on a single short word stranded on its own line: the last two words are bound so they wrap together whenever that final word would take less than a seventh of the measure — unless the bind would cost the penultimate line more than a third of the measure, in which case two short lines in a row is the worse defect and the runt is left standing. A third and not a fifth: the column is set unjustified, so a penultimate line a quarter short of the measure is rag and not a fault, while a last line of one short word is a runt whatever stands above it.

A reference list is the one list whose items carry their own marker inside the text (`4 — …`), so it hangs that marker: an entry's turn line is indented by the marker's own width and stands under the entry's first letter, never on the same left edge as the entry numbers.

### Source codes

A printed page cannot be followed, so every article opener carries one QR
square for the canonical URL of its **first** source id. The URL and the word
`SOURCE` are never set as visible type, and nothing is set under the square.
An article whose first source records no canonical URL prints nothing. The
editorial has no source and never prints a code.

For `illustrated_paper_spots_v1`, the byline and biography stay at the left of
the metadata row and the QR stays at the right. A single gray rule closes the
row. The same semantic anchor becomes both the scannable printed square and the
clickable web square, with no duplicate link at the end of the article.

#### Legacy source-code geometry

The following placement contract applies only to historical editions that do
not declare `format.article_opener`.

The code **opens** the title block’s own credit line: the symbol’s first dark row stands on the byline’s cap top and its first dark column on the live area’s left edge, the credit line’s own origin, where the kicker’s `FEATURE nn` and the fitted title’s first character already flush. The byline and the author note — the author’s name and who the author is — then set as **one column** an inset to its right, so the row reads square, name, biography, left to right: `[ ▪ ] | BY AUTHOR / author note`. Flush and clear are measured to the **ink**, never to the element: the four-module quiet zone lives inside the box (so the element’s own left edge is one quiet zone outside the live area), and the byline’s laid-out baseline — not a predicted one, because Pango may set a fitted title on fewer lines than the unkerned fit reserved — is the vertical anchor.

The column begins **one and a half grid gutters — 14.175pt, ink to ink** — past the symbol’s last dark module, and runs to the live area’s right edge. It began at the end mark’s 24pt, on the argument that `END / nn` is the house’s answer to how far apart two pieces of furniture sharing a band stand; on the page that was the wrong loan. 24pt separates a hairline rule from 6.8pt caps, and the opener sets a 19.6mm block of solid modules against a cap line, where the same distance reads as a hole. Rasterized at 1200 ppi, the printed ink-to-text gap went from 24.6pt to 14.7pt; 15.75pt (`_FIGURE_GAP`) was rendered beside it, measured 16.3pt and still read as two objects. The gap is stated from the **ink**, so the quiet zone is spent inside it — which is why growing the square by a quarter moved the type right by exactly the quiet zone’s own growth and printed the identical 24.6pt, and why closing the row had to be decided on its own. The byline is inset with the note rather than left on the origin, because a name and its biography are one block and a lone square beside a lone byline reads as a mark applied to the page instead of part of it.

The vertical relationship is the byline’s cap top and **not** an optical centring on the byline-plus-note block, and the alternative was built and rendered before this was kept. Centring measures the note, and the code’s own placement changes the note: narrowing the column re-rags the biography, which moves the centre, which moves the square — the reader’s two-round settle equality fails outright and the build refuses. It also fails the two openers that matter. A figure opener hides the note, so the block to centre on is a single 5.4pt cap band and a symbol centred on it rises half its own height above the byline — 19pt at the square’s current size — and crowds the fitted title; and on a prose opener the square’s position becomes a function of how many lines a biography happens to rag onto, so editing an author note moves furniture. The cap top is one number, it is the alignment the publication already uses everywhere else, and it gives the symbol a line to stand on.

A byline is a single zero-leading line and must stay one. Inset past the square it can no longer reach the code at all — it starts beyond it and grows away from it — so the refusal is re-derived to the failure that remains: a byline whose ink would pass the live area’s **right** edge is refused, not wrapped.

The line an inset note might take is free, because the adapter states every article opener’s white field itself — for an opener with a figure, deep enough for the symbol to clear the artwork; for one without, the credit block’s own lowest ink plus one measured 40.75pt breath before the standfirst, so a two-line title no longer inherits the dead paper a four-line title needed — and the code can never move a line of prose. On an opener that carries its own figure the stated field deepens just enough for the symbol’s last dark row to clear the artwork by the credit’s 12pt pad — and the figure’s 270pt image cap gives the same depth back, so a full opener stays one page and the code’s cost lands on the artwork’s size rather than on the pagination. Retiring the label gave 11.95pt of that depth back to the artwork. The finished page is then asked the promise directly: the laid-out square’s own ink, plus the pad, must stand above the laid-out figure’s head, because the square is *placed* from a measured byline while the field is *predicted* from an arithmetic one, and two numbers for one line is the shape of every defect here.

The square is a constant — one size on every opener, the way the byline has one size — and it is **55.5pt, 19.6mm**. The size is a whole multiple of the symbol most of this publication’s addresses set at: nine of the twelve codes editions 002 and 003 print come out 37 modules across the quiet zone, and 37 × 1.5 lands their cell on a round point and a half rather than on a division’s remainder. It was 45pt (15.9mm), sized to span the byline and a two-line author note; at 19.6mm the square stands a shade taller than that block and reads as the credit line’s own opening mark, and every module is about a quarter wider, which is where a phone camera’s margin lives. What varies with the URL is the module: a longer address is a denser symbol in the same square. Error correction is chosen for cell width and not for redundancy: the level taken is whichever leaves the widest module in the fixed square, and only a tie goes to the higher correction. Below a 0.35mm module the build refuses outright rather than printing a symbol a phone cannot resolve — a cap of 154 characters on this square, against 106 on the old one.

**A bigger square buys read margin, not redundancy, and cannot buy the second by accident.** The floor can only ever exclude a level whose symbol is *longer* than the winner’s, and a longer symbol is a narrower cell that would have lost the widest-cell comparison anyway. So enlarging the square reopened levels that still lose — ECC-H now sets at 0.40mm on a 45-character address where it used to refuse — and changed the level taken on none of the sixteen codes editions 001–003 print. If this publication ever wants the redundancy, it has to be asked for in the level rule.

The code is drawn in one ink — INK modules over the paper — as vector SVG, so it is exact at any print density. The finder patterns were violet and are not: on a monochrome printer a 0.18 gray is halftoned rather than printed solid, and a halftone cell the width of the module puts holes through a finder ring one module thick. The house violet moved to the label, and the label is retired; the square spends no house colour at all now, and its place on the grid is what makes it the publication’s.

Every code is then read back off the rasterized page at 300 ppi by an independent barcode reader — whichever page the square was *measured* on, at the box the adapter placed it in, never a page number assumed from where an opener ought to be — and a build whose code does not decode to its own canonical URL is refused before the PDF is written. A code that has landed on the wrong page is the failure the gate exists for as much as one that will not scan, so the page it reads is the measurement's; that the measurement really is the article's opener page is asserted against the contents map on a real build, in the test suite, and not assumed by the gate. A code that looks right and does not scan is worse than no code at all, and nothing but a decode can tell the two apart. The Spanish overlay carries the same symbol automatically, because the code is provenance and the URL is language-free — and with the label gone there is nothing on the square left to localize at all.

### Article tails

With the source code on the opener, the article’s last page closes with the **tail ornament** again: a restrained, article-specific motif in the cover grammar, declared per article as `tail_art_path` and crop-filled across the full 325pt reading measure. Its room is bounded by the reader’s own chrome — the band never comes closer than 24pt to the frame’s foot or 31pt to the end mark’s baseline — and it prints only where that leaves at least 96pt of real room, deliberately the render critic’s own void bar: wherever the open paper under an article could read as dead sheet, the declared motif claims it, and a tighter ending than that is an article honestly ending, not a slot. The band is capped at 214pt so an article that ends very high does not turn its motif into a poster, and a capped band is centred in its room rather than sunk to the foot, so no dead band strands above it. Every declaration is ledgered: the packaged manifest’s `layout.tail_arts` records, per article, whether the ornament printed, at what height, or exactly how much room it was short by, and the render critic raises each dropped ornament for review — a tail can no longer vanish silently. The band is out of flow and can never move a line or open a page; the committed raster must resolve at 300 ppi in the band it prints across, and it passes the same print-contrast preflight as a curated figure, because an ornament that ships pale is as soft a page as a diagram that does.

The edition-level `tail_art_fit` defaults to `cover`. It may be set to
`contain` when the complete horizontal sequence is editorially meaningful,
such as a multi-step comic, and no edge may be cropped as the available tail
height changes between languages.

### Authored illustration direction

Every new cover art round carries exactly three alternatives before selection:
`synthetic`, `art_directed`, and `wildcard`. They must express one editorial
reading through materially different media or visual languages, and none may
contain baked-in typography. The canonical
`editions/<edition-id>/art/cover-candidates.yaml` record pins all three square
PNGs, their generation methods, directions, and selection state. `mag collect`
scaffolds this record for every collecting edition, and the release transition
does the same for the next edition. No edition manifest key enables or disables
the contract. `uv run --locked mag illustrate <edition-id>` writes all three
cover prompts beside the interior illustration prompts. `mag validate` refuses
a missing, duplicated, undersized, non-square, or hash-drifted candidate. A
pending round leaves the existing production cover untouched until an editor
selects one.

An edition may use wordless editorial illustrations for every article opener,
and may replace geometric tail ornaments and signature-closing filler with
illustrations too. The generation step remains
**author-time only**: `mag build` never calls an image model and never changes
selected pixels. The edition declares `art_direction_path`, whose plan records
one shared visual language plus an exact brief, description, credit, role, and
committed path for every required opener, article tail, and closing plate. A
plan may carry that direction inline or name one reusable `direction_preset`;
it may never do both.
The selected preset is a first-class build input and its path and SHA-256 are
recorded beside the plan, so improving the publication default cannot silently
change an older edition's recipe. `uv run --locked mag illustrate
<edition-id>` validates that the plan and manifest name the same inventory,
checks each PNG's role-specific resolution and orientation, and writes exact
prompts plus a hash-bound inventory under
`output/<edition-id>/illustration-prompts/`.

The default for new editions is
`art-directions/playful-science-vignettes.yaml`: original late-20th-century
Japanese children's science-manga energy, especially the cheerful economy and
gadget logic associated with Doraemon-era work, without copying any franchise
character or signature object. Each image is one wordless narrative vignette,
with friendly rounded figures, simple black contours, warm paper, sparse
halftone, and relaxed spot color. Article tails favor wide scenes whose core
action survives the safe crop. Square scenes are preferred for standalone
placements when the layout supports them. Portraits are secondary, used only
for truly vertical subjects and closing plates. The preset's approved square
and wide prototype PNGs are also first-class, hash-bound inputs: prompt
packages tell the authoring tool which visual anchors to use, and build
manifests record the exact files that informed the selected art.

The prompt package is a reproducible editorial recipe, not an approval. An
editor still selects the candidates and commits the chosen PNGs. Builds bind
the plan, every article opener, every article tail, and every closing plate
into the packaged input manifest. For
`format.article_opener: illustrated_paper_spots_v1`, the plan and manifest must
contain exactly one matching `article_opener` asset per article, including its
path, alt text, and credit. Historical editions need no plan; once an edition
declares one, a missing brief, uncredited image, stale path, undersized raster,
wrong orientation, or role mismatch is a validation error.

Illustrations own their palette. They may use a broad family of print-safe
colors when the edition's direction calls for it; house violet and signal
orange are available accents, not a mandatory gamut. Continuity comes from the
declared visual language, black-ink structure, paper relationship, and page
layout. The compiler guards resolution and placement while the final render
critic judges the actual printed contrast and crop.

### Backmatter and back cover

Backmatter uses the same opener and continuation system. The selected Signal fold back cover is a full-bleed orange closing poster with giant localized LOOP CLOSED / CICLO CERRADO display type, a protected vertical identity corridor, and a white statement insert. The insert renders the configured editor-written closing statement without a redundant ownership caption; the lower slug closes with localized END/FIN and the numeric date. It never substitutes an unattributed source quotation.

The back face is compiled through `uv run --locked mag back-cover-proof <edition-id>` using the same outlined SVG -> one-page PDF -> PDF-derived PNG contract as the front. The generated PDF includes an invisible bundled-font text layer so every word remains searchable and selectable. A full build replaces both outer reader pages in one splice, and A4 imposition consumes that exact reader.

## Screen profile

`mag web` translates Quiet Standard to the screen; the print stylesheet remains
the authority for paper. The translation uses pure white behind near-black ink,
one centered 44rem reading measure, and the bundled faces served through
`@font-face` so no host font ever sets a line. The illustrated opener preserves
the same semantic order, art crop, orange offset, color signals, metadata
hierarchy, QR anchor, single rule, and drop cap as print. Its layout contracts
responsively at phone widths without horizontal overflow: the title reflows,
the art remains landscape, and the QR keeps a touch-safe clickable area and a
scannable square. Print facts keep their screen verdicts: the contents folio is
hidden because its number exists only through print's `target-counter`, and
the hyphenation opt-outs carry over unchanged because reference lists, name
rosters, and code break for no medium.

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
- Do not caption the source code; its flush on the credit line's own left origin is what makes it furniture, and a label there was tried and retired.
- Do not set a source URL as type; the reading measure cannot break one, and the code is the link.
- Preserve the one-page editorial and seven-page source-article limits; an edition may declare a tighter editorial budget than the two-page ceiling, never a looser one.
- Generate every configured language on validation and build.
- Run the render critic for every configured language; structural errors block the build.
- Inspect every numbered render-review contact sheet after layout changes and before delivery. Reopen every full-page opener crop from its exact path at original resolution; do not approve from a resized preview. For the illustrated opener, explicitly check that white remains outside the black frame at the top-right and bottom-left corners before the translated orange rectangle begins.
- Record independent approval with `mag review record`; release requires hashes matching every current language PDF.
- Do not call an edition press-ready without a named printer profile and a passing studio preflight.
