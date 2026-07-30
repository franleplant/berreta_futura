# Magazine Compiler

Magazine Compiler turns captured internet sources into a private, print-ready
anthology. It is deliberately a **faithful-edit** system, not a summarizer: source
language remains intact unless a paragraph-level edit record says otherwise.
Articles are capped at seven rendered A5 pages. Over-budget sources become
explicitly credited, source-mapped faithful syntheses rather than silently
truncated reprints.
The opening editorial requires a title and is capped at a single rendered A5
page, including its label, title, and byline.

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
  --title "An article" \
  --author "A. Writer" \
  --author-note "A. Writer is chief architect at Example Company." \
  --author-evidence https://example.com/author /tmp/author-profile-browser-export
uv run --locked mag sources
uv run --locked mag media-index
uv run --locked mag validate issue-001
uv run --locked mag fit issue-001
uv run --locked mag cover-proof issue-001 --all-languages
uv run --locked mag build issue-001
```

## Fast edition workflow

`mag status` is the read-only control plane. It reports every checkpoint, the
first blocker, whether the next action is deterministic, authorial, or a human
review, and the exact recovery command. `mag run` performs only the named
deterministic work, then stops. It never writes prose, generates images,
selects artwork, records a review, or releases an edition.

```sh
uv run --locked mag status 004-unreleased
uv run --locked mag status 004-unreleased --json
uv run --locked mag run 004-unreleased --json
```

After capture and extraction, a versioned article brief is the first safe unit
of editorial assembly:

```yaml
schema_version: 1
edition_id: 004-unreleased
id: systems-that-hold
title: Systems That Hold
short_title: Systems
display_emphasis: Hold
opener_variant: edge_medallion
content_mode: faithful_edit
minimum_reader_pages: 1
source_ids:
- source-one
- source-two
```

```sh
uv run --locked mag article stage article-brief.yaml --dry-run
uv run --locked mag article stage article-brief.yaml
```

The real stage is one integration transaction. It creates the source-linked
manuscript slot and fidelity skeleton, updates the edition manifest, and
immediately reconciles every configured non-English overlay so its placeholder
and advisory backlog is visible. It writes no article prose and no
translation. If any overlay staging step fails, the edition is restored to its
pre-command bytes for every file this invocation changed, provided its current
bytes still match the staged result. Unrelated concurrent files are ignored;
concurrently edited touched files are preserved and reported while every other
safe write is rolled back. Capture remains URL-by-URL because durable snapshot
and author-evidence acquisition are explicit adapters; the brief begins only
after those source bundles exist.

Creative work has separate studio commands:

```sh
# Immutable cover rounds
uv run --locked mag cover-art status 004-unreleased
uv run --locked mag cover-art next-round 004-unreleased \
  --editorial-reading "A precise statement of the issue's visual argument."
uv run --locked mag cover-art prompts 004-unreleased 2
uv run --locked mag cover-art register 004-unreleased 2 \
  --image synthetic=/tmp/synthetic.png \
  --image art_directed=/tmp/art-directed.png \
  --image wildcard=/tmp/wildcard.png
uv run --locked mag cover-art proof 004-unreleased
uv run --locked mag cover-art select 004-unreleased 2 wildcard

