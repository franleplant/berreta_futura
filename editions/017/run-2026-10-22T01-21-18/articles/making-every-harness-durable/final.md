---
source_ids:
- making-every-harness-durable-974b525b
content_mode: article
label: ARTICLE
---

Harnesses like Pi, Claude Code, Codex, and OpenCode were built for long sessions held in memory on one machine. In the cloud, a VM with persistent storage doesn't record which model and tool calls completed, or resume an interrupted turn after a crash. A failed turn or network error means lost work. Today we're introducing `durable-harness`, an open-source package that extends the durability eve and fx already have to any harness. It writes each step of a turn to a log, so a new function continues where a dead one stopped, without repeating what finished.

## The log and the queue

Before a model call or tool call runs, `durable-harness` records an intent. When the call finishes, it records the outcome. A queue message backstops the turn: if its function dies, the queue hands the turn to a new function that reads the log and continues.

After a crash, the log says what finished, what was running, and what never started:

- Completed calls never run again. Their results are read from the log, so you're never billed twice for a finished model call's tokens.
- Interrupted tools marked `replay: 'safe'` run again. Any other tool comes back to the model as possibly run, and the model decides whether to check.

Claude Code's transcript, Codex's rollout, and OpenCode's event store are mirrored record by record into the log, so a new function or Sandbox rebuilds them from it. If the browser disconnects, the agent keeps running, and reconnecting catches up from the log. None of this changes the harness itself.

## Tools

Each tool states what happens if a crash interrupts it. A file read or a CI status check is `'safe'` and runs again automatically. A refund or a PR comment is `'never'`. The model is told the call may have happened, so it can check before it tries again.

## Where it runs

A durable agent needs a log of each step, a way to resume a turn when its process dies, and a stream for whoever is watching. Workflow SDK ships all three behind one interface, a World:

```typescript
import type { Queue, Storage, Streamer } from '@workflow/world'
interface World extends Storage, Queue, Streamer {}
```

The same agent moves between Worlds without code changes: the Vercel World on Vercel, files on your machine in development, and Postgres, MongoDB, Redis, or Turso on your own servers. Two variables move it to Postgres:

```bash
WORKFLOW_TARGET_WORLD="@workflow/world-postgres"
WORKFLOW_POSTGRES_URL="postgres://user:password@host:5432/database"
```

## Files and documents

A shared serverless host isn't a safe place for a shell. Many sessions can share one function, and its filesystem isn't guaranteed to persist. There are three options:

- `virtual()` keeps files in the session's log, with a bash-compatible shell that can't reach your function's files or the network. It suits short tasks and small workspaces.
- `virtual({ durable: false })` keeps files in memory and clears them at the end of every turn.
- `sandbox()` gives the session its own Vercel Sandbox, with `/workspace` on a Drive that outlives every sandbox and every function. It suits real projects and long-running work.

Claude Code and Codex always run in a Vercel Sandbox, since they expect a real shell and filesystem and aren't safe for multi-tenant use.

Some state belongs with the session but not the conversation: a to-do list, a plan, a form. A document is typed JSON in the session's log. Each edit commits alongside the tool's result, and your app can read it without a database of its own. The `virtual()` workspace is itself a document.

## Wrapping up

Developers choose a harness for the choices it makes about prompts, tools, and context. How it survives a crash shouldn't be one of them. `durable-harness` is open source on GitHub.
