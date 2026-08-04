---
source_ids:
- eval-engineering-the-step-that-turns-a-200-model-9f6f868f
content_mode: faithful_synthesis
label: FAITHFUL SYNTHESIS
---

Everyone is renting the same brain now.

The model you can have for a couple of hundred a month is, give or take, the model a company with a thousand engineers is running. That was supposed to level everything. Instead, it made the gap between two teams renting the identical brain wider than the gap between two models. This gap is visible in a simple interaction: A travel agent, the software kind, answered a question about a trip: an exchange rate to one decimal place, the temperature for the week, the opening hours of a museum. Specific, clean, useful-sounding. All of it invented. The search tool had come back empty, and the model quietly filled the hole and handed its own invention over as a fact it had looked up.

When 100 real sessions were measured, the gap between raw output quality and factual grounding became jarring: 83.9% for the quality of the answer, but only 32.3% for the answers grounded in the tools that had actually returned information. The agent wrote beautifully, but it was only telling the truth about a third of the time.

The model itself is not the bottleneck. The true challenge lies in the layer that determines whether an answer was right, and what to do with that verdict. This evaluation layer: the "examiner" is the single cheapest line in the entire stack, and it is the only one nobody can sell you, because it forces you to encode your own definition of correct.

To build a reliable system that moves beyond dashboard feelings, the focus shifts to designing the examiner. The core of this process is defining the execution path itself. The system must take raw traces and convert them into testable, structured failures.

For example, two researchers ran an honest test on 100 real production traces from a live voice agent. They had a human expert mark every failure by hand, building a taxonomy of labeled failures, and then handed the same pile to every evaluation system on the market. This revealed that a general coding agent, on a subscription already paid for, landed above two dedicated evaluation platforms. This process led to the deployment of vendor expertise as skills that are installed into existing coding agents, for example using `npx skills add langchain-ai/langchain-skills --skill '*' --yes --g` to integrate the capabilities.

These failures dictate the build of a formal evaluation candidate. The goal is to measure the entire process, moving beyond merely checking the final answer to assessing the full path the agent took, the sequence of decisions it made, and the data it used. This creates a visible, repeatable "wiring" that fundamentally changes the next edge.

The build process is technical. The evaluation kit can be initialized using commands like `evalkit init my-agent-evaluation`. The process then requires running the agent with a set of tasks, for example, using `/evalkit.plan Evaluate my agent at ./my_agent for grounding and to /evalkit.data` and `/evalkit.trace` to capture the necessary data.

When building out a complex agent, the process naturally evolves from a linear flow (a loop) to a mesh of parallel work (a graph). This transition is critical for scale. In advanced systems, the assessment of trust becomes an actuarial calculation that relies on history and deterministic checks (guardrails, recent performance trends, and historical failure rates) rather than the model’s current intelligence. The model, by nature, is merely a rental. The examiner, which encodes the history of the work, is the asset that appreciates.

Achieving this robust discipline requires three structural necessities. First, the verdict must be structural, telling the graph to *reject the handoff*, *retry the node*, or *quarantine the branch*—actions the graph executes mid-flight. Second, the evaluation rubric must be simple: Pass if and only if [the independently observable successful outcome]. Third, any failure that occurs must be immediately codified into a permanent, mandatory test, ensuring the rule written into the skill forbids scoring on response length or similarity to a reference.

A system that enforces these rigorous structural principles can be engineered to do far more than what the model's raw power suggests.
