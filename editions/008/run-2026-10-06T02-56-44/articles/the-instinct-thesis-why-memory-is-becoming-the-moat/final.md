---
source_ids:
- the-instinct-thesis-why-memory-is-becoming-the-m-14970672
content_mode: article
label: ARTICLE
---

My hypothesis is that Instinct feels magical not because of an inimitable agentic engine but because of its memory architecture. Foundation models have already commoditized, execution is going down the same path, and utility-driven memory is becoming the wow-factor and the moat. A grain of salt: Noah, who built it, was my student at MIT, I'm CEO of Sentra, where we build memory for enterprise agents, and I have no inside knowledge of Instinct's internals. This is my attempt to make sense of a product from using it.

## The engine isn't the secret

Individually, nothing Instinct does is surprising next to Hermes or OpenClaw. The difference shows only with use: other agents seem to degrade, and this one seems to improve. Any large model with a mildly competent tool harness can call APIs, follow instructions, and plan in several steps. Execution has become an engineering problem; memory is the scarce asset.

A transactional agent runs a few turns and stops. A long-running one has to survive days and weeks of friction. Lowering a cable bill means calling, holding, hearing a vague retention offer, waiting for a callback, checking back, and escalating. The hard part isn't the running; it's the waiting: holding state and knowing what matters while nothing is happening.

## Memory is a compiler

Treating memory as a database means storing every transcript and receipt and hoping vector search or graph RAG will fish out the right piece later. "Funes the Memorious" is the story of a man who forgets nothing and therefore can no longer think. To think is to forget differences and abstract.

Richards and Frankland argued, in my paraphrase, that the point of memory is not to transmit the past with high fidelity but to support intelligent decisions in the future. Memory needs two utility functions:

- **Admission utility:** does a new observation hold enough future value to justify storing and indexing it?
- **Action utility:** does a state change justify acting, weighed for risk, irreversibility, and authority? High-value, authorized, and reversible (a calendar hold): act silently. Consequential or irreversible (an email, a payment): ask. Low net value: stay silent.

## What I think Instinct does

From its behavior I believe, and I could be very wrong here, that a utility-driven loop runs quietly in the background, instead of compacting an ever-growing conversation or retrieving over raw history. As texts, tool calls, and receipts arrive, it asks what changes our understanding of the user, what task just moved forward, and what can be discarded. The answers compile into tiers:

- **Ephemeral ingestion:** raw transcripts and receipts, held until digested, then discarded.
- **Semantic ledger:** an append-only log of admitted events ("Retention offer promised within 48h"), with provenance but without the raw payload.
- **Belief and preference map:** mutable and versioned ("User hates morning calls").
- **Commitment scratchpad:** unresolved subgoals ("If silent by Thursday, escalate").

The agent then acts from clean, consolidated state rather than drowning in context rot. I bet it also understands forgetting. In traditional RAG, deleting a vector leaves its inferences alive in summaries and graph edges. If every belief carries provenance, a revoked source or updated preference can retire a whole dependency branch, without ghost hallucinations.

## Proactivity as a state differential

Most agents are reactive; the rest mimic proactivity with timers and check-ins, and the more such features one adds, the less proactive the thing feels. Memory is the substrate, but genuine proactivity needs the full stack: stateful memory, continuous observation, commitment tracking, and a risk-aware action policy. An email arrives while you sleep; the scratchpad detects the delta, the habit map judges whether it's worth waking you, and the ledger supplies the receipts when the agent explains itself. An agent that knows when not to reach out understands you better than one that always does.

## The field, and how I'd be proven wrong

Generative Agents, MemGPT and Letta, Mem0 and A-MAC laid the groundwork, but the industry has spent years on retrieval. The frontier is moving earlier: what deserves admission, how it compiles into mutable state, and when to stay quiet. The only similar behavior I've seen is in our own internal agents at Sentra. If I'm right:

- Instinct should degrade gracefully as user history grows.
- It should handle "actually, I'm vegetarian now" without old preferences bleeding through.
- It should sometimes, deliberately, do nothing. If it's pinging like a needy app in month three, I'm wrong.

Whatever the terms of service say, a system that extracts semantic state and discards the raw stream is aligned with data minimization. Durable facts are the asset; uncompressed exhaust is a liability. Aggressive forgetting can become the primary trust story, not a limitation buried in the fine print.

## The third wave

In 2023, Reflexion felt like a trick for one task at a time: fail, digest the failure into plain words, try again. If my read is right, Instinct runs a related intuition continuously over a messy personal life. The first wave was capability: foundation models. The second was execution: Devin and Claude Code. The third is state: agents that stay situated long enough to know what has happened, what matters now, and what should happen next. Memory is a compiler, not a database, a graph, or a filesystem.

An organization needs the same across thousands of humans and agents. Field notes from building that for a 20,000-person company will come later.
