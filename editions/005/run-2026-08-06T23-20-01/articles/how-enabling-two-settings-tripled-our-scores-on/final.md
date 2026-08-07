---
source_ids:
- how-enabling-two-settings-tripled-our-scores-on--265c6a01
content_mode: article
label: ARTICLE
---

GPT‑5.6 Sol scored 7.8% on ARC‑AGI‑3, a benchmark of unfamiliar 2D puzzle games. We suspected the model, then looked at the harness. It threw away the model's private reasoning after every action and discarded old history once the context passed 175,000 characters. Turning on two Responses API settings — retained reasoning and compaction — took the public‑set score from 13.3% to 38.3% and cut output tokens sixfold. The average human tester, by our estimate from official logs, scores 48%.

## The benchmark

Agents explore games they have never seen and must infer the rules unaided. They are not told how they are scored and cannot see their score; each action returns a text frame and a level number. The metric, Relative Human Action Efficiency, compares them to a human baseline. ARC built the harness plainly on purpose: no tools, no per‑model tuning, on the view that a bare harness exposes weakness and makes comparison fair. Twenty‑five demo games are public at arcprize.org/tasks.

## What was wrong

Two things, both invisible in the score.

Reasoning was dropped after each action. The model kept a record of its moves and short notes, but not the plans that produced them — a prisoner waking each morning in the same maze, holding a list of turns he no longer understands.

Truncation was rolling. As history grew, the oldest actions vanished. So it could not remember its thinking, and was losing its actions too. Between them, they account for a model that dwelt long on each move and learned nothing across a run.

## What we changed

Our models are trained to think in private messages that stay in the history, and to summarize that history when it grows too long. That is how they run in ChatGPT and Codex. We rebuilt the harness to match: with the Responses API, passing the previous response ID retains reasoning across turns and tool calls.

Two effects followed. Sol thought less before each action, having no need to reconstruct the game from nothing. And it held a strategy across many moves instead of a few.

Compaction replaced truncation. Truncation loses observations outright and keeps the model working near a full window, which dulls it slightly. Compaction preserved what each game had taught, over longer runs, for fewer tokens. Our version caps at 175,000 tokens rather than characters; the two are close here, since almost all the text is action grids and our tokenizer takes them near 1:1.

The combined result is roughly triple the score at a sixth of the output.

## Recommendations

- Use the Responses API, not the legacy Chat Completions API.
- Retain reasoning.
- Use compaction.

When comparing models, prefer evals configured this way; they match how the models are actually deployed. This is not the first low public score we have traced to a generic runner that discarded reasoning. Our thanks to ARC, whose own analysis prompted us to look.
