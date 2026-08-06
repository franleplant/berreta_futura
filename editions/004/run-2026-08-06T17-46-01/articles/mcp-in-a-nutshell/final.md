---
source_ids:
- architecture-overview-ce5cb1d1
content_mode: in_a_nutshell
label: IN A NUTSHELL
---

**The 30-second version.** MCP is a protocol for handing context to an AI application. A host — Claude Code, Claude Desktop, VS Code — opens one client per server. Each server offers three things: tools it can run, resources it can read, prompts it can lend. Messages are JSON-RPC 2.0. Every request carries its own protocol version and capabilities in `_meta`, so the server needs no memory of what came before. That is the whole idea. The rest is detail.

## The participants

A host is the AI application. It coordinates clients. A client holds one connection and fetches context through it. A server is the program that serves the context, and it does not matter where it runs. Local servers speak over stdio and usually serve one client. Remote servers speak Streamable HTTP and serve many.

Connect VS Code to Sentry and it makes a client. Connect it to the filesystem too and it makes another.

## The two layers

The data layer is the inner one: JSON-RPC messages, discovery, primitives, notifications. The transport layer is the outer one: stdio for local processes, Streamable HTTP for the rest, with bearer tokens, API keys, or OAuth. The message format does not change when the transport does.

## No memory, so ask

MCP is stateless. Each request states the version it speaks and the capabilities it brings; clients should name themselves as well. A server can answer any request alone, like a librarian who is handed the catalogue afresh with every question.

Servers must implement `server/discover`. Clients may call it first to learn versions, capabilities, and identity in one round trip, or skip it and handle a version error if one comes back. The answer is usually cacheable.

## What is on offer

Tools do things. Resources supply data. Prompts are templates. Each has `*/list` to find it and `*/get` to fetch it; tools add `tools/call`. Listings are dynamic, so the client asks rather than assumes.

Clients offer one primitive back: elicitation. A server that needs more from the user, or a confirmation, calls `elicitation/create`. Sampling and logging are deprecated as of protocol version `2026-07-28`; go to the LLM provider directly, and log to stderr or OpenTelemetry. Extensions sit beside the core — Tasks, for instance, hands back a durable handle for long work.

## Word of a change

Notifications are opt-in. The client opens a long-lived `subscriptions/listen` stream and names the events it wants. The server acknowledges with the subset it will honor, and every notification on that stream carries the listen request's ID. No response is expected. Delivery is best effort, so keep polling.

## One server, end to end

A weather server.

The client sends `server/discover`. The server replies: `tools` with `listChanged: true`, `resources` with nothing special.

The client sends `tools/list`. Back comes `weather_current`, with a title, a description, and an input schema. The result is complete and may be cached for five minutes.

The client sends `tools/call` with the exact name `weather_current` and arguments `location: "San Francisco"`, `units: "imperial"`. The server returns a `content` array. One object, `"type": "text"`. The model reads it as context.

Then the client opens `subscriptions/listen` with `toolsListChanged: true`. The server acknowledges. Later a forecast tool appears, the notification arrives, and the client calls `tools/list` again.

Discover, list, call, listen. Every other primitive follows the same four beats.
