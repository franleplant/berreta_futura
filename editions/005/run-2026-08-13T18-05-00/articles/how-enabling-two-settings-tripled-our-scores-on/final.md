---
source_ids:
- how-enabling-two-settings-tripled-our-scores-on--265c6a01
content_mode: article
label: ARTICLE
---

GPT‑5.6 Sol scored 13.3% on the ARC-AGI-3 public set under the benchmark's official harness. We reran it with two settings we already use in ChatGPT and Codex, retained reasoning and compaction, and it scored 38.3% while using 6x fewer output tokens. The official harness threw away the model's private thinking after every action and dropped the oldest messages once context filled. Sol was not playing the game badly; it was meeting the game again, every turn. Based on official gameplay logs, we estimate the average human tester scored 48%.

## The puzzle before the puzzle

The low scores puzzled us: 7.8% for Sol, 0.4% for GPT‑5.5, from models that have solved longstanding open problems in mathematics like the cycle double cover conjecture and beaten Pokémon FireRed with a vision-only harness, Slay the Spire with Codex computer use, and the first stages of Baba Is You.

ARC-AGI-3 asks agents to explore unfamiliar 2D games and infer how they work without instructions. Its harness is generic by design. ARC's reasoning was that a simple harness makes model shortcomings more visible and comparisons more fair. Commercial developers do the opposite and tune the harness to the model.

## Two ways to lose the thread

Watching the attempts, the model did not appear too bright. It dwelled on each action and struggled to progress. Two harness settings explained much of that. First, all private reasoning was discarded after each action, so Sol could see a record of past moves and brief notes but not the plans, insights, or thoughts behind them. Second, a rolling truncation window discarded the oldest messages once the conversation exceeded 175,000 characters, so it was losing its actions as well as its thinking.

## What the settings changed

Our models think in private reasoning messages before they reply or call tools, and those messages stay in the history; when a conversation grows too long, we summarize it and continue. That is how they are trained and how they run in our products. So we implemented the harness with our Responses API, where passing the previous response ID retains reasoning across tool calls and turns.

Two things followed. Sol spent less time thinking before each action, having no need to interpret the game from scratch, and it learned over time, holding coherent strategies.

Then we replaced rolling truncation with compaction. Truncation costs twice: earlier observations and actions are lost, and the model spends much of the task with a fuller context window, which can slightly impair performance. With compaction, Sol preserved what it had learned across longer runs and scored higher on fewer output tokens. Together the two settings gave GPT‑5.6 Sol (max) roughly 3x the score with 6x fewer output tokens.

## Recommendations

Evals rarely measure models in isolation. They also measure less visible choices about API settings, harness design, and prompting, and this is not the first time a surprising public score traced back to a generic runner that dropped reasoning messages. To maximize performance, use what we deploy: the Responses API rather than the legacy Chat Completions API, retained reasoning, and compaction. When comparing models, prefer evals that use those settings. We are grateful to ARC, whose own analysis prompted us to look.
