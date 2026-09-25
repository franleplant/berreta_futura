# Renderer transition record

This record supersedes the earlier one, which described a TypeScript engine
that no longer exists.

## Current state (WP-6.1, 2026-09-25)

`mag render` typesets through Typst, in Rust (`mag/src/typeset/`); it is the
only engine. It stages the edition, lays out the A5 reader, runs the render critic, and
writes the reader, booklet, preflight, web, and package outputs.

## Why the flip was allowed

The gate is WP-4.1 (`meta/verification/evidence/WP-4.1.md`): `mag parity 010`
at Tier E exited 0 twice from a clean checkout, every evaluated clause
passing on reader pages 1..56, normalized verdict sha256
`172444721bb321f4d0a55a7b6431ec425c4a283760dae518bb830d580313c3ab` on both
runs. WP-4.2's own render and ad hoc parity run are in
`meta/verification/evidence/WP-4.2.md`.

Parity was proven for edition 010 in English, with hyphenation configured
for parity. WP-4.3 measures the shipping hyphenation setting.

## The deletion (WP-6.1)

Edition 011 shipped on Typst, and on 2026-09-25 Fran retired the Python
renderer: `src/magazine/`, `--engine weasyprint`, `mag parity`, the parity
ladder, the Python oracles, `pyproject.toml`, and `uv.lock` are gone. The
tracer the render critic reads PDFs with survives as `mag/src/trace/`.
Editions 001-009 can no longer be re-rendered byte-faithfully; their
committed PDFs are the record. Committed test expectations are now
regression snapshots of the Rust output.
