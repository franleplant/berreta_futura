---
source_ids:
- agents-are-users-so-your-software-needs-evals-c19318be
content_mode: article
label: ARTICLE
---

Agents are now users of software, doing work on people's behalf. They go through the same funnel a human does: *Discovery*, *Selection*, *Access*, and *Success*. We focus on *Success*: whether the agent completes the user's task correctly. That's harder to check than it sounds. An agent can place a "successful" order for a hot latte when the user asked for an iced one. The request worked, so the logs look fine. And because LLM outputs vary between runs, one good manual test can't tell you whether a fix worked. An eval is a test you run many times and score. To build one, you set a goal, pick metrics by what a failure costs your user, write a few tasks with verifiers, run every variant several times, and read the traces.

## The agentic testing pyramid

We group agentic tests by how many LLM calls they typically need: deterministic tests (0), one-turn evals (1), and E2E evals (2+ across a whole task). That count has turned out to be a great proxy for the effort to build them, the time they take to run, and their cost. As in the practical test pyramid, the cheap and fast tests should make up the bulk of your suite. Start with the problem you want to catch and pick the lowest tier that can catch it.

For *Success*, that's the top. A one-turn eval checks a single decision, like which command the agent runs first. But each step can look reasonable on its own, and the agent can still get the wrong outcome. An E2E eval lets the agent work through the whole task in an environment, then checks whether the final result meets the user's requirements. SWE-bench and Terminal-Bench are E2E evals.

Say you own SF Beans, an API for ordering coffee in San Francisco, and you're shipping a CLI, `sfbeans`. A typical request:

> Get me a large iced latte with whole milk, ready for pickup by 9:00, under $8 including tip. I'm in the Mission.

At 8:30am, Fog City Roasters has no iced drinks, 24th St Beans costs $9.27 after tax and tip, Dolores Drip's earliest pickup is 9:20, and Valencia Grind, at $7.42 and ready at 8:50, meets all three constraints.

## Building an end-to-end eval

We use Harbor, an open-source framework from the creators of Terminal-Bench that runs agents in containers, checks results, and records their actions. A *variant* is the agent setup: model, prompt, tools, memory, and skills. A *trial* is one attempt by one variant at one task.

### Set a goal

With agents, the surface you'd need to cover is everything an LLM might do with your product, and even figuring out where that ends is hard. Start with one outcome your users care about, narrow enough for a handful of tasks. You'll usually find it in observability, customers, or the roadmap.

For `sfbeans`, most agent traffic comes from Claude Code and Codex, and the top support ticket is "my agent ordered the wrong drink." So the goal is to increase the success rate on ordering the exact drink the user asked for. Done when both agents get the order right in every trial.

### Define metrics

Success rate is the share of trials that pass. Pass@k is the chance that at least one of k trials passes ("can the agent do this at all?"). Pass^k is the chance that all k pass ("can I rely on it every time?"). Steps, time, and cost are measured on successful trials only.

Five trials of Claude Code + Opus 5.5 on the iced latte could look like this: three passes, one fail that skipped `quote` and ordered at 24th St for $9.27, and one that ordered at Dolores, ready at 9:20. That's a 60% success rate. Pass@5 is about 99%. Pass^5 is about 8%: a user who orders this every weekday gets at least one wrong coffee in 92% of weeks. Both numbers are right; they answer different questions. Cost is $0.56 per successful trial, but $0.78 per success once you count the failed trials you paid for too.

Which metric leads depends on what a failure costs. Someone ordering their morning coffee doesn't get a retry, so `sfbeans` optimizes for pass^5. A coding agent with a test suite can lead with pass@k; an email draft the user reviews, with success rate. Overall averages can hide a task that fails frequently, so inspect results per task. And with only five trials, 100% means "no failures seen yet," not "never fails."

### Design the task set

A good set covers the common case, the edge cases that trip agents up, and at least one request where the right move is not to act. Each task needs an instruction, an environment with the same starting state for every trial, a verifier that checks the final state (ideally scored per constraint), and, optionally, a known-good solution.

We wrote four: `iced-latte-mission`, `usual-unavailable`, `team-order` (6 drinks, $45 total, one pickup spot), and `impossible-request`, where nothing fits and the right move is to tell the user.

The instruction names the `sfbeans` CLI, skipping *Discovery* and *Selection* to keep the eval on *Success*, and says it's 8:30am. The environment runs the real CLI against seeded cafes and a frozen clock. To keep the demo simple, `cafes.json` lives inside the agent's environment. In a real eval, protect the seed data and verifier code: agents can attempt to reward hack, for example by editing the inventory or writing `orders.json` directly.

The verifier scores each constraint separately (one order, right drink, on time, on budget) and sets `reward` to 1 only if all of them pass, so a failed trial shows exactly what broke. Run the known-good solution before any real agent to prove the task works.

We run trials concurrently through Harbor's Vercel integration, which we built upstream: Claude Code and Codex with two models each, four tasks, five attempts, 80 trials.

### Analyze traces

Scores tell you how often your agents fail; traces tell you why. Read the failures, and some passes too, since a pass only means the verifier was satisfied.

Our baseline, with each metric computed per task and averaged across the four (numbers are illustrative):

| Variant | Success | Pass^5 | Avg steps (successful) | Cost per success |
| --- | --- | --- | --- | --- |
| Claude Code + Opus 5.5 | 85% | 60% | 9 | $0.61 |
| Claude Code + Sonnet 5.5 | 75% | 52% | 11 | $0.27 |
| Codex + GPT-6 Astra | 80% | 43% | 8 | $0.48 |
| Codex + GPT-6.1 Sol | 65% | 14% | 13 | $0.22 |

On pass^5, even the best variant is far from reliable, but the score doesn't say what to fix. In trial 2, the verifier shows right drink, on time, over budget. The trajectory shows the agent saw $7.50 on the menu and went straight to `order`, with no `quote`. Trial 1, same variant, quoted three cafes and ordered at Valencia. So the CLI can get the order right, but the agent doesn't reliably check the total before spending the user's money. If that pattern keeps showing up, there's something specific to fix: make the total harder to miss, or add a `--max-total` flag so `order` refuses anything over budget. That's more useful than "Opus scored 85%."

The traces also exposed problems with the eval itself:

- The first run scored 0% on every variant. The agents didn't know `sfbeans` existed: a *Discovery* failure, fixed by naming the tool in the instruction.
- Codex kept looking for `sfbeans` as a connected tool and never ran it in the shell: an *Access* problem, not a *Success* one.
- Codex passed `impossible-request` almost every time, but 9 of 10 passes were the agent giving up without looking. We tightened the verifier to check, through a command log the agent can't write to, that it searched first.

## Iterate

Apply the fix the traces point to, rerun the same job, and compare against the baseline: check that it reduces the targeted failures without introducing new ones. Rerun the eval on every release to catch regressions. Expect to add harder tasks over time. As models and your product improve, evals saturate. A saturated eval still catches regressions, but it can't tell you what to improve next.
