---
source_ids:
- the-2026-07-28-mcp-specification-release-candida-1a1752b8
content_mode: faithful_synthesis
label: FAITHFUL SYNTHESIS
---

A remote MCP server that previously needed sticky sessions, a shared session store, and deep packet inspection at its gateway can now run behind a plain round-robin load balancer. Traffic can route on an `Mcp-Method` header, and clients can cache `tools/list` responses for as long as the server’s `ttlMs` permits. For an implementer, start with the transport: change deployment and request handling around a stateless protocol core, move application state and long-running work into explicit handles or extensions, and separate immediate migrations from changes with a grace period. The `2026-07-28` release candidate is the largest revision since launch. The candidate was locked on May 21, 2026, and the final specification ships July 28.

## Change deployment and request handling

In `2025-11-25`, calling a tool over Streamable HTTP means establishing a session first. The exchange begins with this request:

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

The server returns an `Mcp-Session-Id`, and every later `tools/call` carries it. In `2026-07-28`, that `tools/call` is self-contained:

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

The `initialize`/`initialized` handshake and protocol-level session are gone. Protocol version, client information, and capabilities now travel in `_meta` on every request, while `server/discover` lets a client fetch server capabilities up front. Any instance can handle any request.

Streamable HTTP now requires `Mcp-Method` and `Mcp-Name` headers. Load balancers, gateways, and rate limiters can route without inspecting the body, and servers reject disagreement between headers and body. List and resource-read results carry `ttlMs` and `cacheScope`, so clients know freshness and whether a result is safe to share. W3C Trace Context propagation in `_meta` fixes the names `traceparent`, `tracestate`, and `baggage`. A trace can follow a call from the host application through the client SDK, MCP server, and downstream services as one span tree in an OpenTelemetry-compatible backend.

## Keep application state and retries explicit

Removing the protocol-level session does not make an application stateless. A tool can mint an explicit handle such as `basket_id`, and the model passes it as an ordinary argument on later calls. The protocol no longer manages that state for you, but it doesn’t prevent you from managing it yourself. In practice, we’ve found this pattern (the model threading an identifier from one tool call to the next) to be more than just a workable substitute for session state. It’s often a more powerful one. The model can compose handles across tools, reason about them, and hand them off between steps in ways that externally managed session state, hidden in transport metadata, never really allowed.

Server-initiated requests may now be issued only while actively processing a client request (SEP-2260). A user is never prompted out of nowhere, and every elicitation traces back to something they (or their agent) started. Multi Round-Trip Requests (SEP-2322) no longer hold an SSE stream open. Instead, the server returns an `InputRequiredResult` such as:

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

The client gathers the answers and re-issues the original call with `inputResponses` and the echoed `requestState`. Because the context is in the payload, any server instance can handle the retry.

## Migrate calls, authorization, and schemas

Long-running work has an immediate migration. Tasks shipped as an experimental core feature in `2025-11-25`. Production use surfaced enough redesign that the right home is an extension rather than the specification. The Tasks extension fits the stateless model: a server can answer `tools/call` with a task handle, and the client drives it with `tasks/get`, `tasks/update`, and `tasks/cancel`. Task creation is server-directed. The client advertises the extension, and the server decides when a call runs as a task. `tasks/list` is removed because it cannot be scoped safely without sessions. Anyone who shipped against the experimental API must migrate.

Authorization now follows OAuth 2.0 and OpenID Connect deployments more closely. Clients must validate the `iss` parameter in authorization responses. It identifies the authorization server, giving the client a low-cost check against a response from the wrong one, a mix-up attack more prevalent in MCP’s single-client, many-server pattern. In a future version, clients will be expected to reject responses that omit it, so authorization servers should supply it now. Dynamic Client Registration carries the OpenID Connect `application_type`, avoiding the case where a desktop or CLI client is treated as a `web` client and its localhost redirect is rejected. Clients bind credentials to the issuing server’s `issuer` and re-register when a resource moves. The specification also clarifies refresh-token requests, scope accumulation during step-up, and the `.well-known` discovery suffix.

Schema and error handling bring another compatibility check. Tool `inputSchema` and `outputSchema` now use full JSON Schema 2020-12. Input schemas keep a `type: "object"` root but allow `oneOf`, `anyOf`, `allOf`, conditionals, `$ref`, and `$defs`. Output schemas are unrestricted, and `structuredContent` may be any JSON value. Implementations must not auto-dereference external `$ref` URIs and should bound schema depth and validation time. A missing-resource error changes from MCP’s `-32002` to JSON-RPC’s `-32602 Invalid Params`, so clients matching the old literal must update.

## Use extensions and deprecation windows

Extensions now have a formal path. They use reverse-DNS IDs, negotiate through an `extensions` map in client and server capabilities, live in `ext-*` repositories with delegated maintainers, and version independently. An Extensions Track can move a feature from experimental to official.

MCP Apps lets servers ship interactive HTML in a sandboxed iframe. Tools declare UI templates ahead of execution, so hosts can prefetch, cache, and security-review them. The UI talks to the host over the same JSON-RPC base protocol, keeping every UI action on the audit and consent path of a direct tool call.

Three core features are annotation-only deprecations. Roots, the feature represented by root declarations, moves toward tool parameters, resource URIs, or server configuration. Sampling, which lets MCP call an LLM provider, moves toward direct provider integration. Logging, which emits log output, moves to `stderr` for stdio transports and OpenTelemetry for structured observability. Their methods, types, and capability flags continue to work in this release and every specification version published within a year of it. Removing any of them requires a separate SEP.

The ten-week period between the May 21 lock and the July 28 final release is for SDK maintainers and client implementers to validate the changes against real workloads. Tier 1 SDKs are expected to ship support during that window.

## Build on the compatibility suite

This release contains breaking changes. We don’t intend for that to be the norm. The feature lifecycle policy gives every feature Active, Deprecated, and Removed states, with at least twelve months between deprecation and the earliest possible removal. Extensions let new capabilities ship as opt-in work and stabilize there before, if ever, moving into the specification. A Standards Track SEP cannot reach Final until a matching scenario lands in the conformance suite, the same suite the SDK tier system uses to score official SDKs.

With the stateless rework landed, and with deprecation windows and extensions as the standard tools going forward, our expectation is that implementers targeting `2026-07-28` will be able to adopt future revisions without rewriting their transport or lifecycle code.
