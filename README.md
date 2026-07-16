# Magazine Compiler

Magazine Compiler turns captured internet sources into a private, print-ready
anthology. It is deliberately a **faithful-edit** system, not a summarizer: source
language remains intact unless a paragraph-level edit record says otherwise.
Articles are capped at seven rendered A5 pages. Over-budget sources become
explicitly credited, source-mapped faithful syntheses rather than silently
truncated reprints.
The opening editorial requires a title and is capped at two rendered A5 pages,
including its title and byline.

The publication compiled by this repository is **BERRETA FUTURA**. Its name is
configured once under `[publication]` in `magazine.toml`; edition manifests own
issue titles and cover copy, but do not duplicate or override the masthead.
Every configured language is built together. English is the source edition and
keeps its existing package paths; the Spanish package is emitted beneath `es/`.

The external interface is intentionally small:

```python
from pathlib import Path
from magazine import Magazine

mag = Magazine(Path.cwd())
record = mag.capture(
    "https://example.com/article",
    snapshot=Path("/tmp/article-browser-export"),
    capture_method="authenticated_browser",
    title="An article",
)
mag.write_sources()
result = mag.build("issue-001")
```

The equivalent command line is:

```sh
uv run --locked mag capture https://example.com/article \
  --snapshot /tmp/article-browser-export \
  --capture-method authenticated_browser \
  --title "An article"
uv run --locked mag sources
uv run --locked mag validate issue-001
uv run --locked mag build issue-001
```

`capture` requires a raw file or directory supplied by the caller. It copies the
bundle into content-addressed, source-local storage before it writes the source
record or queues the source. The compiler never treats a live URL as the durable
copy. Web or authenticated-browser acquisition remains an explicit adapter, so
cookies, credentials, authorization headers, and browser profiles stay outside
the repository.

## Python toolchain

UV owns the complete Python lifecycle for this repository. After cloning, run:

```sh
uv sync --locked
```

Run every project command through `uv run --locked`. Add, remove, and update
dependencies with `uv add`, `uv remove`, and `uv lock`; commit both
`pyproject.toml` and `uv.lock`. Do not use `pip`, invoke `python -m venv`,
activate an environment, or create ad-hoc dependency directories. UV's internal
project environment is an implementation detail and is never managed by hand.

## Repository model

```text
library/sources/<source-id>/record.yaml    structured source record
library/sources/<source-id>/raw/<sha>/     immutable committed raw capture
library/sources/<source-id>/extracted.md  local, faithful extraction
library/release-state.yaml                open-edition and released-edition assignments
editions/<edition-id>/edition.yaml        edition manifest
editions/<edition-id>/editorial.md        original opening editorial
editions/<edition-id>/articles/*.md       edited source manuscripts
editions/<edition-id>/fidelity/*.yaml     paragraph-level edit ledger
editions/<edition-id>/translations/es/    hash-pinned Spanish edition overlay and manuscripts
output/<edition-id>/                      generated release package
output/<edition-id>/es/                   Spanish reader, booklet, preflight, and package metadata
```

`sources.md` is always generated from the source records. Never edit it by hand.

## Language editions

`publication.language` selects the source edition and `publication.languages`
declares every required output. A build fails if any configured translation is
missing, stale, or structurally incomplete. The source English `reader.pdf` and
`home/booklet-a4.pdf` remain at the package root. Spanish generates the same
permutations under `output/<edition-id>/es/`.

Each translation overlay records the exact SHA-256 of its English editorial,
articles, and backmatter. It must preserve the ordered Markdown block structure
of the English manuscript, including headings, paragraphs, lists, quotations,
and code. Changing an English input therefore makes the translation stale and
blocks validation until it is reviewed and updated.

The Spanish house register is educated castellano with a restrained Argentine
inclination where it reads naturally, without slang or lunfardo. Where no clear
Argentine preference applies, use Spain Spanish; do not fall back to generic
Latin American, Mexican, Caribbean, or other regional variants.

## The open edition

The repository has exactly one open edition. Every newly captured source is
assigned to it automatically; a batch of submitted links is never treated as an
edition boundary. `mag capture` queues its source immediately, while `mag
sources` and `mag queue` reconcile manually created records into the same open
edition.

