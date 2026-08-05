The sentence: A reader gets a working path from a polished but ungrounded answer to an evaluation loop that changes the agent's next action, using the travel agent as the thread.

The two absences: the vendor-by-vendor leaderboard and installation command blocks; the self-improving-codebase statistics and promotional sign-offs.

Everyone is renting the same brain now. The model you can have for a couple of hundred dollars a month is, give or take, the model a company with a thousand engineers is running. Yet the gap between two teams renting the identical brain can be wider than the gap between two models.

A software travel agent answered a simple trip question with an exchange rate, the week's temperature, and a museum's opening hours. Specific, clean, useful-sounding. All of it invented. The search tool had returned nothing, and the model quietly filled the hole, then handed its invention over as a fact it had looked up.

Across 100 real sessions, the team measured answer quality at 83.9 percent. Faithfulness to what the tools had actually returned was 32.3 percent. The agent wrote beautifully and told the truth about a third of the time.

A better model would not have caught this. What was missing was the layer that decides whether an answer was right, then does something with the verdict. That layer is the distance between an AI that impresses people and one that gets paid. It encodes your definition of correct, which no vendor can sell you ready-made.

A thermometer tells you the room is cold. A thermostat turns the heat on.

Most teams have a dashboard, a feeling, or a Friday afternoon spent scrolling outputs and deciding that things seem worse than last week. Eval engineering runs the wire from the reading to the furnace. A loop lets one agent try, inspect what came back, and try again. A graph lets independent work run side by side. The judge decides whether the speed was worth having.

Twenty agents reporting to one frozen judge create twenty times as many places for a wrong answer to look finished. The examiner becomes more valuable each week because every failure you feed it stays there, while the model remains a rental.

The entry cost has changed. Researchers took 100 production traces from a live voice agent, had a human expert mark 39 kinds of failure, hid those labels, and tested evaluation systems against the same pile. A general coding agent on a subscription many teams already pay for recovered more of the flagged failures than two dedicated platforms. Within about four weeks, evaluation vendors began shipping their expertise as skills for coding agents. The category was unbundling itself into the terminal already open.

The useful detail is what the tools do after installation. `evalkit init` lays out an evaluation folder, and `/evalkit.report` returns prioritized recommendations tied to locations in the code. One skill builds evaluations; another pulls the real production runs from which to build them. The files follow an open skills specification, so they can load into Codex, Cursor, Windsurf, or Goose.

A score in a report still changes nothing. The score needs a path back to the run it measured.

A score that never changes behavior is analytics. An eval that changes the next edge is engineering.

The wiring is direct. Low context recall rejects a handoff. Bad tool use retries or swaps a node. Hallucination quarantines a branch. A schema failure blocks the edge. Compliance risk routes to human review. Verified completion terminates the run. Each verdict becomes a routing decision the graph executes mid-flight.

The judge needs rules of its own. Use a different model family when possible, because a model recognizes its own writing and grades it more kindly. Write one primary rubric in the form “Pass iff [the independently observable successful outcome].” Let plain code handle objective checks such as whether a test passed, a file exists, or state changed. Do not reward response length, keywords, citation counts, exact phrasing, or similarity to a reference. Pin the judge's version and log it, or a silent upgrade will make a month's scores impossible to compare.

Optimize against a judge long enough and the agent learns to look right rather than be right.

The best tests are already in the logs. Start with 25 complete traces, chosen so good and bad behavior sit beside each other: a normal request, a user-confirmed success, a correction or rephrasing, a failed or repeated tool call, and an external failure such as a timeout or rate limit. For each trace, record the observed behavior, what worked and what did not, who caused the result, and the capability an evaluation should preserve or improve.

Attribution matters. The same lookup twice with identical arguments is a loop in your agent. A 429 is somebody else's limit, unless your agent was supposed to recover from it.

Turn the finding into a folder such as `evals/<task-id>/`, with an instruction, an environment, and tests. The tested agent sees the instruction and environment. The expected outcome, rubric, and judge credentials stay hidden. Never treat the recorded answer as truth. Test the verifier with one clearly correct and one plausible but wrong result. Check that the environment does not reveal the answer before the agent reaches the tool. Simulate anything that would cost money or write to production.

Then the graph can decide what to do with its own work. A pull request supplies a deterministic guardrail result, the recent eval trajectory for that agent version, its historical revert rate on that repository and change class, and the sandbox outcome. Together they produce a confidence score. Above the threshold, the change merges. Below it, a human receives the named failing signal instead of starting at line one.

At one company, 19 of every 20 pull requests from a fully autonomous agent merged without human involvement. Across the top agents, about three quarters of merged work went in without a human edit, with revert rates in the low single digits. These are reported results, not a promise that every team will see them.

The careful path is to run the gate in shadow mode for at least four hours, merging nothing. Keep it closed when automated and human verdicts differ by more than 2 percent. Sample only 1 to 5 percent of traces. Open the gate on the boring 80 percent and keep the risky slice under review.

Start with three measurements for a tool-using agent: faithfulness, tool parameter accuracy, and response quality. If the agent ships code, score the change across intent and decision, execution and artifact, completeness and usefulness, instruction and boundary, and efficiency. Choose the dataset type deliberately: `final_response`, `single_step`, `trajectory`, or `RAG`. A final-response score can miss a broken path that happened to end correctly.

Keep the suite alive. Hold out 300 to 800 cases and keep 500 running in under five minutes. Begin with five evals: an empty tool result, a repeated call, a boundary refusal, handoff integrity, and verified completion.

The model will be replaced. The examiner remains: the failures turned into tests, the rules that change the next edge, and the track record that lets a machine merge its own work. That is what decides whether the $200 on the card statement produces a demo or a business.

Install one skill. Pull 25 traces. Build one eval today, then add one whenever something breaks.
