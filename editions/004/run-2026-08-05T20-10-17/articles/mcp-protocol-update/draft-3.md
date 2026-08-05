---
source_ids:
- the-2026-07-28-mcp-specification-release-candida-1a1752b8
content_mode: faithful_synthesis
label: FAITHFUL SYNTHESIS
---

A remote MCP server that previously needed sticky sessions, a shared session store, and deep packet inspection at its gateway can now run behind a plain round-robin load balancer. Traffic can route on an `Mcp-Method` header, and clients can cache `tools/list` responses for the server’s `ttlMs` while consulting `cacheScope` before sharing them. For an implementer, this is a deployment migration first: make requests independently routable, keep application state in explicit handles, and use extensions and deprecation windows to stage the rest. The candidate was locked on May 21, 2026; the final specification ships July 28 after ten weeks of validation.

## Change deployment and request handling

In `2025-11-25`, calling a tool over Streamable HTTP means establishing a session first. Keep the opening server’s search call in view:

```http
POST /mcp HTTP/1.1
Content-Type: application/json

{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "initialize",
  "params": {
    "protocolVersion": "2025-11-25",
    "capabilities": {},
    "clientInfo": {
      "name": "my-app",
      "version": "1.0"
    }
  }
}
```

The server responds with an `Mcp-Session-Id`, and every subsequent request carries it, pinning the client to whichever instance issued it. In `2026-07-28`, the search call is self-contained and any server instance can handle it:

```http
POST /mcp HTTP/1.1
MCP-Protocol-Version: 2026-07-28
Mcp-Method: tools/call
Mcp-Name: search
Content-Type: application/json

{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/call",
  "params": {
    "name": "search",
    "arguments": {
      "q": "otters"
    },
    "_meta": {
      "io.modelcontextprotocol/clientInfo": {
        "name": "my-app",
        "version": "1.0"
      }
    }
  }
}
```

The `initialize`/`initialized` handshake is removed (SEP-2575). Protocol version, client information, and capabilities travel in `_meta` on every request, while `server/discover` lets clients fetch server capabilities when needed. SEP-2567 removes `Mcp-Session-Id` and its protocol session, so any instance can handle any request.

Streamable HTTP now requires both `Mcp-Method` and `Mcp-Name` headers (SEP-2243). Load balancers, gateways, and rate-limiters can route without inspecting the body, and servers reject requests where headers and body disagree. List and resource-read results carry `ttlMs` and `cacheScope` (SEP-2549), so clients know when a `tools/list` result is fresh and whether it is safe to share. W3C Trace Context propagation in `_meta` fixes the `traceparent`, `tracestate`, and `baggage` key names (SEP-414). A trace can follow a call from the host application through the client SDK, MCP server, and downstream services as one span tree in an OpenTelemetry-compatible backend.

## Keep application state and retries explicit

Removing the protocol-level session does not mean your application has to be stateless. A basket tool can mint an explicit handle, `basket_id`, and the model can pass it as an ordinary argument on later calls. The protocol no longer manages that state for you, but it doesn’t prevent you from managing it yourself. In practice, we’ve found this pattern (the model threading an identifier from one tool call to the next) to be more than just a workable substitute for session state. It’s often a more powerful one. The model can compose handles across tools, reason about them, and hand them off between steps in ways that externally managed session state, hidden in transport metadata, never really allowed.

Server-initiated requests may now be issued only while the server is actively processing a client request (SEP-2260). If this server needs to ask “Delete 3 files?” mid-call, Multi Round-Trip Requests (SEP-2322) return an `InputRequiredResult` instead of holding an SSE stream open:

```json
{
  "resultType": "input_required",
  "inputRequests": {
    "confirm": {
      "type": "elicitation",
      "message": "Delete 3 files?",
      "schema": {
        "type": "boolean"
      }
    }
  },
  "requestState": "eyJzdGVwIjoxLCJmaWxlcyI6WyJhIiwiYiIsImMiXX0="
}
```

The client gathers the answer and re-issues the original call with `inputResponses` and the echoed `requestState`:

