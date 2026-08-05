Everyone is renting the same brain now. The model you can have for a couple of hundred dollars a month is, give or take, the model a company with a thousand engineers is running. Yet the gap between two teams renting the identical brain can be wider than the gap between two models.

A software travel agent answered a simple trip question with an exchange rate, the week's temperature, and a museum's opening hours. Specific, clean, useful-sounding. All of it invented. The search tool had returned nothing, and the model quietly filled the hole, then handed its invention over as a fact it had looked up.

Across 100 real sessions, the team measured answer quality at 83.9 percent. Faithfulness to what the tools had actually returned was 32.3 percent. The agent wrote beautifully and told the truth about a third of the time.

A better model would not have caught this. What was missing was the layer that decides whether an answer was right, then does something with the verdict. That layer is the distance between an AI that impresses people and one that gets paid. It encodes your definition of correct, which no vendor can sell you ready-made.

A company later changed no model, prompts, or human nudges across successive versions of its agent. Only the evals changed, and the scores moved across every dimension. Their conclusion was that the evals should have been in the system on day one, not month nine.

A thermometer tells you the room is cold. A thermostat turns the heat on. Most teams have a dashboard, a feeling, or a Friday afternoon spent scrolling outputs and deciding that things seem worse than last week. Eval engineering runs the wire from the reading to the furnace.

The travel agent's empty search should have produced a verdict that changed the run. Low context recall rejects the handoff. Bad tool use retries or swaps a node. Hallucination quarantines the branch. A schema failure blocks the edge. Compliance risk routes to human review. Verified completion terminates the run. Each verdict becomes a routing decision the graph executes mid-flight.

The order matters. One agent in a loop came first, so it could try, inspect what came back, and try again. Then many agents were laid out as a graph, so independent work could run side by side. The graph made the system faster. The judge decides whether that speed was worth having. Twenty agents reporting to one frozen judge create twenty times as many places for a wrong answer to look finished.

The entry cost has changed. Researchers took 100 production traces from a live voice agent, had a human expert mark 39 kinds of failure, hid those labels, and tested evaluation systems against the same pile. Braintrust Loop recovered 87.2 percent of the human-flagged failures. Codex on GPT-5.5 High reached 84.6 percent recall and 82.8 percent precision. LangSmith reached 79.5 percent. Arize AX reached 74.4 percent recall with 91.0 percent precision. A general coding agent on a subscription many teams already pay for beat two dedicated platforms. Within about four weeks, LangChain, Galileo, AWS, and Arize had shipped their expertise as skills for coding agents. The category was unbundling itself into the terminal already open.

One complete path starts with `npx skills add langchain-ai/langchain-skills --skill '*' --yes --global`, followed by `npx skills add langchain-ai/langsmith-skills --skill '*' --yes --global` and `uv tool install evalkit --from git+https://github.com/awslabs/Agent...`. The two repositories have different jobs: `langchain-skills` builds the evals, while `langsmith-skills` pulls the real production runs from which to build them. These skills follow the open skills specification, so the same files load into Codex, Cursor, Windsurf, or Goose.

Inside the project, `evalkit init my-agent-evaluation` creates the folder. The phases then run as `/evalkit.plan`, `/evalkit.data`, `/evalkit.trace`, `/evalkit.run_agent`, `/evalkit.eval`, and `/evalkit.report`. The final command returns prioritized recommendations tied to locations in the code. A score in a report still changes nothing unless it has a path back to the run it measured.

A score that never changes behavior is analytics. An eval that changes the next edge is engineering.

The judge needs rules of its own. Use a different model family when possible, because a model recognizes its own writing and grades it more kindly. Write one primary rubric in the form “Pass iff [the independently observable successful outcome].” Let plain code handle objective checks such as whether a test passed, a file exists, or state changed. Do not reward response length, keywords, citation counts, exact phrasing, or similarity to a reference. Pin the judge's version and log it, or a silent upgrade will make a month's scores impossible to compare.

Optimize against a judge long enough and the agent learns to look right rather than be right.

The best tests are already in the logs. Pull 25 complete traces, chosen so good and bad behavior sit beside each other: a normal request, a user-confirmed success, a correction or rephrasing, a failed or repeated tool call, and an external failure such as a timeout or rate limit. For each trace, record:

`Observed behavior`: what the user asked and what the agent actually did.  
`Comparison`: what worked and what did not.  
`Attribution`: agent behavior, dependency behavior, or unclear.  
`Eval candidate`: the capability to preserve or improve.

Attribution matters. The same lookup twice with identical arguments is a loop in your agent. A 429 is somebody else's limit, unless your agent was supposed to recover from it. The travel agent's empty search becomes a faithfulness test only if the agent was expected to admit the missing result.

Turn the finding into a Harbor task under `evals/<task-id>/`, containing `task.toml`, `instruction.md`, `environment/`, and `tests/`. The tested agent sees the instruction and environment. The expected outcome, rubric, and judge credentials stay hidden. Never treat the recorded answer as truth. Take the answer key from tests, source records, policy, known state, or a person. Test the verifier with one clearly correct and one plausible but wrong result. Check that the environment does not reveal the answer before the agent reaches the tool. Simulate anything that would cost money or write to production.

Then the graph can decide what to do with its own work. A pull request supplies a deterministic guardrail result, the recent eval trajectory for that agent version, its historical revert rate on that repository and change class, and the sandbox outcome. Together they produce a confidence score. Above the threshold, the change merges. Below it, a human receives the named failing signal instead of starting at line one.

At one company, 19 of every 20 pull requests from a fully autonomous agent merged without human involvement. Across the top agents, about three quarters of merged work went in without a human edit, with revert rates in the low single digits. But another team ran 285 iterations of a self-improving codebase and produced 1,094 merged pull requests with zero regressions while 38 green tests coexisted with a completely broken product. A suite can go all green while the product it guards falls apart. The loop has to converge on the specification, not merely the score.

The careful path names who may trust the gate. Run it in shadow mode for at least four hours of real traffic, merging nothing. Keep it closed when automated and human verdicts differ by more than 2 percent. Sample 1 to 5 percent of traces. Open the gate on the boring 80 percent and keep the risky slice under review.

Start with three measurements for a tool-using agent: faithfulness, tool parameter accuracy, and response quality. If the agent ships code, score the change across intent and decision, execution and artifact, completeness and usefulness, instruction and boundary, and efficiency. Choose the dataset type deliberately: `final_response`, `single_step`, `trajectory`, or `RAG`. A final-response score can miss a broken path that happened to end correctly.

Keep the suite alive. Hold out 300 to 800 cases and keep 500 running in under five minutes. Begin with five evals: an empty tool result, a repeated call, a boundary refusal, handoff integrity, and verified completion. The travel agent should fail the first when its search returns nothing, then learn not to invent the number.

The model will be replaced. The examiner remains: the failures turned into tests, the rules that change the next edge, and the track record that lets a machine merge its own work. That is what decides whether the $200 on the card statement produces a demo or a business.

Install one skill. Pull 25 traces. Build one eval today, then add one whenever something breaks.
