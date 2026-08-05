---
source_ids:
- the-2026-07-28-mcp-specification-release-candida-1a1752b8
content_mode: faithful_synthesis
label: FAITHFUL SYNTHESIS
---

A remote MCP server that previously needed sticky sessions, a shared session store, and deep packet inspection at the gateway can now run behind a plain round-robin load balancer. The 2026-07-28 release candidate removes the protocol-level session, routes requests with headers, and lets clients cache responses according to the server’s instructions. It is the largest revision since MCP launched, and it contains breaking changes.

In the 2025-11-25 protocol, a client began with an `initialize` handshake. The server returned an `Mcp-Session-Id`, and every later request had to carry it, pinning traffic to the instance that issued it. In 2026-07-28, the handshake and session disappear. Protocol version, client information, and capabilities travel in `_meta` on each request, while a new `server/discover` method lets clients fetch server capabilities when needed. Any request can reach any instance.

Stateless protocol, stateful applications

Removing protocol state does not remove application state. A server can mint an explicit handle, such as a `basket_id` or `browser_id`, and have the model pass it back as an ordinary argument on later calls. In practice, we’ve found this pattern (the model threading an identifier from one tool call to the next) to be more than just a workable substitute for session state. It’s often a more powerful one. The model can compose handles across tools, reason about them, and hand them off between steps. The protocol no longer manages that state for you, but it doesn’t prevent you from managing it yourself. The explicit-handle pattern simply makes the state visible to the model rather than hidden away.

Servers can still ask clients for input during a call, but only while actively processing a client request. A user is never prompted out of nowhere, and every elicitation traces back to something they or their agent started. Instead of holding an SSE stream open, the server returns an `InputRequiredResult` containing the questions and a `requestState`; the client answers and re-issues the original call with `inputResponses` and the echoed state. Any server instance can handle that retry because the payload carries what it needs.

Three operational headers make the traffic easier to handle. Streamable HTTP now requires `Mcp-Method` and `Mcp-Name`, so load balancers, gateways, and rate limiters can route on the operation without inspecting the body. Servers reject requests when the headers and body disagree. List and resource-read results carry `ttlMs` and `cacheScope`, telling clients how long a response remains fresh and whether it may be shared. W3C Trace Context names, including `traceparent`, `tracestate`, and `baggage`, are documented in `_meta`, allowing one trace to follow a call through the host, SDK, MCP server, and downstream services.

Extensions become the place for capabilities that should evolve independently. Extensions now have reverse-DNS identifiers, negotiation in the capabilities map, delegated maintainers, their own repositories, and a path from experimental to official. MCP Apps lets a server provide an interactive HTML interface in a sandboxed iframe. Hosts can prefetch, cache, and review the UI before it runs, and actions from that interface still use the same JSON-RPC protocol and audit path as direct tool calls.

Tasks move out of the core and become an extension. A server may answer `tools/call` with a task handle, while the client drives the work with `tasks/get`, `tasks/update`, and `tasks/cancel`. The server decides when a call should become a task. `tasks/list` is removed because it cannot be scoped safely without sessions, so anyone using the 2025-11-25 experimental API must migrate.

Authorization changes follow ordinary OAuth and OpenID Connect deployments more closely. Clients must validate the `iss` parameter in authorization responses, declare their OpenID Connect `application_type` during dynamic registration, bind credentials to the issuing server, and re-register when a resource moves. The specification also clarifies refresh-token requests, scope accumulation during step-up, and discovery naming.

Three older features are deprecated: Roots moves to tool parameters, resource URIs, or server configuration; Sampling moves to direct LLM-provider integration; and Logging moves to `stderr` for stdio transports or OpenTelemetry for structured observability. These are annotation-only deprecations. The methods, types, and capability flags continue to work in this release and every specification version published within a year of it. Removal requires a separate SEP.

Tool schemas now support full JSON Schema 2020-12. Input schemas still require an object root, but may use `oneOf`, `anyOf`, `allOf`, conditionals, and references. Output schemas are unrestricted, and `structuredContent` may be any JSON value. Implementations must not auto-dereference external `$ref` URIs and should bound schema depth and validation time. A missing-resource error also changes from MCP’s `-32002` to the JSON-RPC standard `-32602 Invalid Params`; clients matching the old literal must update.

The release is a deliberate break, with machinery intended to make the next one less disruptive. Every feature now has Active, Deprecated, and Removed stages, with at least twelve months between deprecation and the earliest possible removal. New capabilities can mature as opt-in extensions, and a Standards Track SEP cannot reach Final status until a matching scenario enters the conformance suite. With the transport reset, explicit deprecation windows, and extensions in place, implementers targeting 2026-07-28 should be able to adopt future revisions without rewriting their transport or lifecycle code.
