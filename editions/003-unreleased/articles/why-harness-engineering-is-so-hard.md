---
source_id: why-harness-engineering-is-so-hard-fe732038
content_mode: faithful_synthesis
label: FAITHFUL SYNTHESIS
---

Five months, 104 commits, and one repeating lesson: harness engineering is hard.

An illusion settles over almost every project built on a large language model: that the model is the product. An API call, a prompt, an impressive first demo — and the hard part feels finished. It is not.

The difficult part is turning that demonstration into behaviour you can rely on: the same constraints across inputs, the right ideas without drifting, surviving model updates, failing visibly instead of silently, output that can be tested though never perfectly deterministic.

That behavioural layer is much of what I mean by the harness: the prompts, examples, schemas, validators, evals, and guardrails between a probabilistic model and the person using your product. The model generates the output; the harness makes it usable.

This keeps surprising otherwise excellent engineers. I've spent months in it; most of the pain comes from structural facts that look like ordinary software problems, but are not.

## You can't write the test you want to write

Your testing instinct breaks first. Every practice you've built assumes determinism: given this input, the code produces this output, and I assert equality. Feed a language model the same input twice and you get two different outputs — a few words apart, but enough that strict equality is useless.

This removed the floor under my quality strategy. You can assert on structure and invariants, but both are weaker than engineers are used to and let unexpected output through. Instead of one output equalling one expected answer, you ask whether the system satisfies a rubric across a distribution of inputs and repeated runs — a confidence level, not a proof.

Failure, meanwhile, is silent and graded, not binary. Ordinary software announces failure; model output does not crash. A model 95% correct and 5% broken produces a response that looks fine, the wrong 5% woven into the right 95%. The most dangerous outputs almost pass: drifting off a constraint, inventing a plausible value instead of admitting ignorance, obeying a rule's letter while breaking its spirit. None of these crash. All of them ship. You can't catch what you can't see, so much of harness engineering is making the invisible visible: checks that surface drift, humans in the loop where confidence is low.

## You're debugging prose, not code

When the harness breaks, the "code" at fault is often a paragraph of English; the only debugger is your judgment. A single word can be the bug: I've spent hours tracking a regression to one adjective the model read as permission to do something I never intended. A one-word bug is invisible — it shifts the model's behaviour a few degrees, enough to quietly corrupt output. You reason about a prompt the way a writer reasons about a paragraph, by feel: a genuinely different skill from debugging.

The most reliable failure pattern is the additive trap: something breaks, and you add a rule to the prompt. But the growing prompt is the disease, not the cure. Natural-language rules interact unpredictably: a fix for one failure contradicts an earlier fix; "never do X" makes the model think about X, and X appears where it never did; the over-constrained model quietly picks a rule to violate. I've watched a prompt grow from twenty lines to two hundred until it could barely produce anything good. The fix, every time, was to subtract — remove rules, collapse duplicates, enforce constraints in code — and the jumps in quality came from deletion, not addition.

A corollary: examples steer harder than rules. Write "don't do X," include an example that does X, and the model will do X. The example wins. Everything in a prompt is a behavioural program; no part is neutral, and every token pushes the model somewhere.

## The foundation rewrites itself

The model is not a stable foundation. Vendors update it, sometimes unannounced, and behaviour changes. Your defences, tuned to the old model's failure modes, now guard against problems that no longer occur while the new ones go unguarded. With Opus 5, many report previously reliable skills files simply stopped working.

Your tests can be green while your product regresses: they assert against the old model's behaviour, and the model moved. No "lock the version" escape hatch holds forever. A harness is never "done"; the honest response is minimal prompts, validation that catches drift, and the humility to expect the next update to break something you can't yet name.

Feedback loops are slow and expensive, too. One model call costs money, and an end-to-end test can take minutes to hours. You can't brute-force twenty variations in a minute; you try three, wait, read carefully, try one more. Expense also breeds under-testing: you convince yourself a change is small enough to skip the full run. It almost never is, and under-testing a probabilistic system is how you ship drift.

## The difficulty is the point

The last pain is social: nobody can see the work. "Prompt engineering" sounds as hard as writing an email. The tightening, the removed contradictions, the silent failures caught before shipping — all invisible. Make it visible on purpose — track the failures you caught, measure the drift you prevented — and accept that some of the value will never be legible to those around you.

Every one of these pain points is structurally hard. They come from the substrate: a probabilistic system with no stack trace, no determinism, no stable contract, no separation between "the program" and "the data it was trained on." You can't engineer those facts away; you can only build a harness that absorbs them.

And that, honestly, is the moat. If harness engineering were easy, the model would be the product, and anyone with an API key could compete. A real application is hard to build for the same reason it's hard to copy: turning probabilistic output into a shippable, reliable, tested thing is invisible, painful, and not transferable by reading your prompt.

The pain is the work, and the work is the moat.
