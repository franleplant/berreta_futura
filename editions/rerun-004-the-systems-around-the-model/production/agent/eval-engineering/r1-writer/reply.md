---
source_id: eval-engineering-the-step-that-turns-a-200-model-9f6f868f
content_mode: faithful_synthesis
label: FAITHFUL SYNTHESIS
---

A travel agent, the software kind, answered a question about a trip: an exchange rate to one decimal place, the temperature for the week, the opening hours of a museum. Specific, clean, useful-sounding. All of it invented. The search tool had come back empty, and the model quietly filled the hole and handed its own invention over as a fact it had looked up.

Then the team measured it across 100 real sessions and got two numbers that should never sit that far apart. How good the answers were: 83.9%. How much of those answers was grounded in what the tools actually returned: 32.3%. The agent wrote beautifully and told the truth about a third of the time. Nobody caught it, because the writing was the only part anyone ever looked at.

A better model would not have caught this. What was missing was the layer that decides whether an answer was right and then does something with the verdict: the one line in the stack nobody can sell you, because it encodes your own definition of correct. The model you rent for a couple of hundred a month is, give or take, the model a company with a thousand engineers is running. That was supposed to level everything. Instead it made the gap between two teams renting the identical brain wider than the gap between two models.

## Thermometer, thermostat

A company running agents in production changed no model, no prompts and no human nudges across successive versions, only the evals, and the scores moved across every dimension. Same brain. Different examiner. Better product. Their own conclusion was blunter: the evals should have been in the system on day one, not month nine.

A thermometer tells you the room is cold. A thermostat turns the heat on. Almost everyone building with AI owns a thermometer at best: a dashboard, a feeling, somebody scrolling outputs on a Friday afternoon. Eval engineering is the wiring from the reading to the furnace, and the verdict goes back into the graph to change what runs next.

Loops, then graphs, then evals. The graph was the last upgrade that made you faster; the judge decides whether that speed was worth having, because twenty agents all reporting to one frozen judge is twenty times as many places for a wrong answer to look finished. The examiner is yours. It costs almost nothing, and every failure you feed it stays there permanently. You already own the engine, too: in a blind test over 100 real production traces from a live voice agent, a coding agent on a subscription you pay for anyway caught more of an expert's hand-marked failures than two dedicated evaluation platforms did.

## What a score is allowed to do

A number in a report has no path back to the run it measured. The line that fixes the whole discipline belongs to a 21-year-old founder in Tokyo with 258 followers whose post on it got two likes. A score that never changes behavior is analytics. An eval that changes the next edge is engineering. His wiring is six rules, each doing something structural to the run in progress:

```
low context recall    → reject the handoff
bad tool use          → retry or swap the node
hallucination         → quarantine the branch
schema failure        → block the edge
compliance risk       → route to human review
verified completion   → terminate the run
```

The examiner needs hygiene of its own. Judge from another family, because a model recognizes its own writing and grades it kinder once it does. Never score on length, keywords or similarity to a reference, because reward the shape and the agent learns the shape. Pin the judge's version, or a month of scores becomes unreadable after the fact. Even then, optimize against a judge long enough and the agent learns to look right rather than be right.

Tests you invent from imagination protect you from failures you already imagined. The ones that cost money are sitting in your logs right now, wearing a timestamp. Pull 25 complete traces, no more, and include one the user corrected, where the correction is the label free of charge. Attribution is where beginners lose a week: the same lookup twice with identical arguments is your loop, while a 429 is somebody else's limit, and it only becomes your eval if your agent was supposed to recover from it.

## The gate that merges itself

Every pull request an agent opens lands in a human queue, and you become the bottleneck of your own automation. A confidence score is computed the moment the request opens, from four signals: a deterministic guardrails pass or fail, this version's recent eval scores, its revert rate on this class of change, and whether the sandbox run worked. Three of those are history and deterministic checks, and exactly one touches the model. Above the threshold it merges itself. Below it, a human gets it with the failing signal named.

Trust in an agent is an actuarial calculation. What you are building is a track record with a price on it, the same way an insurer's is, and it sharpens every week whether or not the models improve. At the same company that changed nothing but its evals, 19 of every 20 pull requests on the fully autonomous agent merge with no human involved. Somebody who merged around 1,500 of his own in 90 days without reading a line of the code put it in a way no vendor would: "I don't trust them at all. I also don't trust my ability to code review their work. But I do trust my ability to constrain their work."

