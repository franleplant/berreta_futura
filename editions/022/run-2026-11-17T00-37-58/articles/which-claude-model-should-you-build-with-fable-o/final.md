---
source_ids:
- which-claude-model-should-you-build-with-fable-o-5c11131c
content_mode: article
label: ARTICLE
---

Start most work on Opus 5.5 at `medium`, its default effort. It's the default model in Claude Code, and it costs half as much per input and output token as Fable 5.2. Move down to Sonnet 5.5 for well-scoped work, and to Haiku 5.5 for classification, routing, extraction and subagent side tasks. Move up to Fable 5.2 for the hardest technical projects in coding, finance and the sciences, for long unattended runs, or when Opus 5.5 at `high` still falls short. Before you change models, try changing effort.

## Effort first

Effort is a finer dial than the model, for both cost and capability. Higher effort helps when the model needs to think longer, call more tools or check its own work, but it adds latency. It won't give a model knowledge or skill it doesn't have; for that, you still need a bigger model. Past `high`, one more effort level can cost as much as a bigger model, so if you're past `high`, test the next model up at a lower effort instead.

A clear spec doesn't by itself mean Sonnet. A migration or a performance optimization can have clear specs and still warrant Opus 5.5, or Fable 5.2 for a major one.

## By task

| Task | Start with | Effort |
| --- | --- | --- |
| Everyday engineering, debugging, multi-PR features | Opus 5.5 | `medium`, then `high` |
| Classification, routing, tagging, high-volume extraction | Haiku 5.5 | `medium` |
| Subagents that search, read logs or summarize | Haiku 5.5 or Sonnet 5.5 | default |
| Chat and interactive sessions | Sonnet 5.5 (Haiku 5.5 for simple chat at volume) | `low` or `medium` |
| Bug fixes, feature iteration, spec-driven work | Sonnet 5.5 | `medium`, then `high` |
| Documents, slides, spreadsheets | Sonnet 5.5 (Opus 5.5 for a complex financial model or a large pile of sources) | `high` (`medium` in Claude Code) |
| Repeated agent tasks: investigation, review, drafting | Sonnet 5.5 | `medium` |
| Computer use and vision-heavy workflows | Opus 5.5 | `medium` |
| Major refactors, architecture, leading many subagents | Fable 5.2 | `medium`, then `high` |
| Deep research, scientific or quantitative analysis | Fable 5.2 | `medium`, then `high` |
| Not sure yet | Opus 5.5 | `medium` |

## Side by side

| | Haiku 5.5 | Sonnet 5.5 | Opus 5.5 | Fable 5.2 |
| --- | --- | --- | --- | --- |
| Input / output per M tokens | $0.10 / $0.50 up to 100K prompt; $0.50 / $2.50 over | $2 / $10 | $4 / $20 | $8 / $40 |
| Cache read per M | $0.01 / $0.05 | $0.10 | $0.20 | $0.20 |
| Latency | Fastest | Fast | Moderate | Moderate |
| API default effort | `medium` | `high` | `medium` | `high` |
| Fast mode | No | No | Yes | Yes |

All four have a 1M-token context window and 128K max output. Opus 5.5 and Fable 5.2 always think; Sonnet 5.5 and Haiku 5.5 think by default.

## Cost per finished task

A higher price per token doesn't always mean a higher cost per task, or a better result. On our Terminal-Bench 3.0 runs, the previous Fable, 5.1, at `max` scored 58.0%; Opus 5.5 at `high` scored 58.9% with half the tokens. On the hardest work the gap can close the other way: on FrontierCode 2.0, Fable 5.2 at `high` scored about level with Opus 5.5 at `max` (45.3% vs. 45.5%) for roughly half the cost per task. So before you raise Opus 5.5 past `high` on a hard task, test Fable 5.2.

Small models generally do well on high-volume work with checkable outputs and are less suited to long agentic loops.

Price the hardest tasks in your set, not just the typical ones. On one 20-problem search benchmark, two problems carried 43% of the spend.

## Latency against accuracy

For replies a person waits on, start Sonnet 5.5 at `low` or `medium`. On SWE-bench Pro, against Opus 5.5 at `high`:

- `medium` scored about 2.5 points lower for about 70% of the cost.
- `low` scored about 8 points lower for about a third of the cost.
- `xhigh` scored about 1.4 points higher for 2.5 times the cost.

Self-verification is often cheaper and faster than more effort. When a model isn't good enough, first make sure it can check its own work with a test, a build or a script; then raise effort one level; then move up a model, at a lower effort than before. If outcomes can be checked automatically, run everything low and re-run only the failures high. On the same subset, Opus 5.5 at `low` with failures re-run at `high` passed about 97% of tasks for about $0.17 each, against 95.3% for $0.29 with everything at `high`.

If you need speed without giving up capability, Opus 5.5 and Fable 5.2 offer fast mode at premium pricing.

## Context against cost

Large context costs you on every turn, because each turn resends it, though on long runs most of that input bills as cache reads. A turn's cache read on Opus 5.5 costs about $0.03 at 150K tokens and about $0.004 at 20K. Since Fable 5.2 and Opus 5.5 charge the same $0.20 for cache reads, on a long, cache-heavy run the gap between them comes down to uncached input and output. Keep the expensive model's context for decisions, and let cheaper subagents do the verbose reading.

## Mixing models

**Switch at a natural break.** The prompt cache belongs to the model that wrote it, so the first turn on a new model pays the cache-write price on the whole conversation. Run `/compact` first, or start fresh with a short written plan; on the API, open with a summary.

**Put subagents on smaller models.** A subagent bills at its own model's rates. Set `model:` in its definition, or `CLAUDE_CODE_SUBAGENT_MODEL` for the default:

```markdown
---
name: log-reader
description: Reads test output and logs, and reports each failing case. Use after a test run.
tools: Read, Grep, Glob, Bash
model: haiku
---

Read the logs you're given. For each failure, report the file, the test name and the first error line. Don't edit any files.
```

Give small models work where a mistake is cheap to spot: finding files, running tests, reading logs. Keep code edits and judgment calls on the main model. When a small model misreads a search result, the main model opens the wrong file and spends tokens on it.

**Delegate bulk work.** For work bigger than one context window, a top-tier lead can split the task across many cheaper workers. On a defect-search benchmark over about 22 million tokens of code, an Opus 5.5 lead over up to 25 Sonnet 5.5 workers cost about a third less than Opus 5.5 alone at default effort, and scored about the same. Skip it for a chain of dependent steps or work that fits one context window, where planning and merging cost more than they save.

## Measure on your own work

Published results give you a starting model. Then:

1. Take a sample of real tasks, each with an outcome check.
2. Run each candidate at two or three effort levels, in separate sessions, recording cost per completed task from `usage`.
3. Plot score against spend. Keep a multi-model setup only if it beats every single-model point.
4. Run the winner in shadow on real traffic before cutting over.

For a quick check in Claude Code, run one backlog task on two models with `/model` and compare `/usage`.
