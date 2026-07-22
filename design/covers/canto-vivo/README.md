# Canto vivo cover direction

`design.toml` is the single authored geometry and color contract for both outer
covers. The compiler combines it with localized edition copy, bundled Inter and
Source Serif fonts, and the edition artwork to materialize self-contained SVGs.
Every visible letter is converted to SVG paths; neither face has a system-font
or network dependency.

Run the fast design loop with:

```sh
uv run --locked mag cover-proof 002-unreleased
uv run --locked mag cover-proof 002-unreleased --all-languages
uv run --locked mag back-cover-proof 002-unreleased
uv run --locked mag back-cover-proof 002-unreleased --all-languages
```

Each proof directory contains the materialized `cover.svg`, the exact one-page
`cover.pdf` used in production, `cover.png` rasterized from that PDF, visual
comparison images, and `proof.json`. A full build splices the front and back
PDFs into the reader's outer pages in one operation; ReportLab owns interiors
and blank cover placeholders only. Home-booklet imposition consumes that final
reader, so it cannot drift from either proof.

The front and back reference directories freeze the previously approved English
and Spanish faces for migration comparison. A deliberate redesign may differ,
but a reference must never be updated until an independent visual review
approves the new result.
