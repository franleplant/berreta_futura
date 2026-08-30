---
source_ids:
- running-a-software-factory-efficiently-at-uber-s-36ff06c6
content_mode: article
label: ARTICLE
---

AI tools sit in every phase of software development here. More than 70% of pull requests are attributed to local or cloud agents, and a growing share of sessions aren't started by humans at all. From February to mid-August 2026, weekly active users grew 7x and weekly agentic requests 9.4x, while total spend has relatively stabilized since April. Holding one model fixed from February to July, cost per 1,000 model requests is down almost 34% from its peak, and cost per session down 52% from its June peak. We got there by splitting spend into six terms that multiply, growing the first two and squeezing the middle three: the work the agent does on its own behalf, on top of the request an engineer actually made.

### The equation

Total spend is users, times sessions per user, times turns per session, times requests per turn, times tokens per request, times price per token. The first two are adoption and engagement, which we want to keep growing. The three in the middle are where most of our effort goes.

Our specific reductions are unique to our environment, and yours may differ with your codebase, team size, and workflows. The pricing here is public information, and the gains come from routing our own workloads more intelligently inside standard tier pricing. The method, benchmarking real work and optimizing for accuracy and cost, travels anywhere.

### Price per token

The vendor sets the price. We pick which model runs which workload, and we pick the one that is Pareto efficient for it: cost per completed task, output quality, reliability. Build a benchmark from the agent's real work, run it on a harness that serves any model behind one interface, move to whatever is Pareto optimal, and keep moving. The frontier shifts every few weeks.

uReview, which reviews all our pull requests, has a benchmark built from real PRs with known bugs graded easy, medium, and hard. We score precision, recall, and F1 against those bugs, plus cost per review, latency, timeouts, and noise. Switching models improved F1 while dramatically reducing cost per PR.

In interactive use the unit price is fixed, but the distribution across models is not. The subagent default has proven the most impactful lever, and its significance keeps growing. Subagents do well-defined tasks with specified inputs that often don't need frontier reasoning, so we default them to a weaker, cheaper model and allow overrides. The primary model decomposes and evaluates; subagents execute.

### Tokens per request

Every turn re-sends the whole conversation, the project context, and the tool results. Anything that shrinks the payload compounds.

We compact at 400K tokens even on million-token models, and default reasoning effort to Medium, since output and reasoning tokens bill at multiples of input. Cache reads cost 0.1x standard input; a 5-minute write costs 1.25x, an hour costs 2x. Engineers leave sessions idle for more than five minutes, and those gaps were invalidating the prefix and forcing full-price rebuilds, so interactive sessions moved to the hour. Subagents, short-lived, keep the five minutes.

Then the schemas. Standard MCP loads every tool definition into every session whether or not it's ever called; with over 100 tools that was roughly 50K to 70K tokens of overhead, re-sent each turn. Two vendors ship 34 and 46 tools, a workspace suite bundles 49 into one server at about 22K tokens. Load two or three and the agent carries more schema than the file it's editing before anyone types a prompt. So all 1,000-plus tools behind our gateway are projected as CLI commands the model resolves at call time, and tool search loads only what a session needs.

Code-mode goes further: as shell commands, actions batch into one script. A single SQL query under MCP means a request, two to five status polls, and a retrieval, each landing in context. In a subprocess, only the summary comes back. Five identical queries run both ways: 903 tokens against 402, 954 against 403, 1,600 against 457. A wide `SELECT *` came to 1,431,594 tokens through tool use and 900 through code-mode. Even on result sets far below any size limit the savings pass 50%, and they come from removing schema loading, polling, and step-by-step reasoning, not from dodging large payloads. Bulk work compounds past 90%.

### Requests per turn

An ungrounded agent fails slowly rather than cheaply. Across hundreds of millions of lines and thousands of tables, agents spend most of their turns finding things rather than writing code, so we built the AI Context Graph: 24 million nodes and 80 million edges across 86 nodes and 117 edge types, drawing on more than 30 internal systems, from services and teams to incidents, PRs, design docs, deployments, datasets, and historical queries. Any agent can ask it in natural language.

Same prompt, same model, twice. Grounded, it queried historical usage, found the table over 50 analysts use, and answered in 38 seconds. Ungrounded, it spent 20 minutes and 9 seconds reading service code, spawned 2 subagents, hit 3 errors, and concluded the dataset was unqueryable. It was wrong.

### What an engineer sees

We chose nudges over caps. Running session cost stays visible in the status line. One shared tier covers all interactive harnesses, with separate tiers for managed agents, Slack alerts at 50, 80, and 100% of expected spend, and manager sign-off that propagates quickly. A cost dashboard skill reads session traces across local and remote sandboxes and flags 16 distinct anti-patterns with their financial impact and a fix: simple sessions running on Opus that Sonnet could serve, 40KB payloads billed again every turn, caches left to expire over long breaks, 100,000 tokens of instructions and definitions loaded before the user says anything.

### Next

We're growing the fleet of managed agents on the same roadmap each time: target outcome metrics, evaluation benchmarks, a Pareto-optimal model. We're widening benchmark coverage across languages, repositories, and modalities for dynamic routing, opening graph queries to more autonomous agents, moving session analytics from batch detection toward real-time guidance, and building an automated way to collect papercuts from skill executions and generate skill updates from the traces.

Curbing AI coding spend is a tractable engineering problem. We scaled usage 7x and cut unit costs across every metric by removing zero-value tokens, not by buying cheaper units or worse tools. The strategic shift is from interactive workflows to fully managed agents, where we control routing, harness, and spend. A fleet of specialized agents, each with its own benchmark and its own efficient model, is easier to optimize than thousands of terminal sessions.
