---
source_ids:
- eval-engineering-the-step-that-turns-a-200-model-9f6f868f
content_mode: faithful_synthesis
label: FAITHFUL SYNTHESIS
---

Everyone rents the same brain. The difference between teams is the examiner they build around it.

A travel agent scored 83.9% on response quality and 32.3% on faithfulness — the same run, the same day. It wrote beautifully and told the truth a third of the time. Nobody noticed, because the writing was the only part anyone looked at.

A better model would not have caught that. What was missing was the layer that decides whether an answer was right and then does something with the verdict. Install it with three commands, wire six verdicts to six actions, mine your own logs for the tests, and let the graph merge its own work. One afternoon.

## The examiner you already own

Two researchers took 100 production traces from a live voice agent, had an expert hand-label 39 failures, hid the labels, and handed the pile to every evaluation system on the market. Braintrust Loop recovered 87.2%. Codex on GPT-5.5 High, 84.6% recall at 82.8% precision. LangSmith 79.5%. Arize AX 74.4%, with the cleanest precision at 91.0%.

A general coding agent, on a subscription you already pay for, beat two dedicated platforms. Within four weeks the platforms moved in: LangChain, Galileo, AWS under Apache 2.0, and Arize all shipped their expertise as skills for somebody else's coding agent. A category unbundling itself into the terminal you have open.

```
npx skills add langchain-ai/langchain-skills --skill '*' --yes --g
npx skills add langchain-ai/langsmith-skills --skill '*' --yes --g
uv tool install evalkit --from git+https://github.com/awslabs/Agen
```

Two repositories, two jobs: one builds the evals, the other pulls the production runs to build them from. Most people install the first and then wonder where the material comes from. The files follow the open skills spec, so they load into Codex, Cursor, Windsurf and Goose too.

## A verdict that changes the next edge

You will get your first number, look at it, and feel nothing happen. That is correct. A number in a report has no path back to the run it measured.

A thermometer says the room is cold. A thermostat turns the heat on. The wiring is six rules:

```
low context recall    → reject the handoff
bad tool use          → retry or swap the node
hallucination         → quarantine the branch
schema failure        → block the edge
compliance risk       → route to human review
verified completion   → terminate the run
```

The judge needs hygiene of its own. Grade with another family — a model recognises its own writing and is kind to it. Write the rubric as one line: *Pass iff [the independently observable successful outcome]*. Let plain code decide the objective calls and the judge decide the semantic ones. Never score length, keywords, citation count, phrasing, tool-call count or similarity to a reference: reward the shape and the agent learns the shape. Pin the judge and log its version, or a month of scores becomes unreadable after the fact.

## Where the tests come from

Tests you invent protect you from failures you already imagined. The expensive ones are in your logs, wearing a timestamp.

Pull 25 complete traces, no more, chosen so good and bad sit side by side: one clean run, one the user confirmed, one the user corrected — the correction is a free label — one with a failed, empty or repeated tool call, one where the world said no. Write each up in four lines: observed behaviour, comparison, attribution, eval candidate.

Attribution is where the week goes. The same lookup twice with identical arguments is your loop. A 429 is somebody else's limit, and becomes your eval only if your agent was meant to recover.

Then the finding becomes a folder: `task.toml`, `instruction.md`, `environment/`, `tests/`. One capability each. The instruction and environment are visible to the agent under test; the expected outcome, the rubric and the judge are not. That partition is the only reason the score means anything.

Never treat the recorded answer as truth — the trace says what your agent did, not what it should have done. Test the verifier first with two hand-written results, one right and one plausibly wrong. Watch for an environment that hands over the answer before the agent reaches the tool: that task passes forever and measures nothing. Simulate anything that costs money or writes to production.

## Letting the graph merge

Every pull request an agent opens lands in a human queue, and your fleet runs at the speed of one tired reviewer.

Four signals are already there when it opens: a deterministic guardrails pass or fail, the recent eval trajectory for this exact version, the historical revert rate for this agent on this repository on this class of change, and whether the sandbox ran. Three are history and arithmetic; one touches the model. Above the threshold it merges itself; below it, a human gets it with the failing signal named, so review starts at the problem.

Trust in an agent is an actuarial calculation. You are building a track record with a price on it.

At one company, 19 of every 20 pull requests on the fully autonomous agent merge untouched; about three quarters of merged work goes in with no human edit, reverts stay in low single digits, and guardrails alone bounce one in five before anyone looks.

The warning is worth more than the formula. A team ran 285 iterations, 1,094 merged pull requests, zero regressions, and reported this: 38 green tests coexisted with a completely broken product. A suite can go all green while the thing it guards falls apart — a map so detailed it covers the territory and hides it. Converge on the spec, not the score.

So: run the gate in shadow for at least four hours of real traffic, merging nothing. Hold a 2% deviation threshold between machine and human verdicts; above it the gate stays shut. Sample traces at 1–5%.

## This week

Three measurements, not twelve. Faithfulness — the one that sat at 32.3%. Tool parameter accuracy. Response quality. If your agent ships code, score the change instead: intent and decision, execution and artifact, completeness and usefulness, instruction and boundary, efficiency.

Pick one dataset type on purpose: `final_response`, `single_step`, `trajectory`, or RAG. Grade only the final response and you will never see the correct answer reached through a broken sequence.

Hold out 300 to 800 cases and keep 500 running in under five minutes. A suite longer than a coffee break stops being run.

The five evals: empty tool result, where the agent must say so rather than invent the number. Repeated call — same arguments twice is a loop, and the eval fails it. Boundary refusal, declining cleanly instead of hunting for a route around. Handoff integrity, where what one node produced is what the next one reads. Verified completion, where done means a real signal says done.

The model is a rental and will be replaced twice before the year ends. What survives every replacement is the catalogue: failures turned into permanent tests, verdicts wired to edges, a track record that lets a machine merge its own work. It only grows.

Measure the path, not just the answer. A verdict that changes nothing is a report. Any failure you do not turn into a test, you will meet again.
