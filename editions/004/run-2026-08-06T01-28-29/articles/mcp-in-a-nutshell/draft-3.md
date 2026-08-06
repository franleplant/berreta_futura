---
source_ids:
- architecture-overview-ce5cb1d1
content_mode: in_a_nutshell
label: IN A NUTSHELL
---

An AI application needs a weather answer. A separate program has the data and the operation that can fetch it. MCP gives them a shared conversation: the application opens one client connection to that server, learns what the server supports, calls the right tool, and receives context for the model. JSON-RPC 2.0 supplies the message grammar: requests ask for work, responses carry results, notifications announce events without asking for a response, and an ID ties each response to its request. A transport carries those messages. Each request identifies the protocol version and capabilities, so the server can handle it without depending on remembered connection state.

## One host, one client for each server

Picture Visual Studio Code as the host. It coordinates the model and any MCP integrations. When it connects to a server, the runtime creates an MCP client dedicated to that server. A second server gets a second client and a second connection.

The server is the program that provides context. It may run beside the host through standard input and output, or on another machine over HTTP. The arrangement stays the same: host, client, server. A local server commonly serves one client; a remote HTTP server may serve many.

MCP has two layers. The inner data layer defines the JSON-RPC messages and the things a server can offer. The outer transport layer establishes the channel, frames messages, and handles authorization. Stdio is direct process communication. Streamable HTTP uses HTTP POST and can add Server-Sent Events for streaming. For remote authentication, the transport supports bearer tokens, API keys, and custom headers; MCP recommends obtaining tokens with OAuth. The same data messages travel through either transport.

## The server opens its doors

Suppose the weather server supports a tool named `weather_current`. Before using it, the client may send `server/discover`. The request carries a protocol version, client identity, and client capabilities in `_meta`; clients should include their identity unless configured not to. The response reports the server's supported versions, identity, and capabilities. If the versions do not match, the server rejects the request with the versions it accepts, and the client retries with a compatible one.

Discovery is optional because every request carries the same per-request metadata. It is useful because one exchange gives the client a map of the server. An application can cache that response, register the server, and decide which kinds of functionality it can use.

The client then sends `tools/list`. The response describes each tool with a name, title, description, and JSON Schema for its inputs. That schema tells the application which arguments are required and lets it validate a call. Listings can change, so clients need not assume that yesterday's tool registry is today's.

Servers can expose three main kinds of primitives. Tools are executable functions for actions such as API calls or database queries. Resources give the application context, such as file contents or database records. Prompts package reusable interaction templates, including system prompts and few-shot examples. Clients discover these with the corresponding `*/list` methods and retrieve or execute them with methods such as `*/get` and `tools/call`.

MCP also defines client-side primitives. With elicitation, a server can ask the user for more information or confirmation through `elicitation/create`, using the Multi Round-Trip Requests pattern for the exchange. Sampling, which lets a server request model completions from the host, and logging are deprecated as of protocol version 2026-07-28. New implementations should call language-model provider APIs directly and send logs to stderr or OpenTelemetry. Optional extensions such as Tasks can return a durable handle for a long-running request, which the client polls for status and later retrieves.

## The call carries its own context

The application now knows the exact tool name and its input shape. It sends `tools/call` with `name: "weather_current"` and arguments such as a location and units. The request carries the protocol version and client capabilities in `_meta`, plus the client's identity unless the client is configured not to include it. A JSON-RPC request ID lets the response be matched to the call.

The server returns a content array. One item may be text; other supported content types can carry richer results. When the language model decides to use the weather tool, the AI application routes that call to the appropriate MCP server and returns the result to the model as conversation context.

MCP defines this exchange and the available primitives. The AI application connects them to its conversation.

## Changes arrive only when requested

Now imagine the weather server changes its available tools because an external dependency or permission changes. A client that wants live updates opens a long-lived stream with `subscriptions/listen`, asking for `toolsListChanged`. The server acknowledges the subscription and may later send `notifications/tools/list_changed`.

That notification has no request ID because it expects no response. It carries a subscription ID so the client knows which stream produced it. On receipt, the client typically calls `tools/list` again and updates the model's available actions.

This is opt-in and best effort. A server must advertise support for the notification, and a reconnect may lose an event. Clients should also poll when they need to preserve freshness, because the stream cannot guarantee that every change will arrive. For the weather example, the client refreshes its tool list after an event and checks again when a missed update would matter.
