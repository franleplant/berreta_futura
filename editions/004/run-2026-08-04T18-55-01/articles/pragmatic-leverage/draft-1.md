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

Lets assume if you yolo a two-sentence prompt into your factory, your chance of getting a fully-mergeable result is ~50%, the chance you have to rework it is 50%.

Now lets say you are a principal engineer with 10 years of experience. You have the whole codebase across 100 repos downloaded into your head. So you spend an afternoon writing a perfectly detailed spec by hand. Now your odds are better, but you probably still have about a 10% chance that you'll have to redo *something* significant.

And at the far end: write every line yourself. Nothing's left for the agent to get wrong, so the rework chance goes to zero.

**note** For this example I'm gonna blur

> "chance you'll have to change something" weighted by "how painful the change will be"

into a single percentage number but obviously they're two separate variables. If the model is 50% likely to get a button style wrong, but the fix is one cheap prompt, then our combined "expected pain" is low.

> expected pain = P(you'll have to change it) × how painful the change is

If you draw this out, there's an inverse relationship between effort invested up front and expected pain.

What you don't want to do is spend 6 hours planning a task for which you could have eliminated 80% of the expected pain in the first 10 minutes.

You need to do this without overindexing on questions you won't be able to answer without going down a level. For example, if you've done some work at the "Product" level and have not answered all the open questions yet, its possible you may need to end it where you are and zoom down a level to the technical details to understand what's feasible. There's no perfect process for this.

This is what we mean by leverage, and it requires being pragmatic. If you're doing multiple phases of planning, zooming in from 50kft view all the way to the 10kft view, you want to do a little bit of steering at each phase to ensure you are eliminating as much expected pain as possible.

good luck.

<!-- SCRATCH: not part of the manuscript -->

Reprint rationale: ephemeral X article, no other access. Restated above.

Chrome removed: the "dex @dexhorthy" byline line and the source's own H1 ("# Pragmatic Leverage in the Software Factory") — title/byline are pinned in edition.yaml per the format spec, and the body must open on a paragraph so the illustrated opener can set it. No other chrome (no nav, ads, or engagement counters) was present in the extraction.

Typography: no changes needed beyond the heading removal. Left the two headings as `##`, kept the two blockquotes, kept bold markers on "*something*" and "**note**" as in source.

Referents left standing: "the recent series" and "the main post" (paragraph 1) are named specifically enough one line later ("Why Software Factories Fail part 2: Turning the lights back on") that a reader isn't lost; I did not invent a link or fuller title since the extraction doesn't supply one. Flagging for editor_decision per the missing-referents rule in case a fuller citation is wanted.

Voice preserved as-is, including the author's typos/informality ("Lets", "its possible" for "it's possible", missing apostrophes) and the lowercase sign-off "good luck." — did not capitalize to match the house-doc's stylized quotation of it, since that would be altering the author's own casing.

Words I wrote myself: none in the manuscript body. Only this scratch note and the reprint-rationale line in my reply are mine.
