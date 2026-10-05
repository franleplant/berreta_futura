---
source_ids:
- evals-how-to-know-whether-an-ai-system-actually-a5c96be7
content_mode: article
label: ARTICLE
---

An eval is a repeatable test that tells you, with a number you can trust, whether an AI system does what you want, and whether a change made it better or worse. A language model does not fail like normal software. It does not crash. It produces a fluent, confident answer that may be wrong, and reading one good answer tells you nothing about the next hundred. The method has four steps: collect inputs with the right answers written down, run the system, grade every output with code, a second model, or a human, and turn the grades into one number with an error bar. The grader is part of the system you must test. The most common way an AI team fools itself is a confident number from an unchecked grader.

## One ticket through the loop

Our running example is a support assistant for a fictional bike and camping shop. **Triage** sorts tickets into 12 categories. **Answer** finds handbook pages and writes a reply that cites them. **Agent** looks up orders, issues refunds, and escalates against a mock database.

A customer asks about a late refund. Triage says *returns*, and gold says *returns*. The reply cites the returns section and states both required facts. Two code checks pass it. A model judge fails it, because it invented "a total allowance of up to 15 business days". A fluent reply can pass every surface check and still be wrong.

## Inputs, gold answers, and the number

Cases should look like real traffic, awkward ones included. Our 80 tickets came from a grid of persona × topic × scenario. Anthropic's guide suggests starting with 20 to 50 tasks taken from real failures.

Gold answers record the correct category, the sections a reply must draw on, and the facts it must state. Ours are correct by construction. In a real product they come from domain experts.

We use twenty tickets for tuning and sixty for reporting only, because tuning on the reported cases flatters the number.

An eval measures your system on your data. A benchmark measures a model on a public task.

## Read before you grade

Before building any grader, read the outputs. Write a note on each failure, then group the notes. On our 60 replies, 34 pass. The failures:

- missing required fact: 15
- unsupported claim: 12
- wrong section retrieved: 8
- did not answer: 5
- wrong value: 2
- over-promise: 1

That list is the specification: one grader per failure type, in order of frequency. Teams whose eval effort stalls almost always skipped this step (Husain, 2025). Expect the rubric to change while you grade. Shankar et al. (2024) call this criteria drift.

## Code graders

Code graders are free, instant, and give the same answer every time.

- Triage accuracy is 0.700, with macro F1 at 0.697.
- Only 17% of replies fit in 150 words.
- Required-fact checks catch the top failure type at zero cost.
- Embedding similarity separates good replies from bad with an AUC of 0.709. That is useful as a drift alarm and useless for saying whether a reply is correct.

Only 11.7% of replies pass all code checks, yet those checks caught none of the invented claims. Rules see form; they do not see meaning.

## Model judges, and checking them

**How to ask.** Ask one yes/no question per failure type. Require the judge to quote its evidence, and give it the context. Cho et al. (2026) planted three factual errors in a summary. Holistic judges gave it a perfect 5.0, and the question-based judge gave it 1.57. They also found that adding more instructions eventually made the judge worse.

**Checking ours.** We labelled the 60 replies by hand and ran the judge.

- Judge and humans agree on 60% of replies. A judge that said "pass" to everything would agree on 57%.
- Cohen's kappa, which corrects for chance, is 0.15. The usual bar for gating a release is 0.6, and 0.8 for running unsupervised.
- The judge passes 42 replies where 34 deserve it, and catches 10 of the 26 bad ones.

Iterating on the dev set brought the missing-fact question to a usable level. The unsupported-claim question did not get there and went to a specialised detector.

**Known biases.**

- **Position:** grade both orders.
- **Length:** use binary questions or length control.
- **Self-preference:** use a judge from another model family.
- **Satisfaction over success:** give the judge the tool calls and the final state.
- **Judge identity:** record the judge's model and version.

**The GAUGE audit** (Bodhwani et al., 2026) covered 25 agents and about 3,700 transcripts. It tested the usual release gate: a simulated user talks to the agent, a judge scores the transcript, and the higher score ships.

- When one agent was clearly better, the gate ranked well (correlation 0.94).
- On near-equal pairs, it promoted the worse agent 31% of the time.
- A judge that saw only the chat was a coin flip (AUC 0.49). A judge that also saw tool calls, authentication, and resolution reached 0.73.

Their conclusion: reliability comes from what evidence the judge is given, not from how strong the judge model is.

## Honest numbers

**Error bars.** A bootstrap puts triage accuracy at 0.700, with a 95% CI of [0.583, 0.817]. Miller (2024) showed that most reported differences between models in published evals are smaller than such intervals.

**Paired comparisons.** We tested a second prompt that retrieves more sections, on the same 60 tickets. Both versions score 0.700, and the difference's interval is [-0.117, +0.117], so we keep v1. Yet v2 regressed on 14% of cases while improving others. A difference whose interval includes zero is noise.

**Detection floor.** With 60 cases, the smallest difference we can reliably detect is about 12 points, so a 5-point regression is invisible.

## Systems with parts

**Retrieval.** Grade the finder and the writer separately. Our finder scores hit@2 0.93 and recall@2 0.88. Of 18 failing replies, 1 failed in the finder and 17 in the writer. RAGAS told the same story: context relevance 0.855, faithfulness 0.737.

**Agents.** Grade the final state and the path, and run each task several times.

- pass@k measures capability. pass^k measures reliability, and customer-facing agents need pass^k. Ours scores pass^3 = 0.75.
- Rabanser et al. (2026) studied 15 frontier models. Two years of capability gains delivered about one sixth as much reliability gain.
- Bai et al. (2026) found the same task on the same model varied 30-fold in cost, and accuracy peaked at intermediate cost. Models predicted their own cost with a correlation of at most 0.39. Rank models on cost per correct outcome.

## Making it a habit

**Cadence.**

- Every commit: code graders.
- Every change to prompt, model, or retrieval: judges, detectors, and human review of a sample.
- After shipping: an A/B test on real traffic.

**The gate.** Our CI gate fails the build if the pass rate drops more than 3 points below 0.70. With a 12-point floor, a 5-point regression walks through. Say so in the dashboard.

**Monitoring.** After launch, run cheap graders on all traffic and expensive ones on a slice. Calibrate the cheap gate against ground truth once, and trust it only inside that region. Re-audit when the model, judge, simulator, or domain changes.

**Cost.** Our full A/B costs 121 judge calls, about four cents. Cost is not the reason to skip evals.

**What a leader should ask for.** Four numbers on one page:

- the pass rate with its interval
- the grader's agreement with human labels
- the detection floor
- the share of cases that got worse in the last change

If any is missing, the other three are not yet meaningful.
