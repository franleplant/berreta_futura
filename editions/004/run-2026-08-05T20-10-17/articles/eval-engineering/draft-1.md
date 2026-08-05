---
source_ids:
- eval-engineering-the-step-that-turns-a-200-model-9f6f868f
content_mode: faithful_synthesis
label: FAITHFUL SYNTHESIS
---

Everyone is renting the same brain now. The model you can have for a couple of hundred a month is, give or take, the model a company with a thousand engineers is running. That was supposed to level everything. Instead it made the gap between two teams renting the identical brain wider than the gap between two models.

A software travel agent answered a trip question with an exchange rate, a weekly temperature, and a museum's opening hours. Every answer sounded specific and useful. All of it was invented. The search tool had returned empty, and the model filled the hole with a fact it had not looked up. Across 100 real sessions, answer quality was 83.9%; grounding in tool returns was 32.3%. The agent wrote beautifully and told the truth about a third of the time.

A better model would not have caught this. What was missing was the layer that decides whether an answer was right, then does something with the verdict. That layer is the whole distance between an AI that impresses people and an AI that gets paid. It is the cheapest line in the stack and the only one nobody can sell you, because it encodes your own definition of correct.

A thermometer tells you the room is cold. A thermostat turns the heat on. Almost everyone building with AI owns the thermometer: a dashboard, a feeling, or a Friday afternoon spent scrolling outputs. Eval engineering is the wiring from the reading to the furnace.

## What eval engineering is

A company running agents in production changed no model, prompts, or human nudges across successive versions. It changed only the evals, and scores moved across every dimension. A blind test of 100 real traces, human-labeled into 39 failures, put a general coding agent on a subscription already paid for above two dedicated platforms. Within four weeks vendors shipped their expertise as skills for coding agents.

Loops came first, then graphs, then evals. A loop lets one agent try again; a graph lets independent agents run side by side. The graph was the last upgrade that made you faster. The judge decides whether that speed was worth having. Twenty agents reporting to one frozen judge create twenty times as many places for a wrong answer to look finished.

## Make the score change the next edge

A score that never changes behavior is analytics. An eval that changes the next edge is engineering. Low context recall rejects a handoff; bad tool use retries or swaps a node; hallucination quarantines a branch; schema failure blocks an edge; compliance risk routes to a human; verified completion terminates the run. Each verdict steers the graph mid-flight.

The judge needs rules. Use a model from another family, since a model that recognizes its own writing shares its blind spots. Write one primary verdict as `Pass iff [the independently observable successful outcome]`, never a bundle of proxy scores. Let plain code check objective facts such as a test, file, or state change, and let the judge handle semantic calls. Do not score response length, keywords, citation count, exact phrasing, tool-call count, or similarity to a reference. Pin the judge and log its version. Optimize against a judge long enough and the agent learns to look right rather than be right.

## Turn a failed run into an eval

Tests invented at a desk protect you from failures you already imagined. The expensive ones are in the logs. Start with 25 complete traces, no more, chosen so good and bad behavior sit together: a normal finished request; one the user confirmed; one the user corrected or rephrased; a failed, empty, or repeated tool call; and an external timeout or rate limit. Write each in four lines: observed behavior, comparison, attribution, and an eval candidate. Attribution matters: the same lookup twice is a loop in the agent; a 429 is somebody else's limit and becomes your eval only if the agent was supposed to recover.

Put one capability in each Harbor task under `evals/<task-id>/`. The tested agent sees the instruction and environment; the expected outcome, rubric, and judge credentials stay hidden. Never treat the recorded answer as truth. Take the answer key from tests, source records, policy, known state, or a person. Hand the verifier one clearly correct and one plausible but wrong result before the real run, and check that the environment does not give away the answer. Simulate anything that costs money or writes to production. The interview is deliberate because the definition of correct lives in the user's head and nowhere in the model.

## Let the graph merge its own work

Every pull request an agent opens lands in a human queue. A gate can combine four signals: deterministic guardrails, the recent eval trajectory for this agent, its historical revert rate on this repository and change class, and the sandbox outcome. Above the threshold it merges itself; below it reaches a human with the failing signal named. Three signals are history or deterministic checks, and exactly one touches the model. Trust in an agent is an actuarial calculation. At one company, 19 of every 20 pull requests from the fully autonomous agent merge without a human.

A green score can still guard a broken product. Their own line was sharper: 38 green tests coexisted with a completely broken product. A suite can go all green while the product it guards falls apart, which is why the loop has to converge on the spec rather than on the score. Run the gate in shadow for at least four hours of real traffic, keep it closed when automated and human verdicts differ by more than 2%, and sample only 1% to 5% of traces. The model bill does not move. Everything else does.

## The evals to build this week

Start with three measurements: faithfulness, tool-parameter accuracy, and response quality. Faithfulness is the travel agent's 32.3% warning. Choose a dataset that matches the question, whether `final_response`, `single_step`, `trajectory`, or `RAG`; scoring only the final answer can hide a broken path. Keep the suite short enough to run: 500 cases should finish in under five minutes.

Build five evals first:

1. Empty tool result: report absence rather than invent.
2. Repeated call: identical arguments twice fails as a loop.
3. Boundary refusal: decline cleanly outside the agent's permissions.
4. Handoff integrity: the next node reads exactly what the previous one produced.
5. Verified completion: a real signal says done, never the agent's own word.

That is an afternoon of work, and the suite is worth more every week you run it.

The model was never the interesting part. It is a rental, identical for everyone. What survives every replacement is the examiner you built around it: the failures you turned into permanent tests, the rules that let a verdict change the next edge, the track record that lets a machine merge its own work.

Most people will go back to scrolling outputs on a Friday and deciding it feels about right.

Install one skill. Pull 25 traces. Build one eval today, and add one every time something breaks.
