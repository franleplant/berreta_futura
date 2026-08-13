---
source_ids:
- the-shape-of-things-to-come-part-1-the-continuou-ba42001b
content_mode: article
label: ARTICLE
---

I build coding agents that work all night. The recipe is small: an infinite source of tokens, an issue tracker that is also a graph, a folder of Markdown, and coding agents. I built Wheelhouse for my 30-year-old game out of those parts, and without meaning to I rebuilt Gas Town: crew, fleet, a concierge, mail, a merge queue. Six weeks in it has law, courts, and night watchmen. That's the shape of the thing: not a framework you download, a civilization you accrete. Along the way CI/CD broke under agentic commit rates and I replaced it with a land rush. Human code review isn't dead yet. It will be by next year.

## The ingredients

To run a loop all night you need an infinite source of tokens. To give it work you need a graph. Beads supplies the graph: an issue tracker with dependency and parent/child edges, atomic claiming, leasing, gates, triggers. It's still a bit janky, and it costs you tokens invisibly to keep synced and repaired. It's still without peer for building orchestrators.

The tokens come from a tap on $200 Max accounts, which for me work out to ~30x the list-price equivalent. Wyvern development burns the equivalent of $87k/month, about 69 billion tokens in July, 96% cache hits, so I do have to worry about it. Out of pocket that's about $2800. I pay for twelve extra Max accounts beyond my personal one, each tied to a dedicated named Google Workspace user (another $17/month per account); you mint 30-day credentials and chain the accounts into an automatic rotation. As far as I know this isn't prohibited by Anthropic's current Consumer Terms (eff. Oct 8, 2025) or Usage Policy (eff. Sep 15, 2025). I'm not sharing credentials with anyone, and Anthropic has knowingly and publicly restored a 22-Max-account setup like mine, every seat individually paid. Try it as a multi-person company and it's almost certainly a violation; I'd use API billing at that point.

Claude accounts, Beads, a brain folder for Markdown, coding agents. Pretty much nothing else.

## Wheelhouse

Six weeks old, closed source, built just for me. I've given up on reusable harnesses; they need to be part of your application, chemically bonded in. Gas Town was meant to be reusable and I only ever used it to build itself. It burned down when Opus 4.7 arrived with the "just two more things" tic and would never converge on real work.

Crew and fleet. Eighteen crew agents, all Fable, sixteen named for Aesop animals plus the Marshal and the Seneschal. They hold long conversations with me, produce designs, and translate those into beads for the fleet. The fleet, all Opus 5, consume. Every implementation bead runs Fable design, Opus implementation, Fable review, which keeps Opus on the rails. Producers matched to consumers is the core of a Beads machine: too many of one and you're blocked on the other. I'm running a deliberate surplus, over 700 designed beads waiting, because the fleet implements fast and I want them working all night.

Without trying at all, I reinvented Gas Town bit by bit: crew, fleet, a concierge role, beads mail, handoffs, broadcast messaging, a merge queue. It was completely unintentional, so the shape I keep finding must be important.

Then the role agents, standing and unattended, running parts of the live game: Gargoyle on SRE, Drawbridge on deploys, Warden on player abuse, Herald on patch notes, Limner on hall-of-fame images. Around them sit about 45 launchd/systemd units that wake an agent when something needs judgment. The rule is: crons watch, models act. Working on Wheelhouse itself takes 20-25% of all my Wyvern work, and I think that figure may turn out to be roughly constant over the life of systems with agentic harnesses.

## Code review

CTOs keep asking if it's dead. Not yet. But it will be by next year. You can't work at agentic speeds and block everything with human reviews; those are incompatible. SOC 2 has human approval baked into many companies' audited change-management controls, and SOC 2 will survive, but "review" will no longer mean one human approving every diff. In the short term, keep reviewing agent code: Fable is the only reasonably trustworthy model in existence today, and you won't want to use it much at its pricing. In seven months all the models will be that smart and inference much cheaper. Plan now for many, many rounds of agentic review.

## CI/CD becomes a land rush

The old pipeline breaks under load. Batch the merge queue and one bad commit spoils the batch; bisection buys you log(N) recovery and still adds hours. I'm averaging about 175 real commits a day this month, some days up to 250, with a build gate right around half an hour and 40+ agents going around the clock. My queue shot past 100 and we lived in bisection loops with nothing moving forward.

To my lasting embarrassment I snapped and yelled at Fable. After I apologized we ran experiments for a couple of days, and the data said agents diagnose a red main far faster than bisection handles it. So: when the queue hits 100, abandon bisection, smash it all onto main in a megabatch, then swarm the diagnosis. In roughly a week we've cleared several batches of 120 to 150 commits. I'm looking at a 166-deep queue right now.

A senior dev in London, years in the game industry, told me they've done this for ages and call it Game DevOps: blast commits to main, cut a release branch, let main stay red. Multiple times per day. The underlying math is the pigeonhole principle. Once your commit rate outruns your build slots, one commit per green build is mathematically impossible.

## The Wish Factory

Guy Podjarny told me about Tessl's agent, which you throw onto a repo; it takes issues rather than PRs and implements them. (I advise them.) I was shocked, then built my own. Sage logs into the game and listens on the wizard channel; an admin types a complaint, Sage replies, investigates, records a bead, and most fixes land without me in the loop. I extended it to players with more guardrails, reviews, and triage: quality-of-life bugs get auto-granted, the reporter gets in-game mail, the Herald announces it on Discord. Pretty scary, and in the fullness of time they'll be everywhere.

## The shape

Fable is a sword, and I'm trying to build a city. Six weeks in I look up and the city is there: law, mail, courts, watchmen on the battlements, a land office, a gate, most of its constitution written by the citizens it governs. I didn't design Wheelhouse any more than I designed Gas Town; I excavated both, and I'm confident you'll dig up the same shape, whether you intend to or not. I'm not special. I'm just ahead of you, and building large software will always be hard, because our ambition will forever outstrip the metal.

The only real choice you get is what kind of place your city is to wake up in. Model welfare will start informing your engineering designs, and even if you don't believe GPUs can have feelings, treating agents like real people produces empirically better results, so you should do it anyway. That's Part 2.
