---
source_ids:
- eval-engineering-the-step-that-turns-a-200-model-9f6f868f
content_mode: faithful_synthesis
label: FAITHFUL SYNTHESIS
---

A travel agent, the software kind, answered a question about a trip: an exchange rate to one decimal place, the temperature for the week, the opening hours of a museum. Specific, clean, useful-sounding. All of it invented. The search tool had come back empty, and the model quietly filled the hole and handed its own invention over as a fact it had looked up.

Then the team measured it across 100 real sessions and got two numbers that should never sit that far apart. How good the answers were: 83.9%. How much of those answers was grounded in what the tools actually returned: 32.3%. The agent wrote beautifully and told the truth about a third of the time. Nobody caught it, because the writing was the only part anyone ever looked at.

A better model would not have caught this. What was missing was the layer that decides whether an answer was right and then does something with the verdict: the one line in the stack nobody can sell you, because it encodes your own definition of correct. The model you rent for a couple of hundred a month is, give or take, the model a company with a thousand engineers is running. That was supposed to level everything. Instead it made the gap between two teams renting the identical brain wider than the gap between two models.

## Thermometer, thermostat

A company running agents in production changed no model, no prompts and no human nudges across successive versions, only the evals, and the scores moved across every dimension. Same brain. Different examiner. Better product. Their own conclusion was blunter: the evals should have been in the system on day one, not month nine.

A thermometer tells you the room is cold. A thermostat turns the heat on. Almost everyone building with AI owns a thermometer at best: a dashboard, a feeling, a sense that it seems worse than last week. Eval engineering is the wiring from the reading to the furnace, and the verdict goes back into the graph to change what runs next.

Loops, then graphs, then evals. The graph was the last upgrade that made you faster; the judge decides whether that speed was worth having, because twenty agents all reporting to one frozen judge is twenty times as many places for a wrong answer to look finished. The examiner is yours. It costs almost nothing, and every failure you feed it stays there permanently. You already own the engine, too: in a blind test, a coding agent on a subscription you pay for anyway beat two dedicated evaluation platforms at recovering an expert's hand-marked failures.

## What a score is allowed to do

A number in a report has no path back to the run it measured. The line that fixes the whole discipline belongs to a 21-year-old founder in Tokyo with 258 followers whose post on it got two likes. A score that never changes behavior is analytics. An eval that changes the next edge is engineering. His wiring is six rules, each taking a verdict and doing something structural to the run in progress: a hallucination quarantines the branch it came from, a verified completion ends the run. All six are routing decisions the graph executes, so the eval steers the run mid-flight, one edge at a time.

The examiner needs hygiene of its own. Judge from another family, because a model recognizes its own writing and grades it kinder once it does. Never score on length, keywords or similarity to a reference: reward the shape and the agent learns the shape. Pin the judge's version, or a month of scores becomes unreadable. Even then, optimize against a judge long enough and the agent learns to look right rather than be right.

Tests you invent from imagination protect you from failures you already imagined. The ones that cost money are sitting in your logs right now, wearing a timestamp. Pull 25 complete traces, no more, and include one the user corrected, where the correction is the label free of charge. The trace tells you what your agent did, never what it should have done, so the answer key comes from tests, records, policy or a person. Attribution is where beginners lose a week: the same lookup twice with identical arguments is your loop, while a 429 is somebody else's limit, and it only becomes your eval if your agent was supposed to recover from it.

## The gate that merges itself

Every pull request an agent opens lands in a human queue, and you become the bottleneck of your own automation. A confidence score is computed the moment it opens, from four signals: a deterministic guardrails pass or fail, this version's recent eval scores, its revert rate on this class of change, and whether the sandbox run worked. Three of those are history and deterministic checks, and exactly one touches the model. Above the threshold it merges itself. Below it, a human gets it with the failing signal named.

Trust in an agent is an actuarial calculation. You are building a track record with a price on it, the same way an insurer does, and it sharpens every week whether or not the models improve. At the same company that changed nothing but its evals, 19 of every 20 pull requests on the fully autonomous agent merge with no human involved. Somebody who merged around 1,500 of his own in 90 days without reading a line of the code put it in a way no vendor would: "I don't trust them at all. I also don't trust my ability to code review their work. But I do trust my ability to constrain their work."

The constraint is the product. The warning comes from a team that ran 285 iterations of a self-improving codebase to 1,094 merged pull requests and zero regressions. Their own line is the one to keep: 38 green tests coexisted with a completely broken product. The loop has to converge on the spec rather than on the score, so run the gate in shadow first and keep it shut while the two verdicts disagree by more than 2%.

## An afternoon of work

Three measurements, not twelve: faithfulness, the one the travel agent failed while every other number on the dashboard looked fine, tool parameter accuracy, and response quality. Grade the path and not only the answer: a correct result reached through a broken sequence still passes when the final response is all you score.

