---
source_ids:
- what-a-task-costs-on-opus-5-5-3d1eacfa
content_mode: article
label: ARTICLE
---

You don't set out to buy millions of tokens. You set out to finish a task, and the token count is whatever the model needed to get there. Every turn resends the conversation so far, so a model that needs more turns costs more at the same price. Opus 5.5 cuts every price line: input and output 20% below Opus 5, cache reads 60%. Every way to spend fewer tokens can also cost you a finished task, and a retry costs more than those savings. Some numbers here are list prices and some are illustrations built from them, so check the docs and your own math.

## What a task costs

A task in Claude Code is a loop: read the conversation, call a tool, read the result, go round again. Each trip is one request. Four things set the price.

**Turns.** Say a task grows from 20K tokens of context to 120K. At 40 turns the average turn sends about 70K, about 2.8M input tokens in all, though the conversation never passed 120K. At Opus 5.5 list prices ($4 per million input, $20 output, $0.20 cache reads), with 90% from cache, input costs about $1.62. In 25 turns it's about 1.75M tokens and $1.02. The cheapest turn is the one you don't need. A test, a build, or a script the model can run to check its work finds mistakes earlier, and batching tool calls pays the resend fewer times.

**Cache reads.** The same 2.8M tokens cost $11.20 with no cache, $1.62 at 90%, about $0.99 at 96%. No other setting moves input cost this much.

**Output.** On Opus 5.5 an output token costs 100 times a cache read. The 60K output of a typical task costs $1.20, the same as reading 6M tokens from cache. Thinking is billed as output, even when Claude Code shows only a summary. That's why effort moves the bill so much.

**Model.** Each model has its own prices. Cheaper cache reads mostly help long sessions; cheaper output mostly helps reasoning-heavy tasks.

## What changed in Opus 5.5

The read rate falls from a tenth of the input price to a twentieth. On Pro, Max or Team plans, limits go about 25% further than on Opus 5; the extra cut on cache reads is an API price change. In one illustrative session with identical token counts, the cache line falls from $1.00 to $0.40 and the session costs about 31% less. A session that's mostly cache reads can save up to 60% on input; a short, uncached question with a long answer, up to 20%.

Opus 5.5 can also use more tokens on an answer, because it always thinks before it replies. We expect people to get more done on it, but it varies by task. On a well-scoped task both models finish in about the same turns, and the price cut is all you get. The gap should be biggest on open-ended tasks. Long runs now end with a report of what changed, what was found, and what's needed from you, so you rerun less often.

## Effort before model

Opus 5.5 has low, medium, high and xhigh, plus max for a single session. Try **medium** for well-scoped daily work, **high** when medium stalls, **low** for renames and known patterns. Say high adds 20K thinking tokens: $0.40. A ten-turn retry loop at 100K cached context with 10K output costs about the same. So high pays for itself on a task where it saves one retry, and is wasted on one medium would have finished.

The clearest sign you need more effort is a fix that stops at one layer: at medium, a renamed field gets updated in the handler, its tests pass, and the client still sends the old field. A test through the client catches the same bug at medium. A test run costs one turn; more effort adds thinking to every turn. So check whether the model can check its work before you raise effort.

On an API key or subscription, changing effort keeps the cache. On Amazon Bedrock, Google Cloud's Agent Platform or a Claude apps gateway, it clears the cached conversation, so change it at a break.

## Choosing the model

Model choice sets the price of every token, including every subagent that inherits it. Use Opus 5.5 for work you supervise. Move up to Fable 5.1 when the result matters more than the token price: long unsupervised runs, problems with no existing pattern, large changes coordinating many subagents. If high hits the same problem twice, switch. Fable 5.1 lists at $10 input and $50 output, two and a half times Opus 5.5, but its cache reads cost $0.25, only 1.25 times. Switch at a natural break, since the first turn on a new model pays the write price on the whole conversation; /compact first to shrink it.

Move down to Sonnet or Haiku for lookups, not for writing code: search, logs, test output. Set `model: haiku` in a subagent's definition, or `CLAUDE_CODE_SUBAGENT_MODEL` for all of them. A small model that misreads a search result sends the main model after the wrong file, so keep it where mistakes are cheap to spot.

## Prompts written for older models

Old instructions can make Opus 5.5 write more and repeat tool calls. `/claude-api prompt-audit` checks your skills and CLAUDE.md. On one internal support benchmark of 44 tickets, moving from Opus 4.8 to Opus 5.5 at low effort cut cost about 18%; the audit cut a further 9%, to about 25% below the start. It's one benchmark, an example rather than a number to expect.

## Cache and compaction

A cache read costs 5% of fresh input. A write costs 1.25 times input for five minutes, twice for an hour. Subscriptions get an hour; API keys and cloud providers get five minutes by default. At 120K context a five-minute write costs about $0.60 and a read about $0.02, so on an API key a six-minute coffee break turns a $0.02 read into a $0.60 write.

The cache stores a prefix. Expect a write when you pause past its lifetime, connect or disconnect an MCP server, switch models, or compact. Set these up at the start and leave them alone.

Long sessions cost more per turn even with a warm cache: a turn's read is about $0.004 at 20K and $0.03 at 150K. Use /clear between unrelated tasks. Compacting at 150K costs about $0.25 and saves about $0.025 a turn, so it pays for itself within about ten turns. The summary also loses detail, so compact at a break and name what to keep. Keep CLAUDE.md under 200 lines; it loads into every session.

## Measure it yourself

Run /usage at the end of a task. Run the same real task on Opus 5 and Opus 5.5, and do three or four before concluding. Check cache share, output against input, and total input against conversation size; a large multiple means many turns. For a baseline, the costs docs give about $13 per developer per active day, and under $30 for 90% of users. Your own numbers are the ones to trust.
