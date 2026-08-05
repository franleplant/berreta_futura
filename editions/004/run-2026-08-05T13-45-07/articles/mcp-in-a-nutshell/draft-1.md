---
source_ids:
- architecture-overview-ce5cb1d1
content_mode: faithful_synthesis
label: FAITHFUL SYNTHESIS
---

Open Visual Studio Code and point it at two servers, one for Sentry and one for the local filesystem, and its runtime builds two separate client objects, one dedicated connection each. That is the whole shape of the Model Context Protocol: an AI application, the host, holds one client per server, and every server, wherever it runs, answers the same three requests. Discover what it offers. Ask it for something. Listen for when the answer changes. MCP governs that exchange and nothing past it: what the model does with what comes back is the host's business, not the protocol's.

## Transport layer

A local server, like that filesystem server, connects over stdio. Stdio means standard input and output between two processes on the same machine. It has no network in between. A local server usually serves one client.

A remote server, like the hosted Sentry server, connects over Streamable HTTP. The client sends HTTP POST requests. The server can stream replies back over Server-Sent Events. A remote server usually serves many clients at once.

Streamable HTTP carries ordinary HTTP authentication: bearer tokens, API keys, custom headers. MCP recommends OAuth for obtaining those tokens. Either transport carries the same message format underneath. MCP calls this the transport layer, and its only job is moving the same JSON-RPC 2.0 protocol across a different kind of wire.

## Statelessness and discovery

MCP's core protocol, the data layer, is stateless. A server does not remember the last request. Every request carries its own protocol version and its own capabilities, both in a `_meta` field. A client should also put its own name and version in `_meta`, unless told not to.

A server that wants to announce what it supports implements `server/discover`. Every server must offer it. Its response lists the protocol versions the server accepts, the primitives it exposes, and the server's own identity. A client can cache that response instead of asking again before its next call.

Calling `server/discover` is optional, though. Every request already carries version and capability information. A client can send `tools/call` directly, and if the server rejects it with an `UnsupportedProtocolVersionError`, the client retries with a different version. Discovery is a convenience, not a requirement.

## Primitives

A server can expose three things: tools, resources, and prompts. A tool is a function the AI application can call to take an action: querying a database, calling an API, writing a file. A resource is data the application can read: a schema, a file, a record. A prompt is a template for structuring an interaction: a system prompt, a set of worked examples. Each primitive has its own `list` method for discovery and its own `get` method for retrieval; tools also have a `call` method. A server built around a database, for instance, can offer query tools, a resource holding the schema, and a prompt showing how to use both together.

A client can expose one thing back to a server: elicitation. Elicitation lets a server ask the user a question through `elicitation/create`, when it needs more input or a confirmation before acting.

Two older client primitives, sampling and logging, were deprecated in protocol version 2026-07-28. Sampling let a server request a completion from the client's own AI application, so the server never had to bundle a model SDK of its own; a server built today should call a model provider directly instead. Logging let a server hand debug messages to the client; a server built today should write those messages to stderr over stdio, or send them through OpenTelemetry.

## Notifications

Notifications tell a client something changed. The client does not have to ask. Notifications are opt-in: a client opens a long-lived stream with `subscriptions/listen`, naming the event types it wants, and the server writes back an acknowledgment carrying that subscription's own ID.

Every later notification on the stream carries that same ID, so a client juggling several subscriptions can tell which one just fired. No notification carries an `id` field of its own, because none of them expects a reply.

Ask for `toolsListChanged`, for example. When the server's tools change, it sends `notifications/tools/list_changed` on the stream, and the client typically answers by calling `tools/list` again.

None of this is guaranteed. A notification can be lost, particularly across a transport reconnect, so a client that only listens, and never polls, will drift out of date.

Run the whole sequence once and the pattern holds: discover what is on offer, list the tools, call `weather_current` with a city and a unit system, then go quiet until told something changed. Even the answer carries its own expiration, a `ttlMs` of five minutes for a weather lookup, because MCP's job ends at the reply. What the model does with that reply, and whether it trusts a five-minute-old temperature, is left to the host it was built to serve.
