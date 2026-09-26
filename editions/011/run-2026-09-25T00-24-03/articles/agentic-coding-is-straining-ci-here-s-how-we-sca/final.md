---
source_ids:
- agentic-coding-is-straining-ci-here-s-how-we-sca-86abcc6f
content_mode: article
label: ARTICLE
---

Anthropic engineers ship 8x as much code per quarter as they did from 2021-2025, and Claude authors 80% of it. Our tests grew 10x, and CI jobs rose 25x over six months. That threatened to overload our test impact analysis service several times. Three quick fixes lasted 70 days, then 29 days, then less than a day. Then we redesigned it around stateless workers and an in-memory store. It took one engineer three weeks; a year ago it would have been closer to a quarter. I anticipate horizontally scaled test selection will become industry standard as teams running agents create more PRs and more tests. The lesson I learned the hard way: always plan for the exponential.

## The service

Running every test on every change works up to a point, but doesn't scale: CI gates get long, expensive, and untrustworthy. Humans are good at spotting which failures don't apply to them. Agents need more context, and when they get a specific set of valid tests, they can self-verify and iterate more effectively.

Our service has two deterministic parts. A listener records the test results from every CI run. A selector reads that history and decides which tests run on each PR. With multiple CI jobs every second, the listener falls behind. Twenty minutes of lag can mean tens of thousands of test updates missing from the selector:

- A bad merged change starts failing for everyone, causing needless investigations.
- A flaking dependency blocks merges with flaky reds.
- A fixed or new test won't run until the listener catches up, risking a regression.

It all ran as one process, because a running history per test needed a single writer. That v0 design kept us from sharding horizontally.

## Three patches

**A bigger machine.** By October the service was straining, and we got paged two days straight. We doubled the cores, knowing it would be fleeting. Ownership was murky. No one wanted to own another piece of infrastructure, and the CI team had bigger fish to fry.

**Sharding.** I kept a long-running session in an internal version of Claude Tag watching the service. Whenever the listener fell more than 50,000 jobs behind, Claude pinged me and resumed our conversation. Claude often argued for an overhaul, but we usually settled on another patch. In February we parallelized. The listener didn't need one writer overall; it needed one writer per package. Claude generated the code to give each package its own shard and worker. We knew this would be fleeting too, but we didn't realize it would buy only 29 days.

**Daily restarts.** In March the process reached its memory limit by mid-afternoon on most weekdays. We found only four bugs. Swapping the memory allocator did nothing. We didn't want to risk memory profiling a singleton under heavy load. Restarting bought less than a day, and the restarts left the service gradually further behind. When it fell more than an hour behind, which happened several times, a ton of job results went unrecorded. CI still ran on those PRs, and untested code didn't reach production. But the selector decided on stale data, which mostly meant running tests that were already flaky or failing across the board.

These techniques are common and aren't the insight. The point is that each bought a fraction of the time it did a year ago, while a complete redesign now also takes a fraction of the time and is much more sustainable.

## The redesign

We took Claude's advice and gave the service an in-memory data store. Any listener worker can process any result, append it to a journal in the store, and move on without holding anything in memory: stateless, and so horizontally scalable. A small consumer rolls the journal up into per-test history every few seconds, and the selector looks it up quickly.

It is more expensive to run, but much easier to scale and memory profile than a shaky singleton. Claude did the fine tuning, sizing the journal and the number of workers, largely autonomously. The service has remained stable since.

## What I would do differently

Sent back to October 2025, I would account for the AI exponential. CI jobs grow exponentially as the number of agents per engineer rises and accelerated PR approval becomes more sophisticated. Claude prefers smaller, more granular PRs, so there are more jobs each day. Agents push overnight and on weekends, which raises the floor, but load stays bursty because humans still drive and approve many PRs.

Whether you build or buy, assume your architecture will be at 25x load within two quarters. Over-engineering is starting to fade slightly, or at least the bar is moving much higher. If your budget allows, design your v0 for 10-20x the perceived scale.

Instrument your services to be Claude's eyes and ears; it lets Claude hill-climb and fix problems incrementally much better and faster than we could manually. In particular, make sure the number of CI jobs coming in equals the number going out. Keep state out of the process from the start. Avoid running any critical service as a single instance unless you can measure it and any canary changes. CI is evolving too quickly to proceed any other way.
