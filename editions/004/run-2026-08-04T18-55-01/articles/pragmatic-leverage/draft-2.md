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

Let's assume if you yolo a two-sentence prompt into your factory, your chance of getting a fully-mergeable result is ~50%, the chance you have to rework it is 50%.

Now let's say you are a principal engineer with 10 years of experience. You have the whole codebase across 100 repos downloaded into your head. So you spend an afternoon writing a perfectly detailed spec by hand. Now your odds are better, but you probably still have about a 10% chance that you'll have to redo *something* significant.

And at the far end: write every line yourself. Nothing's left for the agent to get wrong, so the rework chance goes to zero.

**note** For this example I'm gonna blur

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

- Mechanics (3 findings, apostrophes): fixed as spelling normalization — "Lets" -> "Let's" (twice) and "its possible" -> "it's possible". These are mechanical corrections, not wording or voice changes, so they don't conflict with the hard rule against paraphrasing the author's sentences.
- Craft (repeated if/then shape): cut one instance per the finding's own suggested remedy ("cut one instance or restructure one section"). Changed "If you draw this out, there's an inverse relationship..." to "Drawn out, there's an inverse relationship...", dropping one conditional clause while keeping every word of the claim. Left the other four if/then constructions untouched — each is doing real argumentative work (the AI-leverage claim, the expected-pain formula, the Product-level example, the closing steering advice), and cutting more would start reordering the author's reasoning rather than trimming one repeated shape.

Findings NOT applied as suggested, left standing and recorded here instead:

- Shape / missing transition ("You need to do this..."): the suggested fix is a new bridging sentence ("To navigate this trade-off, find where..."). That's new prose written in the author's voice to connect two of his own points, which the format's hard rules ban outright ("no transition... of any kind inside the article"). I left "You need to do this" as-is; its antecedent (stop planning once you've eliminated most of the expected pain) is one sentence up, so a reader can still follow it, just without a signposted bridge. Recording per the missing-referents rule so this reaches a human as editor_decision rather than getting quietly patched with a note.
- Shape / orphan referent (50kft/10kft vs. "Product" level/technical details): the suggested fix asks me to introduce the framework with a clarifying gloss connecting the two framings. The source itself never states these are the same model, only implies it, so inventing that connective tissue would be adding an inference the author didn't write, in his own voice, inside the article, which the mode forbids. Left both framings as the author wrote them and record the possible mismatch here for editor_decision.

No other wording, order, or content changed from the prior manuscript.