# Explicit interior illustration inventory
uv run --locked mag interior-art status 004-unreleased
uv run --locked mag interior-art scaffold illustration-brief.yaml
uv run --locked mag interior-art prompts 004-unreleased
uv run --locked mag interior-art register 004-unreleased tail-systems /tmp/tail.png
uv run --locked mag interior-art review-sheet 004-unreleased
```

Cover rounds are append-only. Registration computes hashes from validated PNG
bytes, `proof` renders every requested round, branch, and language through the
production cover compiler, and writes one full-cover comparison sheet.
Selection is a separate human decision. Interior art likewise requires an
explicit versioned brief, validates each registered asset, and produces a
review sheet without generating an image.

The older focused commands remain supported. `mag illustrate` still emits its
combined legacy prompt package, while `mag cover-proof`, `mag translate`,
`mag fit`, `mag measure`, `mag validate`, `mag build`, and `mag release` keep
their existing behavior. New automation should prefer `status`, conservative
`run`, and the two studio surfaces.

`cover-proof` is the fast design loop. It compiles only the cover and writes a
self-contained SVG, the exact one-page PDF later used by the full build, a
PDF-derived PNG, and visual comparison evidence. Its warm cached path avoids
article pagination and booklet imposition.

`fit` is the fast measurement loop, the same idea for page budgets. The
seven-page article cap and the declared editorial cap used to be enforceable
only deep inside a full build, so an author finished a manuscript, its ledger,
its translation, and every hash pin before learning the piece did not fit.
`mag fit` paginates the reader with the adapter's own front half — the same
HTML compilation, stylesheet, and measure-then-settle passes a build runs —
then stops before paint: no PDF, no rasters, no package. It prints a verdict
for every configured language in about four seconds instead of a forty-second
build and exits nonzero on any budget breach. `mag measure` reports the full
measurement as JSON for agents and scripts — the editorial span, every
article's span against its cap, the last page's body-line count, end-mark and
tail measurements, and a per-paragraph rag table — so judging a layout
question no longer requires a throwaway script into the renderer's privates.
Both take `--language` to narrow to one configured language; `mag measure
--json PATH` writes the dump to a file instead of stdout.

`capture` requires a raw file or directory supplied by the caller. It copies the
bundle into content-addressed, source-local storage before it writes the source
record or queues the source. New CLI captures also require an author identity.
For a person or named group, `--author-note` contains edition-ready identity or
CV context and at least one `--author-evidence URL SNAPSHOT` archives the
official biography, employer page, or profile that supports it. Repeat
`--author-evidence` when several primary profiles support a collective byline.
Use `--institutional-author` instead when the organization byline is
self-explanatory and should carry no biography.

Author evidence is stored as a purpose-tagged immutable raw bundle. The
schema-v2 source record pins the biography to its evidence URL and bundle ID;
edition validation then requires the English byline and `author_note` to match
the captured identity exactly. Article synopses remain separate metadata and
cannot become biographies by flowing through the assembly path.

The compiler never treats a live URL as the durable copy. Web or
authenticated-browser acquisition remains an explicit adapter, so cookies,
credentials, authorization headers, and browser profiles stay outside the
repository.

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
library/sources/<source-id>/extracted.md  faithful extraction of the source body from one raw bundle
library/release-state.yaml                open-edition and released-edition assignments
editions/<edition-id>/edition.yaml        edition manifest
editions/<edition-id>/editorial.md        original opening editorial
editions/<edition-id>/articles/*.md       edited source manuscripts
editions/<edition-id>/fidelity/*.yaml     paragraph-level edit ledger
editions/<edition-id>/reviews/*.yaml      hash-bound render and evidence review records
editions/<edition-id>/translations/es/    hash-pinned Spanish edition overlay and manuscripts
output/<edition-id>/                      generated release package
output/<edition-id>/es/                   Spanish reader, booklet, preflight, and package metadata
output/<edition-id>/cover-proof/<lang>/   fast cover SVG/PDF/PNG and comparison evidence
design/covers/canto-vivo/design.toml      canonical cover geometry and ink contract
```

`sources.md` is always generated from the source records. Never edit it by hand.

New source records carry:

```yaml
schema_version: 2
author: A. Writer
author_profile:
  note: A. Writer is chief architect at Example Company.
  evidence:
  - url: https://example.com/author
    capture_id: <sha256 of the archived profile bundle>
```

The `note` is the canonical English author biography used by edition manifests.
It must identify the author through a role, notable company, founder or creator
status, career history, first-hand experience, or a publishing identity. It
must never describe, explain, or summarize the captured article.

`extracted.md` is the verifiable source side of the fidelity chain. Its YAML
frontmatter names the source id, the committed raw bundle it was transcribed
from, and the extraction method; its body is the source's substantive text,
reproduced verbatim (interface chrome and navigation may be omitted). A
fidelity ledger's `source_body_sha256` is the SHA-256 of the UTF-8 bytes of
that body — everything after the frontmatter's closing `---` line. Single-source
ledgers declare one hex digest; multi-source ledgers declare a mapping keyed by
source id. Whenever a source has an extraction and a ledger pins it, validation
requires the hashes to match. Every source of the open (unreleased) edition
must have an extraction and a matching pin; released editions predate committed
extractions, so their recorded pins are kept but skipped.

Every such pin — a ledger's extraction-body hashes, a translation overlay's
base copy and per-file source hashes, a localized figure's caption and credit
pins — is a pure function of files already in the repository, so it is
recomputed by command rather than by hand: `mag pin <edition-id>` refreshes
every derivable pin in the edition's authored files and reports each digest it
moved. The rewrite is a targeted textual substitution — only the digest
changes, the author's comments, key order, and wrapping survive — and the
whole batch is verified by re-parsing before anything reaches disk. It never
invents a missing pin key, and it refuses anything under `reviews/` outright:
review records are written only by `mag review record`. Repinning is always
this explicit command; `mag validate` reports staleness but never repins,
though every staleness error now states both the pinned and the expected
digest, so the fix is a decision rather than an investigation.

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

