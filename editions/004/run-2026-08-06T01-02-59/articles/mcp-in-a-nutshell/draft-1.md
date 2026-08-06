---
source_ids:
- architecture-overview-ce5cb1d1
content_mode: faithful_synthesis
label: FAITHFUL SYNTHESIS
---

Visual Studio Code connects to a Sentry server, then to a local filesystem server. The application does not open one magical pipe to “MCP.” It creates one MCP client for each server, and each client keeps its own connection. The Sentry program may run remotely on Sentry’s platform; the filesystem program may run beside the application over standard input and output. They speak the same protocol.

## Three participants, two layers

The host is the AI application, such as Claude Code, Claude Desktop, or Visual Studio Code. It coordinates the clients. A client maintains a connection to one server and obtains context for the host. A server is simply the program that provides that context, wherever it runs.

Local servers commonly use the STDIO transport and often serve one client. Remote servers use Streamable HTTP and can serve many clients. The location changes the communication channel, not the role: a server remains a server whether it runs in another process on your laptop or on a platform across the network.

MCP focuses solely on the protocol for context exchange—it does not dictate how AI applications use LLMs or manage the provided context.

The protocol has an inner data layer and an outer transport layer. The data layer defines messages and their meaning through JSON-RPC 2.0. The transport layer establishes connections, frames messages, and handles authentication. STDIO carries messages between local processes without network overhead. Streamable HTTP sends them through HTTP POST, with optional Server-Sent Events for streaming and ordinary HTTP authentication methods such as bearer tokens, API keys, and custom headers. The same JSON-RPC messages can travel through either transport.

## A request can stand alone

MCP is stateless. Every request carries the protocol version and the relevant capabilities in its `_meta` field, and clients normally identify themselves there as well. A server can therefore process a request on its own instead of depending on hidden connection state.

A client may begin with the mandatory `server/discover` request. The response tells it which protocol versions the server accepts, which capabilities it offers, and who it is. If the requested version is unsupported, the server returns the versions it does support, and the client retries with a mutually supported one. Discovery is optional because the same metadata travels with every request, but it is a convenient way to learn the server’s identity and capabilities in one exchange. Its result is usually cacheable.

That exchange prevents a common kind of failure: a client does not have to guess whether a server supports tools, resources, prompts, or change notifications. The application can record the answer and decide which servers belong in its tool registry.

## The primitives are the vocabulary

Servers expose three core primitives. Tools are executable functions, such as file operations, API calls, or database queries. Resources are sources of context, such as file contents, database records, or API responses. Prompts are reusable templates that structure interactions with language models.

Each kind has discovery methods such as `tools/list`, `resources/list`, or `prompts/list`, retrieval methods where appropriate, and execution for tools through `tools/call`. Listings may change over time, so a client can discover what exists instead of relying on a fixed manifest.

Imagine a database server. It can expose a tool that runs a query, a resource containing the database schema, and a prompt with examples of how to use the tool. The model receives three different kinds of help: an action it can perform, information that explains the world, and a pattern for asking.

Clients can also expose primitives. Elicitation lets a server request more information from the user or ask for confirmation before an action. Sampling and logging are deprecated as of protocol version 2026-07-28. New implementations should call language-model providers directly for completions, and should write logs to standard error or use OpenTelemetry.

Optional extensions add further behavior. The Tasks extension, for example, lets a server return a durable handle for a long-running request so the client can check its status and retrieve the result later.

## From discovery to action

A typical interaction follows a small loop. The client discovers the server, lists its tools, chooses one, and calls it with arguments that match the tool’s declared JSON Schema. The tool name must match exactly. The response contains a content array, which can hold text, images, resources, or other supported forms.

When a language model decides to use a tool, the AI application intercepts that decision, routes the call through the right MCP client, sends it to the server, and returns the result to the conversation. MCP supplies the bridge. The application still decides how to present the result and how the model should use it.

An application connected to many servers can combine their tool listings into one registry for the model. It can also discover tools progressively instead of loading every tool at once. That choice matters when a federation of servers offers more functions than a model can usefully inspect in one pass.

## Staying current

The protocol supports real-time notifications to enable dynamic updates between servers and clients. A client opts in by opening a long-lived subscription and naming the event types it wants, such as changes to the tool list. If the server agrees, it acknowledges the subscription and sends notifications without expecting a response.

A notification says that something changed; it does not carry the entire replacement list. The client normally responds by requesting `tools/list` again and updating the model’s available capabilities. Tools may appear, disappear, or change because of server state, external dependencies, or user permissions.

Notifications are best effort. Reconnects can lose them, so clients should also poll when they need freshness. The subscription stream keeps an active conversation responsive, while polling supplies the less glamorous guarantee that the registry will eventually catch up.

MCP’s achievement is modest in the useful sense. It gives an AI application a shared language for discovering context, asking for actions, receiving results, and noticing change. The host can connect many servers, each client can keep its boundary clear, and every request carries enough information to be understood on its own.