`library/release-state.yaml` is the authoritative ledger. A source appears
either in the open edition or in one released edition, never both. Only an
explicit release closes the collection and permits the next edition to open.

Release the complete open edition with:

```sh
uv run --locked mag release <edition-id>
```

Release is deliberately all-or-nothing. The command first reconciles every
source record into the open queue and verifies that every queued source appears
in a rendered article's `source_ids` provenance. A bare entry under the
manifest's top-level `sources` inventory is not enough. It then validates the fidelity
ledgers, and successfully builds the reader and home-print packages. Only then
does it mark the edition manifest `released`, move its sources into
`released_editions`, and open an empty incremented edition such as
`002-unreleased`. Manifest and ledger updates use atomic replacements with
rollback on failure. Rights and distribution fields are preserved unchanged;
release does not turn a private reprint into a publicly cleared one.

Use `--next-edition-id 002-a-working-title` only when the next collection
already has an intentional identifier. New captures after release are queued
there; sources assigned to the released edition are never requeued.

## Source records

The capture command creates a record like:

```yaml
id: an-article-a1b2c3d4
url: https://example.com/article
canonical_url: https://example.com/article
title: An article
author: Example Author
captured_at: 2026-07-15T12:00:00Z
content_mode: faithful_edit
tags: []
primary_material: []
raw_captures:
  - id: 0f4c...c93a
    path: raw/0f4c...c93a/manifest.json
    method: authenticated_browser
    artifact_count: 3
rights:
  status: unknown
  intended_use: private_reference
  public_reprint_allowed: false
```

Tracking parameters and URL fragments are removed during canonicalization. A
stable suffix derived from the canonical URL prevents slug collisions. Every
raw manifest records each artifact's repository-relative path, byte count, and
SHA-256. The bundle directory name hashes that ordered inventory. Validation,
build, and release fail if an artifact is missing or has changed.

## Edition manifests

See `templates/edition.yaml`. An article points at both a manuscript and a
fidelity ledger, and supplies a concise `author_note` that is rendered below
the byline. Each language overlay provides its own localized note. Paths are
repository-relative and cannot escape the project. The compiler validates
required fields, source references, duplicate IDs, and file existence before
layout.

The fidelity ledger records every substantive source paragraph as one of:

- `retained`
- `boilerplate_removed`
- `substantive_cut`
- `modified`
- `editorial_addition`

The renderer enforces a hard seven-page budget per article. A long source uses
`faithful_synthesis`, which maps the complete source to a materially shorter
manuscript while preserving its argument, evidence, qualifications, and
conclusion. Short pieces remain `faithful_edit`.

`modified` entries preserve both source and edited text. Editorial additions
must be visually labelled in the manuscript. The generated fidelity report
provides word counts and retention percentages; it is evidence for review, not
an automatic claim that an edit is acceptable.

## PDF outputs

The A5 reader PDF is produced deterministically with ReportLab. The home booklet
is imposed onto landscape A4 with `pypdf` and padded to a multiple of four pages.
The package contains:

```text
reader.pdf
home/booklet-a4.pdf
home/printing-instructions.md
fidelity.md
preflight.json
edition-manifest.json
SHA256SUMS
```

`preflight.json` validates page geometry, signature length, booklet sheet size,
cover resolution, rights clearance, and studio blockers. The renderer embeds
the standard PDF fonts by default. A professional print profile is included as
a specification, but PDF/X conversion, trim bleed, and the printer ICC output
intent remain explicit studio preflight steps.

## First edition

Issue 001 lives at `editions/001-the-work-left-to-us/`. It captures an X post as
the original discovery lead and combines four substantive works by Arvind
Narayanan, Unmesh Joshi, Satya Nadella, and Demis Hassabis. It is a private
faithful-edit edition with paragraph-level fidelity ledgers, an original opening
editorial, and a generated A5/A4 print package. Public faithful republication
remains blocked while source rights are unknown.

```sh
uv run --locked mag sources
uv run --locked mag validate 001-the-work-left-to-us
uv run --locked mag build 001-the-work-left-to-us
```

## Development

```sh
uv run --locked pytest
uv run --locked mag --help
```

The metadata, validation, fidelity, catalog, and packaging modules use only the
standard library plus PyYAML. ReportLab and pypdf are imported only by their PDF
paths, making non-rendering operations easy to test in constrained environments.
