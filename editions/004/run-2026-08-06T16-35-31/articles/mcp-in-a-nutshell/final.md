---
source_ids:
- architecture-overview-ce5cb1d1
content_mode: in_a_nutshell
label: IN A NUTSHELL
---

**The thirty-second version.** MCP hands context from a program to an AI application. The application is the host; it opens one client per server, one connection each. A server offers three things: tools to run, resources to read, prompts to borrow. The messages are JSON-RPC 2.0. Every request states its own protocol version and capabilities, so the server remembers nothing between them. Local servers speak over stdio, remote ones over HTTP POST with optional Server-Sent Events. The rest is detail.

## Who talks to whom

VS Code is a host. Connect it to a weather server and its runtime makes a client for that server. Connect it to the filesystem server as well and it makes a second client. The word *server* says nothing about where the thing runs. The filesystem server runs on your machine because it uses stdio. Sentry's runs on Sentry's platform because it uses Streamable HTTP. Same word, different rooms.

Two layers. The data layer is the protocol itself: the requests, the primitives, the notifications. The transport layer is the pipe: connection, framing, authorization — OAuth for tokens, if you are on HTTP. The data layer does not care which pipe it is in.

## What is on offer

Servers expose tools, resources, and prompts. Tools do things. Resources hold things. Prompts are templates for talking to a model. Each has `*/list` to discover it and `*/get` to fetch it; tools also have `tools/call`.

Clients expose one primitive now: elicitation, by which a server asks the user a question or asks for confirmation, via `elicitation/create`. Sampling and logging are deprecated as of protocol version `2026-07-28`. Call the model's API yourself; log to stderr.

## The weather server, start to finish

Our server has one tool. Follow the whole conversation.

The client sends `server/discover`. It does not have to — every request already carries `io.modelcontextprotocol/protocolVersion` and `clientCapabilities` in its `_meta`, and normally `clientInfo` too, so any request can be the first one. Discovery is simply the cheap way to learn everything at once, and the answer is cacheable. Ours declares `"elicitation": {}`. The server answers with its supported versions and `"tools": {"listChanged": true}`, `"resources": {}`. Speak a version it does not know and it refuses with `UnsupportedProtocolVersionError` and a list of versions it does know. You retry.

The client sends `tools/list`. Back comes an array. One tool: `weather_current`, with a title, a description, and an `inputSchema` naming `location` and `units`. The result is marked complete and carries `ttlMs` — five minutes, here — and a `cacheScope` saying who else may reuse it.

The client sends `tools/call` with the name exactly as listed and arguments matching the schema: San Francisco, imperial. Back comes a `content` array of typed objects. This one is text. The host feeds it to the model.

Then the tool list changes. The client learns of it only if it asked to. Notifications are opt-in: it opens a long-lived stream with `subscriptions/listen` and a filter, `"toolsListChanged": true`. The server acknowledges with the subset it will honor, and every notification on that stream is tagged with the ID of the listen request that opened it. When the tools change, `notifications/tools/list_changed` arrives, with no `id`, expecting no reply. The client sends `tools/list` again. Delivery is best effort. Across a reconnect, notifications are lost. Poll anyway.

Long jobs get a handle. The Tasks extension lets a server return one and lets the client come back later for the result.

---

A server's list of tools is a catalog that can be rewritten while you are reading it. The protocol's only real promise is that it will tell you when — if you remembered to ask.
