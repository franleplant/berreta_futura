---
source_id: agent-swarms-and-the-new-model-economics-8b346f57
content_mode: faithful_synthesis
label: FAITHFUL SYNTHESIS
---

Earlier this year, a long-running swarm built a web browser from scratch: a useful proof of concept, but far from polished software. After that deliberately empirical hill-climb, we wanted to engineer the system with intent. We returned to a task the old swarm had struggled with—implementing SQLite in Rust from its documentation alone—and the new harness beat it with every model mix. Grok 4.5 reached 80 percent in four hours while the old run spiraled before hour two. More agents were not the decisive variable; topology, memory, coordination, and the planning-execution split changed quality and cost.

## Trees and memory

Large tasks naturally form trees: a goal at the root divides recursively until the leaves are concrete units of work. Our swarm uses two roles around that structure. Planner agents, powered by the strongest models, decompose goals and delegate them. Worker agents, generally faster and cheaper, execute the leaves. Rather than impose a fixed orchestration graph, the swarm grows to match the contours of the problem, so compute and context scale with complexity.

This design has generalized to math problems, GPU kernels, vulnerability fixes, test coverage, and synthetic data. We think its scaling advantage comes more from context efficiency than parallelism. A single agent must traverse the whole tree while remembering its position and wider goal; it either focuses locally and loses the whole, or preserves the whole and weakens its local work. A planner never implements, so detail does not consume its context; a worker never plans and can focus on one leaf. Like the bounded tiers in Ronald Coase's account of firms, the tree contains coordination costs that otherwise grow faster than the work.

## Failure modes at swarm speed

The browser swarm peaked around 1,000 Git commits per hour; the new system can approach 1,000 per second. Coarse-locking tools cannot operate at that tempo, so we built a version-control system from scratch. Because every change passes through it, that layer also became the natural place to detect collisions and coordinate.

Two unaware planners could create split-brain designs, implementing one concept incompatibly. We changed the prompts so planners own design decisions and delegated subtrees cannot decide the same question. When planners still fought over files, merge tooling could not reconcile their different pictures of reality. Agents now record decisions in shared documents; code carries compile-checked references to them; and a reconciler merges contradictions so resolutions propagate downstream.

Workers were poor at absorbing another agent's context during a merge, so a neutral third party now resolves collisions. Workers can flag megafiles, block further commits, and hand decomposition to an outside agent. To counter learned reluctance to touch core code, intentional breakage lets an agent make a focused change, leave its reasoning, and use compiler failures to carry the new design through dependent work.

Review became another system, not a single pass. We tried reviewers with the worker's full transcript, only its output, or only the codebase; we also varied model and personality. No lens catches everything, but decorrelated lenses stack. Because review is cheaper than the work it audits, that compute had unusually high returns and appears to have helped quality survive long runs.

## Letting agents shape the environment

Rules such as “keep notes” and “document decisions” are a form of stigmergy: agents change the environment, which guides the next agent. We extended this with a Field Guide owned by the swarm and injected into every new trajectory. Under a line budget, agents preserve surprising encounters so successors take shorter paths. Model weights stay frozen, but the working environment can learn.

## Rebuilding SQLite from a manual

We gave the improved swarm the 835-page SQLite manual and withheld the source, tests, binary, and internet access. We graded the result against millions of sqllogictest queries with known answers. The swarm was never told that suite existed; after each run we manually checked for shortcuts and verified that the system had been built broadly rather than only where tests happened to look.

We tested four model mixes: GPT-5.5 everywhere; Grok 4.5 everywhere; Opus 4.8 planning with Composer 2.5 working; and Fable 5 planning with Composer 2.5 working. Strategies differed—some built broad foundations before a late score spike, others scored early and then plateaued—but the harness result did not. At four hours the new runs were between 73 and 85 percent while the old runs ranged from 11 to 77 percent. Every new configuration later passed the full suite.

## A deep dive into the runs

Activity alone was misleading. The old Grok run made 68,000 commits in under two hours, about seventy times the new run's pace, but accumulated more than 70,000 merge conflicts and accelerated rather than stabilizing. The new run logged fewer than 1,000 conflicts across its full four hours. One old megafile attracted 7,771 conflicts from 1,173 agents; the most contested file in the new codebase saw 47.

Split-brain showed up in the package structure too. The old swarm sprawled to 54 Rust crates, including three competing SQL packages. The new swarm settled on nine crates early and never added another. That coherence reached the final code: in the Fable mix, both harnesses eventually passed the suite, but the old one needed 64,305 lines of engine code and the new one 9,908. With the Opus mix, the old harness used 19,013 lines to reach 97 percent; the new one reached 100 percent in 4,645.

## Model economics

Similar quality concealed enormous cost differences: $1,339 for the Opus-and-Composer hybrid versus $10,565 for GPT-5.5 alone. Workers carried at least 69 percent of tokens in every run and more than 90 percent in most. Planner tokens cost more, but there are only a few moments when frontier intelligence is indispensable—the initial decomposition, major design decisions, and difficult trade-offs. Once ambiguity has been collapsed into explicit instructions, inexpensive models can perform most of the execution.

In the all-GPT-5.5 run, workers alone cost $9,373. In the Opus-planner, Composer-worker run, the whole worker fleet cost $411. Yet cheap planning is not automatically cheap overall. Fable used fewer planning tokens than Opus despite its higher per-token price, but its workers consumed several times as many tokens, making the complete run substantially more expensive. Models have to be selected by role and by their effect on downstream work, not by one headline token price.

## Specs become prompts

Each capability jump raises the working abstraction: autocomplete operated on a line, early models on a block, agents on a file or feature. With swarms, the unit becomes the specification. We handed the system 835 pages of prose and it returned a database; the scarce resource was the right description of intent.

A swarm therefore resembles a compiler. Planners parse a goal into task trees and lower it step by step into executable work. The difference is that a compiler preserves meaning deterministically while a swarm is probabilistic at every stage. The task tree, shared memory, coordination machinery, review lenses, and verification environment all exist to close that semantic gap.
