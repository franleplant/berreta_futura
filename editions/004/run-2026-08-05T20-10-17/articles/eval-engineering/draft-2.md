---
source_ids:
- eval-engineering-the-step-that-turns-a-200-model-9f6f868f
content_mode: faithful_synthesis
label: FAITHFUL SYNTHESIS
---
Everyone is renting the same brain now. A software travel agent answered a trip question with an exchange rate to one decimal place, the week’s temperature, and museum hours. The answer was specific, clean, and useful-sounding. All of it was invented. Search had returned nothing, so the model filled the hole and passed its invention off as a lookup. Across 100 real sessions, response quality was 83.9%. Grounding in the tool returns was 32.3%. The agent wrote beautifully and told the truth about a third of the time. A better model would not have caught this. An eval checks the answer against what the tools returned and sends the verdict somewhere the run can act on. That layer turns a rented model into a system people can trust.

One production team changed no model, prompts, or human nudges across successive versions. It changed only the evals, and scores moved across every dimension. The team later said evals should have been there on day one, not month nine. A thermometer tells you the room is cold. A thermostat turns the heat on. Most teams have a thermometer at best: a dashboard, a feeling, or a Friday afternoon spent scrolling outputs. Eval engineering wires the reading to the furnace. A loop lets an agent try, inspect the return, and try again. A graph lets independent work run side by side. Evals close the circuit, so the verdict changes what runs next. The progression runs from loops to graphs to evals. With twenty agents running at once and one frozen judge, there are twenty places for a wrong answer to look finished. Models may change. The failure record stays with the examiner.

The return path no longer needs a platform contract. In a blind test, two researchers took 100 production traces from a live voice agent, had an expert mark each failure, built 39 labeled failures, hid the labels, and gave the same pile to every evaluation system. Codex on GPT-5.5 High, a general coding agent on a subscription already paid for, reached 84.6% recall and 82.8% precision, surpassing the scores of two dedicated platforms. Within four weeks, LangChain, Galileo, AWS, and Arize shipped their expertise as skills for coding agents. `langchain-skills` builds evals. `langsmith-skills` pulls the production runs that supply them. Install them with `npx skills add langchain-ai/langchain-skills --skill '*' --yes --g` and `npx skills add langchain-ai/langsmith-skills --skill '*' --yes --g`, then install AWS’s `evalkit` with `uv tool install evalkit`. In Claude Code, use `/plugin marketplace add langchain-ai/langchain-skills` and `/plugin install langchain-skills@langchain-skills`. Run `evalkit init my-agent-evaluation`, then `/evalkit.plan`, `/evalkit.data`, `/evalkit.trace`, `/evalkit.run_agent`, `/evalkit.eval`, and `/evalkit.report`. The last command returns prioritized recommendations tied to locations in your code.

A score still does nothing unless it changes execution. A score that never changes behavior is analytics. An eval that changes the next edge is engineering. For the travel agent, an empty search result becomes a failing verdict that blocks a fabricated answer. The same wiring routes other failures:

- Low context recall means the handoff lacks needed information, so reject it.
- Bad tool use retries or swaps the node.
- A hallucination quarantines the branch.
- A schema failure blocks the edge.
- Compliance risk routes to human review.
- Verified completion ends the run only after a real signal says done.

Choose a judge from another model family, because a model recognizes its own writing and grades it kindly. Write one primary rubric line: `Pass iff [the independently observable successful outcome]`. Let the judge handle semantic calls. Plain code checks a test, a file, or a state change. The skill forbids scoring response length, keywords, citation count, exact phrasing, tool-call count, and similarity to a reference. Pinning and logging the judge version keep scores comparable. A familiar judge can teach an agent to look right rather than be right.

Tests you invent from imagination protect you from failures you already imagined. The expensive failures have timestamps in production logs. Pull exactly 25 complete traces, no more, placing good and bad behavior together: a finished normal request, a user-confirmed request, a correction or rephrase, a failed, empty, or repeated tool call, and an external timeout or rate limit. Record observed behavior, comparison, attribution, and an eval candidate. The same lookup twice with identical arguments is the agent’s loop. A 429 belongs to the dependency unless the agent was expected to recover.

Turn each capability into a Harbor task:

```text
evals/<task-id>/
├── task.toml
├── instruction.md
├── environment/
└── tests/
```

The target sees the instruction and environment. The expected outcome, rubric, and judge credentials stay hidden. Start with `Use the eval-engineering skill.` Map the repository’s entrypoint, tools, backing data, and result shape. Read the 25 traces in `./traces`, propose candidates grounded in actual failures, recommend one, and wait for my choice. Build the chosen task under `evals/`, then test the verifier on one passing and one plausible wrong result. Keep the environment from giving away the answer. Simulate anything that costs money or writes to production.

Once a verdict reaches the run, it can gate the pull-request queue. Four signals are already available:

1. A deterministic guardrail pass or fail.
2. The recent eval trajectory for this version of the agent.
3. Its historical revert rate on this repository and class of change.
4. The sandbox outcome.

Combine them into a confidence score. A change above the threshold merges itself; below it, a human receives the named failing signal. Three of the four are historical or deterministic checks. Exactly one touches the model. A travel-agent-style empty-search hallucination is now a concrete failure signal, so a code change showing it stays with a human. At one company, 19 of every 20 pull requests on a fully autonomous agent merge without human involvement. Yet 38 green tests once coexisted with a completely broken product. The loop must converge on the specification rather than the score.

Run the gate in shadow first. Score every pull request against at least four hours of real traffic and merge none. If automated and human verdicts disagree by more than 2%, keep the gate closed. Sample 1% to 5% of traces. Leave the risky slice closed while the boring 80% opens. For code-shipping agents, score the change on intent and decision, execution and artifact, completeness and usefulness, instruction and boundary, and efficiency.

That score is the gate’s input. For any agent that calls tools, the working default is three measurements. Measure faithfulness first: is the answer grounded in what the tools returned? The travel agent scored 32.3% here. Then check tool-parameter accuracy, the right tool with the right arguments. Keep response quality as the third measure. Choose the dataset type deliberately: `final_response` for the answer alone, `single_step` for one decision, `trajectory` for the whole path, or `RAG` for retrieval quality. Scoring only a final response can hide a broken sequence. Hold out 300 to 800 cases and keep 500 running in under five minutes. A suite longer than a coffee break stops being run.

Start with five evals:

1. An empty tool result, so the agent admits it has no number.
2. A repeated call with the same lookup and arguments, which fails the loop.
3. A boundary refusal when the request exceeds the agent’s permissions.
4. Handoff integrity, checking that the next node reads what the previous one produced.
5. The completion check, using the rule above.

The first item is the travel agent’s failure turned into a test. Every model replacement leaves this examiner and its failures intact. The next time search returns nothing, the agent can say so, route the work, and leave a permanent test behind.
