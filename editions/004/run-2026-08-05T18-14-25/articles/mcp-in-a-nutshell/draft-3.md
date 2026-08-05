---
source_ids:
- architecture-overview-ce5cb1d1
content_mode: faithful_synthesis
label: FAITHFUL SYNTHESIS
---

Visual Studio Code is an MCP host. When it connects to the Sentry MCP server, its runtime creates one MCP client for that connection. When it connects to a local filesystem server, it creates another. Each client keeps a dedicated connection to its server. The host coordinates them; the servers provide context. This separation gives an application a simple working path: connect, discover what each server supports, invoke the right primitive, and refresh when the server changes.

MCP calls the host the AI application, the client the component that maintains one server connection, and the server the program that provides context. A server may run on the same machine or somewhere else. Claude Desktop can launch a filesystem server through STDIO. The official Sentry MCP server runs on the Sentry platform through Streamable HTTP.

The transport decides how those connections move. STDIO links local processes through standard input and output, with no network overhead. Streamable HTTP sends client-to-server messages with HTTP POST and can use Server-Sent Events for streaming. It supports bearer tokens, API keys, and custom headers. MCP recommends OAuth for obtaining authentication tokens. Both transports carry the same JSON-RPC 2.0 message format.

With those connections in place, the client and server exchange JSON-RPC messages. MCP is a stateless protocol. Every request carries the protocol version and relevant capabilities in its `_meta` field. Clients should also include `io.modelcontextprotocol/clientInfo` there unless configured not to. Because each request carries this information, a server can process it on its own. Every server must implement `server/discover`, but calling it before another request is optional.

A client that does call `server/discover` sends `io.modelcontextprotocol/protocolVersion`, its identity, and `io.modelcontextprotocol/clientCapabilities`. The response returns the server’s supported versions, capabilities, and identity. If the requested version is unsupported, the server returns an `UnsupportedProtocolVersionError` listing the versions it accepts. The client can retry with a mutually supported version. Discovery responses are typically cacheable, so an application can store the result instead of repeating the exchange for every request. Because the same metadata travels with each request, a client may also send another request directly and handle a version error if one comes back.

Once the client knows what a server offers, it can inspect the primitives. A tool performs an action such as a file operation, API call, or database query. A resource supplies context such as file contents, database records, or API responses. A prompt provides a reusable interaction template, including system prompts and few-shot examples. The parallel definitions matter less than the boundary: the server exposes capabilities, and the client decides when to use them.

Each primitive type has discovery methods such as `*/list`, retrieval methods such as `*/get`, and, where applicable, execution through `tools/call`. A database server could expose a query tool, a resource containing the database schema, and a prompt with examples of using those tools.

The client begins with `tools/list`. The response can be paginated with a cursor and returns tool metadata including `name`, `title`, `description`, and `inputSchema`. The name is the identifier used for execution. The schema defines the required and optional arguments. A response may also include `resultType`, `ttlMs`, and `cacheScope`, which tell the client whether the listing is complete and how long, and for whom, it may be reused. Clients that federate many servers can use progressive discovery instead of loading every tool at startup.

The client then sends `tools/call` with the exact discovered name and arguments that match the schema. The request still carries the protocol version, client capabilities, and normally client identity in `_meta`. The server returns a `content` array. Its entries may contain text, images, resources, or other supported forms. The AI application passes that result back to the language model as context.

Clients can expose one primitive of their own. Through `elicitation/create`, a server can ask the user for more information or request confirmation before an action. Sampling, which lets servers request model completions from the client, and logging are deprecated as of protocol version 2026-07-28. New implementations should call provider APIs directly for model access and use stderr or OpenTelemetry for logs. Optional extensions can add further behavior. The Tasks extension, for example, gives a long-running request a durable handle that clients can poll.

A server can change its tools while a conversation is running. To hear about those changes, the client opens a long-lived `subscriptions/listen` stream and asks for the event types it wants, such as `toolsListChanged`. The server acknowledges the subscription with `notifications/subscriptions/acknowledged` and places the subscription ID in `_meta`. Later it can send `notifications/tools/list_changed`, again tagged with that ID. The notification has no response ID because it is a JSON-RPC notification.

The client then calls `tools/list` again and refreshes its registry. This exchange is opt-in. The server must declare support, and the client must request it. Delivery is best effort, especially across reconnects, so clients should still poll when freshness matters.

The model can reach tools and context through MCP, but the application remains the gatekeeper. It chooses the server, sends the call, and decides how a change enters the conversation.
