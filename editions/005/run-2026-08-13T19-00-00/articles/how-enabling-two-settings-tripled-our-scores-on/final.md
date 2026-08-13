---
source_ids:
- how-enabling-two-settings-tripled-our-scores-on--265c6a01
content_mode: article
label: ARTICLE
---

GPT‑5.6 Sol scored 7.8% on ARC-AGI-3, a benchmark of 2D puzzle games, and GPT‑5.5 scored 0.4%. That puzzled us, so we looked at the attempts. Much of the model's confusion turned out to come not from the model but from the harness: after each action all private reasoning was discarded, and a rolling window dropped the oldest history as it grew. We rebuilt the harness on our Responses API with reasoning retained and compaction enabled. On the public set the score went from 13.3% to 38.3%, with 6x fewer output tokens.

## What the harness was doing

ARC-AGI-3 asks agents to explore unfamiliar 2D games and infer how they work without instructions. Its harness is intentionally generic, no tools, no special features. ARC's reasoning was that a simple harness makes model shortcomings more visible and comparisons more fair. Commercial developers optimize for each model's features and quirks.

Two of those generic choices mattered. Discarding reasoning meant the model was asked to figure out the game anew with each action; it could still see its past moves and brief notes, but not the plans and insights that led to them. Rolling truncation, which drops the oldest messages once context exceeds 175,000 characters, meant it was losing memory of the past actions too. Together these help explain why the model struggled to learn over time.

**Agents do best when they remember what they've done**

Our models are trained to think in private reasoning messages that stay in the conversation history, and when a conversation grows too long we summarize it and continue. That is how they are deployed in ChatGPT and Codex. Passing the previous response ID retains reasoning across tool calls and turns.

With reasoning retained, the model spent less time thinking before each action and was better at learning over time and holding a coherent strategy. Replacing truncation with compaction preserved what it had learned across longer runs and scored higher on fewer output tokens; truncation also leaves the model working with a fuller context window for much of the task, which can slightly impair performance. Our implementation caps at 175,000 tokens rather than characters, which works out similar, since most of the text is action grids that our tokenizer handles at roughly 1:1.

Scores are Relative Human Action Efficiency, a comparison against a human baseline. From the official gameplay logs, we estimate the average human tester scored 48%. Models are not told how they will be scored and cannot see it as they play; an action returns only a text representation of the frame and the level.

## Recommendations

Evals rarely measure models in isolation. They also measure a bundle of less visible choices about API settings, harness design, and prompting. This isn't the first time low public scores led us to a generic harness that dropped reasoning messages.

If you're an API developer maximizing performance, use the settings we deploy ourselves: the Responses API rather than legacy Chat Completions, retained reasoning, compaction. If you're comparing models, prefer evals that use them, since they best match real use in ChatGPT and Codex.

We're grateful to ARC for their years of work on AGI evaluation, and for the analysis that prompted this look. The public games are at arcprize.org/tasks if you want to test your own mettle.
