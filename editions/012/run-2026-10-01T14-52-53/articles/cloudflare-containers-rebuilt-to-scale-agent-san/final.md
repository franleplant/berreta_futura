---
source_ids:
- cloudflare-containers-rebuilt-to-scale-agent-san-f1767644
content_mode: article
label: ARTICLE
---

Agents don't deploy sandboxes ahead of time. They create one per task, expect it ready immediately, and want to pause and resume it. So we rearchitected Cloudflare Containers. Your code now chooses each sandbox's image and instance type at runtime, Containers start 6x faster, and filesystem snapshots are in public beta. In ComputeSDK's independent benchmark, median startup fell from just over four seconds to 648 milliseconds. All of it builds on what has always set Containers apart: every Container gets its own Durable Object, a persistent, programmable controller running right next to it.

## Why deployments didn't fit

Until now, Containers were organized around application deployments. You chose an image and compute resources at deploy time and rolled that configuration out across the application. An agent workspace is created on demand, while the agent is working. The task determines its image, resources, tools, and starting filesystem. It might exist for a few minutes, sleep between requests, or be restored days later. Coding agents need repositories, compilers, and test runners. Evals need sandboxes that begin from a known state. Reinforcement learning systems need to create, grade, and reset large numbers of environments. Longer tasks need to keep the files an agent produces.

## The image is an argument

Each combination of image and instance type used to be its own application, with its own Durable Object namespace, set up with `wrangler deploy`. A small Node.js sandbox and a large Python one meant two applications, two namespaces, and routing logic in your Worker.

With the new `durable_object` scheduling policy, you declare your images in `wrangler.jsonc`, and the image and instance type become arguments your code passes to `this.ctx.container.start()`. What used to take a separate application and a separate `wrangler deploy` is now an `if` statement. Infrastructure becomes code that runs at request time, right down to the environment itself.

Rollouts follow from this. Before, updating an image meant updating the whole application: grace periods, percentage splits, API calls, and the platform deciding which instances got replaced and when, whether an agent was in the middle of a task. Now there's no rollout configuration at all. A Container can keep running the image it started with until your code stops it. The next start uses whatever image your code chooses:

```
const image =
  (await this.ctx.storage.get("pinned-image")) ??
  (isCanary(this.ctx.id)
    ? this.ctx.container.images.nodeV2
    : this.ctx.container.images.node);
```

You can canary a new toolchain on 5% of new sandboxes by hashing the Durable Object ID, pin active projects to their current image, migrate a workspace at a natural checkpoint, or roll back by changing which image future starts choose.

## Faster first commands

Previously, our global control plane resolved the application configuration, found capacity, and coordinated placement. That put deployment machinery in the path of an agent's first command. Now demand begins at the Durable Object. The infrastructure looks for capacity on the same machine first, then within the same location, and favors hosts that already have the image or snapshot locally. On the host, the runtime restores a prepared virtual machine that isn't yet assigned instead of booting one from scratch, reuses networking and filesystem setup, batches repeated operations, and no longer waits on services the first command doesn't need.

On ComputeSDK's Burst TTI Benchmark, which launches 100 sandboxes concurrently:

| Startup measurement | Previous scheduling path | New scheduling policy | Improvement |
| --- | --- | --- | --- |
| Median | 4.049 seconds | 648 milliseconds | 6.2x faster |
| 95th percentile | 5.839 seconds | 910 milliseconds | 6.4x faster |
| 99th percentile | 6.717 seconds | 1129 milliseconds | 5.9x faster |

In our preliminary burst test, a single account started 100,000 Containers in 5.387 seconds across six locations.

As scheduling gets faster, preparing the image becomes a larger part of the wait. So we're introducing `cloudflare/debian-trixie`, a ready-to-use system image with Debian Trixie Slim and Node.js 24.20.0 LTS. Your agent can start a Linux sandbox without creating a Dockerfile, building an image, or pushing it, then use `exec()` to clone a repository, install packages, and configure its environment. Because we control this image, we can prepare it across eligible hosts before requests arrive.

## Snapshots

Cloning a repository, installing dependencies, and configuring a toolchain can take much longer than starting the Container. Snapshots, in public beta, let an agent save its workspace when a task pauses and restore it when the session resumes.

One workspace can continue across many sessions: a coding agent saves when the user finishes and restores when they return the next day, with repository, dependencies, build caches, and edits in place. And since snapshots are immutable and reusable, many Containers can start from the same prepared environment. An eval running the same task across different prompts, skills, models, or agent versions can start every attempt from one baseline, reducing setup time and preventing environment drift from affecting the results. An agent can also start from `cloudflare/debian-trixie`, set up with `exec()`, and save the result as a snapshot for future sandboxes.

## The Durable Object, made explicit

Agent systems need a stateful environment outside the Container to keep state, hold credentials, and control the sandbox's lifecycle. You can run the agent in the Durable Object and use the Container as its workspace, following the "decoupling the brain from the hands" pattern described by Anthropic, or run the agent in the Container and use the Durable Object to supervise it. Under the new policy, the Durable Object controls its Container directly: `exec()`, outbound request interception, runtime image and instance selection, and snapshots are all on `ctx.container`. That allows:

- An agent loop in the Durable Object that stays available over WebSockets while its Linux workspace sleeps, paying nothing for idle Linux compute.
- A Durable Object that updates its Container's Outbound Request Handler to inject newly granted credentials, enforce new policies, or record activity.
- An eval coordinator that snapshots a base workspace, forks it into N attempts, each with its own Durable Object and Container, grades them, snapshots the best, and forks again. Each Durable Object preserves its result even if the Container crashes.

When we launched, we deliberately hid the Durable Object behind the Container class so sandboxes would feel familiar, and the Sandbox SDK built command execution, interception, and snapshots in userspace. That abstraction made it harder to combine the Durable Object's identity, state, and coordination with the Container, and nearly every team needed a slightly different lifecycle. So:

- New capabilities are native-only, through `ctx.container`.
- We'll maintain the `Container` class and legacy `Sandbox` class through December 31, 2026. Existing deployments keep running after that date, but the classes won't get updates. We recommend migrating.
- Sandbox SDK 1.0 is a set of utilities, not a base class.
- `@cloudflare/computer` combines Dynamic Workers and Containers with a synchronized filesystem.

Migrating usually means changing extends `Container` to extends `DurableObject` and calling `this.ctx.container` directly. The `durable_object` scheduling policy is available to all today in public beta.
