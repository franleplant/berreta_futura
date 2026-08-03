# BERRETA FUTURA design system

This document defines visual policy. The TypeScript/XState engine owns all
lifecycle work. Art creation, selection, measurement, rendering, visual review,
and release are durable offers and decisions through `RunEngine`, normally
driven from the CLI with `npm run engine -- ...`.

The retained Python renderer, old configuration fields, historical layout
measurements, and prototype generators are not a contributor workflow. They may
remain behind versioned TypeScript adapter interfaces while the seam exists, but
they do not decide readiness, layout approval, or release.

## Design position

BERRETA FUTURA is a small-format reading magazine, not a set of web pages
printed to PDF. Its production interior is Quiet Standard: book typography, one
calm reading measure, useful images, and intentional white space. The retained
A/B study in `prototypes/interior-reading-prototype/` is historical design
context, not a runtime selector.

The system combines literary reading typography with the visual confidence of
an art and graphic-design journal. Hierarchy is emphatic, provenance remains
unmistakable, and long-form pages stay calm.

## Cover art

Cover art is a compact abstract proposition, not a miniature narrative scene.
It uses a few exact shapes, one dominant silhouette, and substantial negative
space. It avoids literal robots, people, rooms, machinery, circuit boards, and
generic AI imagery.

- Use three to seven hard-edged geometric components.
- Use warm paper, near-black, ultraviolet, and a small signal-orange accent.
- Keep signal orange below five percent of artwork area.
- Never bake a masthead, cover line, title, issue number, logo, caption, or
  watermark into art. Layout owns all typography.
- Image generation and human art selection are distinct offers. Rendering may
  consume only registered selected-art artifacts and must never create images.

## Typography and page structure

| Role | Typeface | Use |
| --- | --- | --- |
| Display | Source Serif 4 Display Semibold | Titles and section headings |
| Reading | Source Serif 4 Small Text Regular | Body and standfirsts |
| Emphasis | Source Serif 4 Small Text Italic/Bold | Quotations and emphasis |
| Navigation | Inter | Running matter, credits, labels, and folios |
| Code | Courier | Exact source code in a full-width frame |

Use book-scale body text, a single-column reading measure, clear title and
byline hierarchy, quiet running matter, and reliable folios. Fenced code is
full width and must be a contiguous exact run from a committed extraction.
Actual type fit, opener fit, and page counts come only from `measureArticle` or
`measureEdition`, never from character limits or copied wrapping calculations.

- Trim is A5 portrait and booklet imposition is A4 landscape.
- The inside front cover and inside back cover, including their imposed sheet
  sides, are blank.
- Source articles are at most seven A5 reader pages.
- The opening editorial visibly renders its label, title, and byline, and fits
  on one A5 reader page in every configured language.
- English is the source edition. Spanish preserves Markdown structure and uses
  educated castellano with restrained Argentine preferences.

## Reader elements

Feature openers make source attribution clear through a content-mode label,
title, author information, and, when applicable, a source link or scannable
source reference. Original editorial material must be visibly labeled as
magazine-authored. Captions, figures, and furniture cannot conceal whether text
is source-authored or magazine-authored.

Figures remain at their semantic anchor. They must be readable at final print
size and use registered artifacts with immutable provenance. Do not repeat cover
art as an interior watermark, crop, or palette source.

## Review and release

The renderer produces exact reader, web, booklet, package, inspection, and
preflight artifacts for every configured language. Independent visual review
uses those exact artifact IDs at original resolution. A new render is a new
review target and cannot inherit an earlier approval.

No edition is press-ready without a named printer profile, passing per-language
preflight artifacts, and explicit studio readiness. Release approval names the
exact approved render and source artifacts and is atomically recorded by the
engine.

## Historical material

The detailed legacy geometry, renderer-switch notes, and prototype records are
kept in Git history and retained fixture directories. They may inform a scoped
adapter-maintenance task, but never override the current engine contracts or
this policy.