`mag translate <edition-id> <language>` does the clerical half of that update,
and refuses, loudly, to do the creative half. A missing overlay is scaffolded
whole: structure mirrored from the English edition, every derivable pin
computed with the canonical hashers validation uses, and every localized prose
field filled with its English text as a placeholder — each one named in the
report as untranslated backlog, so nothing English can ship as Spanish
silently. An existing overlay is reconciled, not regenerated: new English
articles, figures, and plates gain placeholder rows with correct pins; missing
pin keys are repaired in place; rows whose English counterpart vanished are
dropped with their localized prose quoted in the report, because deleting a
translation someone wrote is a fact the author must see; and every changed
English input becomes a re-translation advisory. Staging writes only inside
its own overlay, never overwrites an existing translation, and is a no-op on a
finished one — what remains after staging is exactly the prose.

The Spanish house register is educated castellano with a restrained Argentine
inclination where it reads naturally, without slang or lunfardo. Where no clear
Argentine preference applies, use Spain Spanish; do not fall back to generic
Latin American, Mexican, Caribbean, or other regional variants.

## Collecting editions

The repository may have several collecting editions, with exactly one selected
as the intake target. This lets production continue on one edition while new
leads accumulate in the next without pretending the earlier edition is
released. Opening a collection is explicit:

```sh
uv run --locked mag collect 004-unreleased --issue-number 4
```

New captures are queued to the intake edition by default. `mag capture
--edition <edition-id>` can deliberately target another collecting edition,
while `mag sources` and `mag queue` reconcile otherwise unassigned records into
the intake edition. A batch of submitted links never creates an edition
implicitly.

`library/release-state.yaml` is the authoritative ledger. A source appears in
exactly one collecting or released edition. Release a complete collecting
edition with:

```sh
uv run --locked mag release <edition-id>
```

Release is deliberately all-or-nothing. The command first reconciles every
source record into the intake queue and verifies that every source queued to
the release target appears
in a rendered article's `source_ids` provenance. A bare entry under the
manifest's top-level `sources` inventory is not enough. It then validates the fidelity
ledgers, and successfully builds the reader and home-print packages. Only then
does it mark the edition manifest `released`, move its sources into
`released_editions`. Other collecting editions and their queues are unchanged;
if none remains, release opens an empty incremented edition such as
`002-unreleased`. Manifest and ledger updates use atomic replacements with
rollback on failure. Rights and distribution fields are preserved unchanged;
release does not turn a private reprint into a publicly cleared one.

Use `--next-edition-id 002-a-working-title` only when the next collection
has not already been opened and already has an intentional identifier. Sources
assigned to the released edition are never requeued.

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

Authenticated browser captures that expose embedded media must archive each
observed asset separately and include a `media-manifest.json` beside the capture.
Each manifest entry uses a safe `relative_url` and may preserve its original
HTTP(S) `source_url`, positive `source_position`, semantic `role` (`diagram`,
`figure`, `photo`, `title_card`, `decorative`, or `duplicate`), heading, title,
description, and alt text. The inventory validates and carries this context into
automatic curation. Title cards, decorative assets, and duplicate bytes are
rejected deterministically; source-referenced print-resolution diagrams remain
eligible even when the browser export itself is a full-page screenshot.

Automatic media decisions live in a bundle-keyed curation audit and are pinned
in `record.yaml`; exhaustive inventories remain generated output. The curator
extracts substantive inline SVG diagrams into generated PNG derivatives without
changing immutable raw evidence, rejects screenshots, decorative vectors,
low-resolution assets, and context-free images, then selects only the strongest
zero to three candidates. Every decision records its score, rationale, and
rejection reasons. A build fails if any capture has not been curated.

## Edition manifests

See `templates/edition.yaml`. An article points at both a manuscript and a
fidelity ledger. It may supply a concise `author_note`, rendered below the
byline, containing identity or relevant CV context: current role, notable
company, founder status, or first-hand experience that establishes why the
author is worth hearing. It must not summarize the article. Omit it for
self-explanatory house or institutional bylines such as `The Editors`.
Each language overlay provides a localized note when the English article has
one and omits it when English does. An overlay may localize the `author` byline
itself when it is a description rather than a proper name; absent, the base
author is used. Paths are
repository-relative and cannot escape the project. The compiler validates
required fields, source references, duplicate IDs, and file existence before
layout.

