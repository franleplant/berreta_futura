---
source_ids:
- architecture-overview-ce5cb1d1
content_mode: faithful_synthesis
label: FAITHFUL SYNTHESIS
---

Open Visual Studio Code and point it at two servers, one for Sentry and one for the local filesystem, and its runtime builds two separate client objects, one dedicated connection each. That is the whole shape of the Model Context Protocol: an AI application, the host, holds one client per server, and every server, wherever it runs, answers the same three requests. Discover what it offers. Ask it for something. Listen for when the answer changes. MCP governs that exchange and nothing past it: what the model does with what comes back is the host's business, not the protocol's.

## Primitives

Call `tools/list` first, and a server hands back an array of the tools it exposes, `weather_current` among them, each with a name, a human-readable title, a description, and an input schema, so the client knows before it calls anything what a tool needs and what it does. Call `tools/call` next, naming `weather_current` and passing `location: "San Francisco"` and `units: "imperial"` (metric is what the tool defaults to if you leave that out). Here is the request that goes over the wire:

```
{
    "jsonrpc": "2.0",
    "id": 3,
    "method": "tools/call",
    "params": {
      "name": "weather_current",
      "arguments": {
        "location": "San Francisco",
        "units": "imperial"
      },
      "_meta": {
        "io.modelcontextprotocol/protocolVersion": "2026-07-28",
        "io.modelcontextprotocol/clientInfo": {
          "name": "example-client",
          "version": "1.0.0"
        },
        "io.modelcontextprotocol/clientCapabilities": {
          "elicitation": {}
        }
      }
    }
}
```

`name` has to match the discovery response exactly; `arguments` has to match the tool's own input schema; `_meta` carries the same protocol version and client identity every MCP request carries, discovery or not. The server executes the call and hands back a `content` array. In this example it's plain text, though MCP allows images and other content types too.

The `tools/list` response also carries a `ttlMs` freshness hint, five minutes in this walkthrough, and a `cacheScope` saying who may reuse it, so a client doesn't have to call `tools/list` again before every `tools/call`.

Tools are one of three things a server can expose. Resources and prompts follow the same discovery pattern, `*/list` for the listing and `*/get` for retrieval, but hand back different things: a database schema or a file's contents from a resource, a reusable interaction template, a system prompt or a set of worked examples, from a prompt. A server built around a database can expose all three at once: query tools, a resource holding the schema, and a prompt showing how to use both together.

That's what a server can hand a client. A client can hand a server exactly one thing back: elicitation. A server asks the user a question through `elicitation/create`, when it needs more input or a confirmation before it acts.

Two older client primitives, sampling and logging, were deprecated in protocol version 2026-07-28. Sampling let a server request a completion from the client's own AI application through `sampling/createMessage`, so the server never had to bundle a model SDK of its own; build that today by calling a model provider directly instead. Logging let a server hand debug messages to the client; send those to stderr over stdio today, or through OpenTelemetry.

## Statelessness and discovery

MCP's core protocol, the data layer, is stateless: a server does not remember the last request. Every request carries its own protocol version and capabilities in a `_meta` field (`io.modelcontextprotocol/protocolVersion` and `io.modelcontextprotocol/clientCapabilities`), and a client should put its own name and version there too, in `io.modelcontextprotocol/clientInfo`, unless told not to.

A server that wants to announce what it supports implements `server/discover`; every server must offer it. Its response lists the versions it accepts, the primitives it exposes, and its own identity, in `io.modelcontextprotocol/serverInfo`. A client can cache that response instead of asking again before its next call.

An application does something simple with what it learns here: store it, then gate what it offers the model per server.

```
# Pseudo Code
async with Client(stdio_client(server_config)) as client:
    if client.server_capabilities.tools:
        app.register_mcp_server(client, supports_tools=True)
    app.set_server_ready(client)
```

Calling `server/discover` is optional, though: every request already carries version and capability information. A client can send `tools/call` directly, and if the server rejects it with an `UnsupportedProtocolVersionError`, the client retries with a different version. Discovery is a convenience, not a requirement.

## Notifications

Notifications tell a client something changed, without the client asking. They are opt-in: a client opens a long-lived stream by sending a `subscriptions/listen` request, naming the event types it wants:

```
{
    "jsonrpc": "2.0",
    "id": 4,
    "method": "subscriptions/listen",
    "params": {
      "_meta": {
        "io.modelcontextprotocol/protocolVersion": "2026-07-28",
        "io.modelcontextprotocol/clientInfo": {
          "name": "example-client",
          "version": "1.0.0"
        },
        "io.modelcontextprotocol/clientCapabilities": {
          "elicitation": {}
        }
      },
      "notifications": {
        "toolsListChanged": true
      }
    }
}
```

The server writes back `notifications/subscriptions/acknowledged`, carrying that subscription's own ID and the subset of the request it agreed to honor:

```
{
    "jsonrpc": "2.0",
    "method": "notifications/subscriptions/acknowledged",
    "params": {
      "_meta": {
        "io.modelcontextprotocol/subscriptionId": 4
      },
      "notifications": {
        "toolsListChanged": true
      }
    }
}
```

Every later notification on the stream carries that same ID, in `_meta`, so a client juggling several subscriptions can tell which one just fired. None of them carries its own `id` field, because none expects a reply.

Ask for `toolsListChanged`, and when the server's tools change, it sends `notifications/tools/list_changed` on the stream; the client typically answers by calling `tools/list` again.

None of this is guaranteed. A notification can be lost, particularly across a transport reconnect, so a client that only listens, and never polls, drifts out of date.

## Transport layer

A local server, like that filesystem server, connects over stdio, standard input and output between two processes on the same machine, with no network in between, and usually serves one client. A remote server, like the hosted Sentry server, connects over Streamable HTTP: the client sends HTTP POST requests, and the server can stream replies back over Server-Sent Events. A remote server usually serves many clients at once.

Streamable HTTP carries ordinary HTTP authentication: bearer tokens, API keys, custom headers. MCP recommends OAuth for obtaining those tokens. Either transport carries the same JSON-RPC 2.0 message format underneath; that is the transport layer's only job, moving the same protocol across a different kind of wire.

Run the whole sequence once and the pattern holds: discover what's on offer, list the tools, call `weather_current` with a location and a unit system, then go quiet until told something changed. MCP's job ends at the reply. What the model does with that reply, and whether it trusts a tool list cached five minutes ago, are left to the host it was built to serve.
