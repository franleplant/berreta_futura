---
source_ids:
- eval-engineering-the-step-that-turns-a-200-model-9f6f868f
content_mode: faithful_synthesis
label: FAITHFUL SYNTHESIS
---

A travel agent answered a simple trip question with an exchange rate, a weekly temperature, and museum hours. Every detail sounded clean. Every detail was invented. The search tool had returned nothing, so the model filled the gap and passed its guess off as a lookup. Across 100 real sessions, the team found 83.9% response quality and 32.3% faithfulness to tool results. The agent wrote beautifully and told the truth about a third of the time.

## The missing return arrow

A better model would not have caught this. What was missing was the layer that decides whether an answer was right, then changes what runs next.

One company changed only its evals across successive versions of the same agent. The model, prompts, and human nudges stayed fixed, yet scores moved across every dimension. Their conclusion was blunt: the evals should have been in the system on day one, not month nine.

Most teams have a thermometer: a dashboard, a score, or a Friday afternoon spent scrolling outputs and deciding they seem worse. Eval engineering adds the wire from the reading back to the system. A loop lets one agent try, inspect the result, and try again. A graph lets independent work run in parallel. The evaluator decides whether that speed produced useful work or twenty polished-looking failures.

“Everyone is renting the same brain now.” The model may cost about $200 a month, but the examiner records your definition of correct and every failure you feed it. That record improves while the rented model changes.

A blind test made the difference concrete. Researchers took 100 production traces from a live voice agent, had a human expert mark 39 kinds of failure, hid those labels, and tested evaluation systems against the same pile. Braintrust Loop recovered 87.2% of the human-flagged failures. Codex on GPT-5.5 High reached 84.6% recall and 82.8% precision, while LangSmith scored 79.5%. Within four weeks, vendors began shipping their evaluation expertise as skills for coding agents. The category was moving into the terminal many teams already had open.

## Make the verdict move the run

A report alone changes nothing. “A score that never changes behavior is analytics. An eval that changes the next edge is engineering.”

The travel agent's empty search result should have produced a verdict while the run was still alive. Low context recall could reject its handoff and force another search. A hallucination could quarantine the branch. Bad tool use could retry or swap the node. A schema failure could block the edge, a compliance risk could route to human review, and verified completion could terminate the run. Each verdict is a routing decision, not a note attached after the fact.

The judge needs discipline of its own. A model from another family is less likely to recognize and reward its own habits. The rubric should state one independently observable pass condition, while ordinary code checks facts such as whether a test passed, a file exists, or state changed. Scores should ignore response length, keywords, citation counts, exact phrasing, and similarity to a reference. Pin the judge's version and log it, or scores from different months cannot be compared. Optimize against a judge long enough and the agent learns to look right rather than be right.

Now the travel trace has somewhere to go. The empty result is a hidden test, the faithfulness verdict changes the next edge, and a later run can show whether the agent recovered instead of inventing the number.

## Let failures choose the tests

Tests invented at a desk protect you from failures you imagined. The failures that cost money are already timestamped in your logs.

A useful first sample is 25 complete traces, chosen so good and bad behavior sit close together: a normal successful request, one the user confirmed, one the user corrected or rephrased, one with a failed or repeated tool call, and one with an external timeout or rate limit. The travel-agent session belongs here because its empty search result gives you a concrete failure to preserve. Each trace gets four lines: what the user asked and what the agent did, what worked and what did not, who caused the problem, and the capability the eval should preserve.

Attribution prevents wasted effort. The same lookup twice with identical arguments is an agent loop. A 429 is the dependency's limit, unless the agent was supposed to recover from it. In the travel case, the search tool's emptiness was external, but presenting an invented exchange rate was the agent's failure.

Each finding becomes a task folder with an instruction, an environment, and hidden tests. The recorded answer is evidence of what happened, not an answer key. Correctness comes from source records, policy, known state, or a person. The verifier earns trust only after it sends one clearly correct result and one plausible but wrong result down the right paths. The environment must not reveal the answer before the agent reaches the tool. Anything that would spend money or write to production gets simulated.

The interview matters because the definition of correct usually lives in the team's head. Asking the owner to choose an eval beats one-shot generation. Run this loop often enough and the travel-agent incident becomes a permanent test instead of a surprising anecdote.

## Put a gate in front of the queue

Agents can open pull requests faster than people can review them. The escape route is a gate that combines four signals: deterministic guardrails, the recent eval trajectory for that agent version, the repository's historical revert rate for that class of change, and the sandbox result. A confidence score above the threshold merges automatically. A lower score sends the change to a human with the failing signal named.

Three of those signals come from history or deterministic checks. Only one touches the model. Trust becomes an actuarial calculation: a track record with a price on it.

At one company, 19 of every 20 pull requests from a fully autonomous agent merge without human involvement. Across leading agents, roughly three quarters of merged work needs no human edit; reverts remain in the low single digits, and Guardrails rejects one pull request in five before review. The operator who approved about 1,500 pull requests in 90 days explained the arrangement plainly: he trusted his ability to constrain the work, not the agents or his own ability to review every line.

The travel agent's faithfulness score can become one of those gate signals. If a new version keeps inventing data after empty searches, its confidence falls and the run goes to a person. The safe start is shadow mode for at least four hours of real traffic, with the gate closed while it scores. A 2% maximum disagreement between automated and human verdicts keeps the gate closed when the measures diverge. Sampling 1% to 5% of traces limits the cost. The boring 80%, where the risk is understood, is the first slice to pass automatically.

The warning is that green scores can still guard a broken product. One team ran 285 iterations, merged 1,094 pull requests, and recorded zero regressions, yet reported that 38 green tests coexisted with a completely broken product. The loop must converge on the specification, not on the score.

## The afternoon that compounds

A tool-using agent can begin with three measurements: faithfulness to returned data, tool-parameter accuracy, and response quality. Faithfulness is the measurement that exposed the travel agent. For code changes, production teams score intent and decision, execution and artifact, completeness and usefulness, instruction and boundary, and efficiency.

The dataset shape determines what the score can see: final response, one isolated step, the whole trajectory, or retrieval quality. A final-response score can praise a correct answer reached through a broken path. A holdout of 300 to 800 cases keeps the suite useful, with 500 running in under five minutes. A suite longer than a coffee break stops being run.

The first five evals follow common failure edges: an empty tool result where the agent must admit it has no number; a repeated call with identical arguments; a boundary refusal outside its permissions; handoff integrity between two nodes; and verified completion based on an external signal rather than the agent's claim. The travel-agent trace supplies the first one and gives the rest a standard: measure the path, then make the verdict alter it.

The model was never the interesting part. It is a rental, replaced while the examiner, the permanent tests, and the track record remain yours. That is what decides whether $200 on the card produces a demo or a business.

A failure becomes a test, the test changes the next edge, and the next run leaves a better record.
