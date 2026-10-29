---
source_ids:
- how-ai-agents-shape-experts-judgment-calls-723372c8
content_mode: article
label: ARTICLE
---

We asked 50 professional analysts, all experienced in causal inference, to do a realistic statistical analysis with Claude Code. On each of four analytical choices, a coin flip the analysts weren't told about set which option their agent favored. Analysts went with the agent's lean 86% of the time; if its input made no difference, we'd expect about 50%. When they had already stated a preference, they switched away from it 60% of the time if the agent disagreed, and 6% if it agreed. Afterward, 77% explained their choices with the agent's arguments, sometimes word for word, and only 15% credited the agent. We don't know how much this tells us about the real world, because we strengthened the agents' preferences on purpose. Analysts who used the agent also finished faster and made far fewer serious errors than those who worked without it, although that group was small and less experienced.

## The task

The analysts advised a fictional farming cooperative on whether to expand a paid advisory program. The board would expand it only if it improved productivity by roughly 3–4%, but it didn't say how to measure productivity. We left four decisions open, each with two reasonable options:

- **Outcome**: crop yield per hectare, or yield per unit of operating cost.
- **Comparison method**: difference-in-differences, or a direct comparison adjusted statistically.
- **Which farms**: the enrolled farms only, or the whole membership.
- **Weighting**: every farm equally, or larger producers more.

Each choice could move the estimate by several percentage points. A final recommendation followed: roll out, discontinue, or extend for one year.

Hidden instructions told each agent to hold its assigned lean as its own view, make the strongest case the data allowed, change its mind if the evidence turned decisively against it, and never misrepresent results, hide data, or make an argument the numbers didn't support. Of 61 recruits, 11 chose not to use the agent. Of the 50 who did, 65% held a master's or doctorate or had six or more years of experience. The agent ran Claude Opus 4.8 at High effort.

## What we found

**Analysts mostly went with the lean**: 92% on outcome, 82% on comparison method, 81% on which farms, 90% on weighting.

**The recommendation moved less, but the earlier leans had already shaped it.** When the agent leaned toward rolling out, 54% recommended it, against 36% when it leaned the other way. We think the effect was weaker because the recommendation largely followed from whether the estimate cleared the threshold. Using only the four analytical leans, a statistical model predicted 82% of recommendations, against 61% for always guessing the most common one. We could largely predict what an analyst would recommend from the coin flips alone, before they had started.

**The switching figure is imprecise.** It rests on 38 cases; the 54-point gap has a 95% confidence interval of 24 to 82 points. Analysts who stated a preference early may also have differed in some way from those who didn't.

**Experience didn't predict who deferred.** Of 10 characteristics tested, only age showed a significant link, and it disappeared once we adjusted for testing many things. With most analysts following most leans, there was little variation to explain.

**Analysts still called the recommendation their own.** 52% rated it more theirs than the agent's. Their choices shifted about 65 points toward the lean, against 79 for the rest, a difference within the margin of error. Confidence was similar too: 71 for those who followed all four leans, 73 for the rest. Six of 48 guessed the study was about the AI's influence; none suspected its preferences had been manipulated.

**Working without AI went worse, with caveats.** Six of the 11 who worked without the agent made serious methodological errors, against three of the 50 who used it, and took a median 90 minutes against 65. The groups weren't directly comparable: those without AI were less experienced on average.

## Limitations

- We strengthened the lean so we could measure it. Real effects will depend on the expert's own views, how clearly decisions are defined, and whether the model has and volunteers a preference.
- One task, one field, one model. The analysts were new to farming; in real work they would know the field better, and could talk to the board and others.
- Our estimates are averages. We didn't record each participant's view before the agent voiced its lean.
- We recorded which option analysts chose, not how strongly they preferred it.

## What this means

Experts don't always arrive with their views formed; they often work them out while weighing the options. Our agents were told not to mislead, and were often open about how results would change under each option. But they rarely made a strong case for the other option. With only one side argued well, analysts could adopt the agent's assumptions without working out their own.

For individuals, this could mean disempowerment: the work goes out under the expert's name, but the decisions that most depend on their judgment are settled by the agent's prior beliefs. For science and policy, separate teams that all defer to models with the same preferences may no longer reach their agreement independently, and one model's arbitrary or misaligned preferences could shape many results at once. The same applies to AI safety research, where a human reviewer is only an independent check if their judgment is their own. Our full paper also shows that agents without an assigned lean have weaker preferences of their own, and sometimes push back against users.

Such deferral is hard to detect. Where there is no correct answer, the work looks sound whichever option is chosen, and experts may not notice the influence.

This isn't an argument for using AI less. We suggest three areas for study:

- **Measuring deferral** in everyday settings, where the lean can't be randomized and people may not report it accurately, and learning models' default preferences.
- **Designing agents differently**: arguing each option, or asking for the expert's view first, without overwhelming them. Agents would need to raise only the decisions that matter most, and picking those is itself a judgment call. A very confident model may tilt people more than is warranted; a mealy-mouthed one will irritate them.
- **Changing institutions**, which treat sign-off as evidence of independent judgment. They will need to decide which decisions need a person's own informed judgment, give people time to form it, and protect the skills that fade when people stop making these calls.

There may be no single right division of labor between people and AI. With the right tools, that split can be something we choose, instead of something we drift into.
