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
  the first time, scaffolds `edition.yaml`: author_note is a short bio (role
  and where the author works or writes) from one gated call that rejects a
  bio naming the author or reusing a title word, never a summary; the first three source images
  (every one in verbatim) become figure rows captioned from their alt and
  re-anchored to the run's headings, the rest commented out; a verbatim
  body drops bare-URL lines, headings that repeat the title, and a heading that opens it,
  since the opener needs a paragraph first, then one gated cleanup call
  (`prompts/verbatim-cleanup.md`) cuts whole blocks that are not the article
  (repeated intros, promo and link footers, docs boilerplate), only among the
  first three blocks or a run that ends it, never code, at most 15% of words;
  one gated call drafts short_title and display_emphasis; art stays TODO) -> edit `edition.yaml` -> `mag art NNN` (default gen-cmd is
  `tools/imagegen`) -> the agent always picks openers, tails, and closing
  plates itself; the editor picks cover, endpaper, and card art in
  `art/showcase.html` and gives the final ok on everything -> `mag art NNN --promote`
  -> `mag art NNN --only endpaper` (once the cover is picked; promote prints
  it) -> pick and promote again -> `mag render NNN`. If a
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
  run (never an untracked local run), read from a sparse worktree of HEAD at
  `.magazine/site-head` (so uncommitted edits neither block nor leak; `mag
  epub` loads through it too), with the print-tone figure copies,
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
  the approved files to the issue's GitHub Release (every issue ships both the
  reader PDF, the EPUB, and `-a4-booklet.zip` holding `booklet-a4-cover.pdf`
  and `booklet-a4-interior.pdf` from beside `--pdf`, so pass a full render's
  reader.pdf; without `--epub` it builds one with `mag epub`) (`gh`, logged in on the
  owner's laptop; repo from `[site] repo`): tag `issue-NNN`, created when
  missing, assets `berreta-futura-NNN-<lang>.pdf` and `.epub` replaced in place
  with `--clobber` (only the latest exists), an asset whose sha256 already
  matches the release's digest is skipped. It writes
  `editions/NNN/publish.yaml` as `<lang>: {pdf: {url, bytes, sha256}, epub:
  {...}, booklet: {...}}`; committing that file publishes the links, which the site adds
  with `?v=<sha8>`.
- After pushing a `site/` change, run `uv run tools/deploy.py`: it deploys the
  committed `site/` from the laptop with wrangler (only changed assets upload);
  Workers Builds repeats the same deploy from the pushed commit.
- `tools/letter.py`, `coverproof.py`, `compare.py`, and `read.py` are
  standalone Python side scripts (`uv run --with <dep> tools/<name>.py`), not
  pipeline steps; nothing in `mag` calls them.
- `mag cards` makes standalone model cards outside any issue, for sharing and printing:
  `mag cards write <slug> --source <id>...` writes `cards/<slug>/card.json` through the same
  gated card writer produce uses; `mag cards art <slug>` generates one candidate per art brief
  into `cards/<slug>/candidates/` (gitignored; earlier ones move to `earlier-<time>/`) plus a
  labelled `preview.pdf` with each set in the card; `--rebrief` rewrites only the art briefs
  (every other field stays) before generating;
  `--pick <n-vN>` promotes one to `cards/<slug>/art.jpg`; `mag cards sheet <slug|card.json[:art]>...
  [--out pdf]` lays cards three to an A4 landscape sheet with crop marks, each sheet followed by
  the brand pattern back (`mag/assets/typeset/card-sheet.typ`: violet, halftone waves, wordmark +
  site + BF tiles on a -30 degree half-drop). The back is a uniform all-over pattern on purpose:
  duplex alignment is never trusted and every trimmed card must still read. Print duplex, short
  edge. A source for a card alone is captured with `mag capture <url> --library-only` (no plan
  row, no intake change).
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
  - `record.yaml`: id, title, author, url, site, captured_at, published_at,
    tags, synopsis. An author the page does not name falls back to its
    JSON-LD author or publisher, then og:site_name; site is og:site_name or
    the host.
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
  gets its own `article` row (never auto-promoted to verbatim); `--article
  <id>` joins an existing row instead and `--mode` (article, in_a_nutshell,
  explainer, verbatim) picks another mode. Decide the source-to-article
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
  `original_synthesis`, `in_a_nutshell`, `explainer` (multi-source teaching piece:
  user, developer, internals; `prompts/explainer.md`), `verbatim` (source text unchanged, no
  writer call, head/tail cleanup only, ten-page cap instead of seven), `model_card` (an AI model
  launch post: the article writer as usual plus one gated call, `prompts/model-card.md`, writing
  `articles/<id>/card.json` in the run; every number, the model id, and the tester quote must
  appear in the row's sources, each fact once; produce names missing slots such as the price and
  searches the lab's own sites for them (one sonnet call with WebSearch/WebFetch, prompts/
  model-card-sources.md; every URL must be on the lab's domains), captures what it finds with
  `--article <id>` (the page joins the row), and rewrites the card; the release date must be printed
  in the sources too. The article's opener is the title plus the card on one page (no opener art,
  no author note; the card art from `card_art_path` is the only picture), and `mag render` writes
  each card as a standalone 300 ppi PNG to `editions/NNN/cards/<id>.png`, which the site and EPUB
  use as the article's lead image and social preview), plus the `original_editorial` opener.
- `mag capture` without `--mode` or `--article` checks for a model launch post: a regex
  prefilter (benchmark names or a per-million-token price), then one gated sonnet call
  (`prompts/model-card-detect.md`, the evidence sentence and model name must be on the page);
  a launch becomes a `model_card` row, `--mode article` overrides. Card art is its own slot:
  the card's four art briefs come from their own gated call after the card text
  (`prompts/model-card-art.md`, from the card alone: a beautiful giant, surreal and free, each
  brief a different idea, composition, and painting style; no menu or example in the prompt, they
  bias every card the same way). `mag art NNN --only card` makes one image per brief, verbatim
  plus a no-text line (no anatomy gate), pick in the showcase, then `--promote`. Never a
  "creature", never birds; the gate refuses a brief that never says giant, colossus, or titan,
  a non-character subject, and many-armed figures.
  See `docs/EDITORIAL_POLICY.md`.
- Source articles fit in at most seven A5 reader pages (ten for
  `verbatim`). No edition carries an opening editorial: produce no longer
  writes one, the renderer treats `editorial:` as optional, and an older
  edition drops its `editorial:` row when it is re-produced.
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
- The endpaper is the inside face of the A4 cover sheet, one landscape
  pattern across both inside covers and the fold (`cover.endpaper_path`,
  `prompts/endpaper.md`). `mag art NNN --only endpaper` refuses until
  `cover.art_path` is picked, drafts eight pattern briefs from the cover's
  brief, and passes the cover pick to the generator as `{ref}`. Render
  appends it as side 2 of `booklet-a4-cover.pdf` only (duplex, short edge);
  the reader PDF, EPUB, site, and all-in-one booklet never carry it.
- The inside front cover carries the credits (`[credits]` in magazine.toml,
  the site, and the issue's URL); book issues end on the about page
  (`[about]` in magazine.toml) as the last interior page, so it prints in the
  A4 interior; the inside back cover stays blank (the endpaper covers it).
- Render stages raster figures capped at 2480 px on the long side (a full
  A5 page at 300 ppi) and embeds art as print JPEG copies at q80; picks stay
  q90. The EPUB carries images at 1200 px, q78.
- Typesetting is chosen per edition by `format.typesetting` in edition.yaml:
  `book` (EB Garamond, `mag/assets/typeset/template-book.typ`, 018 on, and
  what `mag produce` scaffolds) or `classic` (the default, the frozen
  `template.typ` that editions 001-017 keep). Change book for new issues;
  leave classic alone so old issues re-render as published.
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
