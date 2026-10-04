# Architecture

The magazine is produced by two programs and a pile of files.

## The Rust CLI (`mag/`)

`mag` drives the workflow from the repo root:

- `mag plan <edition>` reads every `library/sources/*/article.md`, proposes an
  edition plan (7 sources, paired where useful, one content mode each), and
  writes `editions/<edition>/plan.yaml`.
- `mag produce` runs the writer prompts over the planned sources and writes
  the manuscripts and frontmatter into a timestamped run directory under the
  edition.
- `mag art` proposes the edition's full art-brief slate (cover, one opener
  and one tail per article, closing plates; see `prompts/illustrations.md`)
  and renders candidate rounds; `--dry-run` writes the briefs and an
  executable `generate.sh` without spending image credits.
- `mag translate` produces the Spanish edition from the finished English one.
- `mag render` stages everything an edition references (manuscripts, art,
  figure images, source records), typesets it through Typst
  (`mag/src/typeset/`), runs the render critic, and writes the reader,
  booklet, web, and package outputs, then reports page counts and critic
  results.

Model calls go through `caller.rs`, which takes `<backend>:<model>` specs.

## The files

- `library/sources/<id>/` is a captured source: `record.yaml` (title, author,
  url, dates, tags, synopsis), `article.md` (verbatim text), `media/` (images).
- `library/release-state.yaml` says which sources are queued or released per
  edition; `sources.md` is generated from the records.
- `editions/<edition>/` holds `plan.yaml`, `edition.yaml`, manuscripts, art,
  translations, and timestamped `run-*`/`render-*` output directories.
- `prompts/` holds the hand-tested prompts; `templates/` the edition template;
  `schemas/` the record schema; `profiles/` printer profiles.

## Verification

`cargo test` in `mag/` covers the CLI and the Typst renderer. Render the
current edition after renderer changes and read the PDF; the render critic's
report sits beside it.

## Dependency pins

`typst`, `typst-layout`, `typst-pdf`, and `typst-syntax` are pinned with `=`
because a patch release can move glyph positions and line breaks, which
changes the printed pages; a bump is a deliberate step followed by rendering
an edition and comparing pages. They also release in lockstep, so they move
together. `resvg`, `usvg`, and `tiny-skia` are pinned for pixel
reproducibility of the cover, logo, and social-card rasters, and their
versions must equal the ones `typst-library` (usvg) and `krilla-svg` (resvg,
usvg, tiny-skia) already resolve, or Cargo would build duplicate copies and
`tiny_skia::Pixmap` would stop matching across crates. `typst-library` is not
listed; `typst` re-exports what is needed.
