# Magazine project guidance

This repository captures articles, rewrites them, and produces a printable A5
magazine. Keep it simple: capture the text and images, write, render. No
provenance bundles, no pinning, no bookkeeping beyond one small record file.

## Pipeline

- `mag` (Rust, in `mag/`) is the CLI: `capture`, `plan`, `produce`, `art`,
  `translate`, `anchors`, `render`, `epub`, `site`, `publish`. Build with `cargo build`, run from the repo root.
- The pipeline leads: every step prints the next command when it finishes.
  Follow that, not the previous edition. The order is `mag capture` (writes
  the plan row) -> `mag produce editions/NNN/plan.yaml` (writes the run and,
  the first time, scaffolds `edition.yaml` with TODO fields and figure
  candidates) -> edit `edition.yaml` -> `mag art NNN` (default gen-cmd is
  `tools/imagegen`) -> pick in `art/showcase.html` -> `mag art NNN --promote`
  -> `mag render NNN`. If a
  step leaves you guessing what comes next, fix the step's output in code;
  documenting the gap here is the fallback, not the fix.
- `mag render` typesets through Typst in Rust (`mag/src/typeset/`): it
  loads `edition.yaml`, lays out reader pages, and writes the PDFs; the render
  critic reads the laid-out Typst document, not the PDF. `--no-legibility`
  skips the tesseract figure legibility check. There is no other engine and
  no Python in the render path. It makes no model call: it refuses a figure
  anchor that matches no heading of the run and names the fix, `mag anchors NNN`
  (the one cheap model call that re-anchors figures and patches `edition.yaml`;
  `--check` only lists them and exits 2 when any are unresolved, 1 on error).
- `mag site [--out site] [--check]` builds the public static site into the
  committed `site/`; Cloudflare Workers Builds deploys it to
  berreta.franleplant.com when a push changes `site/**`
  (`deploy/web/README.md`). `--check` rebuilds into a temp dir and fails
  listing paths that differ from `--out`. It publishes the editions listed in
  `magazine.toml` `[site] editions`, each from its newest git-tracked complete
  run (never an untracked local run), with the print-tone figure copies,
  resized JPEG/WebP variants, and no Typst render and no model call. Download links
  come only from a committed `editions/NNN/publish.yaml`; without one the
  issue page has no PDF or EPUB link. It refuses to write a page that drops any manuscript block,
  figure, or extract.
- `mag render` also writes the typeset front cover as `<lang>/cover.png` in
  its render dir. `mag epub NNN [--lang en] [--cover file]` packages that
  language as a reflowable EPUB 3 for Apple Books: the newest tracked run's
  manuscripts, figures, and extracts through the site's HTML walk (same
  drop check), embedded Source Serif, and the newest render's cover. It
  writes `editions/NNN/epub/<publication>-NNN-<lang>.epub` (gitignored; it
  ships through `mag publish`).
- `mag publish NNN --pdf <file> [--epub <file>] [--lang en] [--dry-run]` ships
  the approved files to the issue's GitHub Release (`gh`, logged in on the
  owner's laptop; repo from `[site] repo`): tag `issue-NNN`, created when
  missing, assets `berreta-futura-NNN-<lang>.pdf` and `.epub` replaced in place
  with `--clobber` (only the latest exists), an asset whose sha256 already
  matches the release's digest is skipped. It writes
  `editions/NNN/publish.yaml` as `<lang>: {pdf: {url, bytes, sha256}, epub:
  {...}}`; committing that file publishes the links, which the site adds
  with `?v=<sha8>`.
- `tools/letter.py`, `coverproof.py`, `compare.py`, and `read.py` are
  standalone Python side scripts (`uv run --with <dep> tools/<name>.py`), not
  pipeline steps; nothing in `mag` calls them.
