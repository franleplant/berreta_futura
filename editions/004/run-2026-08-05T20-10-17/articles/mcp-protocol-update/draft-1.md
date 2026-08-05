---
source_ids:
- the-2026-07-28-mcp-specification-release-candida-1a1752b8
content_mode: faithful_synthesis
label: FAITHFUL SYNTHESIS
---

A remote MCP server that previously needed sticky sessions, a shared session store, and deep packet inspection at the gateway can now run behind a plain round-robin load balancer, route traffic on an `Mcp-Method` header, and let clients cache responses for as long as the server’s `ttlMs` permits. The release candidate for the 2026-07-28 specification is the largest revision since launch. It makes that deployment possible by making the protocol core stateless, adding an Extensions framework with Tasks and MCP Apps, hardening authorization, and setting a deprecation policy. It is a breaking release; the final specification ships July 28, 2026.

Until 2025-11-25, Streamable HTTP began with an `initialize`/`initialized` handshake. The server returned an `Mcp-Session-Id`, and every later request carried it, pinning the client to the instance that issued it. In `2026-07-28`, the same `tools/call` is self-contained. `MCP-Protocol-Version`, `Mcp-Method`, and `Mcp-Name` travel with the request, while protocol version, client information, and capabilities sit in `_meta`. The handshake and session are gone. The new `server/discover` method lets a client fetch server capabilities when it needs them, and any request can reach any instance.

An application may still keep state. A tool can mint a `basket_id`; the model passes that identifier as an ordinary argument on the next call. The protocol no longer manages that state for you, but it doesn’t prevent you from managing it yourself. In practice, we’ve found this pattern (the model threading an identifier from one tool call to the next) to be more than just a workable substitute for session state. It’s often a more powerful one. The model can compose handles across tools and hand them between steps, where transport-managed state stayed hidden.

Server-to-client requests now have a boundary. A server may issue one only while actively processing a client request, so a user is never prompted out of nowhere, and every elicitation traces back to something they (or their agent) started. Multi-round-trip work returns an `InputRequiredResult` with input requests and an opaque `requestState`. The client sends the original call again with `inputResponses` and that state. Because the payload carries the context, any server instance can handle the retry.

Three transport details finish the operational change. `Mcp-Method` and `Mcp-Name` let a load balancer, gateway, or rate limiter route without inspecting the body, and servers reject a disagreement between headers and body. List and resource reads carry `ttlMs` and `cacheScope`, so clients know freshness and whether a result may be shared. W3C Trace Context keys in `_meta`, `traceparent`, `tracestate`, and `baggage`, let a tool call remain one trace from host through SDK and server into downstream services.

## Extensions Become First-Class

Extensions now have a formal path. They use reverse-DNS IDs, negotiation through an `extensions` map, separate `ext-*` repositories, delegated maintainers, and independent versions; an Extensions Track can carry a feature from experimental to official. MCP Apps lets a server ship an interactive HTML interface for a sandboxed iframe, declare its UI templates before execution, and send UI actions over the same JSON-RPC path as tool calls. Hosts can prefetch, cache, and security-review the template, and the action follows the same audit and consent path.

Tasks graduates from the core into an extension shaped for the stateless model. A server can answer `tools/call` with a task handle; the client drives it with `tasks/get`, `tasks/update`, and `tasks/cancel`. The server decides when a call becomes a task after the client advertises support. `tasks/list` is removed because it cannot be scoped safely without sessions, so anyone who shipped against the experimental 2025-11-25 API must migrate.

## Authorization Hardening

Clients must validate `iss` in authorization responses, a mitigation for mix-up attacks that matter more when one client talks to many servers. In a future version, clients will be expected to reject a response that omits it, so authorization servers should supply it now. Dynamic Client Registration now carries the OpenID Connect `application_type`; clients bind registered credentials to the issuing server’s `issuer` and re-register if a resource moves. The specification also clarifies refresh-token requests, scope accumulation during step-up, and the `.well-known` discovery suffix.

Roots, Sampling, and Logging are annotation-only deprecations. Roots move toward tool parameters, resource URIs, or server configuration; Sampling toward direct LLM-provider integration; Logging toward `stderr` for stdio and OpenTelemetry for structured observability. Their methods, types, and capability flags continue to work in this release and every specification version published within a year of it, and removal needs a separate SEP.

Tool schemas now use full JSON Schema 2020-12. Input schemas still need an object root but may use composition, conditionals, and references; output schemas are unrestricted, and `structuredContent` may be any JSON value. Implementations must not auto-dereference external `$ref` URIs and should bound schema depth and validation time. A missing-resource error changes from `-32002` to JSON-RPC’s `-32602 Invalid Params`, so clients matching the old literal must update.

## How the Protocol Evolves From Here

This release contains breaking changes. We don’t intend for that to be the norm. The feature lifecycle gives each capability an Active, Deprecated, and Removed state, with at least twelve months between deprecation and earliest removal. Extensions let new work stabilize as opt-in. A Standards Track proposal cannot reach Final until a matching scenario lands in the conformance suite, the same suite used to score official SDK tiers. The stateless rework in this release is the kind of foundational change that needed a clean break. With it landed, and with deprecation windows and extensions as the standard tools going forward, our expectation is that implementers targeting `2026-07-28` will be able to adopt future revisions without rewriting their transport or lifecycle code.
