---
source_ids:
- pragmatic-leverage-in-the-software-factory-09879736
content_mode: faithful_edit
label: FAITHFUL EDIT
---

This one is a bit of an addendum / side-quest to the recent series. It didn't fit cleanly into the main post so I'm publishing it standalone. It is referenced briefly in Why Software Factories Fail part 2: Turning the lights back on.

## Seeking Leverage

Even before AI, only 25-50% of the time to ship a feature was writing the code itself. The rest was aligning/planning, code-review/rework, and testing/verifying the solution.

If you're only using AI to write the code, then you're taking the 2-4 hours of coding time down to 10-20 minutes, but you haven't accelerated anything else here.

But if you use AI to help you plan and align, then you actually get closer to 2-3x faster.

## The 80/20 rule in AI coding leverage

Let's assume if you yolo a two-sentence prompt into your factory, your chance of getting a fully-mergeable result is ~50% and the chance you have to rework it is 50%.

Now let's say you are a principal engineer with 10 years of experience. You have the whole codebase across 100 repos downloaded into your head. So you spend an afternoon writing a perfectly detailed spec by hand. Now your odds are better, but you probably still have about a 10% chance that you'll have to redo *something* significant.

And at the far end: write every line yourself. Nothing's left for the agent to get wrong, so the rework chance goes to zero.

For this example I'm gonna blur

> "chance you'll have to change something" weighted by "how painful the change will be"

into a single percentage number but obviously they're two separate variables. If the model is 50% likely to get a button style wrong, but the fix is one cheap prompt, then our combined "expected pain" is low.

> expected pain = P(you'll have to change it) × how painful the change is

Drawn out, there's an inverse relationship between effort invested up front and expected pain.

What you don't want to do is spend 6 hours planning a task for which you could have eliminated 80% of the expected pain in the first 10 minutes.

You need to do this without overindexing on questions you won't be able to answer without going down a level. For example, if you've done some work at the "Product" level and have not answered all the open questions yet, it's possible you may need to end it where you are and zoom down a level to the technical details to understand what's feasible. There's no perfect process for this.

This is what we mean by leverage, and it requires being pragmatic. If you're doing multiple phases of planning, zooming in from 50kft view all the way to the 10kft view, you want to do a little bit of steering at each phase to ensure you are eliminating as much expected pain as possible.

good luck.

<!-- SCRATCH: not part of the manuscript -->

Reprint rationale unchanged: ephemeral X article, no other access.

Findings resolved this pass:

- Mechanics / comma splice ("~50%, the chance you have to rework it is 50%"): fixed
  by inserting "and", per the suggestion. Grammar is explicitly not voice under this
  mode's judging criteria ("mechanics... where capitalisation and grammar are never
  voice"), so repairing a comma splice is not a paraphrase of the author's sentence,
  it's a mechanical correction, same footing as the apostrophe fixes from the prior
  pass.
- Mechanics / labeled aside ("**note** For this example I'm gonna blur"): removed
  the bold "**note**" label and left the author's sentence running as ordinary prose.
  This is normalizing markup for print (procedure step 3), not writing new apparatus;
  the words are the author's, only the typographic call-out is gone. This is not an
  editor's note in the sense the hard rule bans, it was the source author's own
  aside, but a labeled call-out reads as editorial apparatus on the page regardless
  of authorship, so the label goes and the content stays.

Findings NOT applied, left standing and recorded here instead:

- Shape / ending ("good luck."): declined. `docs/WRITING_RULES.md`, "Openings and
  endings," lists this exact line as a passing ending verbatim: '"Good luck." (the
  author's own, kept.)' Cutting it or subordinating it to the "steering" sentence
  would remove the author's sign-off, which the hard rules protect explicitly
  ("insults, and sign-offs... are the reason this mode exists"), and would contradict
  the house exemplar for this precise phrase. Declining per the rule that a
  suggestion which would damage the piece is not to be taken; the defect as
  described doesn't hold given the exemplar.
- Shape / orphan referent ("You need to do this"): unchanged from the prior pass.
  The only available repair is a bridging sentence naming what "this" refers to,
  which is new prose in the author's voice and is banned outright by the hard
  rules. Left as editor_decision; a human can either accept the ambiguity (the
  antecedent sits one sentence up and is recoverable) or decide the piece needs a
  different remedy this mode can't supply.
- Shape / argument order (50kft/10kft framework introduced after the Product-level
  example): unchanged from the prior pass. Reordering the author's own sections to
  introduce the framework before the example is forbidden ("Keep the source's...
  section order"). The source itself never states the two framings are the same
  model, so gluing them together would also be adding an inference the author
  didn't write. Left as editor_decision.

No other wording, order, or content changed from the prior manuscript.
