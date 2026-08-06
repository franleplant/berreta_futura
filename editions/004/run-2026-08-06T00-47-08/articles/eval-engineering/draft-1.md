---
source_ids:
- eval-engineering-the-step-that-turns-a-200-model-9f6f868f
content_mode: faithful_synthesis
label: FAITHFUL SYNTHESIS
---

Everyone is renting the same brain now.

The model you can have for a couple of hundred a month is, give or take, the model a company with a thousand engineers is running. That was supposed to level everything. Instead it made the gap between two teams renting the identical brain wider than the gap between two models.

A travel agent answered a question about an exchange rate, the week’s temperature, and a museum’s opening hours. Specific, clean, useful-sounding. All of it invented. The search tool had come back empty, and the model quietly filled the hole and handed its invention over as a fact it had looked up.

The team measured 100 real sessions and found two numbers that should never sit that far apart: response quality was 83.9%, while faithfulness to what the tools actually returned was 32.3%. The agent wrote beautifully and told the truth about a third of the time.

## The missing wire

A better model would not have caught this. What was missing was the layer that decides whether an answer was right, then does something with the verdict.

That layer is the distance between an AI that impresses people and an AI that gets paid. It is cheap to install, but nobody can sell it to you, because it encodes your definition of correct.

A thermometer tells you the room is cold. A thermostat turns the heat on.

Almost everyone building with AI owns a thermometer at best: a dashboard, a feeling, a Friday afternoon spent scrolling outputs and deciding they seem worse than last week. Eval engineering is the wiring from the reading to the furnace. The verdict returns to the graph and changes what runs next.

The progression is simple. One agent in a loop came first, so it could try, inspect what came back, and try again. Then many agents were laid out as a graph, so independent work could run side by side. Loops, then graphs, then evals. The graph made you faster. The judge decides whether that speed was worth having.

Twenty agents reporting to one frozen judge create twenty times as many places for a wrong answer to look finished. The examiner, unlike the model, is yours. Every failure you feed it stays there.

## Make the score act

A score in a report has no path back to the run it measured. A score that never changes behavior is analytics. An eval that changes the next edge is engineering.

The verdict must steer the run while it is still moving. Low context recall can reject a handoff. Bad tool use can retry or swap a node. A hallucination can quarantine a branch. A schema failure can block an edge. A compliance risk can route to human review. Verified completion can terminate the run. These are routing decisions the graph executes, one edge at a time.

The judge needs rules of its own. Use a model from another family when possible, because a model recognizes its own writing and grades it more kindly. Write one observable success condition for each primary verdict. Let the judge handle semantic calls, while plain code checks objective facts such as whether a test passed, a file exists, or state changed. Do not reward response length, keywords, citation count, exact phrasing, or similarity to a reference. Pin the judge and log its version, or a silent upgrade will make a month of scores incomparable.

Optimize against a judge long enough and the agent learns to look right rather than be right.

## Mine the failures you already paid for

Tests invented at a desk protect you from failures you already imagined. The expensive ones are in your logs, wearing timestamps.

Start with 25 complete traces, with good and bad behavior next to each other: a normal request that finished, a request the user confirmed, one the user corrected or rephrased, a run with a failed or repeated tool call, and a run with an external failure such as a timeout or rate limit.

Write each finding in four lines: what the user asked and what the agent did, what worked and what did not, whether the cause was the agent or a dependency, and the capability an eval should preserve or improve. Attribution matters. The same lookup twice with identical arguments is a loop in your agent. A 429 is somebody else’s limit unless your agent was supposed to recover from it.

The trace tells you what happened, not what should have happened. Take the answer key from tests, source records, policy, known state, or a person. Test the verifier with one clearly correct result and one plausible but wrong result before trusting it. Keep the expected outcome and judge credentials hidden from the agent being tested. If the environment gives away the answer, the task passes forever and measures nothing.

Questioning the user before implementation is deliberate. The definition of correct lives in someone’s head and nowhere in the model. Run this loop repeatedly and each failure stops being an incident and becomes a permanent test.

## Let the record decide who merges

Every pull request an agent opens can land in the same human queue. Then the reviewer becomes the bottleneck, and the fleet runs at the speed of one tired person.

A confidence score can combine four signals: deterministic guardrails, the recent eval trajectory for this version of the agent, the historical revert rate for this repository and class of change, and the sandbox outcome. Above the threshold, the change merges itself. Below it, a human receives the failing signal instead of starting at line one. Three of those signals are history or deterministic checks; exactly one touches the model.

Trust in an agent is an actuarial calculation.

At one company, 19 of every 20 pull requests on a fully autonomous agent merge without human involvement. Across top agents, about three quarters of merged work goes in without a human edit, reverts remain in the low single digits, and Guardrails alone rejects one pull request in five before review.

The constraint is the product.

That constraint still needs a warning label. A team ran 285 iterations of a self-improving codebase and produced 1,094 merged pull requests with zero regressions. Yet 38 green tests coexisted with a completely broken product. The loop has to converge on the specification, not merely on the score.

Run the gate in shadow first, for at least four hours of real traffic. Keep it closed when automated and human verdicts differ by more than 2%. Sample only 1% to 5% of traces unless you truly need full capture. With the risky slice gated and the boring 80% open, two people can quote on work they used to decline. The model bill does not move. Everything else does.

## The first suite

Start with three measurements for any agent that calls tools: faithfulness to tool results, tool-parameter accuracy, and response quality. The travel agent’s 32.3% faithfulness score is why the first measure matters. If the agent ships code, score the change across intent and decision, execution and artifact, completeness and usefulness, instruction and boundary, and efficiency.

Choose the dataset type on purpose. A final-response set grades only the answer. A single-step set isolates one decision. A trajectory set grades the whole path. A retrieval set grades RAG quality. Grading only the final response lets an agent reach a correct answer through a broken sequence.

Keep the suite alive: hold out 300 to 800 cases, with 500 running in under five minutes. Then build five tests first: an empty tool result that forces the agent to admit it has no number, a repeated call, a boundary refusal, handoff integrity, and verified completion based on a real signal.

The model is a rental. It will be replaced twice before the year ends. What survives is the examiner around it: failures turned into tests, rules that change the next edge, and a track record that lets a machine merge its own work.

Most people will keep scrolling outputs on Friday and deciding they feel about right. The ones who go first spend one afternoon wiring the thermostat, then spend the next year with an agent that cannot break the same thing twice.
