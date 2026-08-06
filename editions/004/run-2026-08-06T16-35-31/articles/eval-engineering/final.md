---
source_ids:
- eval-engineering-the-step-that-turns-a-200-model-9f6f868f
content_mode: faithful_synthesis
label: FAITHFUL SYNTHESIS
---

Everyone rents the same brain. What differs is the examiner you build around it. One travel agent scored 83.9% on answer quality and 32.3% on whether those answers came from its tools — it wrote beautifully and told the truth a third of the time, and nobody caught it because the writing was the only part anyone read. So: install an eval skill into the coding agent you already pay for, mine 25 real traces for failures, turn each failure into a permanent test whose verdict changes what the graph does next, and let a confidence score decide which pull requests merge. One afternoon. The model bill does not move.

## The layer nobody sells you

The search tool came back empty. The model filled the hole and handed its invention over as a fact it had looked up. A better model would not have caught that. What was missing was the layer that decides whether an answer was right and then does something with the verdict.

A thermometer says the room is cold. A thermostat lights the furnace. Most people building with AI own a dashboard and a Friday feeling.

One company running agents in production changed no model, no prompts, no human nudges — only the evals — and every score moved. Their conclusion: the evals should have been there on day one, not month nine.

The order was always loops, then graphs, then evals. Graphs made you fast. Twenty agents at once is twenty places for a wrong answer to look finished.

## The examiner you already own

Two researchers took 100 production traces from a live voice agent, had an expert label 39 failures by hand, hid the labels, and handed the pile to every evaluation system on the market. Braintrust Loop recovered 87.2%. Codex on GPT-5.5 High: 84.6% recall, 82.8% precision. LangSmith 79.5%. Arize AX 74.4% recall at 91.0% precision.

A general coding agent beat two dedicated platforms. Within four weeks the platforms moved in — LangChain on 22 July, then Galileo, AWS under Apache 2.0, Arize. Each shipped its expertise as a skill installed into somebody else's coding agent. A category unbundling itself into a terminal you already have open.

```
npx skills add langchain-ai/langchain-skills --skill '*' --yes --g
npx skills add langchain-ai/langsmith-skills --skill '*' --yes --g
uv tool install evalkit --from git+https://github.com/awslabs/Agen
```

Two repositories, two jobs: one builds the evals, the other pulls the production runs to build them from. People install the first and wonder where the material comes from. The files follow the open skills spec, so they load into Codex, Cursor, Windsurf, Goose.

The AWS kit runs six phases into an `eval/` folder — `plan`, `data`, `trace`, `run_agent`, `eval`, `report`. The last hands back recommendations pointing at specific lines of your code.

## A verdict that moves an edge

A score that never changes behaviour is analytics. Six rules turn one into engineering:

```
low context recall   → reject the handoff
bad tool use         → retry or swap the node
hallucination        → quarantine the branch
schema failure       → block the edge
compliance risk      → route to human review
verified completion  → terminate the run
```

Each is a routing decision the graph executes mid-flight.

The judge needs hygiene of its own. Grade with another model family; a model recognises its own writing and marks it kindly. Write the rubric as one line — *Pass iff the independently observable outcome* — one verdict, not a bundle. Let code decide the objective calls and the judge the semantic ones. Never score length, keywords, citation count, phrasing or similarity to a reference; reward the shape and the agent learns the shape. Pin the judge and log its version, or a month of scores becomes unreadable after the fact.

## Where the tests come from

Tests you invent protect you from failures you already imagined. Pull 25 complete traces, no more: one normal success, one the user confirmed, one the user corrected, one with a failed or repeated tool call, one where the world said no with a timeout or a 429. Write each up in four lines — observed behaviour, comparison, attribution, eval candidate.

Attribution costs beginners a week. The same lookup twice with identical arguments is your loop. A rate limit is somebody else's, and becomes your eval only if the agent was meant to recover.

Then the finding becomes a folder: `task.toml`, `instruction.md`, `environment/`, `tests/`. One capability each. The instruction and environment are visible to the agent under test; the expected outcome, the rubric and the judge are not, and that wall is the only reason the number means anything.

Three rules stop the failures that make people quit. The trace shows what your agent did, never what it should have done — take the answer key from tests, records, policy, state or a person. Feed the verifier one clearly correct and one plausibly wrong result by hand before you trust it. And check that the environment isn't handing over the answer before the agent reaches the tool. Simulate anything that costs money or writes to production.

Ask for one candidate at a time and make the agent interview you first. The definition of correct lives in your head and nowhere in the model.

## Letting the graph merge

Every pull request an agent opens lands in a human queue, and your fleet runs at the speed of one tired reviewer.

Four signals are already sitting there when the request opens: a deterministic guardrails pass or fail, this version's recent eval trajectory, its historical revert rate on this repository and this class of change, and whether the sandbox ran. Three are history and arithmetic; one touches the model. Above the threshold it merges itself; below it, a human receives it with the failing signal named, so review starts at the problem.

Trust in an agent is an actuarial calculation, and the track record sharpens whether or not the models improve.

At that same company, 19 of every 20 pull requests on the fully autonomous agent merge untouched; across the top agents about three quarters of merged work goes in with no human edit, reverts stay in the low single digits, and guardrails bounce one in five before anyone looks. A man running the pattern on his own repositories put it best: around 1,500 pull requests merged in 90 days without reading a line. *I don't trust them at all. I also don't trust my ability to code review their work. But I do trust my ability to constrain their work.*

The warning is worth more than the formula. A team ran 285 iterations of a self-improving codebase to 1,094 merged pull requests and zero regressions, and reported that 38 green tests coexisted with a completely broken product. Converge on the spec, not the score.

Turn it on carefully: shadow mode for at least four hours of real traffic, scoring everything and merging nothing; the gate stays shut if automated and human verdicts disagree by more than 2%; sample traces at 1–5%.

## This week

Three measurements, not twelve. Faithfulness — is the answer grounded in what the tools returned. Tool parameter accuracy — right tool, right arguments. Response quality. If the agent ships code, score the change instead: intent and decision, execution and artifact, completeness and usefulness, instruction and boundary, efficiency.

Choose the dataset type deliberately: `final_response`, `single_step`, `trajectory`, or RAG. Grade only the final response and an agent will reach the right answer through a broken sequence with nobody noticing.

Hold out 300 to 800 cases and keep 500 of them running in under five minutes. A suite longer than a coffee break stops being run.

The first five: an empty tool result the agent must admit to rather than fill; the same call twice, which is a loop and fails; a request outside its permissions, declined cleanly with no hunt for a route around; handoff integrity, where the next node reads exactly what the last one produced; and verified completion, where done means a real signal, never the agent's own word.

The model is a rental and will be replaced twice this year. What survives is the examiner — a small permanent library of every way you have already been wrong, which no vendor can sell you because it is written in your own hand. Install one skill. Pull 25 traces. Build one eval today, and one more each time something breaks.