An article may select at most three curated figures. Each selection records why
it is important, useful, beautiful, or cool; resolves to a hash-verified source
asset; and uses a full-width `evidence_band`, an `evidence_band_prose` with a
centered readable measure below the image, or a single-column `column_plate`.
Placement is semantic: `__opener__` or an exact `##` heading,
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

The A5 reader PDF is produced deterministically by the renderer named in
`[render] engine` — WeasyPrint by default, or `"reportlab"` for the legacy
typesetter. The two are no longer interchangeable: WeasyPrint kerns, ligates,
may break inside a hyphenated token, sets real quotation marks instead of ASCII
ones, and binds a paragraph's last two words rather than stranding the final one
on a line of its own; ReportLab does none of those, so selecting it changes the
publication rather than rolling it back.
`mag build --engine <name>` overrides the key for a single build without
changing configuration; see `docs/RENDERER_MIGRATION.md`.
The home booklet
is imposed onto landscape A4 with `pypdf` and padded to a multiple of four pages.
Reader page 2 is an otherwise empty inside front cover, the penultimate reader
page is an otherwise empty inside back cover, and the designed back cover remains
the final page. Both inside covers, and their shared A4 booklet side after
ordinary imposition, remain completely blank.

Three A4 saddle-stitch impositions of the same block ship together, all folded by
one rule and all short-edge duplex. `home/booklet-a4.pdf` is the unchanged
all-in-one for a single-stock print. `home/booklet-a4-interior.pdf` is reader
pages 3 to N-2 — the magazine without the cover and without the blank inside
covers — as its own signature. `home/booklet-a4-cover.pdf` is the outer wrap
alone, one sheet carrying the back cover beside the front cover on its outer side
and both blank inside covers on its inner side, so the wrap can go on heavier
stock the way a bindery prints it. `home/printing-instructions.md` states the
sheet count and stock for each. The package contains:

```text
reader.pdf
home/booklet-a4.pdf
home/booklet-a4-interior.pdf
home/booklet-a4-cover.pdf
home/printing-instructions.md
fidelity.md
preflight.json
render-critic.json
render-review/reader-contact-sheet-01.png
render-review/booklet-contact-sheet-01.png
edition-manifest.json
SHA256SUMS
```

`preflight.json` validates page geometry, signature length, the sheet size and
sheet count of all three booklets, cover and figure resolution, figure geometry,
and studio blockers. Rights metadata remains part of source provenance but does
not gate preflight, builds, or releases. Curated figures require captions, credits, non-colliding placement,
and at least 300 effective PPI. The renderer embeds
the standard PDF fonts by default. A professional print profile is included as
a specification, but PDF/X conversion, trim bleed, and the printer ICC output
intent remain explicit studio preflight steps.

