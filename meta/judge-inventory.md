# Judge inventory — taken 2026-08-06, before removal

The write → judge → rewrite loop was removed from `mag produce` on 2026-08-06
in favor of single-shot verbatim writer prompts (see `prompts/README.md`).
This is the record of what the judge system was when it was removed. Every
file listed here exists in git history at commit
`892401bdd3d6517be8634cc295597df072384024` and earlier.

## What it cost

From the last three full edition-004 runs (`codex:gpt-5.6-luna` for both
writers and judges), out of ~138–139 calls per run:

- judges: 115 calls, 64–68 minutes of model time per run (~83% of calls, ~80% of model time)
- writers: 23–24 calls, 14–16 minutes

The loop drove those writer counts up too: every piece was rewritten up to
twice to satisfy blocking/major findings, and most pieces exhausted their
rounds anyway (`rounds_exhausted` in run summaries), so the extra spend did
not even buy convergence.

## The lenses

Each lens was one prompt file in `prompts/`, run in parallel per piece per
round. "Sources" marks whether the lens saw the source extraction —
source-blindness was enforced by construction (the prompt simply never
contained the source).

| lens | file | ran on | sources | one-question charter |
|---|---|---|---|---|
| worth | worth-review.md | articles | yes | does a reader who reads only this get the source's key ideas, with space spent on what mattered? |
| evidence | evidence-review.md | articles | yes | adversarial fact-checker: is every claim the source's claim, at the source's strength? |
| mechanics | mechanics-review.md | articles + editorial | no | is the English correct as it will be typeset? |
| shape | shape-review.md | articles + editorial | no | is the piece in the right order, does it hold together? |
| craft | craft-review.md | articles + editorial | no | did a person write this, sentence by sentence? |
| teaching | teaching-review.md | in_a_nutshell only | yes | could a reader who didn't know the subject now explain it to someone else? |
| edition | edition-review.md | whole edition, once | no | managing editor: do these pieces belong between the same covers, in this order? |

## The loop mechanics

- Findings came back as YAML (`findings:` list with `severity`); only
  `blocking` and `major` fed the rewrite loop, everything else was advisory.
- `MAX_REWRITE_ROUNDS = 2`: write, judge, rewrite, judge, rewrite, judge —
  then `clean` or `rounds_exhausted`.
- Rewrites carried a "findings from earlier rounds, already addressed"
  section so round 3 wouldn't undo round 2's repairs (anti-churn).
- Writer replies were wrapped in `<manuscript>` tags with a
  `<!-- SCRATCH -->` marker separating working notes, both parsed out by the
  pipeline.

## Why it went

Fran's side-by-side experiments (2026-08-06, edition-004 material): short
verbatim style-mix prompts against opus 5 / gpt sol with no judges at all
produced clearly better prose than the full prompt-pack + five-lens loop.
The judges also had a track record of missing what mattered — the edition-4
fabricated quote shipped through a passing review — while burning 4/5 of
every run's model time.

## What did NOT go

- `prompts/translation-es.md`, `prompts/cover-art-candidates.md` — untouched.
- The render critic (`src/magazine/render_critic.py`) — layout review, not
  writing review.
- `tools/produce.py` (the legacy Python pipeline) still references the
  deleted review prompts and the old writer prompts; it was already stale
  (no backends, old run layout) and now fails if run. Delete or ignore.
