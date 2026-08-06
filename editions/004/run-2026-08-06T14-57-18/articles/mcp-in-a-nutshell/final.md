---
source_ids:
- architecture-overview-ce5cb1d1
content_mode: in_a_nutshell
label: IN A NUTSHELL
---

# MCP in a Nutshell

## The 30-Second Version

An AI application needs things it does not have: your files, your database, your error logs. MCP is the protocol it speaks to get them.

One host (the AI application) opens one client per server. Each server offers three things: **tools** it can run, **resources** it can read, **prompts** it can reuse. The client asks what exists, then asks for what it wants. Messages are JSON-RPC 2.0, over stdio for local servers or Streamable HTTP for remote ones.

MCP carries context. It says nothing about what the model does with it.

## The Shape of It

Two layers. The data layer defines the messages — discovery, the primitives, notifications. The transport layer moves them. The data layer sits inside; transport wraps it. The same messages travel either transport unchanged.

The protocol is stateless. Every request carries its own protocol version and capabilities in `_meta`, and usually the client's identity too. Nothing is remembered between requests, so nothing is lost when a connection drops.

Discovery is one mandatory request, `server/discover`. The server answers with its identity, its capabilities, the versions it accepts. The answer is cacheable. It is also optional — since every request declares its own version, a client may simply ask for what it wants and handle a version error if one comes back.

## One Example, Followed Through

A weather server. Watch a client use it.

**It asks what exists.** `tools/list`. Back comes an array. One tool named `weather_current`, with a title, a description, and an `inputSchema` — JSON Schema, so the client knows `location` is required and `units` is not. The response says how long it may be cached and who may reuse it.

**It calls the tool.** `tools/call`, with the exact name from the listing and arguments matching the schema: `location` San Francisco, `units` imperial. The reply is a `content` array of typed objects — here, text. Text now, images or resources elsewhere.

**It subscribes to change.** Notifications are opt-in. The client opens a long-lived stream with `subscriptions/listen`, naming what it wants: `toolsListChanged`. The server acknowledges, echoing back only the filters it agreed to honor. Later, when the tool list changes, `notifications/tools/list_changed` arrives on that stream, tagged with the subscription's ID. No `id` field, no response expected. The client asks `tools/list` again and learns what changed.

That is the whole cycle: discover, call, subscribe, refresh. Everything else is more of the same.

## What Clients Offer Back

Servers can ask the client for things too. **Elicitation** — `elicitation/create` — requests information or confirmation from the user.

Sampling and logging are deprecated as of protocol version 2026-07-28. New implementations call LLM providers directly and log to stderr or OpenTelemetry.

## The Grain of the Design

Listings are dynamic, so tools may appear and vanish. Notifications are best effort — across a reconnect, one may never arrive, so a careful client polls as well. Nothing is assumed: capabilities are declared, so unsupported operations are never attempted.

Extensions build on the core without changing it. The Tasks extension returns a durable handle for a long-running request; the client polls, then collects the result.

A database server, told concretely: tools to query it, a resource holding the schema, a prompt with few-shot examples for using the tools. The primitives are that small, and that is the point.
