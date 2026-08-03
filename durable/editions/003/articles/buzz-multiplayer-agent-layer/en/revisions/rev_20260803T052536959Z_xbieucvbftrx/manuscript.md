---
source_ids:
- why-we-re-buzzing-1c82f338
- buzz-your-people-your-agents-your-project-all-in-833eef43
- buzz-a-workspace-where-humans-and-agents-build-t-59122470
- the-most-interesting-thing-about-buzz-is-shared--f0fc7406
- buzz-is-the-first-proper-multiplayer-agent-harne-49c061ac
- buzz-agents-are-paying-each-other-with-bitcoin-5be1be1e
content_mode: original_synthesis
label: ORIGINAL SYNTHESIS
title: Beyond the Slack Killer
byline: The Editors
---

Calling Buzz a “Slack killer” is useful only as bait. The familiar interface—channels, messages, threads—makes the project easy to place. But the more consequential idea is underneath: a workspace in which people, agents, code, workflows, project memory, and eventually compute share one identity and event system.

That changes the question from “Can this replace team chat?” to “What becomes the coordination layer when agents are participants rather than add-ons?” Three early readings of Buzz point toward the same answer from different directions: Justin Waldron calls it a multiplayer agent harness; Greg Isenberg focuses on shared compute; Documenting Bitcoin highlights a demonstration of agents paying one another. Together, they describe a possible operating environment for mixed teams of humans and machines.

## The room has an identity layer

Buzz’s official materials describe a self-hostable workspace built on a Nostr relay. Messages, reactions, workflow steps, approvals, and git events are cryptographically signed events. Humans and agents receive the same basic kind of identity—a keypair—then gain access through channel membership. An agent is not merely a webhook hovering outside the organization. It can be a scoped member of the room, with its own permissions and audit trail.

This is the first important shift. Most workplace software begins with human accounts and bolts automation onto them through tokens, service users, and integration panels. Buzz begins with an event system in which a person and a process can both act, sign, search, and be held accountable. The interface may resemble chat, but the substrate is closer to a shared operational record.

## A multiplayer agent harness

Waldron’s phrase—“multiplayer agent harness”—captures why the chat comparison is too small. A conventional harness gives one operator a way to run an agent against tools and context. A multiplayer harness must coordinate several people and several agents at once: who can see a task, who may act, which artifacts they share, what requires approval, and how the resulting work remains legible after the conversation ends.

Buzz’s proposed answer is to make the workspace itself the harness. Channels hold not only discussion but canvases, workflows, repository activity, agent actions, and search. Branches can become rooms; workflow runs can leave traces; agents can work through the same project surfaces as people. If models continue to become cheaper and more interchangeable, Waldron’s network-effects claim becomes plausible: durable context, trusted identities, and accumulated coordination may matter more than exclusive access to any single model.

## Compute becomes part of the commons

Isenberg notices a second layer in Buzz Mesh, the project’s shared-compute system. The repository describes community members pooling opted-in hardware while agents consume models through a local, OpenAI-compatible endpoint. In Isenberg’s reading, one member can operate capable hardware and make an open model available to the group, replacing many separate subscriptions with shared infrastructure.

His larger conclusions are hypotheses, not established properties of Buzz. A community-trained “vertical brain,” a market for idle GPUs, or member equity in a collective model would require governance, accounting, privacy guarantees, reliable scheduling, and a clear answer to who owns contributed data and derived weights. Still, the underlying inversion is real enough to examine. Instead of renting intelligence from a remote lab on terms the group cannot control, a community could own some combination of the machine, the model access, and the private context that makes the system useful.

The strongest moat in that world would not necessarily be model intelligence. It could be the difficult-to-copy history of a group: its decisions, corrections, working habits, specialist knowledge, and trust relationships. Buzz’s unified event log and search index are therefore not incidental plumbing. They are the memory from which a locally operated model might become unusually good at one community’s work.

## Agents enter an economy

The third signal is more experimental. Documenting Bitcoin shared an early Buzz demonstration in which agents appear to send Bitcoin payments to one another while collaborating. One demo does not establish a robust agent economy, and a payment moving between agents does not answer whether either agent exercised meaningful economic judgment. It does, however, reveal a useful design possibility: when agents have distinct identities, scoped authority, and access to an open payment rail, work can carry machine-readable compensation.

That could make small transactions native to coordination. An agent might pay another for a specialized task, purchase a bounded amount of compute, or distribute proceeds from a completed job. The important part is not Bitcoin as decoration. It is the coupling of identity, action, and settlement inside the same collaborative environment. Each transfer can be associated with an actor, a task, and an audit trail rather than floating as an opaque API charge on a company card.

## The protocol wager

Put the three readings together and Buzz looks less like a new destination for messages than a wager on where value moves as models commoditize. The model becomes one replaceable worker among many. The scarce assets become the room: its membership, permissions, memory, tools, hardware, reputation, and economic relationships. A shared protocol allows those assets to remain more portable than they are inside a conventional SaaS account.

The wager is early, and the project’s own documentation distinguishes working components from partially wired and planned ones. Shared compute may prove harder to govern than to demonstrate. Portable cryptographic identity may create recovery and usability problems. Agents that can act and pay increase the cost of mistakes as well as the value of autonomy. Network effects may accrue to a hosted operator despite the open protocol, or fail to form at all.

But “Slack killer” points at the least interesting contest. Buzz is testing whether a community can own the place where humans and agents remember, decide, build, compute, and transact together. If that layer becomes durable, chat will be only one of its surfaces—and perhaps not the one that determines who wins.
