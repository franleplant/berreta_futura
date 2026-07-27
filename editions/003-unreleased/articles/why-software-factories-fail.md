---
source_id: why-software-factories-fail-f53679d7
content_mode: faithful_synthesis
label: FAITHFUL SYNTHESIS
source_body_sha256: d33fdc4b32b52fc15f7182bdcd5745446577528e319f95736b29305f233b1299
---

We're all racing to put AI coding into production, and the prevailing wisdom is we should write more loops. StrongDM wrote about their lights-off software factory where no human reads code and no human writes code. The narrative: you are the bottleneck, the models are good enough, code is free, just ship more stuff. These people are really dang smart, but the most cynical take: another excuse to pump more VC money into the slop cannon.

Meanwhile, companies that have no business having outages due to coding-agent mishaps are, well, having outages due to coding-agent mishaps, and codebases are falling apart faster than they ever have before. Faros AI put out a report: since we all picked up these tools, review quality is way down, tons of PRs merged with no review, incidents and bugs per developer way up. It's correlation, not a verifiable smoking gun, but it feels directionally valid.

People will tell you this is a skill issue: spend more tokens, let go of reading the code. The promise of all that "just token harder" yapping is, succinctly: 10 to 100x faster, high quality, and nobody ever has to do code review. What I'm gonna try to convince you is that no amount of harness engineering or loopsmaxxing can solve what is fundamentally a model-training issue.

An aside: this has nothing to do with vibe coding—the rest of this is aimed at folks solving hard problems in complex codebases, where an agent-built codebase starts to struggle after maybe three to six months.

## A brief history of the software factory

The term traces back to a NATO conference in 1968, the same one that gave us "software engineering." In a typical 2022 factory, right before AI: people decide what to build, it goes in a tracker, someone builds it, a pull request gets automated checks and a human review, it ships, monitoring pages an engineer at 3am, and user complaints feed the tracker. We haven't even hit AI yet, and there are already several loops in this picture.

Now every company and their mother—Ramp, Stripe, WorkOS, Brex—has explained how they built an agent factory that ships on the order of 75% of their code, swapping "someone builds the thing" for "an agent builds the thing." Building drops to minutes or hours; review still takes hours or days, so review is now the bottleneck. You speed review up with agentic code review and regression testing, route incidents and user feedback in, and the job becomes two questions: how much can you stuff into the queue, and how fast can you review what comes out?

## The lights-off software factory

Dan Shapiro coined the term; Simon Willison wrote about StrongDM's implementation: we no longer read the code. That annoying little code review step? No thanks. Drop it, invest in testing, sandboxes, automated review, monitoring, rollout, feedback signals, and the job becomes one question: how much of the ocean do we want to boil? I'm going to posit something potentially controversial: the lights-off factory does not work.

In July 2025 we went full lights-off—background agents for everything small and medium. You find one issue gnarly enough that the agent can't solve it, and you have to go dig into the codebase you stopped reading three months ago—while your site was down, your users were pissed, and you were miserable reading all the slop code you let slip in. The first time, I shook it off: the downside risk was worth the velocity. By the third time, in November, it was easier to rewrite from scratch, and my cofounder spent two weeks plumbing out the patterns by hand.

What I want to get to is this: models can't maintain and improve codebase quality over time, not without a decent amount of human steering. By maintainability I mean the specific thing where it becomes really, really hard to change one part of the codebase without breaking another—Martin Fowler's shotgun surgery.

Surely the models have gotten better since then? Way better at one-off problems and vibe-coding a marketing site; not much better at improving codebase quality, as far as I can tell. I can't prove it; neither can you: there are no good benchmarks for a model's ability to maintain codebase quality. Work with coding agents for a while, though, and you have the vibe: they make things worse over time.

## There's no penalty for bad design

Claude Code went from nothing to something like $9B in revenue in under a year, though great CLI agents—aider, cline, codebuff—predated it with the same tools. The canonically-accepted explanation: Anthropic RL'd the model inside the harness, the first time a lab trained a model against the exact tools it would ship with. Build a harness without owning the weights and you're at a disadvantage to a team that owns both.

Coding-agent RL in sixty seconds: generate agent traces that solve a problem, score them with a verifier, update the weights to make good traces more likely, repeat millions of times. The scoring can be whimsically one-dimensional.

Take SWE-bench Multilingual: fifteen-minute tasks scraped from open-source repos, rewarded one or zero—did you fix the thing, without breaking anything else? In one real fastlane task, the human fix was two lines. The agent patches from a base commit and a bug report; its test-file edits are thrown away (we've caught a model quietly commenting out the failing test); the benchmark's tests go on top and the suite runs. If they pass, we win—but there is no penalty for eroding codebase maintainability. That's how you get try-catches around everything.

Tests give feedback in seconds; that's why RL can run millions of loops. The cost function of bad architecture is measured in weeks, months, maybe years—the first time someone opens a file for a one-line change and realizes the same edit now lives in eleven places. Bad design is the one thing today's benchmarks can't evaluate, and I don't trust benchmark gains to mean models stopped slopping up codebases.

Lots of smart folks are working on this; the hype is outrunning the discipline. SWE-Marathon scores ~400-hour tasks with a compound reward channel; DeepSWE builds tasks that can't already sit in the training set; Frontier Code penalizes tests that don't fail on the pre-patch code. But if a model could reliably tell good code from bad, it might have written the good version to begin with—RL needs a fast oracle, and maintainability doesn't have one. More review agents and tokens raise the floor, not the ceiling; the ceiling is whatever we taught the model in RL. They're the first evals even trying to score maintainability. I still wouldn't bet my codebase on them.

## Turning the lights back on

Maybe a future model just gets this and we can stop. If you want to yolo prompts until GPT-7 ships, be my guest—but bitter lesson be damned, we've got problems to solve now—how we solve them is part II. Stay tuned.
