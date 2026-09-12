# Magazine project guidance

This repository captures articles, rewrites them, and produces a printable A5
magazine. Keep it simple: capture the text and images, write, render. No
provenance bundles, no pinning, no bookkeeping beyond one small record file.

## Pipeline

- `mag` (Rust, in `mag/`) is the CLI: `capture`, `plan`, `produce`, `art`,
  `translate`, `render`. Build with `cargo build`, run from the repo root.
- The pipeline leads: every step prints the next command when it finishes.
  Follow that, not the previous edition. The order is `mag capture` (writes
  the plan row) -> `mag produce editions/NNN/plan.yaml` (writes the run and,
  the first time, scaffolds `edition.yaml` with TODO fields and figure
  candidates) -> edit `edition.yaml` -> `mag art NNN` (default gen-cmd is
  `tools/imagegen`) -> pick in `art/showcase.html` -> `mag render NNN`. If a
  step leaves you guessing what comes next, fix the step's output in code;
  documenting the gap here is the fallback, not the fix.
- `src/magazine/` (Python, run through `uv`) is the renderer: it loads
  `edition.yaml`, lays out reader pages, and produces PDF/web output through
  WeasyPrint. It renders; it does not orchestrate.
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
- `library/release-state.yaml` tracks which sources are queued for or released
  in each edition. `sources.md` is generated from the records; do not hand-edit.
- `mag capture <url> [--edition NNN] [--tags a,b]` is the whole intake: it
  fetches the page, transcribes it to verbatim Markdown through one
  fidelity-gated model call (prose must match the page word-for-word, code
  blocks byte-exact, retried with the misses fed back), downloads media,
  writes record.yaml, queues the source, prepends the `sources.md` entry,
  and records the source in `editions/<edition>/plan.yaml` (creating the
  plan from every queued source if it does not exist). By default the source
  gets its own row, auto-promoted to `verbatim` when the captured text fits
  seven reader pages (word-count calibration in plan_cmd) and `article`
  otherwise; `--article <id>` joins an existing row instead and `--mode`
  (article, in_a_nutshell, verbatim) overrides the auto decision. Decide the source-to-article
  mapping at capture time, on the command line, so it lives in plan.yaml and
  never only in a conversation. Raw HTML lands in `.magazine/capture/` (untracked). For pages curl
  cannot reach (login walls, JS-rendered apps like X), fetch the DOM with a
  browser first and pass it as `--html <file>`; the rest is identical.
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
  `verbatim`); the opening editorial
  fits on one, including label, title, and byline, and must not be an
  article-by-article summary.
- Every fenced code block in a manuscript is a contiguous exact run from a
  captured source. Drop a block whole if it cannot be preserved.
- No CommonMark footnote syntax (`[^1]`) in manuscripts.
- English is the source edition. Spanish uses educated castellano with
  restrained Argentine preferences, no slang, and preserves Markdown structure,
  links, and code exactly.

## Art and render

- Image generation and art selection are separate steps; rendering only
  consumes selected art and never generates an image.
- Cover art carries no baked-in masthead or cover lines; layout owns all
  typography.
- Keep the inside front and back covers blank.
- Layout feedback comes from the production measurement interface, not
  character counts.

## Repository rules

- Ship each feature complete in the fewest lines that stay readable, and
  keep cyclomatic complexity low. Style is enforced by tooling, not prose:
  `cargo fmt`, `cargo clippy` (complexity and length lints in Cargo.toml),
  `uvx ruff format` and `uvx ruff check` (C901, ERA in pyproject.toml), and
  `tools/nocomments.py` under `cargo test` for the one rule no linter has
  (no comments; clap help text and `__doc__` usage strings excepted).

- Never author Unicode U+2014 in prose, comments, prompts, or copy. Preserve it
  only inside captured source text or an exact quotation.
- Keep `.magazine/`, `output/`, run scratch, and credentials out of Git.
- Setup, once per clone: `git config core.hooksPath .githooks`. The
  pre-commit hook then runs `cargo fmt --check`, `cargo clippy -D warnings`,
  `ruff format --check`, `ruff check`, and `tools/nocomments.py`; a commit
  that fails any of them does not land, and `cargo test` fails until the
  hook is installed. Zero warnings is the standing state, not a goal.
- Verification: `cargo test` in `mag/` (also runs the comment check and the
  hook-install check); load the editions through
  `magazine.manifest.load_edition` when the Python side changes.
- Work on the branch the user asks for and commit coherent checkpoints.
