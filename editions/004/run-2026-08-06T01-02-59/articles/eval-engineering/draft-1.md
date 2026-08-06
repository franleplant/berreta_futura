---
source_ids:
- eval-engineering-the-step-that-turns-a-200-model-9f6f868f
content_mode: faithful_synthesis
label: FAITHFUL SYNTHESIS
---

A software travel agent gave a clean answer: an exchange rate to one decimal place, the week's temperature, and a museum's opening hours. The search tool had returned nothing. The agent filled the silence with invention and presented it as lookup. Across 100 real sessions, its answers scored 83.9% for quality and 32.3% for faithfulness to the tools. It wrote beautifully and told the truth about a third of the time.

## The missing return arrow

Everyone is renting the same brain now. A model available for a few hundred dollars a month is, roughly, the model a company with a thousand engineers is running. The gap between teams has moved elsewhere: into the layer that decides whether an answer was right and changes what happens next.

A better model would not have caught the travel agent's failure. The missing part was evaluation engineering. A thermometer tells you the room is cold. A thermostat turns the heat on. Most teams have the thermometer: a dashboard, a score, or a Friday afternoon spent scrolling through outputs and deciding that things seem worse. Eval engineering wires the reading back into the system.

That wiring changes the economics. The model is rented. The examiner is yours. Every failure you feed it can remain in the system as a test, while the examiner costs almost nothing to run.

The sequence matters. One agent in a loop came first, able to inspect a result and try again. Then graphs let independent work run in parallel. Evals are the next step: the judge decides whether the speed was worth having. Twenty agents reporting to one frozen judge create twenty places for a wrong answer to look finished.

## Build the examiner you already have

The old assumption was that evaluation required a platform, a contract, and months before the first useful number. A blind test of 100 production traces from a voice agent showed a different path. Human experts marked 39 kinds of failure, then the same hidden set went to several evaluation systems. Braintrust recovered 87.2% of the human-flagged failures. Codex on GPT-5.5 High reached 84.6% recall and 82.8% precision, ahead of LangSmith's 79.5% recall. Arize had 74.4% recall and the cleanest precision at 91.0%.

The interesting result was not the winner. A general coding agent on a subscription many teams already pay for performed above two dedicated platforms. One conclusion followed plainly: similar results were available from the coding agent itself. Within four weeks, four evaluation vendors had shipped their expertise as skills for other coding agents. The category was unbundling into the terminal already open.

The installation commands matter less than two details. One set of skills builds evaluations; another pulls real production runs to supply the material. Install the first without the second and you have a framework with nothing to examine. And the skills follow an open specification, so the same files can load into Codex, Cursor, Windsurf, or Goose. The reporting step is the useful one: it returns prioritized recommendations tied to locations in the code.

Then the examiner has to act. A score that never changes behavior is analytics. An eval that changes the next edge is engineering. The routing rules can be direct:

- low context recall rejects the handoff;
- bad tool use retries or swaps the node;
- hallucination quarantines the branch;
- schema failure blocks the edge;
- compliance risk routes to a human;
- verified completion terminates the run.

Each verdict becomes a structural decision in the graph.

## Keep the judge honest

The examiner needs its own discipline. Use a judge from another model family when possible. A model recognizes its own writing and can grade it kindly; one team uses Sonnet to judge Haiku for that reason. Write the rubric as one observable condition: “Pass iff [the successful outcome].” Give it one primary verdict rather than a bundle of proxy scores.

Let ordinary code handle objective checks: whether a test passed, a file exists, or state changed. Let the judge handle semantic calls. Do not reward the shape of an answer through length, keywords, citation counts, exact phrasing, tool-call counts, or similarity to a reference. Reward the outcome the agent was meant to produce.

Pin the judge and log its version. A silent upgrade makes scores before and after incomparable, and the problem can sit unnoticed for a month. Optimize against a judge long enough and the agent learns to look right rather than be right.

## Turn failures into permanent tests

Tests invented at a desk protect you from failures you imagined. The expensive failures are already in the logs.

Start with 25 complete traces, selected so good and bad behavior sit beside each other: a normal successful request, a request the user confirmed, one the user corrected or rephrased, a run with a failed, empty, or repeated tool call, and a run with an external failure such as a timeout or rate limit. For each trace, record what the user asked and what the agent did, what worked, who caused the failure, and what capability an eval should preserve or improve.

Attribution saves time. The same lookup twice with identical arguments is an agent loop. A 429 is somebody else's limit unless the agent was supposed to recover from it. A trace records what happened, not what should have happened, so take the answer key from tests, source records, policy, known state, or a person.

Each capability becomes its own hidden test folder. The agent sees the instruction and environment. It does not see the expected outcome, rubric, or judge credentials. Test the verifier with one clearly correct result and one plausible but wrong result before trusting it. Also check that the environment does not reveal the answer before the agent reaches the tool. Anything that would cost money or write to production gets simulated.

The interview matters. Ask the agent to map the repository, read the traces, propose candidates, and recommend one before implementation. The definition of correct often lives in the user's head and nowhere in the model. Run this loop repeatedly and each incident becomes a test instead of a recurring surprise.

## Let evidence decide who reviews

An autonomous fleet otherwise ends at one human queue. A confidence score can decide which changes need that queue. Four signals are available when a pull request arrives: deterministic guardrails, the recent eval trajectory for this agent version, the historical revert rate for this repository and change class, and the sandbox outcome.

Above a threshold, the change merges. Below it, a human receives the failing signal instead of starting at line one. Three signals are history or deterministic checks; only one touches the model. Trust in an agent is an actuarial calculation, a track record with a price on it.

At one company, 19 of every 20 pull requests from a fully autonomous agent merge without human involvement. Across leading agents, about three quarters of merged work receives no human edit, reverts remain in the low single digits, and Guardrails rejects one pull request in five before review. One operator described the attitude behind it: “I don't trust them at all. I also don't trust my ability to code review their work. But I do trust my ability to constrain their work.”

The constraint is the product.

The warning is that a green suite can still guard a broken product. One team ran 285 iterations, merged 1,094 pull requests, and recorded zero regressions, yet 38 green tests coexisted with a completely broken product. The loop must converge on the specification, not merely on the score.

Run the gate in shadow mode for at least four hours of real traffic. Set a 2% disagreement threshold between automated and human verdicts. Sample 1% to 5% of traces instead of capturing everything. Keep the gate closed on risky work and open on the boring 80%. The model bill does not move. Everything else does.

## The small suite that stays alive

Start with three measurements for a tool-using agent: faithfulness to tool results, tool-parameter accuracy, and response quality. The travel agent's 32.3% faithfulness score is why the first measurement belongs there. For code changes, score intent and decision, execution and artifact, completeness and usefulness, instruction and boundary, and efficiency.

Choose the dataset type deliberately. `final_response` tests only the answer. `single_step` isolates one decision. `trajectory` tests the whole path. `RAG` tests retrieval. Grading only the final response lets an agent reach a correct answer through a broken sequence.

Keep 300 to 800 cases on holdout, with 500 running in under five minutes. A suite longer than a coffee break stops being run. The first five evaluations should cover an empty tool result, a repeated call, a boundary refusal, handoff integrity, and verified completion. Done must have an external signal, not the agent's own declaration.

The model will be replaced. The examiner remains: the failures turned into tests, the routing rules, and the track record that lets a machine merge its own work. Install one skill, pull 25 traces, build one eval, and add another whenever something breaks. After that afternoon, the system has a memory. It cannot break the same thing twice without leaving evidence.
