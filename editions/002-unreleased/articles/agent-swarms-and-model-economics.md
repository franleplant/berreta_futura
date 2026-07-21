---
source_id: agent-swarms-and-the-new-model-economics-8b346f57
content_mode: faithful_synthesis
label: FAITHFUL SYNTHESIS
---

We have been experimenting with how far coding-agent swarms can scale. A new harness, built from the SQLite documentation, outperformed our earlier approach in every model configuration. The striking result was not simply that more agents helped. It was that topology, memory, version control, and the division between planning and execution changed both quality and cost.

## Trees preserve context

Our swarm forms a tree. A capable planner splits work and delegates it; cheaper workers execute focused tasks. The planner never implements and the worker never plans. This separation is valuable less for parallel speed than for context efficiency: each agent sees the memory required for its role instead of carrying the entire project until it drifts.

Coordination required infrastructure. The old browser experiment produced around a thousand commits an hour; the SQLite experiment could approach a thousand a second, so we built a custom version-control layer. Shared design documents, compile references, neutral reconcilers, megafile limits, and controlled breakage reduced split-brain designs and merge thrash. Multiple decorrelated review lenses were cheap and delivered unusually high returns.

## A manual as the world

For SQLite, agents received an 835-page manual but no source code, tests, binary, or internet access. We evaluated them against millions of sqllogictest cases, with a held-out set protecting the final result. Four planner/worker configurations reached between 73 and 85 percent after four hours in the new harness and later reached 100 percent; the old harness ranged from 11 to 77 percent at the same checkpoint.

The traces explain the difference. The old system made tens of thousands of early commits yet thrashed through roughly seventy thousand conflicts, spawned overlapping SQL implementations, and grew far more code. The new system made fewer, more coherent changes. One successful run reached full correctness in 4,645 lines where an older run used 19,013 lines for 97 percent.

## Models are roles, not a single bill

Costs ranged from roughly $1,339 for an Opus-planner hybrid to $10,565 for an all-GPT-5.5 configuration. Workers consumed at least 69 percent of tokens and more than 90 percent in most runs. Frontier reasoning mattered at a few planning moments, while the bulk of execution could use cheaper models. In one comparison, GPT-5.5 workers cost $9,373 and Composer workers $411.

The implication is architectural and economic: select models by role. A planner's extra judgment can be worth its price because it shapes thousands of cheaper actions. A nominally inexpensive planner can still raise the total bill if its decomposition causes workers to consume far more tokens.

## Specs become prompts

As agents improve, the unit given to a model rises from line, to block, to file, feature, and eventually specification. A swarm begins to resemble a probabilistic compiler: intent becomes tasks, tasks become coordinated work, and verification closes the semantic gap. The scarce input is not code generation. It is precise intent, supported by an environment that lets many agents preserve it.
