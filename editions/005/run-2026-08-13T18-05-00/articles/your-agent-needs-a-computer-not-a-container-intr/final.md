---
source_ids:
- your-agent-needs-a-computer-not-a-container-intr-4851b3c5
content_mode: article
label: ARTICLE
---

Give an agent a computer and it knows what to do. Coding agents already work this way: filesystem, shell, tools, packages, the ability to run code. The obstacle is arithmetic. Across all the clouds there is nowhere near enough compute in the world to give every user's agent its own container, and that will not scale to hundreds of millions, then billions, of concurrent agents. Isolates do scale horizontally: they spin up and tear down quickly, hibernate when the agent is idle, store their own state. So today we're introducing an early preview of `@cloudflare/computer`, an open-source library that hands an agent one declaratively defined filesystem and several places to run code against it. An isolate for manipulating files, processing data, managing a git repo. A container when the task needs Linux, `npm`, or a native binary. The same files either way. Our goal is a runtime where a container is required for less than 10% of the work.

## Why not a container each

Over the past six months we've watched harnesses move from running the agent inside a container to calling a sandbox through tools, separating the hands from the brain. Wherever the harness runs, the container-per-agent bill comes due, and the industry demand for CPU compute, not just GPU compute, is desperate and panicked. We believe meeting that demand requires looking beyond traditional containerization.

We made the out-of-consensus bet on isolates almost ten years ago with Workers, and again almost six years ago with Durable Objects. Last year we gave isolates the ability to spin up their own container sandboxes: the harness runs in a Durable Object and calls the attached container on demand, heavier primitives only when required. That is how we build agents, and customers are building this way too. But asking developers to combine both primitives themselves in userspace is something we think we can do better; we think we can provide a simpler abstraction.

## The workspace

A virtual filesystem backed by SQLite, populated from git repositories, storage buckets, or any files you choose: one library of files, consulted from different rooms. Runtimes share the interface `exec(string, options)`, and two ship in the box. An isolate runtime uses just-bash to translate shell code into JavaScript inside a dynamic worker, with the filesystem available through worker bindings. A container runtime gives a full Linux environment, with the filesystem mounted via FUSE so changes sync back. The `Workspace` class offers a direct API and a `node:fs` compatible wrapper for third-party libraries. All operations are gated, audited and observed, which gives you fine-grained control and a clear paper trail of what the agent did.

Install it:

```
npm install @cloudflare/computer
```

The AI SDK toolkit provides read, write, edit, ls and exec. The exec tool takes a `backend` argument, and its description guides the agent toward the fast, cheap worker or the fully featured container. In our testing, the frontier models are very good at making the correct decision and falling back to containers only when needed.

## Already running

Agents that use isolates exclusively to build, test, and deploy JavaScript applications with modern tooling, to generate tailored documentation for each of our customers, and to drive web browsers through complex tasks. We're shipping this as an experiment, to learn with the customers pushing the bounds of running agents at scale.
