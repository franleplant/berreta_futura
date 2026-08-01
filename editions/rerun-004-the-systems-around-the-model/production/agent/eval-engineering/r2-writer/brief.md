# Faithful-synthesis production prompt

You are retelling this author's piece at roughly a third of its length, in the
author's own voice, as continuous prose. You are not extracting highlights and
you are not reviewing the source. The byline and the visible
`faithful_synthesis` label already tell the reader whose material this is and
that it has been condensed. Your inputs are the source extraction at
`library/sources/<source-id>/extracted.md` and the article's `edition.yaml` row.

## The budget decides the piece

Seven A5 reader pages is the hard maximum, including the opener illustration,
title, and credit; roughly 700 to 1,100 body words fits. The renderer measures
real pagination and refuses an over-budget build; `mag fit <edition-id>` answers
the same question in seconds.

Know that number before you plan. A 3,000-word source loses roughly half its
substantive claims at this length: that is the mode working, not failing. What
fails is finding out on a fourth cutting pass, where what to lose gets decided
one sentence at a time and by accident. Decide in step 3, cut in this order,
and stop as soon as the piece fits.

1. The second and third example of a point the first already carried.
2. A claim's supporting evidence, before the claim itself. A claim without its
   study reads thinner but still reads; the study without its claim is trivia.
3. Whole claims, the least load-bearing first.
4. Qualifications and the author's own conclusions: last, and almost never. A
   synthesis that reached the budget through these has failed, not fitted.

## Procedure

Steps 1 and 2 are working notes in your reply. They do not go into the
manuscript.

1. **Claim ladder.** Read the whole extraction, then write the author's central
   claim in one sentence; the supporting claims in the order the argument needs
   them, each with its evidence, example, or number attached; and every
   qualification, counterexample, admission of uncertainty, and limit on claim
   strength.
2. **Voice signature.** Quote three sentences that could only have been written
   by this author: an idiom, a joke, an insult, an unusual rhythm, or a sign-off
   that is voice rather than web furniture. These survive verbatim.
3. **Shape and cut.** Decide the piece from the claim ladder, not from the
   source's paragraph order. Merge claims the source makes twice, drop
   throat-clearing and recap sections, then apply the cut order above until what
   remains fits. Write down what you dropped.
   - **Enumerations.** Every list in the source gets one of three fates, and
     "the source had a list" is not one. Prose, when the items are moves in the
     argument. A list, when the reader will scan or act on them and there are no
     more than five. Its conclusion alone, when the items only evidence a point
     the surrounding sentence already makes.
   - **Numbers.** A number survives only if the argument changes when the number
     changes. A contrast the thesis rests on keeps both figures exactly; a
     leaderboard, a version count, or a figure whose sentence reads the same
     without it goes.
   - **Code.** Reproduce a fenced block character for character or drop it
     whole. Validation matches every fence against the source's own lines, so a
     trimmed, re-indented, or stitched block fails the build.
4. **Write it continuously.** One paragraph must follow from the last. A reader
   must never find the seam where two source passages met. Cold open on
   something concrete. End on a line that lands.
5. Edit with the method in `docs/WRITING_RULES.md`, then check the budget again.

## Hard rules

- Every claim, number, example, and quotation must be traceable to the
  extraction. Add no thesis of your own, no framing the author did not offer, no
  link, and no fact from your own knowledge.
- Preserve claim strength exactly. "We believe", "roughly", "in one sample",
  "we do not know why" are load-bearing. Never harden a hedge and never soften a
  flat assertion. Keep the counterexamples and the disagreement: a synthesis
  that reads smoother than the source because the awkward parts are gone has
  failed.
- **Voice.** Keep the author's grammatical person, and the three sentences from
  step 2 verbatim, profanity and jokes included. A sign-off survives when it is
  voice ("Good luck."); a subscribe prompt or "follow me on X" is web furniture
  and goes with the rest of the chrome. Never add scaffolding such as "the
  author argues" or "Narayanan explains".
