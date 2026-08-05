---
source_ids:
- architecture-overview-ce5cb1d1
content_mode: faithful_synthesis
label: FAITHFUL SYNTHESIS
---

Visual Studio Code connects to a Sentry server. Its runtime creates one MCP client for that connection. When it connects to a filesystem server, it creates another client. The application is the host; each client keeps one dedicated connection to its server.

MCP gives those connections a shared language for exchanging context. The host coordinates clients. A server provides context. A client obtains it for the host. Servers may run locally through standard input and output, or remotely through Streamable HTTP. Remote messages use HTTP POST, with optional Server-Sent Events for streaming. The transport supports bearer tokens, API keys, and custom headers. MCP recommends OAuth for obtaining authentication tokens.

The protocol has two layers. The data layer defines JSON-RPC 2.0 messages and their meaning. JSON-RPC is a request-and-response format with an identifier that lets each side match replies to requests. The transport layer establishes connections, frames messages, and handles authentication. Both transports carry the same messages, so moving a server from a local process to a remote service does not change the data exchange.

Start with discovery. Every request carries the protocol version and relevant capabilities in its `_meta` field. Clients should also identify themselves there unless configured not to. A client may send `server/discover` before any other request. The server responds with its supported versions, `serverCapabilities`, and `serverInfo`. If the requested version is unsupported, the server returns `UnsupportedProtocolVersionError` with the versions it accepts. The client retries with a mutually supported version. Discovery is optional because later requests carry the same metadata, and the response is usually cacheable.

The useful part of the data layer is its primitives. Servers expose tools, resources, and prompts. Tools let an AI application perform actions such as file operations, API calls, or database queries. Resources provide context such as file contents, database records, or API responses. Prompts provide reusable interaction templates. Each primitive type has associated methods for discovery ( */list ), retrieval ( */get ), and in some cases, execution ( tools/call ).

A client discovers tools with `tools/list`, resources with `resources/list`, and prompts with `prompts/list`. Resource contents arrive through `resources/read`; the corresponding `*/get` methods apply where defined. A tool entry includes a unique `name`, a human-readable `title`, a `description`, and an `inputSchema` written as JSON Schema. The schema tells the client which arguments are required and what types they have. Lists can change, and `tools/list` accepts an optional cursor for pagination.

Imagine a database server. It exposes a tool for querying the database, a resource containing the database schema, and a prompt with examples of how to use the tool. The client lists the tools, gives their descriptions and schemas to the language model, then routes the model's chosen action to the server. The client sends `tools/call` with the exact discovered name and its arguments. The server returns a `content` array. Each item has a type, such as `text`, and the array can contain text, images, resources, or other supported forms.

The source's concrete request shows the envelope. It uses JSON-RPC version `2.0`, request ID `3`, method `tools/call`, and parameters containing `"name": "weather_current"` and `"arguments": {"location": "San Francisco", "units": "imperial"}`, alongside the standard `_meta` fields. This is a weather example, not a second database design. Its point is operational: the name must match the discovery response, and the arguments must match the declared schema. The application places the returned content back into the conversation.

Clients can expose a primitive too. Elicitation lets a server request more information from a user or ask for confirmation through `elicitation/create`. Sampling and logging are deprecated as of protocol version 2026-07-28. New implementations should call language-model providers directly for sampling and should write logs to standard error or use OpenTelemetry.

A server can also report changes. The client opts in by opening a long-lived `subscriptions/listen` stream with a filter such as `"notifications": {"toolsListChanged": true}`. The server acknowledges it with `notifications/subscriptions/acknowledged`. When the tool list changes, the server may send `notifications/tools/list_changed` with the subscription ID in `_meta`. That message has no response ID because JSON-RPC notifications do not expect a response.

After receiving the notification, the client sends `tools/list` again and replaces the server's entries in its tool registry. If the conversation is active, the application tells the language model that its available capabilities changed. Notifications are best effort, especially across reconnects, so clients should still poll when freshness matters.

This workflow gives an application a stable way to connect, discover, call, and refresh. When a server misbehaves, you can inspect the same things in order: the transport channel, the request metadata, the discovered capability, and the arguments sent to the named tool.
