---
source_ids:
- the-2026-07-28-mcp-specification-release-candida-1a1752b8
content_mode: faithful_synthesis
label: FAITHFUL SYNTHESIS
---

A remote MCP server that once needed sticky sessions, a shared session store, and gateway inspection can now sit behind an ordinary round-robin load balancer. Requests identify their operation in headers. Clients can cache results for exactly as long as the server permits. The release candidate for the 2026-07-28 specification makes that possible by removing state from the protocol core.

The change is large enough to break existing clients and servers. The final specification is scheduled for July 28, 2026, after a ten-week validation window for SDK maintainers and implementers.

## Any request can reach any instance

Under the 2025-11-25 specification, a client first established a session with `initialize`. The server returned an `Mcp-Session-Id`, and every later request carried it. That identifier pinned the client to the server instance that issued it, which meant that a horizontally scaled deployment needed sticky routing and a shared session store.

The new protocol removes both the `initialize`/`initialized` handshake and the `Mcp-Session-Id` header. Protocol version, client information, and capabilities travel in `_meta` on each request, while a new `server/discover` method lets clients fetch server capabilities when they need them. A tool call is now self-contained, so any server instance can handle it.

The protocol no longer manages that state for you, but it doesn’t prevent you from managing it yourself. An application that needs continuity can mint an explicit handle, such as a `basket_id` or `browser_id`, and have the model pass it back as an ordinary argument on later calls. The identifier is visible in the conversation and can be composed across tools instead of hiding inside transport metadata.

This also changes how a server asks a client for input during a call. Server-initiated requests may occur only while the server is processing a client request, so a user is never prompted without an action that started the exchange. For a multi-step interaction, the server returns an `InputRequiredResult` containing the question and a `requestState`. The client gathers the answer, then retries the original call with `inputResponses` and the echoed state. Any instance can handle that retry because the needed information is in the payload.

## Traffic becomes easier to operate

Streamable HTTP now requires `Mcp-Method` and `Mcp-Name` headers. Load balancers, gateways, and rate limiters can route or throttle by operation without inspecting the request body, and servers reject a request when its headers disagree with its contents.

List and resource-read responses now include `ttlMs` and `cacheScope`. A client can tell how long a `tools/list` response remains fresh and whether it is safe to share between users. A long-lived server-sent-events stream is no longer the only way to learn that a list changed.

The specification also documents W3C Trace Context propagation in `_meta`, fixing the names for `traceparent`, `tracestate`, and `baggage`. A trace can follow a tool call from the host application through the client SDK, MCP server, and downstream services into one OpenTelemetry-compatible span tree.

## Extensions have somewhere to grow

Extensions existed in the previous release, but they had no formal process. The new framework gives them reverse-DNS identifiers, capability negotiation through an `extensions` map, independent versions, delegated maintainers, and their own repositories. A new Extensions Track lets an idea move from experiment to official extension without first becoming part of the core specification.

Two extensions arrive with this release. MCP Apps lets a server provide an interactive HTML interface that a host renders in a sandboxed iframe. Tools declare their UI templates in advance, allowing hosts to prefetch, cache, and review them before execution. The interface still communicates through MCP’s JSON-RPC base protocol, so an action from the interface follows the same audit and consent path as a direct tool call.

Tasks takes a different route. It began as an experimental core feature in 2025-11-25, but production use exposed enough problems that it now belongs outside the specification. A server can answer `tools/call` with a task handle, and the client manages that task with `tasks/get`, `tasks/update`, and `tasks/cancel`. The server decides when a call should become a task after the client advertises support. The old `tasks/list` method is removed because it cannot be scoped safely without sessions. Implementations built on the experimental API must migrate.

## Authorization and schemas tighten

Six changes bring authorization closer to common OAuth 2.0 and OpenID Connect deployments. Clients must validate the `iss` parameter in authorization responses, reducing a mix-up attack that is especially relevant when one client talks to many servers. Clients also declare their OpenID Connect `application_type` during dynamic registration, bind credentials to the issuing authorization server, and re-register when a resource moves to another issuer. The release clarifies refresh-token requests, scope accumulation during step-up authorization, and the discovery suffix used in `.well-known` URLs.

Tool schemas now use full JSON Schema 2020-12. Input schemas still require an object at the root, but may use `oneOf`, `anyOf`, `allOf`, conditionals, and references through `$ref` and `$defs`. Output schemas are unrestricted, and `structuredContent` may contain any JSON value rather than only an object. Implementations must not automatically dereference external references and must bound schema depth and validation time.

A missing resource now uses the JSON-RPC standard error `-32602 Invalid Params` instead of MCP’s custom `-32002`. Clients that match the old literal value need to change.

## Deprecation becomes a schedule

Roots, Sampling, and Logging are deprecated under the new lifecycle policy. Roots are replaced by tool parameters, resource URIs, or server configuration. Sampling gives way to direct integration with an LLM provider. For logging, stdio transports can use `stderr`, while structured observability belongs in OpenTelemetry.

These are annotation-only deprecations. The methods, types, and capability flags continue to work in this release and every specification version published within a year of it. Removal requires a separate SEP.

That twelve-month minimum window is part of a broader attempt to make future change less disruptive. Features now move through Active, Deprecated, and Removed states. Extensions can mature as opt-in capabilities. A Standards Track SEP cannot reach Final status until a matching scenario appears in the conformance suite, the same suite used to score official SDK tiers.

The stateless redesign required a clean break. The expectation is that future revisions, using extensions and deprecation windows, will let implementers adopt new behavior without rewriting their transport or lifecycle code.

The release candidate is locked. SDK maintainers and client implementers have until July 28 to test it against real workloads, with Tier 1 SDKs expected to ship support during that window. The next version of MCP asks less of the network, makes more state visible to the model, and gives the protocol a slower way to change.
