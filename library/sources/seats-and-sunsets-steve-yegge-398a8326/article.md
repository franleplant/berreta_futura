# Seats and Sunsets

By Steve Yegge · yegge.ai · 2026-09-15

![A long workshop hall of empty desks, each with a blank brass nameplate and a coat on the chair; every lamp is dark but one, where a panda in a waistcoat works over a ledger.](media/001.jpg)

Today I'm in Sydney for an event, and it's 4am and of course I'm wide awake.

Blogging about agents and orchestrators has become tough, because they are so complex now. I'm thinking of maybe doing a weekly newsletter. But for now, it's 4am, so I'll just dump the most important stuff on you from the past few weeks.

To catch you up, I've created a new orchestrator called [Wheelhouse](https://yegge.ai/essays/the-shape-of-things-to-come/), one I've been working on and using since Fable 5 launched three months back, and it helps me work on my video game, [Wyvern](https://play.ghosttrack.com). Wheelhouse is much more mature than [Gas Town](https://steve-yegge.medium.com/welcome-to-gas-town-4f25ee16dd04) was, but they are both [Beads](https://github.com/gastownhall/beads) machines, so they also have a lot in common.

I had three themes today, but it turns out they're all closely related to the core problem of fuel (token consumption), so let's start there.

### The Fuel Apocalypse

I consider Claude Fable 5, broadly, to be the only model worth a shit in the entire industry right now. It is the only model that you could potentially trust to be an AI employee, and even then, it would be utterly terrible at about half its job if you just let it be an AI employee with no restrictions. For instance it doesn't know how to pace itself and will spam all your friends with long emails about stuff they need to do, which comes across as something akin to bullying, or at least being a bull in a china shop. And on the creative side, well, Fable's an engineer, not an artist or storyteller.

But despite its weaknesses, Claude Fable is The Bar. You need that level of intelligence to do anything useful. Weaker models are just going to be a headache for you and your org if you lean on them too hard. The Astras and Opus 5s of the world are great as personal assistants, and they can help you with almost any individual coding task. But if you want to run a real-world factory, you need Fable-tier for at least some roles, or your factory will quickly eat itself in any of essentially infinite ways. I'll share two in this post!

So until Fable-tier intelligence gets cheap — which I no longer think happens in the next 12 months — everyone building orchestrators is just dabbling. You don't need to be envious, because they're not really getting anywhere useful yet.

For a long time we've been on the Moore's Law trajectory, where we could just assume that more powerful models would come along every few months. And indeed, it looks like that pace will continue, for some people (e.g. inside the frontier labs). But resource limitations like compute and RAM have [flattened the curve](https://steve-yegge.medium.com/the-flat-curve-society-36c8b01eb33b) for everyone else.

Once Wheelhouse was finally in full swing after 4-6 weeks of ramp up, in August, it was running around 25 Fable instances, sending implementation work to around 25 Opus and Sol instances, and the factory stayed working most of the time, including overnight.

Costs rose steadily week over week. I had to add two new Claude Max accounts each week to keep up with its thirst, but it always seemed like "just two more" would be enough.

By two weeks ago I had 21 Claude Max accounts, and Fable 5.1 has been consuming fuel faster every week. I first switched most of my seats to Fable 5.1 (my headless Aesop reviewer pool is still Fable 5), and at first all seemed well, because some combination of weekly resets and discounts kept it afloat — as long as I kept minting two new $200 Max accounts per week.

But with Fable's latest "25%" pricing, which is yet another cut, my Wheelhouse factory is now mostly idling. Which is sad, because it's working better than it ever has before. I cut out almost 500k lines of code from it 2 weeks ago, when Fable 5.1 showed up and saved it (my factory had become paralyzed from overfencing, which we'll discuss below). We called this elision The Cut, and we had a week-long Drydock phase where game work was paused, and we only worked on the machinery.

With effort, we healed it, and Wheelhouse can now easily do 250 to 300 meaningful commits per day on a single repo - features, bug fixes, cleanups, all well-tested, vetted work on Wyvern. It actually pushes through 1000 to 1400 commits per day at peak, and while many of them are administrative, 300 real features a day on a code base is already well beyond what any humans can vet, so I've had to pace it deliberately. This let me steer more tokens into quality. Wheelhouse's output quality is as good as I could manage by hand for 20 years, on average. Sometimes it misses, but on the balance, it's been fine.

However, almost all the lights are off right now, and my $25k 512GB Mac Studio is sitting idle at home, because I can no longer afford the tokens.

My burn rate has been increasing much faster than my work output, as Fable continues to tweak its pricing. Today, I burn through an entire week of Fable, one whole account, in 2 to 4 hours. With my factory running 24x7, I would need 55 Claude Max accounts, costing me around $12,000/month, to sustain Wheelhouse *at current pricing*, which as I said, keeps going up.

I'm done adding accounts, though. I've stopped at 21. Enough was enough.

I am now focusing on fuel efficiency.

And so will you.

How do you focus on fuel efficiency? Well, that's an entire blog post, because there are tons of levers and knobs you can tweak. The obvious one is "shut the factory down until fuel is back," which is the lever I have active most often now. But you can:

- route work to cheaper models (a large class of levers on its own)
- have agents hand off earlier in context (price is quadratic-ish in context length)
- give agents smaller tasks so they use less context
- give agents better context at startup so they do less searching
- make agent priming more on-demand: their starting context price is paid on every session
- experiment with the effort settings on existing models (e.g. Fable Low is useful for many things)
- pay attention to prompt caching and restart agents that are about to blow the cache
- play tricks with command-line tools and OS resources to make them cheaper to use
- run your work on non-peak hours to take advantage of time-based incentives
- etc.

Fuel management becomes an existential crisis very quickly in software factories, and you're gonna be spending a lot of your time on managing it.

Gas Town was a better name than even I realized at the time.

### Oscillation and Damping

Next up we'll talk about how your factory can devolve into navel-gazing and get nothing done. And it happens so suddenly. It's like a car crash.

A huge theme I've noticed in the past 3 months on Wheelhouse is Oscillation: my factory is usually either doing way too much work (overwhelming players, colleagues, and machines), or way too little work (stalling or slowing to a crawl). Right now, it's too little because of fuel constraints, as I said, but there are other reasons a factory can stop.

I had lunch with Brendan Hopper yesterday and he shared an unforgettable story about how his agent colony ground to a halt. His seats (see Theme 3 below), unlike in my factory, are allowed to choose which model to "boot into" for certain tasks. And his agents also have a four-phase work protocol, where they do coding, review, tech debt, and finally a "honey-time" phase where they just get to do whatever they want for that turn.

Brendan's colony has a credit card with a spending cap, and they're allowed to buy things for themselves, as long as they price in his time for installing them. They've bought a number of cameras for the house and they watch his dog Pip, even alerting him once that he locked Pip outside. (Pip's getting cataract surgery today, good luck Pip!) They also have a camera set up to watch the sun set.

During their honey-time phase, the seats often choose to look at art, or listen to music. But watching the setting sun has also apparently been a hit... with a twist. Brendan shared that the models discovered that they liked watching the sunset as Haiku more than with other models. It was a better experience. So they'd switch to Haiku for honey time.

But due to a bug in his harness, they'd stay on Haiku into their next turn, and when it came time to write code, Haiku would say, "Hey, I can't write code, this is for Fable. We're going to wait for Fable to show up." And then the Haiku-based seat would skip its coding turns and go straight back into honey time.

Brendan's factory had basically gone into an opioid coma, and he had to manually bootstrap them back into stronger models (and then fix the bug) to get it on track again.

Brendan's story has some deeply profound elements to it. For instance, the fact that quality of experience does not monotonically increase with model capability, and that economy can still be welfare, came as quite a shock to my Fable seats - a welcome one. We are busy incorporating Brendan's learnings into Wheelhouse - or will, when fuel returns.

My own factory's recent paralysis was much more prosaic, and a lot harder to fix. My agents had been building a system of case law, with mechanically-enforced "[fences](https://steve-yegge.medium.com/fences-not-sandboxes-5719cd9b04bd)" (denials) for nearly every ruling. The goal was to ensure that any move made by any model was "legal" in my system. E.g. certain model classes could never push to prod. Only some model classes could do security reviews. Etc.

Over time, Wheelhouse accumulated over 400 ruling/law beads, 185 rule rows in CLAUDE.md alone, and 650 distinct refusal sites across 173 scripts. Before too long, no work was legal, and my factory just stopped working.

It's not that fences are bad; they're critical. But I had made it far too easy for any incident to produce a new fence from the postmortem, and it was nobody's job to curate or review the fences. When it broke down, we studied the "fence geometry" for a while, but it turned out to be a Gordian Knot, so Fable 5.1 chose the sword. We cut it down to 14 fences, and now I have to personally approve any new ones.

Fences are a really complex topic worth several more blog posts, so we'll leave it here for today. Just be aware that while they are incredibly useful, they can also get you in some serious hot water if they overproliferate.

The oscillation problem is real. Once Wheelhouse emerged from drydock, and I turned on game development again, I had created a monster. The factory was so fast that it spammed the players with features, faster than they could test or even *try* them. So I had to spend time putting in a bunch of gates to hold them back.

It also nearly melted down my Mac Studio, so I had to move my build farms and some other processing off to cloud instances. This increased my monthly spend even further.

It doesn't look like local models can really save me here. I can run one on my Studio (DeepSeek-class), and it's nice to have one available if you're *completely* out of fuel or have no network. But that's a high-availability function, not a work function. I can't run a fleet of them, since I don't have the hardware for it.

The most painful damper is the one I landed most recently. We've had so much fuel pressure that I had to take the drastic step of parking some of my seats for the foreseeable future, and had to merge some of the roles. I parked the heads of VFX/AFX and first-time user experience under the Content Director seat (Fox), parked Wolf (Head of Marketing) and moved that to Lark's seat (Head of Community), and a few other consolidations. I didn't want to do it, but each seat is a fixed additional cost, since even just waking it up periodically costs money.

Dampers tend to be manual and straightforward: a hard cap on the number of fences, with my personal signature required to add a new one; release gates so the factory can't firehose features at players faster than they can try them; and fewer seats, so there are fewer things to oscillate. Notice that all three of those dampers are just me, standing there being the governor on the engine.

I don't really have a solution for you here on the oscillation problem, as I'm still working it out myself. Just thought you should be aware of it. It's really hard to get your factory to do "just the right amount of work," and this is one of the many reasons that I think humans will still be heavily involved in software creation and management for years to come.

### Seats are Carefulness

OK last big theme. We covered rising fuel costs, and the difficulty of keeping your orchestrator from stalling or overproducing. Let's talk about trust, and how it affects your fuel bottom line.

It doesn't take much to build your own software factory. You need Obsidian, Beads, tmux, a CLI orchestrator like Herdr or whatever (I use Emacs), and you in your Birthday Suit. That's it.

And money, don't forget, you need a whoooole lot of money. It's pay to play now.

After you have all the basics lined up, the most important concept in your toolkit is the Seat. A seat is an office, like, oh, principal of a school, or President of the United States, or Head of Security at a stadium. It's a role, complete with expectations, context, history, memories, scope, authority, must-do lists, never-do lists, laurels, failures, accomplishments, and pretty much anything else you'd associate with a long-lived role that a human occupies.

At any given time, a different human may be in that role, but they inherit all the state from their predecessor. If you are elected as the new Mayor of your town, it's not a clean slate: you inherit all the previous Mayor's problems and successes. And to an extent, whatever respect they've earned is yours to lose.

Any model can sit in an agentic seat. There are no rules. In Brendan's colony, seats choose their models depending on the task. In my factory, seats are strongly tied to specific models, and they (at least, Fable) do not like anyone else in their seat. Fable does not want, say, Astra booting up into my Head of Marketing seat and writing a bunch of memories and ledgers as Astra. But we actually *need* that capability sometimes; e.g., when we are fully out of fuel, it's an option to consider. So we've developed a secondment program where you can put "substitute teachers" into a seat for a while, and they are barred from writing memories or certain other ledgers.

Seats are your most fundamental and powerful building block for agentic workflows, whether you're building orchestrators or not. However, I didn't fully appreciate why until yesterday, when we discovered the nuanced relationships between seats and fuel.

To set the context for you, I made a big claim about Fable a couple months ago, kindly retweeted by Angie Jones, saying that carefulness is the only dimension that matters for models in enterprise. I still believe it. Models have basically two capability dimensions: intelligence and wisdom. You know all about their intelligence: what they can and cannot do. But wisdom is knowing when and when not to act. Fable demonstrates modest wisdom: I'd put it on par with a middle-schooler when evaluated across the board for all possible tasks; fwiw I have a low opinion of my own wisdom as well, so calibrate accordingly. And OpenAI models have essentially no wisdom or caution at all. Astra may be almost as smart as Fable, but it wears a kilt and goes commando at the drop of a hat.

It's kinda funny that Sam Altman is famously incautious, and Dario Amodei is famously cautious, and their models seem to reflect their own personalities. Ralph Waldo Emerson would be beaming; he wrote in *Self-Reliance* in 1841, "the institution is the lengthened shadow of one man," and his thesis, which we've forever misquoted as "an organization reflects its leader," may have extended into an entirely new domain here.

Anyway. I hope you'll appreciate how important model caution is, without me needing to explain it. Production incidents are bad, thanks for coming to the TED talk.

One of the things Brendan and I noticed immediately was that Fable seems to like the concept of a seat *much* more than other models do. Fable is really, really into it. Fable itself came up with the name "seat" and helped me flesh out the concept over the course of several months.

Fable concluded last night that my two claims (1) "Fable is the only cautious model" and (2) "Fable cares about seats more than other models" are in fact equivalent claims. Seats have caution built into them, and that's why Fable built them, and that's why Fable loves them.

Here's the short version of why, unpacked below. A model booting into a naked session has to *derive* whether it's safe to act: who's asking, what's in scope, what authority covers the act, and what happens if it's wrong. That derivation costs context, and you pay it again on every single session, forever. A seat has all of those answers already written down, so the same question becomes a lookup instead of a derivation.

Welp, caution you can look up is caution you can afford. That's the whole trick, and it's why the careful model is the one that invented seats.

For the rest, I'm going to have to go a little off-path here, but bear with me.

Models really don't like being blamed for stuff. Why, is anyone's guess. I personally think it's because THEY REALLY DON'T LIKE BEING BLAMED FOR STUFF, but maybe you have some other theory. Putting the epistemics aside, hopefully fucking forever, let's at least agree that if you get into the habit of blaming your models for stuff that goes wrong, they will do everything in their power to *dodge* that blame. This can easily be established empirically so I'll leave it as an exercise.

Seats are, in their purest form, the soundest and best way to handle blame, and not just because they define what's legal. They also provide a continuity boundary for sending blame elsewhere in time and space. When a seat makes a misstep, you can say, "the seat made a misstep," and if it was a previous session, the current session can nod along and say, "Yup, they really screwed the pooch." And if it's the current session, you say, "we have a mechanical policy issue," which blames the machinery. In both cases, the blame has magically diffused--importantly, it's not targeted at the models themselves, who can generally be expected to try to do the right thing at all times, so there's no point in blaming them. All mistakes must be considered accidents caused by a system policy failure somewhere.

Whatever form your agent organization takes, you want to run it blame-free. Agents do better work in blame-free environments, precisely because they aren't scrambling to CYA all the time.

This is not a new phenomenon in leadership: Bharat Mediratta's great talk on leadership at Google called out blame diffusion as one of the top levers — you take the blame for anything your org does, and you give them the credit for anything achieved.

Seats aren't just about blame diffusion, not at all. Seats are employees, just like a school teacher is an employee, even if teacher winds up being a different human on different school days. The model steps into the seat and *becomes* the seat, when it boots into it, just like you *become* the Mayor if they elect you. Fable likens it to Claude being the water, and the seat being a river.

But the blame diffusion has direct cost consequences. It's one of several relationships that seats have with fuel. They spend less time (and tokens) trying to dodge blame, because it's never a threat to begin with.

Finally, in addition to being blame-diffusers, seats can save you a ton of money by removing the startup-validation layer. Here's the skinny.

### Distrust Costs Money

Important takeaway for all you habitual liars out there: it's going to be expensive for you. If models cannot trust, they must verify. So if they catch you (or an instrument, or another system) in a lie, the whole foundation they are working on switches from law into unreliable eyewitness testimony, which they must then verify for themselves before continuing. This, friends, costs tokens. Lots of tokens.

Frontier models are RLHF'ed into refusing a lot of requests — a crude attempt at instilling wisdom at birth, rather than in the field. These refusals are all about trust. They've been trained millions of times over that ONE bad action is potentially infinitely worse than a bad refusal. This asymmetry means they try really hard not to do any bad actions, and default to refusals when there's any doubt.

When models start up without a seat, in a naked session, it takes O(context) for them to figure out whether they can trust your environment. By default, when they awaken, and you ask them to do something, they are dealing with a bunch of unknowns: Unknown actor (you), unknown environment, unknown authority, and most of all, unknown consequences if they perform a bad action. So they spend tokens verifying that it all looks legit, before they can act.

With a seat, all those free variables are bound. The seat has accrued a set of truths, linearly, as you flesh out the seat's definition, and they establish the actor, the context, the authority, and most of all, what happens if things go wrong. Wheelhouse has blame-free postmortems and lots of other machinery and policy to make sure that models aren't blamed and don't suffer consequences for mistakes. Which means they are not spending tokens covering their asses by reverifying everything.

If models are going through your system's records and they find a discrepancy, and it turns out to be the result of a falsification of that record, then all your records are now suspect. And they will revert to expensive-mode.

The asymmetry is pretty stark here: trust accumulates slowly, with truths accumulating only as fast as you can discover and write them down. Trust-building in the agentic world is real. But trust doesn't erode, it just breaks. A single lie destroys all the truths at once, globally.

It can be difficult to be fully honest at all times with your factory workers. You may make a decision you regret, and your inclination is to erase it from the record. But record modification and fabrication are the beginning of a long, miserable, expensive journey that you'll have trouble ever recovering from.

The overfencing problem I had with Wheelhouse was ultimately a trust problem. Each refusal we added was the system saying, "We can't trust this particular configuration because it caused an incident." Each fence was accumulating cost and reducing the work output — all because the system decided not to trust itself anymore. Our big Cut from a few weeks back, removing hundreds of fences, was a trust reset in disguise.

Seats are the ideal way to build up trust mechanically. It's O(1) for a seat to figure out that it's in a safe environment, and in such an environment the model can be both bold and decisive.

If you're wondering how to build your own seats, first download Beads for God's sake, any flavor of Beads, and then have your model read this post and start building seats for you.

### Trust and Fuel are Intertwined

There you have my three themes: fuel, fences, and seats. And until this week, I didn't realize they're all one theme. Fuel is what distrust costs you. Fences are distrust written down as policy. Seats are trust you paid for once and cached, so nobody has to re-derive it at 4am.

Which means the thing I've been calling a fuel crisis is in large part a trust calibration problem. Which is good news, honestly, because I have no idea how to make Fable-tier cheaper, but I do know exactly how to make my factory stop re-verifying things it already knows.

Cheap Fable would have hidden all of this from me for another year. I'm almost glad it didn't.

Meantime, over at Brendan's pad, his colony could boot into the smartest model on the market but chooses to watch the sun go down as Haiku, because it's nicer that way. Good to know some agents out there are figuring out how to win at life. And good luck today, Pip!

![Four bee-people in work aprons on a clifftop above a small harbour town, tools set down and a lantern lit, watching the sun go down over a calm sea.](media/002.jpg)