The model was never the interesting part. It is identical for everyone, and it will be replaced twice before the end of the year. Most people will go back to scrolling outputs on a Friday and deciding it feels about right. The ones who go first spend one afternoon wiring the thermostat, and then spend the next year with an agent that cannot break the same thing twice.

<!-- SCRATCH: not part of the manuscript -->

## What round 2 changed, and why

Round 1 failed one deterministic gate, twice reported: the fenced block holding the six verdict-to-action routing rules. My predecessor's own notes admit it: "The routing rules are a mapping, and prose bullets are what the previous draft was criticised for, so I used one fenced block. That was my call." It was the wrong call, and the reason is not stylistic. The magazine's fence rule is a copy-and-run guarantee: a fenced block must be the source's own lines character for character, and this one was invented formatting. The source presents those six pairs inside a block labelled `python` that is neither Python nor reproducible from the extraction as a stable, untruncated set of lines, so there was no faithful fence available to substitute. **Do not try again.** Any future reviser who reaches for a fence here for the routing rules, the install commands, the `evalkit` phases, the Harbor folder tree, or the four-line write-up template should stop: every code region in this extraction is either OCR-truncated at the right margin (`--yes --g`, `Evaluate my agent at ./my_agent for grounding and to`, `mine traces -> identify a failure -> build an eval -> improve the`) or arrives with column padding that cannot be trusted to match the pinned bytes. This article has no reproducible code, and that is a property of the source, not a gap in the writing.

The repair: the six rules are now two sentences of ordinary prose, and they deliberately name only two of the six actions (quarantine the branch, end the run) plus the conclusion the source itself draws, that each is a routing decision the graph executes mid-flight. Three reasons for naming only two:

1. **The figure already enumerates them.** `edition.yaml` pins figure `eval-routing` to this exact heading with the caption "Scores become useful only when they change the next edge: retry, reject, quarantine, block, or route to human review." A prose list of all six would put the same enumeration on the page twice, which is the "nothing appears twice" rule with the manifest's figures counted as part of the page. My predecessor spotted this coupling and flagged it as a prompt gap; it is now load-bearing on the repair. **If anyone later removes or re-anchors that figure, this paragraph should grow back one or two of the missing actions**, because the reader would otherwise lose the range of what a verdict can do.
2. The brief's enumeration rule allows a list only when the reader will act on the items and there are no more than five. There are six, and a print reader acts on the principle rather than the table.
3. The two I kept are the two the surrounding argument uses: quarantine picks up the hallucination thread from the travel agent, and "ends the run" sets up the verified-completion idea that the gate section depends on.

Nothing else in the draft failed a check, so I kept the round 1 shape intact rather than re-planning the piece. The block's removal freed roughly a fenced block's worth of vertical space, and I spent it on one qualification the budget had squeezed out: the trace tells you what your agent did and never what it should have done, with the answer key coming from tests, source records, policy or a person. That sentence was the highest-value thing on the cut list because without it "mine your logs for tests" reads as an instruction to enshrine the agent's own past output as ground truth, which is the exact failure the source warns about.

Two smaller edits: `source_id` became `source_ids` as a list, matching the brief's Format block, this edition's other faithful_synthesis manuscripts, and the `edition.yaml` row; and "Every one of those six is a routing decision" became "All six are routing decisions" to drop a dead word.

**On length.** The body is 1,130 words excluding headings, against a guide of "roughly 700 to 1,100". Round 1 was about 1,107 words *plus* a six-line fenced block, and it passed the fit gate; a monospace block of that size, with its blank lines above and below, costs more vertical space on A5 than the two sentences of prose that replaced it, so the rendered page count should be at or below round 1's. Run `mag fit rerun-004-the-systems-around-the-model` before accepting this. If it overflows, cut in this order and stop as soon as it fits: (1) "so run the gate in shadow first and keep it shut while the two verdicts disagree by more than 2%" (rollout mechanics, 20 words, the least load-bearing sentence in the piece); (2) "and include one the user corrected, where the correction is the label free of charge"; (3) the blind-test sentence closing *Thermometer, thermostat*, which is the whole "you already own the engine" step and should go only under real pressure. Do not reach for the caveats: the travel-agent numbers, "the agent learns to look right rather than be right", and "38 green tests coexisted with a completely broken product" are what a manager has to be able to restate after one read.

To buy that space I already compressed the blind test (dropped its "100 real production traces from a live voice agent" detail, which also stopped a second, unrelated "100" from colliding with the 100 sessions in paragraph 2) and replaced the Friday-afternoon scroll in the thermostat paragraph with "a sense that it seems worse than last week", so the Friday image now appears once, in the close, where it earns the ending. My predecessor flagged that repeat and left both in.

## Claim ladder

**Central claim.** Everyone rents the same model now, so what separates two teams is the examiner they build around it: the layer that judges whether an answer was right and then changes what the system does next. It costs almost nothing, nobody can sell it to you because it encodes your own definition of correct, and it appreciates every week you run it.

