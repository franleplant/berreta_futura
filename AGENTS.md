# Magazine project guidance

This repository builds private-first, source-faithful magazine editions.

## Non-negotiable rules

- Preserve provenance from the submitted lead to every underlying primary source.
- Treat `sources.md` as generated output. Human annotations belong in source records.
- Never replace a source article with an unlabeled or generic AI summary. New magazine-authored arguments use `original_synthesis`; length-driven condensation uses attributed, source-mapped `faithful_synthesis`.
- Write `faithful_synthesis` in the source author's existing grammatical person and point of view. The byline and mode label provide attribution; do not add “the author argues/says/explains” narration unless those are the source's exact words. Prefer retained wording and light edits, summarizing only where the page budget requires it.
- Source articles may occupy at most seven A5 pages in the rendered reader. If a faithful edit exceeds the cap, use the explicit `faithful_synthesis` mode and preserve the argument, evidence, qualifications, and conclusion. `prompts/faithful-synthesis.md` owns the order in which an over-budget piece loses material; the claim-level fact-checker, not a bookkeeping artifact, is what proves the result still represents its source.
- The opening editorial must declare and visibly render a title, and may occupy at most one A5 reader page including its label, title, and byline.
- AI proposes editorial patches; deterministic validation and human decisions advance workflow state.
- Drafting and judging run through `uv run --locked mag produce <edition-id>`, never by hand-driving the prompts. The pipeline owns the order: one writer call per piece over the complete source extraction, then the deterministic gates, then the fact-checker and the line editor in parallel, then at most three revision rounds carrying both the findings and the previous draft's working notes, then the learning personas and the managing editor. It reuses registered art and never generates an image. `--dry-run` prints the plan without calling a model, `--articles` narrows the run, and a piece whose inputs, prompt, and manuscript are unchanged and whose judges approved is skipped. Every call leaves an execution record under `editions/<edition-id>/production/` naming the prompt file and its SHA-256, the backend, model, argv, duration, round, and resulting manuscript digest; those records are provenance and never gate a release.
- An agent driving an edition produces it with the cooperative backend and never hand-orchestrates writers. `uv run --locked mag produce <edition-id> --backend agent` writes every brief that is ready right now under `editions/<edition-id>/production/agent/<piece>/r<n>-<role>/brief.md` and reports the set; answer each one by writing `reply.md` beside it (or `--submit <item>`), then run the same command again to ingest and get the next set. Fan out one subagent per ready brief: several writers are ready at once, and a draft's fact-checker and line editor are ready together. The pipeline still owns the order, the gates, the round budget, escalation at three rounds, and every recorded verdict. If the backend breaks, fix the backend; firing writer subagents around it reintroduces exactly the improvised orchestration `mag produce` exists to abolish.
- Do not refactor the produce pipeline while a run is in flight, for the same reason you would not migrate a schema under a running job. A cooperative run's finished work lives on disk as replies bound to the identity of the question each answered: the prompt file's digest plus the digests of the manuscript, sources, findings and notes the call was handed. Rewording a brief is free and cannot void anything. Editing a file under `prompts/`, or editing the identity functions in `src/magazine/produce_prompts.py`, changes the question and voids every stored answer for the affected role, which on a seven-piece edition is a dozen model calls of completed, judged work. Nothing is deleted (a voided reply is kept as `reply.superseded.md`, and produce names every stored reply the replay did not reach), but recovery is by hand. Finish the edition first.
- Never answer a piece's `evidence` and `line` briefs from the same worker, even sequentially. The line editor is denied the source on purpose, and a worker that has just fact-checked against the source cannot unsee it. Measured on this pipeline: a judge that ran both passes in order caught itself failing to flag an undefined term because the source had defined it, and wrote its first suggested repair in wording only the source could have supplied. Contamination surfaces as findings that are never made, so it leaves no trace to review. One brief, one worker, every time; batch across pieces if you must batch, never across roles.
- Label original editor text so it cannot be mistaken for a source author's words.
- Never author the Unicode em dash character U+2014 in repository prose, code comments, prompts, UI copy, or social copy. Use a period, comma, colon, semicolon, or parentheses instead. Preserve U+2014 only inside immutable raw evidence or an exact source quotation where changing it would misquote the author.
- File a defect found outside the produce loop with `uv run --locked mag finding file <edition-id> <piece-id> --note "..."`, never by pasting it into a writer's prompt. The finding is stored beside the production records, the piece stops counting as settled, its next writer brief carries it alongside the judges' findings and the draft it complains about, and a round that passes marks it addressed. `mag finding list <edition-id>` shows what is outstanding, and `mag status` blocks the production checkpoint while anything is open. Pasting a finding into an agent prompt leaves no record that the instruction was ever given and is the improvised orchestration the loop exists to replace.
- Never write CommonMark footnote syntax (`[^1]`) in a manuscript. This publication renders CommonMark with no footnote extension, so a marker is typeset literally on the page; validation refuses it by name and produce reports it as a per-piece gate. Fold the note into its sentence or into a parenthetical. Supporting real footnotes would need a document-tree node, every adapter taught to place it, and a page design nobody has made.
- An article with an illustrated opener has a hard limit on its *first paragraph*: it is set on the opener page beside the art and the title, it does not wrap to the next page, and the build refuses the edition when it will not fit. The limit depends on how many lines that article's title and byline take, so it is measured per article and stated in the generated writer brief as "Opening paragraph budget". It does not vary by `opener_variant`, which no layout code reads. The limit is a count of typeset lines and nothing else; the character figure beside it is a floor, low enough that prose of that length always fits, and not the real edge. Test a candidate paragraph with `printf '%s' "..." | uv run --locked mag fit <edition-id> --opener <article-id>`, which prints the lines it would set as and exits 1 when it overruns. Never reproduce the wrapping by hand, and never treat the character figure as the thing being enforced.
- Every fenced code block in a manuscript must appear as a contiguous run of lines inside one of the article's committed source extractions. `src/magazine/code_blocks.py` enforces this during validation and it is the only deterministic content check left on a manuscript; reproduce a block character for character from the extraction or drop it whole.
- Keep the reusable Orwell-based writing method in `docs/WRITING_RULES.md`. It is the house method for every artifact the magazine publishes: source articles in all content modes, explainers, opening editorials, captions, and social posts through `docs/SOCIAL_WRITING.md`. Editor-written text follows it directly; in `faithful_edit` and `faithful_synthesis` it governs only the editor's own sentences, never the source author's voice.
- An opening editorial develops a distinct unifying idea, set of ideas, or emergent narrative across the edition. It must not summarize the articles one by one or become a prose table of contents.
- Social drafts must be concise, direct, source-linked, and approved by a human before publication.
- A source is not captured until its raw evidence bundle is committed under `library/sources/<source-id>/raw/<bundle-sha256>/`. Archive before queueing; never rely on a live URL as the durable copy.
- Raw bundles may contain page responses, rendered text, images, or sanitized browser exports. Never commit cookies, credentials, authorization headers, browser profiles, or session data.
- Never claim an edition is press-ready without a named printer profile and a passing preflight.
- Cover art contains no baked-in masthead or cover lines. Layout code owns all typography.
- Keep the inside front cover (reader page 2) and inside back cover (the penultimate reader page) completely blank; the imposed inside-cover sheet side must therefore also be blank.
- Treat intake batches as transport only. Every unreleased source belongs to exactly one collecting edition; several editions may collect concurrently, with one explicit intake target.
- Never create a collecting edition merely because the user sends another group of links. Open or select one only through `uv run --locked mag collect <edition-id> --issue-number <number>` or an equally explicit human decision.
- Finish a human-approved collecting edition only with `uv run --locked mag finish <edition-id>`. That command owns its stable id, web and print generation, release transaction, and next collection. `mag release` is the lower-level compatibility seam. Every source record must be queued and represented in a rendered article's `source_ids`; a top-level manifest declaration alone cannot silently postpone material.
- Use UV for every Python operation. Never use `pip`, bare `python`, `python -m venv`, an activated virtualenv, or an ad-hoc dependency directory.
- Generate every language listed in `publication.languages` on every validation, build, and release. English remains the source edition; Spanish translations use educated castellano with restrained Argentine preferences, fall back to Spain Spanish, avoid slang and generic Latin American regionalisms, preserve Markdown block structure, and pin the exact English input hashes.
- Never compute or hand-edit a SHA-256 pin. After changing any English input, refresh the derivable pins with `uv run --locked mag pin <edition-id>` and stage each configured overlay with `uv run --locked mag translate <edition-id> <language>`; translate the placeholder and advisory rows it reports before validating. `mag validate` reports staleness (with the expected digest) but never repins.
- Check page budgets with `uv run --locked mag fit <edition-id>` before authoring the translation for a new article, and again after every manuscript edit. Use `uv run --locked mag measure <edition-id>` when you need spans, caps, last-page lines, or the per-paragraph rag table as JSON. Never run a full build, or reach into the renderer with ad-hoc scripts, just to ask whether a piece fits.
- Run project tools as `uv run --locked <command>`, synchronize with `uv sync --locked`, and change dependencies with `uv add`, `uv remove`, or `uv lock`.
- Commit `pyproject.toml`, `.python-version`, and `uv.lock` whenever their state changes. UV's internal environment must never be managed manually.

