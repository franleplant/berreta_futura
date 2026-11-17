---
source_ids:
- choosing-quepaxa-an-unusual-consensus-algorithm-e4c8a7e8
content_mode: article
label: ARTICLE
---

Meerkat, our experimental consensus service for Cloudflare's internal global control plane, runs on QuePaxa, an algorithm published in 2023 by Tennage & Băsescu et al. Most consensus systems use Raft, Multi-Paxos or Viewstamped Replication, which are well understood and usually work well. But they rely on a leader that is available and has predictable latency, and over the Internet, where Meerkat runs, a slow or disconnected leader stalls the system until it's replaced. QuePaxa makes the leader optional, needs no fault detection, and has proposers cooperate instead of compete. In our evaluations, with servers on nearly all continents, Meerkat kept processing requests when the leader crashed, disconnected, or slowed. We have never seen it completely stall.

## Why leaders fail at global scale

Meerkat replicas agree on an ordered log of events, each decided by consensus, and build the same key-value state from it, much like Consul, etcd or ZooKeeper. Unlike them, a Meerkat cluster may span continents, over links with high and variable latency.

Many consensus algorithms become disproportionately slow or unavailable when the network degrades even though no machine crashes. In 2020, the partial failure of a core Cloudflare switch made a consensus-powered system degrade and the dashboard run 80x slower than usual for six hours. The system lost no data, but it was unavailable for writes until the issue was resolved, which is unacceptable.

Two traits cause this.

**Destructive interference.** In Paxos, any proposer can send a ballot number to a majority of acceptors, who then accept only that ballot or higher. A second proposer can slip a higher ballot between the first one's two phases and block it; the first replies in kind, and the two can block each other forever. Paxos doesn't guarantee liveness without assuming partial synchrony. Raft, Multi-Paxos and Viewstamped Replication avoid this with a single leader, which is fast, deciding in one round trip, while the leader is healthy and the network behaves. When the leader fails, replicas must elect a new one by majority vote, and several candidates can split the vote and keep calling elections. The interference returns. Elections can go on after the original fault is gone: a two-second outage can trigger a much longer metastable failure.

**Fault detection.** A process can't observe that a remote process has failed, only that an expected message hasn't arrived. In asynchronous networks, where most messages arrive on time but bursts of latency and lost connections come without warning, a dead server and a slow network are indistinguishable. Every detector guesses, and a wrong guess starts an election that stops the system. A right guess is still slow: the timeout can't be below network latency, so Raft is commonly run with an election timeout of five to ten round trips. Across the world, a round trip takes hundreds of milliseconds, so detecting a failed coordinator can take around a second, and until then the system is down.

## How QuePaxa works

QuePaxa has proposers and recorders. Each proposal gets a random priority; the optional leader gets an exclusive maximum. Recorders pass along what they see, and a proposer that receives a higher-priority proposal adopts it. Proposers work together toward the highest priority they collectively know, so they can't lock each other out indefinitely.

Each round has four phases. In each, proposers broadcast their adopted proposal and advance once a majority of recorders replies.

- **Phase 0 (Propose and Adopt):** proposers pick random priorities, send their proposals, and adopt the highest one in the majority that replies. In the first round, if the leader's proposal reached a majority first, the leader decides at once. This is safe because any two majorities share a recorder, so every other proposer will meet the leader's proposal and adopt it.
- **Phase 1 (Spread):** proposers spread what they adopted; recorders keep the highest priority they see, which prevents a later decision on a lower one.
- **Phase 2 (Check and Decide):** proposers ask a majority for the highest proposal seen in Phase 1. If it's their own, they decide.
- **Phase 3 (Carry Forward):** proposers that didn't decide adopt the best proposal a majority holds. If anyone decided, they're guaranteed to adopt that decision.

After the first round there is no fast path, and the only way to decide is to converge. Adoption makes deciding exponentially easier as rounds go on. The paper predicts a 50% chance of deciding per round; in practice it is much higher. A failed round doesn't throw away the work already done.

The leader is the only proposer that can decide in one round trip, so we want to use it, without making it a single point of failure. Clients send requests to every replica, and non-leaders wait a short hedge timeout to let the leader decide alone. In our implementation, unlike the paper, clients wait the timeout instead of replicas, to send fewer messages; the result is the same. This timeout isn't fault detection and isn't bound by network latency. In Raft, a five-millisecond timeout on a 100-millisecond network would freeze the system; in QuePaxa, it only adds active proposers. That costs bandwidth and may slow decisions, a tradeoff we're more than willing to make.

## What we've seen

More than 95% of decisions are made by the leader in Phase 0, which keeps throughput fairly stable. When a decision needs three phases, throughput drops momentarily to at most a third of the usual rate. In one leader failure, the decision rate fell to about 65% and decisions moved entirely to Phase 2; it returned to 100% when the leader was replaced a minute later. The system never halted. We can also switch the leader while the cluster runs without worrying much about stability.

## What comes next

QuePaxa hasn't been battle-tested as extensively as Raft or Paxos, and we're extending its crash-stop design to support crash recovery. That demands stronger evidence of correctness than usual, so we are formally verifying our QuePaxa implementation and Meerkat as a whole, alongside extensive simulation and fault-injection testing. Future posts will cover that verification, failure testing, benchmarks, and what we've learned turning an academic protocol into a production system.