```json
{
  "method": "tools/call",
  "params": {
    "inputResponses": {
      "confirm": true
    },
    "requestState": "eyJzdGVwIjox…"
  }
}
```

Everything needed for the retry is in the payload, so any server instance can pick it up.

## Migrate calls, authorization, and schemas

Long-running work on this same server has a new lifecycle. Tasks shipped as an experimental core feature in `2025-11-25`. Production use surfaced enough redesign that the right home for it is an extension rather than the specification. The Tasks extension reshapes the lifecycle around the stateless model. A server can answer `tools/call` with a task handle, and the client drives it with `tasks/get`, `tasks/update`, and `tasks/cancel`. Task creation is server-directed: the client advertises the extension, and the server decides when a call should run as a task. `tasks/list` is removed because it cannot be scoped safely without sessions. Anyone who shipped against the experimental Tasks API will need to migrate.

Authorization hardening gives clients another compatibility check. Clients must validate the `iss` parameter in authorization responses (SEP-2468). It identifies the authorization server, letting a client reject a response from the wrong one. That mix-up attack is more prevalent in MCP’s single-client, many-server pattern. In a future version, clients will be expected to reject responses that omit `iss`, so authorization servers should begin supplying it now. Dynamic Client Registration carries the OpenID Connect `application_type`, avoiding the case where a desktop or CLI client is treated as a `web` client and its localhost redirect is rejected. Clients bind credentials to the issuing server’s `issuer` and re-register when a resource moves.

Schema and error handling are a separate compatibility check. Tool `inputSchema` and `outputSchema` now use full JSON Schema 2020-12. Input schemas keep a `type: "object"` root but allow composition, conditionals, and references such as `oneOf`, `anyOf`, `allOf`, `$ref`, and `$defs`. Output schemas are unrestricted, and `structuredContent` may be any JSON value. Implementations must not auto-dereference external `$ref` URIs and should bound schema depth and validation time. A missing-resource error changes from MCP’s `-32002` to JSON-RPC’s `-32602 Invalid Params`, so clients matching the old literal must update.

## Use extensions and deprecation windows

Extensions now have a formal path. They use reverse-DNS IDs, negotiate through an `extensions` map in client and server capabilities, live in `ext-*` repositories with delegated maintainers, and version independently. An Extensions Track gives a feature a route from experimental to official.

MCP Apps (SEP-1865) lets the server ship interactive HTML interfaces that hosts render in a sandboxed iframe. Tools declare UI templates ahead of execution, so hosts can prefetch, cache, and security-review them. The rendered UI talks to the host over the same JSON-RPC base protocol, keeping every UI action on the audit and consent path of a direct tool call.

The release marks three core features as annotation-only deprecations. For Roots, root declarations can give way to tool parameters, resource URIs, or server configuration. Sampling lets MCP call an LLM provider today. Direct integration with that provider is the replacement. Logging emits log output. Stdio transports use `stderr`, while OpenTelemetry supplies structured observability. Their methods, types, and capability flags continue to work in this release and in every specification version published within a year of it. An implementer can keep those calls working while moving toward the replacements. Removing any of them requires a separate SEP.

During the ten-week candidate window, SDK maintainers and client implementers validate the changes against real workloads. Tier 1 SDKs are expected to ship support during that period.

## Build on the compatibility suite

This release contains breaking changes. We don’t intend for that to be the norm. The feature lifecycle policy gives every feature an Active, Deprecated, and Removed lifecycle, with at least twelve months between deprecation and the earliest possible removal. Extensions let new capabilities ship as opt-in work and stabilize there before, if ever, moving into the specification. A Standards Track SEP cannot reach Final until a matching scenario lands in the conformance suite, the same suite the SDK tier system uses to score official SDKs.

The stateless rework in this release is the kind of foundational change that needed a clean break. With it landed, and with deprecation windows and extensions as the standard tools going forward, our expectation is that implementers targeting `2026-07-28` will be able to adopt future revisions without rewriting their transport or lifecycle code.
