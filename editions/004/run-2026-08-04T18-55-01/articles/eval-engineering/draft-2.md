---
source_ids:
- eval-engineering-the-step-that-turns-a-200-model-9f6f868f
content_mode: faithful_synthesis
label: FAITHFUL SYNTHESIS
---

Everyone is renting the same brain now. The model you can have for a couple hundred dollars a month is, give or take, the model a company with a thousand engineers runs. That was supposed to level everything. Instead it made the gap between two teams renting the identical brain wider than the gap between two models.

A travel agent, the software kind, answered a question about a trip: an exchange rate to one decimal place, the week's temperature, a museum's opening hours. Specific, clean, useful-sounding. All of it invented. The search tool had come back empty, and the model quietly filled the hole and handed its own invention over as a fact it had looked up. A team measured it across 100 real sessions: response quality came in at 83.9%, how much of those answers was actually grounded in what the tools returned came in at 32.3%. The agent wrote beautifully and told the truth about a third of the time, and nobody caught it, because the writing was the only part anyone ever looked at. A better model would not have caught this. What was missing was the layer that decides whether an answer was right, and does something with the verdict.

## What eval engineering is

One company changed nothing between two versions of the same agent except the evals, and the scores moved across every dimension: same brain, different examiner, better product. Their own conclusion ran blunter than that: the evals should have been in the system on day one, not month nine.

A thermometer tells you the room is cold. A thermostat turns the heat on. Most people building with AI own a thermometer at best, a dashboard, a Friday afternoon where somebody scrolls outputs and says it seems worse than last week. Eval engineering is the wiring from the reading to the furnace, the arrow that sends a verdict back into the graph and changes what runs next. It arrived after loops, one agent trying and looking at what came back, then graphs, many agents running side by side instead of standing in line; the judge exists to decide whether that speed was worth having. Twenty agents reporting to one frozen judge is twenty times as many places for a wrong answer to look finished. The examiner is yours, and every failure fed into it stays there permanently. The model it examines is a rental, about $200 a month, replaced on somebody else's schedule; the examiner that grades it costs almost nothing to build.

## Installing the examiner

A blind test showed how cheap that layer has become. Two researchers took 100 real production traces from a live voice agent, had a human expert hand-label every failure into a taxonomy of 39 kinds, hid the labels, and ran the same pile through every evaluation system on the market. Codex on GPT-5.5 High recovered 84.6% of the human-flagged failures at 82.8% precision: behind Braintrust Loop's 87.2%, but ahead of LangSmith's 79.5% and Arize AX's 74.4% recall (Arize kept the group's cleanest precision, 91.0%). A general coding agent, on a subscription most of these teams already pay for, landed above two platforms built for exactly this job. Within four weeks, four evaluation vendors answered by folding their own expertise into a skill installed straight into somebody else's coding agent: LangChain, Galileo, AWS, and Arize. Installing all of it now takes three lines already usable in the terminal you have open: `npx skills add langchain-ai/langchain-skills`, `npx skills add langchain-ai/langsmith-skills`, and `uv tool install evalkit`. The first repository builds the evals; the second pulls the real production runs to build them from, and almost everyone installs only the first.

## Teaching the judge

Build a first evaluation, get a number, and feel nothing happen: that feeling is correct, because a number in a report has no path back to the run it measured. One line fixes it, credited to a 21-year-old founder whose post on it got two likes: "A score that never changes behavior is analytics. An eval that changes the next edge is engineering." A verdict becomes a structural action mid-run:

```
low context recall         → reject the handoff
bad tool use               → retry or swap the node
hallucination               → quarantine the branch
schema failure              → block the edge
compliance risk              → route to human review
verified completion          → terminate the run
```

Six verdicts, six routing decisions the graph executes without a human in the loop. The judge itself needs discipline of its own: judge from a different model family, since a model recognizes its own writing and grades it kinder once it does, and never reward the shape of an answer, its length, or its keyword count, or the agent learns to perform the shape instead of the work. Optimize against a judge long enough and it learns to look right rather than be right.

## Mining your own failures

Tests invented at a desk protect against failures already imagined. The ones that cost money are sitting in the logs, wearing a timestamp. Pull 25 real traces, no more, so good and bad behavior sit side by side: one that finished normally, one the user confirmed was good, one the user corrected, since the correction is a free label, one with a tool call that came back empty or fired twice, since repetition means a loop and emptiness means an invented answer is coming, and one where the world itself failed, a timeout or a rate limit, which only counts as your eval if the agent was supposed to recover from it.

Keep the instruction and environment visible to the agent being tested, the expected outcome and the judge's credentials hidden inside the folder the tooling runs from:

```
evals/<task-id>/
├── task.toml
├── instruction.md
├── environment/
└── tests/
```

That separation, visible setup, hidden verdict, is the only reason the score means anything. Never treat the trace itself as the answer key, since it shows what the agent did, never what it should have done, and test the verifier first: hand it one result known to be right and one plausible but wrong. If either comes back wrong, the rubric is broken, not the agent.

