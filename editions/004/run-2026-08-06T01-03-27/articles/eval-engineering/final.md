---
source_ids:
- eval-engineering-the-step-that-turns-a-200-model-9f6f868f
content_mode: faithful_synthesis
label: FAITHFUL SYNTHESIS
---

Everyone is renting the same brain now. A software travel agent answered a simple trip question with an exchange rate, a weekly temperature, and museum hours. The search tool had returned nothing. The agent filled the gap, then presented its invention as researched fact. Across 100 real sessions, its answers scored 83.9% for quality and only 32.3% for faithfulness. It wrote beautifully and told the truth about a third of the time.

The gap matters because a better model would not have caught this. The missing part was the layer that decides whether an answer was right and sends that verdict back into the system. That layer separates an impressive demo from a product someone can trust.

## The return arrow

A team running agents in production changed no model, prompts, or human nudges across successive versions. They changed only the evaluations, and the scores moved across every dimension. Their conclusion was blunt: the evals should have been in the system on day one, not month nine.

A thermometer tells you the room is cold. A thermostat turns the heat on.

Most teams have the thermometer: a dashboard, or a Friday afternoon spent scrolling through outputs and deciding they seem worse than last week. Eval engineering adds the wiring from the reading to the furnace. The verdict changes what runs next.

The sequence developed in a clear order. First came one agent in a loop, able to inspect a result and try again. Then came graphs, where independent work could run side by side. Evals came after that, deciding whether the speed was worth keeping. Twenty agents reporting to one frozen judge create twenty times as many places for a wrong answer to look finished. The examiner is a rental's opposite: every failure fed into it stays there permanently, so it becomes more valuable each week while the model remains replaceable.

The examiner is also cheap to start. In a blind test, researchers took 100 production traces from a voice agent, had a human expert mark 39 kinds of failure, hid those labels, and gave the same traces to evaluation systems. Braintrust recovered 87.2% of the flagged failures. Codex on GPT-5.5 High reached 84.6% recall and 82.8% precision, above LangSmith at 79.5% and Arize AX at 74.4% recall. A coding agent already on a subscription performed better than two dedicated platforms.

Within four weeks, LangChain, Galileo, AWS, and Arize had shipped their evaluation expertise as skills for coding agents. The jobs split in two: one repository builds the evaluations, while another pulls real production runs so those evaluations have material to examine. The category was unbundling into the terminal many teams already had open.

## Make the score steer the run

A number in a report does nothing by itself. The useful distinction is simple: a score that never changes behavior is analytics; an eval that changes the next edge is engineering.

The verdict must route the graph while the run is still in progress. Low context recall rejects a handoff; bad tool use triggers a retry or swaps a node; a hallucination quarantines a branch; a schema failure blocks an edge; a compliance risk routes to human review; verified completion terminates the run. Each result becomes an action.

The team designing the judge has to control its own blind spots. A model from another family is safer when possible, since models can grade their own family kindly. The rubric should state one independently observable pass condition, rather than bundle proxy scores. Semantic calls belong to the judge; ordinary code can check whether a test passed, a file exists, or state changed. A response that wins by length, keywords, citation count, exact phrasing, or similarity to a reference has learned the shape of approval instead of the task. Pinning the judge's version and logging it keeps scores comparable over time.

Optimize against a judge long enough and the agent learns to look right rather than be right.

## Turn failures into tests

Tests invented at a desk protect against failures someone already imagined. The expensive failures are in the logs.

A useful first sample contains 25 complete traces: a normal request that finished, a request the user confirmed, one the user corrected or rephrased, a run with a failed or repeated tool call, and a run with an external failure such as a timeout or rate limit. Each trace can be written in four lines: what the user asked and what the agent did, what worked and what did not, whether the cause was the agent or a dependency, and the capability an eval should preserve or improve.

That attribution matters. The same lookup twice with identical arguments is an agent loop. A 429 is somebody else's limit unless the agent was supposed to recover from it.

Each failure becomes a task with one capability. The agent sees the instruction and environment. The expected outcome, rubric, and judge credentials stay hidden, which is what gives the score meaning. Do not treat the recorded answer as truth. The trace records what happened, not what should have happened. Test the verifier with one clearly correct and one plausible but wrong result before trusting it. Check that the environment does not reveal the answer before the agent reaches the tool. Simulate anything that costs money or writes to production.

The interview step is deliberate. The definition of correct often lives in the user's head and nowhere in the model. Asking questions before implementation beats one-shot generation because it turns that private definition into a test.

Run the loop repeatedly and an incident becomes a permanent check.

## Let evidence decide what merges

An autonomous agent that opens pull requests still leaves every change in a human queue. The fleet then moves at the speed of one tired reviewer.

A merge gate can combine four signals: deterministic guardrails, the recent evaluation trajectory for this version of the agent, the historical revert rate for this repository and class of change, and the sandbox outcome. Above a threshold, the change merges. Below it, a human receives the failing signal and starts at the problem.

Three of those signals are history or deterministic checks. Only one touches the model. Trust in an agent becomes an actuarial calculation, a track record with a price on it.

At one company, 19 of every 20 pull requests from a fully autonomous agent merge without human involvement. Across leading agents, about three quarters of merged work needs no human edit; revert rates remain in the low single digits, and Guardrails rejects one pull request in five before review. One operator approved and merged about 1,500 pull requests in 90 days without reading a line of code. He did not trust the agents, or his own ability to review their work. He trusted his ability to constrain them.

The constraint is the product.

That confidence still needs a warning. A team ran 285 iterations of a self-improving codebase, merged 1,094 pull requests, and recorded zero regressions. Yet 38 green tests coexisted with a completely broken product. The loop must converge on the specification, not merely on the score.

Start in shadow mode for at least four hours of real traffic. Set a 2% deviation threshold between automated and human verdicts. Sample 1% to 5% of traces instead of capturing everything. Keep the gate closed on risky work and open on the boring 80%. The model bill does not move, but a two-person team can begin taking on contracts its single reviewer could never read through.

## The first afternoon

For a tool-using agent, begin with three measurements: faithfulness to tool results, tool-parameter accuracy, and response quality. The travel agent's 32.3% faithfulness score shows why the first measure deserves its own line.

For code-producing agents, score the change across intent and decision, execution and artifact, completeness and usefulness, instruction and boundary, and efficiency. Choose the dataset deliberately: final response, single step, full trajectory, or retrieval quality. Grading only the final answer can hide a broken path that happened to reach a correct result.

Hold out 300 to 800 cases, with about 500 running in under five minutes. A suite longer than a coffee break stops being run.

The first five evals should catch an empty tool result, a repeated call, a request outside the agent's permissions, a broken handoff between nodes, and a false claim of completion without an external signal. Three measurements, one dataset type, five tests: an afternoon's work, then a growing record of what the system must not repeat.

The model will be replaced. The examiner remains: the failures turned into tests, the rules that change the next edge, and the record that lets a machine merge its own work. That is what decides whether a $200 monthly bill produces a demo or a business.

Install one skill, pull 25 traces, build one eval, and add another whenever something breaks.
