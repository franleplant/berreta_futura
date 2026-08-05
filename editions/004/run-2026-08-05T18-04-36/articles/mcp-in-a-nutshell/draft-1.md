---
source_ids:
- architecture-overview-ce5cb1d1
content_mode: faithful_synthesis
label: FAITHFUL SYNTHESIS
---

Visual Studio Code connects to a Sentry server. Its runtime creates one MCP client for that connection. When it connects to a filesystem server, it creates another client. The application is the host; each client keeps one dedicated connection to its server.

MCP defines the protocol for exchanging context. It does not decide how an AI application uses a language model or manages that context. The host coordinates the clients. A server provides context. The client obtains that context for the host. Servers may run on the same machine or on another platform. Local servers commonly use standard input and output. Remote servers commonly use Streamable HTTP, which supports ordinary HTTP authentication such as bearer tokens and API keys. MCP recommends OAuth for obtaining authentication tokens.

The protocol has two layers. The data layer defines the messages and their meaning. The transport layer establishes connections, frames messages, and handles authentication. Both transports carry the same JSON-RPC 2.0 messages, so the protocol does not change when a server moves from a local process to a remote service.

Every request carries the protocol version and the capabilities relevant to that request in its _meta field, so the server can process each request on its own. Clients should also identify themselves there unless configured not to. A client may call `server/discover` before anything else. That request lets the server report its supported versions, capabilities, and identity. The response is usually cacheable. Discovery is optional because each later request carries the same information; a client can send another request and handle an unsupported-version error if one returns.

The useful part of the data layer is its primitives. Servers can expose tools, resources, and prompts. A tool is an executable function, such as a file operation, API call, or database query. A resource supplies context, such as file contents, database records, or an API response. A prompt is a reusable interaction template. Clients find these through methods such as `tools/list`, `resources/list`, and `prompts/list`, then retrieve or execute them with the matching methods. The lists can change over time.

Imagine a database server. It can expose a tool for querying the database, a resource containing the schema, and a prompt with examples of how to use the tool. The client first discovers the tools. Each tool includes a unique name, a description, and an input schema. The language model can then see the available actions and choose one. The client sends `tools/call` with the exact discovered name and the required arguments. The server returns a content array that may contain text, images, resources, or other supported forms. The application places that result back into the conversation.

Clients can expose a primitive too. Elicitation lets a server request more information from a user or ask for confirmation through `elicitation/create`. Sampling and logging are deprecated as of protocol version 2026-07-28. New implementations should call language-model providers directly for sampling, and should write logs to standard error or use OpenTelemetry.

Servers can also report changes. A client opts in by opening a long-lived `subscriptions/listen` stream and naming the notification types it wants. If the server’s tool list changes, it can send `notifications/tools/list_changed`; the message has no response ID because JSON-RPC notifications do not expect a response. The client usually requests `tools/list` again and refreshes the capabilities available to the model. Notifications are best effort, especially across reconnects, so clients should still poll when freshness matters.

That is the shape of MCP: one host, one client per server, a stable message layer carried by different transports, and primitives that let servers offer actions and context. The model can then use what the application has discovered, while the application keeps the connections and boundaries visible.
