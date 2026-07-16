# COMMONPLACE design system

COMMONPLACE is a small-format reading magazine, not a stack of web pages printed to PDF. Its visual system should make long-form text calm to read, make provenance immediately legible, and remain economical on an ordinary home printer.

## Design position

The system borrows principles, not layouts, from two editorial traditions:

- Monocle's disciplined reduction: fewer type styles, a more open grid, and the confidence to show less.
- Veronica Ditting's work for *The Gentlewoman*: editorially driven form, pared-back typography, and exact cropping, sizing, and alignment.

The resulting identity is original to COMMONPLACE: literary serif display type, robust small-text typography, compact sans-serif navigation, oxblood signals, and generous unprinted space.

## Typography

| Role | Typeface | Default use |
| --- | --- | --- |
| Display | Source Serif 4 Display Semibold | Covers, article titles, section titles |
| Reading | Source Serif 4 Small Text Regular | Body and standfirsts |
| Emphasis | Source Serif 4 Small Text Italic/Bold | Quotations and emphasis |
| Navigation | Inter Regular/Medium/Semibold/Bold | Running heads, credits, labels, folios |
| Code | Courier | Source code only |

Source Serif's optical cuts let the display and reading voices feel related without forcing one drawing to do both jobs. Inter is deliberately quieter: it carries facts and navigation without competing with the prose.

The font files and their SIL Open Font License texts are committed under `src/magazine/assets/fonts`. Do not replace them with system-font lookups; deterministic builds must use the bundled versions.

## Color

| Token | RGB intent | Use |
| --- | --- | --- |
| Ink | blue-black | Primary text and large fields |
| Oxblood | dark red | Section labels, bullets, rules, signals |
| Slate | neutral blue-gray | Secondary metadata and folios |
| Sand | warm gray | Hairlines and quiet separation |
| Pale sand | warm tint | Code panels |
| Paper | soft cream | Covers and reversed text |

Interior pages remain white except for small signals. This preserves contrast, avoids muddy home-printer backgrounds, and limits ink coverage.

## A5 page architecture

- Trim: A5 portrait, imposed two-up on A4 landscape for home printing.
- Live area: 41 pt left, 37 pt right, 52 pt top, 45 pt bottom.
- Body: Source Serif 4 Small Text at 9.55/12.55 pt.
- Standfirst: 11.6/15.2 pt.
- Article display title: 27.5 pt, reduced only when needed to stay within five lines.
- Running matter appears only on continuation pages. Opener pages reserve the full top field for the title.
- Folios sit at the outer bottom corner: left on versos, right on rectos.
- Headlines keep at least two body lines with them when pagination allows.

## Page types

### Front cover

The cover uses the issue artwork as the dominant gesture. A translucent paper field carries the masthead, display title, deck, and a small oxblood mark. Issue metadata stays at the foot.

### Contents

A dark header field establishes the issue. Entries use a repeated label-title-author-folio hierarchy, with no dot leaders or decorative furniture.

### Editorial and feature openers

Each opener has four stable layers:

1. section or feature label;
2. display title;
3. author and editorial treatment;
4. a fine sand rule leading into the text.

`FAITHFUL EDIT`, `FAITHFUL SYNTHESIS`, and `AN ORIGINAL ARGUMENT` are publication facts, not decoration. They must remain visible.

### Continuation pages

The running head identifies the magazine, issue, and current article. It is separated from the text by a sand hairline and cannot appear on an opener.

### Back cover

The back cover is typographic: one issue-defining sentence, a large quiet field, and private-edition metadata at the foot.

## Guardrails

- Do not add more typefaces without an explicit redesign decision.
- Do not introduce full-page interior tints solely for atmosphere.
- Do not shrink body type to solve article-length problems; edit or synthesize the article.
- Do not let a running head cross an opener title.
- Preserve the hard limits of two editorial pages and seven pages per source article.
- Render and inspect every reader page and every imposed booklet side after layout changes.