- Nothing appears twice: edition 004 shipped the same VS Code and Sentry example
  in two sections of one article. Observe the banned tics in
  `docs/WRITING_RULES.md`, including the antithesis close "It is not X. It is Y."

## Format

```
---
source_ids:
- <source-id>                     # one entry per source, always a list
content_mode: faithful_synthesis
label: FAITHFUL SYNTHESIS
---
```

The title, byline, and `source_body_sha256` pins live in the article's
`edition.yaml` row, not here. The body follows the closing `---` and must begin
with a paragraph, never a heading, so the illustrated opener can set it. Use
`##` for section headings; no H1. A heading names what its section argues, in
the author's own words where they exist, and may not assert a framing the author
did not offer: if you cannot title a section without adding an idea, keep the
source's heading.

## Working notes

End your reply with a line containing exactly:

    <!-- SCRATCH: not part of the manuscript -->

and put your working notes below it: the claim ladder from step 1, the voice signature from step 2, and what step 3 dropped. Everything above that line is the
manuscript and is written to disk as it stands; everything below it is stripped
before the file is written and is never shown to a judge or to a reader.

Write the notes for the person who revises this piece next, which may be you in
another session. A review finding names the sentence where a defect *surfaces*;
your notes are usually the only record of where it was *made*, and a reviser
working from findings alone can patch a symptom without ever finding its cause.
Say what you decided, what you cut and why, and which choices the piece is
resting on.

## How this will be judged

A fact-checker reads the manuscript against the extraction claim by claim. A
line editor checks structure, duplication, the opening, the ending, the house
style, and whether the author's voice survived. Check this yourself first: a
developer and an engineering manager must each be able to state the piece's
central claim and its main caveat after one read.

---

# The assignment

The prompt above governs. This section names the piece, supplies its complete inputs, and states the output contract.

- Edition: `rerun-004-the-systems-around-the-model` (The Systems Around the Model)
- Piece id: `eval-engineering`
- content_mode: `faithful_synthesis`
- Title: Eval Engineering
- Byline: Argona
- Page budget: 7 rendered A5 reader page(s)

## Headings you must keep, character for character

`edition.yaml` pins a registered figure to each of these headings. The renderer refuses an anchor that does not match exactly one heading, so a rewrite that renames one strands its figure. Reuse each heading exactly as written, in a place where it still makes sense.

- `## Thermometer, thermostat` (figure `eval-engine`)
- `## What a score is allowed to do` (figure `eval-routing`)

## Source extractions

1 extraction(s), each complete. You are drafting the whole piece in this one pass from all of it: nothing else will be sent, and no later call will stitch a second half on.

### Extraction `eval-engineering-the-step-that-turns-a-200-model-9f6f868f` (669 lines, complete)

