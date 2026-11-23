---
source_ids:
- verifying-formal-models-of-raft-implementations-69abfaca
content_mode: article
label: ARTICLE
---

At Antithesis, we used AI, TLA+, and Antithesis to formally model two production Raft libraries, etcd-raft and HashiCorp Raft. Once we applied the fixes and workarounds they needed, we proved that their specific designs, scoped to the features we modeled, offer the same core safety guarantees as the Raft paper. The proofs cover models of the code, not the code itself. Trace validation under Antithesis testing is what ties the two together. Each library cost less than $1,200 in Claude Fable tokens and about 2000 Antithesis compute-hours. This is an early research project.

### Isn't Raft already verified?

The Raft protocol has been studied, specified, and proven correct under a set of assumptions. Yet we keep finding bugs in every major Raft implementation we test. Many implementations subtly deviate from those assumptions, redesign the algorithm for performance, or add unverified extensions.

AI has since made theorem proving and verification of complex systems much more scalable. So we set out to verify the specific designs in production libraries: their data structures, concurrency, pre-votes, leadership transfers, and snapshots. For etcd-raft we also covered read indexes, async storage writes, and membership changes.

### Modeling, and checking the model against the software

Claude Fable 5.2 inferred TLA+ models from each library's code. We reviewed the safety properties, chose which features to model, specified scenarios, and made one refinement to the generated properties. AI is generally bad at inferring properties, so we told the agent to express the core ones from the Raft paper:

- **Election Safety**: at most one leader per term.
- **Log Matching**: logs sharing an entry's index and term agree up to it.
- **Leader Completeness**: a leader holds every entry committed in earlier terms.
- **State Machine Safety**: no two nodes apply different entries at the same index.

To show the model matches the software, the Antithesis plugin set up a test cluster, a workload covering the modeled features, and assertions mirroring the model's properties. It then ran the software under fault injection. A trace validation kit made the code emit log events matching TLA+ state transitions, and any trace that fit no path in the model was flagged. A flag could mean bad instrumentation, a modeling error, or a real bug. The agent diagnosed which, and iterated until traces and model converged.

### Bounded checking, then proof

TLC checked the invariants on small instances: usually three nodes, one client value, a couple of terms, short logs, and few messages in flight. These bounds were enough for competing elections, deposed leaders still replicating, overwritten entries, and crashes mid-operation. Some instances reach over 1.6 million states, explored exhaustively. If the software couldn't exhibit a violation the model produced, the model was tightened.

We found bugs in both libraries. Some were known (hashicorp/raft#695, etcd-io/raft#551) and some were new (hashicorp/raft#746, etcd-io/raft#558). We applied 7 patches across the two. A few crash bugs turned up as well, but they don't violate safety.

Bounded checking only shows the absence of bugs in a small state space. Unbounded assurance needs proof. We translated the TLA+ into Veil, a Lean library, and had Claude Fable 5.2 build the proofs. We chose Lean for its interactive tactics, predictable performance, and persistent kernel-checked proof terms, which suited an iterative loop.

Proof also caught a bug. A model of etcd-raft's membership change could not be proven, which revealed a complex bug beyond the bounded state space. When Claude hypothesized intermediate invariants, it used Antithesis to check them quickly and discarded those that failed. Once the spec was frozen, agents proved the same invariants directly in TLAPS. That step wasn't strictly necessary, but it removed any doubt about the Lean proofs and the TLA+ spec.

### What isn't proven

The proofs verify models, not code. Confidence in the models' fidelity comes from trace validation under extensive testing, including network partitions and node crashes. Mutation testing of the spec, the stored logs, and the software adds to it.

The models assume storage never tears or corrupts a single write, which BoltDB guarantees. A crash can still fall between two writes.

Several features are left unmodeled:

- Lease-based reads in etcd-raft, which depend on wall-clock timing.
- Async heartbeats in hashicorp-raft, known to be very buggy.
- Membership changes in hashicorp-raft, because we were exhausted from patching the simpler core.

Only safety is verified, not liveness.

### Trace validation in brief

Suppose a spec says each loop iteration increments either `passed` or `failed`, so `passed + failed == i` always holds. Code that logs "loop passed loop failed" maps to a valid sequence of states. Add a `continue` on a network timeout and the logs can read "loop loop", a behavior the spec forbids. The code has diverged from the design.

Here, the mapping was easy because code and spec sat at roughly the same level of abstraction, with Go and TLA+ closely matched line for line. Most real-world specs sit two levels above their code, which makes trace validation harder.

### Looking ahead

We see ourselves less as a fuzzing company than as a correctness company. Formal specification proves the design correct but doesn't guarantee the code matches it. Trace validation uses tests to cover that weakness, and it works best when tests reach wildly unusual states. Think of this as us demonstrating a medicine works on mice, but we haven't yet done a human trial.
