---
source_ids:
- pragmatic-leverage-in-the-software-factory-09879736
content_mode: faithful_edit
label: FAITHFUL EDIT
---

Writing the code was never the bottleneck. It was a quarter to a half of the work; the rest was agreeing what to build, reviewing it, and proving it worked. Aim the machine only at the code and you cut hours to minutes on the part that was already cheapest. Aim it at the thinking and you move two or three times faster. But thinking has a floor: the first ten minutes remove most of the risk, the sixth hour removes almost none. Spend accordingly.

## Where the time goes

Before any of this, only 25–50% of shipping a feature was typing code. The remainder went to aligning and planning, to review and rework, to testing.

So if the agent writes your code, two to four hours becomes ten to twenty minutes, and nothing else has moved. The other three quarters of the day sit exactly where they sat.

## The shape of the curve

Yolo a two-sentence prompt into the factory: call it a coin flip. Half the time it merges, half the time you do it again.

Now be a principal engineer with ten years and a hundred repos loaded in your head, and spend an afternoon writing the spec by hand. Better odds — but still roughly one in ten that something significant has to be redone.

At the far end sits the man who writes every line himself. He has left the agent nothing to get wrong, and his chance of rework is zero. He has also left himself nothing.

I am blurring two things into one number here — how likely you are to have to change it, and how much the change hurts:

> expected pain = P(you'll have to change it) × how painful the change is

They are separate variables. A model that gets the button style wrong half the time costs you one cheap prompt. Low pain, high probability. Fine.

Draw it and the relationship is plain: effort up front, expected pain down. The curve is steep at the start and flat at the end.

## Being pragmatic about it

What you must not do is spend six hours planning a task where ten minutes would have killed 80% of the pain.

Nor should you overindex on questions you cannot answer from where you stand. Work at the product level, find the open questions won't close, and the honest move is to stop, drop a level, and look at the technical detail to see what is even feasible. There is no clean process for this.

That is what leverage means. If you are planning in phases, from the 50,000-foot view down to the 10,000-foot one, steer a little at each altitude and take the pain off the table while it is still cheap to remove.

good luck.
