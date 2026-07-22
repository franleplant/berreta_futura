# Canto vivo cover direction

`design.toml` is the single authored geometry and color contract for the cover.
The compiler combines it with localized edition copy, the bundled Inter fonts,
and the edition artwork to materialize a self-contained SVG. Every visible
letter is converted to SVG paths; the SVG has no system-font or network
dependency.

Run the fast design loop with:

```sh
uv run --locked mag cover-proof 002-unreleased
uv run --locked mag cover-proof 002-unreleased --all-languages
```

Each proof directory contains the materialized `cover.svg`, the exact one-page
`cover.pdf` used in production, `cover.png` rasterized from that PDF, visual
comparison images, and `proof.json`. A full build splices that same cover PDF
into reader page 1; ReportLab owns interiors only.

The references freeze the previously approved English and Spanish covers for
migration comparison. A deliberate redesign may differ from them, but the
reference must never be updated until an independent visual review approves the
new result.