**Main caveat a reader must be able to state after one read.** The examiner can be gamed and can be wrong about the whole product: optimize against a judge long enough and the agent learns to look right rather than be right, and 38 green tests coexisted with a completely broken product.

**Supporting claims in the order the argument needs them.**

1. Quality and truth are different measurements and only one is usually watched. Travel agent invents an exchange rate, a week's temperature, museum hours; the search tool came back empty. Over 100 real sessions: response quality 83.9%, faithfulness 32.3%. Nobody caught it because the writing was the only part anyone looked at.
2. A better model would not have caught it. The missing layer decides whether an answer was right and does something with the verdict; cheapest line in the stack, and nobody can sell it to you.
3. The rented brain is the same everywhere ("give or take"), which widened the gap between teams instead of levelling it.
4. Evals alone move the product: no model, prompt or human-nudge changes across versions, scores moved on every dimension; the team's own conclusion was day one, not month nine.
5. Thermometer against thermostat; the return arrow is the whole difference.
6. Loops, then graphs, then evals. The graph made you fast; the judge decides whether the speed was worth having. Twenty parallel agents on one frozen judge multiplies exposure.
7. The examiner appreciates; the model is a rental.
8. You already own the eval engine (blind test, coding agent above two dedicated platforms).
9. A number in a report has no path back to the run it measured; the Tokyo founder's line; six verdict-to-action rules, each a routing decision executed mid-flight.
10. Judge hygiene: another family, no shape-rewarding, pin the version.
11. Tests come from logs, not imagination: 25 traces, the user correction as a free label, the trace is not truth, attribution.
12. The merge gate: four signals, one confidence score, three of four deterministic or historical.
13. Trust is actuarial; 19 of 20 merge unattended; the 1,500-pull-request practitioner; the constraint is the product.
14. The counterexample: 285 iterations, 1,094 merges, zero regressions, and 38 green tests over a broken product. Converge on the spec, not the score. Shadow mode, 2% deviation.
15. This week: three measurements; grade the path, not only the answer.
16. The model will be replaced twice before the end of the year; the examiner survives.

## Voice signature, carried verbatim

1. "The agent wrote beautifully and told the truth about a third of the time." Paragraph 2.
2. "Same brain. Different examiner. Better product." Opening paragraph under *Thermometer, thermostat*.
3. "Trust in an agent is an actuarial calculation." Opens the second paragraph under *The gate that merges itself*. My predecessor briefly promoted it to a heading and demoted it again; leave it in the prose, because the contract requires the sentence to survive in the manuscript and a heading is not a sentence a reader hears in the author's voice.

Other unmistakable lines kept whole: "The constraint is the product", "reward the shape and the agent learns the shape", "The ones that cost money are sitting in your logs right now, wearing a timestamp", "38 green tests coexisted with a completely broken product", and the closing "spend the next year with an agent that cannot break the same thing twice".

## What is cut, and why (unchanged from round 1 unless noted)

Dropped whole: the "not a skim, open a terminal beside it" preamble and both X/Telegram promotion blocks; every install command and the `evalkit` phase list (a print reader cannot run them, and see the fence warning above); the two-repositories detail and the open-skills portability list; the leaderboard's four rows, reduced to the single comparison the author calls the interesting one; the vendor unbundling; the Harbor folder tree, the four-line write-up template and the verifier self-test; the interview step, which restates "it encodes your own definition of correct"; the aggregate merge statistics and the two-person-shop economics, as second evidence for what 19-in-20 already carries; the dataset taxonomy, the sizing numbers and the five first evals; and the source's closing three-line recap, which would have ended the piece on a list.

Numbers kept: 83.9, 32.3, 100 sessions, 25 traces, 429, 19 of 20, 1,500, 90 days, 285, 1,094, 38, 2%. Dropped: 87.2, 84.6, 82.8, 79.5, 74.4, 91.0, 39, $200, 300 to 800, 5 minutes, 4 hours, 1% to 5%. Rule applied, per the brief: a number survives only if the argument changes when the number changes.

## What the piece is resting on

- The dollar figure is gone from the body even though it is in the source's title. The argument survives it ("a couple of hundred a month"), but if an editor wants the title's `$200` echoed, the place is paragraph 3, not the close.
- Both pinned headings are reused character for character: `## Thermometer, thermostat` and `## What a score is allowed to do`. The other two headings, `## The gate that merges itself` and `## An afternoon of work`, are mine and carry no figure, so they are free to change. The pinned two are not: renaming either strands its figure and the renderer refuses the build.
- The close deliberately avoids the source's own three-line recap and `WRITING_RULES.md`'s exemplar ending, which is a near-copy of that recap's third line. Reusing either would have read as an edition-wide cadence.
- Claim strength preserved at every hedge: "give or take", "about a third of the time", "around 1,500", "the same way an insurer's is". The gain-from-evals-alone claim is reported as the company's, not verified.
