---
source_ids:
- architecture-overview-ce5cb1d1
content_mode: faithful_synthesis
label: FAITHFUL SYNTHESIS
---

An AI application becomes more useful when it can reach tools and data outside its own model. The Model Context Protocol (MCP) defines the boundary for that exchange. It specifies how an AI application connects to programs that provide context, how both sides describe what they support, and how requests and results move between them. It does not dictate how an application uses a language model or manages the context it receives.

## One host, several dedicated connections

MCP follows a client-server architecture where an MCP host, an AI application like Claude Code or Claude Desktop, establishes connections to one or more MCP servers. The host creates one MCP client for each server, and each client maintains its own connection.

A server can run beside the application or somewhere else. MCP servers can execute locally or remotely. A local server commonly uses the STDIO transport, which connects two processes through standard input and output. A remote server uses Streamable HTTP and can serve many clients. Visual Studio Code, for example, might connect to a local filesystem server and a remote Sentry server. Its runtime creates a separate client for each connection, so the two servers remain distinct even though the model sees their capabilities together.

The architecture has two layers. The data layer defines the JSON-RPC message structure and the things clients and servers can offer. The transport layer handles connection setup, message framing, and authentication. The data layer is the inner layer, while the transport layer is the outer layer. Because transport details stay outside the protocol messages, the same JSON-RPC 2.0 exchange can travel over either STDIO or HTTP. Streamable HTTP supports standard authentication methods such as bearer tokens, API keys, and custom headers; MCP recommends OAuth for obtaining authentication tokens.

## The primitives are the useful part

The data layer is where MCP defines what context can cross the boundary. Every request carries the protocol version and relevant capabilities in its `_meta` field, and clients normally identify themselves there as well. Servers advertise their supported versions and capabilities through the mandatory `server/discover` request. A client may call discovery first, or send another request and handle a version error if the server does not support the requested version.

The central primitives are tools, resources, and prompts. Tools are executable functions, such as file operations, API calls, or database queries. Resources provide contextual data, such as file contents, database records, or API responses. Prompts are reusable templates that structure interactions with language models. Clients discover these primitives with methods such as `tools/list` and then retrieve or execute them with methods such as `resources/read` and `tools/call`.

Consider a server that exposes a database. It might offer a tool for querying the database, a resource containing the schema, and a prompt with examples of how to use the query tool. The client can list what exists, present the available tools to the model, and invoke the selected tool with arguments that match its input schema. The server returns content objects, which may contain text, images, resources, or other supported forms. The application adds that result to the conversation so the model can use it.

MCP also supports richer interactions in the other direction. Elicitation lets a server ask the user for more information or confirmation through `elicitation/create`. Sampling and logging are deprecated as of protocol version `2026-07-28`; new implementations should call language-model provider APIs directly and send logs to stderr for STDIO or use OpenTelemetry. Optional extensions can add further behavior. The Tasks extension, for example, lets a server return a durable handle for a long-running request so the client can poll for its status and retrieve the result later.

## Requests do not depend on a remembered connection

MCP is a stateless protocol. Each request carries the information the server needs to process it, including the version and capabilities relevant to that request. This makes discovery useful for compatibility, but it does not make a session state the foundation of every call.

The protocol supports real-time notifications to enable dynamic updates between servers and clients. A client opts in by opening a long-lived `subscriptions/listen` stream and naming the changes it wants, such as a changed tool list. When the server reports that tools were added, modified, or temporarily unavailable, the client can request `tools/list` again and refresh the registry it has given the model.

Notifications have no response ID because they are JSON-RPC notifications. They are best effort, especially across transport reconnects, so clients should still poll when freshness matters. This creates a refresh cycle that keeps the client’s understanding of available tools current. The application can then expose the changed capabilities to an ongoing conversation without rebuilding the connection or guessing what the server now supports.

MCP’s boundary is simple: one host coordinates clients, clients connect to servers, and the data layer gives both sides a shared vocabulary for discovery, context, action, and change. The model remains inside the application. The tools and data remain where their servers provide them. The protocol is the part that lets them meet.