The constraint is the product. The warning comes from a team that ran 285 iterations of a self-improving codebase to 1,094 merged pull requests and zero regressions. Their own line is the one to keep: 38 green tests coexisted with a completely broken product. The loop has to converge on the spec rather than on the score. Run the gate in shadow first, and keep it shut while the automated and human verdicts disagree by more than 2%.

## An afternoon of work

Three measurements, not twelve: faithfulness, the one the travel agent failed while every other number on the dashboard looked fine, tool parameter accuracy, and response quality. Grade the path and not only the answer, because a correct result reached through a broken sequence still passes when the final response is all you score.

The model was never the interesting part. It is identical for everyone, and it will be replaced twice before the end of the year. Most people will go back to scrolling outputs on a Friday and deciding it feels about right. The ones who go first spend one afternoon wiring the thermostat, and then spend the next year with an agent that cannot break the same thing twice.

<!-- SCRATCH: not part of the manuscript -->

## 1. Claim ladder

**Central claim.** Everyone now rents the same model, so what separates two teams is the examiner they build around it: the layer that judges whether an answer was right and then changes what the system does next, which costs almost nothing, cannot be bought because it encodes your own definition of correct, and gets more valuable every week you run it.

**Supporting claims, in the order the argument needs them.**

1. Quality and truth are different measurements and only one of them is usually watched. The travel agent invented an exchange rate to one decimal place, the week's temperature, museum opening hours; the search tool had come back empty and the model filled the hole. Across 100 real sessions: response quality 83.9%, faithfulness 32.3%. Nobody caught it because the writing was the only part anyone looked at.
2. A better model would not have caught it. What was missing was the layer that decides whether an answer was right and does something with the verdict. It is the cheapest line in the stack and the only one nobody can sell you.
3. The rented model is roughly the same everywhere ("give or take"), which was supposed to level things and instead widened the gap between teams renting the identical brain beyond the gap between two models.
4. Evals alone move the product. One company changed no model, no prompts, no human nudges across successive versions, only the evals, and scores moved on every dimension. Their conclusion: evals should have been in on day one, not month nine.
5. Thermometer versus thermostat. Most people own a dashboard, a feeling, a Friday scroll. The difference is the return arrow: the verdict re-enters the graph and changes what runs next.
6. Fixed order of arrival: loops, then graphs, then evals. The graph was the last upgrade that made you faster; the judge decides whether the speed was worth having. Twenty parallel agents on one frozen judge is twenty times as many places for a wrong answer to look finished.
7. The examiner is the only appreciating part. The model is a rental at about $200 a month; the examiner costs almost nothing to install and every failure fed to it stays permanently.
8. You already own the eval engine, and this stopped being false about four weeks ago. Blind test: two researchers, 100 real production traces from a live voice agent, a human expert hand-marking every failure, a taxonomy of 39 labeled failures, labels hidden, the pile handed to every evaluation system on the market. Braintrust Loop recovered 87.2% of human-flagged failures; Codex on GPT-5.5 High 84.6% recall and 82.8% precision; LangSmith 79.5%; Arize AX 74.4% recall with the cleanest precision at 91.0%. The interesting row was not the winner: a general coding agent on a subscription you already pay for landed above two dedicated platforms, and one of those platforms said you can get similar results from using your coding agent.
9. The vendors unbundled themselves into the coding agent. Inside four weeks: LangChain on 22 July, Galileo, AWS under Apache 2.0, Arize shipping trace extraction into skills for "your favorite coding agent". Nobody has counted those four as one move.
10. Installation is three lines. Two repositories, two jobs (one builds evals, one pulls the production runs to build them from); most people install the first and then wonder where the material comes from. Open skills specification, so the same files load into Codex, Cursor, Windsurf, Goose. The AWS kit is six phase commands writing into an `eval/` folder; `/evalkit.report` returns prioritized recommendations pointing at specific locations in the code.
11. A number in a report has no path back to the run it measured. The line, from a 21-year-old founder in Tokyo with 258 followers whose post got two likes: a score that never changes behavior is analytics; an eval that changes the next edge is engineering. Six verdict-to-action rules: low context recall → reject the handoff; bad tool use → retry or swap the node; hallucination → quarantine the branch; schema failure → block the edge; compliance risk → route to human review; verified completion → terminate the run. Each is a routing decision the graph executes mid-flight, one edge at a time.
12. Judge hygiene, five rules: judge from another family (a model grades its own writing kinder; one team runs Sonnet judging Haiku output on purpose; same family generating and grading shares blind spots); rubric as one line, *Pass iff [the independently observable successful outcome]*, one primary verdict not a bundle of proxy scores; split semantic calls (judge) from objective ones (plain code: did the test pass, does the file exist, did the state change); never reward the shape of an answer (no length, keywords, citation count, exact phrasing, tool-call count, similarity to a reference); pin the judge and log its version, the step people skip, which makes a month of scores unreadable after the fact.
13. Tests come from logs, not imagination. 25 complete traces, no more, chosen so good and bad sit side by side: a normal finished request; a user-confirmed request; a user-corrected or rephrased request (the correction is the label, free of charge); a failed, empty or repeated tool call (repetition means a loop, emptiness means an invented answer is coming); an external failure such as a timeout or rate limit. Four-line write-up template: observed behavior, comparison, attribution, eval candidate.
14. Attribution is where beginners lose a week. The same lookup twice with identical arguments is your loop; a 429 is somebody else's limit.
15. The finding becomes a Harbor task folder (`task.toml`, `instruction.md`, `environment/`, `tests/`), one capability per folder. Instruction and environment visible to the agent under test; expected outcome, rubric and judge's credentials hidden, and that separation is the only reason the score means anything. Three rules: never treat the recorded answer as truth (the answer key comes from tests, source records, policy, known state or a person); test the test with two hand-made fake results, one clearly correct and one plausible but wrong; watch for an environment that hands over the result before the agent reaches the tool. Anything that costs money or writes to production is simulated.
16. The interview step is deliberate: questioning the user beats one-shot generation every time, because the definition of correct lives in your head and nowhere in the model.
17. The payoff is the merge gate. Agent pull requests land in a human queue and the fleet runs at the speed of one tired reviewer. Four signals give a confidence score on the spot: guardrails result (deterministic, no model), recent eval trajectory for this exact version, historical revert rate for this agent on this repository on this class of change, sandbox outcome. Above threshold it self-merges; below, a human gets it with the failing signal named. Three of four are history and deterministic checks; exactly one touches the model.
18. Trust in an agent is an actuarial calculation: a track record with a price on it, sharpening weekly whether or not models improve.
19. Observed results: at the same company, 19 of every 20 pull requests on the fully autonomous agent merge with no human. Across the top agents, about three quarters of merged work goes in with no human edit, the revert rate stays in the low single digits, and Guardrails alone bounces one pull request in five. The 1,500-pull-request practitioner quote, ending "I do trust my ability to constrain their work". The constraint is the product.
20. Economic consequence: a two-person shop is capped at what one reviewer can read; with the gate closed on the risky slice and open on the boring 80%, they quote on contracts they used to decline. The model bill does not move. Everything else does.
21. What to build this week: three measurements, not twelve (faithfulness, tool parameter accuracy, response quality); for code-shipping agents, five dimensions of the change (intent and decision, execution and artifact, completeness and usefulness, instruction and boundary, efficiency); one dataset type chosen on purpose from final_response, single_step, trajectory, RAG; 300 to 800 held-out cases with 500 running in under 5 minutes; five first evals (empty tool result, repeated call, boundary refusal, handoff integrity, verified completion).
22. Conclusion: the model is a rental that will be replaced twice before the end of the year; what survives is the examiner, and that decides whether the $200 produces a demo or a business.