Every language also passes through the render critic before packaging. It
rasterizes every reader page with Poppler, blocks unintended blank pages, orphan display
punctuation, inefficient contents pagination, placeholder cover copy, invalid
signature length, and breached editorial or article page caps. It also checks each
imposed document against its declared plan: the all-in-one booklet and the cover
wrap side by side with their rasters, and the interior structurally — side count,
A4 landscape geometry, and exact left/right reader-page pairing — since its pages
are already judged in the reader pass. It records
per-page ink geometry in `render-critic.json` and produces numbered contact
sheets plus 144-DPI individual page and booklet-side rasters for the required
final visual review. The critic also verifies each imposed left/right page pair
against the declared saddle-stitch, short-edge-duplex plan, including the
inside-cover side, which must be blank. Sparse pages are
review prompts, not automatic failures, because deliberate openers and closing
plates may use whitespace. Because pale ornaments barely register as ink, each
page row also records a presence ratio and bounding box, its running-text line
count, and its largest all-paper rectangle inside the live area; on those
measurements the critic raises a `whitespace-void` review item for a void at
least 96 pt tall spanning at least ninety percent of the measure (a trailing
void on an article's last page is the article simply ending, and is excused)
and an `article-stub-last-page` item when an article's final page carries
fewer than five lines of running text, prompting a human to re-cut the break.
The editorial page cap is read from the package's own `edition-manifest.json`,
clamped to the publication ceiling, rather than hardcoded. And when the build
manifest declares `layout.tail_arts`, the critic reconciles the ledger: every
tail ornament an article declared but the typesetter did not print becomes a
`tail-art-dropped` review prompt. The report and review images are included in
`SHA256SUMS`.

Edition-owned illustration directions are compiled separately from the build:

```sh
uv run --locked mag illustrate <edition-id>
```

New illustrated editions should begin with `templates/illustrations.yaml`. Its
`direction_preset` points to
`art-directions/playful-science-vignettes.yaml`, the publication's reusable
default: original Doraemon-era children's science-manga energy, one wordless
narrative vignette, friendly rounded figures and gadgets, simple black ink,
warm paper, and relaxed spot color. Wide single scenes are the default for
article tails; square scenes are preferred when a standalone placement
supports them; portrait scenes are secondary and reserved for vertical ideas
or closing plates. The preset explicitly forbids recognizable franchise
characters and copied signature gadgets. It also names the approved square and
wide prototypes under `art-directions/references/`; their hashes travel with
the prompt package and build manifest so future generations use the same visual
anchors rather than relying on prose alone.

The command validates the committed article-tail and closing-plate inventory,
then writes exact authoring prompts and a hash-bound selection manifest under
`output/<edition-id>/illustration-prompts/`. Image generation and candidate
selection happen at author time; `mag build` only consumes the committed PNGs.

## Web edition

`mag web <edition-id>` writes a browsable web edition for every configured
language to `output/<edition-id>/web/<language>/index.html`, printing one
`<language>: <index path>` line per language written; `--language` narrows to
one. The directory is self-contained — the semantic HTML with the screen
stylesheet injected, the bundled OFL faces and their licenses, and every
content image copied under a sanitized asset name — so `index.html` opens
directly from the filesystem or from any static server (`python -m
http.server` in the output directory). Repeated runs are byte-identical.

The web edition is a private screen profile, not a publication step. It is
not part of `mag build`, never enters a release package, and is outside the
hash-bound render review, which binds PDFs only. While captured sources lack
a public redistribution basis, web output must not be published; it lives
under `output/`, which stays out of Git.

## Release archive

`output/` is generated scratch and is not version-controlled, so an edition's
as-printed deliverables are preserved by hand in a sibling repository-external
directory:

```text
../magazine-releases-archive/<edition-id>/       English reader, booklets, and machine records
../magazine-releases-archive/<edition-id>/es/    the same set for Spanish
```

That directory is **the authoritative copy** of what was printed. It holds
`reader.pdf`, the A4 impositions under `home/`, and the build's own
`edition-manifest.json`, `render-critic.json`, `preflight.json`, `fidelity.md`
and `SHA256SUMS`; the `render-review/` rasters are excluded because every build
regenerates them. Verify an archived edition with `shasum -c SHA256SUMS` inside
its directory — the raster lines are expected to report missing files. Each
edition directory carries a README recording its renderer, what changed, and how
it verified, and the archive root indexes every edition. Editions 001 and 002
were set by ReportLab and are not reproducible from the current renderer.

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
every configured reader and booklet exactly as they sit on disk, then rewrites
each package's `render-critic.json` `visual_review` block (and its `SHA256SUMS`
line) in place so the reports expose the decision without re-typesetting
anything; `--rebuild` restores the old rebuild-and-compare proof. Any
subsequent PDF change makes the review `stale`. A `changes_required` decision
must include at least one `--finding`. `mag release` refuses missing, stale, or
changes-required review state.

The evidence review is the render review's editorial sibling: the adversarial
manuscript-versus-source audit defined by `prompts/evidence-review.md`,
recorded rather than merely performed. After auditing every article against its
fidelity ledger and the committed source extractions:

```sh
uv run --locked mag review record <edition-id> --kind evidence \
  --reviewer "Independent auditor" \
  --result approved
```

The decision is written to `editions/<edition-id>/reviews/evidence.yaml`,
binding per article the SHA-256 of the manuscript, of the fidelity ledger, and
of every extraction body it was audited against. Staleness is derived per
article: `mag review status` reports, for each article, whether its bound
hashes still match disk and when it was last audited, and one drifted article
makes the whole record `stale` (naming the drifted articles and inputs). After
re-auditing only what changed, `--articles <id,id>` re-binds just those
articles from current disk state and preserves every other article's recorded
binding and `reviewed_at`, so one changed manuscript no longer costs a
full-edition re-audit. `mag review status` reports both kinds, and `mag
release` refuses a missing, stale, or changes-required evidence review before
rendering.

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
standard library plus PyYAML. WeasyPrint, ReportLab and pypdf are imported only
by their PDF paths — and the two reader engines only by the one that is
selected — making non-rendering operations easy to test in constrained
environments.
