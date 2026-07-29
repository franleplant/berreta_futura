---
source_id: the-2026-07-28-mcp-specification-release-candida-1a1752b8
content_mode: faithful_synthesis
label: FAITHFUL SYNTHESIS
---

The release candidate for the July 28, 2026 Model Context Protocol specification is the largest revision since launch. It introduces a stateless core, first-class extensions, long-running Tasks, MCP Apps, authorization hardening, a formal deprecation policy, and full JSON Schema for tools.

The practical effect is operational. A remote MCP server that once required sticky sessions and a shared session store can run behind an ordinary round-robin load balancer. Gateways can route requests from headers. Clients can cache list responses for an explicit period.

## A stateless protocol

In the 2025 specification, a Streamable HTTP client initialized a session, received an `Mcp-Session-Id`, and attached that identifier to later requests. The session pinned traffic to the server instance that created it or required shared state across instances.

In the new protocol, a tool call is self-contained. The protocol version, client information, and relevant capabilities travel in `_meta` on each request. The initialization handshake and protocol-level session are gone.

Clients can call `server/discover` when they need the server's versions and capabilities before making another request. Any request can land on any compatible server instance.

This does not require applications to forget state. A tool can create an explicit handle such as `basket_id` or `browser_id`, return it to the model, and accept it as an ordinary argument on the next call.

Explicit handles are often more useful than transport metadata. The model can see them, compose them across tools, reason about ownership, and pass them between steps. State remains possible, but it becomes application data instead of an invisible property of a connection.

## Server requests without a permanent channel

Servers still need to request information from the client during a tool call. An operation may require confirmation, credentials, or another user choice.

The new rule is that a server can initiate such a request only while processing a client request. A user should never receive an unrelated prompt from a dormant server.

Multi Round-Trip Requests replace the assumption of one persistent stream. The server returns an `input_required` result containing one or more input requests and an opaque `requestState`. The client gathers answers, repeats the original operation with `inputResponses`, and echoes the state.

Any server instance can process the retry because the payload carries everything required to continue.

## Routable, cacheable, traceable

Streamable HTTP now requires `Mcp-Method` and `Mcp-Name` headers. A load balancer can route and rate-limit `tools/call` for `search` without parsing the JSON-RPC body. Servers reject a request when headers and body disagree.

List and resource-read results can declare `ttlMs` and `cacheScope`. A client knows how long a `tools/list` response remains fresh and whether it can be shared across users. Servers no longer need a long-lived event stream merely to keep every catalog current.

Trace context moves through standard `traceparent`, `tracestate`, and baggage headers. One tool call can appear inside the same OpenTelemetry trace as the host action and downstream service calls.

These changes make MCP traffic legible to existing HTTP infrastructure rather than demanding protocol-specific gateways.

## Extensions move independently

The core protocol is smaller because optional capabilities can evolve as extensions with delegated maintainers and independent versions.

MCP Apps is an official extension for server-rendered interfaces. A server can return an interactive UI where plain text or structured data is not enough.

Tasks also graduates into an extension. It supports long-running work that can be polled and retrieved after the initiating request. The earlier core task lifecycle is removed because it could not be scoped safely without sessions.

The separation lets the core remain stable while UI and asynchronous-work patterns evolve faster.

## Authorization hardening

The authorization revisions align MCP more closely with real OAuth and OpenID Connect deployments.

Resource indicators become stricter so tokens are issued for the intended server. Authorization-server metadata must identify the issuer consistently. Client registration can use standards-based mechanisms instead of assuming every server operates its own custom registry.

The specification also handles resources that migrate between authorization servers and documents how clients should request refresh tokens from OpenID Connect-style providers.

The direction is clear: MCP should fit existing identity systems instead of inventing a parallel one.

## Deprecations and schemas

Roots, Sampling, and Logging are deprecated in the core.

Roots can be replaced by tool parameters, resource URIs, or server configuration. Sampling can move to direct integration with model-provider APIs. Logging can use standard observability infrastructure.

These are annotation-only deprecations in this release. Methods and capability flags remain available while implementations migrate.

Tool schemas now use full JSON Schema 2020-12. Servers and clients can express richer validation rules, but they should treat schemas as untrusted input, bound recursion and validation time, and avoid automatically resolving remote references.

A missing resource now uses the standard JSON-RPC method-not-found family rather than the MCP-specific `-32002` value. Implementations that match the literal old code need to change.

## How the protocol evolves

Breaking changes should become rarer. Features move through Active, Deprecated, and Removed states, with at least twelve months between deprecation and removal. SDK tiers define support expectations for official implementations.

The release candidate opens a ten-week window for SDK maintainers, client authors, server operators, and gateway vendors to validate behavior against the prior specification. The final specification ships on July 28, 2026.

The durable architectural change is not one header or method. MCP is moving toward an ordinary stateless web protocol with explicit application state, standard routing, standard caching, standard tracing, and optional features that can evolve outside the core.
