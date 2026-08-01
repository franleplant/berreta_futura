---
source_ids:
- the-2026-07-28-mcp-specification-release-candida-1a1752b8
content_mode: faithful_synthesis
label: FAITHFUL SYNTHESIS
---

A remote MCP server that needed sticky sessions, a shared session store, and deep packet inspection at the gateway can now run behind a plain round-robin load balancer. That is the immediate effect of the `2026-07-28` release candidate on a production deployment, and it is the largest revision of the protocol since launch.

## The handshake and session are gone

The headline change is that MCP is now stateless at the protocol layer. The `initialize`/`initialized` handshake is removed. The protocol version, client info, and client capabilities once exchanged at connection time now travel in `_meta` on every request, and a new `server/discover` method lets clients fetch server capabilities up front. The `Mcp-Session-Id` header and the protocol-level session that came with it are also removed. With both gone, any MCP request can land on any server instance, and the sticky routing and shared session stores that horizontal deployments needed are no longer required at the protocol layer.

A stateless protocol still needs a way for servers to ask the client for something mid-call, such as an elicitation prompt. Server-initiated requests may now only be issued while the server is actively processing a client request, which earlier spec versions recommended and this one requires, so a user is never prompted out of nowhere. Instead of holding a Server-Sent Events stream open, the server returns an `InputRequiredResult` that the client answers by re-issuing the original call with the echoed `requestState`.

## Stateless protocol, stateful applications

Removing the protocol-level session does not mean your application has to be stateless. Servers that need to carry state across calls can do what HTTP APIs have always done: mint an explicit handle (a `basket_id`, a `browser_id`) from a tool and have the model pass it back as an ordinary argument on later calls. In practice, we've found this pattern (the model threading an identifier from one tool call to the next) to be more than just a workable substitute for session state. It's often a more powerful one. The model can compose handles across tools, reason about them, and hand them off between steps in ways that externally managed session state, hidden in transport metadata, never allowed. The protocol no longer manages that state for you, but it doesn't prevent you from managing it yourself.

## Routable, cacheable, traceable

Three smaller changes make the resulting traffic easier to operate. Streamable HTTP now requires `Mcp-Method` and `Mcp-Name` headers, so load balancers and rate-limiters can route on the operation without inspecting the body. List and resource read results carry `ttlMs` and `cacheScope`, modeled on HTTP `Cache-Control`, so clients know exactly how long a `tools/list` response is fresh and whether it is safe to share across users. And the `traceparent`, `tracestate`, and `baggage` key names are now fixed in the spec, so a tool call can show up as one span tree in an OpenTelemetry-compatible backend.

## Extensions become first-class

Extensions existed in `2025-11-25` but had no formal process behind them. They are now negotiated through an `extensions` map on client and server capabilities, live in their own `ext-*` repositories, and version independently of the specification, with a new Extensions Track in the SEP process to carry them from experimental to official.

Two official extensions ship with this release, and they arrived from opposite directions. MCP Apps lets servers ship interactive HTML interfaces that hosts render in a sandboxed iframe, declared as templates ahead of time so hosts can security-review them before anything runs, and the rendered UI talks back over the same JSON-RPC base protocol, so every UI-initiated action goes through the same audit and consent path as a direct tool call. Tasks went the other way: it shipped as an experimental core feature in the last release, and production use surfaced enough redesign that the right home for it is an extension rather than the specification. Its lifecycle is reshaped around the stateless model, and `tasks/list` is removed because it can't be scoped safely without sessions. Anyone who shipped against that experimental Tasks API will need to migrate.

## What you have to change now

Roots, Sampling, and Logging are deprecated under the new feature lifecycle policy, each with a replacement:

- Roots: tool parameters, resource URIs, or server configuration.
- Sampling: direct integration with LLM provider APIs.
- Logging: `stderr` for stdio transports, OpenTelemetry for structured observability.

These are annotation-only deprecations. The methods, types, and capability flags keep working in this release and in every specification version published within a year of it, and removing any of them will require a separate SEP.

Other changes need attention sooner. Clients must now validate the `iss` parameter on authorization responses per RFC 9207, a low-cost mitigation for a class of mix-up attack that MCP's single-client, many-server deployment pattern makes more prevalent; in a future version, clients will be expected to reject responses that omit `iss`, so authorization servers should begin supplying it now if they don't already. And the error code for a missing resource changes from the MCP-custom `-32002` to the JSON-RPC standard `-32602 Invalid Params`. If your client matches on the literal `-32002` value, update it.

## How the protocol evolves from here

This release contains breaking changes. We don't intend for that to be the norm. Three governance SEPs are designed so that future revisions can evolve the protocol without breaking core capabilities. The feature lifecycle policy gives every feature an Active, Deprecated, and Removed lifecycle with at least twelve months between deprecation and the earliest possible removal. New capabilities can stabilize as opt-in extensions before, if ever, moving into the specification. And a Standards Track SEP can no longer reach Final status until a matching scenario lands in the conformance suite that the new SDK tier system scores official SDKs against.

The release candidate is locked as of May 21, 2026, and the final specification will be published on July 28, 2026. The ten weeks between are for SDK maintainers and client implementers to validate the changes against real workloads. The stateless rework is the kind of foundational change that needed a clean break. With it landed, our expectation is that implementers targeting `2026-07-28` will be able to adopt future revisions without rewriting their transport or lifecycle code.
