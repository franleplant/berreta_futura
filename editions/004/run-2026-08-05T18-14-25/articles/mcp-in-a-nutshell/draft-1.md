---
source_ids:
- architecture-overview-ce5cb1d1
content_mode: faithful_synthesis
label: FAITHFUL SYNTHESIS
---

Visual Studio Code is an MCP host. When it connects to the Sentry MCP server, its runtime creates an MCP client for that connection. When it connects to a local filesystem server, it creates another client. Each client keeps a dedicated connection to its server. The host coordinates them, while the servers provide context.

MCP calls the host the AI application, the client the component that maintains one server connection, and the server the program that provides context. A server may run on the same machine or somewhere else. Claude Desktop can launch a filesystem server through STDIO. The official Sentry MCP server runs on the Sentry platform, and uses the Streamable HTTP transport.

MCP covers context exchange only. It does not dictate how an AI application uses an LLM or manages the context it receives. Its architecture has two layers. The data layer defines the JSON-RPC 2.0 messages, version and capability discovery, and the primitives that clients and servers offer. The transport layer establishes connections, frames messages, and handles authorization. The same JSON-RPC format can travel over either transport.

STDIO connects local processes through standard input and output. It avoids network overhead. Streamable HTTP sends client-to-server messages with HTTP POST and can use Server-Sent Events for streaming. It supports bearer tokens, API keys, and custom headers. MCP recommends OAuth for obtaining authentication tokens.

The data layer is where an application learns what a server can do. MCP is stateless. Every request carries the protocol version and relevant capabilities in its `_meta` field. Clients should also identify themselves there unless configured not to. A client may send the mandatory `server/discover` request before other requests to learn a server’s supported versions, capabilities, and identity. The response is typically cacheable.

Calling server/discover is optional. Because every request carries the same _meta fields, a client is free to send any request directly and handle a version error if one comes back.

Servers expose three core primitives. Tools are executable functions for actions such as file operations, API calls, and database queries. Resources provide context such as file contents, database records, and API responses. Prompts are reusable interaction templates, including system prompts and few-shot examples. Each primitive type has associated methods for discovery ( */list ), retrieval ( */get ), and in some cases, execution ( tools/call ). Listings can change over time, so a client can discover tools when it needs them instead of loading every tool at startup.

A database server might expose a query tool, a resource containing the database schema, and a prompt with examples of using those tools. A client first calls `tools/list`, then calls `tools/call` with the exact discovered name and the arguments required by its input schema. The server returns content objects, which may contain text, images, resources, or other supported forms. The AI application passes that result back to the language model as context.

Clients can expose elicitation. A server uses `elicitation/create` to request more information or confirmation from a user. Sampling, which let servers request model completions from the client, and logging are deprecated as of protocol version 2026-07-28. New implementations should call provider APIs directly for model access and use stderr or OpenTelemetry for logs. Optional extensions can add further behavior. The Tasks extension, for example, gives a long-running request a durable handle that clients can poll.

MCP also supports notifications. A client opens a long-lived `subscriptions/listen` stream and names the changes it wants, such as tool-list updates. A server sends a notification when its tools change. The message has no response ID, and the server sends it only when the client opted in and the server declared support. Notifications are best effort, especially across reconnects, so clients should still poll when freshness matters.

That is the working shape: one host, one client per server, a stateless JSON-RPC exchange, and primitives that let an application discover context and actions before it uses them.
