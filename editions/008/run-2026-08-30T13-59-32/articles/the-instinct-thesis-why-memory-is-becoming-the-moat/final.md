---
source_ids:
- the-instinct-thesis-why-memory-is-becoming-the-m-14970672
content_mode: article
label: ARTICLE
---

Instinct feels magical, and I don't think the agentic loop is why. My hypothesis is memory: foundation models have commoditized, execution is going the same way, and what's scarce is a notebook that decides what's worth admitting, compiles it into beliefs and commitments, and knows when to stay quiet. Grain of salt upfront: Noah was my student at MIT, I have no inside knowledge of Instinct's internals, and I spend my days wrestling with agent memory for enterprises. If I'm right, Instinct should hold up as history grows, absorb reversals, and sometimes do nothing at all.

## The engine is commodity

Individually, nothing Instinct does is surprising next to hermes or openclaw. Any large model with a mildly competent tool-use harness can call APIs, follow instructions, and plan across steps. Permissions and reliability vary, but execution has become an engineering problem. The difference shows up only after you play with it a while: other agents seem to degrade, and this one seems to improve. That's the clue.

A transactional agent runs a few turns, fetches an answer, and terminates. A long-running one has to survive days of asynchronous friction. Take lowering a cable bill: call, hold, a vague retention offer, wait for a callback, check back, escalate. The hard part isn't the running. It's the waiting, holding state and staying oriented while nothing is happening.

## Memory is a compiler

People try to solve this by treating memory like a database: store every transcript and receipt, and hope some vector search or graph RAG fishes the right thing out later. Borges wrote the definitive story about it, "Funes the Memorious", the man who forgets nothing and, precisely because of it, can no longer think. Thinking is forgetting differences, generalizing, abstracting.

Memory makes no sense without a utility function, an active bet about what will be useful tomorrow. Richards and Frankland put it well (I'm paraphrasing): the point of memory is not to transmit the past with high fidelity, but to support intelligent decisions in the future. So there are two gates.

- Admission: does this observation carry enough expected value for future decisions to justify the cost of storing and indexing it?
- Action: does this state change justify acting? Not just convenience against annoyance, but risk, irreversibility, and authority. High-value, authorized, reversible, like a calendar hold: act silently. Consequential or irreversible, like an email or a payment: ask. Low expected value: silence.

## What I think the notebook holds

I could be very wrong here. I believe a continuous background loop digests the episodic stream and asks what changes our understanding of the user, what active task just moved, and what can be safely discarded, then compiles the answers into tiers: an ephemeral ingestion layer, held only long enough for semantic digestion; an append-only semantic ledger of admitted events with provenance ("retention offer promised within 48h"); a mutable, versioned belief and preference map ("user hates morning calls"); and a scratchpad of unresolved subgoals ("if silent by Thursday, escalate"). The agent then picks up from consolidated state instead of re-reading a giant corpus.

Provenance is what makes forgetting real. Delete a vector and its inferences persist in summaries and derived edges. An explicit provenance model with temporal checks can invalidate a whole dependency branch, retiring outdated facts cleanly. Generative Agents, MemGPT and Letta, Mem0 and A-MAC laid the groundwork, but the field spent years obsessing over retrieval; the frontier has moved earlier, to admission.

## Proactivity is a differential, not a timer

Almost every agent is reactive: poke it, it pokes back. The rest mimic proactivity with crude timers, and the more scheduled check-ins you bolt on, the less proactive the thing feels. Genuine proactivity needs the full stack: stateful memory, continuous event observation, explicit commitment tracking, and a risk-aware action policy. An email arrives while you're asleep, the background engine digests it and notices a delta. The scratchpad detects the change, the habit map judges whether it's worth waking you or is a note for the morning, and the ledger supplies the receipts when the agent explains itself. The deepest evidence of a working utility function isn't the well-timed ping, it's the silence: an agent that knows when not to reach out understands you better than one that always does.

## The testable part

If I'm right, three things should hold. Instinct should degrade gracefully as user history grows, because it acts from consolidated state rather than raw scrollback. It should handle "actually, I'm vegetarian now" without the old preference bleeding through, because provenance makes pruning real. And it should sometimes, deliberately, do nothing. If it's pinging like a needy app in month three, I'm wrong.

The privacy consequence follows from the same architecture. When you extract semantic state and discard the raw stream, durable facts become the asset and uncompressed exhaust becomes a liability. Aggressive compilation and selective retention can become the core trust story.

## The third wave

Three years ago Noah and I spent about three months on an embarrassingly simple idea: let an agent look back at its own mistakes and introspect. That became Reflexion, and it felt like a trick for one task at a time. What strikes me about Instinct, if my read is right, is the same intuition running continuously over a messy personal life instead of a single benchmark episode.

The first wave was capability, the second was execution, and the third is state: agents situated in the world long enough to know what has happened, what matters now, and what should happen next. Memory is a compiler, not a database, not a graph, not a filesystem. The enduring problem is no longer teaching machines how to think or how to act, but teaching them what the world currently is and what is worth remembering about it.

Note: I am CEO of Sentra, where we're building a shared memory layer meant to serve humans and agents across an org, and I deal with these issues.
