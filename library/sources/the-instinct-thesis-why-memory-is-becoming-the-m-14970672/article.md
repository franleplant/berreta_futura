# The Instinct Thesis: Why Memory Is Becoming the Moat

TL;DR: My hypothesis is that Instinct feels magical not because of an inimitable agentic engine, but because of its memory architecture. Just as ChatGPT marked the era of foundation models and Devin/Claude Code marked the era of autonomous execution, Instinct signals a third wave: foundation models have already commoditized, execution is rapidly going down the same path, and utility-driven memory is becoming the real wow-factor as well as the moat.

Back in 2023, Noah and I spent about 3 months playing with an embarrassingly simple idea: "what happens if you let an LLM Agent look back at its own mistakes and introspect?" That experiment became Reflexion, which eventually took a life of its own. But, in all honesty we didn't start intending to create a complex reasoning engine, it was an attempt at giving AI working memory for the sake of self-critique because we figured the critique could nudge the next attempt to be more right. Keep this in mind, we will come back to this idea later towards the end.

Before I go further, necessary grain of salt upfront: Instinct is an awesome product, Noah was a student of mine, I worked with him during my time at MIT and we have lightly kept in touch since then, but I have no inside knowledge of Instinct's internals. I also carry obvious biases for him being my student as well as someone who spends time wresting with agents and their memories, albiet for enterprises rather than personal ones. What follows is purely my attempt to make sense of a magical product from experiencing it.

Watching the multitude of tasks that people have been doing with instinct is truly fascinating and also a little odd since individually nothing it has done is particularly surprising compared to hermes or openclaw, but why then are people shouting "Look at this breakthrough agent". I believe on the surface it seems that way but one experiences the difference only when you play with the tool for a bit and as you play with it more unlike other agents that seem to degrade this one doesn't, it seems to somehow improve and lies the clue.

Personal memory architecture. A long-running agent does not need an attic full of raw history; it needs a selective working state. Ephemeral observations are admitted only when useful, compiled into durable beliefs and commitments, and retained with provenance so the agent can resume, revise, and explain itself.

## The Commoditization of the Engine

I have a different take, I don't think instinct's core agentic loop is likely to be particularly special. I say this because standard agentic execution has already commoditized. Also, any large foundation model paired with even a mildly competent tool-use harness can execute API calls, follow instructions, and generate multi-step plans. And, while the permissions, details of computer use, and execution reliability can vary, its execution has rapidly become an engineering problem while the memory is the scarce architectural asset.

My working hypothesis is that Instinct's real breakthrough is a notebook, or something like it, that its agent carries on its side: it's a principled memory architecture operating under the hood. It's the first time I have personally experienced an ordinary agent, outside of my own agents, sitting on top of a personal-memory architecture this good. And, if I'm right about how the notebook works, it explains the most uncanny thing about Instinct, not what it does when you ask, but what it does when you don't. To understand why the notebook is the load-bearing wall, look at the difference between a toy agent and a long-running one. A transactional agent runs for a few operational turns, fetches some answer, does some tool calls and then terminates. A long-running agent has to survive in the real world across days and weeks of asynchronous friction. Take the most mundane task imaginable: lowering a cable bill. One calls, sits on hold, listen to a vague retention offer, wait for a callback, check back a few days later, and then escalate. The hard part of an agent doing such a long-running task isn't the running; it's the waiting, it's holding state, staying oriented, and knowing what matters while nothing is happening.

## Memory Is a Compiler of Sorts, Not a Database or a Graph

People have tried to solve these issues by treating memory like a database: store every transcript and receipt, hoping some shitty vector search or graph RAG will fish out the needed information later, all the while forgetting that a tape recorder is not a memory. Borges wrote the definitive story about this, "Funes the Memorious", the man who forgets nothing and, precisely because of it, can no longer think. The act of thinking is to forget differences, to generalize, to abstract. If you record every photon hitting your eye and every sound wave entering your ear, you don't have understanding, or a brain, you just have whitewashed noise.

