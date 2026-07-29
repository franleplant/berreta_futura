# Magazine project guidance

This repository builds private-first, source-faithful magazine editions.

## Non-negotiable rules

- Preserve provenance from the submitted lead to every underlying primary source.
- Treat `sources.md` as generated output. Human annotations belong in source records.
- Never replace a source article with an unlabeled or generic AI summary. New magazine-authored arguments use `original_synthesis`; length-driven condensation uses attributed, source-mapped `faithful_synthesis`.
- Write `faithful_synthesis` in the source author's existing grammatical person and point of view. The byline and mode label provide attribution; do not add “the author argues/says/explains” narration unless those are the source's exact words. Prefer retained wording and light edits, summarizing only where the page budget requires it.
- Source articles may occupy at most seven A5 pages in the rendered reader. If a faithful edit exceeds the cap, use the explicit `faithful_synthesis` mode and preserve the argument, evidence, qualifications, and conclusion through source-to-edited fidelity mappings.
- The opening editorial must declare and visibly render a title, and may occupy at most one A5 reader page including its label, title, and byline.
- AI proposes editorial patches; deterministic validation and human decisions advance workflow state.
- Label original editor text so it cannot be mistaken for a source author's words.
- A source is not captured until its raw evidence bundle is committed under `library/sources/<source-id>/raw/<bundle-sha256>/`. Archive before queueing; never rely on a live URL as the durable copy.
- Raw bundles may contain page responses, rendered text, images, or sanitized browser exports. Never commit cookies, credentials, authorization headers, browser profiles, or session data.
- Never claim an edition is press-ready without a named printer profile and a passing preflight.
- Cover art contains no baked-in masthead or cover lines. Layout code owns all typography.
- Keep the inside front cover (reader page 2) and inside back cover (the penultimate reader page) completely blank; the imposed inside-cover sheet side must therefore also be blank.
- Treat intake batches as transport only. Every unreleased source belongs to exactly one collecting edition; several editions may collect concurrently, with one explicit intake target.
- Never create a collecting edition merely because the user sends another group of links. Open or select one only through `uv run --locked mag collect <edition-id> --issue-number <number>` or an equally explicit human decision.
- Release only with `uv run --locked mag release <edition-id>`. Every source record must be queued and represented in a rendered article's `source_ids`; a top-level manifest declaration alone cannot silently postpone material.
- Use UV for every Python operation. Never use `pip`, bare `python`, `python -m venv`, an activated virtualenv, or an ad-hoc dependency directory.
- Generate every language listed in `publication.languages` on every validation, build, and release. English remains the source edition; Spanish translations use educated castellano with restrained Argentine preferences, fall back to Spain Spanish, avoid slang and generic Latin American regionalisms, preserve Markdown block structure, and pin the exact English input hashes.
- Never compute or hand-edit a SHA-256 pin. After changing any English input, refresh the derivable pins with `uv run --locked mag pin <edition-id>` and stage each configured overlay with `uv run --locked mag translate <edition-id> <language>`; translate the placeholder and advisory rows it reports before validating. `mag validate` reports staleness (with the expected digest) but never repins.
- Check page budgets with `uv run --locked mag fit <edition-id>` before authoring the translation or fidelity ledger for a new article, and again after every manuscript edit. Use `uv run --locked mag measure <edition-id>` when you need spans, caps, last-page lines, or the per-paragraph rag table as JSON. Never run a full build, or reach into the renderer with ad-hoc scripts, just to ask whether a piece fits.
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

Every build must pass the built-in render critic for every configured language.
It rasterizes the reader and imposed booklet, writes `render-critic.json`, and
generates numbered contact sheets and 144-DPI individual rasters under
`render-review/`; its structural errors block packaging and release.

After each meaningful layout change and before delivery, spawn an independent
render-critic subagent. Give it every reader and booklet contact sheet plus any
explicitly locked design decisions. It must inspect every sheet, identify
page-specific visual defects, and avoid changing locked elements. Fix confirmed
defects, rebuild all languages, and repeat until the machine report passes and
the independent critic has no remaining actionable findings. Then record the
decision only through `uv run --locked mag review record <edition-id>` with the
reviewer and result flags; do not hand-edit the canonical review record.
Recording binds the decision to the PDFs exactly as they sit on disk and
rewrites only the packaged reports in place — it does not rebuild, so record
against the packages you actually inspected; pass `--rebuild` only when the
rebuild-and-compare proof is explicitly wanted. `mag release` must reject a
missing, stale, or changes-required review.

Every source of every collecting edition needs a committed
`library/sources/<source-id>/extracted.md`, and its fidelity ledgers must pin
`source_body_sha256` to the extraction body. Before release, perform the
adversarial manuscript-versus-source audit (`prompts/evidence-review.md`) and
record it with `uv run --locked mag review record <edition-id> --kind evidence`;
`mag release` rejects a missing, stale, or changes-required evidence review.
Evidence staleness is derived per article: when `mag review status` names
drifted articles, re-audit those articles against their ledgers and
extractions, then re-record with `--articles <id,id>` naming exactly the
articles whose audit was actually repeated — never an article you did not
re-audit. Every other article keeps its recorded binding and `reviewed_at`.
