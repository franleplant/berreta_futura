---
source_ids:
- the-2026-07-28-mcp-specification-release-candida-1a1752b8
content_mode: faithful_synthesis
label: FAITHFUL SYNTHESIS
---

A remote MCP server that needed sticky sessions, a shared session store, and deep packet inspection at the gateway can now run behind a plain round-robin load balancer on a production deployment, route traffic on an Mcp-Method header, and let clients cache tools/list responses for as long as the server's ttlMs permits. The 2026-07-28 release candidate is the largest revision of the Model Context Protocol since launch.

## The handshake and the session are gone

Under the outgoing 2025-11-25 transport, a tool call opened with a handshake:

```
POST /mcp HTTP/1.1
Content-Type: application/json


{"jsonrpc":"2.0","id":1,"method":"initialize",
 "params":{"protocolVersion":"2025-11-25","capabilities":{},
           "clientInfo":{"name":"my-app","version":"1.0"}}}
```

The server answered with an Mcp-Session-Id that every later request had to carry, pinning the client to whichever instance had issued it. The initialize/initialized handshake is gone outright, removed by SEP-2575: protocol version, client info, and capabilities now travel in _meta on every request instead, and a new server/discover method lets a client fetch a server's capabilities up front when it needs them. Gone too, under SEP-2567, are the Mcp-Session-Id header and the session it created. A single self-contained request now carries an MCP-Protocol-Version header and an Mcp-Method header naming the operation, and any server instance can answer it. The sticky routing and shared session store that a horizontal deployment needed under the old handshake have no home in the protocol layer anymore.

## Stateless protocol, stateful applications

None of this makes a server itself stateless. A server that needs to carry state across calls does what an HTTP API has always done: a tool mints an explicit handle, a basket_id or a browser_id, and the model passes it back as an ordinary argument on the next call. "In practice, we've found this pattern (the model threading an identifier from one tool call to the next) to be more than just a workable substitute for session state. It's often a more powerful one," the maintainers write: the model can compose handles across tools, reason about them, and hand them off between steps in ways a session hidden in transport metadata never allowed. The protocol no longer manages that state, but nothing stops an application from managing it itself. The explicit handle just makes the state visible to the model instead of hidden away.

## Server-to-client requests, restructured

A stateless protocol still needs a way for a server to ask mid-call for something, an elicitation prompt, say. A server may now ask only while it's actively processing a request the client sent, a rule SEP-2260 promotes from recommendation to requirement: a user is never prompted out of nowhere, and every elicitation traces back to something they, or their agent, started. How the prompt travels changes too, under SEP-2322. Instead of holding an SSE stream open, the server returns an InputRequiredResult:

