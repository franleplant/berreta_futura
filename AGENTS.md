# Magazine project guidance

This repository captures articles, rewrites them, and produces a printable A5
magazine. Keep it simple: capture the text and images, write, render. No
provenance bundles, no pinning, no bookkeeping beyond one small record file.

## Pipeline

- `mag` (Rust, in `mag/`) is the CLI: `plan`, `produce`, `art`, `translate`,
  `render`. Build with `cargo build`, run from the repo root.
- `src/magazine/` (Python, run through `uv`) is the renderer: it loads
  `edition.yaml`, lays out reader pages, and produces PDF/web output through
  WeasyPrint. It renders; it does not orchestrate.
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
  writes record.yaml, queues the source, and prepends the `sources.md`
  entry. Raw HTML lands in `.magazine/capture/` (untracked). For pages curl
  cannot reach (login walls, JS-rendered apps like X), fetch the DOM with a
  browser first and pass it as `--html <file>`; the rest is identical.
- Never replace a source's text with an unlabeled summary. Keep the author's
  wording, structure, and headings; drop site chrome.

## Editions

- `editions/<edition>/edition.yaml` names articles, manuscripts, art, and
  figures. A figure row names its `source_id` and a `path` relative to that
  source's directory, plus caption, alt_text, anchor, and layout.
- Content modes: `faithful_edit`, `faithful_synthesis`, `selected_extracts`,
  `original_synthesis`, `in_a_nutshell`, plus the `original_editorial` opener.
  See `docs/EDITORIAL_POLICY.md`.
- Source articles fit in at most seven A5 reader pages; the opening editorial
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

- Never author Unicode U+2014 in prose, comments, prompts, or copy. Preserve it
  only inside captured source text or an exact quotation.
- Keep `.magazine/`, `output/`, run scratch, and credentials out of Git.
- Verification: `cargo test` in `mag/`, and load the editions through
  `magazine.manifest.load_edition` when the Python side changes.
- Work on the branch the user asks for and commit coherent checkpoints.
