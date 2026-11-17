---
source_ids:
- building-always-on-agents-2fce942b
content_mode: article
label: ARTICLE
---

Always-on agents are stateful and proactive: they manage context across sessions and act without direct supervision. They run on the same core loop as other agents; the difference is the architecture around it. We've seen a resurgence of them because the latest models have better judgment about user intent and when to check in, and because intelligence is getting cheaper, with long-horizon tasks benefiting most. On one long-horizon coding benchmark, Opus 5.5 cost 78% less per solved task than Opus 5, compared with 40% less on typical workloads. The architecture comes down to five primitives: an event inbox, timers, memory, permissions, and an outbox.

## The cycle

An always-on agent is not actually "always on." That describes the user experience. The agent spends most of its time asleep and wakes periodically to do work. Each stretch of work is a **run**: an event arrives, the agent completes its task, and it saves what happened. A run works inside a **session**, the transcript of messages and tool calls. Then the agent sleeps, and the cycle repeats.

## Event inbox

Always-on agents can be triggered by webhooks, scheduled tasks, and background jobs, not only by user messages. Letting each source call the agent directly fails in a few ways: two simultaneous events can start competing runs, and a crash can lose an event entirely.

So every source writes to an inbox instead. The simplest version has three parts: a durable list of events (usually a database table), a handler that writes to it (usually an HTTP endpoint), and a worker that reads from it (usually a background service). The inbox tracks each event's status and can deduplicate on the source's identifiers. We recommend starting with one inbox per user.

Events that continue earlier work, such as a user reply, resume an existing session; everything else starts a new one. A few practices:

- **Acknowledge quickly.** Some sources treat slow responses as failures. Deeper checks, such as for prompt injection, belong in the run.
- **The inbox is the source of truth.** A woken worker pulls the latest events first, so if it dies mid-run, a new one can retry.
- **One active worker per inbox.** This prevents duplicated or overwritten work. A new event mid-run can go to the next run, fold into the current one, or interrupt and restart it.
- **Batch pending events.** Several messages in a row can become one run and one reply.

## Timers

Timers, with the inbox, make the agent proactive. A **follow-up** is a deadline the agent sets for itself, such as checking on a reply. A **schedule** recurs on a known cadence, such as a daily newsletter, and must also track its recurrence.

Timers live in their own durable store, separate from the inbox, which should hold only events ready to be worked on. A timer doesn't start a run itself. A scheduler polls the store at a fixed interval, marks due follow-ups done, moves due schedules to their next occurrence, adds an event to the inbox, and wakes the worker. You can build the scheduler yourself or use a durable execution engine.

## Memory

Memory is what holds continuity across disjointed runs. In Claude Code's auto memory and the Messages API's memory tool, it's a directory of files; for an always-on agent, that directory should map to durable storage so memories outlive the worker.

Memory should only hold what the agent can't look up again. If something lives in another system, such as an issue tracker, save a pointer. An always-on agent should store:

- **User instructions**, in their own file, loaded every run, since the user won't always be there to steer.
- **User notes**: role, preferences, corrections. Start with one file; as notes grow, split them and load only an index.
- **Past messages**, so nothing is repeated, either in a file or loaded by the worker.
- **Task progress**, one file per ongoing task, so any run can pick up where the last left off. Again, load only an index.

You can also add dreaming, which reviews past sessions to replace outdated entries and find patterns visible only across many runs.

Every run loads the system prompt, tool definitions, and memory files before any work. We recommend keeping this overhead lean and using prompt caching to lower costs. If a session grows too long, you can compact older messages or start a new session. Both lose detail, so anything that must persist should be saved to memory along the way.

## Permissions

Permissions are where always-on agents carry the most risk: a run holds the user's access and operates unattended. For each tool call, the agent must proceed, block, or wait for approval. The components are the same ones other agents use:

- **Credential store.** The recommended pattern is a proxy outside the agent's environment that injects real credentials into outgoing requests the agent sends without them.
- **Auto mode.** As in Claude Code, classifiers review higher-risk actions and block the dangerous ones so Claude can find a safer approach. User review is still necessary for the most important decisions.
- **Deferred tool calls.** A hook can defer a call until the user answers. The run ends with the session saved mid-call, the request is shown to the user, and the answer returns as an inbox event that starts a new run resuming the session. Meanwhile the worker can handle other events.

## Outbox

Most agents stream their work to the user. Always-on agents work in the background, and the user gets the outcome and a few details. A run ends in one of three ways: the agent sends a message, decides nothing needs sending, or defers a tool call to ask for permission or input.

Most agents can get by with a "send" tool. You only need a formal outbox, a table of outgoing messages read by a dispatcher, when you want to pace messages or let the agent recover from errors. Too many messages make the agent noisy; too few miss what the user needs. We recommend building evals to find the balance. In practice, it's better for the agent to start quiet and earn more of the user's attention over time.

## How it fits together

Every run starts with an event from the inbox: a user message, a webhook, or a timer. The worker starts a run in a new or existing session. The agent reads its memory, acts within its permissions, updates its memory, and pushes a row to the outbox for the dispatcher to deliver. A run can set a timer that wakes the agent later, and a user's reply returns as a new event. Each run is brief, but the cycle keeps going indefinitely, and that's what makes the agent feel like it's always on.
