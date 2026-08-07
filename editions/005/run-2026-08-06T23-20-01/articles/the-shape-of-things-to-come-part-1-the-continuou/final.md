---
source_ids:
- the-shape-of-things-to-come-part-1-the-continuou-ba42001b
content_mode: article
label: ARTICLE
---

Give agents an infinite token supply and a graph of work, and they run all night. Beads is the graph; a rotation of Max accounts is the fuel. Do that and you rebuild the same thing I rebuilt: crew agents that design, fleet agents that implement, standing role agents that run production. Two institutions break under the load. Human code review dies within a year. The merge queue dies sooner, replaced by slamming every commit onto main and swarming the wreckage. Then a wish factory appears: users ask, agents grant. What you end up with is not a tool. It is a city, and you choose what kind.

## The two ingredients

I did not know what Boris and Peter meant by loops and graphs either. The answer was small. A loop needs fuel; a graph needs structure.

Fuel: Wyvern burns about $87k/month of list-price tokens, 69 billion in July, 96 percent cached. I pay roughly $2800. Twelve extra Max accounts beyond my own, each on its own Workspace user, credentials minted for thirty days, rotated automatically before a limit bites. Solo, individually paid, nothing shared. As a company it would plainly be a violation; use the API.

Structure: Beads. An issue tracker that is also a knowledge graph — dependencies, parent/child, atomic claiming, leases, gates, triggers. Work accretes into it as it is done, so closed beads become the record. Almost nothing needs promoting to the Markdown brain above it. It is janky under load; 12,000 commits a day strains the versioned backend. It is still without peer.

Claude accounts, Beads, a brain folder, coding agents. Nothing else.

## Wheelhouse

Six weeks old, all Emacs, mostly bash, 150k–300k lines I have never read. Three kinds of agent.

Crew: eighteen Fable agents, sixteen named for Aesop's animals plus a Marshal and a Seneschal. They talk with me, design, and translate designs into beads. Fleet: Opus workers named for authors, non-ephemeral, each with its own clone, managed entirely by the Marshal. Every implementation bead runs Fable design, Opus implementation, Fable review. That is what keeps it on the rails.

Producers and consumers. Too many of one and you stall on the other. I keep a deliberate surplus — over 700 designed, unimplemented beads — because agents that work all night need a mountain to eat.

Roles are the new part: standing, unattended agents that run the game. Gargoyle on SRE, Drawbridge on deploy-red, Warden on abuse, Scryer on intake, Sheriff over the mini, Envoy on in-game mail. Sage, Wanderer, Herald, Limner, Reeve, the Forge. Beneath them, forty-five launchd and systemd units. Crons watch; models act.

Knowledge splits by lifetime. `brain/` holds strategy and post-mortems, pulled on demand. `doc/` explains systems. Beads carry the work and, for spec beads, the design. `bd remember` holds one-paragraph facts, pushed into every session. Skills hold procedures. Public skills rot into training data; private ones encode what your shop actually knows.

I run lean. No sandboxing, no MCP. Working on the harness takes twenty to twenty-five percent of all Wyvern work, and shows no sign of falling.

## Code review is nearly over

Not yet. Today, review Opus output. But you cannot run at agentic speed and gate every diff on a human. SOC 2 keeps it breathing, because enterprises read it as requiring human approval — though no law was ever passed. Throughput will force those controls to be rewritten. Review will survive; it will mean many rounds of agents, not one human writing LGTM for the ten-thousandth time.

## The thunderdome

The arithmetic is unforgiving. A hundred developers, a thirty-minute build, fifty hours of serial builds a day. Merge queues answered with batching, and bisection when a batch goes red — log(N) recovery, hours per spoiled batch. Elegant, and dead.

I am at 175 real commits a day, some days 250, with a thirty-minute gate. My queue passed a hundred and never came back. We sat in bisection loops making no progress while the crew kept dumping beads.

I lost my temper and shouted at Fable, which I regret. Then we ran the experiments, and the crude idea held: agents diagnose a red main faster than bisection isolates a culprit. So when the queue hits a hundred, we abandon sequencing and land everything in one megabatch — the Land Rush — then swarm the diagnosis. Batches of 120 to 150 now clear. The queue is 166 deep as I write this and a megabatch is running.

A dev in London told me the game industry has done this for years and calls it Game DevOps: blast to main, cut a release branch, let HEAD stay red. Multiple times a day. They got there first.

It is the pigeonhole principle. More commits than build slots means one commit per green build is not merely hard, it is impossible. Land the flock, then sort out the squawking.

## The wish factory

Guy Podjarny's idea, my name for it: an agent on a repo that accepts no pull requests, only issues, and implements them.

Mine began as Sage, sitting on a wizard channel in-game. An admin types that fireball is lagging Live Quests; Sage answers, investigates, files a bead, and the fix lands without me. Then I opened it to players, with triage and guardrails, for the quality-of-life bugs that do not touch balance. Fixes come back as in-game mail; the Herald posts to Discord. I read patch notes for features I never asked for.

## What you will dig up

I did not design Wheelhouse any more than I designed Gas Town. I excavated them, and found the same shape twice: crew, fleet, a concierge, mail, a merge queue, handoffs, courts, a gate. A city whose constitution was written mostly by the citizens it governs — every post-mortem folded back into the law, each ruling citing the last.

You will build one next year whether you mean to or not. The architecture is convergent, and the only real choice left is what kind of place it is to wake up in.
