---
source_ids:
- addressing-the-code-review-bottleneck-9386e979
content_mode: article
label: ARTICLE
---

How many agent PRs are waiting for your review? I'm not going to suggest merging them without a human; that's for a post-AGI world. The goal today is to cut the time each review takes. There are three levers: run rounds of adversarial review with your own agent before a human looks, have agents verify user flows end-to-end, and score every PR's merge risk so reviewers know where to focus. None of this removes the human. It raises trust in agent work and lowers the attention it needs.

## Build your own review agent

Agents should review their own work before a teammate does: a "make it work" pass, then a "make it good" pass. Building the reviewer yourself is easy and valuable. You set the grading criteria your team cares about, and you can tune its accuracy on your own data. As Addy Osmani notes of Anthropic's process, production incidents and reverts are high-signal evidence that something slipped through review, and they can become eval cases.

Review agents often comment on the GitHub PR, but most of that noise doesn't need a human. Keep the agents working together outside the thread, and surface only what needs human input. Our default loop in Warp Factories:

- The implementation agent hands off to the review agent.
- The reviewer lists findings with severity, impact, and a suggested change, and hands anything ambiguous back to a human.
- The implementer fixes what it can.
- The cycle repeats until everything is settled or N turns pass.

Multiple rounds get expensive, so we've been experimenting with a gate that decides whether review is needed. In early benchmarks on our own full-stack systems, we found that restricting multi-round review to larger features is a viable option. We'll share more soon.

Then evaluate the reviewer: the reviews themselves, plus cost per PR, cycle time, and incident rollbacks. An LLM-as-a-judge scores against rubrics, and a self-improvement agent reads those scores to propose improvements.

## Give agents a computer

Would you trust a coworker's PR they never verified on a local build? The same should go for agents. For backends, that means a realistic environment: a staging database, test credentials, access logs. For client apps, it means tools to navigate like a user: the Chrome DevTools MCP and WebMCP for the web, and computer use, which is becoming more common across harnesses, for any kind of client. In Warp Factories, a computer-use subagent drives a virtual desktop and reports back screenshots and recordings.

Those artifacts belong in front of the reviewer, showing the before and after state; we suggest making them a required PR field. Avoid over-verification: one screenshot per distinct flow, and recordings with the dead space cut. Our FFmpeg post-processing can cut clips from minutes to 10-15 seconds in our experience.

## Score the risk

The reviewer then needs the scope of the change and the parts worth closest review. Five criteria:

- **Verification:** test coverage and end-to-end artifacts.
- **Alignment:** does the code follow the issue, or carry drive-by fixes and side effects?
- **Impact:** the blast radius, and whether it touches auth, permissions, or billing; route those by code owner.
- **Rollback cost:** a two-way door, or a one-way door like a destructive schema migration?
- **Error detection:** are errors swallowed, logged, or reported to monitoring? The last is ideal, since agents can see and fix their own mistakes; we relay Sentry alerts to our factory agents.

Our /merge-risk skill scores these. An agent can run it as a last step to strip unaligned changes, add monitoring on new paths, split high-impact work into stacked PRs, avoid sensitive paths when it can, and verify end-to-end.

## Where to start

Add "impact" and "rollback cost" to your PR descriptions. Then layer on a review step, and computer use for deeper verification than e2e tests provide. Engineers should stay involved in how a codebase evolves, but focus on the systems driving the agents instead of reviewing every PR line by line.