- `mag print <url> [--html file] [--out dir] [--chrome bin]` is a standalone
  side tool, not an edition step: it turns one blog post into
  `output/print/<slug>/print.pdf` ready to print (plus the self-contained
  index.html it is rendered from), with no model call and no library record.
  It re-typesets the article reader-mode style: the site's CSS is discarded
  and the content is set in a built-in print stylesheet (serif body, reading
  measure, standard code/quote/table treatment, centered images), after
  stripping site chrome, scripts, players, link-preview cards, bare-URL link
  lists, and emptied wrappers; images are localized and the PDF step runs
  headless Chrome, trying three image-size caps and keeping the densest PDF
  (`--image-cap` pins one). `--layout` picks the page: `a5` (default,
  booklet: two numbered A5 pages per landscape A4 sheet in reading order,
  no imposition yet), `columns` (A4 two columns), `single` (A4 one column).
- Prompts live in `prompts/`. The writer prompts are hand-tested; do not add
  instructions to writer calls or inject style packs.

## Sources

- A captured source is `library/sources/<id>/`:
  - `record.yaml`: id, title, author, url, captured_at, published_at, tags,
    synopsis.
  - `article.md`: the source's substantive text, verbatim, in source order.
    Image references point at `media/...` inside the same directory.
  - `media/`: the source's images at original resolution.
- Edition membership lives in `editions/<edition>/plan.yaml` alone; the default
  capture edition is `[intake] edition` in `magazine.toml`. `sources.md` is
  generated from the records; do not hand-edit.
- `mag capture <url> [--edition NNN] [--tags a,b]` is the whole intake: it
  fetches the page, transcribes it to verbatim Markdown through one
  fidelity-gated model call (prose must match the page word-for-word, in page
  order, without skipping stretches of it; code blocks byte-exact; retried
  with the misses fed back), downloads media,
  writes record.yaml, prepends the `sources.md` entry,
  and records the source in `editions/<edition>/plan.yaml` (created with that
  one row if it does not exist, and then `[intake] edition` moves to it). By default the source
  gets its own row, auto-promoted to `verbatim` when the captured text fits
  seven reader pages (word-count calibration in plan_cmd) and `article`
  otherwise; `--article <id>` joins an existing row instead and `--mode`
  (article, in_a_nutshell, verbatim) overrides the auto decision. Decide the source-to-article
  mapping at capture time, on the command line, so it lives in plan.yaml and
  never only in a conversation. Raw HTML lands in `.magazine/capture/` (untracked). For pages curl
  cannot reach (login walls, JS-rendered apps like X), fetch the DOM with a
  browser first and pass it as `--html <file>`; the rest is identical. When `--edition` is a prefix of
  existing edition ids but matches none exactly, capture refuses and asks for
  the full id (`plan_cmd::intake_edition_for`).
  `mag capture --refresh <source-id> [--html file]` re-transcribes an existing
  source through the same gate and replaces its article.md, changed media,
  synopsis, and `sources.md` entry; it touches no plan or edition.
  `mag plan NNN` only checks that every source a plan references has a record.
- Never replace a source's text with an unlabeled summary. Keep the author's
  wording, structure, and headings; drop site chrome.

## Editions

- `editions/<edition>/edition.yaml` names articles, manuscripts, art, and
  figures. A figure row names its `source_id` and a `path` relative to that
  source's directory, plus caption, alt_text, anchor, and layout.
- An `extracts` row is the figure pattern for text the edition MUST print
  verbatim: it names a `source_id`, `begin`/`end` markers that each pin one
  position in that source's article.md, a `style` (`code` or `quote`),
  caption, and anchor. The renderer pulls the run from the captured source at
  load time, never from the writer, and refuses to load if the markers are
  ambiguous or the manuscript already carries the run verbatim.
  Captions and anchors localize; the run itself never does. Declare the row
  in plan.yaml and carry it into edition.yaml at assembly.
