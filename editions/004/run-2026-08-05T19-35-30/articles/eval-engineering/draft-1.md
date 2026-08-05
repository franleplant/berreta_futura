---
source_ids:
- eval-engineering-the-step-that-turns-a-200-model-9f6f868f
content_mode: faithful_synthesis
label: FAITHFUL SYNTHESIS
---

Everyone is renting the same brain now. The model a company can run for a couple of hundred dollars a month is, give or take, the model a company with a thousand engineers is running. The gap has moved somewhere else.

A software travel agent answered a simple trip question with an exchange rate, a weekly temperature, and museum hours. It sounded clean and useful. All of it was invented. The search tool had returned nothing, so the model filled the gap and passed its invention off as a lookup. Across 100 real sessions, the team found response quality of 83.9% and faithfulness of 32.3%. The agent wrote beautifully and told the truth about a third of the time.

A better model would not have caught this. What was missing was the layer that decides whether an answer was right and then changes what runs next. A thermometer tells you the room is cold. A thermostat turns the heat on. Most teams have the thermometer: a dashboard, or a Friday afternoon spent scrolling through outputs and deciding that things seem worse. Eval engineering is the wiring from the reading to the furnace.

Loops came first, then graphs, then evals. An agent in a loop could try, inspect what came back, and try again. A graph let independent work run side by side. Evals decide whether that speed was worth having. Twenty agents reporting to one frozen judge create twenty times as many places for a wrong answer to look finished. The model is a rental. The examiner is yours, and every failure you feed it stays there.

## Install the examiner

You do not need to begin with a new platform. Two researchers tested 100 production traces from a voice agent, had a human expert label 39 kinds of failure, hid those labels, and gave the same cases to evaluation systems. Braintrust Loop recovered 87.2% of the human-flagged failures. Codex on GPT-5.5 High reached 84.6% recall and 82.8% precision, above LangSmith at 79.5% and close to the dedicated tools. A coding agent you already pay for was competitive with evaluation platforms.

The category responded by moving into the terminal. LangChain, Galileo, AWS under Apache 2.0, and Arize shipped their evaluation knowledge as skills for coding agents. The same files can load into Claude Code, Codex, Cursor, Windsurf, or Goose. Installing the examiner takes commands such as `npx skills add langchain-ai/langchain-skills --skill '*' --yes --global` and `uv tool install evalkit --from git+https://github.com/awslabs/Agent...`; inside Claude Code, the equivalent is `/plugin marketplace add langchain-ai/langchain-skills` followed by `/plugin install langchain-skills@langchain-skills`.

The important distinction is between the repositories. `langchain-skills` builds evals; `langsmith-skills` pulls real production runs to build them from. AWS's kit scaffolds a project with `evalkit init my-agent-evaluation`, then runs `/evalkit.plan`, `/evalkit.data`, `/evalkit.trace`, `/evalkit.run_agent`, `/evalkit.eval`, and `/evalkit.report`. That last command returns prioritized recommendations pointing to locations in your code.

## Make the score change the run

A number in a report has no path back to the execution it measured. “A score that never changes behavior is analytics. An eval that changes the next edge is engineering.”

The wiring is direct. Low context recall rejects a handoff. Bad tool use retries or swaps the node. A hallucination quarantines the branch. A schema failure blocks the edge. Compliance risk routes to human review. Verified completion terminates the run. Each verdict becomes a routing decision in the graph.

The judge needs rules too. Use a model from another family when possible, because a model grading its own family can share its blind spots. Write one observable success condition: `Pass iff [the independently observable successful outcome]`. Let the judge handle semantic calls and ordinary code handle objective ones such as whether a test passed, a file exists, or state changed. Do not reward response length, keywords, citation counts, exact phrasing, tool-call counts, or similarity to a reference. Pin the judge and log its version, or a silent upgrade will make a month of scores impossible to compare.

Optimize against a judge long enough and the agent learns to look right rather than be right. The score must remain connected to the work.

## Turn failures into permanent tests

Invented tests protect you from failures you imagined. The expensive failures are already in your logs. Start with 25 complete traces, chosen so good and bad behavior sit beside each other: a normal request, a user-confirmed success, a correction or rephrasing, a failed or repeated tool call, and an external failure such as a timeout or rate limit.

Write each finding in four lines: observed behavior, comparison, attribution, and an eval candidate. Attribution matters. The same lookup twice with identical arguments is your agent looping. A 429 is somebody else's limit unless your agent was supposed to recover from it.

Then give each capability its own folder, such as `evals/<task-id>/` containing `task.toml`, `instruction.md`, `environment/`, and `tests/`. The agent sees the instruction and environment. The expected outcome, rubric, and judge credentials stay hidden. Never treat the recorded answer as truth; it records what happened, not what should have happened. Test the verifier with one clearly correct result and one plausible wrong result. Make sure the environment does not reveal the answer before the agent reaches the tool. Simulate anything that costs money or writes to production.

The instruction that starts the process is simple: use the eval-engineering skill, map the repository's agent and its backing data, read the 25 traces, propose candidates grounded in failures, recommend one, and wait before implementing. The interview is deliberate. The definition of correct lives in the team's head and nowhere in the model. Run this loop often enough and each incident becomes a test.

## Let safe work merge itself

Every pull request an agent opens otherwise lands in a human queue. A confidence score can combine four signals: deterministic guardrails, the recent eval trajectory for this agent, its historical revert rate on this repository and change class, and whether it passed the sandbox. Above the threshold, merge it. Below it, send a human the failing signal so review starts at the problem.

Trust in an agent is an actuarial calculation. In one production system, 19 of every 20 pull requests from a fully autonomous agent merged without human involvement. Across top agents, about three quarters of merged work required no human edit, reverts stayed in the low single digits, and guardrails rejected one pull request in five before review.

The constraint is the product. One team ran 285 iterations of a self-improving codebase, merged 1,094 pull requests, and had zero regressions, yet 38 green tests coexisted with a completely broken product. A suite can go green while the product falls apart, so the loop must converge on the specification, not the score.

Run the gate in shadow mode for at least four hours of real traffic. Keep it closed when automated and human verdicts differ by more than 2%. Sample only 1% to 5% of traces. With the risky slice gated and the boring 80% open, a two-person shop can take on work it once declined. The model bill does not move. Everything else does.

Start this week with faithfulness, tool-parameter accuracy, and response quality. For code changes, score intent and decision, execution and artifact, completeness and usefulness, instruction and boundary, and efficiency. Choose the dataset deliberately: `final_response`, `single_step`, `trajectory`, or RAG. A final answer can be correct even when the path was broken.

Keep 300 to 800 held-out cases, with 500 running in under five minutes. Begin with five failures: an empty tool result that must not become an invented number, a repeated call, a boundary refusal, handoff integrity, and verified completion based on a real signal. Three measurements, one dataset type, and five evals are an afternoon of work. Each week after that, the suite is worth more than it was the week before.

What survives model replacement is the examiner: the failures turned into tests, the rules that change the next edge, and the track record that lets a machine merge its own work. Install one skill, pull 25 traces, and build one eval today. Add another whenever something breaks.
