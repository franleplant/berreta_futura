---
source_ids:
- eval-engineering-the-step-that-turns-a-200-model-9f6f868f
content_mode: faithful_synthesis
label: FAITHFUL SYNTHESIS
---

A travel agent answered a simple trip question with an exchange rate, a weekly temperature, and museum hours. Every detail sounded clean. Every detail was invented. The search tool had returned nothing, so the model filled the gap and passed its guess off as a lookup. Across 100 real sessions, the team found 83.9% response quality and 32.3% faithfulness to tool results. The agent wrote beautifully and told the truth about a third of the time.

## The missing return arrow

A better model would not have caught this. What was missing was the layer that decides whether an answer was right, then changes what runs next.

Most teams have a thermometer: a dashboard, a score, or a Friday afternoon spent scrolling outputs and deciding they seem worse. Eval engineering adds the wire from the reading back to the system. A loop lets one agent try, inspect the result, and try again. A graph lets independent work run in parallel. The evaluator decides whether that speed produced useful work or twenty polished-looking failures.

“Everyone is renting the same brain now.” The model may cost about $200 a month, but the examiner records your definition of correct and every failure you feed it. That record improves while the rented model changes.

The first evidence came from a blind test of 100 production traces from a live voice agent. Researchers had a human expert mark 39 kinds of failure, hid those labels, and tested evaluation systems against the same pile. Braintrust Loop recovered 87.2% of the human-flagged failures. Codex on GPT-5.5 High reached 84.6% recall and 82.8% precision, ahead of LangSmith's 79.5% recall and close to dedicated platforms. Within four weeks, vendors began shipping their evaluation expertise as skills for coding agents. The category was moving into the terminal many teams already had open.

## Make the verdict move the run

A report alone changes nothing. “A score that never changes behavior is analytics. An eval that changes the next edge is engineering.”

The useful verdicts are routing decisions: low context recall rejects a handoff; bad tool use retries or swaps a node; hallucination quarantines a branch; a schema failure blocks an edge; a compliance risk routes to human review; verified completion terminates the run. The graph acts on the score while the work is still in progress.

The judge needs rules too. Use a model from another family when possible, because a model tends to recognize and grade its own style kindly. Write one observable pass condition rather than a bundle of proxy scores. Let ordinary code check objective facts such as whether a test passed, a file exists, or state changed. Do not reward response length, keywords, citation counts, exact phrasing, or similarity to a reference. Pin the judge's version and log it, or scores from different months cannot be compared. Optimize against a judge long enough and the agent learns to look right rather than be right.

## Let failures choose the tests

Tests invented at a desk protect you from failures you imagined. The failures that cost money are already timestamped in your logs.

A practical starting set has 25 complete traces, chosen so good and bad behavior sit close together: a normal successful request, one the user confirmed, one the user corrected or rephrased, one with a failed or repeated tool call, and one with an external timeout or rate limit. For each trace, record what the user asked and what the agent did, what worked and what did not, who caused the problem, and the capability the eval should preserve.

Attribution prevents wasted effort. The same lookup twice with identical arguments is an agent loop. A 429 is the dependency's limit, unless the agent was supposed to recover from it.

Turn each finding into a task folder with an instruction, an environment, and hidden tests. The recorded answer is evidence of what happened, not an answer key. Use source records, policy, known state, or a person to define correctness. Test the verifier with one clearly correct and one plausible but wrong result before trusting it. Make sure the environment does not reveal the answer before the agent reaches the tool. Simulate anything that would spend money or write to production.

The interview matters because the definition of correct usually lives in the team's head. Asking the owner to choose an eval beats one-shot generation. Run this loop often enough and an incident becomes a permanent test.

## Put a gate in front of the queue

Agents can open pull requests faster than people can review them. The escape route is a gate that combines four signals: deterministic guardrails, the recent eval trajectory for that agent version, the repository's historical revert rate for that class of change, and the sandbox result. A confidence score above the threshold merges automatically. A lower score sends the change to a human with the failing signal named.

Three of those signals come from history or deterministic checks. Only one touches the model. Trust becomes an actuarial calculation: a track record with a price on it.

At one company, 19 of every 20 pull requests from a fully autonomous agent merge without human involvement. Across leading agents, roughly three quarters of merged work needs no human edit, reverts remain in the low single digits, and Guardrails rejects one pull request in five before review. The operator who approved about 1,500 pull requests in 90 days explained the arrangement plainly: he trusted his ability to constrain the work, not the agents or his own ability to review every line.

Start in shadow mode for at least four hours of real traffic. Keep the gate closed while it scores. Set a 2% maximum disagreement between automated and human verdicts, and sample only 1% to 5% of traces. Open the gate first for the boring 80%, where the risk is understood.

The warning is that green scores can still guard a broken product. One team ran 285 iterations, merged 1,094 pull requests, and recorded zero regressions, yet reported that 38 green tests coexisted with a completely broken product. The loop must converge on the specification, not on the score.

## The afternoon that compounds

Begin with three measurements for a tool-using agent: faithfulness to returned data, tool-parameter accuracy, and response quality. For code changes, score intent and decision, execution and artifact, completeness and usefulness, instruction and boundary, and efficiency.

Choose the dataset shape deliberately: final response, one isolated step, the whole trajectory, or retrieval quality. A final-response score can praise a correct answer reached through a broken path. Hold out 300 to 800 cases, with 500 running in under five minutes. A suite longer than a coffee break stops being run.

Build the first five evals around common failure edges:

1. An empty tool result, where the agent must admit it has no number.
2. A repeated call with identical arguments.
3. A boundary refusal outside its permissions.
4. Handoff integrity between two nodes.
5. Verified completion based on an external signal rather than the agent's claim.

The model was never the interesting part. It is a rental, replaced while the examiner, the permanent tests, and the track record remain yours. That is what decides whether $200 on the card produces a demo or a business.

Most teams will keep scrolling outputs on Friday and deciding they feel about right. The teams that move first will pull 25 traces, build one eval, and add another whenever something breaks.
