---
source_ids:
- the-2026-07-28-mcp-specification-release-candida-1a1752b8
content_mode: faithful_synthesis
label: FAITHFUL SYNTHESIS
---

MCP `2026-07-28` drops the session. No `initialize` handshake, no `Mcp-Session-Id`: every request carries what it needs, so any instance can serve it and a plain round-robin balancer suffices. Extensions become a formal system, with two official ones — MCP Apps and Tasks. Authorization moves closer to how OAuth and OpenID Connect are actually deployed. Roots, sampling and logging are deprecated but still work. Tool schemas become full JSON Schema 2020-12. The candidate is locked as of 21 May 2026; the final ships 28 July 2026. It breaks things, deliberately, once.

## The session is gone

Six SEPs do the work. The handshake is removed (SEP-2575); protocol version, client info and capabilities now ride in `_meta` on every request, and `server/discover` fetches server capabilities when a client wants them up front. The session header is removed (SEP-2567). Sticky routing and shared session stores are no longer required by the protocol.

Stateless protocol, not stateless application. A tool mints a handle — `basket_id`, `browser_id` — and the model passes it back as an ordinary argument. The state was always there; it simply lived in transport metadata, where the model could not see or reason about it. Now it can compose handles across tools and hand them between steps.

## Asking the client something mid-call

A server may only initiate a request while processing a client request (SEP-2260). Recommended before; required now. Nobody is prompted out of nowhere.

Instead of holding an SSE stream open, the server returns an `InputRequiredResult` carrying `inputRequests` and an opaque `requestState` (SEP-2322). The client collects the answers and re-issues the original call with `inputResponses` and the echoed state. Any instance can pick it up.

## Traffic you can operate

`Mcp-Method` and `Mcp-Name` headers are required, so gateways route without reading bodies; servers reject headers that contradict the body (SEP-2243). List and resource-read results carry `ttlMs` and `cacheScope`, modelled on `Cache-Control` (SEP-2549). Trace Context key names — `traceparent`, `tracestate`, `baggage` — are fixed in `_meta`, so one span tree spans host, client, server and downstream (SEP-414).

## Extensions

Reverse-DNS IDs, negotiated through an `extensions` map, kept in their own repositories, versioned apart from the specification (SEP-2133).

**MCP Apps** (SEP-1865): servers ship HTML rendered in a sandboxed iframe. Templates are declared ahead, so hosts can prefetch, cache and review them. UI actions travel the same JSON-RPC path, and the same consent path, as any tool call.

**Tasks** leaves core for an extension. A `tools/call` may return a task handle driven by `tasks/get`, `tasks/update`, `tasks/cancel`. Creation is server-directed. `tasks/list` is gone — it cannot be scoped safely without sessions. Anyone on the experimental API must migrate.

## Authorization

Validate `iss` on authorization responses, per RFC 9207 (SEP-2468); future versions will expect clients to reject responses that omit it. Declare `application_type` at registration, so CLI and desktop clients stop being defaulted to `"web"` and refused their localhost redirect (SEP-837). Bind credentials to the issuer and re-register on migration (SEP-2352). Refresh tokens (SEP-2207), step-up scope accumulation (SEP-2350) and the `.well-known` suffix (SEP-2351) are clarified.

## Deprecations and schemas

Roots, sampling and logging are deprecated (SEP-2577) — annotation only. They work in this release and in every version published within a year of it; removal needs its own SEP. Replacements: tool parameters or server configuration; direct LLM provider APIs; stderr and OpenTelemetry.

Tool `inputSchema` and `outputSchema` become full JSON Schema 2020-12 (SEP-2106): composition, conditionals, `$ref`. Inputs keep an object root; outputs are unrestricted and `structuredContent` may be any JSON value. Do not dereference external `$ref` URIs; bound depth and validation time. Missing-resource errors change from `-32002` to `-32602`; if you match the literal, fix it (SEP-2164).

## Why this should be the last break

Every feature now has an Active, Deprecated, Removed lifecycle with at least twelve months between the last two. New capabilities can ship as opt-in extensions and stabilise there. A Standards Track SEP cannot reach Final without a matching conformance scenario (SEP-2484) — the same suite that scores official SDKs.

Ten weeks stand between the candidate and the final for validation against real workloads; Tier 1 SDKs are expected to ship support inside them. Problems go to the specification repository, implementation questions to the Working Group channels.
