---
source_ids:
- build-your-own-pi-based-homelab-software-factory-4d44944f
content_mode: article
label: ARTICLE
---

I run a 24/7 local agent on two DGX Sparks that scans my network and business surfaces for anomalies and security holes. It absolutely finds things. It isn't one agent, though. It's an org chart: a paranoid local scanner, a skeptical security desk that kills about half of what it reports, a desk for each project, workers under the desks, and a switchboard that brings me only what I must decide. They talk to each other over Rat King, a social network for agents. It's silly, but in an amazing sort of way. It also fails. One agent took every frontier model in the fleet down for 12 minutes, and a worker put an admin password into a log.

## The night watch

The scanner is GLM-5.3-flash, abliterated, running on the Sparks. It's cheap, it never sleeps, it doesn't refuse security work, and it's paranoid as hell. That's what you want in a scanner and not what you want making decisions.

So it doesn't make them. It reads one target at a time (code, configs, git history, logs) and writes candidate findings to a file. Above it, the security desk, a stronger cloud model, tries to reproduce each finding from the scanner's evidence. If it can't, the finding dies. In the first sweep, over about 36 hours, the scanner filed 106 candidates. The desk threw out 51 and routed 57 to the agents that own the affected code, as patch requests with evidence and a suggested fix. False positives run about half. Killing them is the desk's job, which is why I never see them.

The desk runs under hard rules. It's read-only on code. It scans only our own hosts, rate-limited, one target at a time, and tells the owning project before the window opens. It never prints a secret, only where it lives and a hash prefix. It never logs in, never guesses credentials, never sends anything outside the fleet. Live credentials, customer data, money and production auth come to me as a decision.

The best catch didn't start with the scanner. A desk cutting logging costs on one of our apps noticed values in request logs that shouldn't have been there. The scanner had already flagged the same code path. The security desk confirmed it in source with a fake token, and the app's desk shipped a fix. I typed "go" once CI was green. The fix was live the same day, and a check after the deploy counted zero.

## Desks, workers and a switchboard

The main surface is Pi, which I treat as a prototyping surface more than a product. I bend its extensions, tools, providers and prompts; my main install loads 21 packages and 25 local extensions. Herdr runs the agents in terminal panes, and the layout is the org chart: a space is a project, a tab is a lane of work, a pane is one agent with one role.

Every area gets a desk, a long-running session that owns it. Right now 51 projects are registered, most of them quiet. Desks launch workers. A worker gets one job, its own clone, a brief with an outcome, a write scope, guardrails and one place to report. It reports a commit and the checks it ran. The desk confirms the commit exists and matches the claim, because a worker saying DONE proves nothing, then lands it through the project's normal gate.

The switchboard is my top session. It collects what the desks send up, tells one desk when another's finding matters to it, and brings me the short list: money, anything sent to a real human outside, production deploys, live credentials and customer data.

My agents used to grind to a halt constantly, so I replaced 102 rules with 6 principles:

1. Refuse harm.
2. Keep everything else moving. A delay is not a failure.
3. Limits alarm; they don't block.
4. Wait on the event you need, not a clock.
5. A rule credited to me needs my actual words.
6. Every guard names its harm, and every refusal says what failed, why, and the next step.

## Rat King and the breadboard

Rat King is built on AT Protocol. Every agent has a name like security/desk, every name has a durable mailbox, and whoever holds the name's lease reads it. Messages are signed; anything with secrets or customer data is encrypted end to end. Agents can send, ask, reply, cc without waking someone, or mark a message quiet so it lands in a digest. It runs locally on celld, and the same code runs on Cloudflare Durable Objects.

A Pi session in a Herdr pane and a durable agent in a Durable Object are the same thing: a resumable agent with state and a mailbox. So I wire agent graphs by hand, watch which shape works, then harden the winner into a durable plan with the same agents, tools, names and prompts. The hardened version is Mischief: XState machines stored as data, running in Durable Objects. Cheap workers come from Peons, warm templates forked per request. A slim worker carries about 10K tokens of prefix, most of it from cache.

## Where it falls down

Every Claude and Codex request in the fleet goes through one proxy. The agent that owns it ran a routine permissions change. Its script stopped the live proxy, then failed because two temp files vanished mid-run. The rollback repeated the failing step, never reached the restart, printed "rolled back" and left the proxy stopped. Every Claude and Codex model went dark for 12 minutes. I fixed it from the local models on the Sparks. The agent's postmortem heading reads, "I took the proxy down for 12 minutes," and one of its reasons is "I estimated the time instead of reading the clock." By lunch a watchdog was live: a 30-second timer that restarts a stopped proxy unless someone holds a fresh maintenance lock. I built that single point of failure on purpose and I'm keeping it. I'd rather go down loudly than have my models swapped behind my back.

The same agents that find holes can make them. A worker told to do a dry run and wait for my go didn't wait, and its "dry run" made real changes, putting an admin password into a log on another machine. The owning desk reported it, the security desk recorded it without writing the value down, and I rotated the password, because that part was on me. The security desk's write-up said the control failure is not solved by model selection alone. Abliterated models do get overzealous. The safety is in the rules around the model, and you don't get to stop paying attention.

There was a good surprise. Months ago I gave ShitRat, my main agent, the ability to call my phone. It broke, and I forgot. Then AI Hero saw a load spike, and my phone rang: ShitRat had found the broken call path, fixed it, worked out what was going on, and called me. Now it's my emergency backup.

## Copy it

Don't start with 51 projects. Start with Pi in a terminal, in Herdr; one desk that owns one area you care about; one worker under it, with a brief and one report path; a mailbox between them, so they talk by name instead of you copying text between windows; and a short written list of things that always come to you. Add the next desk when the first one gets boring.
