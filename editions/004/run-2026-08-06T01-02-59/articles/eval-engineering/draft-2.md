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

That wiring changes the economics. The model is rented. The examiner is yours. Every failure you feed it can remain in the system as a test, while the examiner costs almost nothing to install.

The sequence matters. One agent in a loop came first, able to inspect a result and try again. Then graphs let independent work run in parallel. Evals are the next step: the judge decides whether the speed was worth having. Twenty agents reporting to one frozen judge create twenty places for a wrong answer to look finished.

## Build the examiner you already have

The old assumption was that evaluation required a platform, a contract, and months before the first useful number. A blind test of 100 production traces from a voice agent showed a different path. Human experts marked 39 kinds of failure, then the same hidden set went to several evaluation systems. Braintrust recovered 87.2% of the human-flagged failures. Codex on GPT-5.5 High reached 84.6% recall and 82.8% precision, ahead of LangSmith's 79.5% recall. Arize had 74.4% recall and the cleanest precision at 91.0%.

This was a contrast to the travel agent, not a fix for it: a general coding agent on a subscription many teams already pay for performed above two dedicated platforms. One conclusion followed plainly: similar results were available from the coding agent itself. Within four weeks, four evaluation vendors had shipped their expertise as skills for other coding agents. The category was unbundling into the terminal already open.

The installation commands matter less than two details. One set of skills builds evaluations; another pulls real production runs to supply the material. Install the first without the second and you have a framework with nothing to examine. The skills follow an open specification, so the same files can load into Codex, Cursor, Windsurf, or Goose. The reporting step returns prioritized recommendations tied to locations in the code.

Then the examiner has to act. A score that never changes behavior is analytics. An eval that changes the next edge is engineering. In the travel-agent case, an empty search result should have caused a refusal or a retry rather than a fabricated lookup. More generally, low context recall can reject a handoff; bad tool use can retry or swap a node; hallucination can quarantine a branch; schema failure can block an edge; compliance risk can route to a human; verified completion can terminate the run. Each verdict becomes a structural decision in the graph.

## Keep the judge honest

The examiner needs its own discipline. A judge from another model family is less likely to recognize its own writing and grade it kindly; one team uses Sonnet to judge Haiku for that reason. The rubric works best as one observable condition: “Pass iff [the successful outcome].” One primary verdict is easier to trust than a bundle of proxy scores.

Ordinary code can handle objective checks such as whether a test passed, a file exists, or state changed. The judge can handle semantic calls. Scores should not reward answer length, keywords, citation counts, exact phrasing, tool-call counts, or similarity to a reference. They should reward the outcome the agent was meant to produce.

The judge's version also belongs in the record. A silent upgrade makes scores before and after incomparable, and the problem can sit unnoticed for a month. Optimize against a judge long enough and the agent learns to look right rather than be right.

## Turn failures into permanent tests

Tests invented at a desk protect you from failures you imagined. The expensive failures are already in the logs, including the travel agent's quiet invention after an empty search.

A useful first sample contains 25 complete traces, with good and bad behavior beside each other: a normal successful request, one the user confirmed, one the user corrected or rephrased, a run with a failed, empty, or repeated tool call, and a run with an external failure such as a timeout or rate limit. Each trace records what the user asked and what the agent did, what worked, who caused the failure, and what capability an eval should preserve or improve.

Attribution saves time. The same lookup twice with identical arguments is an agent loop. A 429 is somebody else's limit unless the agent was supposed to recover from it. A trace records what happened, not what should have happened, so the answer key comes from tests, source records, policy, known state, or a person.

Each capability becomes its own hidden test folder. The agent sees the instruction and environment. It does not see the expected outcome, rubric, or judge credentials. Before the suite is trusted, the verifier must distinguish a clearly correct result from a plausible but wrong one. The environment must also withhold the answer until the agent reaches the tool. Anything that would cost money or write to production gets simulated.

The interview matters. The agent first maps the repository, reads the traces, proposes candidates, and recommends one before implementation. The definition of correct often lives in the user's head and nowhere in the model. Run this loop repeatedly and each incident becomes a test instead of a recurring surprise.

## Let evidence decide who reviews

An autonomous fleet otherwise ends at one human queue. A confidence score can decide which changes need that queue. Four signals are available when a pull request arrives: deterministic guardrails, the recent eval trajectory for this agent version, the historical revert rate for this repository and change class, and the sandbox outcome.

Above a threshold, the change merges. Below it, a human receives the failing signal instead of starting at line one. Three signals are history or deterministic checks; only one touches the model. Trust in an agent is an actuarial calculation, a track record with a price on it.

At one company, 19 of every 20 pull requests from a fully autonomous agent merge without human involvement. Across leading agents, about three quarters of merged work receives no human edit, reverts remain in the low single digits, and Guardrails rejects one pull request in five before review. One operator described the attitude behind it: “I don't trust them at all. I also don't trust my ability to code review their work. But I do trust my ability to constrain their work.”

The constraint is the product.

The warning is that a green suite can still guard a broken product. One team ran 285 iterations, merged 1,094 pull requests, and recorded zero regressions, yet 38 green tests coexisted with a completely broken product. The loop must converge on the specification, not merely on the score.

A cautious rollout keeps the gate in shadow mode for at least four hours of real traffic, compares automated and human verdicts within a 2% disagreement threshold, and samples 1% to 5% of traces instead of capturing everything. The gate stays closed on risky work and opens on the boring 80%. The model bill does not move. Everything else does.

## The small suite that stays alive

Three measurements cover the first pass for a tool-using agent: faithfulness to tool results, tool-parameter accuracy, and response quality. For code changes, the dimensions are intent and decision, execution and artifact, completeness and usefulness, instruction and boundary, and efficiency.

Dataset type matters. `final_response` tests only the answer. `single_step` isolates one decision. `trajectory` tests the whole path. `RAG` tests retrieval. Grading only the final response lets an agent reach a correct answer through a broken sequence.

The suite needs a size that survives ordinary work: 300 to 800 holdout cases, with 500 running in under five minutes. A suite longer than a coffee break stops being run. The first five evaluations cover an empty tool result, a repeated call, a boundary refusal, handoff integrity, and verified completion. Done must have an external signal, not the agent's own declaration.

The model will be replaced. The examiner remains: the failures turned into tests, the routing rules, and the track record that lets a machine merge its own work. The practical starting point is one skill, 25 traces, and one eval, followed by another whenever something breaks. After that afternoon, the system has a memory. It cannot break the same thing twice without leaving evidence.
