---
source_ids:
- pragmatic-leverage-in-the-software-factory-09879736
content_mode: faithful_synthesis
label: FAITHFUL SYNTHESIS
---

Even before AI, only 25–50% of the time to ship a feature was writing the code itself. The rest was aligning and planning, code review and rework, and testing and verification. AI can cut 2–4 hours of coding to 10–20 minutes, but the larger gain comes from reducing the uncertainty around the work.

## Seeking leverage

If you use AI to help plan and align, you can get closer to 2–3x faster. The leverage comes from deciding how much effort to invest before asking the agent to build.

Assume that if you yolo a two-sentence prompt into your factory, your chance of getting a fully mergeable result is about 50 percent, and your chance of having to rework it is 50 percent.

Now imagine a principal engineer with 10 years of experience and the whole codebase across 100 repos downloaded into their head. They spend an afternoon writing a perfectly detailed specification by hand. The odds improve, but there is still perhaps a 10 percent chance that they will have to redo something significant.

At the far end, write every line yourself. Nothing is left for the agent to get wrong, so the rework chance reaches zero.

The useful measure combines “chance you'll have to change something” with “how painful the change will be”:

> expected pain = P(you'll have to change it) × how painful the change is

If the model is 50 percent likely to get a button style wrong, but the fix is one cheap prompt, the combined expected pain is low. The probability and the cost are separate variables; this example blurs them into one percentage.

The payoff from planning is largest at the start. You do not want to spend six hours planning a task when the first 10 minutes could have eliminated 80 percent of the expected pain.

You also need to avoid overindexing on questions you cannot answer without going down a level. If you have done some work at the “Product” level and have not answered all the open questions, you may need to end it there and zoom down to the technical details to understand what is feasible. There is no perfect process.

When planning happens in multiple phases, zooming in from the 50kft view to the 10kft view, do a little steering at each phase. The aim is to eliminate as much expected pain as possible without spending more time than the problem calls for.

Good luck.
