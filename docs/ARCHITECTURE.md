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
  results. `--engine weasyprint` hands the same request to the Python
  renderer instead (the rollback; see `RENDERER_MIGRATION.md`).

Model calls go through `caller.rs`, which takes `<backend>:<model>` specs.

## The Python rollback renderer (`src/magazine/`)

Kept only as the rollback and as the `mag parity` oracle until WP-6.1
deletes it. Run through `uv`. It validates `edition.yaml` (`manifest.py`,
`media_schema.py`), renders semantic HTML (`html_edition.py`), lays out A5
reader pages and booklets through WeasyPrint (`render.py`,
`weasyprint_adapter.py`, `booklet.py`), builds the web edition
(`web_edition.py`), and runs the render critic (`render_critic.py`). It is a
renderer, not an orchestrator: it receives paths, returns results, and owns no
workflow state.

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
current edition after renderer changes; `mag parity NNN` compares it against
the WeasyPrint leg. For Python rollback changes, load each edition through
`magazine.manifest.load_edition`.
