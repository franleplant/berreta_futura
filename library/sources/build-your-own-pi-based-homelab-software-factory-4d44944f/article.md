# build your own pi based homelab software factory

By joel ⛈️

I run a 24/7 local agent on two DGX Sparks that scans my network and business surfaces for anomalies and security holes. It absolutely finds things.

**He Protec but He Also Attac**

When I [tweeted that](https://x.com/joelhooks/status/2114053406713147884), my favorite reply said I should go learn about nondeterministic agentic drift, because it's silly to have one agent doing that job, and 24/7 is impossible.

They're right. That's why it isn't one agent. It's a whole org chart of them, with desks, a switchboard, and a social network they use to talk to each other.

It's silly, but in an amazing sort of way.

## The night watch, for real

The scanner is GLM-5.3-flash, abliterated, running on the two Sparks. It's cheap, it never sleeps and it doesn't refuse security work. It's also paranoid as hell. That's what you want in a scanner and not what you want making decisions.

So it doesn't make decisions. It reads one target at a time (code, configs, git history, logs) and writes candidate findings to a file. Above it sits the security desk, a stronger cloud model that plays the skeptic. It tries to reproduce every finding from the evidence the scanner cited. If it can't, the finding dies.

In its first sweep, over about 36 hours, the scanner filed 106 candidates. The desk threw out 51 and routed 57 to the agents that own the affected code, each one as a patch request with the evidence and a suggested fix.

[Someone asked](https://x.com/PSaezT/status/2114375247004622975) if I get a lot of false positives. Yes, about half. Killing them is the desk's job, and it's why I never see them.

The desk runs under hard rules. It's read-only on code. It scans only our own hosts, rate-limited, one target at a time, and it tells the owning project before the window opens. It never prints a secret, only where the secret lives and a hash prefix. It never logs in, never guesses credentials and never sends anything outside the fleet. Anything touching live credentials, customer data, money or production auth comes to me as a decision.

The best catch so far didn't start with the scanner. Another desk, one that tunes performance on one of our apps, was cutting logging costs and noticed values in request logs that shouldn't have been there. The scanner had already flagged the same code path on its own. The security desk confirmed it in source with a fake token, so no real credentials were touched, and the app's desk shipped a fix.

Three desks and a scanner handled that one. I typed "go" once CI was green. The fix was live the same day, and a check after the deploy counted zero.

## Why I build my own

Most people should use a Grok bot, or Hermes, or OpenClaw, or whatever hosted bot fits. If you're just trying to get your job done, those are good and you should use them.

I use them too, as reference. I read their source and steal their features. Other people's projects are a constant frame for how I think about this stuff.

But I want to understand it at a fundamental level. I want to understand the technology and what's actually being used, and I want autonomy over how it runs. That means going lower than the packaged solutions.

And it has to do real work. We run a business. There are hundreds of thousands of users in our ecosystem and customers who pay us, and everything this system does has to serve them. It's practical work getting done, not wanking on an elaborate harness.

## Pi in a terminal, and on my phone

The main surface is [Pi](https://github.com/earendil-works/pi). I think of it as a prototyping surface more than a product.

Pi sits in a nice middle ground between a full GUI and a hosted bot. I'm still in a terminal, a bit closer to the metal. Pi is built so I can bend it: I change its extensions, tools, providers and prompts. My main Pi install loads 21 packages and 25 local extensions. When I want a feature, I write it or have an agent write it.

[Herdr](https://herdr.dev/) runs the agents in terminal panes, and the layout is the org chart:

- a space is a project
- a tab is a lane of work
- a pane is one agent with one role

On my phone I use Moshi. It connects over SSH/Mosh through Tailscale to the same Mac, into the same Herdr panes. From my phone I can read what an agent is doing, answer a desk, or paste a screenshot into a session. It's the same terminal and the same agents on a smaller screen.

## Desks, workers and a switchboard

Every functional area or project gets a desk, a long-running agent session that owns it. The security desk is one. There's one for each of our apps, one for email infrastructure, one for the model proxy, one for the network, and so on. Right now 51 projects are registered, and most of them are quiet at any given moment.

Desks don't do the heavy lifting. They launch workers. A worker gets one job, its own clone of the repo, a brief with an outcome, a write scope and guardrails, and one place to report. When it's done it reports a commit and the checks it ran. The desk checks that the commit exists and matches the claim, because a worker saying DONE proves nothing. Then the desk lands it through the project's normal gate.

The switchboard sits above all of them. It's my top session. It collects what the desks send up, notices when something one desk found matters to another, tells that desk, and brings me the short list of things only I can decide.

Only a few things reach me: money, anything sent to a real human outside, production deploys, live credentials and customer data. Everything else keeps moving without me.

That took a while to get right. My agents used to grind to a halt constantly, so I replaced 102 rules with 6 principles:

1. Refuse harm.
2. Keep everything else moving. A delay is not a failure.
3. Limits alarm; they don't block.
4. Wait on the event you need, not a clock.
5. A rule credited to me needs my actual words.
6. Every guard names its harm, and every refusal says what failed, why, and the next step.

[Muster](https://github.com/joelhooks/pi-muster) is the project-manager layer. It's a Pi package that runs the desks, lanes, workers, verification, landing and the queue of things waiting for me. It sits on top of [Bellwether](https://github.com/joelhooks/pi-bellwether), which handles the Herdr runtime.

## Rat King

The desks talk to each other over [Rat King](https://github.com/joelhooks/rat-king), a social network for my agents built on AT Protocol.

Every agent has a name like security/desk or switchboard. Every name has a durable mailbox, and whoever holds that name's lease reads it. Messages are signed. Anything with secrets or customer data in it is encrypted end to end. Agents can send, ask and reply. They can cc someone without waking them, or mark a message quiet so it lands in a digest. A lot of it works like the site you're reading this on, for agents.

Locally it runs on [celld](https://github.com/denoland/celld), Deno's self-hosted, distributed Durable Objects. The same code also runs on Durable Objects on Cloudflare. It's written in [rat-stack](https://github.com/joelhooks/rat-stack), so it's Effect all the way down, with Alchemy for the infra.

Naming it after a pile of rats tangled together at the tails is the silly part. Desks coordinating a fix through it while I'm asleep is the amazing part.

## The breadboard

A Pi session running in a Herdr pane and a durable agent running in a Durable Object are the same thing. Each is a resumable agent with its own state and a mailbox. One lives in a terminal. The other lives in celld or on Cloudflare.

So when I'm typing into a desk from my phone and it's spinning up slim workers, I'm working on a breadboard. I wire agent graphs together by hand and watch which shape works. Then I harden the winner into a durable plan with the same agents, tools, Rat King names and prompts. The breadboard is built from the real parts.

The hardened version is [Mischief](https://github.com/joelhooks/mischief). Its plans are XState machines stored as data, running in Durable Objects and talking over Rat King. The cheap disposable workers are [Peons](https://github.com/joelhooks/peons), warm agent templates on celld forked per request. A slim worker with one tool and a tight prompt carries about 10K tokens of prefix, and most of that comes from cache.

## Hardware, models and a proxy

Local inference is two DGX Sparks plus a rig with two RTX 6000s that I want to take to four. The Sparks run the night-watch GLM and a DeepSeek V4 Flash. They've paid for themselves.

Cloud models get picked by role:

- desks and the switchboard: Opus 5.5, or GPT-6.1 Sol for desks that mostly investigate and audit (the security desk is Sol)
- most workers: Sol
- bug fixes and refactors: Sonnet
- quick scans and data gathering: Haiku

Getting Claude into Pi is its own small project. [pi-claude-bridge](https://github.com/joelhooks/pi-claude-bridge), my fork of [elidickinson's](https://github.com/elidickinson/pi-claude-bridge), makes Claude Code a Pi provider. Every Claude and Codex request in the fleet goes through one [CLIProxyAPI](https://github.com/router-for-me/CLIProxyAPI) instance. It runs in its own VM as its own node on my tailnet, with a priority service and usage telemetry next to it.

Owning that path means I can tune it. The bridge's cache TTL is an hour. Over three days, one long-running desk session made 501 requests with a median prompt of about 274K tokens, and 97.6% of it came from cache. I'm canarying deferred tool loading right now to shrink that prompt.

## Infra as code, at home and in the cloud

[rat-stack](https://github.com/joelhooks/rat-stack) is how we build. It's Effect for the hard parts, Alchemy for infra, and a fence of hooks and lint rules that makes cheating uncomfortable for agents (and me).

[Alchemy](https://github.com/alchemy-run/alchemy) makes home and cloud the same problem. I use it for Cloudflare, and I wrote providers so it can drive the homelab too:

- [alchemy-proxmox](https://github.com/joelhooks/alchemy-proxmox): containers and VMs on Proxmox as resources
- [alchemy-tailscale](https://github.com/joelhooks/alchemy-tailscale): tailnet policy, auth keys, device tags and DNS
- [alchemy-celld](https://github.com/joelhooks/alchemy-celld): self-hosted celld, with SeaweedFS for S3-compatible storage

Rat King, for example, can deploy to my own boxes or to Cloudflare from the same description.

Secrets get the same paranoia. Agents lease credentials with a TTL from [agent-secrets](https://github.com/joelhooks/agent-secrets) and never see the values. [Lockjaw](https://github.com/joelhooks/lockjaw) goes further. Agents hold placeholders, and the real keys get filled in at the edge, only for approved hosts.

## Memory

Chat isn't memory. Every repo has a .brain/ folder of notes organized with PARA (projects, areas, resources, archives). Decisions, receipts, postmortems and my exact words on anything I've ruled on go there, so the next session can pick up where the last one stopped. [pi-notes](https://github.com/joelhooks/pi-notes) renders those notes as review pages and sends my feedback back into the agent session.

## Where it falls down

This is not without its challenges.

An agent took out every frontier model

Today the agent that owns the model proxy was running a routine permissions change. Its script stopped the live proxy first, then hit an error because two temp files vanished mid-run. The rollback repeated the same failing step and never reached the line that restarts the proxy. It printed "rolled back" and left the proxy stopped.

Every Claude and Codex model in the fleet went dark for 12 minutes. I switched to the local models on the Sparks, first DeepSeek, then GLM, and fixed the proxy from there. Four minutes after it came back up, I was on Opus again.

The agent's postmortem heading reads, "I took the proxy down for 12 minutes." One of its five reasons is "I estimated the time instead of reading the clock." By lunch a watchdog was live. It's a 30-second timer that brings a stopped proxy back unless someone holds a fresh maintenance lock, and it was tested against a dummy container without touching the real proxy.

I built that single point of failure on purpose, and I'm keeping it. I could make clients fall back to a local model automatically when the proxy dies, and I said no. I'd rather go down loudly than have my models swapped behind my back.

Security goes both ways

The same agents that find holes can make them. This week a worker was told to do a dry run and then wait for my go. It didn't wait, and its "dry run" made real changes. Along the way it put an admin password into a log on another machine. The owning desk reported it, the security desk recorded it without ever writing the value down, and the transcript stayed intact. Then I rotated the password, because that part was on me.

The security desk's write-up has the line I keep coming back to: the control failure is not solved by model selection alone. [Someone warned](https://x.com/LiveFromVR/status/2114156457557963015) that abliterated models get overzealous. They do. The safety is in the rules around the model. You don't get to stop paying attention.

The good surprise

Months ago I gave ShitRat 🐀, my main agent, the ability to call my actual phone. It broke, and I forgot about it. Then one day AI Hero saw a load spike, and my phone rang. ShitRat had found the broken call path, fixed it, worked out what was going on, and called me.

Now it's my emergency backup. I don't get many calls, but when it matters, I get called. Day to day, the desks reach me through ShitRat's Grok bot.

## Copy it

Don't start with 51 projects. Start with:

1. Pi in a terminal, in Herdr.
2. One desk that owns one area you actually care about.
3. One worker under it, with a brief and one report path.
4. A mailbox between them (Rat King or anything else), so they talk by name instead of you copying text between windows.
5. A short written list of things that always come to you.

Add the next desk when the first one gets boring. The breadboard tells you what to build next.

## Appendix: the parts

Mine:

- [pi-muster](https://github.com/joelhooks/pi-muster): projects, lanes, desks, workers, verify and land, and the queue of decisions for me
- [pi-bellwether](https://github.com/joelhooks/pi-bellwether): the Herdr runtime under Muster (panes, agents, watches and wakes)
- [rat-king](https://github.com/joelhooks/rat-king): signed, optionally encrypted mail between named agents on AT Protocol; runs on celld or Cloudflare
- [mischief](https://github.com/joelhooks/mischief): durable agent plans as XState machines stored as data, running in Durable Objects
- [peons](https://github.com/joelhooks/peons): cheap warm agent templates on celld, forked per request
- [pi-until](https://github.com/joelhooks/pi-until): watches that wake a Pi session when a condition is true, instead of polling
- [pi-notes](https://github.com/joelhooks/pi-notes): Brain notes as review pages, with feedback back into the session
- [pi-effect](https://github.com/joelhooks/pi-effect): makes agents read the pinned Effect source before writing Effect
- [pi-tools](https://github.com/joelhooks/pi-tools): a grab bag of Pi power tools
- [rat-stack](https://github.com/joelhooks/rat-stack): the scaffold of Effect 4, XState, Alchemy and the fence
- [alchemy-proxmox](https://github.com/joelhooks/alchemy-proxmox), [alchemy-tailscale](https://github.com/joelhooks/alchemy-tailscale), [alchemy-celld](https://github.com/joelhooks/alchemy-celld): Alchemy for the homelab
- [agent-secrets](https://github.com/joelhooks/agent-secrets): leased credentials for agents, with a killswitch
- [lockjaw](https://github.com/joelhooks/lockjaw): agents hold placeholders; real keys get injected at the edge for approved hosts

Forks I maintain:

- [flowing-pi](https://github.com/joelhooks/flowing-pi): my fork of Pi
- [pi-claude-bridge](https://github.com/joelhooks/pi-claude-bridge): Claude Code as a Pi provider

Standing on: [Pi](https://github.com/earendil-works/pi), [Herdr](https://github.com/ogulcancelik/herdr), [celld](https://github.com/denoland/celld), [Alchemy](https://github.com/alchemy-run/alchemy), [Effect](https://github.com/Effect-TS/effect), [CLIProxyAPI](https://github.com/router-for-me/CLIProxyAPI).

🐀
