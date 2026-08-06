---
source_ids:
- the-2026-07-28-mcp-specification-release-candida-1a1752b8
content_mode: faithful_synthesis
label: FAITHFUL SYNTHESIS
---

The release candidate for `2026-07-28` is out; the final lands July 28. MCP is now stateless at the protocol layer: the `initialize` handshake and the `Mcp-Session-Id` header are gone, and every request carries its own protocol version, client info, and capabilities in `_meta`. Any instance can answer any request. Extensions become formal, with two official ones — MCP Apps and Tasks. Authorization moves closer to how OAuth and OpenID Connect are actually deployed. Roots, Sampling, and Logging are deprecated, and keep working for at least a year. Tool schemas get full JSON Schema 2020-12. There are breaking changes. There is now a policy meant to make that rare.

## The session is gone

Six SEPs did it. SEP-2575 removes the `initialize`/`initialized` handshake; what was exchanged once now rides on each request, and `server/discover` fetches server capabilities for clients that want them up front. SEP-2567 removes the session header. What needed sticky routing and a shared store runs behind round-robin.

## State you keep yourself

Stateless protocol, stateful application. A tool mints a handle — `basket_id`, `browser_id` — and the model passes it back as an ordinary argument. We have found this better than what it replaces. State kept in transport metadata was invisible; a handle can be composed, reasoned about, threaded from one call to the next. The protocol no longer holds the thread for you. It hands you the thread.

## Asking mid-call

Servers may issue requests only while processing a client request (SEP-2260) — recommended before, required now. Nothing prompts a user out of nowhere. Instead of holding an SSE stream open, the server returns an `InputRequiredResult` with its `inputRequests` and an opaque `requestState` (SEP-2322). The client answers and re-issues the call. Everything the retry needs is in the payload, so any instance can take it.

## Traffic you can operate

`Mcp-Method` and `Mcp-Name` headers are required, so gateways route without reading bodies; servers reject headers that contradict the body (SEP-2243). List and resource reads carry `ttlMs` and `cacheScope`, modeled on `Cache-Control` (SEP-2549). W3C Trace Context key names are fixed in `_meta` (SEP-414), so one tool call is one span tree.

## Extensions

SEP-2133 gives extensions reverse-DNS IDs, negotiation through an `extensions` capability map, their own repositories and maintainers, and versions independent of the spec.

MCP Apps (SEP-1865): servers ship HTML interfaces, hosts render them in a sandboxed iframe. Templates are declared ahead of time so hosts can prefetch and review them, and every UI action takes the same consent path as a tool call.

Tasks leaves the core. A server answers `tools/call` with a task handle; the client drives `tasks/get`, `tasks/update`, `tasks/cancel`. The server decides what becomes a task. `tasks/list` is gone — without sessions it cannot be scoped safely. Anyone on the experimental API must migrate.

## Authorization

Clients validate `iss` per RFC 9207 (SEP-2468); later versions will reject responses without it. Clients declare `application_type` at registration (SEP-837), so a CLI client is no longer defaulted to `"web"` and refused its localhost redirect. Credentials bind to the issuer and re-register on migration (SEP-2352). Refresh tokens, step-up scope accumulation, and the `.well-known` suffix are documented (SEP-2207, 2350, 2351).

## Deprecations and schemas

Roots, Sampling, Logging: annotation-only, under SEP-2577. Use tool parameters or resource URIs; call provider APIs directly; use stderr or OpenTelemetry. They work in this release and in every version published within a year of it. Removal needs its own SEP.

Tool `inputSchema` and `outputSchema` become full JSON Schema 2020-12 (SEP-2106): composition, conditionals, `$ref` and `$defs`. Input keeps its object root; output is unrestricted, and `structuredContent` can be any JSON value. Do not auto-dereference external `$ref`s; bound depth and validation time. Missing resources now return `-32602` rather than `-32002` (SEP-2164) — update anything matching the old literal.

## From here

The lifecycle policy gives every feature at least twelve months between deprecation and removal. Extensions let capabilities stabilize outside the spec. A Standards Track SEP cannot reach Final without a conformance scenario (SEP-2484), against which the SDK tier system scores official SDKs.

The candidate is locked as of May 21. Ten weeks are for validation against real workloads; Tier 1 SDKs are expected to ship support inside that window. Problems go to the specification repository, implementation questions to the Working Group channels on Discord.
