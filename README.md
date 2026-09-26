# Berreta Futura

Captures articles, rewrites them, and produces a printable A5 magazine plus a
web edition. `mag`, a Rust CLI in `mag/`, runs the whole pipeline.

## Setup

```sh
git config core.hooksPath .githooks
cd mag && cargo build --release
```

Run `mag` from the repository root. The pre-commit hook runs `cargo fmt`,
`cargo clippy -D warnings`, `ruff` on `tools/`, and the no-comments check.

## Pipeline

Every step prints the next command when it finishes.

```sh
mag capture <url> [--edition NNN]          # source into library/, row into plan.yaml
mag produce editions/NNN/plan.yaml         # writes the run, scaffolds edition.yaml
# edit editions/NNN/edition.yaml
mag art NNN                                # art candidates; pick in art/showcase.html
mag source-codes NNN                       # QR codes for the openers
mag render NNN                             # reader.pdf, booklets, web edition, package
mag translate <run dir>                    # Spanish edition
```

`mag render` typesets through Typst in Rust (`mag/src/typeset/`).

`mag print <url>` is a standalone side tool that turns one blog post into a
printable PDF; it is not an edition step.

## Layout

- `library/sources/<id>/`: captured sources (`record.yaml`, verbatim
  `article.md`, `media/`).
- `editions/NNN/`: `plan.yaml`, `edition.yaml`, runs, art, source codes.
  Render output (`render-*`) is not tracked.
- `prompts/`: writer and translator prompts.
- `mag/`: the CLI; `mag/assets/typeset/` holds the Typst template.
- `docs/`: editorial policy, architecture, renderer migration record.

## Verification

```sh
cd mag && cargo test
```

Contributor rules live in `CLAUDE.md`.
