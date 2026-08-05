---
source_ids:
- architecture-overview-ce5cb1d1
content_mode: faithful_synthesis
label: FAITHFUL SYNTHESIS
---

MCP is a protocol for exchanging context between an AI application and programs that provide data or actions. It defines the connection and the messages, not how an application uses a language model or manages the context it receives.

MCP follows a client-server architecture where an MCP host — an AI application like Claude Code or Claude Desktop — establishes connections to one or more MCP servers. The host creates one MCP client for each server, and each client keeps its own connection. Visual Studio Code might connect to a Sentry server and a local filesystem server, creating separate client objects for each. A server is called local or remote according to where it runs and how it connects: a filesystem process using standard input and output usually runs on the same machine, while Sentry’s server uses Streamable HTTP from the Sentry platform. Local servers typically serve one client; remote servers may serve many.

The architecture has two layers. The data layer defines the JSON-RPC 2.0 messages, version and capability discovery, and the things clients and servers can offer. The transport layer handles connection setup, message framing, authentication, and the channel itself. MCP supports standard input and output for direct local process communication, and Streamable HTTP for remote communication, with HTTP authentication and optional Server-Sent Events. The same JSON-RPC message format works over either transport.

MCP uses JSON-RPC 2.0 as its underlying RPC protocol. Clients and servers send requests and responses, while notifications carry updates that need no reply. Every request includes protocol metadata in its `_meta` field, including the version and the client’s capabilities. Clients normally identify themselves there as well. A server must implement `server/discover`, which advertises its supported versions, capabilities, and identity. A client can call it before anything else, cache the result, and avoid attempting operations the server cannot handle. Discovery is optional because each request carries enough metadata for the server to process it independently and reject an unsupported version.

MCP primitives are the most important concept within MCP. Servers can expose tools, resources, and prompts. Tools are executable functions for actions such as file operations, API calls, or database queries. Resources provide contextual data such as file contents, records, or API responses. Prompts are reusable templates for structuring interactions with a language model. Each kind has methods for discovering what exists, such as `tools/list`, and retrieving or executing it, such as `resources/read` and `tools/call`. Listings may change over time, so a client can discover tools first and then call one using the exact name and arguments described by its schema.

A database server, for example, might expose a query tool, a resource containing the database schema, and a prompt with examples of how to use the tool. The application gathers these offerings from its connected servers into a tool registry the language model can use. When the model chooses a tool, the application routes the call to the matching client, sends it to the server, and returns the server’s result as conversation context. Tool responses can contain several content types, including text, images, and other resources.

Clients can expose primitives too. Elicitation lets a server ask the user for more information or confirmation through `elicitation/create`. Sampling and logging are deprecated as of protocol version 2026-07-28. New implementations should call language-model providers directly for completions, and should send logs to standard error or OpenTelemetry.

The protocol also supports optional extensions. Tasks, for instance, let a server return a durable handle for a long-running request so the client can poll for its status and retrieve the result later.

The protocol supports real-time notifications to enable dynamic updates between servers and clients. These updates are opt-in. A client opens a long-lived `subscriptions/listen` stream and names the events it wants, such as changes to the tool list. When a server reports that tools were added, modified, or temporarily unavailable, the client can request `tools/list` again and refresh the registry. Notifications have no response and are best effort, especially across reconnects, so clients should still poll when freshness matters.

That is the shape of MCP: a host coordinates dedicated clients, transports carry the messages, discovery reveals what each server can do, primitives provide the useful surface, and notifications keep that surface from going stale.
