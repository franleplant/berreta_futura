---
source_ids:
- eval-engineering-the-step-that-turns-a-200-model-9f6f868f
content_mode: faithful_synthesis
label: FAITHFUL SYNTHESIS
---

A travel agent, the software kind, answered a question about a trip: an exchange rate to one decimal place, the temperature for the week, the opening hours of a museum. All of it invented. The search tool had come back empty, and the model quietly filled the hole and handed its own invention over as a fact it had looked up. Nobody caught it, because the writing was the only part anyone ever looked at.

Then the team measured it across 100 real sessions and got two numbers that should never sit that far apart. How good the answers were: 83.9%. How much of those answers was grounded in what the tools actually returned: 32.3%. The agent wrote beautifully and told the truth about a third of the time. A better model would not have caught this. What was missing was the layer that decides whether an answer was right and then does something with the verdict, the one line in the stack nobody can sell you, because it encodes your own definition of correct.

The model you rent for a couple of hundred a month is, give or take, the model a company with a thousand engineers is running, and the gap between two teams renting the identical brain is now wider than the gap between two models. One company changed no model, no prompts and no human nudges across successive versions of its agent, only the evals, and every score moved. Their own conclusion afterwards: the evals should have been in the system on day one, not month nine.

A thermometer tells you the room is cold. A thermostat turns the heat on. Almost everyone building with AI owns a thermometer at best, a dashboard or a feeling, and eval engineering is the wiring that runs from the reading to the furnace: the verdict goes back into the graph of agents and changes what runs next.

## Where the tests come from

Tests you invent from imagination protect you from failures you already imagined. The ones that cost money are sitting in your logs right now, wearing a timestamp. Pull 25 complete traces, no more, chosen so good and bad behavior sit next to each other: one that finished normally, one the user confirmed, one the user corrected (the correction is the label, free of charge), one with a failed, empty or repeated tool call, and one where a timeout or a rate limit made the world say no.

Attribution is where beginners lose a week. The same lookup called twice with identical arguments is a loop in your agent; a 429 is somebody else's limit, and it only becomes your eval if your agent was supposed to recover from it. And never treat the recorded answer as truth: the trace tells you what your agent did, never what it should have done, so the answer key comes from tests, records, policy or a person.

Installing the machinery is three lines, `npx skills add` twice and `uv tool install evalkit`, and the two repositories do two jobs: `langchain-skills` builds the evals, `langsmith-skills` pulls the real production runs to build them from. Almost everyone installs the first and then wonders where the material comes from. `evalkit init` lays out the folder each finding turns into: `task.toml`, `instruction.md`, `environment/`, `tests/`. The agent being tested sees the instruction and the environment; the rubric and the expected outcome stay hidden, and that is the only reason the score means anything. `/evalkit.report`, last of the six commands, points its recommendations at specific locations in your code.

The first eval to build is the one the travel agent would have failed: the tool comes back empty, and the agent has to say so instead of inventing the number.

## What a score is allowed to do

You will get your first number and feel nothing happen. That feeling is correct: a number in a report has no path back to the run it measured. One line fixes the whole discipline, and it belongs to a 21-year-old founder in Tokyo: "A score that never changes behavior is analytics. An eval that changes the next edge is engineering."

His wiring is six rules, each taking a verdict and doing something structural to the run in progress. Low context recall rejects the handoff. Bad tool use retries or swaps the node. A hallucination quarantines the branch, a schema failure blocks the edge, a compliance risk routes to human review, and a verified completion terminates the run. The eval steers the run mid-flight, one edge at a time.

Judge with a model from another family, because a model recognizes its own writing and grades it kinder once it does, and never score the shape of an answer, its length or its keywords or its citation count. Optimize against a judge long enough and the agent learns to look right rather than be right.

## The gate that merges itself

Every pull request an agent opens lands in a human queue, and you become the bottleneck of your own automation. Four signals are already available when an agent opens one, and the gate scores its confidence from them: guardrails pass or fail on the blocking standards, how this version has been scoring lately, how often its work has been rolled back before, and whether the sandbox run worked. Three of the four are history and deterministic checks, and exactly one touches the model at all. Above the threshold the request merges itself; below it, a human gets it with the failing signal named.

Somebody running this pattern on his own repositories put it in a way no vendor would: "In the past 90 days, I've approved and merged around 1,500 pull requests. I haven't looked at a line of code. How can I put so much trust in agents? I don't trust them at all. I also don't trust my ability to code review their work. But I do trust my ability to constrain their work."

The warning worth more than the formula comes from a team that ran a self-improving codebase to 1,094 merged pull requests and zero regressions: 38 green tests coexisted with a completely broken product, which is why the loop has to converge on the spec rather than on the score.

## The people who go first

Most people will go back to scrolling outputs on a Friday and deciding it feels about right. The ones who go first spend one afternoon wiring the thermostat, and then spend the next year with an agent that cannot break the same thing twice. Install one skill. Pull 25 traces. Build one eval today, and add one every time something breaks.
