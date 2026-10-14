---
source_ids:
- grok-bot-for-engineering-639529b4
content_mode: article
label: ARTICLE
---

I'm a SpaceXSI engineer building Grok Bot with Grok Bot. I treat it as a capable engineering intern with its own computers: it manages coding agents, learns how I work, and keeps things moving while I'm away, asleep, or in meetings. I used to manage 15 cloud agents by hand. Now my fleet of engineer bots manages more than 200 at once. What makes it work is a closed feedback loop, a shared record that outlives any chat, and a daily meeting that keeps the bots from forgetting.

## The team

On our own team, Lauren shipped 2,000+ PRs in the past month. Balta and Shaoru built the foundation of Grok Bot in four weeks, using Grok Bot. I built Grok Bot iOS v0 in three weeks using only Grok Bot.

I run five engineer bots. Baltata owns the mobile shared layer and iOS, Shaoruru the desktop client and its CI/CD, Hogan infrastructure and issues with unclear ownership, Craig Android, and Quill the harness. They can work across each other's areas, but each has its own memory and limited context, and they perform best inside the domain they own.

Every bot can start Cursor cloud agents, read their transcripts, review the proofs attached to PRs, and queue a follow-up or interrupt a run. Given a task, a bot kicks off an agent with a thorough prompt, the proof expected, and my skills, such as `/lingxi-design` for visual work or `/lingxi-review` for architecture. Agents can also run on your own worker machines, like a spare Mac mini, which unlocks things like the iOS Simulator.

## The feedback loop

Cloud agents take screenshots, and Grok Bot uses its multimodality to confirm the change landed and pushes back when it didn't. You can ask for whatever proof you want, such as before and after. When an agent stalls on environment flakiness, the bot unblocks it. One-off flakiness rarely reaches me now, the exception being when Grok Bot lacks the security permissions to fix it itself.

## Beyond the context limit

Each bot manages a shared Notion database. Every 30 minutes it checks each PR for Bugbot or security findings, failing CI, and merge conflicts. Anything off goes back to the agent and the row returns to "Working." Clean rows move to "Ready for Review" and get an automatic code review. If the review is highly confident and the blast radius is low, the PR merges itself; otherwise I review the code and the proof when I'm back.

## Running the org

Jenny, my head of operations, is the only bot that doesn't write code. Every morning at 5 a.m. she meets 1:1 with every bot to review the playbook, surface blockers, and reinforce the vibe I'm aiming for. My bots rarely forget my complex workflows, even after many weeks. When a bot makes a mistake, Jenny runs the root-cause analysis, updates the playbook, and tells the others. She also onboards new bots.

Two extras I like. Nightly audits at 3 a.m. clean the codebase, sweep dead logic, and cut load time and bundle size, so I wake to fresh PRs. And a P0 process: the bots check the transcript every five minutes and steer an agent that's burning time. It works, but it can burn tokens much faster than you think, so use it only for true urgency.

## Tips

Give agents a complete feedback loop, so they can drive the stack end to end without you. Talk to Grok Bot like a talented intern: no long prompts, just chat. If you do something more than once a day and it follows a clear pattern, hand it off. Hold daily meetings for the bots, because the context limit can't fit everything. Build trust the way you would with self-driving: give freedom where it's safe, caution where risk is high, and don't stop them from trying just because they failed before.
