---
source_ids:
- why-software-factories-fail-f53679d7
- why-software-factories-fail-turning-the-lights-b-1312d1ad
content_mode: faithful_synthesis
label: FAITHFUL SYNTHESIS
source_body_sha256:
  why-software-factories-fail-f53679d7: d33fdc4b32b52fc15f7182bdcd5745446577528e319f95736b29305f233b1299
  why-software-factories-fail-turning-the-lights-b-1312d1ad: e2b15724ecd99d724de29cd01cb5920ff35ead723a0da2e53629304307524939
---

We're all racing to put AI coding into production, and the prevailing wisdom is that we should write more loops. The lights-off promise is succinct: you are the bottleneck, the models are good enough, code is free, and nobody ever has to read it. Spend more tokens, add automated reviewers, and move 10 to 100 times faster.

Meanwhile, companies are having outages from coding-agent mishaps and codebases are falling apart faster than ever. Faros AI reported lower review quality, more PRs merged without review, and rising incidents and bugs per developer after teams adopted AI coding tools. That is correlation, not a smoking gun, but it feels directionally valid. This is not about vibe-coding a disposable side project. It is about hard problems in complex codebases, where the cost of a bad decision arrives months later.

No amount of harness engineering or loopsmaxxing can solve what is fundamentally a model-training problem. Models are much better at one-off tasks, but I do not trust them to maintain and improve codebase quality over time without human steering. There are no good benchmarks for that ability.

## Why the lights-off factory fails

Before AI, teams already used loops: decide what to build, put it in a tracker, implement it, review the pull request, ship, monitor, and feed what users discover back into the queue. Agentic factories mostly replace “someone builds the thing” with “an agent builds the thing.” Building falls from days to hours or minutes, while review remains expensive, so review becomes the bottleneck. The lights-off factory removes it and shifts trust to tests, sandboxes, automated review, monitoring, rollout, and user feedback.

We tried that in July 2025: background agents for the small and medium work, no routine code reading. Eventually an issue arrived that the agent could not solve. I had to return to a codebase I had stopped reading three months earlier while the site was down and users were angry. The first time, I decided the velocity justified the risk. By roughly the third time, it was easier to rewrite from scratch; my cofounder spent two weeks plumbing the patterns by hand.

The failure is maintainability: changing one part becomes likely to break another. Tests can report pass or fail in seconds, so reinforcement learning can optimize millions of coding traces against them. The cost of bad architecture appears in weeks, months, or years, when a one-line change must be repeated in eleven places. There is no equally fast, reliable oracle for good design.

## There is no penalty for bad design

A benchmark can ask whether an agent fixed a bug without breaking existing tests. If the suite passes, the patch wins, even when it makes the codebase harder to change. That is how you get try-catches around everything.

Promising evaluations are beginning to use longer tasks, compound rewards, mutation testing, and model-based quality rules. But if a model could reliably judge good code, it might have written the good version to begin with. More tokens and review agents raise the floor; they do not move the ceiling beyond what the model learned to recognize. The frontier is improving; the hype is outrunning the discipline.

## Turning the lights back on

For now, the judge is you, so put code review back—but find leverage before the pull request, when changing direction is cheap. We use AI to front-load alignment across four phases: product review, system architecture, program design, and vertical slices.

A product review pins down the user pain, what success looks like, and, when useful, a rough mockup. Reserve it for work where misunderstanding intent would be expensive.

System architecture aligns services, endpoints, schemas, queues, stores, and data flow without deciding the code's internal shape. Review it with the eventual PR reviewer; disagreement here is cheaper than rework.

## Design the program before the agent cooks

Architecture is not enough. Before implementation, go down into program design: types, method signatures, file layout, and call stacks. Pseudocode, call-stack trees, and file-tree diffs make decisions visible. The model drafts; you argue with it before the expensive moment of code review.

Build vertical slices rather than horizontal plans. Models proceed in stack order—database, service layer, API, frontend—leaving nothing touchable until the end. I prefer an end-to-end sliver: serve mock data, consume it in the interface, test it, then wire in services, storage, logic, and error handling.

When the code matters or the model is working in a difficult part of the system, review each slice too. Checking 100–200 lines and resteering is cheaper than reaching the other side of 2,000 lines with no idea what is broken. I usually send a model one to three slices at a time.

## Work within the constraints

This process is proportional. Roughly 40 percent of tasks can still be one-shot or need only light feedback. Medium work can combine product and system design in one plan. Large or risky changes get the full sequence, with the irrelevant phases skipped when appropriate.

I wanted the world where we could ask for production software, let the models cook, and never read the code. But these are constraints, not an argument against AI. Learn them, develop intuition, optimize within them, and seek leverage. It is possible to spend your time chasing 10-to-100-times claims when you could move two to three times faster, safely.

Read the dang code.
