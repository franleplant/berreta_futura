---
source_ids:
- the-2026-07-28-mcp-specification-release-candida-1a1752b8
content_mode: faithful_synthesis
label: FAITHFUL SYNTHESIS
---

A remote MCP server once needed sticky sessions, a shared session store, and a gateway that inspected request bodies. The 2026-07-28 release candidate removes that burden from the protocol layer. Any request can reach any server instance, and ordinary HTTP infrastructure can route, cache, and trace the traffic.

## The session disappears

In the 2025-11-25 specification, a client began with an `initialize` handshake. The server returned an `Mcp-Session-Id`, and every later request carried it, tying the client to the instance that created the session. The new protocol removes both the handshake and the session identifier.

Protocol version, client information, and capabilities now travel in `_meta` on each request. A new `server/discover` method lets clients fetch server capabilities when they need them. Requests also carry `Mcp-Method` and `Mcp-Name` headers, so a load balancer, gateway, or rate limiter can route on the operation without inspecting JSON. The server rejects a request when its headers and body disagree.

Stateless transport does not forbid stateful applications. A tool can return an explicit handle such as `basket_id` or `browser_id`, and the model can pass that value back on the next call. The protocol no longer manages that state for you, but it doesn’t prevent you from managing it yourself. The handle is visible to the model, which can compose it across tools or hand it from one step to another.

Server-to-client requests have been rebuilt around the same constraint. A server may ask the client for input only while processing an active client request. Instead of holding an SSE stream open, it returns an `InputRequiredResult` containing the prompt and a `requestState` value. The client gathers the answer and retries the original call with `inputResponses` and that state. Any server instance can handle the retry because the needed information travels in the payload. A user is never prompted out of nowhere, and every elicitation traces back to something they (or their agent) started.

List and resource-read results now include `ttlMs` and `cacheScope`, modeled on HTTP caching. Clients can tell how long a `tools/list` response remains fresh and whether it may be shared across users. The specification also documents W3C Trace Context keys in `_meta`, including `traceparent`, `tracestate`, and `baggage`, so a tool call can appear as one distributed trace across the host, SDK, MCP server, and downstream services.

## Extensions leave the basement

Extensions existed before, but without a formal process. The new framework gives them reverse-DNS identifiers, capability negotiation, independent repositories and versioning, delegated maintainers, and an Extensions Track in the SEP process. Experimental features can therefore stabilize without forcing every implementation to adopt them.

MCP Apps is one of the first official extensions. A server can provide an interactive HTML interface that a host renders in a sandboxed iframe. Tools declare their UI templates in advance, allowing hosts to prefetch, cache, and review them before execution. The interface still communicates through MCP’s JSON-RPC base protocol, so a UI action follows the same audit and consent path as a direct tool call.

Tasks also move out of the core specification. In the new extension, a server may answer `tools/call` with a task handle, while the client drives the work with `tasks/get`, `tasks/update`, and `tasks/cancel`. Task creation is server-directed: the client advertises support, and the server decides when a call should become a task. `tasks/list` is removed because it cannot be scoped safely without sessions. Anyone using the experimental Tasks API from 2025-11-25 will need to migrate.

## Security and compatibility

Six authorization SEPs bring MCP closer to deployed OAuth 2.0 and OpenID Connect practice. Clients must validate the `iss` parameter in authorization responses, a defense against mix-up attacks that matter in a system with one client and many servers. Clients now declare their OpenID Connect `application_type` during Dynamic Client Registration, bind credentials to the issuing authorization server, and register again when a resource moves to another issuer. The release also clarifies refresh-token requests, scope accumulation during step-up, and the `.well-known` discovery suffix.

Three core features enter the deprecation lifecycle: Roots, Sampling, and Logging. Roots can be replaced by tool parameters, resource URIs, or server configuration. Sampling gives way to direct integration with an LLM provider. For logging, stdio transports should use `stderr`, while structured observability should use OpenTelemetry. These are annotation-only deprecations. The features continue to work in this release and every specification version published within a year; removal requires another SEP.

Tool schemas now use full JSON Schema 2020-12. Input schemas still require an object at the root, but they may use `oneOf`, `anyOf`, `allOf`, conditionals, and references such as `$ref` and `$defs`. Output schemas are unrestricted, and `structuredContent` may contain any JSON value. Implementations must avoid automatic dereferencing of external references and bound schema depth and validation time. A missing-resource error also changes from MCP’s `-32002` to the JSON-RPC standard `-32602 Invalid Params`, so clients matching the old literal must update.

## A controlled break

This release is breaking because the transport needed a clean break. The maintainers do not expect that pattern to continue. A feature lifecycle now provides Active, Deprecated, and Removed stages with at least twelve months between deprecation and the earliest possible removal. Extensions provide an opt-in path for new capabilities. A Standards Track SEP cannot reach Final status until a matching scenario appears in the conformance suite, the same suite used to score official SDK tiers.

On May 21, 2026, the project locked the release candidate. The final specification will ship on July 28, giving SDK maintainers and client implementers ten weeks to test real workloads. Tier 1 SDKs should ship support during that window.

A plain round-robin load balancer can now distribute MCP requests because the protocol no longer carries a session. Applications may still keep state, but they must name that state and pass it deliberately. Future revisions now have a place to grow without hiding another breaking change inside the transport.
