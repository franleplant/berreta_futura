# Making every harness durable

By Pranay Prakash, Eric Dodds · Vercel · October 19, 2026

Developers are familiar with running coding agents locally through harnesses like Pi, Claude Code, and others. They are reliable daily drivers for generating code, but keeping agents running around the clock requires your computer to be on and awake, which led to the laptop lid memes and Mac mini demand spike.

![Harnesses run in the cloud now, so you can close the lid.](media/001.jpg)

![Harnesses run in the cloud now, so you can close the lid.](media/002.jpg)

#### Running harnesses in the cloud

Harness workloads are moving to the cloud. Individual developers are deploying always-on coding agent workflows, projects like OpenWork and HanaAgent use open-source harnesses as the engines behind the apps, and engineers are building their own harness products.

These harnesses are designed for long-lived processes that keep the session in memory, and agent tasks commonly run for minutes or hours. Locally, a harness has direct, continuous access to the workspace and session history on the same disk, so resuming interrupted work only requires a simple prompt.

In the cloud, you can replicate that setup with a VM and persistent storage, but the VM doesn't automatically record which model and tool calls completed or resume interrupted turns after a crash. A failed turn or network error means lost work.

Also, not every agent task executed through a harness needs a sandbox. Database queries and API calls can run securely in functions, and that also means required credentials never have to enter the sandbox.

### Making every harness durable

