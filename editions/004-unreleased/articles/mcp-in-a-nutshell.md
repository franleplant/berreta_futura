---
source_id: architecture-overview-ce5cb1d1
content_mode: faithful_synthesis
label: FAITHFUL SYNTHESIS
---

The Model Context Protocol defines how an AI application exchanges context and actions with external programs. It does not define how the application uses a language model, plans a task, or manages its internal context. It defines the boundary.

The MCP project includes the specification, language SDKs, development tools such as the Inspector, and reference server implementations. Most developers interact with the SDKs. The architecture underneath is still worth understanding because it explains what connects to what, what a server can expose, and how one request becomes an action.

## Host, client, server

An MCP host is the AI application. Visual Studio Code, Claude Code, or a desktop assistant can act as a host.

The host creates one MCP client for each MCP server. A client is the component that maintains the connection, discovers capabilities, sends requests, and returns server results to the host.

An MCP server is a program that provides context or actions. It can run locally or remotely.

Suppose Visual Studio Code connects to a local filesystem server and a remote Sentry server. VS Code is one host. Inside it, one client connects to the filesystem server and another client connects to Sentry. The connections remain separate even though the host can use both during the same task.

The filesystem server might read files through standard input and output on the same machine. The Sentry server might accept authenticated HTTP requests from many users. Both are MCP servers because they speak the same data-layer protocol.

## Two layers

MCP separates the data layer from the transport layer.

The data layer defines JSON-RPC messages, capability and version discovery, tools, resources, prompts, elicitation, notifications, and progress reporting. This is the part that describes meaning.

The transport layer moves those messages. Local servers commonly use stdio, which connects two processes without network overhead. Remote servers use Streamable HTTP, with HTTP POST for requests and optional Server-Sent Events for streaming notifications. Authentication belongs to this outer layer.

The same `tools/call` message can travel over either transport. The server's location changes; the protocol semantics do not.

## The three server primitives

Tools are executable functions. A tool can read a file, query a database, create an issue, send a message, or call an API. The host decides when to invoke it, usually after the model selects it as part of a task.

Resources are context data. A resource can be a file, database schema, record, log stream, or API response. Resources let the host retrieve information without pretending every read is an action.

Prompts are reusable interaction templates. A server can publish a prompt that encodes a known workflow, expected inputs, or few-shot examples for using its tools.

Consider a database server. It could expose `query_database` as a tool, the current schema as a resource, and a `diagnose_slow_query` prompt with examples. The host can read the schema, apply the prompt, then call the query tool with an informed argument.

Each primitive supports discovery. A client lists tools with `tools/list`, resources with `resources/list`, and prompts with `prompts/list`. It retrieves or executes only after it knows what the server currently offers.

## A request from discovery to action

First, the client asks the server what protocol versions and capabilities it supports through `server/discover`. Every request identifies the protocol version and relevant capabilities in `_meta`, so the server can process it without hidden connection state.

Next, the client calls `tools/list`. The response describes each tool's name, purpose, and input schema.

Assume the server returns a tool named `weather_current` with a required `location` string and optional `units`. The host now has a typed action it can present to the model.

The user asks for the weather in San Francisco. The model selects `weather_current` and supplies `{"location":"San Francisco","units":"imperial"}`. The client sends `tools/call`. The server validates the input, performs the lookup, and returns structured content.

The host can place that result into model context, call another tool, or ask the user for confirmation before a consequential step.

This is the full MCP shape in miniature: discover, list, select, call, return.

## Practical uses

A coding host such as Visual Studio Code can connect to a local filesystem server and a remote Sentry server. Each connection gets its own MCP client, while the host can use both during the same task.

A database server can expose query functions as tools, its schema as a resource, and few-shot examples as a prompt. The host can read the schema before asking the model to select and call a query tool.

An AI application can collect tools from every connected server into one registry. The model sees the available actions, selects one during a conversation, and receives the result back as context.

A local filesystem server can use stdio on the same machine. A remote service such as Sentry can expose the same protocol through authenticated Streamable HTTP.

The protocol does not decide how the application uses a language model or manages the context it receives. Those decisions remain with the host.

## Client features and notifications

Servers can request more information from the user through elicitation. A destructive tool might ask the host to confirm, "Delete these three files?" before continuing. The host controls how that request appears and whether the answer is returned.

Servers can also publish notifications. A client may subscribe to tool-list changes. If a server adds or removes a tool, it sends a notification and the client refreshes its catalog.

Notifications matter because capabilities can be dynamic. Authentication, workspace state, installed plugins, or service health can change what a server is allowed to offer.

Long-running work can report progress or use task-oriented extensions. The core exchange remains requests, responses, and notifications with explicit schemas.

## The useful boundary

MCP is often described as a connector standard. The architecture is more precise than that.

The host owns intelligence and orchestration. Each client owns one protocol relationship. Each server owns a bounded set of context and actions. The data layer defines what messages mean. The transport layer defines how they move.

That separation is the practical value. A server can remain simple and model-independent. A host can combine several servers without merging their implementations. Tool builders can publish stable typed primitives while AI applications compete on how well they use them.
