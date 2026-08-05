---
source_ids:
- architecture-overview-ce5cb1d1
content_mode: faithful_synthesis
label: FAITHFUL SYNTHESIS
---

An AI application reaches a database, a filesystem, or a bug tracker through an MCP server, not directly, and the server does the talking to the real thing on its behalf. Visual Studio Code, an MCP host, opens one MCP client just to hold its connection to the Sentry MCP server, and a second, separate client when it also connects to a local filesystem server. A local server, reached over stdio, typically serves the single client that spawned it; a remote server, reached over Streamable HTTP, typically serves many at once, the way Sentry's does.

The design underneath all of it is that a server is never asked to remember a client between requests. Every request carries its own protocol version and its own capabilities in a `_meta` field, and the client's identity goes in the same field unless it has been told to leave it out, so a server can process each request on its own terms. That is why `server/discover`, the call that returns a server's identity, its versions, and its capabilities, is optional rather than a handshake: a client that already knows what it wants can send that request directly and handle an `UnsupportedProtocolVersionError` if the version is wrong, retrying with one the error names. Discovery exists for convenience, and because its answer barely changes, a client can cache it rather than ask again.

```
  {
      "jsonrpc": "2.0",
      "id": 1,
      "method": "server/discover",
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
        }
      }
  }
```

Two layers carry this traffic. The data layer, the inner one, is JSON-RPC 2.0 messages that mean the same thing no matter how they travel. The transport layer, the outer one, exists to make that difference invisible: stdio pipes two local processes together with no network involved, while Streamable HTTP lets a remote client POST to a remote server and get results back over Server-Sent Events, authenticated by a bearer token, an API key, or, as MCP recommends, OAuth.

## Primitives

A server can offer three things. Tools are functions the application can invoke: a query, a write, an API call. Resources are data it can read for context: a schema, a file, a record. Prompts are reusable templates for structuring an interaction, few-shot examples for using the other two together. Every one is discovered before it is used, `tools/list` before `tools/call`, and that list is fetched fresh on every connection rather than fixed in advance, so a server is free to add or drop a tool between one request and the next.

Calling one means using the exact name the list handed back, not a shorter or friendlier version of it. Ask a weather server what it has and it may answer `weather_current`; call anything else and nothing happens, because the server never promised a `calculate`-shaped shortcut existed. Retrieving a resource, rather than running a tool, is `*/get`.

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

Two primitives run from server to client instead of the other way. Elicitation lets a server ask the user directly for more input or confirmation, through `elicitation/create`. Sampling, which lets a server ask the client's own AI application for a model completion so the server doesn't have to embed an LLM SDK of its own, is deprecated as of protocol version 2026-07-28; the guidance now is to call a model provider's API directly. Logging is deprecated the same date, and its replacement is stderr on stdio or OpenTelemetry, not a message sent back to the client.

## Notifications

Everywhere else, a request is self-contained. Notifications are not. To receive them, a client opens `subscriptions/listen`, naming the event types it wants, and the server has to hold that connection open and remember which subscription asked for what, exactly the bookkeeping the `_meta` field exists to avoid elsewhere. The server acknowledges with a subscription ID, and every notification on that stream afterward carries the same ID in its own `_meta`, so a client juggling several subscriptions can tell which one a given message answers.

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

```
  {
      "jsonrpc": "2.0",
      "method": "notifications/tools/list_changed",
      "params": {
        "_meta": {
          "io.modelcontextprotocol/subscriptionId": 4
        }
      }
  }
```

That bookkeeping is also why notifications carry no promise. The specification calls delivery best effort: a message can go missing, particularly across a reconnect, because reconnecting means rebuilding state a stateless request never had to carry in the first place. A client that only listens and never polls will eventually be wrong about what tools actually exist, so the honest habit is to keep polling anyway and treat a notification as a way to shorten the wait.

MCP focuses solely on the protocol for context exchange: it does not dictate how an AI application uses a model or manages the context that model receives. A server that remembers nothing between requests can be swapped, restarted, or load-balanced without anyone noticing, right up until the one channel that has to remember something anyway. There, the protocol simply asks the client to keep polling.
