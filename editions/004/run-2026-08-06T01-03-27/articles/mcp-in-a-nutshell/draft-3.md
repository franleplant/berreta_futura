---
source_ids:
- architecture-overview-ce5cb1d1
content_mode: faithful_synthesis
label: FAITHFUL SYNTHESIS
---

Visual Studio Code connects to a Sentry server, then to a local filesystem server. Its runtime creates one MCP client for each connection, and each client keeps its own dedicated channel. The arrangement answers the first practical question about MCP: where does an AI application get context, and who carries it there?

## Three participants, two places

The host is the AI application, such as Claude Code, Claude Desktop, or Visual Studio Code. It coordinates clients, each of which maintains one server connection and obtains context for the host. The server is the program providing that context. In the example, one client connects to Sentry and another to the filesystem.

A server may run beside the host or across a network. Local servers commonly use standard input and output to communicate with one client on the same machine; remote servers use Streamable HTTP and may serve many clients. “Local” and “remote” describe where the program runs, not a different kind of server.

MCP focuses solely on the protocol for context exchange. It does not decide how an AI application uses a language model or manages the context it receives. The application remains responsible for the model and the conversation around it.

## The inner and outer layers

MCP has a data layer and a transport layer. The data layer uses JSON-RPC 2.0 to define message structure and meaning. Clients and servers send requests and responses; notifications carry updates when no response is needed.

The transport layer handles connection setup, message framing, and authentication. Stdio provides direct process communication without network overhead. Streamable HTTP uses HTTP POST for client-to-server messages and can add Server-Sent Events for streaming. It supports bearer tokens, API keys, and custom headers; MCP recommends OAuth for obtaining tokens. The same JSON-RPC messages can travel over either transport.

The transport layer abstracts communication details from the protocol layer, enabling the same JSON-RPC 2.0 message format across all transport mechanisms.

MCP is a stateless protocol. Every request carries its protocol version and relevant capabilities in `_meta`, and clients normally identify themselves there as well. A server can therefore process each request without depending on connection state. Before sending other requests, a client may call the mandatory `server/discover` method to learn the server’s supported versions, capabilities, and identity. The response can usually be cached. Discovery is convenient, but a client may also send another request first and handle a version error if necessary.

## What a server can offer

A database server makes the primitives easier to see. It might expose a query tool, a resource containing the database schema, and a prompt with examples for using that tool. Tools perform actions such as file operations, API calls, or database queries. Resources provide data such as file contents, database records, or API responses. Prompts provide reusable interaction templates.

Clients discover these offerings through `tools/list`, `resources/list`, and `prompts/list`. They retrieve a resource with `resources/read` or a prompt with `prompts/get`, and execute a tool with `tools/call`. The listings can change over time, so discovery is a live part of the connection rather than a fixed catalogue.

A client can expose a primitive of its own: elicitation. Through `elicitation/create`, a server may request additional information from a user or ask for confirmation before an action. Sampling and logging, once defined as client primitives, are deprecated as of protocol version 2026-07-28. New implementations should call language-model providers directly for sampling and use standard error output or OpenTelemetry for logging. Optional extensions can add further behavior; the Tasks extension, for example, lets a server return a durable handle for a long-running request that the client can poll.

## From discovery to action

Suppose a server advertises a `weather_current` tool. The client sends `tools/list`; the response includes the tool’s exact name, a human-readable title, a description, and an input schema that states which arguments are required and how to validate them. The client can cache that list according to the server’s freshness and reuse hints.

When the model decides to check the weather, the host routes the call through the client that owns the tool. The request names `weather_current` exactly and supplies arguments such as a location and units. The server returns a content array, which may contain text, images, resources, or other formats. The host adds that result to the conversation so the model can use current information and act outside its original context.

An application connected to many servers can combine their discovered tools into one registry for the model, or discover them progressively instead of loading every tool at once. Each client still keeps its server-specific boundary.

## Staying current

The protocol supports real-time notifications so clients can learn about changes without polling constantly. A client opts in with `subscriptions/listen`, opening a long-lived stream and naming changes such as tool-list updates. The server replies with `notifications/subscriptions/acknowledged`, then emits `notifications/tools/list_changed` when its tools change. That message has no request identifier because it expects no response, and it carries the subscription identifier so the client can match it to the right stream.

After receiving a change notice, the client normally sends `tools/list` again and updates the host’s registry. Notifications are best effort, especially across reconnects, so clients should still poll when they need to preserve freshness.

For a client, the protocol becomes a repeatable loop: learn what a server supports, discover its primitives, call the operation the model selects, and refresh the available list when it changes. Adding a server then changes the model’s available context and actions while the host keeps the same message vocabulary.
