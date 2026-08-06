---
source_ids:
- architecture-overview-ce5cb1d1
content_mode: in_a_nutshell
label: IN A NUTSHELL
---

An AI application can ask a weather server what it supports, find a tool, call it, and, if it opts in, receive notice when that tool list changes. MCP supplies the shared exchange: the host is the AI application, a client maintains each server connection, and the server provides tools, resources, or prompt templates. Requests carry their relevant context with them, while a transport carries the messages.

## A shared exchange between application and service

Picture the application asking for the weather in San Francisco. First it learns which tools the server supports. Then it invokes one by name with arguments that match the server’s declared schema. MCP calls these offerings primitives: tools perform actions, resources provide context, and prompts supply reusable interaction templates.

The exchange has two layers. The data layer defines messages and their meaning. MCP uses JSON-RPC 2.0, a request-and-response message format in which a request names a method and carries parameters, while a response returns a result. This layer handles discovery, capabilities, primitives, and notifications. The transport layer moves those messages and handles connection setup, message boundaries, and authentication.

A local server can use standard input and output streams between processes on the same machine, avoiding network overhead. A remote server can use Streamable HTTP: the client sends messages with HTTP POST, and the server may stream events back through Server-Sent Events. Remote authentication can use bearer tokens, API keys, or custom headers; MCP recommends OAuth for obtaining tokens. The JSON-RPC message format remains the same.

The application is the MCP host; a separate MCP client maintains each server connection and obtains context for the host. A filesystem server launched on the same machine is local. A service running on a platform such as Sentry is remote. “Server” names the program providing context, wherever it runs.

## The weather request, from introduction to answer

When the weather client connects, it may send `server/discover`. The request’s `_meta` field identifies the protocol version, the client, and the client’s capabilities. The response supplies the server’s identity, supported versions, and capabilities. Primitive descriptions arrive through methods such as `tools/list`. Discovery is optional because every request carries its own metadata, but this exchange gathers compatibility information in one place and its result is typically cacheable.

Next the client sends `tools/list`. The server returns tool descriptions, including each tool’s unique `name`, human-readable `title`, `description`, and JSON Schema `inputSchema`. Suppose the list contains `weather_current`, which accepts a required `location` and an optional `units` value. The host can combine tool lists from several connected servers into one registry for the language model.

The model then chooses that weather tool. The client sends `tools/call` with the exact name, arguments such as `"location": "San Francisco"` and `"units": "imperial"`, and the usual `_meta` fields. The server responds with a content array. Here it might contain text, but the protocol can carry other content forms, including images or resources. The host places that result back into the conversation.

The same pattern works for information that should be read rather than executed. A database server might expose a resource containing its schema, alongside tools for querying it and a prompt with examples of how to use those tools. Clients discover primitive types through their corresponding `*/list` methods and retrieve or execute them with methods such as `*/get` and `tools/call`.

MCP also lets a server ask the user for more information or confirmation through elicitation, using `elicitation/create`. Older client primitives include sampling, which let a server request a language-model completion from the host, and logging, which let a server send diagnostic messages. Both are deprecated as of protocol version 2026-07-28; new implementations should call model providers directly and write logs to stderr or OpenTelemetry. Optional extensions can add other patterns. The Tasks extension, for example, gives a long-running request a durable handle that the client can poll and use to retrieve the result.

## When the tool list changes

Tool availability can change while a conversation is running. A client that wants updates opens a long-lived stream with `subscriptions/listen`, asking for `toolsListChanged`. The server acknowledges the subscription, then may send `notifications/tools/list_changed` when tools are added, modified, or temporarily unavailable.

A notification has no response ID because JSON-RPC does not expect a reply. It carries the subscription ID so the client can associate the event with the right stream. On receiving it, the client usually calls `tools/list` again and refreshes the host’s registry. These notifications are opt-in and best effort, so clients should still poll when they need reliable freshness, especially after reconnecting.

This per-request design is called statelessness. The protocol version and relevant capabilities travel in `_meta` on each request, and clients normally include their identity there. A server can process a request using the information attached to that request instead of relying on hidden connection state.

MCP defines the exchange between hosts, clients, and servers. The application still decides how to use its language model and how to manage the context it receives.
