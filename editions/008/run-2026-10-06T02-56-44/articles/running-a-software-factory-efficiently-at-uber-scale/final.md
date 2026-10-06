---
source_ids:
- running-a-software-factory-efficiently-at-uber-s-36ff06c6
content_mode: article
label: ARTICLE
---

AI tools are now in every phase of software development at Uber. More than 70% of pull requests are attributed to local or cloud agents, and a growing share of sessions aren't started by humans but by managed agents. From February to August 2026, weekly active users grew 7x and weekly agentic requests 9.4x, while total AI spend has relatively stabilized since April. With one model held fixed from February to July, cost per 1,000 requests is down almost 34% from its peak, and cost per session is down 52% from its June peak (session data starts at the end of May). We got there by eliminating wasted tokens, not by relying on lower prices or downgrading tools. The core strategic shift is from interactive workflows to managed agents: a fleet of specialized agents, each with its own benchmark and Pareto-efficient model, is inherently more cost-effective and scalable than optimizing terminal sessions across thousands of engineers.

## The cost equation

Total spend = users × sessions/user × turns/session × requests/turn × tokens/request × price/token.

The first two terms are adoption and engagement, which we want to keep growing. The three middle terms are the work the agent does on its own behalf, on top of what the engineer asked for. Most of our effort goes there.

We track this weekly and monthly. Two views matter most: a driver decomposition that explains each cost change by adoption, engagement, input workload, and output workload, "with nothing left in an unexplained residual"; and, for each managed agent, cost per unit of outcome (per merged PR, per review, per alert) beside a quality signal such as revert rate, F1, or MTTR.

Our pricing figures come from public information. The reductions are unique to our environment, and your mileage may vary; we hold that the method, benchmarking real work and optimizing for accuracy and cost, applies anywhere.

## Price per token

The vendor sets the price. We pick the model. For every managed agent we build a benchmark from its real work, run it on a harness that serves any model, frontier or open-weight, behind one interface, and move to whatever is Pareto optimal in cost per completed task, output quality, and reliability. Then we keep moving; the frontier shifts every few weeks.

uReview, which reviews all our pull requests, is benchmarked on real PRs with known bugs, graded easy, medium, and hard. Switching models improved its F1 while dramatically reducing cost per PR.

In interactive use, the subagent default has proven the most impactful lever. Subagents do well-defined tasks that often don't need frontier reasoning, so they default to a weaker, cheaper model, with manual overrides. The primary model decomposes the task and evaluates the work.

## Tokens per request

Every turn re-sends the whole history, so any saving compounds across the session.

- **Defaults.** Compaction triggers at 400K tokens even on 1M-context models. Reasoning effort defaults to Medium, because output tokens are billed at multiples of input.
- **Caching.** Cache reads cost 0.1x the input rate; writes cost 1.25x for a 5-minute TTL and 2x for 1 hour. Engineers often leave sessions idle for more than 5 minutes, so interactive sessions moved to 1 hour. Subagents keep 5 minutes.
- **MCP through the shell.** With over 100 tools installed, standard MCP added roughly 50K–70K tokens of schema to the initial prompt, re-sent on every turn. All 1K+ tools on our gateway are now projected as CLI commands resolved at call time, and tool search loads the rest on demand.
- **Code-mode.** The model writes one script that batches calls and runs the polling loop in a subprocess; only the summary comes back. Across five identical SQL queries, `SELECT 1` fell from 903 tokens to 402, a `GROUP BY LIMIT 20` from 1,600 to 457, and a `SELECT *` on a wide table from 1,431,594 to 900. Even tiny results save more than 50%, from removed overhead rather than skipped payloads; bulk workflows save more than 90%.
- **SaaS MCPs.** One workspace suite ships 49 tools and about 22K tokens of schema. We route vendor servers through the same gateway, as CLIs, with dedicated skills for common workflows.

## Requests per turn

An ungrounded agent fails slowly rather than cheaply. Our AI Context Graph holds 24 million nodes and 80 million edges from over 30 internal systems, and any agent can query it in natural language. Given the same prompt and model, the grounded agent found the table used by over 50 analysts and answered correctly in 38 seconds. The ungrounded one spent 20 minutes, spawned 2 subagents, hit 3 errors, and wrongly concluded the dataset was unqueryable.

## Visibility

We avoid strict caps. A live cost counter sits in the harness status line; one shared spend tier covers all interactive harnesses; Slack nudges arrive at 50, 80, and 100% of expected spend; managers can approve upgrades quickly. A session analysis dashboard, with no setup, flags 16 anti-patterns with their cost and a fix: simple sessions on Opus that Sonnet could handle, 40KB MCP payloads lingering in context, expired caches after long breaks, 100,000 tokens of instructions loaded before the first prompt.

## What's next

We're growing the fleet of managed agents, each with outcome metrics, a benchmark, and a Pareto-optimal model; expanding benchmarks toward dynamic model routing; opening the context graph to more agents; turning batch session analysis into real-time guidance; and working on recording papercuts from skill executions to auto-generate skill updates.
