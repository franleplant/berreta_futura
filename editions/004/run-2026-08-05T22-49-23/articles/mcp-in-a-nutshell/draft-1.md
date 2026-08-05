---
source_ids:
- architecture-overview-ce5cb1d1
content_mode: faithful_synthesis
label: FAITHFUL SYNTHESIS
---

MCP lets an AI application reach tools and data through a shared protocol. The useful picture is a set of separate programs connected by deliberate seams.

An MCP host is the application, such as Visual Studio Code, Claude Code, or Claude Desktop. It creates one MCP client for each MCP server, and each client keeps its own connection. In Visual Studio Code, a connection to Sentry creates one client; a connection to a local filesystem server creates another. The servers may live on the same machine or elsewhere. A local server commonly uses standard input and output, while a remote server commonly uses Streamable HTTP. “Local” describes where the program runs, not a different kind of server.

MCP has two layers. The data layer defines the JSON-RPC 2.0 messages and the things clients and servers can offer. The transport layer handles connection setup, message framing, authentication, and the channel itself. The same JSON-RPC messages can travel over either transport. Stdio is direct process communication with no network overhead. Streamable HTTP uses HTTP POST, can stream with Server-Sent Events, and supports normal HTTP authentication methods. MCP recommends OAuth for obtaining tokens.

The data layer keeps each request understandable on its own. MCP is a stateless protocol. Every request carries the protocol version and relevant capabilities in its `_meta` field, usually along with the client’s identity. A client may send `server/discover` before doing anything else to learn the server’s supported versions, capabilities, and identity. The response can usually be cached. Discovery is optional because the request metadata travels with every later call, so a client can send the call directly and handle a version error if necessary.

Servers expose three core primitives. Tools are executable functions for actions such as file operations, API calls, and database queries. Resources provide context such as file contents, database records, or API responses. Prompts are reusable interaction templates, including system prompts and few-shot examples. Clients discover them with methods such as `tools/list` and retrieve or execute them with methods such as `resources/read` and `tools/call`. Listings can change over time.

Imagine a server that exposes a weather tool. The client first discovers the tool and learns its exact name, description, and input schema. It then calls `weather_current` with a location and optional units. The name must match the discovered name exactly. The request carries the same protocol metadata as every other request, and the response returns an array of content objects that the AI application can pass back to the language model. The model chooses a tool, the application routes the call to the right client, the server executes it, and the result becomes new context.

Servers can also ask users for information or confirmation through elicitation. Sampling and logging are deprecated as of protocol version `2026-07-28`; new implementations should call language-model providers directly and send logs to stderr or use OpenTelemetry. Optional extensions can add other behavior, such as durable handles for long-running tasks.

The protocol supports real-time notifications to enable dynamic updates between servers and clients. A client opts in by opening a long-lived `subscriptions/listen` stream and naming the changes it wants, such as a changed tool list. The server acknowledges the subscription, then sends a notification when its tools change. The notification has no response of its own, and delivery is best effort, especially across reconnects, so clients should still poll when freshness matters. On receiving an update, the client requests `tools/list` again and refreshes what the model can use.

That is MCP’s boundary: one protocol for exchanging context, actions, and interaction patterns, with the application still responsible for deciding how an AI model uses them.
