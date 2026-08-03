---
source_ids:
- the-2026-07-28-mcp-specification-release-candida-1a1752b8
content_mode: faithful_synthesis
label: FAITHFUL SYNTHESIS
---

`Mcp-Session-Id` does not exist in the `2026-07-28` release candidate. Neither does the `initialize` handshake, and with them goes the protocol-level session that pinned every request to whichever server instance issued it. A remote MCP server that previously needed sticky sessions, a shared session store, and deep packet inspection at the gateway can now run behind a plain round-robin load balancer.

The protocol version, client info and client capabilities once exchanged at connection time now travel in `_meta` on every request, and a new `server/discover` method lets clients fetch server capabilities when they need them up front. The Streamable HTTP transport now requires `Mcp-Method` and `Mcp-Name` headers, so a gateway or a rate-limiter can route on the operation without inspecting the body, and servers reject requests where the headers and the body disagree. List and resource read results carry `ttlMs` and `cacheScope`, modeled on HTTP `Cache-Control`, so a client knows exactly how long a `tools/list` response is fresh and whether it is safe to share across users.

## Stateless protocol, stateful applications

Removing the protocol-level session does not mean your application has to be stateless. Servers that need to carry state across calls can do what HTTP APIs have always done: mint an explicit handle (a `basket_id`, a `browser_id`) from a tool and have the model pass it back as an ordinary argument on later calls. In practice, we've found this pattern (the model threading an identifier from one tool call to the next) to be more than just a workable substitute for session state. It's often a more powerful one. The model can compose handles across tools, reason about them, and hand them off between steps in ways that externally managed session state, hidden in transport metadata, never really allowed.

## Anyone who shipped against Tasks will need to migrate

Tasks shipped as an experimental core feature in `2025-11-25`, and production use surfaced enough redesign that the right home for it is an extension rather than the specification. The extension reshapes the lifecycle around the stateless model: a server can answer `tools/call` with a task handle, and the client drives it with `tasks/get`, `tasks/update` and `tasks/cancel`. Task creation is server-directed: the client advertises the extension and the server decides when a call should run as a task. We removed `tasks/list` because it can't be scoped safely without sessions.

A missing resource now returns the JSON-RPC standard `-32602 Invalid Params` rather than the MCP-custom `-32002`. If your client matches on the literal `-32002` value, update it.

We deprecated Roots, Sampling and Logging in the same release, and deprecated is all they are. The methods, types and capability flags keep working here and in every specification version published within a year of this one, and removing any of them will require a separate Specification Enhancement Proposal under the new lifecycle policy. The experimental Tasks API got no such year.

## Mix-up attacks and localhost redirects

MCP's single-client, many-server deployment pattern makes a class of mix-up attack more prevalent, and clients must now validate the `iss` parameter on authorization responses per RFC 9207 as a low-cost mitigation. In a future version, clients will be expected to reject responses that omit `iss`, so authorization servers should begin supplying it now if they don't already. Clients also declare their OpenID Connect `application_type` during Dynamic Client Registration, which ends the common case where an authorization server defaults a desktop or CLI client to `"web"` and rejects its localhost redirect URI.

## What the break buys

This release contains breaking changes. We don't intend for that to be the norm. A Standards Track SEP can no longer reach Final status until a matching scenario lands in the conformance suite, the same suite the new SDK tier system scores official SDKs against, and a capability like Tasks can ship and stabilize as an extension before, if ever, moving into the specification.

The release candidate is locked as of May 21, 2026, and the final specification ships on July 28. The ten weeks between are for SDK maintainers and client implementers to validate the changes against real workloads, and Tier 1 SDKs are expected to ship support inside it. The stateless rework is the kind of foundational change that needed a clean break. Our expectation is that implementers who target `2026-07-28` will not have to rewrite their transport or lifecycle code again.
