# Magazine project guidance

This repository builds private-first, source-faithful magazine editions.

## Non-negotiable rules

- Preserve provenance from the submitted lead to every underlying primary source.
- Treat `sources.md` as generated output. Human annotations belong in source records.
- Never replace a faithful source article with an AI summary unless an edition explicitly selects `original_synthesis` mode.
- AI proposes editorial patches; deterministic validation and human decisions advance workflow state.
- Label original editor text so it cannot be mistaken for a source author's words.
- Store third-party raw captures in the ignored `vault/` content store. Commit hashes and metadata, not private captures.
- Never claim an edition is press-ready without a named printer profile and a passing preflight.
- Cover art contains no baked-in masthead or cover lines. Layout code owns all typography.
- Treat intake batches as transport only. Every unreleased source belongs to the single open edition until that edition is explicitly released.
- Never create a new edition merely because the user sends another group of links. Releasing the open edition is the transition that creates the next collection.
- Use UV for every Python operation. Never use `pip`, bare `python`, `python -m venv`, an activated virtualenv, or an ad-hoc dependency directory.
- Run project tools as `uv run --locked <command>`, synchronize with `uv sync --locked`, and change dependencies with `uv add`, `uv remove`, or `uv lock`.
- Commit `pyproject.toml`, `.python-version`, and `uv.lock` whenever their state changes. UV's internal environment must never be managed manually.

## Git checkpoints

- Commit each verified source-intake batch, edition checkpoint, or compiler change as a coherent unit.
- Inspect the staged diff and run the proportionate validation before committing.
- Keep `vault/`, `output/`, temporary files, credentials, and browser-session data out of Git.
- Commit structured records, edition briefs, fidelity ledgers, templates, tests, and deterministic source code.

## Verification

Synchronize the locked dependencies and run verification through UV:

```sh
uv sync --locked
uv run --locked pytest
```

Render generated PDFs to PNG and inspect every page before delivery.
