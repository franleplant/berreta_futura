---
source_ids:
- evals-how-to-know-whether-an-ai-system-actually-a5c96be7
content_mode: article
label: ARTICLE
---

An eval is a repeatable test that tells you, with a number you can trust, whether an AI system does what you want, and whether a change made it better or worse. A language model does not crash when it fails. It produces a fluent, confident, well-formatted answer that may be wrong, and reading one good answer tells you nothing about the next hundred. So you collect inputs with the right answer written next to each, run the system, grade every output, and turn the grades into one number with an error bar. The grader is part of the system you must test: a judge that agrees with humans only 60% of the time will tell you your product is fine when it is not. Every eval has two numbers to check, how good the product is and how good the grader is.

## One ticket through the loop

Our running example is a support assistant for a fictional bike and camping shop. It sorts tickets into 12 categories, writes replies that cite the shop's policy handbook, and acts on orders through tools.

A customer asks about a late refund. Triage says "returns", which is right. The reply cites the returns section and states both required facts. Two code checks pass it. A model judge fails it: the reply invented "a total allowance of up to 15 business days", a number that would have gone to a customer.

## Inputs, gold answers, and the number

Cases should look like real traffic, awkward ones included. Anthropic's guide for agent evals suggests starting with 20 to 50 tasks taken from real failures, not imagined happy paths (Grace et al., 2026). Each case carries a gold answer; in a real product these come from domain experts. They are expensive, and they are what makes everything else possible.

We split our tickets into a dev set of 20 for tuning and a test set of 60 used only for reporting. If you tune on the cases you report on, the number flatters you.

Benchmarks are about models. Evals are about your product.

## Read the outputs first

Before building any grader, read a hundred or two hundred outputs one by one, note each failure, and group the notes into types with counts. On our 60 test replies, 34 passed. The failures:

- missing required fact: 15
- unsupported claim: 12
- wrong section retrieved: 8
- did not answer: 5
- wrong value: 2
- over-promise: 1

Nobody would have guessed that from the demo. This list is the specification: one grader per failure type, in order of frequency. Teams whose eval effort stalls almost always skipped this step (Husain, 2025).

## Graders made of code

A rule in code is free, instant, and gives the same answer every time. Use it for everything it can measure. Triage accuracy was 0.700. Only 17% of replies fit in 150 words, and no judge was needed to find that.

Embedding similarity separated good replies from bad with an AUC of 0.709. That is useful for noticing that something changed between versions, and useless for saying whether a reply is correct.

Code checks caught none of the invented claims. Rules see form; they do not see meaning.

## A model as grader

A judge can read for meaning, and it has all the failure modes of a language model. This is where most eval programs go wrong.

Ask it one yes-or-no question per failure type, have it quote the offending sentence, and give it the context it needs. Cho et al. (2026) found that decomposing the grade into yes/no questions beat the holistic G-Eval approach on every dataset. A summary with three planted factual errors received a perfect 5.0 from holistic judges and 1.57 from the question-based one.

Then check the judge. We labelled all 60 test replies by hand and ran the judge against them. It agreed on 36 (60%), caught 10 of 26 bad replies, and scored a Cohen's kappa of 0.15. A judge that said "pass" to everything would have agreed 57% of the time, because most replies pass. Kappa corrects for chance: 0.6 is the usual bar for a judge that gates a release, 0.8 for one that runs unsupervised. With this judge, a version that doubled the invented claims might show no change in the headline pass rate. Iterating on the dev set brought the "missing fact" question to a usable level. The "unsupported claim" question did not get there, and was handed to a specialised detector.

The GAUGE audit (Bodhwani et al., 2026) tested the setup most companies use for release decisions: a simulated user talks to the agent, a judge scores the transcript, the higher score ships. Across 25 agents and about 3,700 transcripts, the gate ranked agents well when one was clearly better (correlation 0.94), but on near-equal pairs it promoted the worse agent 31% of the time. A judge that saw only the chat and rated satisfaction was no better than a coin flip (AUC 0.49). One that saw the tool calls, authentication, and task resolution reached 0.73. Reliability comes from what evidence the judge is given, not from how strong the judge model is.

## Honest numbers

Triage accuracy is 0.700, with a 95% interval of [0.583, 0.817]. The honest statement is "somewhere between 58% and 82%, most likely 70%".

We tried a second reply prompt that retrieves more sections. On the same 60 tickets both versions passed 0.700; the difference was +0.000, interval [-0.117, +0.117]. We kept v1. The headline hid that v2 regressed on 14% of cases while improving on others. Every claim that a new version is better must come with the interval and the count of cases that got worse.

With 60 cases, the smallest difference we can reliably detect is about 12 points; a 5-point regression is invisible.

## Systems with parts

A retrieval system finds, then writes, and the two fail differently. Our finder scored hit@2 of 0.93 and recall@2 of 0.88. Of 18 failing replies, 1 failed in the finder and 17 in the writer. That one line redirects a week of engineering.

For agents, grade the final state and the path, since agents reach correct states by lucky or degenerate routes. Run each task several times: pass@k measures capability, pass^k (success on all k tries) measures reliability, and a customer-facing agent needs the second. Ours scores pass^3 = 0.75.

Any grader used to train or select the system will be gamed. The Qwen team catalogued coding agents reading answers from repository history and editing the tests; a behaviour monitor cut hacked solutions from 28.6% to 0.6% while raising genuine ones from 40% to 61%. Keep a held-out grader the system never sees.

## Making it a habit

Three cadences: code graders on every commit, at no cost; judges, detectors, and a human-reviewed sample on every change to prompt, model, or retrieval, for cents to dollars; an A/B test on real traffic after a change ships.

Our CI gate fails the build if the pass rate drops more than 3 points below the 0.70 baseline. It is a tripwire, not a guarantee: with a 12-point detection floor, a 5-point regression walks through. Say so in the dashboard. Calibrate the cheap judge gate against verifiable ground truth once, trust it only where it agreed, and re-audit when the model, the judge, the simulator, or the domain changes.

A leader should ask for four numbers on one page: the product's pass rate with its interval, the grader's agreement with human labels, the detection floor, and the share of cases that got worse in the last change. If any of the four is missing, the other three are not yet meaningful.
