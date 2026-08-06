---
source_ids:
- architecture-overview-ce5cb1d1
content_mode: in_a_nutshell
label: IN A NUTSHELL
---

An AI application needs a weather answer. A separate program has the data and the operation that can fetch it. MCP gives them a shared conversation: the application opens one client connection to that server, learns what the server supports, calls the right tool, and receives context it can give to the model. The messages use JSON-RPC. A transport carries them. Each request identifies the protocol version and capabilities, so the server can handle it without depending on a remembered connection state.

## One host, one client for each server

Picture Visual Studio Code as the host. It coordinates the model and any MCP integrations. When it connects to a server, the runtime creates an MCP client dedicated to that server. A second server gets a second client and a second connection.

The server is simply the program that provides context. It may run beside the host through standard input and output, or on another machine over HTTP. The arrangement stays the same: host, client, server. A local server commonly serves one client; a remote HTTP server may serve many.

MCP has two layers. The inner data layer defines the JSON-RPC messages and the things a server can offer. The outer transport layer establishes the channel, frames messages, and handles authorization. Stdio is direct process communication. Streamable HTTP uses HTTP POST and can add Server-Sent Events for streaming. The same data messages travel through either one.

## The server opens its doors

Suppose the weather server supports a tool named `weather_current`. Before using it, the client may send `server/discover`. The request carries a protocol version, client identity, and client capabilities in `_meta`; the response reports the server's supported versions, identity, and capabilities. If the versions do not match, the server rejects the request with the versions it accepts, and the client retries with a compatible one.

Discovery is optional because every request carries the same per-request metadata. It is useful because one exchange gives the client a map of the server. An application can cache that response, register the server, and decide which kinds of functionality it can use.

The client then sends `tools/list`. The response describes each tool with a name, title, description, and JSON Schema for its inputs. That schema tells the application which arguments are required and lets it validate a call. Listings can change, so clients need not assume that yesterday's tool registry is today's.

Servers can expose three main kinds of primitives. A tool performs an action, such as an API call or database query. A resource supplies context, such as a file or database record. A prompt supplies a reusable interaction template. Clients discover these with the corresponding `*/list` methods and retrieve or execute them with methods such as `*/get` and `tools/call`.

## The call carries its own context

The application now knows the exact tool name and its input shape. It sends `tools/call` with `name: "weather_current"` and arguments such as a location and units. The request also carries the protocol version, client identity, and capabilities in `_meta`, plus a JSON-RPC request ID so the response can be matched to the call.

The server returns a content array. One item may be text; other supported content types can carry richer results. The application routes that result back into the conversation, where the model can use it as current context.

The important boundary is deliberate. MCP defines how clients and servers exchange context. It does not decide how an AI application uses a language model or manages that context. The host still chooses when to call a tool and how to present the result.

## Changes arrive only when requested

Now imagine the weather server changes its available tools because an external dependency or permission changes. A client that wants live updates opens a long-lived stream with `subscriptions/listen`, asking for `toolsListChanged`. The server acknowledges the subscription and may later send `notifications/tools/list_changed`.

That notification has no request ID because it expects no response. It carries a subscription ID so the client knows which stream produced it. On receipt, the client normally calls `tools/list` again and updates the model's available actions.

This is opt-in and best effort. A server must advertise support for the notification, and a reconnect may lose an event. Clients should still poll when they need freshness.

The result is a small, inspectable contract: one client per server, JSON-RPC messages that describe themselves, and primitives that separate actions from data and interaction templates. A tool can appear, be discovered, be called, and change without the host learning the server's private implementation.