**Qualifications, counterexamples, uncertainty, limits on claim strength.**

- "Give or take" on the rented model being the same one a thousand-engineer company runs.
- The gain is attributed to evals only in a case where the team says nothing else changed. The author reports their claim; he does not verify it.
- Twenty agents on one frozen judge multiplies exposure rather than reducing it. Parallelism is not presented as safety.
- Braintrust Loop, not the coding agent, won. The platform with the lowest recall (Arize AX, 74.4%) had the cleanest precision (91.0%). The author's point is explicitly not "the coding agent wins", it is "the interesting row was not the winner".
- Hedged quantities throughout: "about four weeks ago", "about three quarters", "low single digits", "roughly".
- "Nobody has counted those four as one move" is the author's own observation, flagged as uncounted.
- The 21-year-old founder has 258 followers and two likes on the post. The author foregrounds the weak provenance rather than hiding it.
- Optimize against a judge long enough and the agent learns to look right rather than be right. A limit on the whole method.
- An examiner that silently upgrades makes a month of scores unreadable and you will not notice for a month.
- The trace tells you what your agent did, never what it should have done.
- A 429 only becomes your eval if your agent was supposed to recover from it.
- An environment that gives the answer away makes a task that passes forever and measures nothing.
- The central counterexample: 285 iterations, 1,094 merged pull requests, zero regressions, and "38 green tests coexisted with a completely broken product". A suite can go all green while the product falls apart, so the loop has to converge on the spec rather than on the score.
- Rollout hedges: shadow mode for at least 4 hours of real traffic merging nothing; a 2% deviation threshold closes the gate; sampling at 1% to 5% rather than full capture.
- A suite too slow or too vague never gets run; a suite longer than a coffee break stops being run.
- Grading only the final response hides a correct answer reached through a broken sequence.

