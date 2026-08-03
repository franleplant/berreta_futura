---
source_id: eval-engineering-the-step-that-turns-a-200-model-9f6f868f
content_mode: faithful_synthesis
label: FAITHFUL SYNTHESIS
---

Everyone is renting the same brain now. The model available for a few hundred dollars a month is close to the model a company with a thousand engineers can access. That was supposed to level the field. Instead, it made the gap between teams using the same model depend on what surrounds it.

A travel agent answered with an exchange rate, a weekly forecast, and museum hours. The result was specific and useful-sounding. It was also invented. The search tool had returned nothing, and the model silently filled the hole.

Across one hundred real sessions, answer quality scored 83.9 percent while grounding in actual tool results scored 32.3 percent. The agent wrote beautifully and told the truth about a third of the time.

## What eval engineering is

Evaluation becomes engineering when a score changes what the system does next. The work is not a dashboard beside the agent. It is the control layer inside the agent: whether to accept a handoff, retry a tool call, swap a node, quarantine a branch, block an edge, ask for clarification, or route work to a person.

The model is rented. The examiner is yours. Every production failure you turn into a permanent test remains useful after the model, orchestration framework, and vendor change.

The sequence is simple: loops, then graphs, then evals. A loop gives the agent another attempt. A graph gives the attempt somewhere to go. An eval decides which edge the result is allowed to take.

## The examiner you already own

Many teams assume evaluation begins with a platform contract and months of setup. That assumption is outdated.

In one blind comparison, researchers collected one hundred real voice-agent traces, had a human expert label thirty-nine failure types, hid those labels, then compared evaluation systems. Braintrust Loop recovered 87.2 percent of the human-flagged failures. Codex on GPT-5.5 High reached 84.6 percent recall and 82.8 percent precision. LangSmith reached 79.5 percent. Arize AX reached 74.4 percent recall with 91.0 percent precision.

A general coding agent landed above two dedicated platforms. The platforms then began packaging their expertise as installable skills for the coding agents people already use.

The operational point is not which row won. Evaluation knowledge is becoming portable. One tool can pull production traces, another can scaffold an evaluation, and a coding agent can inspect the application, write graders, run the cases, and produce a report. The first useful eval no longer requires a new control plane.

Start with real traces. Pull a bounded sample, inspect the application, identify the user-visible failure, and define what success means before writing the grader. The examiner should know the system it is judging.

## Make the score change the next edge

A number that never changes behavior is analytics.

Low context recall can reject a handoff. Bad tool use can trigger a retry or swap the responsible node. A hallucination can quarantine the branch. A schema failure can block an edge. Compliance risk can route the trace to human review.

These are graph decisions, not report annotations. The evaluator must return structured output that the orchestrator can use. It also needs calibration. A cheap judge can screen routine runs, while disputed or high-risk cases move to a stronger judge or a human.

Do not reward the shape of an answer. A fluent response with headings and citations can still be ungrounded. Grade the property that matters: whether claims follow from tool output, whether the correct tool was selected, whether the answer satisfies the task, and whether the route was safe.

## Turn failed runs into permanent tests

Tests invented from imagination protect against failures you already imagined. Production traces contain the failures your system actually produced.

Mine traces, identify one failure, build an eval, improve the agent, and keep the eval. Begin with about twenty-five complete traces chosen for information value: a known bad run, a confirmed good run, an unexpected route, a costly retry, or an external failure the agent handled poorly.

The recorded answer is not truth. A trace shows what happened, not what should have happened. Write the rubric against the task and available evidence. Separate external failures from agent failures. A rate limit becomes your evaluation only when the agent's response to the rate limit was wrong.

Each case needs the context the agent could see, the action it took, the expected property, and a grader that explains failure. Store the cases beside the system so changes to prompts, tools, policies, and models can run against the same history.

The result is a ratchet. Every failure becomes harder to repeat.

## Let confidence govern review

An autonomous coding system can evaluate its own pull request before asking for human attention. The merge decision can combine automated checks, policy rules, recent eval trajectory, change risk, and confidence in the generated result.

Above the threshold, the system can merge. Below it, a person receives the change with the failing signal already named. Review begins at the problem instead of line one.

This should begin in shadow mode. Score every change and merge none. Compare the gate with actual review outcomes, then automate only the high-confidence region. Keep hard policy blocks separate from probabilistic scores. Sample a small percentage of traces for deeper inspection instead of retaining everything forever.

The objective is not to remove humans. It is to spend human attention where uncertainty and consequence meet.

## The first evals

Build faithfulness first: is the answer grounded in what the tools returned? Then test tool selection, task completion, schema conformance, and policy compliance. Add retrieval metrics when the system depends on search.

Measure pass rate, cost, and latency. Keep a dataset of real failures. Add one case every time the system surprises you.

The model will be replaced. The graph will be rewritten. The examiner survives both because it contains your accumulated definition of acceptable behavior.

Any failure you do not turn into a permanent test is a failure you have agreed to meet again.
