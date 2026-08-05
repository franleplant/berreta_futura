---
source_ids:
- architecture-overview-ce5cb1d1
content_mode: faithful_synthesis
label: FAITHFUL SYNTHESIS
---

The useful way to read the Model Context Protocol is as a boundary with a vocabulary. On one side sits an AI application; on the other sit programs that provide context. MCP specifies how they connect, describe what they support, exchange requests and results, and report change. It does not dictate how the application uses a language model or manages the context it receives.

## One host, several dedicated connections

MCP follows a client-server architecture. An MCP host, such as Claude Code, Claude Desktop, or Visual Studio Code, creates one MCP client for each MCP server. Each client maintains a dedicated connection. Visual Studio Code might connect to a local filesystem server and a remote Sentry server; its runtime keeps those connections distinct while presenting their capabilities together.

Servers can run locally or remotely. A local server commonly uses STDIO, which connects two processes through standard input and output. A remote server uses Streamable HTTP and will typically serve many clients. HTTP supports bearer tokens, API keys, and custom headers; MCP recommends OAuth for obtaining authentication tokens.

The architecture has two layers. The data layer defines JSON-RPC 2.0 messages and the things clients and servers can offer. The transport layer handles connection establishment, message framing, and authentication. The same JSON-RPC exchange can travel over STDIO or HTTP because those communication details stay outside the protocol messages.

## The primitives carry context and action

The data layer is the useful center of MCP because it defines what can cross the boundary. Every request carries a protocol version and relevant capabilities in its `_meta` field, a small envelope that tells the other side which version and features it can handle. Clients normally put their identity there too.

Every server must implement `server/discover`, which advertises supported versions, capabilities, and identity. Calling it first is optional: a client may send another request and handle a version error if necessary. Discovery is simply the convenient single exchange for learning what the server supports.

MCP defines three server primitives:

- Tools are executable functions for actions such as file operations, API calls, and database queries.
- Resources provide contextual data such as file contents, database records, and API responses.
- Prompts are reusable templates for structuring interactions with language models.

Each primitive has discovery and retrieval methods in the `*/list` and `*/get` families: `tools/list`, `resources/list`, `resources/read`, `prompts/list`, and `prompts/get` are concrete examples. Tools can also be executed with `tools/call`. Listings may change, so clients can discover them dynamically.

Imagine a database server exposing a query tool, a resource containing the database schema, and a prompt with examples of using that tool. A client lists the primitives, gives the available tools to the model, then calls the selected tool with arguments matching its input schema. A request has the ordinary JSON-RPC shape, including a method such as `tools/call`; its parameters name the tool and carry arguments such as `"location": "San Francisco"` and `"units": "imperial"`. The response contains a `content` array that may hold text, images, resources, or other supported forms. The application adds that result to the conversation.

A discovery flow in the Python SDK looks like this:

```python
async with Client(stdio_client(server_config)) as client:
    if client.server_capabilities.tools:
        app.register_mcp_server(client, supports_tools=True)
    app.set_server_ready(client)
```

MCP also supports richer interaction in the other direction. Elicitation lets a server request more information or confirmation through `elicitation/create`. Sampling and logging are deprecated as of protocol version `2026-07-28`; new implementations should call language-model provider APIs directly and send logs to stderr for STDIO or use OpenTelemetry. Optional extensions can add behavior such as Tasks, which gives a client a durable handle for a long-running request so it can poll for status and retrieve the result later.

## Requests carry their own context

MCP is stateless. Each request carries the information the server needs to process it, including its version and capabilities, rather than depending on remembered connection state. That makes separate requests understandable even when the surrounding transport changes.

The protocol also supports opt-in notifications for dynamic updates. A client opens a long-lived `subscriptions/listen` stream and names the changes it wants, such as tool-list changes. The server acknowledges with `notifications/subscriptions/acknowledged`, placing the subscription ID in `_meta`. When the available tools change, it can send `notifications/tools/list_changed` on that stream. The client then calls `tools/list` again and refreshes the registry it has given the model.

Notifications have no response ID because they are JSON-RPC notifications. They are best effort, especially across transport reconnects, so clients should still poll when freshness matters. The result is a protocol in which tools and data stay in their own servers while one conversation can discover them, use them, and notice when they change.
