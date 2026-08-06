---
source_ids:
- architecture-overview-ce5cb1d1
content_mode: in_a_nutshell
label: IN A NUTSHELL
---

An AI application can discover a weather service, learn what it can do, call it, and hear when its tools change without learning the service’s private API. MCP supplies the shared conversation. The application is the host; a small client keeps each server connection, and the server offers tools, data, or prompt templates. Every request carries enough information to stand on its own, while a separate transport carries the message.

## A shared counter between the application and the service

Picture an AI application connected to a weather server. The application asks what the server supports, receives descriptions of its tools, and invokes one by name with arguments that match a declared schema. MCP calls these offerings primitives: tools perform actions, resources provide context, and prompts supply reusable interaction templates.

The connection has two layers. The data layer defines the messages and their meaning. MCP uses JSON-RPC 2.0, a request-and-response format in which each request names a method and carries parameters, while a response returns the result. The same layer handles discovery, capabilities, primitives, and notifications. The transport layer moves those messages and handles connection setup, message boundaries, and authentication.

A local server can use the standard input and output streams of processes on the same machine, avoiding network overhead. A remote server can use Streamable HTTP, sending messages with HTTP POST and optionally streaming events back with Server-Sent Events. HTTP authentication may use bearer tokens, API keys, or custom headers; MCP recommends OAuth for obtaining tokens. The message format stays the same.

The application is the MCP host. For every server it connects to, it creates a separate MCP client, which maintains that server’s connection and obtains context for the host. A filesystem server launched on the same machine is local; a service running on a platform such as Sentry is remote. The server means the program providing context, wherever that program runs.

## The weather request, from introduction to answer

When the weather client connects, it may send `server/discover`. The request’s `_meta` field identifies the protocol version, the client, and the client’s capabilities. The response gives the server’s identity, supported versions, capabilities, and primitives. Discovery is optional because every request carries its own metadata, but it gathers compatibility information in one exchange and its result is typically cacheable.

Next the client sends `tools/list`. The server returns tool descriptions, including each tool’s unique `name`, human-readable `title`, `description`, and JSON Schema `inputSchema`. Suppose the list contains `weather_current`, which accepts a required `location` and an optional `units` value. The host can combine tool lists from several connected servers into one registry for the language model.

The model then chooses that weather tool. The client sends `tools/call` with the exact name, arguments such as `"location": "San Francisco"` and `"units": "imperial"`, and the usual `_meta` fields. The server responds with a content array. Here it might contain text, but the protocol can carry other content forms, including images or resources. The host places that result back into the conversation.

The same pattern works for information that should be read rather than executed. A database server might expose a resource containing its schema, alongside tools for querying it and a prompt with examples of how to use those tools. Clients discover primitive types through their corresponding `*/list` methods and retrieve or execute them with methods such as `*/get` and `tools/call`.

MCP also lets a server ask the user for more information or confirmation through elicitation, using `elicitation/create`. Older client primitives include sampling, which let a server request a language-model completion from the host, and logging, which let a server send diagnostic messages. Both are deprecated as of protocol version 2026-07-28; new implementations should call model providers directly and write logs to stderr or OpenTelemetry. Optional extensions can add other patterns. The Tasks extension, for example, gives a long-running request a durable handle that the client can poll and use to retrieve the result.

## When the counter changes

Tool availability can change while a conversation is running. A client that wants updates opens a long-lived stream with `subscriptions/listen`, asking for `toolsListChanged`. The server acknowledges the subscription, then may send `notifications/tools/list_changed` when tools are added, modified, or temporarily unavailable.

A notification has no response ID because JSON-RPC does not expect a reply. It carries the subscription ID so the client can associate the event with the right stream. On receiving it, the client usually calls `tools/list` again and refreshes the host’s registry. These notifications are opt-in and best effort, so clients should still poll when they need reliable freshness, especially after reconnecting.

This per-request design keeps the protocol’s assumptions visible. The protocol version and relevant capabilities travel in `_meta` on each request, and clients normally include their identity there. A server can process a request using the information attached to that request instead of relying on hidden connection state.

MCP defines the exchange between hosts, clients, and servers. The application still decides how to use its language model and how to manage the context it receives.