## Git checkpoints

- Commit each verified source-intake batch, edition checkpoint, or compiler change as a coherent unit.
- Inspect the staged diff and run the proportionate validation before committing.
- Keep legacy `vault/`, `output/`, temporary files, credentials, and browser-session data out of Git. Source-local `library/sources/*/raw/` bundles are canonical and must be committed.
- Commit structured records, edition briefs, manuscripts, source extractions, templates, tests, and deterministic source code.

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
explicitly locked design decisions. It must inspect every sheet, then reopen
every relevant crop from its exact path at original resolution rather than
judging a resized preview. It must turn locked geometry into explicit
pass/fail observations. For the illustrated opener, this includes confirming
that the orange rectangle begins down and right of the black frame, leaving
white at the top-right and bottom-left corners before the shadow begins. It
must identify page-specific visual defects and avoid changing locked elements.
Fix confirmed defects, rebuild all languages, and repeat until the machine
report passes and the independent critic has no remaining actionable findings.
Then record the decision only through
`uv run --locked mag review record <edition-id>` with the reviewer and result
flags; do not hand-edit the canonical review record.
Recording binds the decision to the PDFs exactly as they sit on disk and
rewrites only the packaged reports in place; it does not rebuild, so record
against the packages you actually inspected; pass `--rebuild` only when the
rebuild-and-compare proof is explicitly wanted. `mag finish` and `mag release` must reject a
missing, stale, or changes-required review.

Every source of every collecting edition needs a committed
`library/sources/<source-id>/extracted.md`, and each article's `edition.yaml`
row must pin `source_body_sha256` to the extraction body of every source it
declares in `source_ids`. Before release, perform the adversarial
manuscript-versus-source audit (`prompts/evidence-review.md`) and record it with
`uv run --locked mag review record <edition-id> --kind evidence`; `mag finish`
and `mag release` reject a missing, stale, or changes-required evidence review.
Evidence staleness is derived per article: when `mag review status` names
drifted articles, re-audit those articles against their extractions, then
re-record with `--articles <id,id>` naming exactly the articles whose audit was
actually repeated; never name an article you did not re-audit. Every other
article keeps its recorded binding and `reviewed_at`.