We built [eve](https://eve.dev) and [fx](https://fx.sh/) to run durably in the cloud out of the box, and today we are introducing `durable-harness`, which extends that durability to any harness, including [Pi](https://github.com/earendil-works/pi), [OpenCode](https://opencode.ai/), [Codex](https://github.com/openai/codex), and [Claude Code](https://docs.claude.com/en/docs/claude-code/overview). It uses the same machinery that powers [Workflow SDK](https://workflow-sdk.dev/) to survive crashes and function timeouts.

With `durable-harness`, you can:

- Run any of these harnesses durably on Vercel
- Self-host a harness with your own Postgres instance
- Make your local harness workflow durable
- Build your own durable harness

## Sessions that survive a crash mid-turn

Take the example of a coding agent adding a pricing page to an existing app. The agent reads the existing page, writes a new one, opens a pull request, and waits for CI to finish before reporting back.

What happens if its function times out while CI is still running?

Kill the function or drop the connection in the demo below to compare how the two agents recover and which work is repeated.

Without durability, the agent stops work until it is manually restarted, and completed work is repeated unnecessarily.

With `durable-harness`, a new function reads completed results from the log and resumes the turn. If the browser disconnects, the agent keeps running, and reconnecting catches up from the log.

## Logs and queues

`durable-harness` is the newest package in our open source portfolio. It's a set of adapters and utilities that let the harnesses you already use keep their sessions in a [World](https://workflow-sdk.dev/worlds), the Workflow SDK's durable backend.

It writes each step of a turn to a durable log. Before a model call or tool call runs, it records an intent, and when the call finishes, it records the outcome. The turn itself is backstopped with a queue message, so if its function dies, the queue hands the turn to a new function that reads the log and continues where it left off.

After a crash, the log says what finished, what was running, and what never started:

- Completed calls never run again because their results are read from the log, so you're never billed twice for a finished model call's tokens.
- Models remember their previous calls rather than repeating them.
- Interrupted tools marked `replay: 'safe'` run again. Any other tool comes back to the model as possibly run, and the model decides whether to check.

Harnesses that keep their own session files, like Claude Code's transcript, Codex's rollout, and OpenCode's event store, have every record mirrored into the log, so a new function or Sandbox rebuilds them from it.

## Pick your harness

[fx](https://fx.sh/) and [eve](https://eve.dev) are durable on their own. For the rest, `durable-harness` adds durability from the outside, without changing the harness.

For the full setup guide for each harness, check the [docs](https://vercel.com/docs/agent-harnesses/harnesses).

## Runs everywhere

Durable agents need a log of each step, a way to resume a turn when its process dies, and a stream for whoever is watching.

Workflow SDK ships all three behind one interface, a [World](https://workflow-sdk.dev/worlds).

```typescript
import type { Queue, Storage, Streamer } from '@workflow/world'
interface World extends Storage, Queue, Streamer {}
```

A World is the log, the backstop and the stream behind one interface.

`durable-harness` writes to that interface, so you can move the same agent from one World to another without changing its code:

- On Vercel, it uses the [Vercel World](https://workflow-sdk.dev/worlds/vercel).
- In development, it uses [files on your machine](https://workflow-sdk.dev/worlds/local).
- On your own servers, it uses [Postgres](https://workflow-sdk.dev/worlds/postgres), MongoDB, Redis, or Turso.

Two variables move every agent using `durable-harness` to Postgres.

```bash
WORKFLOW_TARGET_WORLD="@workflow/world-postgres"
WORKFLOW_POSTGRES_URL="postgres://user:password@host:5432/database"
```

Redirects durable-harness to use the Postgres World for durability.

For more control, such as setting a namespace or recovering sessions when your server starts, create the World in code and pass it to your agent:

Check the [self-hosting docs](https://vercel.com/docs/agent-harnesses/self-hosting) for more details.

## See every session in Agent Runs

[Agent Runs](https://vercel.com/docs/agent-harnesses/observability) on Vercel shows the trace for every session, including each model call and tool call. Turns that resumed after a crash appear in the same trace, so you can see exactly where a turn stopped and picked back up.

A Pi session in the Agent Runs tab with an interrupted and retried model call.

## Tools

An agent has only the tools you give it, and they run in your function. Each tool says what should happen if a crash interrupts it. A `'safe'` tool, such as a lookup, can run again. A `'never'` tool, such as a refund, never runs twice: the model is told the call may have happened, so it can check before it tries again.

Here's how the coding agent from the demo above might define its tools:

- A tool that reads a file or checks CI status is marked as `'safe'` so it can run again automatically.
- A tool that posts a PR comment is marked as `'never'` so that comments aren't posted twice.

The following example defines a tool for each policy using the example of an agent processing a refund:

```typescript
import { pi } from 'durable-harness/pi';
import type { HostTool } from 'durable-harness';
import { getOrder, refundOrder } from './orders'; // your own code

const tools: HostTool[] = [
  {
    name: 'get_order',
    description: 'Looks up an order',
    replay: 'safe', // safe to run again after a crash
    inputSchema: { type: 'object', properties: { id: { type: 'string' } }, required: ['id'] },
    execute: async ({ id }) => JSON.stringify(await getOrder(id)),
  },
  {
    name: 'refund_order',
    description: 'Refunds an order',
    replay: 'never', // never runs twice
    inputSchema: { type: 'object', properties: { id: { type: 'string' } }, required: ['id'] },
    execute: async ({ id }) => JSON.stringify(await refundOrder(id)),
  },
];

export const agent = pi({ model: 'anthropic/claude-sonnet-5.5', tools });
```

A lookup can run again after a crash, and a refund never runs twice.

For each harness's built-in tools, like its shell and file editing, read on.

## Files

When a harness needs a shell and files, it's not safe to run them directly on a shared serverless function host. Many sessions can share the same function, and its filesystem isn't guaranteed to persist between invocations.

To address this, `durable-harness` gives you a few options:

- `virtual()` keeps the files in the session's log, with a bash-compatible shell that can't reach your function's files or the network. It suits short tasks and small workspaces without starting an entire sandbox.
- `virtual({ durable: false })` keeps the files in memory for scratch work and clears them at the end of every turn.
- `sandbox()` gives the session its own [Vercel Sandbox](https://vercel.com/docs/sandbox), with `/workspace` on a [Drive](https://vercel.com/kb/guide/vercel-drives) that outlives every sandbox and every function. It suits real projects and long-running work.

Compare the three side by side in the [docs](https://vercel.com/docs/agent-harnesses/tools#files).

Each harness's built-in tools run on the workspace you choose. With Pi, `CodingTools` installs Pi's own `read`, `write`, `edit`, and `bash`, and `virtualEnv()` or `sandboxEnv()` gives them a workspace:

```typescript
import { BACKGROUND_CONTEXT as ctx } from '@earendil-works/chord/context';
import { createRegistry, Harness, type Storage } from '@earendil-works/pi-durable';
import { CodingTools, gatewayModels, resumeWith, virtualEnv } from 'durable-harness/pi-durable';

const models = gatewayModels();
const registry = createRegistry();
registry.install(CodingTools); // Pi's read, write, edit, and bash

// Files kept in the session's log, or sandboxEnv() for the session's own Vercel Sandbox
const env = virtualEnv();

export const open = resumeWith((storage: Storage) => Harness.open(storage, { models, registry, env }, ctx));
```

Gives Pi its coding tools on a virtual workspace or in a Vercel Sandbox.

For OpenCode, pass the workspace as `workspace`, and for fx, pass it to `fxTools()`. Claude Code and Codex always run in a Vercel Sandbox, since they expect a real shell and filesystem, and aren't safe for multi-tenant use. Their built-in tools work on the session's Drive once you turn them on with `builtins: true`. Each [harness guide](https://vercel.com/docs/agent-harnesses/harnesses) lists its built-in tools.

## Documents

Some state belongs with the session but isn't part of the conversation, such as a to-do list, a plan, or a form the agent fills in. A document is typed JSON that lives in the session's log, so it survives a crash and moves with the session.

Tools can edit documents through `io.docs`, and each edit commits to the log alongside the tool's result, so the document's durable state stays consistent with the tool calls themselves:

```typescript
import { defineDoc, type HostTool } from 'durable-harness';

export const Todos = defineDoc<{ items: string[] }>({
  kind: 'app.todos',
  version: 1,
  initial: () => ({ items: [] }),
});

export const addTodo: HostTool<{ item: string }> = {
  name: 'add_todo',
  description: 'Adds a todo',
  replay: 'safe',
  inputSchema: { type: 'object', properties: { item: { type: 'string' } }, required: ['item'] },
  async execute({ item }, io) {
    const todos = io.docs!.update(Todos, (draft) => {
      draft.items.push(item);
    });
    return `${todos.items.length} todos`;
  },
};
```

Defines a to-do list document and a tool that adds to it.

Your app can read and edit the same document without a database of its own, and the chat route can even stream every change to your UI:

```typescript
import { agent } from '@/lib/agent';
import { Todos } from '@/lib/todos';

// In a route or webhook: read the list without a database of your own
const { value } = await agent.sessions.doc(sessionId, Todos);

// In the chat route: stream every change to the browser
export const { GET, POST } = agent.chatRoute({ authorize, docs: [Todos] }); // your auth check
```

Reads the to-do list from your app and streams its changes to your UI.

In fact, the `virtual()` workspace from earlier is built on documents: its file tree is a document in the session's log, and each tool call's changes commit with its result.

Learn more about [tools, files, and documents](https://vercel.com/docs/agent-harnesses/tools) and how to [keep your agent secure](https://vercel.com/docs/agent-harnesses/security).

## Wrapping up

Developers choose a harness for the choices it makes about prompts, tools, and context. How it survives a crash shouldn't be one of them. With `durable-harness`, a turn that loses its function partway through continues from the log on a new one, without a manual retry and without repeating what already finished. Self-hosting and portability work out of the box by building on top of the Workflow SDK's World interface.

`durable-harness` is [open source on GitHub](https://github.com/vercel-labs/durable-harness).
