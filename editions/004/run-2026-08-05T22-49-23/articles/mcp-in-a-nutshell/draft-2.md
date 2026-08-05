---
source_ids:
- architecture-overview-ce5cb1d1
content_mode: faithful_synthesis
label: FAITHFUL SYNTHESIS
---

MCP lets an AI application reach tools and data through a shared protocol. The useful picture is a set of separate programs connected by deliberate seams.

An MCP host is the application, such as Visual Studio Code, Claude Code, or Claude Desktop. It creates one MCP client for each MCP server, and each client keeps its own connection. In Visual Studio Code, a connection to Sentry creates one client; a connection to a local filesystem server creates another. The servers may live on the same machine or elsewhere. A local server commonly uses standard input and output, while a remote server commonly uses Streamable HTTP. “Local” describes where the program runs, not a different kind of server.

MCP has two layers. The data layer defines JSON-RPC 2.0, a format in which one side sends a named request and the other returns a response. The transport layer handles how those messages connect, travel, and get authenticated. Stdio sends messages between local processes without network overhead. Streamable HTTP sends them with HTTP POST and can stream results through Server-Sent Events. It supports bearer tokens, API keys, and custom headers; MCP recommends OAuth for obtaining tokens. The same JSON-RPC messages work over either transport.

MCP is a stateless protocol. Every request carries the protocol version and relevant capabilities in its `_meta` field, usually along with the client’s identity. Every server must implement `server/discover`. A client may call it first to learn the server’s supported versions, capabilities, and identity. If the requested version is unsupported, the server returns an `UnsupportedProtocolVersionError` listing the versions it accepts; the client retries with one they share. The discovery response is typically cacheable. Calling discovery is optional for the client because the same metadata travels with every later request, but the server-side method is required.

Servers expose three core primitives. Tools are executable functions for actions such as file operations, API calls, and database queries. Resources provide context such as file contents, database records, or API responses. Prompts are reusable interaction templates, including system prompts and few-shot examples. Clients discover them with methods such as `tools/list`, retrieve resources with `resources/read`, and execute tools with `tools/call`. Listings can change over time.

A compact exchange makes the shape concrete. A discovery request carries `"method": "server/discover"` and metadata such as `"io.modelcontextprotocol/protocolVersion": "2026-07-28"`, `"clientInfo"`, and `"clientCapabilities"`. The response returns supported versions, server identity, and capabilities such as `"tools": {"listChanged": true}` or `"resources": {}`. A tools/list response describes each tool with a unique `name`, a human-readable `description`, and an `inputSchema` that says which arguments are required.

Suppose the discovered tool is named `weather_current`. The client must use that exact name in a `tools/call` request, with arguments such as `"location": "San Francisco"` and `"units": "imperial"`, plus the same `_meta` fields. The response contains a `content` array. Each item has a type, such as `"text"`, and the AI application can pass that content back to the language model. The model chooses a tool, the application routes the call to the right client, the server executes it, and the result becomes new context.

Servers can ask users for information or confirmation through elicitation. Sampling is deprecated as of protocol version 2026-07-28 . New implementations should call language-model providers directly. Logging is also deprecated; new implementations should log to stderr for stdio transports or use OpenTelemetry. Optional extensions can add other behavior, such as durable handles for long-running tasks.

Notifications let servers report changes without being polled constantly. A client opts in by opening a long-lived `subscriptions/listen` stream with a filter such as `"toolsListChanged": true`. The server acknowledges it with a subscription ID. When its tools change, it sends a `notifications/tools/list_changed` message carrying that ID and no request ID. Notifications are sent as JSON-RPC 2.0 notification messages (without expecting a response). Delivery is best effort, especially across reconnects, so clients should still poll when freshness matters. On receiving an update, the client calls `tools/list` again and refreshes what the model can use.

MCP focuses solely on the protocol for context exchange—it does not dictate how AI applications use LLMs or manage the provided context.
