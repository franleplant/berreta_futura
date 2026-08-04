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

The server answered with an Mcp-Session-Id that every later request had to carry, pinning the client to whichever instance had issued it. SEP-2575 removes the initialize/initialized handshake outright: protocol version, client info, and capabilities now travel in _meta on every request instead, and a new server/discover method lets a client fetch a server's capabilities up front when it needs them. SEP-2567 removes the Mcp-Session-Id header along with the session it created. A single self-contained request now carries an MCP-Protocol-Version header and an Mcp-Method header naming the operation, and any server instance can answer it. The sticky routing and shared session store a horizontal deployment needed under the old handshake have no home in the protocol layer anymore.

## Stateless protocol, stateful applications

None of this makes a server itself stateless. A server that needs to carry state across calls does what an HTTP API has always done: a tool mints an explicit handle, a basket_id or a browser_id, and the model passes it back as an ordinary argument on the next call. "In practice, we've found this pattern (the model threading an identifier from one tool call to the next) to be more than just a workable substitute for session state. It's often a more powerful one," the maintainers write: the model can compose handles across tools, reason about them, and hand them off between steps in ways a session hidden in transport metadata never allowed. The protocol no longer manages that state, but nothing stops an application from managing it itself. The explicit handle just makes the state visible to the model instead of hidden away.

## Server-to-client requests, restructured

A stateless protocol still needs a way for a server to ask mid-call for something, an elicitation prompt, say. SEP-2260 makes a rule the earlier spec only recommended: a server may ask only while it's actively processing a request the client sent, so a user is never prompted out of nowhere and every elicitation traces back to something they, or their agent, started. SEP-2322 changes how the prompt travels. Instead of holding an SSE stream open, the server returns an InputRequiredResult:

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

Three smaller changes make the resulting traffic easier to run. SEP-2243 requires the Mcp-Method and Mcp-Name headers on every Streamable HTTP request, so a load balancer, a gateway, or a rate limiter can route on the operation without reading the body, and a server now rejects a request where the header and the body disagree. SEP-2549 puts ttlMs and cacheScope on list and resource-read results, modeled on HTTP's Cache-Control, so a client knows exactly how long a tools/list response stays fresh and whether it can be shared across users, without holding a long-lived stream open just to learn that a list changed. SEP-414 fixes the key names, traceparent, tracestate, baggage, for W3C Trace Context inside _meta. Several SDKs were already sending them, but with the names locked in the spec, a trace started in a host application can follow a call through the client SDK, the MCP server, and whatever the server calls next, and land as a single span tree in an OpenTelemetry backend.

## Which authorization server actually answered

SEP-2468 makes a client validate the iss parameter on every authorization response, under RFC 9207: a low-cost defense against what the maintainers call a mix-up attack, one made more likely by MCP's pattern of one client talking to many servers. Validation is required now; a future spec version will require a client to reject any response that omits iss, so an authorization server that doesn't send it yet should start. SEP-837 fixes a narrower, more common failure: a client now declares its OpenID Connect application_type during Dynamic Client Registration, so an authorization server stops defaulting a desktop or CLI client to "web" and rejecting its localhost redirect URI.

## An extension gets its own name, repository, and version number

SEP-2133 gives extensions the formal process they lacked in 2025-11-25. An extension is identified by a reverse-DNS ID, negotiated through an extensions map in client and server capabilities, lives in its own ext-* repository under its own maintainers, and versions independently of the specification. A new Extensions Track in the SEP process carries an extension from experimental to official. This release ships two of them.

## MCP Apps: an interface the host reviews before it runs

MCP Apps (SEP-1865) lets a server ship an interactive HTML interface that the host renders in a sandboxed iframe. A tool declares its UI template ahead of time, so a host can prefetch it, cache it, and security-review it before anything runs. The rendered interface talks back to the host over the same JSON-RPC base protocol as everything else in MCP, so a click inside that interface goes through the same audit and consent path as a direct tool call.

## Tasks leaves the core specification

Tasks shipped experimental in 2025-11-25, and production use surfaced enough redesign that an extension, not the specification, is the right home for it now. The lifecycle fits the stateless model: tools/call can answer with a task handle, and the client drives it forward with tasks/get, tasks/update, and tasks/cancel. The server decides when a call becomes a task, not the client. tasks/list is gone, because listing every task in flight can't be scoped safely once there's no session to scope it to. Anyone who built against the 2025-11-25 experimental Tasks API has to migrate to this lifecycle.

## What the maintainers deprecated

SEP-2577's feature lifecycle policy gives the maintainers a formal way to retire a feature, and they used it on three: Roots, Sampling, and Logging. Roots' replacement is a tool parameter, a resource URI, or server configuration. Sampling's is direct integration with an LLM provider's own API. Logging's is stderr on a stdio transport, or OpenTelemetry for anything structured. All three are annotation-only for now: the methods, types, and capability flags keep working in this release and in every spec version published within a year of it, and removing any of them needs its own SEP. One more literal value worth a find-and-replace: a missing resource now returns the standard JSON-RPC -32602 Invalid Params instead of the MCP-specific -32002 (SEP-2164). A client that matches on -32002 needs updating.

## How the protocol evolves from here

