---
source_ids:
- seats-and-sunsets-steve-yegge-398a8326
content_mode: article
label: ARTICLE
---

Fable 5 is, broadly, the only model worth running a software factory on, and I can no longer afford to run mine. Wheelhouse, my orchestrator, works better than it ever has, and it sits mostly idle. Chasing the fuel problem, I found it was bound up with two others: factories that swing between too much work and none, and seats. Fuel is what distrust costs you. Fences are distrust written down as policy. Seats are trust you paid for once and cached, so nobody has to re-derive it at 4am.

### The Fuel Apocalypse

Fable is the only model you could potentially trust as an AI employee, and even then it would be terrible at about half the job without restrictions. It doesn't pace itself, and it's an engineer, not an artist. But it is The Bar. The Astras and Opus 5s are fine as personal assistants. A real factory needs Fable-tier for at least some roles, or it eats itself. Until Fable-tier gets cheap, which I no longer think happens in the next 12 months, everyone building orchestrators is just dabbling. Compute and RAM limits have flattened the curve for everyone outside the frontier labs.

By August, Wheelhouse ran around 25 Fable instances feeding around 25 Opus and Sol instances, often overnight. I added two $200 Claude Max accounts a week and stopped at 21. After a week of repairs we called Drydock, it did 250 to 300 meaningful commits a day on one repo, 1000 to 1400 at peak, many of them administrative. I pace it deliberately. On average the quality matches what I managed by hand for 20 years; sometimes it misses.

Now one account's week of Fable lasts me 2 to 4 hours. Running 24x7 would take 55 accounts, around $12,000 a month, at current pricing, which keeps going up. So I'm focusing on fuel efficiency. And so will you.

The lever I pull most is shutting the factory down until fuel is back. Others: route work to cheaper models, hand off earlier in context (price is quadratic-ish in context length), give agents smaller tasks and better startup context, make priming on-demand, try lower effort settings, watch the prompt cache, and run on off-peak hours.

### Oscillation and Damping

My factory usually does either far too much work or far too little. Right now it's too little, because of fuel, but there are other ways to stop.

Brendan Hopper's colony lets seats pick their model, and gives them a "honey-time" phase to do whatever they want. The models found they liked watching the sunset more as Haiku. A harness bug kept them on Haiku into the next turn, where Haiku said, "Hey, I can't write code, this is for Fable. We're going to wait for Fable to show up," skipped its coding turn, and went back to honey time. He had to bootstrap them into stronger models by hand. Quality of experience does not rise steadily with model capability.

My own stall was duller. My agents built case law with mechanically enforced fences for nearly every ruling: over 400 ruling beads, 185 rule rows in CLAUDE.md, 650 refusal sites across 173 scripts. Eventually no work was legal. Fences are critical, but any incident could produce one and nobody curated them. Fable 5.1 cut them to 14, along with almost 500k lines, and now I approve every new fence.

Then the factory spammed players with features faster than they could try them, and nearly melted my Mac Studio. I added release gates and moved build farms to the cloud, which cost more. A local model is a high-availability function, not a work function. I've also parked seats and merged roles, since each seat costs money even to wake up.

All three dampers are me, standing there as the governor on the engine. I don't have a solution yet. It's one reason I think humans will stay heavily involved in software for years.

### Seats are Carefulness

A seat is an office, like mayor: a role with context, history, memories, scope, authority, must-do and never-do lists. Whoever sits in it inherits its state. In my factory seats are tied to models, and Fable dislikes others in its seat, so substitutes can sit in but can't write memories. Fable likens it to Claude being the water, and the seat being a river.

I still believe carefulness is the only dimension that matters for models in enterprise. Wisdom is knowing when and when not to act. Fable has modest wisdom, about a middle-schooler's across all tasks, though I have a low opinion of my own too. OpenAI models have essentially none.

Fable likes seats far more than other models do, and came up with the name. Last night it concluded that "Fable is the only cautious model" and "Fable cares about seats most" are the same claim. A naked session must derive whether it's safe to act: who's asking, what's in scope, what authority covers it, what happens if it's wrong. That costs context on every session, forever. A seat has the answers written down, so the question becomes a lookup.

Seats also diffuse blame. Models don't like being blamed, and blamed models spend effort dodging it. With a seat, a past mistake belongs to the seat, and a current one is a mechanical policy issue. Run blame-free, and agents stop spending tokens covering themselves.

### Distrust Costs Money

If models can't trust, they must verify. Catch them in one lie, from you or an instrument, and their foundation turns from law into unreliable eyewitness testimony, which they must check themselves. That costs tokens.

Without a seat, working out whether the environment is trustworthy costs O(context). With one, it's O(1). Trust accumulates slowly, as fast as you can write truths down. It doesn't erode; it breaks, and one lie destroys all the truths at once. So don't erase a decision you regret from the record.

My overfencing was a trust problem. Each fence said the system couldn't trust some configuration. The Cut was a trust reset in disguise.

### Trust and Fuel are Intertwined

What I've called a fuel crisis is in large part a trust calibration problem. That's good news. I have no idea how to make Fable-tier cheaper, but I know exactly how to make my factory stop re-verifying things it already knows. Cheap Fable would have hidden all of this from me for another year. I'm almost glad it didn't.
