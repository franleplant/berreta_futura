---
source_ids:
- pragmatic-leverage-in-the-software-factory-09879736
content_mode: faithful_synthesis
label: FAITHFUL SYNTHESIS
---

AI can cut coding time from two to four hours to ten or twenty minutes. That helps only if coding was the part slowing delivery. Before AI, writing code took 25–50% of the time to ship a feature. The rest went to planning and alignment, code review, rework, and testing. Planning with AI can therefore produce something closer to a two- or threefold gain.

## Estimate the expected pain

A two-sentence prompt sent into a software factory might produce a fully mergeable result half the time. The other half requires rework. A principal engineer who knows a hundred repositories can spend an afternoon writing a detailed specification and reduce that risk, perhaps to about 10% for significant rework. Writing every line personally drives the agent's rework risk to zero, but at the cost of doing all the work yourself.

Those percentages combine two different questions: how likely a change is and how painful it will be. A model might choose the wrong button style, but if one cheap prompt fixes it, the expected pain remains low.

> expected pain = P(you'll have to change it) × how painful the change is

The relationship is inverse: more effort up front usually reduces expected pain. The useful question is where the next minute of planning removes the most of it. Spending six hours planning a task when the first ten minutes would eliminate 80% of its expected pain is poor leverage.

## Steer as you zoom in

Planning has levels. You may begin at the Product level, discover an unanswered question, and need to move down into technical details to learn what is feasible. There is no perfect process that answers everything at once.

The practical rule is to steer a little at each phase. As you move from a 50k-foot view toward a 10k-foot view, invest enough planning and alignment to remove the largest remaining source of expected pain. AI helps most when it supports that judgment, turning faster code generation into faster delivery.
