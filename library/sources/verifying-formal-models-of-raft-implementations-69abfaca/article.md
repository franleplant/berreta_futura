# Verifying formal models of Raft implementations
By Rohan Padhye, Hillel Wayne · Antithesis · November 19, 2026

At Antithesis, we love finding bugs in distributed systems. But Antithesis can also help *eliminate* certain classes of bugs by using a combination of AI and formal methods to *prove* the correctness of complex design choices.

In this post, we demonstrate the paradigm on two [Raft](https://raft.github.io/) implementations, production libraries from [etcd](https://github.com/etcd-io/raft/) and [HashiCorp](https://github.com/hashicorp/raft). Although they’re implementing the same protocol, there are significant differences in the approaches the two use. We used AI, TLA+, and Antithesis to formally model the two libraries with trace validation. We iterated between model checking, Antithesis testing, and proof attempts, each of which exposed bugs in the code or gaps in the model. We patched bugs and refined the model until it was provable, *and* until every test run was conformant.

Our model handles several extensions to the core Raft algorithm including pre-votes, snapshots, leadership transfers, and, for etcd-raft only: read indexes for linearizability, async storage writes, and membership changes (where etcd’s implementation [intentionally deviates](https://github.com/etcd-io/raft/blob/v3.7.0/doc.go#L262-L270) from the Raft paper).

**The final proofs establish core Raft safety properties such as Election Safety, Leader Completeness, and State-Machine Safety**. In other words, our process established that once we applied the workarounds and fixes needed, **the specific designs** (scoped to the features we modeled) embodied in HashiCorp Raft and etcd-raft actually offer the same guarantees that the Raft paper does. We make the artifacts available for open review:

- [HashiCorp Raft formalized](https://github.com/antithesishq/hashicorp-raft-formalized)
- [etcd-raft formalized](https://github.com/antithesishq/etcd-raft-formalized)

### Isn’t Raft already verified?

Earlier this year, we wrote about how [we keep finding bugs in every major Raft implementation we test](https://antithesis.com/blog/2026/finding-bugs-in-raft-implementations/) with Antithesis. This was surprising, because the underlying Raft protocol has been extensively studied, formally specified, and rigorously proven correct (under a set of assumptions). In that post, we pointed out that many implementations subtly deviate from those assumptions, re-design the algorithm for performance, and/or extend the core Raft protocol with unverified extensions – thereby introducing bugs.

Since then, advances in AI have made [automated theorem proving](https://openai.com/index/navier-stokes-solution/) and [formal verification of complex systems](https://www.anthropic.com/research/formal-verification) much more scalable, making it feasible to connect a specification to its implementation. So we set out to formally verify not just the core Raft protocol, but the specific designs implemented by production Raft libraries, incorporating custom data structures, different modes of concurrency, and various extensions such as pre-votes, leadership transfers, snapshots, and (in the case of etcd-raft) membership changes.

### Formally modeling Raft implementations

A key challenge in applying formal methods is to identify a level of abstraction that both allows us to reason mathematically about desired properties, *and* bridges the gap between specification and implementation. We are not yet at the point of reasoning directly at the level of assembly instructions or even programming language semantics in order to verify distributed safety properties in production systems.

Both [Anthropic/Theorem’s OSS-Verify](https://theorem.dev/oss-verify/) and [Google DeepMind’s AlphaProof Code](https://deepmind.google/blog/introducing-alphaproof-code/) only model **single-threaded** assembly code; whereas distributed systems are concurrent.

The most widely used approach models the software as a state-transition system in a specification language such as [TLA+](https://lamport.azurewebsites.net/tla/tla.html), and checks invariants over these transitions for finite state spaces. TLA+ models can either be hand-written by experts, or these days, inferred directly from the code using AI. This approach has its [own limitations](https://buttondown.com/hillelwayne/archive/llms-are-bad-at-vibing-specifications/), but is increasingly [popular](https://zfhuang99.github.io/github%20copilot/formal%20verification/tla+/2025/05/24/ai-revolution-in-distributed-systems.html). The next challenge, then, is showing that the [TLA+ model corresponds](https://www.mongodb.com/company/blog/engineering/conformance-checking-at-mongodb-testing-our-code-matches-our-tla-specs) to the actual software [that will run in production](https://www.datadoghq.com/blog/engineering/continuous-formal-spec-validation/).

For our demonstration, we used Claude Fable 5.2 to automatically infer TLA+ models from the implementations of HashiCorp Raft and etcd-raft and then manually reviewed the safety properties declared in the specifications.

The etcd-raft repository has a [TLA+ model](https://github.com/etcd-io/raft/tree/v3.7.0/tla) crafted for trace validation that is now out of date, and is not designed for ease of proof. The [Specular project](https://github.com/specular-org) [produced models of etcd-raft and hashicorp-raft](https://github.com/specular-org/specula-case-studies), but those models are designed for trace validation, not ease of proof, and the [TLAPS leaderboard](https://specular-org.github.io/tlaps-bench-website/) indicates that they remain unsolved as of 20 Nov 2026.

We had to manually provide guidance on which features to model or leave out, what scenarios to specify for model checking, and make one refinement to the auto-generated safety properties. While [AI is generally bad at inferring properties](https://newsletter.pragmaticengineer.com/p/formal-methods-with-hillel-wayne), in this case we simply instructed the agent to express the core safety properties defined in the [Raft paper](https://raft.github.io/raft.pdf).

### But how do we know the model corresponds to the software?

That’s where Antithesis helps.

We used the recently launched [Antithesis plugin](https://github.com/antithesishq/antithesis-plugin) to automatically set up a test cluster, an input-generating workload designed to handle all the features captured in the model, and assertions that correspond to the model’s safety properties. The software was then tested under fault injection while being fed random inputs, exercising various code paths and thread / message interleavings.

For this demonstration, we developed a lightweight [trace validation](https://arxiv.org/abs/2404.16075) kit that allowed the software running in Antithesis to emit structured log events that correspond to state transitions in the TLA+ specification. Any test execution that produced a trace that did not conform to some path in the model got flagged. A non-conformant trace could indicate incorrect instrumentation of the trace logging itself, or more seriously, a modeling error or a real bug in the system. We instructed our AI agent to diagnose which one of these it might be, [using Antithesis as necessary](https://antithesis.com/blog/2026/time-traveling-agents/), and continue iterating until the traces and the inferred model converged.

### Invariants, model checking, and bug fixes

For both Raft models, the specification expresses the following safety properties, taken directly from the [Raft paper](https://raft.github.io/raft.pdf):

- **Election Safety**: at most one leader can be elected in a given term.
- **Log Matching**: if two logs have an entry with the same index and term, they agree on every entry up to that index.
- **Leader Completeness**: a leader’s log contains every entry committed in earlier terms.
- **State Machine Safety**: no two nodes apply different entries at the same index to their state machine (the state machine itself is not modeled).

Before trying to prove anything, we verified that these invariants hold on bounded instances using TLC, the standard TLA+ model checker. These instances, also synthesized by our AI agent, specify various bounds: clusters are usually three nodes, a single client value, at most a couple of terms of leader election, logs that are limited to a few entries, with only a handful of network messages in flight. These bounds sound tiny, but they’re sufficient to create several interesting cases: competing elections, a deposed leader still replicating, log entries overwritten and re-replicated, crashes in the middle of an operation, etc. We also model checked various configurations of the Raft libraries, e.g. with pre-vote or snapshotting features enabled and disabled. These “small” instances can reach a state space of over 1.6 million states, which TLC explores exhaustively. We also included some larger problems which were only checked via random simulation. If model checking triggered a safety violation, we attempted to reproduce it as an assertion failure locally or in Antithesis; if the software couldn’t exhibit the behavior, the model had to be tightened.

Overall, our process was an iterative loop consisting of model checking (flagging invariant violations), trace validation (flagging deviations), model refinement (to fix design flaws or conformance), and software patching (to fix bugs).

In some ways, this approach is similar to and inspired by [Specular](https://arxiv.org/abs/2607.25333). However, given their goal of finding bugs, Specular’s approach involved using AI to identify buggy scenarios before writing models, which meant that [static analysis was doing a lot of the heavy lifting](https://github.com/specular-org/Specular/issues/176). In contrast, our models are intended to be more general and prove safety of the full design.

Along the way, we encountered bugs in both systems, including previously known open issues such as [hashicorp/raft#695](https://github.com/hashicorp/raft/issues/695) and [etcd-io/raft#551](https://github.com/etcd-io/raft/issues/551), as well as new ones such as [hashicorp/raft#746](https://github.com/hashicorp/raft/issues/746) and [etcd-io/raft#558](https://github.com/etcd-io/raft/issues/558). In our internal repository, we applied a total of 7 patches across the two implementations. In each case, our goal was to make the system and model pass both verification and validation.

We also encountered a few additional crash bugs, but those don’t violate safety.

But bounded model checking only shows the absence of bugs in a small state space. The only way to get assurance for unbounded input sizes is via rigorous mathematical proof.

### Proofs, assurances, and limitations

There are two good techniques for proving invariants correct for the whole specification: using a theorem prover integrated into TLA+ called [TLAPS](https://proofs.tlapl.us/doc/web/content/Home.html), or by translating the model into [Veil](https://veil.dev/), a library for the [Lean](https://lean-lang.org/) proof assistant for modeling state-transition systems. We used both, delegating the task of proof construction to Claude Fable 5.2.

We used Veil’s official tla-to-veil LLM skill for the model translation, and the recommended approach of validating this via bounded equivalence checking, using TLC and Veil’s own model checker, on our previously stored instances.

Ideally, a TLAPS proof provides the best assurance, since it can attest to safety properties defined on the TLA+ model itself. However, we decided to translate TLA+ to Veil and attempt proofs in Lean. Why? As described in the previous section, our process was extremely iterative, involving several steps of model refinement. We wanted to use the proof engine as additional feedback in that process, feeding it any candidate specifications on which bounded model checking and trace validation both succeeded. We found Lean’s interactive tactic paradigm, predictable performance, and persistent kernel-checked proof terms to be key benefits in this iterative process.

On one occasion, a model of etcd-raft’s membership change as implemented could not be proven correct, [revealing a complex bug](https://github.com/etcd-io/raft/issues/558) whose trigger was beyond the state space that bounded model checking explores. In such situations, we could use the Antithesis plugin to attempt to synthesize a workload to reproduce the counter-example.

Antithesis also helped in the proof construction process. When working on challenging parts of the proof, Claude hypothesized several intermediate invariants which if true would lead to a straightforward proof strategy. The agent then used Antithesis to [quickly check](https://antithesis.com/blog/2026/streaming-results/) if those invariants held true in test runs, and discarded them if run-time assertions failed. Antithesis thus made the proof construction phase more efficient.

Once we converged on a state where the safety properties were fully provable in Lean and the model was passing trace validation with Antithesis, we froze the specification and asked agents to prove the same invariants on the TLA+ spec directly with TLAPS. This last step wasn’t strictly necessary, but eliminated any shadow of doubt concerning the Lean proofs and the TLA+ spec.

End-to-end, the work on each library cost less than $1,200 in Claude Fable tokens and approximately 2000 Antithesis compute-hours.

Less, we should note, than the prepaid allowance in a single month of [Antithesis Teams](https://antithesis.com/pricing/).

Note that our final proofs verify formal models of the implementation, not the code itself. However, we can gain confidence about the model’s fidelity based on the trace validation performed with the extensive test coverage that Antithesis provides, including fault injection such as network partitions and node crashes. To strengthen assurance even further, our iterative process involved several steps of [*mutation testing*](https://antithesis.com/blog/2026/mutation-testing/), including: mutating the specification to check that the proofs fall through, mutating stored test logs to ensure that trace validation fails, and mutating the software itself to ensure that everything breaks.

The models still make several assumptions about the environment, which limits the reach of verification. For example, both Raft libraries provide pluggable interfaces for local persistent storage. In our test workloads, we use [BoltDB](https://github.com/boltdb/bolt) for storage and the models assume that no single write (e.g., a log entry or tuple of raft state) is ever torn or corrupted, which BoltDB guarantees. A crash can still fall between two writes.

Our work also leaves out several library features which we have not modeled, such as lease-based reads for etcd-raft (because it depends on wall-clock timing), async heartbeats for hashicorp-raft (because it is known to be [very](https://github.com/hashicorp/raft/issues/666) [very](https://github.com/hashicorp/raft/issues/695) [buggy](https://github.com/hashicorp/raft/issues/742); [really](https://github.com/hashicorp/raft/issues/717)), and membership changes for hashicorp-raft (because we were exhausted from patching bugs in the simpler core). Finally, we only verify safety properties and ignore liveness in this prototype. A comprehensive list of assumptions and limitations is provided in the associated artifact’s README.

### Looking ahead

Given our reputation as “a fuzzing company”, formal methods might seem like an odd direction for us to explore. But we see ourselves less as “a fuzzing company” and more as a **correctness company**. We need a wide range of different approaches if we want to build truly robust systems. Each technique compensates for the weaknesses of the others. Moreover, they amplify each other’s strengths. The first property-based testing framework, [QuickCheck](https://dl.acm.org/doi/pdf/10.1145/351240.351266), derived test inputs from a function’s static type. Many of our customers use both testing and formal methods, so we want to make the two techniques work better together.

The biggest weakness of formal specification is that it proves the *design* correct, but doesn’t guarantee that the code we implemented actually matches the design. Trace validation uses the strengths of tests to compensate for the core weakness of formal specification. Validation works best if our tests can reach wildly unusual system states, which aligns well with our core technology.

How formal specification can help testing is relatively less explored, but there are some opportunities here too. We often find that newcomers to property-based testing struggle to describe the properties for their system. But they can describe a high-level outline of what the system essentially does. With trace validation, we can potentially turn that outline *into* a property to test!

All that said, **this is an early research project.** We could easily map trace logs to spec behaviors because the code and spec were at roughly the same level of abstraction, with a close correlation between lines of Go and lines of TLA+. Most real-world specs, though, are two levels of abstraction above the code they model. This is because 1) TLA+ can do things impossible in a real system, like make truly arbitrary nondeterministic choices, and 2) the spec can simplify implementation details that don’t affect the essential design. These features make specification more powerful, but also make trace validation harder.

Think of this as us demonstrating a medicine works on mice, but we haven’t yet done a human trial. More work is needed, work which we’re now doing at Antithesis. Stay tuned to see where it ends up.

### Appendix: A brief intro to trace validation

In formal specification (like with TLA+), we write highly abstract blueprints, or specifications, of systems and find bugs in those blueprints directly. Once we’ve found and fixed all the bugs, we can be confident our real system isn’t going to have certain design issues.

But how do we know that the code we write actually corresponds to the design we verified? This is one of the big unsolved problems of formal specification, and the solution we used here **trace validation** (also called “trace checking”). This was first publicly described in the MongoDB paper [*eXtreme Modeling in Practice*](https://arxiv.org/pdf/2006.00915). The authors took logged events in the production system, converted them into a sequence of states, and checked if that sequence was possible in the blueprint. If not possible, then the implementation must be doing something forbidden by the blueprint, so there is a divergence between the implementation and spec.

It’s easier to see this with a concrete example. Say we have this pseudocode as our specification:

```plaintext
i := 0;
passed := 0;
failed := 0;

while (i < $some_arbitrary_number) {
  i := i + 1;
  either {passed := passed + 1}
  or     {failed := failed + 1}
}
```

By `either-or`, I mean that exactly one of the two will happen each iteration, but the decision logic is an implementation detail I don’t care about. This spec also has the property that, after every loop iteration, `passed + failed == i`.

Now here’s one conforming implementation:

```python
for sensor in get_sensors():
    reading = sensor.get_data()
    if convoluted_analysis_passes(reading):
        add_reading_to_dataset(reading)
    else:
        sensor.mark_broken()
        alert_someone_sensor_is_broken(sensor)
```

While the practical way this works is very different than just arbitrary incrementing variables, it’s still the same thing in essence, and we should expect that every sensor either gets added to the set or marked as broken. To do trace validation, we first add some logs to the code:

```diff
for sensor in get_sensors():
   print("loop")
    reading = sensor.get_data()
    if convoluted_analysis_passes(reading):
       print("passed")
        add_reading_to_dataset(reading)
    else:
       print("failed")
        sensor.mark_broken()
        alert_someone_sensor_is_broken(sensor)
```

We run this program and it prints “loop passed loop failed”. We can convert that to a behavior of the spec. If we denote a state as `(i, passed, failed)`, the corresponding sequence of states would be `[(0, 0, 0), (1, 0, 0), (1, 1, 0), (2, 1, 0), (2, 1, 1)]`. That is valid under the behavior, so this trace conforms to the spec.

Now if we make a diverging change like this:

```diff
for sensor in get_sensors():
    print("loop")
   try:
        reading = sensor.get_data()
   except NetworkTimeoutError:
       continue
    reading = sensor.get_data()
    # ...
```

It’s now possible to run this and see the logs “loop loop”. The corresponding behavior, `[(0, 0, 0), (1, 0, 0), (2, 0, 0)]` is impossible in the spec, so this would fail trace checking and reveal a divergence between the code and spec.

That’s how it all works in principle, anyway. There’s a lot of technical challenges with getting this working practically. For example, how are we supposed to know that a network timeout may give us an invalid trace, and how are we actually supposed to trigger it? And the answer to that is a combination of the techniques that we use in Antithesis: **deterministic simulation testing** and **fuzzing**. But those are things that we talk about in detail in other articles.
