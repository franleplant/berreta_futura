---
source_ids:
- architecture-overview-ce5cb1d1
content_mode: in_a_nutshell
label: IN A NUTSHELL
---

MCP is a protocol for handing context to an AI application. A host — Claude Code, VS Code — opens one client per server. A server offers tools, resources, and prompts. The messages are JSON-RPC 2.0. The protocol is stateless: every request carries its own papers, so the server needs to remember nothing. Locally it speaks over stdin and stdout; remotely, over HTTP POST. That is the whole shape of it.

## Who talks to whom

Three parts. The **host** is the application. The **client** is the connection — one per server, nothing more. The **server** is a program that serves context, whether it runs on your laptop or in a datacenter.

Say you want the weather. You write a weather server. VS Code, on connecting, spins up a client to hold that line open. Connect a second server and you get a second client. Local servers on the stdio transport usually serve one client. Remote servers on Streamable HTTP serve many.

## Two layers

The **data layer** is the inner one: the JSON-RPC messages, the capabilities, the primitives. The **transport layer** is the outer one: how bytes move, how framing works, who is authorized. MCP does not say how you use a model or manage what it gives you. It says only how the context arrives.

## Every request carries its papers

There is no handshake to remember. Each request puts the protocol version and the client's capabilities in `_meta`, and normally the client's name as well:

```json
"_meta": {
  "io.modelcontextprotocol/protocolVersion": "2026-07-28",
  "io.modelcontextprotocol/clientCapabilities": { "elicitation": {} }
}
```

A server must implement `server/discover`, which returns its identity, its supported versions, and its own capabilities. Calling it is optional — a client may send any request cold and handle the version error if one comes back. Discovery is simply the cheap way to ask everything at once, and the answer can be cached.

## What a server offers

Three primitives. **Tools** are functions the model can invoke: `weather_current`. **Resources** are data to read: yesterday's readings. **Prompts** are templates: a worked example of asking for a forecast.

Each has `*/list` to discover and, for tools, `tools/call` to execute. Listings are dynamic by design; results may come back with a freshness hint, `ttlMs`, and a `cacheScope` saying who may reuse them.

## What a client offers

One primitive: **elicitation**. The server asks the user something — a missing city, a confirmation — with `elicitation/create`. Sampling and logging were deprecated in version 2026-07-28. Talk to the model provider directly; log to stderr.

## Notifications, if asked for

Nothing is pushed unbidden. The client opens a long-lived stream with `subscriptions/listen`, naming the events it wants. The server acknowledges, listing only the filters it agreed to honor, and tags every later notification with that subscription's ID. When the tool list changes, `notifications/tools/list_changed` arrives with no `id` and expects no reply. Delivery is best effort. Poll anyway.

## The whole thing, once through

`server/discover` — the server speaks 2026-07-28 and has tools. `tools/list` — one tool, `weather_current`, taking a location and units. `tools/call` with `{"location": "San Francisco", "units": "imperial"}` — a content array comes back with text the model can read. `subscriptions/listen` for `toolsListChanged` — later, a forecast tool appears, the notification arrives, and the client lists again.

A catalogue that announces its own revisions. Everything else is detail.
