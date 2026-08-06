---
source_ids:
- the-2026-07-28-mcp-specification-release-candida-1a1752b8
content_mode: faithful_synthesis
label: FAITHFUL SYNTHESIS
---

MCP `2026-07-28` is stateless. The handshake and the session header are gone; each request carries what it needs, so any server instance can answer it. Extensions are now a formal framework, and it ships with two: MCP Apps and Tasks. Authorization moves closer to ordinary OAuth and OpenID Connect. Roots, Sampling and Logging are deprecated but still work. Tool schemas get full JSON Schema 2020-12. There are breaking changes. The candidate is locked as of May 21, 2026; the final publishes July 28.

## The session is gone

`initialize`/`initialized` is removed (SEP-2575). Protocol version, client info and client capabilities now ride in `_meta` on every request, and `server/discover` fetches server capabilities when a client wants them up front. `Mcp-Session-Id` is removed with it (SEP-2567). A call is one self-contained request:

```http
POST /mcp HTTP/1.1
MCP-Protocol-Version: 2026-07-28
Mcp-Method: tools/call
Mcp-Name: search
```

Sticky routing and shared session stores are no longer required. Round-robin is enough.

## State did not vanish; it changed hands

Servers that need continuity mint a handle from a tool — a `basket_id`, a `browser_id` — and the model passes it back as an ordinary argument. The thread is held by the model, in view, rather than hidden in transport metadata.

## Asking the client for something

Server-initiated requests may only be issued while the server is processing a client request (SEP-2260); a recommendation becomes a rule. Instead of holding an SSE stream open, the server returns an `InputRequiredResult` carrying `inputRequests` and an opaque `requestState` (SEP-2322). The client collects the answers and re-issues the call with `inputResponses` and the echoed state. Any instance can pick it up.

## Traffic you can operate

`Mcp-Method` and `Mcp-Name` headers are required, so gateways route without reading bodies; servers reject headers that disagree with the body (SEP-2243). List and resource-read results carry `ttlMs` and `cacheScope`, modelled on `Cache-Control` (SEP-2549). W3C Trace Context in `_meta` is documented, fixing `traceparent`, `tracestate` and `baggage` (SEP-414).

## Extensions

Reverse-DNS IDs, negotiated through an `extensions` capability map, living in `ext-*` repositories with delegated maintainers and independent versions (SEP-2133). MCP Apps lets servers ship HTML rendered in a sandboxed iframe, templates declared ahead so hosts can prefetch and review them; UI actions take the same consent path as a tool call (SEP-1865). Tasks leaves the core: `tools/call` may return a task handle driven by `tasks/get`, `tasks/update`, `tasks/cancel`. Creation is server-directed. `tasks/list` is removed — it cannot be scoped safely without sessions. Anyone on the experimental API must migrate.

## Authorization

Clients validate `iss` per RFC 9207 (SEP-2468); expect a future version to reject responses without it. Clients declare `application_type` at Dynamic Client Registration, so a CLI is not handed a `"web"` default that rejects its localhost redirect (SEP-837), and bind credentials to the issuer, re-registering when a resource moves (SEP-2352). Refresh tokens (SEP-2207), step-up scope accumulation (SEP-2350) and the `.well-known` suffix (SEP-2351) are clarified.

## Deprecated, not removed

| Feature | Replacement |
|---|---|
| Roots | Tool parameters, resource URIs, server configuration |
| Sampling | Direct LLM provider APIs |
| Logging | stderr for stdio; OpenTelemetry for observability |

Annotations only. They work here and in every version published within a year; removal needs its own SEP under the lifecycle policy (SEP-2577).

## Schemas and one error code

`inputSchema` and `outputSchema` become full JSON Schema 2020-12 (SEP-2106). Inputs keep an object root but gain `oneOf`, `anyOf`, `allOf`, conditionals, `$ref` and `$defs`. Outputs are unrestricted, and `structuredContent` may be any JSON value. Do not auto-dereference external `$ref`; bound depth and validation time. A missing resource now returns `-32602 Invalid Params` instead of `-32002` (SEP-2164) — if you match the literal, change it.

## From here

Every feature gets Active, Deprecated and Removed, with twelve months at minimum between the last two. New capabilities can ship as opt-in extensions and settle there. A Standards Track SEP cannot reach Final without a matching conformance scenario (SEP-2484) — the suite that also scores official SDKs. Ten weeks remain for validation; Tier 1 SDKs are expected to ship support inside them. The candidate is in the draft specification, with a changelog against `2025-11-25`. Problems go to issues in the specification repository; implementation questions go faster in the Working Group channels on the contributor Discord.