Memory makes no sense at all without a utility function, an active bet about what will be useful tomorrow. This isn't just a programmer's metaphor, it reflects a well accepted computational-neuroscience perspective championed by researchers like Richards and Frankland who argued this point succinctly when they said (I'm paraphrasing),"the point of memory is not to transmit the past with high fidelity, but to support intelligent decisions in the future". This is exactly why healthy brains work so hard at forgetting. When you or I go through about our lives, we discard almost all the noise, compress the remaining experiences into a few durable facts, and store those because we are constantly making a bet that they will matter. Real memory isn't brute-force retrieval, instead it's the active, disciplined choice of what to throw away via two distinct utility functions:

- Admission Utility: Evaluating whether a new observation holds enough expected value for future decisions to justify the maintenance cost of storing and indexing it.
- Action Utility (The Interruption Gate): Deciding whether an observed state change justifies action. This isn't just weighing convenience against annoyance, it must evaluate risk, irreversibility, and authority.

If an action is high-value, authorized, and reversible (e.g., updating a calendar hold), the agent acts silently. If it is consequential or irreversible (e.g., sending an email or initiating a payment), it asks. If the net expected value is low, the optimal mathematical action is silence

So what is Instinct actually doing?

Based on all that I can see in its behavior, I believe, and I could be very wrong here, the instinct agent has a continuous, utility-driven loop running quietly in the background. It enables the agent to avoid repeatedly compacting an ever-growing conversation at inference time, or treating retrieval (RAG or graph or whatever) over raw history as memory. Instead the agent is asking three questions as it digests the episodic stream of personal life, texts, tool calls, inbound receipts etc:

- What here changes our understanding of the user?
- What active task just moved forward?
- What can be safely discarded?

The answers get compiled into a multi-tiered state model:

- An Ephemeral Ingestion Layer: Raw transcripts and receipts held only long enough for semantic digestion, then discarded.
- A Selective Semantic Ledger: An append-only log of admitted events and state transitions ('Retention offer promised within 48h'), retaining provenance metadata without hoarding raw payload exhaust.
- An Evolving Belief & Preference Map: A mutable, versioned state of habits and constraints ('User hates morning calls').
- A Procedural Commitment Scratchpad: Dynamic tracking of unresolved subgoals and dependencies ('If silent by Thursday, escalate').

This approach would ensure that when the agent acts, it doesn't drown due to context rot or re-read a giant corpus, instead it picks up instantly from a clean, consolidated state. The memory system also, I bet, understands the mechanics of forgetting. The ledger itself most likely would be append-only, but every belief derived from it carries provenance, which conversation snippet, source and inference. When you update a preference or revoke a connected source, traditional RAG systems struggle, so even if you delete a vector its inferences persist across summaries and derived graph edges. An explicit provenance model paired with temporal check allows the system to invalidate an entire dependency branch cleanly, retiring outdated facts without leaving ghost hallucinations.

Proactivity as a state differential. Genuine proactivity is not a timer. New events are compared against persistent state; only meaningful changes pass through a utility and risk gate into action, escalation, deferral or deliberate silence.

Now, here is the most exciting consequence of such an architecture: a utility-driven compressed memory is the key to genuine agentic proactivity.

Almost every agent today is purely reactive, when you poke it, back it pokes. Most of the others mimic proactivity with crude timers and scheduled check-ins, producing a recognizable pattern. So, paradoxically the proactivity features one adds, the less proactive the thing feels. Natural proactivity is not a scheduled cron job you bolt onto an agent loop. Memory provides the necessary substrate, but genuine proactivity emerges from the full stack: stateful memory + continuous event observation + explicit commitment tracking + a risk-aware action policy. It requires a dynamic sense of state differentials. So, while you're asleep if an email arrives, the background engine digests it and notices a delta against the notepad leading to action or silence.

The three structures cooperate seamlessly: the scratchpad detects the delta, the habit map judges the interruption, i.e. is the state change worth waking you up, or is it a note for the morning? and lastly, the ledger supplies the receipts when the agent explains itself. Now, notice the corollary, because it's the part I find most elegant: the deepest evidence of a working utility function isn't the well-timed ping. It's the silence. An agent that knows when not to reach out understands you better than one that always does.

## Standing on the Shoulders of the Field

Now, here comes the even more interesting part and it's worth saying so. While prior systems laid essential groundwork, Generative Agents with importance reflection, MemGPT and Letta with tiered and sleep-time memory, and recent work like Mem0 and A-MAC formalizing memory admission, the industry has spent years obsessing over retrieval. The frontier is moving earlier in the pipeline: deciding what deserves admission, how it compiles into mutable state, and knowing when to stay quiet. The only other place I've seen similar behavior is in our own internal enterprise agents at Sentra (My startup). If I am right about Instinct, we arrived at simlar conclusions while trying to solve very different problems. To Noah's credit he pointed Instinct at personal agents, something we totally ignored as we obsessed with enterprise agents and issues around shared organizational memory.

That framing also makes everything I have written a testable prediction rather than a vibe. If I'm right, three things should hold:

- Instinct should degrade gracefully as the user history grows, because it acts from consolidated state rather than raw scrollback.
- It should handle reversals like "actually, I'm vegetarian now" without old preferences bleeding through, because provenance makes pruning real.
- It should sometimes, deliberately, do nothing. If it's pinging like a needy app in month three, I'm wrong.

A final note on the discourse surrounding data collection, screen capture, and training licenses. While terms of service across the industry evolve weekly in response to user pushback, the architectural point remains: a system built on utility-driven compilation is fundamentally aligned with data minimization. When you extract semantic state and discard the raw stream, durable facts become the asset, and uncompressed exhaust becomes an unnecessary liability. Aggressive compilation and selective retention can become the core trust story.

The better the notebook, the less of your life anyone needs to keep. The attic model doesn't just make worse agents, it makes worse privacy and depending on what kind of bullshit retrieval mechanism you choose it can be a tech debt. As this category matures and I hope it does for my own sake, aggressive forgetting becomes the primary trust story, not a limitation buried in the fine print.

## The Third Wave

Three years ago, when Noah and I were playing with Reflexion, it felt like a trick for one task at a time: fail, digest the failure into plain words, and try again. If my read is right, what is striking about Instinct is seeing a related intuition appear at an entirely different scale: reflection running continuously over a messy personal life instead of a single benchmark episode. It is genuinely wonderful to watch him chase personal memory this deeply, especially knowing where some of our earliest conversations started. If what I laid out above is indeed what he has built (and only time will tell), it would be a delightful coincidence that we both arrived at the exact same conclusion about memory while applying it to completely different worlds. I say this because we see the exact behavior every day in our internal agents at Sentra, where we have taken the approach described above but pointed it at the enterprise agents. But, that is a story for another day :-)

