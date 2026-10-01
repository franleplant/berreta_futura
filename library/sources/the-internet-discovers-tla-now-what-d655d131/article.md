# The internet discovers TLA+. Now what?

By Anna Mészáros, Szilvia Ujváry, Kseniia Strelbytska, Balázs Szilágyi, and Ferenc Huszár · Reasonable · September 25, 2026

Boris Cherny’s viral TLA+ tweet showed how useful formal models can be in agentic coding. This post gives a practical introduction to what TLA+ is.

But TLA+ is only the starting point. We also look at how temporal specifications, modern proof systems and AI agents can fit together, from modeling system behaviour to generating machine-checked proofs, and ultimately toward software that is specified, implemented and verified in one loop. We also give a sneak peek into some of our work at Reasonable on making this possible.

## Boris tweeteth, the internet copy-pasteth

This week Boris Cherny [graced TLA+](https://x.com/bcherny/status/2102543349102338309), a formal modeling toolkit that is over 30 years old, with a tweet. He used Opus 5.5 to model parts of the Claude Agent SDK in TLA+ and Lean, and the internet did what it does: ~1M views, thousands of bookmarks, and people are asking what TLA+ actually is. Boris's post is a great showcase, and it adds to early examples showing that TLA+ is well worth the effort in agentic coding: see Datadog's post on [harness-first agents](https://www.datadoghq.com/blog/ai/harness-first-agents/).

If you are one of the people now wondering what TLA+ is and what it is for, you are in the right place. TLA+ happens to be one of the formal techniques our team has dived deep into.

But there is also a larger reason we care about it. TLA+ gives us a compact language for saying what a system is allowed to do and what must always or eventually be true of it. That is a useful starting point for verification, but it is not the end of the story.

Here is the short version:

- **TLA+ describes possible system behaviours** and the properties those behaviours should satisfy.
- **TLA+ itself does not fully verify an implementation.** It checks a model of the software, not the software itself, and its main model checker only explores finite instances.
- **Modern proof systems can take us further.** In Verus, specification, proof and Rust implementation can live in the same language.
- **AI can already automate part of this process.** We built an agentic pipeline that turned 16,000+ TLA+ specification/property pairs into 3,000+ machine-checked Verus proofs.

### The interesting question, then, is not only whether an agent can write TLA+. It is what becomes possible once agents can move between specifications, proofs and real programs.

Part of our work at Reasonable is training models to enable agents to do this, consistently, reliably, quickly.

## What TLA+ is

Our running example is the one in the interactive playground below, where three computers, a, b and c, have to agree on which of them is the leader. Databases rely on leader election being correct. We require that no two leaders exist at the same time. You can click through the playground to learn the basics of TLA+ through the five levels of the game.

[Open the playground](https://reasonable.io/figures/tla-playground)

TLA+ (Temporal Logic of Actions) is a language for writing down two kinds of objects:

- **A transition system: what the system can do.** There are *states*, which are snapshots of the system (who is a candidate, who has voted for whom, who is leader) and *actions*, single steps that change a state ("a starts an election", "b votes for a"). In the interactive playground, you take these steps by hand, exploring one possible run the way a tester would.
- **Temporal properties** are statements about how a run plays out over time. For example, "There are never two leaders." "A leader is eventually elected."

A TLA+ model declares legal system states and allowed transitions between these states. For example, in the election, any of a, b or c may start an election from the initial state, voting for itself as it does so, and b may vote for a or for c.

It imposes no order on transitions and does not attempt to model the probability distribution of different events happening, which is the right abstraction for distributed systems, where messages, timeouts and user actions can happen in many different orders.

The underlying mathematics is simple, it uses sets, true/false statements and relations. Temporal properties are then built from operators over executions:

- **□ P** (*always P* ): P holds in every state visited.
- **◇ P** (*eventually P* ): P holds in some future state.
- **P ⇝ Q** (*P leads to Q*): whenever P holds, Q eventually holds afterwards.

Two kinds of property matter particularly often.

**Safety: nothing bad ever happens.** For our election: □ (there are never two leaders). In the playground, the model checker explores every possible state: all 38 states for three computers, and confirms the property. Level 2 changes one rule so that a computer can vote twice. The checker then returns a six-step execution ending with two leaders. That execution is a *counterexample*: a concrete way the model can violate the property.

**Liveness: something good eventually happens.** Safety alone is not enough. A system that does nothing forever is perfectly safe. So we might also require: ◇ (someone is leader). Level 3 shows why this matters: a typo stops anything from happening, and the safety check still passes. Liveness requires *fairness* assumptions, which rule out executions where an action remains possible forever but is simply never taken. Weak fairness WF(A) says that an action that stays enabled must eventually happen; strong fairness SF(A) covers actions that become enabled infinitely often.

The mental model is simple: a TLA+ model describes the possible execution traces of a system, and a property describes which traces are acceptable. Verification asks whether every possible trace is acceptable.

TLC, the standard TLA+ model checker, answers this by enumerating reachable states for a finite instance. A proof makes the stronger statement that the property holds in general.

For more, [Jack Vanlightly](https://jack-vanlightly.com/) has been teaching TLA+ on his blog long before agents made it fashionable

## What TLA+ is not

TLA+ is increasingly widely deployed because this way of reasoning about systems can be practically useful; you'll see it in use at AWS, MongoDB, and Datadog, in Kafka, and many other places. But there are three important caveats, where TLA+ alone stops short of full software verification.

**Model checking only goes so far.** In practice, people most often use TLA+ with TLC. TLC explores every possible run, but only for a finite model. In our example, the state space grows from 38 states with three computers to more than a million with nine. To establish a property for arbitrary system sizes, you need a proof. TLA+'s own prover, TLAPS, can do this in some cases, but its automation is limited, particularly for liveness arguments.

**The model is not the implementation.** A TLA+ specification is usually a separate model of the software. Nothing automatically guarantees that the implementation behaves exactly like the model, and the two can drift apart as the code changes. This is one element of the classic spec-to-implementation gap.

**TLA+ cannot express every property we may want.** TLA+ is based on linear temporal logic, which makes statements about individual executions: "In every run, a leader is eventually elected." But some interesting properties concern alternative futures or strategies.

- **CTL**, a branching-time logic, can express statements such as: "from any state, a new election can still be started."
- **ATL** can express strategic statements such as: "this computer has a strategy to become a leader whatever the others do."

These richer properties become relevant once we start thinking about systems containing multiple competing or collaborating agents.

So TLA+ gives us an unusually useful language for describing temporal behaviour, but a complete verification stack needs more: stronger proof machinery, a connection to real code, and eventually richer logics.

## From TLA+ to proofs

One route is to take the model into a modern proof system. There are several options, examples include:

- **Lean** is interactive: you (or an AI) write the proof step by step. It is very general, widely used in mathematics, and was the prover used in Boris's post.
- **[Verus](https://github.com/verus-lang/verus)** is auto-active and designed around Rust. You provide specifications and the important proof structure, while an automated solver handles much of the lower-level reasoning.
- **[Veil](https://veil.dev/)** is a Lean-based tool built specifically for state-machine models. Leo de Moura has recommended it, and it was recently used to verify a sync engine, fixing 17 bugs in the process. Liveness remains future work, however, and the verified model is still separate from the implementation.

**Why use Verus?** Because specifications and proofs can live alongside the real Rust implementation. That matters because it gives us a route towards closing the spec-to-implementation gap: instead of proving properties only about a separate abstract model, we can ultimately prove that the implementation *refines* that model. Systems such as [Anvil](https://github.com/anvil-verifier/anvil) have already demonstrated this style of verification; our work at Reasonable builds particularly closely on Anvil.

**Why automate formal verification?** The proofs involved are often less exotic than the phrase *formal verification* suggests.

- **Safety proofs are usually inductive.** Show that the property holds initially, then show that every possible action preserves it. Much of the work consists of splitting over the different actions and tracking the relevant invariants.
- **Liveness proofs establish progress.** Typically, some quantity decreases as the system progresses, together with fairness assumptions ruling out executions in which an enabled action is postponed forever. Rules such as WF1, WF2, SF1 and SF2 ([Lamport, 1993](https://lamport.azurewebsites.net/pubs/lamport-actions.pdf)) package these arguments; our temporal library implements a subset of these as proven Verus lemmas.

A large fraction of this work is repetitive: tracking invariants, splitting over actions, supplying intermediate lemmas and filling in solver-visible details. That makes it a natural target for proof-generating agents.

## From proofs to machine-checked software

Automated theorem proving has recently made rapid progress in mathematics. Software verification poses a somewhat different problem: before proving anything, we need a useful description of what the software is supposed to do.

TLA+ is attractive here because temporal specifications are relatively compact and readable, and because many real systems already have TLA+ models. If we can connect those models to modern proof systems and to implementations, several directions become possible.

- **Refinement proofs.** Prove that the Rust implementation follows the TLA+ model. Anvil demonstrated this manually. Automating more of that process would reduce the gap between verifying a model and verifying the software that implements it.
- **Program synthesis.** Start from the model and generate an implementation together with a proof that the implementation refines it. In this setting, the formal specification constrains both code generation and verification.
- **Protocol search.** Once checking a candidate protocol is cheap enough, the verifier can become an objective function: generate variants of a protocol, verify them, and retain those satisfying the desired properties. This starts to look similar to systems such as AlphaEvolve, except that correctness is checked formally rather than estimated by tests.
- **Beyond linear time.** Some properties of multi-agent systems concern alternative futures or strategies rather than individual execution traces. Expressing those requires logics beyond LTL. [Benjamin Brast-McKie](https://benbrastmckie.com)'s work explores this side of the problem, while our current work focuses on proving temporal properties and connecting them to programs.

## A sneak peek at our progress

We have been working on a pipeline for translating TLA+ specifications into machine-checked Verus proofs. Our next blog posts will describe the individual pieces in more detail. For now, the main results are:

- **A TLA+ to Verus transpiler.** We built an algorithmic transpiler and compared it with an agentic alternative in which an LLM produces the translation and a second LLM reviews it.
- **A prover–reviewer loop with anti-cheat checks.** One agent writes a proof and another reviews it. A separate gatekeeper checks that the agents have not modified the specification or introduced shortcuts such as assume(false).
- **A dataset of temporal proofs in Verus.** Starting from 16,459 real-world TLA+ specification/property pairs, the pipeline produced more than 3,000 machine-checked safety and liveness proofs. We also constructed a 40-task evaluation set.
- **An evaluation of current models.** We tested both closed and open-weight frontier models on the evaluation set, looking at which temporal proofs they can complete and where the remaining failure modes are.

We'll cover those results in the follow-up posts.

## Work with us

We're hiring people excited to push the boundaries of formal verification and AI agents. If you want to help build systems where correctness can be machine-checked, we'd love to hear from you: [Careers](https://apply.workable.com/reasonable).

We're also eager to hear from teams building systems where correctness really matters. We're exploring what machine-checked proofs can unlock for real-world applications and we'd love to talk: [Contact](https://www.linkedin.com/company/reasonableai/).

### How to cite this post

```
@misc{meszaros2026tlaplus,
  author       = {M{\'e}sz{\'a}ros, Anna and Ujv{\'a}ry, Szilvia and Strelbytska, Kseniia and Szil{\'a}gyi, Bal{\'a}zs and Husz{\'a}r, Ferenc},
  title        = {The internet discovers TLA+. Now what?},
  howpublished = {\url{https://reasonable.io/blog/tla-tutorial/}},
  year         = {2026},
  month        = sept,
  organization = {Reasonable},
  note         = {Reasonable blog post, accessed \today},
}
```
