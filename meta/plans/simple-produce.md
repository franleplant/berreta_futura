# Simple produce

Status: **shipped with this commit**. One page, on purpose.

## What it is

One Python file, `tools/produce.py`, that takes sources and spits an edition's
content with internal improvement loops. No engine, no database, no run state:
state lives in memory while it runs, and every completed step is written as a
plain file. If it crashes, rerun it; `--resume` skips pieces whose final
manuscript already exists.

```sh
python3 tools/produce.py plan 005            # propose editions/005-*/plan.yaml (1 model call, human edits it)
python3 tools/produce.py run editions/005-unreleased/plan.yaml
python3 tools/produce.py run plan.yaml --resume runs/005/<ts>   # reuse finished pieces
```

## The loop

For each article, concurrently:

1. **Write** — the content-mode prompt (`faithful-synthesis` / `faithful-edit` /
   `in-a-nutshell`) with `WRITING_RULES`, `WRITING_EXEMPLARS`, and the full
   source extractions inlined. No tools, no file access, one call.
2. **Judge** — the applicable seven-bench lenses in parallel (`worth`,
   `evidence`, `mechanics`, `shape`, `craft`, `teaching` for explainers).
   Source-blind lenses simply never receive the source in their prompt.
3. **Rewrite** — if any `blocking`/`major` finding, one revision call with the
   findings inlined, then re-judge. At most 2 rewrite rounds, then it ships
   with its findings attached for the human to read.

Then once: the opening **editorial** from the accepted articles (same loop,
blind lenses only), and one **edition review** pass, advisory.

## Output

```
runs/<edition>/<UTC-timestamp>/
  plan.yaml                      # what was run
  articles/<id>/draft-1.md  findings-1.yaml  draft-2.md ...  final.md  status.yaml
  editorial/...
  edition-review.yaml
  log.jsonl                      # every call: label, model, seconds, dollars
  summary.md                     # per-piece rounds, open findings, words, totals
```

Sortable by timestamp, greppable, committable. Git is the archive; a run dir is
the release candidate. Images, rendering, and translation stay out of this loop
(the renderer consumes a finished run dir as before).

## What it deliberately does not have

Databases, event logs, leases, attempts, fencing, credentials, revision IDs,
hash pins, promotion, migration, workflow authorities, XState, Loops. A full
run is ~40–60 model calls and should finish in about 10 minutes; the recovery
strategy for every failure is "run it again".

The quality system is the prompts under `prompts/` and `docs/WRITING_RULES.md`
— that is where improvement effort goes. This file's job is only to execute
them in the right order without a human driving.
