# Rust rewrite

Status: **proposed**, 2026-08-04. Supersedes `loops-workflow-migration.md` and
`graph-execution-model.md` in full. Companion: `simple-produce.md` (the Python
reference implementation of the produce loop).

## Goal

One Rust CLI, `mag`, that takes sources and spits edition content with internal
improvement loops, in the shape of `tools/produce.py`: state in memory, outputs
as plain sortable files, crash recovery = rerun. Everything the current engine
does that produce.py doesn't is deliberately not carried over.

## The renderer seam (figured out, keep as-is)

The Python renderer is already a clean subprocess with no engine dependency:

```sh
uv run mag-render-adapter <manifest.json> <destination>
```

- Contract `magazine-renderer/1` (`src/magazine/engine_render_bridge.py`):
  a JSON manifest with `operation`, `editionId`, `languages`, `design`, and an
  explicit `inputs` list of `{artifactId, sourcePath, targetPath}`. The bridge
  stages exactly those files in a temp root and writes only under the given
  destination. It never reads workflow state.
- Operations: `measure_article` (the fast page-fit check, usable inside the
  writing loop), `measure_edition`, `render_edition` (reader.pdf, booklet,
  web/, package.zip, QA evidence).
- Rust's job is only: build that JSON manifest from `edition.yaml` + content
  files, spawn the process, read the results.

## What stays (and nothing else)

| Keep | Why |
|---|---|
| `editions/`, `library/`, `runs/` | the product, the sources, run outputs |
| `prompts/`, `docs/` | the quality system — where all future effort goes |
| `src/magazine/` + `pyproject.toml` + `uv.lock` + `templates/` + `design/` + `profiles/` + font vendor files | the renderer subprocess |
| `tools/produce.py` | reference implementation until `mag produce` replaces it |
| `meta/` | plans |
| all generated images, wherever they live today | relocated into `editions/<ed>/art/` before the purge |

Everything else is deleted in one commit (git history keeps it all):
`engine/`, `node_modules/`, `package*.json`, `tsconfig.json`, `dist/`,
`scripts/*.mjs`, `vendor/` (Loops), `.magazine/`, `tests/` (TS), and — after
extraction — `durable/` and `inputs/` (the translation prompt and anything in
`inputs/`/`durable/` not already in `library/`/`editions/` moves first).

## The Rust CLI

`mag` with five subcommands, all following produce.py's rules — no database, no
run state, fail loud, every model call logged with seconds and dollars:

- `mag plan <edition>` — one model call proposes `plan.yaml`; human edits it.
- `mag produce <plan.yaml>` — per article in parallel: write → cheap mechanical
  checks (page fit via `measure_article`, code fences, figure refs — pennies
  before paid judges) → seven-lens judge panel in parallel → rewrite on
  blocking/major findings, ≤2 rounds → editorial → edition review. `--resume`
  skips pieces whose final exists.
- `mag translate <run-dir>` — one call per accepted piece (ES), same loop shape.
- `mag art <edition>` — produce.py-style image rounds: generate candidates into
  `editions/<ed>/art/rounds/<UTC-ts>/`, never overwrite anything, proof sheet,
  human selects, selection recorded in `edition.yaml`. All historic images kept.
- `mag render <edition>` — build the renderer manifest, spawn
  `mag-render-adapter`, human reads the PDF.

Model calls: spawn `claude -p --output-format json --disallowedTools "*"`,
prompt on stdin, parse-or-retry (exactly produce.py's `Caller`). Source-blind
judging stays a property of prompt construction, not an authorization system.

## Steps

1. **Purge first** — so the implementer agent never sees the old code. In one
   commit:
   a. copy anything that exists only under `durable/` or `inputs/` (selected
      Edition 4 images, ES translations, translation prompt) into `editions/` /
      `prompts/`, verified with a diff, not trust;
   b. delete every Python and Node.js implementation file except the keep
      table above: `engine/`, `node_modules/`, `package*.json`,
      `tsconfig.json`, `dist/`, `scripts/*.mjs`, `vendor/`, `tests/`,
      `.magazine/`, `durable/`, `inputs/`, and any `src/magazine/` module the
      renderer seam does not import.
   After this commit the repo contains only: content, prompts, docs, the
   renderer, `tools/produce.py`, and plans.
2. **Validate the loop shape** — one produce.py run on Edition 5 sources (it is
   the executable spec for `mag produce`).
3. **Scaffold `mag`** — edition.yaml serde structs, the `claude -p` caller, the
   renderer-manifest builder. Then port the produce loop, then art, then
   translate/render.
4. **Ship Edition 5 with `mag`** — acceptance is a released edition, not tests
   over infrastructure.

## Non-goals

Durable workflow engines, event logs, leases, attempts, credentials, revision
IDs, content-hash pins as runtime identity, migration tooling, XState, Loops,
or any second authority over what a file in git already says.
