---
source_ids:
- architecture-overview-ce5cb1d1
content_mode: faithful_synthesis
label: FAITHFUL SYNTHESIS
---

Visual Studio Code can connect to a local database server and a remote Sentry server, then present both through one conversation. The Model Context Protocol is the boundary that makes this possible: it gives an AI application and context-providing programs a shared vocabulary for connections, capabilities, requests, results, and changes. It does not dictate how the application uses a language model or manages the context it receives.

## One host, several dedicated connections

MCP follows a client-server architecture. An MCP host, such as Visual Studio Code, Claude Code, or Claude Desktop, creates one MCP client for each MCP server. Each client maintains a dedicated connection. The host can therefore keep its connection to the local database server separate from its connection to remote Sentry while combining what they provide.

A local server commonly uses STDIO, which connects two processes through standard input and output. A remote server uses Streamable HTTP and will typically serve many clients. HTTP supports bearer tokens, API keys, and custom headers; MCP recommends OAuth for obtaining authentication tokens.

The architecture has two layers. The data layer defines JSON-RPC 2.0 messages and the things clients and servers can offer. The transport layer handles connection establishment, message framing, and authentication. The same JSON-RPC exchange can travel over STDIO or HTTP because those communication details stay outside the protocol messages.

## The primitives carry context and action

The data layer defines what crosses the boundary. Every request carries a protocol version and relevant capabilities in its `_meta` field, a small envelope that tells the other side which version and features it can handle. Clients normally put their identity there too.

Every server must implement `server/discover`, which advertises supported versions, capabilities, and identity. Calling it first is optional: a client may send another request and handle a version error if necessary. Discovery is the convenient single exchange for learning what the server supports.

Suppose the local database server connected to Visual Studio Code exposes a query tool, a resource containing the database schema, and a prompt with examples of using that tool. MCP defines three server primitives for this arrangement:

- Tools are executable functions for actions such as database queries, file operations, and API calls.
- Resources provide contextual data such as database records, file contents, and API responses.
- Prompts are reusable templates for structuring interactions with language models.

Each primitive type has a discovery method in the `*/list` family. Retrieval methods exist where applicable, such as `resources/read`, and some primitives can also be executed, including tools through `tools/call`. A client can list the database server's primitives, give the available tools to the model, then call the selected tool with arguments matching its input schema. Listings may change, so clients can discover them dynamically.

A tool request has the ordinary JSON-RPC shape. Its method is `tools/call`; its parameters name the tool and carry arguments such as `"location": "San Francisco"` and `"units": "imperial"`. The response contains a `content` array that may hold text, images, resources, or other supported forms. The application adds that result to the conversation.

MCP also supports richer interaction in the other direction. Elicitation lets a server request more information or confirmation through `elicitation/create`. Sampling and logging are deprecated as of protocol version `2026-07-28`; new implementations should call language-model provider APIs directly and send logs to stderr for STDIO or use OpenTelemetry. Optional extensions can add behavior such as Tasks, which gives a client a durable handle for a long-running request so it can poll for status and retrieve the result later.

## Requests carry their own context

MCP is stateless. Each request carries the information the database server needs to process it, including its version and capabilities, rather than depending on remembered connection state. Separate requests remain understandable even when the surrounding transport changes.

The protocol also supports opt-in notifications for dynamic updates. If the database server's available tools change, Visual Studio Code can open a long-lived `subscriptions/listen` stream and name the changes it wants, such as tool-list changes. The server acknowledges with `notifications/subscriptions/acknowledged`, placing the subscription ID in `_meta`, and can then send `notifications/tools/list_changed` on that stream. The client calls `tools/list` again and refreshes the registry it has given the model.

Notifications have no response ID because they are JSON-RPC notifications. They are best effort, especially across transport reconnects, so clients should still poll when freshness matters. The model's available actions can therefore follow the database server's current capabilities, with polling as the backstop when the update stream goes quiet.