```
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

The client collects the answer and re-issues the original call with inputResponses and the echoed requestState. Everything the retry needs travels in that payload, so any server instance can pick it up. The instance that asked is not required to be the one that gets the answer.

## Routable, cacheable, traceable

Three smaller changes make the resulting traffic easier to run. Every Streamable HTTP request now carries Mcp-Method and Mcp-Name headers, required under SEP-2243, so a load balancer, a gateway, or a rate limiter can route on the operation without reading the body; a server rejects a request where the header and the body disagree. List and resource-read results carry ttlMs and cacheScope under SEP-2549, modeled on HTTP's Cache-Control, so a client knows exactly how long a tools/list response stays fresh and whether it can be shared across users, without holding a long-lived stream open just to learn that a list changed. The key names for W3C Trace Context inside _meta, traceparent, tracestate, baggage, are locked down by SEP-414: several SDKs were already sending them, but with the names fixed in the spec, a trace started in a host application can follow a call through the client SDK, the MCP server, and whatever the server calls next, and land as a single span tree in an OpenTelemetry backend.

## Which authorization server actually answered

A client must now validate the iss parameter on every authorization response, under RFC 9207 and SEP-2468: a low-cost defense against what the maintainers call a mix-up attack, one made more likely by MCP's pattern of one client talking to many servers. Validation is required now; a future spec version will require a client to reject any response that omits iss, so an authorization server that doesn't send it yet should start. A narrower, more common failure gets fixed by SEP-837: a client now declares its OpenID Connect application_type during Dynamic Client Registration, so an authorization server stops defaulting a desktop or CLI client to "web" and rejecting its localhost redirect URI.

## An extension gets its own name, repository, and version number

Beyond these fixes, the release restructures how new capabilities can arrive at all. Extensions get the formal process they lacked in 2025-11-25, under SEP-2133: an extension is identified by a reverse-DNS ID, negotiated through an extensions map in client and server capabilities, lives in its own ext-* repository under its own maintainers, and versions independently of the specification. A new Extensions Track in the SEP process carries an extension from experimental to official. This release ships two of them.

## MCP Apps: an interface the host reviews before it runs

MCP Apps (SEP-1865) lets a server ship an interactive HTML interface that the host renders in a sandboxed iframe. A tool declares its UI template ahead of time, so a host can prefetch it, cache it, and security-review it before anything runs. The rendered interface talks back to the host over the same JSON-RPC base protocol as everything else in MCP, so a click inside that interface goes through the same audit and consent path as a direct tool call.

## Tasks leaves the core specification

Tasks shipped experimental in 2025-11-25, and production use surfaced enough redesign that an extension, not the specification, is the right home for it now. The lifecycle fits the stateless model: tools/call can answer with a task handle, and the client drives it forward with tasks/get, tasks/update, and tasks/cancel. The server decides when a call becomes a task, not the client. tasks/list is gone, because listing every task in flight can't be scoped safely once there's no session to scope it to. Anyone who built against the 2025-11-25 experimental Tasks API has to migrate to this lifecycle.

## What the maintainers deprecated

The maintainers now have a formal way to retire a feature, under SEP-2577's feature lifecycle policy, and they used it on three: Roots, Sampling, and Logging. Roots' replacement is a tool parameter, a resource URI, or server configuration. Sampling's is direct integration with an LLM provider's own API. Logging's is stderr on a stdio transport, or OpenTelemetry for anything structured. All three are annotation-only for now: the methods, types, and capability flags keep working in this release and in every spec version published within a year of it, and removing any of them needs its own SEP. One more literal value worth a find-and-replace: a missing resource now returns the standard JSON-RPC -32602 Invalid Params instead of the MCP-specific -32002 (SEP-2164). A client that matches on -32002 needs updating.

## How the protocol evolves from here

This release breaks things. "We don't intend for that to be the norm," the maintainers write. The feature lifecycle policy behind it holds every feature to an Active, Deprecated, Removed path, with at least twelve months required between the Deprecated stage and the earliest possible removal, and the Extensions framework gives a new capability somewhere to ship and stabilize as opt-in before it ever has to enter the specification proper. The stateless rework needed a clean break to happen at all. With it landed, the maintainers expect an implementer targeting 2026-07-28 to adopt whatever comes next without rewriting transport or lifecycle code again.

The release candidate locked on May 21, 2026. The final specification ships July 28, a ten-week window for SDK maintainers and client implementers to validate the changes against real workloads, and Tier 1 SDKs are expected to land support within it.

Thank you to everyone who shaped these proposals through the Working Groups and a great deal of patient review. We're looking forward to making this final with the community on July 28.

<!-- SCRATCH: not part of the manuscript -->

**Revision pass, addressing the four findings.**

1. **evidence/major, twelve-month window.** The closing section wrongly placed the twelve-month floor between Active and Deprecated. Fixed to match the source exactly: "at least twelve months required between the Deprecated stage and the earliest possible removal." This now agrees with the deprecation section's own "every spec version published within a year of it."

2. **mechanics/major, missing relative pronoun.** Took the suggested repair verbatim: "The sticky routing and shared session store that a horizontal deployment needed under the old handshake have no home in the protocol layer anymore." While fixing it I caught a second, related agreement error the reviewer didn't flag: "Gone too, under SEP-2567, is the Mcp-Session-Id header and the session it created" has a compound subject and needs "are", not "is". Fixed in the same pass since it's the same clause family.

3. **shape/major, missing transition into the extensions section.** Added "Beyond these fixes, the release restructures how new capabilities can arrive at all" ahead of the SEP-2133 sentence, per the suggestion's own wording, to mark the pivot from this-week fixes to the governance material that follows.

4. **craft/blocking, repeated "SEP-number verb" opener.** All eleven flagged sentences were rewritten so the SEP number is no longer the subject of an opening clause: it now lands mid-sentence ("under SEP-2567", "under RFC 9207 and SEP-2468"), after the consequence ("Gone too, under SEP-2567, are..."), or as a trailing citation ("a rule SEP-2260 promotes from recommendation to requirement"). The three-in-a-row cluster in "Routable, cacheable, traceable" no longer opens any of its three sentences on a bare SEP number. I did not touch the SEP-1865 (MCP Apps) or SEP-2352-adjacent sentences, since those already led with the feature name rather than the number and weren't part of the flagged pattern.

No claim, number, or quotation changed as a result of any of these edits; all four were sentence-level repairs to the article's own constructed prose, not to author-retained material, so none required an editor's call beyond the grammar fix already specified in the finding's suggestion.
