---
source_ids:
- redesigning-source-control-at-anthropic-56ee56e4
content_mode: article
label: ARTICLE
---

In May 2026, Anthropic merged around 2,500 code changes a day; as of September, over 30,000. Coding is no longer our bottleneck. The bottleneck is the developer infrastructure built for human scale: source control, builds, and CI. So we built Scion, an in-house version control system, and fully migrated our monorepo from git in five months. Scion assumes clients are always online: the server does the work, and clients fetch only what they need. Our infrastructure footprint is now 200x smaller than our old git mirroring, and checkouts take seconds rather than minutes. Claude's ability to write code was both what put us in this situation and how we built our way out of it. Scion is no replacement for git for general use, but we anticipate this class of problems becoming more common over the next six to 12 months.

## Why git stopped fitting

Git is decentralized: every clone is a complete repository that works offline. For most repositories, that's the right design. Ours increasingly doesn't fit it. The history of main alone is almost 100 GB, and a compressed working copy is over 25 GB. We perform on the order of 25 million checkouts a day for CI, before counting developer environments, agent sandboxes, and research jobs. Fetched naively, that would be over 600 PB of git traffic per day.

We used every standard workaround: shallow clones, sparse checkouts, promisor remotes, mirrors, and snapshots in blob storage. At our peak, we ran several hundred internal git mirrors. This bought us time, but it grew harder to operate as our merge rate rose.

Like most companies, we were using git as a centralized system with one authoritative copy, yet nearly all of our clients were agents and jobs, online by definition. The properties that make git excellent for offline work were undermining our ability to scale. So we asked what source control would look like if it were designed for clients that are always online.

## The principles

We built Scion with the lessons of Google's Piper and Meta's Sapling in mind.

**Clients are always online.** They fetch data when they need it.

**The server does the work.** It answers history and blame queries, creates commits, and performs merges and rebases. The client keeps a bounded local cache, lays out files, and watches for changes. It can compute very little, but needs much less data.

**Everything is an API.** The queries the client uses are exposed to any job, so many jobs need no local repository at all. Our automated bisect and revert pipelines wouldn't be practical at scale without this.

**Commits are cheap, incremental, and lock-free.** Their cost scales with the size of the change, not of the repo. We discourage refs except main and release branches, because global state every server must agree on is a looming scaling problem.

**The working copy is optional and sparse.** Many reads and writes skip the checkout entirely. When a job does need files on disk, it pays only for what it reads.

## How Scion works

The unit of work is a changeset, an entry in a write-ahead log. Where a git commit points to a tree, a changeset lists the files that changed relative to its first parent, with content-addressed pointers to compressed contents in blob storage. (Using the first parent is a stylistic choice; in trunk-based development, people only care about history on the main line.) With no packfiles, no locking or cross-server coordination, and no refs to move, we can accept changesets at very high throughput. Moving a ref is a separate compare-and-swap on a single Spanner row.

All data is content-addressed and never changes once stored, so any server can cache it without consulting the others. The servers are essentially large caches that can also compute additional structures, such as blame and path history, and write them back to Spanner.

The client doesn't tell the server what it has. It asks only for the trees and blobs it wants, starting from a root tree and recursing. Every request is for an immutable object, so any cache can answer it, and the transfer is resumable. Sparse and virtualized checkouts need no special support: the client simply doesn't ask for trees it doesn't want.

Requests pass through three tiers: a scion-daemon on each node, regional scion-cache servers that stream objects from memory in the daemon's disk format, and the authoritative scion-servers, which read from Spanner or cloud storage. All three answer identical RPCs, but we strictly enforce the tiering to isolate failure domains, so that a failure in a regional cache doesn't overwhelm the upstream servers.

Each tier keeps a cache hit rate over 99% and holds no long-lived state. Compared with our git mirrors, the footprint is 200x smaller in CPU and memory. CI and research jobs check out code two orders of magnitude faster, and CI alone gained 25% CPU capacity.

## What we learned

Claude Mythos Preview and Claude Tag became available internally around when we started. Both amplified the need for Scion and accelerated how quickly we could build it. We had largely handwritten a prototype of the git-to-Scion ingestion pipeline. Asked to rewrite it, with no further instructions, an early Mythos snapshot produced a version that used 20x less memory and ran 4x faster, while preserving the implicit invariants around ordering and data structures.

**Rapid development with a small team will become more common.** Seven people built Scion, Antique (our code review tool), and half a dozen related systems, and migrated to them in five months while daily merges grew 10x. In the past, this would have taken a company years and many more engineers.

**Engineers are no less valuable, but their work is changing.** Every engineer on the system would now rate Claude as better at writing code than them. They still supplied the understanding of inter-system components and design tradeoffs. Very often, their role was to tell Claude "no." Agents sometimes violate core constraints to satisfy a pattern that should never have been allowed; several systems tried to find when a change merged by reading the commit log linearly instead of asking the code review tool. Adversarial review is effective in many ways but can be myopic: one review distrusted another internal service and led Claude to add excessive validation. We still review every change, but we examine its intent rather than every line.

**Operations improved.** Using Claude Tag, we gave each component a "superfan": a Claude in its own Slack channel with access to telemetry and logs, obsessively watching that component's health. We keep traditional alerts, but the superfans can detect subtle and novel issues that make those alerts seem one-dimensional by comparison.

**We're rethinking our priors.** A proper merge queue doesn't make much sense at agent scale. We couldn't effectively replicate a global repository lock, so we invested in post-merge and pre-deploy testing. Concurrent changes can conflict, but Claude can typically fix the conflicts faster than humans can identify them.

## What others can take

Scion only makes sense for truly enormous monorepos, with tens of thousands of engineers or swarms of agents. Anthropic is also unusual in how many tokens it can spend internally. Scion diverges so far from git that adopting it would mean migrating the whole development lifecycle, including our bespoke code review, search, and CI, and we worry a public version built to please everyone wouldn't be very useful.

Instead, we're sharing our thinking so others can bring Scion's most successful parts to git. A git server doesn't have to work like a git client. Forges could offer comprehensive server-side RPCs, perhaps standardized so the git client can talk to them. The negotiation protocol could change, and git's sparse and shallow features could be made to compose well.
