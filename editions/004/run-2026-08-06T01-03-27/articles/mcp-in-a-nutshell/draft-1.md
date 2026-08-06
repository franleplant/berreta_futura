---
source_ids:
- architecture-overview-ce5cb1d1
content_mode: faithful_synthesis
label: FAITHFUL SYNTHESIS
---

Visual Studio Code connects to a Sentry server, then to a local filesystem server. Its runtime creates one MCP client for each connection, and each client keeps its own dedicated channel. The arrangement looks modest, but it answers the first practical question about MCP: where does an AI application get context, and who carries it there?

## Three participants, two places

The host is the AI application, such as Claude Code, Claude Desktop, or Visual Studio Code. It coordinates one or more clients. Each client maintains a connection to one server and obtains context for the host to use. The server is the program that provides that context.

A server may run beside the host or across a network. A local server commonly uses standard input and output to communicate with one client on the same machine. A remote server uses Streamable HTTP and may serve many clients. “Local” and “remote” describe where the program runs, not a different kind of server.

MCP defines the protocol for exchanging context. It does not decide how an AI application uses a language model or manages the context it receives. That boundary matters: MCP supplies a common channel, while the application remains responsible for the model and the conversation around it.

## The inner and outer layers

MCP has a data layer and a transport layer. The data layer uses JSON-RPC 2.0 to define message structure and meaning. Clients and servers send requests and responses; notifications carry updates when no response is needed.

The transport layer handles connection setup, message framing, and authentication. Stdio provides direct process communication without network overhead. Streamable HTTP uses HTTP POST for client-to-server messages and can add Server-Sent Events for streaming. It supports ordinary HTTP authentication methods, including bearer tokens, API keys, and custom headers; MCP recommends OAuth for obtaining tokens. The same JSON-RPC messages can travel over either transport.

MCP is a stateless protocol. Every request carries its protocol version and relevant capabilities in `_meta`, and clients normally identify themselves there as well. A server can therefore process each request without depending on connection state. Before sending other requests, a client may call the mandatory `server/discover` method to learn the server's supported versions, capabilities, and identity. The response can usually be cached. Discovery is convenient, but the per-request metadata means a client may also send another request first and handle a version error if necessary.

## What a server can offer

The main building blocks are tools, resources, and prompts. Tools are executable functions, such as file operations, API calls, or database queries. Resources provide contextual data, such as file contents, database records, or API responses. Prompts are reusable templates for structuring interactions with a language model.

Each kind has methods for listing and retrieving what is available, and tools can also be called. A database server might expose a query tool, a resource containing the database schema, and a prompt with examples of how to use the tool. Clients first discover the available items, then choose among them. This design allows listings to be dynamic.

A client can also expose a primitive of its own: elicitation. A server may use it to request additional information from a user or ask for confirmation before an action. Sampling and logging, once defined as client primitives, are deprecated as of protocol version 2026-07-28. New implementations should call language-model providers directly for sampling and use standard error output or OpenTelemetry for logging. Optional extensions can add further behavior; the Tasks extension, for example, lets a server return a durable handle for a long-running request that the client can poll.

## From discovery to action

Suppose a server advertises a `weather_current` tool. The client first asks for the tool list. The response includes the tool's exact name, a human-readable title, a description, and an input schema that states which arguments are required and how to validate them. The client can cache that list according to the server's freshness and reuse hints.

When the model decides to check the weather, the host routes the call through the client that owns the tool. The request names `weather_current` exactly and supplies arguments such as a location and units. The server returns a content array, which may contain text, images, resources, or other formats. The host adds that result to the conversation so the model can use current information and act outside its original context.

The same pattern works when an application connects to many servers. It can combine their discovered tools into one registry for the model, or discover them progressively instead of loading every tool at once. The separate client per server keeps each connection's boundary visible while the host presents a unified set of capabilities.

## Staying current

The protocol supports real-time notifications to enable dynamic updates between servers and clients. A client opts in by opening a long-lived subscription and naming the changes it wants, such as tool-list updates. The server acknowledges the subscription, then sends a notification when its tools change. That message has no request identifier because it expects no response, and it carries the subscription identifier so the client can match it to the right stream.

After receiving a change notice, the client normally requests the tool list again and updates the host's registry. Notifications are best effort, especially across reconnects, so clients should still poll when they need to preserve freshness. The result is a working loop: discover what a server can do, call the right operation, and refresh the picture when that offer changes.

MCP's shape is therefore small enough to share and explicit enough to inspect. The host chooses how to use a model, the client holds a server-specific connection, and the server supplies tools, data, or interaction templates through messages that carry their own context.
