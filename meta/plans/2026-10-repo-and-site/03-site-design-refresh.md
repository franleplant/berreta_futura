# 03 Site design refresh

## Why

The site works (no overflow at 390 px, light/dark, nothing dropped) but reads
as a default template: system-ish UI text, flat blue buttons ("Download the
PDF (PDF, 33.0 MB)" repeats the format and looks like a form submit), uneven
vertical rhythm, and nothing of the print magazine's character beyond the logo.

## Current state (2026-10-04)

- Body: Source Serif 4 SmText; headings: Source Serif 4 Display Semibold;
  labels/UI: Inter; code: Geist Mono. Served as raw TTF (no woff2, no subsetting).
- One CSS file, mag/assets/site.css; pages from mag/src/site/html.rs.
- Downloads: `.download a` blocks, accent fill, 6 px radius.

## Direction (to confirm in step 1)

Keep the magazine's own system instead of inventing a new one:
- Type: Source Serif 4 for reading (it is the print face), the logo's Inter
  Display (Black/Bold) for labels, kickers and buttons so UI text and logo are
  one family; drop the generic sans look. Tighter typographic scale (e.g. 1.25
  ratio), consistent spacing tokens, 66-72ch measure.
- Colour: paper/ink/red from mag/assets/brand plus one quiet accent; the red is
  for kickers and the misregistration detail, not for large fills.
- Downloads: one "Get the issue" block on the issue page: two equal buttons
  (PDF, EPUB) with a small format glyph, label "PDF" / "EPUB" and a muted size
  line ("33 MB, A5 print layout" / "12 MB, for e-readers"), outline style with
  a solid hover, full width on phones; one compact download link in each
  article footer back to the issue.
- Issue page: cover beside title/standfirst on desktop, contents as a proper
  table of contents (number, title, author, page-like rhythm).
- Article page: print-like opener (kicker, title, byline, standfirst), figure
  captions styled like print, pull-quote and code styles aligned to the PDF.
- Fonts as woff2, subset to Latin + the symbols the content uses, preloaded
  for the two faces above the fold; `font-display: swap`.

## Steps

1. Exploration (like the logo round): an agent builds 3 static mockups of the
   issue page and an article page with real 012 content (direction A: refined
   current; B: editorial print-like; C: bolder poster-like using the logo
   language), light and dark, phone and desktop, plus 3 download-button
   treatments, in one showcase page. Owner picks.
2. Implement the pick in site.css / html.rs as tokens (CSS custom properties
   for type scale, spacing, colours), no framework, no JS beyond what exists.
3. Fonts: woff2 + subsetting at `mag site` time (deterministic, e.g. with an
   embedded subsetter or a committed pre-subset set), preload links.
4. Keep `mag site` deterministic and the nothing-dropped checks.

## Verification

- Phone (390 px) and desktop screenshots of index, issue, 3 article types,
  404, light and dark, reviewed by the owner.
- scrollWidth <= 390 on every page; Lighthouse accessibility >= 95 (contrast
  of buttons and muted text in both themes); page weight per article page not
  above today's (fonts get smaller with woff2).
