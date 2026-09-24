# Renderer transition record

This record supersedes the earlier one, which described a TypeScript engine
that no longer exists.

## Current state (WP-4.2, 2026-09-24)

`mag render` typesets through Typst, in Rust (`mag/src/typeset/`). The
`magazine.toml` key `[render] engine = "typst"` selects it. The typst leg
stages the edition, lays out the A5 reader, runs the render critic, and
writes the reader, booklet, preflight, web, and package outputs.

WeasyPrint (`src/magazine/`, Python, run through `uv`) is the rollback. It
stays selectable per run with `mag render NNN --engine weasyprint`, or for
every run by setting `engine = "weasyprint"`. It also remains the oracle
that `mag parity` compares the typst leg against. Rolling back is a config
change only; no code change is needed.

## Why the flip was allowed

The gate is WP-4.1 (`meta/verification/evidence/WP-4.1.md`): `mag parity 010`
at Tier E exited 0 twice from a clean checkout, every evaluated clause
passing on reader pages 1..56, normalized verdict sha256
`172444721bb321f4d0a55a7b6431ec425c4a283760dae518bb830d580313c3ab` on both
runs. WP-4.2's own render and ad hoc parity run are in
`meta/verification/evidence/WP-4.2.md`.

Parity was proven for edition 010 in English, with hyphenation configured
for parity. WP-4.3 measures the shipping hyphenation setting.

## What comes next

WP-6.1 deletes the Python renderer once one real edition has shipped on
the Typst engine. Deleting it removes the rollback and the only way to
re-render editions 001-009 byte-faithfully, so that is Fran's call.