That points to a broader progression in the current AI cycle. The first wave was about capability: foundation models made machines unexpectedly competent at thinking in language. The second was about execution: systems such as Devin and Claude Code wrapped those models in loops that could plan, use tools, and finish work. The third is about state: agents that remain situated in the world long enough to know what has happened, what matters now, and what should happen next. And, the wave has just begun, people have been talking about it for the last year calling it loop engineering, graphs, context-graph and a whole lot of things that beats around the bush. The reality is that memory is a compiler, not a database, not a graph, not a filesystem either. And, I believe Instinct showed us exactly why this looks magical.

The enterprise version should go a step further, a personal agent needs persistent memory of only one person. An organization needs this across thousands of humans and agents maintaining personal and shared state built from communications, systems of record, documents and a whole lot more. It's a very similar architecture as above with many more bells and whistles combined on top. Field notes from building that for a 20,000-person company will come later, but that is a story for a different day :-) . The bigger picture is that the enduring problem is therefore no longer merely teaching machines how to think or how to act. It's teaching them what the world currently is and what is worth remembering about it.

---

Note: I am CEO of Sentra and deal with some of the issues that I wrote about here. At Sentra, where we are building a singular foundational layer that is a shared "memory" (as defined in the article) in service of enabling a company brain: a shared, living model of the entire org. It absorbs all data, structured and unstructured in an org and services humans and agents alike.