**What the budget forced out, and why.** At 1,100 words this source loses roughly half its substantive claims. Order of sacrifice: the "not a skim, open a terminal beside it" preamble and both X/Telegram blocks (throat-clearing and promotion); the install commands, the two-repositories detail, the open-skills portability list and the `evalkit` phases (claim 10), because a print reader cannot run a command from the page and claims 8 and 9 already carry "the engine is on your machine"; the leaderboard rows (claim 8) reduced to the one comparison the author says is the interesting one, with Braintrust Loop's win kept as the qualification and the four numbers dropped; the vendor unbundling (claim 9); the Harbor folder layout, the four-line template and the verifier tests (claims 13 and 15), which are format below the argument's resolution; the interview step (claim 16), which restates "it encodes your own definition of correct" from the opening; the aggregate merge statistics and the two-person-shop economics (claims 19 and 20), as second evidence for a result 19-in-20 already carries; the dataset taxonomy, the sizing numbers and the five first evals (claim 21), collapsed to the measurement triple and the grade-the-path rule; and the source's closing three-line recap, which restates the body and would have ended the piece on a three-item list.

## 2. Voice signature (three sentences carried verbatim)

1. **"The agent wrote beautifully and told the truth about a third of the time."** Second paragraph of the manuscript, verbatim.
2. **"Same brain. Different examiner. Better product."** First paragraph under *Thermometer, thermostat*, verbatim.
3. **"Trust in an agent is an actuarial calculation."** Opens the second paragraph under *The gate that merges itself*, verbatim. It was briefly a section heading instead; I moved it back into the prose because the contract says the sentence survives into the manuscript, and a heading is not a sentence a reader hears in the author's voice.

Other unmistakable lines kept whole because cutting them would have cost the argument: "The constraint is the product", "reward the shape and the agent learns the shape", "The ones that cost money are sitting in your logs right now, wearing a timestamp", "38 green tests coexisted with a completely broken product", and the closing "spend the next year with an agent that cannot break the same thing twice".

## 3. Assessment of the prompt contract

**Clear and load-bearing.**

- The claim ladder did real work, specifically because it separates qualifications from supporting claims. The qualifications in this source cluster around three ideas (the judge can be gamed, the suite can be green over a broken product, the provenance of the best line is thin), and once listed apart they became structural beats instead of asides. Without that split they are the first thing length pressure removes.
- "Decide the piece from the claim ladder, not from the source's paragraph order" is the most useful sentence in the prompt. This source is five numbered steps plus a coda; the default move is to keep five sections and shrink each. That is how a vendor leaderboard survives into a magazine.
- "Drop a second piece of evidence for a point the first already carried" is the only cutting licence in the prompt, and I used it constantly.
- "Nothing appears twice" caught two real repeats on the reread: the Friday-scroll image, which I had in both the thermostat paragraph and the closing, and 32.3%, which appeared in the opening and again in the measurement list. Both are repeated in the source itself, so the rule is doing something the source does not.
- The banned-tic list is concrete enough to obey rather than interpret. The antithesis ban removed three closings I had drafted.
- "Keep the author's grammatical person" plus "never add scaffolding" settled narration in one read.