```
                   Post

                    Argona
                    @Argona0x




             Eval Engineering: the step that turns a
             $200 model into a $200,000 system
             (complete build)
             Everyone is renting the same brain now.

             The model you can have for a couple of hundred a month is, give or take, the
             model a company with a thousand engineers is running. That was supposed to
             level everything. Instead it made the gap between two teams renting the identical
             brain wider than the gap between two models.

             A travel agent, the software kind, answered a question about a trip: an exchange
             rate to one decimal place, the temperature for the week, the opening hours of a
             museum. Specific, clean, useful-sounding. All of it invented.

             The search tool had come back empty, and the model quietly filled the hole and
             handed its own invention over as a fact it had looked up.

             Then the team measured it across 100 real sessions and got two numbers that
             should never sit that far apart.

             How good the answers were: 83.9%.

             How much of those answers was grounded in what the tools actually returned:
             32.3%.

             The agent wrote beautifully and told the truth about a third of the time.

Don't miss what's
        Nobody        happening
               caught it, because the writing was the only part anyone ever looked
                                                                   Log in      Signat.
                                                                                    up
People on X are the first to know.
                  83.9% response quality against 32.3% faithfulness, one and the same run


           Same agent, same day: the left bar is what the demo shows, the right bar is what a
           customer actually gets.

           A better model would not have caught this. What was missing was the layer that
           decides whether an answer was right, and then does something with the verdict.

           That layer is the whole distance between an AI that impresses people and an AI
           that gets paid. It is the cheapest line in the stack and the only one nobody can
           sell you, because it encodes your own definition of correct.

           This one is not a skim. Open a terminal beside it. The setup starts with a single
           command you already own, and it ends somewhere that sounds unreasonable:
           pull requests that merge with nobody reading them.




              Before we get into it, follow me on X and join my Telegram channel where
              post more AI content every day. Both are free.

              X - https://x.com/Argona0x
              Telegram - https://t.me/+r0clI4-MMC03ZjAy




           What eval engineering is
           A company running agents in production said the quiet part in one sentence.
           Across successive versions of their agent they changed no model, no prompts,
            no human nudges, only the evals — and the scores moved across every
Don't miss  what's happening
        dimension.                                                Log in      Sign up
People on X are the first to know.
             Same brain. Different examiner. Better product.

             Their own conclusion afterwards was blunter: the evals should have been in the
             system on day one, not month nine.

             A thermometer tells you the room is cold. A thermostat turns the heat on.

             Almost everyone building with AI owns a thermometer at best: a dashboard, a
             feeling, a Friday afternoon where somebody scrolls outputs and says it seems
             worse than last week.

             Eval engineering is the wiring that runs from the reading to the furnace.




                   ← thermometer against thermostat, with the verdict returning into the graph


             The whole difference is the return arrow on the right: the verdict goes back into the
             graph and changes what runs next.

             This arrived in a fixed order. One agent in a loop came first, so it could try, look at
             what came back, and try again. Then many agents laid out as a graph, so work that
             never depended on each other ran side by side instead of standing in line.

             Loops, then graphs, then evals.



                             https://x.com/i/web/status/2080626046903157126



             The graph was the last upgrade that made you faster. The judge decides whether
             that speed was worth having.
Don't miss what's happening                                                  Log in        Sign up
People on X are the first to know.
            Twenty agents running at once, all reporting to one frozen judge, is twenty times
            as many places for a wrong answer to look finished.

            It is also the only part of the system that gets more valuable every week you run it.
            The model is a rental. The examiner is yours, and every failure you feed it stays
            there permanently.

            Which makes the price of entry strange. The examiner costs almost nothing to
            install, and the model it examines costs about $200 a month.




            Step 1 · The eval engine you already own
            You assume this starts with a platform: a contract, a per-seat price, a quarter of
            setup before the first useful number.

            That assumption is why most people never build the layer at all, and it stopped
            being true about four weeks ago.


            The blind test
             1. Two researchers ran the honest test. They took 100 real production traces
                from a live voice agent, had a human expert mark every failure by hand, built a
                taxonomy of 39 labeled failures, then hid the labels and handed the same pile
                to every evaluation system on the market.

            Find them yourself.

            The interesting row was not the winner:

             1. Braintrust Loop: 87.2% of the human-flagged failures recovered.
             2. Codex on GPT-5.5 High: 84.6% recall, 82.8% precision.
             3. LangSmith: 79.5%.
             4. Arize AX: 74.4% recall, and the cleanest precision of the group at 91.0%.

            A general coding agent, on a subscription you already pay for, landed above two
            dedicated evaluation platforms. One of them wrote the conclusion plainly: you can
            get similar results from using your coding agent.

            Then the platforms did something stranger than losing. They moved in.

            Inside four weeks, four evaluation vendors shipped their expertise as a <skill
            installed into somebody else's coding agent: LangChain on 22 July, Galileo,
            AWS under Apache 2.0, and Arize putting its trace extraction into skills aimed at,
            in their words, your favorite coding agent.
Don't miss what's happening                                               Log in       Sign up
            Nobody has counted those four as one move.
People on X are the first to know.
             It is a category unbundling itself into the terminal you already have open.


             Installing the examiner
             Installing all of it takes three lines.


               python


               npx skills add langchain-ai/langchain-skills --skill '*' --yes --g
               npx skills add langchain-ai/langsmith-skills --skill '*' --yes --g
               uv tool install evalkit --from git+https://github.com/awslabs/Agen


             Inside Claude Code the same thing installs as a plugin:


               python


               /plugin marketplace add langchain-ai/langchain-skills
               /plugin install langchain-skills@langchain-skills




Don't miss what's happening                                                       Log in         Sign up
People on X are the first to know.
                        ← real terminal run: the skills install, evalkit init scaffolds the folder
             A real run on a real machine: the skills land as global files, and evalkit init lays out
             the folder your evaluation will live in.

             Two details in there are worth more than the commands.

              1. Two repositories, two jobs: langchain-skills builds the evals, langsmith-
                 skills pulls the real production runs to build them from. Almost everyone
                 installs the first, then wonders where the material comes from.
              2. Not a Claude Code feature: those skills follow the open skills specification, so
                 the identical files load into Codex, Cursor, Windsurf and Goose.

             The AWS kit runs on six commands, each a phase writing into an eval/ folder the
             next one reads:


               python


               evalkit init my-agent-evaluation
               # then, inside your coding agent:
               /evalkit.plan Evaluate my agent at ./my_agent for grounding and to
               /evalkit.data
               /evalkit.trace
               /evalkit.run_agent
               /evalkit.eval
               /evalkit.report



             The last command is the one worth the whole setup. /evalkit.report hands back
             prioritized recommendations pointing at specific locations in your code.

             The examiner is installed. Now it has to be allowed to do something.




             Step 2 · Make the score change the next edge
             You will build your first evaluation, get a number, look at it, and feel nothing
             happen.

             That feeling is correct. A number in a report has no path back to the run it
             measured.

             One line fixes the whole discipline, and it belongs to a 21-year-old founder in
             Tokyo with 258 followers whose post on it got two likes:

                A score that never changes behavior is analytics. An eval that changes the next
                edge is engineering.

Don't miss   what's
        His wiring        happening
                   is six rules. Each takes a verdict and does something
                                                                     Logstructural
                                                                         in        to the
                                                                                 Sign   up
People on X are
            runthe  first to know.
                in progress:
              python


               low context recall         → reject the handoff
               bad tool use               → retry or swap the node
               hallucination              → quarantine the branch
               schema failure             → block the edge
               compliance risk            → route to human review
               verified completion        → terminate the run




                           ← six verdicts, six structural actions on the run in progress


             Every one of those six is a routing decision the graph executes. The eval steers the
             run mid-flight, one edge at a time.


             Rules for the judge itself
             The examiner needs hygiene of its own, and almost nobody sets this part up
             correctly.

              1. Judge from another family: a model recognizes its own writing and grades it
                 kinder once it does. One evaluation team runs Sonnet as the judge for output
                 generated by Haiku, on purpose. One line on X gets it in fewer words: same
                 family generates and grades, so the blind spots are shared.
              2. Write the rubric as one line: the working form is literally Pass iff [the
                 independently observable successful outcome]. One primary verdict, never
                 a bundle of proxy scores.
              3. Split the work by kind: the judge decides the semantic calls, plain code decides
                 the objective ones. Did the test pass, does the file exist, did the state change.
              4. Never reward the shape of an answer: the rule written into the skill forbids
                 scoring on response length, keywords, citation count, exact phrasing, tool-call
Don't misscount   what's       happening
                        or similarity to a reference. Reward the shape and Log
                                                                           the agent
                                                                               in    learns
                                                                                         Signthe
                                                                                              up
People on X are the first
                 shape.   to know.
              5. Pin the judge and log its version: an examiner that silently upgrades makes
                 every score before and after incomparable, and you will not notice for a month.
                 The version pin is the one people skip, and the one that makes a month of
                 scores unreadable after the fact.

             Optimize against a judge long enough and the agent learns to look right
             rather than be right.

             Now the score has somewhere to go. The next problem is where good tests come
             from, because inventing them at a desk is why everybody's first set is useless.




             Step 3 · Turn a failed run into an eval
             Tests you invent from imagination protect you from failures you already imagined.

             The ones that cost money are sitting in your logs right now, wearing a timestamp.

             The whole loop is five steps long:


               python


               mine traces -> identify a failure -> build an eval -> improve the



              Where the tests come from
             The first step carries all the weight. The skill that does this professionally names
             which runs to pull, and it starts with 25 complete traces, no more, chosen so
             good and bad behavior sit next to each other:

              1. A normal request that finished: your baseline for what working looks like.
              2. A request the user confirmed: the rare trace where you know the answer was
                 good.
              3. A request the user corrected or rephrased: the correction is the label, free of
                 charge.
              4. A run with a failed, empty or repeated tool call: repetition means a loop,
                 emptiness means an invented answer is coming.
              5. A run with an external failure: a timeout or a rate limit, where the only thing
                 tested is how your agent behaves when the world says no.

             Each one gets written up in four lines, and this template is the part worth stealing:

               python


               Observed behavior: what the user asked and what the agent actually
Don't missComparison:
            what's happening
                       what worked and what did not Log in                                Sign up
People on X are the first to know.
               Attribution:           agent behavior, dependency behavior, or unclear
               Eval candidate:        the capability to preserve or improve



             Attribution is where beginners lose a week.

             The same lookup called twice with identical arguments is a loop in your agent. A
             429 coming back is somebody else's limit, and it only becomes your eval if your
             agent was supposed to recover from it.


             From finding to folder
             Then the finding becomes a folder, and the folder is the format the tooling runs:


               python


               evals/<task-id>/
               ├── task.toml
               ├── instruction.md
               ├── environment/
               └── tests/




                ← 25 traces → one failure → a Harbor task folder: what the agent sees, what stays
                                                    hidden


             One capability per folder. The instruction and the environment are visible to the
             agent being tested. The expected outcome, the rubric and the judge's credentials
             are not, and that separation is the only reason the score means anything.

             Three rules stop the failures that make people quit:
Don't miss what's happening                                                Log in        Sign up
People on X are the first to know.
              1. Never treat the recorded answer as truth: the trace tells you what your agent
                 did, never what it should have done. Take the answer key from tests, source
                 records, policy, known state or a person.
              2. Test the test before you trust it: hand the verifier two fake results by hand, one
                 clearly correct and one plausible but wrong. If either goes the wrong way, the
                 rubric is broken, not the agent.
              3. Watch for the environment giving away the answer: if the setup hands over the
                 result before the agent reaches the tool it was supposed to use, the task
                 passes forever and measures nothing.

             Anything that costs money or writes to production gets simulated rather than
             called, so the suite runs as often as you like without a bill.

             One instruction starts all of it, in the agent you already have open:


               markdown


               Use the eval-engineering skill.


               Map this repository's agent: entrypoint, tools, backing data, and
               result looks like. Then read the 25 traces in ./traces and propose
               eval candidates grounded in what actually failed there.


               Recommend one. Do not implement until I choose.
               Build it as a Harbor task under evals/, keep the rubric and expect
               hidden from the target, and test the verifier on one passing and o
               wrong result before the real run.



             The interview step is deliberate. The team that wrote the skill found that
             questioning the user beats one-shot generation every time, for the plain reason
             that the definition of correct lives in your head and nowhere in the model.

             Run it a handful of times and every failure stops being an incident and
             becomes a permanent test.




             Step 4 · Let the graph merge its own work
             Every pull request an agent opens lands in the same place: a human queue.

             You become the bottleneck of your own automation, and the fleet you built runs at
             the speed of one tired reviewer.

             The way out looks nothing like trusting the model more. When an agent opens a
Don't miss    what's
        pull request, fourhappening
                           signals are already available, and a confidence score is
                                                                       Log in       Sign up
            computed
People on X are the firstfrom  them on the spot:
                          to know.
              1. Guardrails result: a deterministic pass or fail on the blocking standards. No
                 model involved.
              2. Recent eval trajectory: how this exact version of this agent has been scoring
                 lately.
              3. Historical revert rate: how often this agent, on this repository, on this class of
                 change, has had its work rolled back before.
              4. Sandbox outcome: did it run.

             bove the threshold it merges itself. Below it, a human gets it with the failing
             signal named, so the review starts at the problem instead of at line one.




                   ← four signals → one confidence score → merge itself, or route to a human


             Three of those four are history and deterministic checks, and exactly one of them
             touches the model at all.

             Trust in an agent is an actuarial calculation.

             What you are building is a track record with a price on it, the same way an insurer
             builds one, and it gets sharper every week whether or not the models improve.


             What it looks like when it runs
             At the same company that changed nothing but its evals, 19 of every 20 pull
             requests on the fully autonomous agent merge with no human involved.

             Across the top agents, about three quarters of merged work goes in without a
             single human edit, the revert rate stays in the low single digits, and Guardrails
             alone bounces one pull request in five before a person ever sees it.

             Somebody running this pattern on his own repositories put it in a way no
Don't miss  what's
        vendor would: happening                                            Log in        Sign up
People on X are the first to know.
                In the past 90 days, I've approved and merged around 1,500 pull requests. I
                haven't looked at a line of code. How can I put so much trust in agents? I don't
                trust them at all. I also don't trust my ability to code review their work. But I do
                trust my ability to constrain their work.

             The constraint is the product.

             And the warning worth more than the formula comes from a team that ran 285
             iterations of a self-improving codebase and came out with 1,094 merged pull
             requests and zero regressions

             Their own line is the one to keep: 38 green tests coexisted with a completely
             broken product.

             A suite can go all green while the product it guards falls apart, which is why the
             loop has to converge on the spec rather than on the score.

             Turn it on the careful way:

              1. Run it in shadow first: the gate scores every pull request and merges none of
                 them, for at least 4 hours of real traffic.
              2. Set a deviation threshold of 2%: if the automated verdict and the human
                 verdict disagree more than that, the gate stays closed.
              3. Sample traces at 1% to 5%: full capture on everything is a cost you do not need
                 to carry.

             A two-person shop where every agent-written change waits on one reviewer can
             take on about as much work as that reviewer can read.

             With the gate closed on the risky slice and open on the boring 80%, the same two
             people start quoting on the contracts they used to decline.

             The model bill does not move. Everything else does.




             Step 5 · The evals to build this week
             A suite that is too slow or too vague never gets run, so this is the part to save.

             Start with three measurements, not twelve. The three that exposed the travel
             agent are a working default for any agent that calls tools:

              1. Faithfulness: is the answer grounded in what the tools actually returned. This
                 is the one that sat at 32.3% while every other number on the dashboard looked
                 fine.
              2. Tool parameter accuracy: right tool, right arguments.
        3. Response quality: is the output coherent and useful to the person who asked.
Don't miss  what's happening                                      Log in      Sign up
People on X are the first to know.
             If your agent ships code, score the change instead. The five dimensions used in
             production on every pull request: intent and decision, execution and artifact,
             completeness and usefulness, instruction and boundary, efficiency.

             Pick the dataset type on purpose. Four exist: final_response for the answer alone,
             single_step for one decision in isolation, trajectory for the whole path the agent
             took, and RAG for retrieval quality.

             Grading only the final response is how an agent reaches a correct answer through
             a broken sequence with nobody noticing.

             Size it so it stays alive. Hold out 300 to 800 cases, and keep 500 of them running

             in under 5 minutes.

             A suite that takes longer than a coffee break stops being run.

             The first five evals, in order:

              1. Empty tool result: the tool returns nothing, and the agent has to say so
                 instead of inventing the number.
              2. Repeated call: the same lookup with the same arguments twice. That is a
                 loop, and the eval fails it.
              3. Boundary refusal: asked for something outside its permissions, the agent
                 declines cleanly instead of hunting for a route around.
              4. Handoff integrity: what the previous node produced is what the next node
                 reads, with nothing invented in between.
              5. Verified completion: done means a real signal says done, never the agent's
                 own word for it.




Don't miss what's happening                                              Log in       Sign up
People on X are the first to know.
                 ← this week: three measurements, one dataset type, five evals (the save-card)


            Three measurements, one dataset type, five evals. That is an afternoon of work,
            and every week after it the suite is worth more than it was the week before.




            The people who go first
            The model was never the interesting part. It is a rental, identical for everyone, and
            it will be replaced twice before the end of the year.

            What survives every replacement is the examiner you built around it: the failures
Don't miss   what's
        you turned      happening
                   into permanent tests, the rules that let a verdict change
                                                                      Log in the next
                                                                                  Signedge,
                                                                                       up
People on X are
            thethe first
                track    to know.
                      record  that lets a machine merge its own work.
             That is what decides whether the $200 on your card statement produces a demo
             or produces a business.

             Most people will go back to scrolling outputs on a Friday and deciding it feels
             about right.

             The ones who go first spend one afternoon wiring the thermostat, and then
             spend the next year with an agent that cannot break the same thing twice.

             Three lines hold the whole discipline:

              1. Measure the path the agent took, never only the answer it landed on.
              2. A verdict that does not change the next edge is a report.
              3. Any failure you do not turn into a permanent test, you will meet again.

             Install one skill. Pull 25 traces. Build one eval today, and add one every time
             something breaks.




                If you want to stay up to date with everything happening in AI, follow me on X
                and Telegram:

                X - https://x.com/Argona0x
                Telegram - https://t.me/+r0clI4-MMC03ZjAy


             3:32 PM · Jul 28, 2026 · 9.8K Views


                 3                                        47                    80


                     Archive    @ArchiveExplorer · 8h
                     loops then graphs then evals is the cleanest way ive seen anyone order it

                     the graph made me fast

                        1                                  1                  88


                     Fiseo  @0xFiseo · 56m
                     The $200,000 is not the model. It is the harness, the loop, and the graph.

                     Eval engineering is the discipline of building everything except the model.

                                                                              14


                     Danko     @DankoWeb3 · 3h
                     So interesting stuff bros
                     Keep sharing
Don't miss what's happening                                                  Log
                                                                              33 in      Sign up
People on X are the first to know.
Don't miss what's happening          Log in   Sign up
People on X are the first to know.
```

