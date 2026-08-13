---
source_ids:
- your-agent-needs-a-computer-not-a-container-intr-4851b3c5
content_mode: article
label: ARTICLE
---

The most capable agents have something simple in common: they're given their own computer. Giving every one of them a container doesn't scale; across all the clouds there's nowhere near enough compute in the world for that. So today we're introducing an early preview of [@cloudflare/computer](https://github.com/cloudflare/computer): each agent gets a primed, declaratively defined filesystem and a choice of execution environments, isolate or container, both working against the same files. The agent picks. Our goal is a runtime where the container is required for less than 10% of the work.

## Why not a container each

Coding agents already work this way: filesystem, shell, tools, packages, the ability to run code. Over the past six months, harnesses have moved to sandboxed execution through tools, separating the hands from the brain. But this will not scale to hundreds of millions, then billions, of concurrent agents. This is why there is desperate, panicked industry demand for CPU compute, not just GPU compute.

We made the out-of-consensus bet on isolates almost ten years ago with Workers, and again with Durable Objects. They spin up and tear down quickly, hibernate when the agent is idle, store the agent's own state, and spin up their own isolates to run untrusted code. Isolates are the best way to scale horizontally, and horizontal scale is what agents demand.

Last year we gave isolates the ability to spin up their own container sandboxes. That's how we build agents: harness in the Durable Object, container called on demand as a tool. But asking customers to combine the primitives themselves in userspace is something we think we can do better. Hence an open-source library, and an experiment, to learn with customers pushing the bounds of running agents at scale.

## One filesystem, two runtimes

```
npm install @cloudflare/computer
```

The workspace is a virtual filesystem backed by SQLite, populated from git repositories, storage buckets, or files you choose. It attaches to any Durable Object. Operations are gated, audited and observed: fine-grained control, and a paper trail of what the agent did.

Two runtimes ship, and you can write your own. The isolate runtime uses just-bash to translate shell code into JavaScript inside a dynamic worker, with the filesystem available through bindings. The container runtime gives a full Linux environment, with the filesystem mounted via FUSE and changes synced back. Both answer the same `exec(string, options)`.

The AI SDK toolkit exposes read, write, edit, ls and exec. Exec takes a `backend` argument, and its description guides the choice: fast, cheap worker, or the fully featured container. In our testing, the frontier models are very good at making the correct decision and falling back to containers only when needed.

## What's next

We're already seeing agents use isolates alone to build, test, and deploy JavaScript applications, generate tailored documentation, and drive browsers. Coding tasks, audio/video manipulation, and document creation are what we want isolates to cover. It's an early preview; we can't wait to hear your thoughts.
