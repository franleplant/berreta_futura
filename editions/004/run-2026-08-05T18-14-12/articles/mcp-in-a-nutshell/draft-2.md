---
source_ids:
- architecture-overview-ce5cb1d1
content_mode: faithful_synthesis
label: FAITHFUL SYNTHESIS
---

An AI application using MCP can discover what a server offers, give those offerings to a language model, and route the model’s chosen action back to the server. MCP standardizes that exchange. It does not decide how the application uses its language model or manages the context it receives.

MCP primitives are the most important concepts within MCP. Servers can expose tools, resources, and prompts. Tools are executable functions for actions such as file operations, API calls, or database queries. Resources provide contextual data such as file contents, records, or API responses. Prompts are reusable templates for structuring interactions with a language model. Each type has methods for discovery and retrieval or execution, including `tools/list`, `resources/read`, and `tools/call`. Listings can change, so a client discovers a tool first, then calls it with the exact name and arguments described by its input schema.

A database server might expose a query tool, a resource containing the database schema, and a prompt with examples of how to use the tool. The application gathers these offerings from its connected servers into a registry the language model can use. When the model chooses a tool, the application routes the call to the matching client, sends it to the server, and returns the result as conversation context. A response can contain several content types, including text, images, and other resources.

The application is the MCP host. It creates one MCP client for each MCP server, and each client maintains a dedicated connection. Visual Studio Code, for example, might connect to a Sentry server and a local filesystem server, creating separate client objects for each. A server is local or remote according to where it runs and how it connects. A filesystem process using standard input and output usually runs on the same machine, while Sentry’s server uses Streamable HTTP from the Sentry platform. Local servers typically serve one client; remote servers may serve many.

MCP has two layers. The data layer defines JSON-RPC 2.0 messages, version and capability discovery, and the primitives clients and servers can offer. The transport layer handles connection setup, message framing, authentication, and the channel itself. Standard input and output supports direct communication between local processes. Streamable HTTP supports remote communication, HTTP authentication, and optional Server-Sent Events. The same JSON-RPC message format works over either transport.

Every request carries protocol metadata in its `_meta` field, including the protocol version and the client’s capabilities. Clients normally identify themselves there as well. A server must implement `server/discover`, which advertises its supported versions, capabilities, and identity. A client can call it before other requests and cache the response. The exchange shows which primitives and notifications each side supports, so the client need not attempt operations the server cannot handle. Discovery is optional because every request carries enough metadata for the server to process it independently and reject an unsupported version.

Notifications keep a client’s view of a server from going stale. They are opt-in: the client opens a long-lived `subscriptions/listen` stream and asks for event types such as `toolsListChanged`. The server acknowledges the subscription with `notifications/subscriptions/acknowledged`, returning a subscription ID. When the tool list changes, it sends a `notifications/tools/list_changed` notification carrying that ID. The client then sends `tools/list` again and refreshes its registry. Notifications require no response and are best effort, especially across reconnects, so clients should still poll when freshness matters.

Clients can expose primitives too. Elicitation lets a server request more information or confirmation through `elicitation/create`. Sampling and logging are deprecated as of protocol version 2026-07-28. New implementations should call language-model providers directly for completions and send logs to standard error or OpenTelemetry. Optional extensions add further behavior; Tasks, for example, let a server return a durable handle for a long-running request so the client can poll for its status and retrieve the result.

MCP gives an application a standard exchange for discovering and invoking context and actions, while leaving the application’s use of the model and that context as its own design problem.