This release breaks things. "We don't intend for that to be the norm," the maintainers write. The feature lifecycle policy behind it holds every feature to an Active, Deprecated, Removed path with at least twelve months between the first two, and the Extensions framework gives a new capability somewhere to ship and stabilize as opt-in before it ever has to enter the specification proper. The stateless rework needed a clean break to happen at all. With it landed, the maintainers expect an implementer targeting 2026-07-28 to adopt whatever comes next without rewriting transport or lifecycle code again.

The release candidate locked on May 21, 2026. The final specification ships July 28, a ten-week window for SDK maintainers and client implementers to validate the changes against real workloads, and Tier 1 SDKs are expected to land support within it.

Thank you to everyone who shaped these proposals through the Working Groups and a great deal of patient review. We're looking forward to making this final with the community on July 28.

<!-- SCRATCH: not part of the manuscript -->

**The sentence.** A reader gets the release notes reordered around consequence rather than around the spec's own eight sections: what breaks at the wire level first (session, handshake), then the mechanisms that replace it (handles, elicitation, routing), then the two concrete action items with dates attached (iss, the -32002 code), then what a reader can safely ignore for a year (deprecations, governance). The source's own order is release-notes order; this one is a reader deciding what to do this week versus what to file away. Checked against the draft: yes, each section states or implies who does something differently and when.

**The two absences.** (1) The full JSON Schema 2020-12 section (oneOf/anyOf/allOf, $ref/$defs, output-schema unrestricted, the ban on auto-dereferencing external $ref URIs) does not appear. It's a real change but changes nothing about how a reader operates a deployment this week, and none of its four sub-facts pass "does the argument change if this number/detail changes." (2) The "Looking Ahead" closing paragraph and the Discord/issue-tracker contact boilerplate in "Release Timeline and Validation" are cut entirely: pure restatement and web furniture. The genuine sign-off ("Thank you to everyone...") is kept as the ending in its place.

**Claim ladder** (central claim and support): central claim is the opener, kept close to the source's own best sentence per docs/WRITING_RULES.md's own citation of it, split across two sentences per rule iii's repair. Supporting claims covered: handshake/session removal (SEP-2575, SEP-2567) with before-code demonstrated, the explicit-handle pattern (with the load-bearing hedge "we've found... often" preserved verbatim), elicitation restructuring (SEP-2260, SEP-2322) with the InputRequiredResult demonstrated, routing/caching/tracing (SEP-2243, SEP-2549, SEP-414), the two authorization SEPs with the clearest reader-facing failure modes (SEP-2468 iss, SEP-837 application_type), Extensions framework (SEP-2133), MCP Apps (SEP-1865), Tasks becoming an extension (with the tasks/list removal reasoning kept, since "can't be scoped safely without sessions" is the kind of claim that changes if you don't know it), the three deprecations with their replacements and the annotation-only/twelve-month guarantee, the -32602/-32002 change, and the governance triad (lifecycle policy, Extensions framework, and the "clean break" expectation) with the "we don't intend for that to be the norm" hedge kept intact next to it, not softened into a promise.

**Voice signature** (verbatim, kept): "We don't intend for that to be the norm." / "In practice, we've found this pattern (the model threading an identifier from one tool call to the next) to be more than just a workable substitute for session state. It's often a more powerful one." / "Thank you to everyone who shaped these proposals through the Working Groups and a great deal of patient review. We're looking forward to making this final with the community on July 28."

**What step 3 dropped, beyond the two absences.** The session-pinning HTTP example (the second before/after code block) is described in prose instead of shown twice; the source's own truncated "after" code block was corrupted by the PDF extraction (cut off mid-string) and dropped whole per the code rule rather than repaired or reproduced broken. Four of the six authorization SEPs (refresh token documentation, scope accumulation during step-up, the .well-known discovery suffix, and the credential-binding-to-issuer SEP-2352) are cut: none changes a reader's action this week and keeping all six would have made the section a list of SEP numbers rather than two demonstrated failures. The SDK tier system and SEP-2484's conformance-suite gate are cut from the governance paragraph as a duplicate of the timeline paragraph's Tier 1 mention; only the timeline keeps it, concretely, as a date and a set of SDKs rather than a mechanism restated twice.

**Headings changed from the source, and why**, per docs/WRITING_RULES.md's own citations of this exact article: "Extensions Become First-Class" (dead metaphor, rule i) became "An extension gets its own name, repository, and version number." "Authorization Hardening" (jargon arriving instead of a description, rule v) became "Which authorization server actually answered," and the section now opens on the failure (Feynman's order) rather than asserting a direction of travel. "Roots, Sampling, and Logging Are Deprecated" (passive with a known actor, rule iv) became an active heading ("What the maintainers deprecated") over an active first sentence ("the maintainers used it on three"). "Tasks graduates to an extension" (a school-promotion figure that was never earned) became "Tasks leaves the core specification."

**What this draft is resting on.** The mix-up attack is named but not mechanically explained, since the source only names it and explaining the mechanism would be a fact from outside the extraction; a reviser should not add that explanation even though it's accurate, unless a future source revision supplies it. If a judge flags the authorization section as thin, the fix is tightening what's here, not importing an explanation.
