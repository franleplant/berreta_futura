---
source_ids:
- why-software-factories-fail-f53679d7
- why-software-factories-fail-turning-the-lights-b-1312d1ad
- why-software-factories-fail-benchmarking-the-new-f1d9c04a
content_mode: faithful_synthesis
label: FAITHFUL SYNTHESIS
---

We're all racing to put AI coding into production, and the prevailing wisdom is that we should write more loops. The lights-off promise is succinct: you are the bottleneck, the models are good enough, code is free, and nobody ever has to read it. Spend more tokens, add automated reviewers, and move 10 to 100 times faster.

Meanwhile, companies are having outages from coding-agent mishaps and, as Matt Pocock put it, codebases are falling apart faster than they ever have before. Faros AI reported lower review quality, more PRs merged without review, and rising incidents and bugs per developer after teams adopted AI coding tools. That report is more of a correlation signal than a verifiable smoking gun, but it feels directionally valid based on what I've seen. This is not about vibe-coding a disposable side project. It is about hard problems in complex codebases, where the cost of a bad decision arrives months later.

No amount of harness engineering or loopsmaxxing can solve what is fundamentally a model-training problem. Models are much better at one-off tasks, but I do not trust them to maintain and improve codebase quality over time without a decent amount of human steering. There are no good benchmarks for that ability.

## Why the lights-off factory fails

Before AI, teams already used loops: decide what to build, put it in a tracker, implement it, review the pull request, ship, monitor, and feed what users discover back into the queue. Agentic factories mostly replace “someone builds the thing” with “an agent builds the thing.” Building falls from days to hours or minutes, while review remains expensive, so review becomes the bottleneck. The lights-off factory removes it and shifts trust to tests, sandboxes, automated review, monitoring, rollout, and user feedback.

We tried that in July 2025: background agents for the small and medium work, no routine code reading. Eventually an issue arrived that the agent could not solve. I had to return to a codebase I had stopped reading three months earlier while the site was down and users were angry. The first time, I decided the velocity justified the risk. By roughly the third time, it was easier to rewrite from scratch; my cofounder spent two weeks plumbing the patterns by hand.

The failure is maintainability: changing one part becomes likely to break another. Tests can report pass or fail in seconds, so reinforcement learning can optimize millions of coding traces against them. The cost of bad architecture appears in weeks, months, maybe even years, when a one-line change must be repeated in eleven places. There is no equally fast, reliable oracle for good design.

## There is no penalty for bad design

A benchmark can ask whether an agent fixed a bug without breaking existing tests. If the suite passes, the patch wins, even when it makes the codebase harder to change. That is how you get try-catches around everything.

Promising evaluations are beginning to use longer tasks, compound rewards, mutation testing, and model-based quality rules. But if a model could reliably judge good code, it might have written the good version to begin with. More tokens and review agents raise the floor; they do not move the ceiling beyond what the model learned to recognize. The frontier is improving; the hype is outrunning the discipline.

## The oracle arrives in checkpoints

That claim about benchmarks was not entirely true. SlopCodeBench reveals requirements checkpoint by checkpoint. The model never sees the whole problem up front; it must evolve its own code while every inherited regression test remains binding. What's cool about this benchmark is that it is unsaturated: at the time of running, the best models available, GPT-5.4 and Opus 4.6, got 11 percent and 17 percent strict pass rates, respectively.

I ran Opus 4.8, Sonnet 5, and Opus 5 through three problems—easy, medium, and hard—seventeen checkpoints in total. They received the same prompts and a fresh context window at each checkpoint. A strict pass meant every new and inherited test passed held-out black-box evaluation.

No model finished any challenge cleanly, even the easy one. Opus 5 cleared four of seventeen checkpoints, or 24 percent; Opus 4.8 and Sonnet 5 each cleared one. Three of Opus 5's passes opened a single problem. It won technically, but nobody bought enough correctness. Obviously this small subset cannot tell us definitively that spending more money will lead to higher pass rates. The big headline is that 24 percent is not much higher than Opus 4.6's 17 percent strict pass rate in the original paper.

The quality measures are repeatable, but I am not sold on linting the slop away. Every model increased verbosity and complexity. Opus 5 wrote five times as many functions as Opus 4.8, though its production-code volume was closer to 1.8 times as large. On duplication, however, Opus 5 is basically flat, 2.41 to 2.64, so if you trust duplication as a golden metric, you could argue that we did get incrementally better in the last three months. Big if though, and most software architecture experts would agree it is not black and white. Most of the 41 metrics did not clearly separate the models; no single metric is established as a proxy for ease of change.

## Can the next model inherit the design?

The better oracle is the trajectory: can early design decisions survive later requirements? Cost, time, and tokens may matter too; a well-factored codebase should make the next change cheaper. An even sharper test would let a frontier model build checkpoints one through seven, then ask a smaller model to implement checkpoint eight. If it can inherit and extend the design, that result belongs to the model that left the codebase behind.

SlopCodeBench turns my vibes into a signal: for real-shaped work, today's models still cannot be trusted to run lights-off without steering. If they score above 80 percent on a well-held-out benchmark like this, I will feel much better turning the lights off. When matters less than knowing it is happening.

## Turning the lights back on

For now, the judge is you, so put code review back—but find leverage before the pull request, when changing direction is cheap. We use AI to front-load alignment across four phases: product review, system architecture, program design, and vertical slices.

A product review pins down the user pain, what success looks like, and, when useful, a rough mockup. Reserve it for work where misunderstanding intent would be expensive.

System architecture aligns services, endpoints, schemas, queues, stores, and data flow without deciding the code's internal shape. Review it with the eventual PR reviewer; disagreement here is cheaper than rework.

## Design the program before the agent cooks

Architecture is not enough. Before implementation, go down into program design: types, method signatures, file layout, and call stacks. Pseudocode, call-stack trees, and file-tree diffs make decisions visible. The model drafts; you argue with it before the expensive moment of code review.

Build vertical slices rather than horizontal plans. Models proceed in stack order—database, service layer, API, frontend—leaving nothing touchable until the end. I prefer an end-to-end sliver: serve mock data, consume it in the interface, test it, then wire in services, storage, logic, and error handling.

When I care about the code a lot, or I am skeptical about the model's ability to do good work in this part of the codebase, I review each slice too. Checking 100–200 lines and resteering is cheaper than reaching the other side of 2,000 lines with no idea what is broken. I usually send a model one to three slices at a time.

## Work within the constraints

This process is proportional. I would guess roughly 40 percent of tasks can still be one-shot or need only light feedback. Medium work can combine product and system design in one plan. Large changes get the full sequence, with the irrelevant phases skipped when appropriate.

I wanted the world where we could ask for production software, let the models cook, and never read the code. But what I've done my best to lay out here are nothing but constraints. Learn them, develop intuition, optimize within them, and seek leverage. It is possible to spend your time chasing 10-to-100-times claims when you could move two to three times faster, safely.

Read the dang code.
