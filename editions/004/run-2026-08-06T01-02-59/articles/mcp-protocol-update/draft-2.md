---
source_ids:
- the-2026-07-28-mcp-specification-release-candida-1a1752b8
content_mode: faithful_synthesis
label: FAITHFUL SYNTHESIS
---

A remote MCP server that once needed sticky sessions, a shared session store, and deep packet inspection at the gateway can now sit behind a plain round-robin load balancer. The 2026-07-28 release candidate removes the protocol session, makes requests independently routable, lets clients cache results, and adds extensions for long-running work and server-rendered interfaces. It also changes authorization, schema validation, and the rules for retiring features. The final specification is scheduled for July 28, 2026, and the release contains breaking changes.

## Any instance can handle the request

Before this revision, a Streamable HTTP client established a session with an `initialize` handshake. The server returned an `Mcp-Session-Id`, and later calls had to return to the instance that issued it. That arrangement required sticky routing and often a shared session store.

The handshake and session are gone. Protocol version, client information, and capabilities now travel in `_meta` on each request. Clients that need server capabilities can fetch them through a new `server/discover` method. The `Mcp-Session-Id` header disappears, so any request can land on any server instance. `Mcp-Method` and `Mcp-Name` headers expose the operation to load balancers, gateways, and rate limiters without forcing them to inspect the request body; servers reject requests when the headers and body disagree.

Removing protocol state does not prevent an application from keeping state. A tool can mint an explicit handle such as `basket_id` or `browser_id`, then the model can pass that value to later tools as an ordinary argument. In practice, we’ve found this pattern (the model threading an identifier from one tool call to the next) to be more than just a workable substitute for session state. It’s often a more powerful one. The model can compose handles across tools, reason about them, and hand them off between steps. The protocol no longer manages that state for you, but it doesn’t prevent you from managing it yourself.

Server-to-client requests are rebuilt around the same rule. A server may ask for something mid-call, such as confirmation, only while it is actively processing a client request. The client receives an `InputRequiredResult`, gathers the answer, and re-issues the original call with `inputResponses` and the echoed `requestState`. Because the needed state travels in the payload, any server instance can handle the retry.

List and resource-read results now include `ttlMs` and `cacheScope`, so clients know how long a `tools/list` response remains fresh and whether it can be shared. W3C Trace Context propagation in `_meta` fixes the names for `traceparent`, `tracestate`, and `baggage`, allowing a tool call to appear as one trace across the host, SDK, MCP server, and downstream services.

## Extensions get a place to grow

Extensions existed in the 2025-11-25 release without a formal process. SEP-2133 gives them reverse-DNS identifiers, capability negotiation, independent versions, delegated maintainers, and an Extensions Track that can move an experiment toward official status.

This release includes MCP Apps. A server can provide an interactive HTML interface for a host to render in a sandboxed iframe. Tools declare their UI templates ahead of time, allowing hosts to prefetch, cache, and review them before execution. The interface still communicates through MCP’s JSON-RPC foundation, so actions from the UI follow the same audit and consent path as direct tool calls.

Tasks leave the experimental core and become an extension. A server can answer `tools/call` with a task handle, while the client uses `tasks/get`, `tasks/update`, and `tasks/cancel` to drive the lifecycle. The server decides when a call should become a task after the client advertises support. `tasks/list` is removed because it cannot be scoped safely without sessions. Anyone using the experimental Tasks API from 2025-11-25 must migrate.

## Authorization and schemas move closer to practice

The authorization specification now requires clients to validate the `iss` parameter in authorization responses, a mitigation for mix-up attacks that matter in MCP’s single-client, many-server deployments. Clients declare their OpenID Connect `application_type` during Dynamic Client Registration, bind credentials to the issuing authorization server, and re-register when a resource moves to another issuer. The specification also clarifies refresh-token requests, scope accumulation during step-up, and the `.well-known` discovery suffix.

Three core features enter the new deprecation lifecycle: Roots, Sampling, and Logging. Roots should give way to tool parameters, resource URIs, or server configuration. Sampling should use direct integration with LLM provider APIs. Logging has two replacements: `stderr` for stdio transports and OpenTelemetry for structured observability. These are annotation-only deprecations for now. The methods, types, and capability flags continue to work in this release and in every specification version published within a year of it. Removal requires a separate SEP.

Tool schemas now use full JSON Schema 2020-12. Input schemas still require an object at the root, but they can use `oneOf`, `anyOf`, `allOf`, conditionals, and references. Output schemas are unrestricted, and `structuredContent` may contain any JSON value. Implementations must not automatically dereference external `$ref` URIs and should bound schema depth and validation time. A missing-resource error also changes from MCP’s custom `-32002` to the JSON-RPC standard `-32602 Invalid Params`, so clients matching the old literal must update.

## A protocol that can change without breaking every deployment

This revision is a clean break because the transport and lifecycle changes needed one. The governance changes aim to make future breaks rarer. Every feature now has Active, Deprecated, and Removed stages, with at least twelve months between deprecation and the earliest possible removal. Extensions can stabilize as opt-in capabilities before entering the core specification. A Standards Track SEP cannot reach Final status until a matching scenario appears in the conformance suite, the same suite used to score official SDK tiers.

The release candidate was locked on May 21, 2026. The ten-week window before the July 28 final release is for SDK maintainers and client implementers to test real workloads; Tier 1 SDKs are expected to support the changes during it. The draft specification contains the full candidate, and the changelog will list every difference from 2025-11-25.

If you maintain an SDK or client, the immediate work is to run the candidate against real workloads before July 28 and ship support during that window. Tier 1 SDKs are expected to do so.
