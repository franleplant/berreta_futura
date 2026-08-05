---
source_ids:
- the-2026-07-28-mcp-specification-release-candida-1a1752b8
content_mode: faithful_synthesis
label: FAITHFUL SYNTHESIS
---

A remote MCP server that once needed sticky routing, a shared session store, and inspection of request bodies can now sit behind a plain round-robin load balancer. `MCP-Protocol-Version` names the protocol version; `Mcp-Method` and `Mcp-Name` identify the operation; `ttlMs` tells clients how long a cached response remains fresh.

The release candidate for the 2026-07-28 specification removes the protocol-level session. Under the 2025-11-25 protocol, a client established a session and received an `Mcp-Session-Id`; later requests had to return to the instance that issued it. The new protocol removes that handshake and header. Protocol version, client information, and capabilities travel in `_meta` on each request, while `server/discover` lets a client fetch server capabilities when it needs them. Any request can now reach any server instance.

The application may still need state. A tool can return `basket_id: "b_123"`, and the model can pass that handle to `add_item` on a later call. The protocol no longer manages that state for you, but it doesn’t prevent you from managing it yourself. In practice, we’ve found this pattern more than a workable substitute for session state. The model can compose handles across tools, reason about them, and hand them off between steps in ways that externally managed session state, hidden in transport metadata, never really allowed.

The same stateless design changes how a server asks for input during a call. Server-initiated requests may only happen while the server is actively processing a client request. A user is never prompted out of nowhere, and every elicitation traces back to something they (or their agent) started. Instead of holding an SSE stream open, the server returns an `InputRequiredResult` with a `resultType`, an `inputRequests` entry describing the prompt and its schema, and a `requestState` value:

```json
{
  "resultType": "input_required",
  "inputRequests": {
    "confirm": {
      "type": "elicitation",
      "message": "Delete 3 files?",
      "schema": { "type": "boolean" }
    }
  },
  "requestState": "eyJzdGVwIjoxLCJmaWxlcyI6WyJhIiwiYiIsImMiXX0="
}
```

The client gathers the answer and re-issues the original call with `inputResponses` and the echoed state. Because the information is in the payload, any server instance can handle the retry.

Three operational changes follow. Streamable HTTP now requires `Mcp-Method` and `Mcp-Name` headers, so load balancers, gateways, and rate limiters can route on the operation without inspecting the body; requests are rejected when the headers and body disagree. List and resource-read results carry `ttlMs` and `cacheScope`, telling clients how long a response is fresh and whether it is safe to share. W3C Trace Context names such as `traceparent`, `tracestate`, and `baggage` are fixed in `_meta`, allowing one trace to follow a tool call through the host, client SDK, server, and downstream services.

Extensions now have a formal home. Each gets a reverse-DNS name, such as a domain-like identifier owned by its author, and client and server capabilities negotiate it through an `extensions` map. Extensions live in separate repositories with delegated maintainers and can version independently of the specification. This release includes two official extensions, including MCP Apps, which let a server provide an interactive HTML interface for a sandboxed iframe. Hosts can prefetch, cache, and security-review the declared templates, while UI actions still travel through the same JSON-RPC protocol and audit path as direct tool calls.

Tasks also leave the core specification and become an extension. A server may answer `tools/call` with a task handle, while the client drives the lifecycle with `tasks/get`, `tasks/update`, and `tasks/cancel`. The server decides when a call should become a task after the client advertises support. `tasks/list` is removed because it cannot be scoped safely without sessions. Anyone using the experimental Tasks API from 2025-11-25 will need to migrate.

The release includes breaking changes beyond transport and lifecycle. Authorization clients must validate `iss`, the issuer identifier in an authorization response, and declare their OpenID Connect `application_type`, which tells the authorization server whether the client is a web, native, or other application. Clients bind registered credentials to the issuing authorization server and re-register when a resource migrates between authorization servers. The specification also describes refresh-token requests for OpenID Connect-style servers, scope accumulation during step-up authorization, and the `.well-known` discovery suffix.

Tool schemas now use full JSON Schema 2020-12. Input schemas still require an object at the root, but may use composition, conditionals, and references such as `oneOf`, `anyOf`, `allOf`, `$ref`, and `$defs`. Output schemas are unrestricted, and `structuredContent` may contain any JSON value. Implementations must not automatically dereference external `$ref` URIs, and they must bound schema depth and validation time. A missing-resource error changes from MCP’s `-32002` to the JSON-RPC standard `-32602 Invalid Params`, so clients matching the old literal must update.

Three older features are deprecated: Roots, Sampling, and Logging. Their methods, types, and capability flags continue to work in this release and in every specification version published within a year of it. Removal requires another SEP. Roots can be replaced with tool parameters, resource URIs, or server configuration; Sampling with direct provider integrations; and Logging with `stderr` for stdio transports or OpenTelemetry for structured observability.

This release contains breaking changes. The maintainers do not intend that to become normal. The feature lifecycle policy sets Active, Deprecated, and Removed stages with at least twelve months between deprecation and the earliest possible removal. The Extensions framework gives new capabilities an opt-in path, and a Standards Track SEP cannot reach Final status until a matching scenario appears in the conformance suite. The stateless rework in this release is the kind of foundational change that needed a clean break. With it landed, implementers targeting 2026-07-28 are expected to adopt future revisions without rewriting their transport or lifecycle code.
