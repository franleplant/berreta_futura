# Magazine project guidance

This repository builds private-first, source-faithful magazine editions.

## Non-negotiable rules

- Preserve provenance from the submitted lead to every underlying primary source.
- Treat `sources.md` as generated output. Human annotations belong in source records.
- Never replace a source article with an unlabeled or generic AI summary. New magazine-authored arguments use `original_synthesis`; length-driven condensation uses attributed, source-mapped `faithful_synthesis`.
- Write `faithful_synthesis` in the source author's existing grammatical person and point of view. The byline and mode label provide attribution; do not add “the author argues/says/explains” narration unless those are the source's exact words. Prefer retained wording and light edits, summarizing only where the page budget requires it.
- Source articles may occupy at most seven A5 pages in the rendered reader. If a faithful edit exceeds the cap, use the explicit `faithful_synthesis` mode and preserve the argument, evidence, qualifications, and conclusion through source-to-edited fidelity mappings.
- The opening editorial must declare and visibly render a title, and may occupy at most two A5 reader pages including its label, title, and byline.
- AI proposes editorial patches; deterministic validation and human decisions advance workflow state.
- Label original editor text so it cannot be mistaken for a source author's words.
- A source is not captured until its raw evidence bundle is committed under `library/sources/<source-id>/raw/<bundle-sha256>/`. Archive before queueing; never rely on a live URL as the durable copy.
- Raw bundles may contain page responses, rendered text, images, or sanitized browser exports. Never commit cookies, credentials, authorization headers, browser profiles, or session data.
- Never claim an edition is press-ready without a named printer profile and a passing preflight.
- Cover art contains no baked-in masthead or cover lines. Layout code owns all typography.
- Treat intake batches as transport only. Every unreleased source belongs to the single open edition until that edition is explicitly released.
- Never create a new edition merely because the user sends another group of links. Releasing the open edition is the transition that creates the next collection.
- Release only with `uv run --locked mag release <edition-id>`. Every source record must be queued and represented in a rendered article's `source_ids`; a top-level manifest declaration alone cannot silently postpone material.
- Use UV for every Python operation. Never use `pip`, bare `python`, `python -m venv`, an activated virtualenv, or an ad-hoc dependency directory.
- Generate every language listed in `publication.languages` on every validation, build, and release. English remains the source edition; Spanish translations use educated castellano with restrained Argentine preferences, fall back to Spain Spanish, avoid slang and generic Latin American regionalisms, preserve Markdown block structure, and pin the exact English input hashes.
- Run project tools as `uv run --locked <command>`, synchronize with `uv sync --locked`, and change dependencies with `uv add`, `uv remove`, or `uv lock`.
- Commit `pyproject.toml`, `.python-version`, and `uv.lock` whenever their state changes. UV's internal environment must never be managed manually.

## Git checkpoints

- Commit each verified source-intake batch, edition checkpoint, or compiler change as a coherent unit.
- Inspect the staged diff and run the proportionate validation before committing.
- Keep legacy `vault/`, `output/`, temporary files, credentials, and browser-session data out of Git. Source-local `library/sources/*/raw/` bundles are canonical and must be committed.
- Commit structured records, edition briefs, fidelity ledgers, templates, tests, and deterministic source code.

## Verification

Synchronize the locked dependencies and run verification through UV:

```sh
uv sync --locked
uv run --locked pytest
```

Render generated PDFs to PNG and inspect every page before delivery.