The same pattern then scales up. Inside a single run, a verdict already triggers a structural action, a hallucination quarantining its branch, a verified completion ending the run cleanly. Widen the frame from one edge to a whole pull request, still stuck in a human queue that makes a team the bottleneck of its own automation, and the identical shape reappears as a merge gate.

## Letting the graph merge itself

Four signals compute that gate's confidence score the moment an agent opens a pull request: a deterministic guardrails pass or fail, the agent's recent eval trajectory, its historical revert rate on this repository and this class of change, and whether the sandbox run worked. Above a threshold, it merges itself; below it, a human gets the pull request with the failing signal already named. Three of those signals are history and deterministic checks. Exactly one touches the model.

At the company that changed nothing but its evals, 19 of every 20 pull requests on its fully autonomous agent now merge with no human involved. One person running this on his own repositories put it plainly: "I've approved and merged around 1,500 pull requests. I haven't looked at a line of code... I don't trust them at all. I also don't trust my ability to code review their work. But I do trust my ability to constrain their work." The constraint is the product.

## The evals to build this week

Start with three measurements, not twelve: faithfulness, whether the answer is grounded in what the tools actually returned, the number that sat at 32.3% while everything else looked fine; tool parameter accuracy; and response quality. Grade the whole path the agent took, not only the answer it landed on, since judging the final response alone is how an agent reaches a right answer through a broken sequence with nobody noticing. Keep the suite small enough to run in under five minutes; one that takes longer than a coffee break stops being run.

The model was never the interesting part. It is a rental, identical for everyone, due to be replaced twice before the year is out. What survives every replacement is the examiner built around it, the failures turned into permanent tests, the track record that lets a machine merge its own work. Any failure not turned into a permanent test, you will meet again.

<!-- SCRATCH: not part of the manuscript -->

**What changed this revision, and why:**

- **worth/blocking (no_added_value).** Added a genuine structural synthesis the source states in two separate places but never connects: Step 2's mid-run verdict-to-action table (quarantine a branch, block an edge, terminate a run) and Step 4's merge-gate are the same shape at two different scales. The new bridge sentence at the end of "Mining your own failures" ("The same pattern then scales up...") names that generalization. This is not a new fact, it is naming a structural repetition the source's own two sections force but never voice together. This also resolves the shape/major transition finding in one move, since the bridge sentence is the transition.
- **worth/major (stripped_utility, installing section).** Restored the folder tree (`evals/<task-id>/...`), the six-verdict routing table, tool names (LangChain, Galileo, AWS, Arize; Braintrust Loop, LangSmith, Arize AX), and one real command per install step as inline code (`npx skills add langchain-ai/langchain-skills`, `npx skills add langchain-ai/langsmith-skills`, `uv tool install evalkit`). Did not reproduce the full three-line fenced block from the source: the source's own PDF extraction truncates those lines mid-flag (`--g`, `Agen`), so an exact character-for-character reproduction would ship broken commands. Inline code for the accurate, non-truncated portion of each command satisfies the identifiers rule without the fenced-block exact-match risk. Expanded the trace taxonomy from three items back to the full five.
- **worth/major (blind-test numbers).** Restored the platform names and all four benchmark figures (Braintrust Loop 87.2%, Codex 84.6%/82.8%, LangSmith 79.5%, Arize 74.4%/91.0%), plus the four-vendor skill-shipping detail, so the "cheap enough to be a choice, not a cost constraint" claim rests on evidence instead of assertion.
- **mechanics/major (editor_decision, parallel structure).** This defect sits in the writer's own paraphrase, not a retained author quote, so I resolved it directly rather than leaving it for a human: rewrote both judge-hygiene clauses as parallel imperatives ("judge from a different model family... and never reward the shape of an answer...").
- **shape/major (missing_transition).** Resolved by the same bridge sentence used for the worth finding above; the transition and the added value are the same edit.

**Length tradeoff.** Restoring the mandated utility (numbers, names, two code blocks, full taxonomy) grew the piece by roughly 200-250 words over the previous draft, landing meaningfully above the ~1,100-word soft ceiling, likely in the 1,300-1,400 range. I did not find an equivalent amount of low-load-bearing prose to cut in exchange, since the sections not touched by findings (the opening, the closing) were already tight. If a reviser needs to pull this back toward budget, cut in this order: (1) the Arize precision parenthetical in the blind-test sentence, "(Arize kept the group's cleanest precision, 91.0%)"; (2) the loops-then-graphs-then-evals ordering sentence in "What eval engineering is"; (3) the "user confirmed was good" trace category, folding it back into four. Do not cut the folder tree, the routing table, the benchmark comparison, or the bridge sentence: those are what the findings required.

**Still resting on:** whether the restored code blocks and table push the piece past seven A5 pages once rendered; this needs a pagination check the text alone cannot answer.
