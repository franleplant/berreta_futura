---
source_ids:
- mega-megadevhq-on-x-b8963c9d
content_mode: article
label: ARTICLE
---

Models got smarter, but they still lack our context. Our job is to shape an environment where agents reach that context on their own, run in the cloud, start work from events and schedules, and stay within real limits. I rebuilt a four-year-old project this way in five days: the app, the website, and the API. It required an insane amount of work and expertise. Product development isn't fully autonomous yet, but we're clearly moving in that direction.

## Context, not intelligence

Language models are highly capable, but their knowledge is limited, and that affects their judgment. It's not just the knowledge cutoff. It's our personal and project context.

Agents should have easy access to:

- the app, so they can interact with it and take screenshots
- product docs, plus docs and SDKs for what we integrate with
- development and production logs
- development databases and controlled, indirect access to production data
- past agent sessions and past decisions
- issue trackers, team channels, and support tickets

They shouldn't have direct access to the production database or root permissions on a server.

## Work that doesn't wait for us

Agents can coordinate one another, and recent models do it significantly better. Much of the work we assign them could be triggered automatically by bug reports, support tickets, code-review requests, scheduled quality checks, alerts, incidents, and log errors. So agents can do most of the work without waiting for us, while maintaining quality. Some changes may not even require human supervision, depending on the project and our policies.

For that, agents have to move from our Macs and PCs to the cloud, stay available at all times, and have their own email and messaging accounts. Currently, Grok Bot, Pi, and Herdr are among the best tools for coordinating them.

## Letting go of control

With dozens of agents working in the cloud on external triggers, it's extremely hard to understand what's going on. Every time we look at the codebase, it feels as if we've just joined a new team. Using AI to understand the logic faster may work, but only to some extent, since our cognitive capabilities, energy, and time are limited.

Instead, we can let go of control. Models still make mistakes, but in many cases those mistakes have limited consequences, and AI is, in many ways, more knowledgeable and skilled than most of us. Some situations still require human judgment or context the model lacks; many routine tasks don't. So:

- A spec can be drafted from the project vision, its change history, and a long audio recording of us describing the feature.
- Implementation can run in "waves" managed by a coordinator agent, which another agent can manage in turn.
- After implementation, agents can interact with the app and validate its behavior and appearance against defined checks.

The most important part is keeping tasks narrowly scoped and threads as short as possible. Even models like GPT-6 generally handle smaller tasks more easily, and since other agents manage the threads, splitting the work is easy.

## Discipline at scale

Docs and specs fall out of sync, and agents keep forgetting to update specifications. That upkeep can be automated too.

Specs should sit in folders that show the feature, its stage, and when work took place; follow flexible templates; and reference commits rather than include code. Docs should be built with Astro, Next.js, or similar so agents can manage them, and optimized for agents, who are increasingly their primary readers. We just need to set up agents to maintain them on a schedule.

## I nuked a four-year-old project and rebuilt it in five days

A month after ChatGPT launched, I started a chat UI that helped personalize interactions with AI. It helped us generate around $750k through various campaigns. Its core architecture dated from text-davinci-003. I decided to scrap everything and rethink its core assumptions, architecture, and UI. Even with today's models, rebuilding at this scale felt almost impossible, because people rely on this tool in their daily work.

The foundation:

- a unified logging system for the API, Rust, and Svelte
- a testing environment connected to the app's webview, so agents can interact, take screenshots, and collect measurements
- a design system, which Fable 5.1 and Astra built for me in Ultracode mode
- a few primitives (Integrations, Secrets, Events, Values, Capability) that let agents generate and manage components I used to maintain myself
- an Astro site whose docs use design-system components instead of screenshots

That wasn't enough on its own. The agents also needed a way to manage specifications:

- **Global Context:** vision.md and the styleguide, which I defined and continue to oversee
- **Board:** current and planned tasks
- **Specifications:** features, issues, and fixes, with the reasoning behind decisions and lessons learned

Grok Bot is my entry point to a VPS, reached through Tailscale, that hosts the project with Herdr and Pi. My custom Pi extension injects the style guide and vision and sends steering messages to Coordinators, Workers, Reviewers, and Researchers.

For a feature, I send Grok Bot an audio recording, sometimes a long one. It checks the board and either spawns a Coordinator or passes the task to an existing one. The Coordinator spawns Researchers, drafts the specs, and reports back so we can discuss the direction. Then it manages Workers, and I can talk to any of them and steer it directly.

I don't read code anymore, but I still care about its quality, so dedicated Coordinators work in the background, often at night, on schedules set by Grok Bot. In five days, I delivered the app, the entire website, and the API.

## Takeaway

This approach works for both me and my friends. Product development isn't fully autonomous yet, but we're clearly moving in that direction. The app's development was nearly autonomous, yet it required an insane amount of work and expertise, though from just one person.

To start, install Grok Bot, ask it to set up a VPS with Herdr and either Pi or omp, create vision.md and a styleguide, keep the scope relatively small, and stay up to date with what's happening in your product.
