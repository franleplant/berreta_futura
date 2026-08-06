---
source_ids:
- eval-engineering-the-step-that-turns-a-200-model-9f6f868f
content_mode: faithful_synthesis
label: FAITHFUL SYNTHESIS
---

Everyone is renting the same brain now.

The model you can have for a couple of hundred a month is, give or take, the model a company with a thousand engineers is running. That was supposed to level everything. Instead it made the gap between two teams renting the identical brain wider than the gap between two models.

A travel agent answered a question about an exchange rate, the week’s temperature, and a museum’s opening hours. The answer was specific, clean, and useful-sounding. All of it was invented. The search tool had come back empty, and the model quietly filled the hole and handed its invention over as a fact it had looked up.

The team measured 100 real sessions and found two numbers that should never sit that far apart: response quality was 83.9%, while faithfulness to what the tools actually returned was 32.3%. The agent wrote beautifully and told the truth about a third of the time.

## The examiner closes the loop

A better model would not have caught this. What was missing was the layer that decides whether an answer was right, then does something with the verdict.

One company changed no model, prompts, or human nudges across successive versions of its agent. It changed only the evals, and the scores moved across every dimension. Its conclusion was plain: evals should have been in the system on day one, not month nine.

A thermometer tells you the room is cold. A thermostat turns the heat on.

Almost everyone building with AI owns a thermometer at best: a dashboard, a feeling, a Friday afternoon spent scrolling outputs and deciding they seem worse than last week. Eval engineering is the wiring from the reading to the furnace. The verdict returns to the graph and changes what runs next.

The evidence that this is practical is already here. Researchers took 100 production traces from a live voice agent, had a human expert label 39 kinds of failure, hid those labels, and tested evaluation systems against the same pile. Braintrust Loop recovered 87.2% of the human-flagged failures. Codex on GPT-5.5 High reached 84.6% recall and 82.8% precision. LangSmith reached 79.5%, while Arize AX reached 74.4% recall with 91.0% precision. A coding agent on a subscription people already pay for rivaled dedicated platforms. Within four weeks, vendors were shipping their expertise as skills for those same agents. The category is unbundling into the terminal already open.

The model is a rental. The examiner is yours, and every failure you feed it stays there.

## Start with a failure

Tests invented at a desk protect you from failures you already imagined. The expensive ones are in your logs, wearing timestamps.

A useful first set comes from 25 complete traces, with good and bad behavior next to each other: a normal request that finished, one the user confirmed, one the user corrected or rephrased, a run with a failed or repeated tool call, and a run with an external failure such as a timeout or rate limit.

Each finding records what the user asked and what the agent did, what worked and what did not, whether the cause was the agent or a dependency, and the capability an eval should preserve or improve. Attribution matters. The same lookup twice with identical arguments is a loop in your agent. A 429 is somebody else’s limit unless your agent was supposed to recover from it.

The trace tells you what happened, not what should have happened. The answer key must come from tests, source records, policy, known state, or a person. The verifier needs two hand-made checks before the real run: one clearly correct result and one plausible but wrong result. The environment must not reveal the answer before the agent reaches the tool; otherwise the task passes forever and measures nothing. Expected outcomes and judge credentials stay hidden from the agent being tested.

Anything that costs money or writes to production is simulated rather than called, so the suite can run repeatedly without a bill or an accidental side effect. Questioning the user before implementation is deliberate. The definition of correct lives in someone’s head and nowhere in the model. Run this loop repeatedly and each failure stops being an incident and becomes a permanent test.

## Make verdicts spendable

A score in a report has no path back to the run it measured. A score that never changes behavior is analytics. An eval that changes the next edge is engineering.

The verdict must steer the run while it is still moving. A context-recall failure rejects a handoff; bad tool use sends the node around for a retry or swap. Hallucinated work can be quarantined, while a schema failure closes the edge. Compliance risk sends the branch to human review, and a verified completion signal ends the run. These are routing decisions the graph executes, one edge at a time.

The evaluation team also has to protect the judge from its own blind spots. A model from another family is safer because models recognize their own writing and grade it more kindly. The rubric should state one independently observable successful outcome for each primary verdict. Semantic calls belong to the judge; plain code can check whether a test passed, a file exists, or state changed. The skill should forbid rewards for response length, keywords, citation count, exact phrasing, or similarity to a reference. Pinning the judge and logging its version keeps scores comparable when the model is upgraded.

Optimize against a judge long enough and the agent learns to look right rather than be right.

## Let the record set the gate

The mined tests and their verdict history now give a merge decision somewhere to stand. Every pull request an agent opens can land in the same human queue. Then the reviewer becomes the bottleneck, and the fleet runs at the speed of one tired person.

A confidence score can combine deterministic guardrails, the recent eval trajectory for this version of the agent, the historical revert rate for this repository and class of change, and the sandbox outcome. Above the threshold, the change merges itself. Below it, a human receives the failing signal instead of starting at line one. Three signals are history or deterministic checks; exactly one touches the model.

At one company, 19 of every 20 pull requests on a fully autonomous agent merge without human involvement. Across top agents, about three quarters of merged work goes in without a human edit, reverts remain in the low single digits, and Guardrails alone rejects one pull request in five before review.

The constraint is the product.

That constraint still needs a warning label. A team ran 285 iterations of a self-improving codebase and produced 1,094 merged pull requests with zero regressions. Yet 38 green tests coexisted with a completely broken product. The loop has to converge on the specification, not merely on the score.

The gate first runs in shadow for at least four hours of real traffic. It stays closed when automated and human verdicts differ by more than 2%. Sampling 1% to 5% of traces is usually enough; full capture is a cost you do not need to carry. With the risky slice gated and the boring 80% open, two people can quote on work they used to decline. The model bill does not move. Everything else does.

## Keep the suite alive

Three measurements cover a useful starting point for an agent that calls tools: faithfulness to tool results, tool-parameter accuracy, and response quality. If the agent ships code, the change can be scored across intent and decision, execution and artifact, completeness and usefulness, instruction and boundary, and efficiency.

The dataset type determines what the grader can see. A final-response set grades only the answer. A single-step set isolates one decision. A trajectory set grades the whole path. A retrieval set grades RAG quality. Grading only the final response lets an agent reach a correct answer through a broken sequence.

A suite stays alive when 300 to 800 cases are held out and 500 run in under five minutes. The first five tests can cover an empty tool result, a repeated call, a boundary refusal, handoff integrity, and verified completion based on a real signal. The travel agent’s invented answer belongs in the first group: when the tool returns nothing, the agent must say so instead of supplying a number.

The model can be replaced twice before the year ends. What survives is the examiner around it: failures turned into tests, rules that change the next edge, and a track record that lets a machine merge its own work.

Most people will keep scrolling outputs on Friday and deciding they feel about right. The ones who go first spend one afternoon wiring the thermostat, then spend the next year with an agent that cannot break the same thing twice.
