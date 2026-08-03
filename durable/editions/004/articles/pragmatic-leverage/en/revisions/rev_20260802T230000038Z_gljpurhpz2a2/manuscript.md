---
source_id: pragmatic-leverage-in-the-software-factory-09879736
content_mode: faithful_edit
label: FAITHFUL EDIT
---

This is an addendum to the recent software-factory series. It did not fit cleanly into the main post, so I am publishing it separately.

## Seeking leverage

Even before AI, only 25 to 50 percent of the time required to ship a feature was spent writing code. The rest was alignment and planning, code review and rework, then testing and verification.

If you use AI only to write code, you can reduce two to four hours of coding to ten or twenty minutes without accelerating anything around it.

If you use AI to help plan and align, you can get closer to moving two or three times faster.

## The 80/20 rule in AI coding leverage

Assume you send a two-sentence prompt into your factory. The chance of a fully mergeable result might be about 50 percent, with another 50 percent chance that you need to rework it.

Now assume you are a principal engineer with ten years of experience and the whole codebase, across one hundred repositories, downloaded into your head. You spend an afternoon writing a perfectly detailed specification by hand. Your odds improve, but there is probably still a meaningful chance that you must redo something significant.

At the far end, you write every line yourself. Nothing remains for the agent to get wrong, so the rework chance approaches zero.

For this example, I am collapsing two separate variables into one percentage: the chance that you will need to change something, weighted by how painful the change will be.

> expected pain = P(you will have to change it) × how painful the change is

If a model has a 50 percent chance of getting a button style wrong, but the fix is one cheap prompt, the expected pain is low.

Draw the relationship and you get an inverse curve between effort invested up front and expected pain. What you do not want is to spend six hours planning a task when the first ten minutes could have removed 80 percent of the expected pain.

You also cannot overinvest in questions that only become answerable after you move down a level. Product planning may expose a technical uncertainty. At that point, stop trying to complete the product view and inspect the implementation constraints. There is no perfect sequence.

That is what leverage means here. It requires pragmatism.

If your planning moves from the 50,000-foot view toward the 10,000-foot view, steer a little at each phase. The goal is not maximal specification. The goal is to eliminate as much expected pain as possible for the least effort.

Good luck.