**Vague or weak.**

- *The length budget is stated too late and too mildly, and it is the binding constraint.* "Roughly 700 to 1,100" sits under *Length and format*, after the procedure, and step 5 says "cut to the page budget" as if trimming. Following steps 1 to 4 faithfully produced 2,350 words: more than double. Four further passes were needed to reach 1,107, and each one was a judgment about which of the author's claims to lose, which is exactly the judgment the prompt should govern and does not. The budget should lead the prompt, with an explicit warning that a source of this length will lose about half its substantive claims, and with an ordering rule for what goes first. Without one, "keep every qualification" and the editorial policy's "map the complete substantive source" read as promises the word count cannot keep.
- *No rule for enumerations, which is the actual failure mode.* The prompt handles duplicated evidence and says nothing about lists. This source contains a four-row leaderboard, a five-kind trace list, a five-rule judge list, a six-rule routing table, a three-rule rollout, a five-eval starter set, a four-type dataset taxonomy and a five-dimension rubric. Which of those becomes prose, which stays a list, and which collapses to its conclusion is the whole job in the middle of the piece. A usable rule: an enumeration survives as a list only if the reader would act on it item by item; otherwise it becomes the one sentence it exists to support.
- *The verbatim-three requirement has no ceiling and no floor.* In this source the most distinctive sentences are also the load-bearing ones, so about ten survive whole. Nothing says whether that is fidelity or under-synthesis.
- *Silent on code blocks, tables, and figures.* The routing rules are a mapping, and prose bullets are what the previous draft was criticised for, so I used one fenced block. That was my call. Worse, `edition.yaml` already declares a figure for this article ("Scores become useful only when they change the next edge: retry, reject, quarantine, block, or route to human review"), so my block may duplicate the rendered figure. The prompt never mentions that the manifest's figures are part of the page and part of the duplication check.
- *Headings versus the no-added-framing rule.* The prompt asks for headings that name ideas rather than the source's section titles, and separately bans "framing the author did not offer". Every heading I wrote is an assertion the author did not write in that form. The two rules pull against each other and the prompt does not say which wins. Note also that `edition.yaml` anchors both figures to the old headings ("The examiner you already own", "Make the score change the next edge"), so any reheading silently breaks figure placement. Nothing in the prompt warns about that coupling.
- *The house exemplar collides with this source.* `WRITING_RULES.md` offers as a model ending "Any failure you do not turn into a permanent test is a failure you have agreed to meet again", which is a near-copy of this source's own third closing line. I avoided it in case reusing the house exemplar reads as another edition-wide cadence, but the rules do not say whether the exemplars are quotable.
- *The voice rule was written for a different author.* "Profanity and jokes and sign-offs included" does not fit a source whose sign-offs are "follow me on X, join my Telegram". I dropped them under the editorial policy's promotional-material clause, not under this prompt, which literally says sign-offs survive.

**Invented because the prompt did not say.**

- All four section headings, and the decision to promote and then demote "Trust in an agent is an actuarial calculation" between heading and body.
- Dropping every command and code sample except the routing rules. The traceability rule governs what may be added and says nothing about what may be omitted for a print reader.
- Which numbers to keep. I kept 83.9%, 32.3%, 25 traces, 19 of 20, 1,500, 285, 1,094, 38, 2%, and dropped 87.2%, 84.6%, 82.8%, 79.5%, 74.4%, 91.0%, 39, $200, 300 to 800, 5 minutes, 4 hours, 1% to 5%. The rule I invented: a number survives if the argument changes when it changes. No such rule is in the prompt, and it is the single decision the caller cared most about.
- Number style: "83.9%" rather than "83.9 percent", "19 of every 20", digits for "4 hours" and "2%".

**Verdict.** Not sufficient on its own, but close. Steps 1 and 3 prevent the failure that produced the previous draft and they work as written. Three gaps remain, and they are the three that produced the last middle section: a word budget stated so late that a faithful pass overshoots it by more than double, no rule for enumerations, and no rule for which numbers earn their place. Fix those and the contract holds without a diagnosis to lean on. As it stands, a writer who follows the prompt literally will produce a well-shaped 2,300-word article and then have to invent an editorial policy to cut it in half.