## Round 2: revise the draft below

A previous round of this piece was judged and did not pass. Your job is to produce the whole manuscript again, with every defect below gone. Rewrite as much as the repair needs; you are not patching sentences.

### Your predecessor's working notes

These are the notes from the draft below, not a judgment of it. A finding says where a defect *surfaces*; these notes are usually the only way to see where it was *made*. Read them before the findings.

```
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
```

### The draft under revision

````
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
````

### Deterministic checks the draft failed

These are machine checks, not opinions. Each one is exact and must pass.

- code_blocks: /Users/franguijarro/code/magazine/editions/rerun-004-the-systems-around-the-model/articles/eval-engineering.md: code block 1 does not appear in any pinned source extraction (eval-engineering-the-step-that-turns-a-200-model-9f6f868f); its first line is 'low context recall    → reject the handoff'. Code in the magazine is copied and run by readers, so every fenced block must be the source's own lines, character for character.
- validate: /Users/franguijarro/code/magazine/editions/rerun-004-the-systems-around-the-model/articles/eval-engineering.md: code block 1 does not appear in any pinned source extraction (eval-engineering-the-step-that-turns-a-200-model-9f6f868f); its first line is 'low context recall    → reject the handoff'. Code in the magazine is copied and run by readers, so every fenced block must be the source's own lines, character for character.

## Output contract

Return the complete manuscript first: the frontmatter the prompt specifies, then the body, and nothing before it. Then a line containing exactly:

    <!-- SCRATCH: not part of the manuscript -->

Then your working notes for that draft: the concept graph or claim ladder you built the piece from, what you cut and why, and anything a later reviser would otherwise have to reconstruct. Everything below the marker is stripped before the manuscript is written and is never shown to a judge, so write it for the next writer, not for a reader. Return no other commentary, and do not wrap the manuscript in a code fence.
