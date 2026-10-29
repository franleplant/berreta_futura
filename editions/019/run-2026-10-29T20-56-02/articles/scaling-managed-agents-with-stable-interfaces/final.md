---
source_ids:
- scaling-managed-agents-with-stable-interfaces-a7646326
content_mode: article
label: ARTICLE
---

Harnesses encode assumptions about what Claude can't do on its own, and those assumptions go stale as models improve. Claude Sonnet 4.5 wrapped up tasks early as it sensed its context limit approaching, so we added context resets; on Claude Opus 4.5 the behavior was gone and the resets had become dead weight. So we built Managed Agents, a hosted service that runs long-horizon agents through a small set of interfaces meant to outlast any implementation, including the ones we run today. We virtualized an agent into three parts: a session (the append-only log of everything that happened), a harness (the loop that calls Claude and routes its tool calls), and a sandbox (where Claude runs code and edits files). Each can be swapped without disturbing the others. We're opinionated about the shape of these interfaces, not about what runs behind them.

Operating systems solved the same problem decades ago. They virtualized hardware into abstractions, *process* and *file*, general enough for programs that didn't exist yet. `read()` doesn't care whether it reads a 1970s disk pack or a modern SSD. The abstractions outlasted the hardware.

## Don't adopt a pet

We started with session, harness, and sandbox in one container. File edits were direct syscalls and there were no service boundaries to design.

But the container became a pet: a named, hand-tended individual you can't afford to lose. If it failed, the session was lost. If it hung, we had to nurse it back. Our only window in was the WebSocket event stream, which couldn't tell a harness bug from a dropped packet from a dead container. Opening a shell inside meant touching user data, so in practice we couldn't debug.

The harness also assumed Claude's work lived in the container beside it. Customers who wanted Claude in their own VPC had to peer their network with ours or run our harness themselves.

## Decouple the brain from the hands

We separated the "brain" (Claude and its harness) from the "hands" (sandboxes and tools) and from the session. Each could fail or be replaced on its own.

**The container became cattle.** The harness calls it like any tool: `execute(name, input) → string`. If it dies, Claude sees a tool-call error and may retry; a new one comes up with `provision({resources})`.

**The harness became cattle.** The session log lives outside it, so nothing in the harness needs to survive a crash. A new one boots with `wake(sessionId)`, reads the log with `getSession(id)`, and resumes from the last event. During the loop it records events with `emitEvent(id, event)`.

**Credentials left the sandbox.** In the coupled design, Claude's generated code ran beside the credentials, so a prompt injection only had to convince Claude to read its own environment. Narrow scoping helps, but it assumes what Claude can't do with a limited token, and Claude is getting increasingly smart. The structural fix: tokens are never reachable from the sandbox. For Git, the repo's token clones the repo at sandbox setup and is wired into the remote; `push` and `pull` work without the agent handling it. For MCP tools, OAuth tokens sit in a vault, and a proxy fetches them per session to make the call. The harness never sees credentials.

## The session is not Claude's context window

Compaction, memory files, and context trimming all make irreversible choices about what to keep, and it is hard to know which tokens future turns will need. Prior work has stored context as an object outside the window, such as one in a REPL that the model slices with code.

The session does the same, but durably. `getEvents()` lets the brain select positional slices: resume where it stopped, rewind to see the lead-up to a moment, reread before an action. The harness can transform fetched events before they reach Claude, for prompt cache hit rate or any other context engineering. We kept storage in the session and management in the harness because we can't predict what context engineering future models will require.

## Many brains, many hands

**Many brains.** With the harness out of the container, the VPC peering requirement went away. So did a cost: before, every session paid full container setup before any inference, even sessions that never touched the sandbox. Now containers are provisioned by tool call only when needed, and inference starts once pending events are pulled from the log. Our p50 time-to-first-token dropped roughly 60% and p95 over 90%. Scaling to many brains means starting many stateless harnesses.

**Many hands.** Reasoning across many execution environments is harder than working in one shell. We started with one container because earlier models weren't capable of this. As intelligence scaled, the single container became the limit: when it failed, we lost state for every hand the brain reached into. Now each hand is a tool behind `execute(name, input) → string`, whether a custom tool, an MCP server, or our own. The harness doesn't know if the sandbox is a container, a phone, or a Pokémon emulator. Because no hand is bound to a brain, brains can pass hands to one another.

## Conclusion

Managed Agents is a meta-harness, unopinionated about the specific harness Claude will need. Claude Code is one we use widely; task-specific harnesses excel in narrow domains; it can hold any of them. We are opinionated about the interfaces: Claude will need to manipulate state (the session), perform computation (the sandbox), and scale to many brains and many hands. We make no assumptions about how many brains or hands Claude will need, or where they will be.