- Content modes: `faithful_edit`, `faithful_synthesis`, `selected_extracts`,
  `original_synthesis`, `in_a_nutshell`, `verbatim` (source text unchanged, no
  writer call, ten-page cap instead of seven), plus the `original_editorial`
  opener.
  See `docs/EDITORIAL_POLICY.md`.
- Source articles fit in at most seven A5 reader pages (ten for
  `verbatim`). Editions from 010 on carry no opening editorial: produce no
  longer writes one and the renderer treats `editorial:` as optional
  (editions 001-009 keep theirs).
- Filler art never repeats inside an edition: cover, openers, tails, and
  closing plates must all be distinct images, and two variants of one brief
  count as a repeat; generate more plates instead (`mag art <edition> --only
  closing`).
- Every fenced code block in a manuscript is a contiguous exact run from a
  captured source. Drop a block whole if it cannot be preserved.
- No CommonMark footnote syntax (`[^1]`) in manuscripts.
- English is the source edition. Spanish uses educated castellano with
  restrained Argentine preferences, no slang, and preserves Markdown structure,
  links, and code exactly.

## Art and render

- Image generation and art selection are separate steps; rendering only
  consumes selected art and never generates an image.
- Candidates in `art/rounds/` stay local (gitignored). `mag art NNN --promote`
  turns each pick edition.yaml names there into `art/picks/<stem>.jpg` (the
  JPEG print embeds anyway) and repoints edition.yaml; render refuses round
  paths. Editions 001-009 still track their rounds and need a promote to render.
- Cover art carries no baked-in masthead or cover lines; layout owns all
  typography.
- Keep the inside front and back covers blank.
- The logo is defined in `mag/assets/brand/README.md` and generated by `tools/logo.py`;
  the cover masthead, site header, favicon, and social card all draw those committed SVGs.
- A figure that misses its heading's page floats to the next page top while the text flows on (`mag/src/typeset/flow.rs`); a rotated plate waits for a block boundary.
- Layout feedback comes from the production measurement interface, not
  character counts.

## Repository rules

- Mechanical beats linguistic: solve a problem with a deterministic, measured
  step (pixel statistics, OCR geometry, Typst measurement, string checks)
  before reaching for a model call. Use an LLM only where no deterministic
  signal exists, and gate its output with a mechanical check.
- Ship each feature complete in the fewest lines that stay readable, and
  keep cyclomatic complexity low. Style is enforced by tooling, not prose:
  `cargo fmt`, `cargo clippy` (complexity, length, and a named list of
  pedantic lints, all `deny` in Cargo.toml; add pedantic lints by name,
  never the whole group, and fix findings instead of adding `allow`),
  `uvx ruff format` and `uvx ruff check` on `tools/` (C901, ERA in ruff.toml),
  and `mag/tests/nocomments.rs` under `cargo test` for the one rule no linter
  has (no comments; clap help text and `__doc__` usage strings excepted).

- Never author Unicode U+2014 in prose, comments, prompts, or copy. Preserve it
  only inside captured source text or an exact quotation.
- Keep `.magazine/`, `output/`, run scratch, and credentials out of Git.
- Setup, once per clone: `git config core.hooksPath .githooks`. The
  pre-commit hook then runs `cargo fmt --check`, `cargo clippy -D warnings`,
  `ruff format --check` and `ruff check` on `tools/`, and the no-comments
  test; a commit that fails any of them does not land. Zero warnings is the
  standing state, not a goal.
- Verification: `cargo test` in `mag/` (also runs the comment check). Tests assert
  invariants by hand, not recorded oracle output; the one surviving snapshot is
  `mag/tests/pdf_fixtures/verdicts.tsv`, re-recorded with
  `MAG_PDF_FIXTURES_BLESS=1 cargo test --test pdf_fixtures` after an intended change.
- NEVER switch to a feature branch; always work on main unless a human
  requested otherwise. Commit coherent checkpoints.
- Assume there are other agents working in this very same local repo; don't
  interfere with them.
