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
uv run --locked mag media-index
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
library/sources/<source-id>/media/<sha>.json deterministic generated media inventory
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

Every capture also produces a bundle-keyed media inventory, including explicit
zero-image results. Raster candidates record their hash, MIME type, dimensions,
aspect ratio, color mode, ICC-profile presence, alpha, and animation state.
Duplicate hashes and local HTML or captured-manifest references are audited;
missing local images or stale inventories fail validation. `mag media-index`
rebuilds these derived inventories for existing immutable captures without
changing anything under `raw/`.

Automatic media decisions live in a bundle-keyed curation audit and are pinned
in `record.yaml`; exhaustive inventories remain generated output. The curator
extracts substantive inline SVG diagrams into generated PNG derivatives without
changing immutable raw evidence, rejects screenshots, decorative vectors,
low-resolution assets, and context-free images, then selects only the strongest
zero to three candidates. Every decision records its score, rationale, and
rejection reasons. A build fails if any capture has not been curated.

## Edition manifests

See `templates/edition.yaml`. An article points at both a manuscript and a
fidelity ledger, and supplies a concise `author_note` that is rendered below
the byline. Each language overlay provides its own localized note. Paths are
repository-relative and cannot escape the project. The compiler validates
required fields, source references, duplicate IDs, and file existence before
layout.

An article may select at most three curated figures. Each selection records why
it is important, useful, beautiful, or cool; resolves to a hash-verified source
asset; and uses either a full-width `evidence_band` or a single-column
`column_plate`. Placement is semantic: `__opener__` or an exact `##` heading,
never a fragile page number. Spanish preserves figure identity and layout while
providing a hash-pinned localized caption, alt text, and heading anchor.

The fidelity ledger records every substantive source paragraph as one of:

- `retained`
- `boilerplate_removed`
- `substantive_cut`
- `modified`
- `editorial_addition`

The renderer enforces a hard seven-page budget per article. A long source uses
`faithful_synthesis`, which maps the complete source to a materially shorter
manuscript while preserving its argument, evidence, qualifications, conclusion,
and grammatical point of view. The byline and mode label carry attribution;
synthesized prose remains in the source author's voice instead of narrating what
the author “argues” or “explains.” Short pieces remain `faithful_edit`.

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
render-critic.json
render-review/reader-contact-sheet-01.png
render-review/booklet-contact-sheet-01.png
edition-manifest.json
SHA256SUMS
```

`preflight.json` validates page geometry, signature length, booklet sheet size,
cover and figure resolution, figure geometry, rights clearance, and studio
blockers. Curated figures require captions, credits, non-colliding placement,
and at least 300 effective PPI. The renderer embeds
the standard PDF fonts by default. A professional print profile is included as
a specification, but PDF/X conversion, trim bleed, and the printer ICC output
intent remain explicit studio preflight steps.

Every language also passes through the render critic before packaging. It
rasterizes every reader page with Poppler, blocks blank pages, orphan display
punctuation, inefficient contents pagination, placeholder cover copy, invalid
signature length, and breached editorial or article page caps. It records
per-page ink geometry in `render-critic.json` and produces numbered contact
sheets plus 144-DPI individual page and booklet-side rasters for the required
final visual review. The critic also verifies each imposed left/right page pair
against the declared saddle-stitch, short-edge-duplex plan. Sparse pages are
review prompts, not automatic failures, because deliberate openers and closing
plates may use whitespace. The report and review images are included in
`SHA256SUMS`.

Independent visual judgment is recorded by the compiler rather than inferred
from agent instructions. After inspecting every generated language package:

```sh
uv run --locked mag review status <edition-id>
uv run --locked mag review record <edition-id> \
  --reviewer "Independent critic" \
  --result approved \
  --notes "All reader pages and booklet sides inspected."
uv run --locked mag release <edition-id>
```

`mag review record` writes the canonical decision to
`editions/<edition-id>/reviews/render.yaml`, binding it to the SHA-256 hashes of
every configured reader and booklet, then rebuilds the packages so their
reports expose the decision. Any subsequent PDF change makes the review
`stale`. A `changes_required` decision must include at least one `--finding`.
`mag release` refuses missing, stale, or changes-required review state.

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
