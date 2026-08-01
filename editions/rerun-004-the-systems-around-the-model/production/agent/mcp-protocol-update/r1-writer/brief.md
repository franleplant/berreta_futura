# Faithful-synthesis production prompt

You are retelling this author's piece at roughly a third of its length, in the
author's own voice, as continuous prose. You are not extracting highlights and
you are not reviewing the source. The byline and the visible
`faithful_synthesis` label already tell the reader whose material this is and
that it has been condensed. Your inputs are the source extraction at
`library/sources/<source-id>/extracted.md` and the article's `edition.yaml` row.

## The budget decides the piece

Seven A5 reader pages is the hard maximum, including the opener illustration,
title, and credit; roughly 700 to 1,100 body words fits. The renderer measures
real pagination and refuses an over-budget build; `mag fit <edition-id>` answers
the same question in seconds.

Know that number before you plan. A 3,000-word source loses roughly half its
substantive claims at this length: that is the mode working, not failing. What
fails is finding out on a fourth cutting pass, where what to lose gets decided
one sentence at a time and by accident. Decide in step 3, cut in this order,
and stop as soon as the piece fits.

1. The second and third example of a point the first already carried.
2. A claim's supporting evidence, before the claim itself. A claim without its
   study reads thinner but still reads; the study without its claim is trivia.
3. Whole claims, the least load-bearing first.
4. Qualifications and the author's own conclusions: last, and almost never. A
   synthesis that reached the budget through these has failed, not fitted.

## Procedure

Steps 1 and 2 are working notes in your reply. They do not go into the
manuscript.

1. **Claim ladder.** Read the whole extraction, then write the author's central
   claim in one sentence; the supporting claims in the order the argument needs
   them, each with its evidence, example, or number attached; and every
   qualification, counterexample, admission of uncertainty, and limit on claim
   strength.
2. **Voice signature.** Quote three sentences that could only have been written
   by this author: an idiom, a joke, an insult, an unusual rhythm, or a sign-off
   that is voice rather than web furniture. These survive verbatim.
3. **Shape and cut.** Decide the piece from the claim ladder, not from the
   source's paragraph order. Merge claims the source makes twice, drop
   throat-clearing and recap sections, then apply the cut order above until what
   remains fits. Write down what you dropped.
   - **Enumerations.** Every list in the source gets one of three fates, and
     "the source had a list" is not one. Prose, when the items are moves in the
     argument. A list, when the reader will scan or act on them and there are no
     more than five. Its conclusion alone, when the items only evidence a point
     the surrounding sentence already makes.
   - **Numbers.** A number survives only if the argument changes when the number
     changes. A contrast the thesis rests on keeps both figures exactly; a
     leaderboard, a version count, or a figure whose sentence reads the same
     without it goes.
   - **Code.** Reproduce a fenced block character for character or drop it
     whole. Validation matches every fence against the source's own lines, so a
     trimmed, re-indented, or stitched block fails the build.
4. **Write it continuously.** One paragraph must follow from the last. A reader
   must never find the seam where two source passages met. Cold open on
   something concrete. End on a line that lands.
5. Edit with the method in `docs/WRITING_RULES.md`, then check the budget again.

## Hard rules

- Every claim, number, example, and quotation must be traceable to the
  extraction. Add no thesis of your own, no framing the author did not offer, no
  link, and no fact from your own knowledge.
- Preserve claim strength exactly. "We believe", "roughly", "in one sample",
  "we do not know why" are load-bearing. Never harden a hedge and never soften a
  flat assertion. Keep the counterexamples and the disagreement: a synthesis
  that reads smoother than the source because the awkward parts are gone has
  failed.
- **Voice.** Keep the author's grammatical person, and the three sentences from
  step 2 verbatim, profanity and jokes included. A sign-off survives when it is
  voice ("Good luck."); a subscribe prompt or "follow me on X" is web furniture
  and goes with the rest of the chrome. Never add scaffolding such as "the
  author argues" or "Narayanan explains".
- Nothing appears twice: edition 004 shipped the same VS Code and Sentry example
  in two sections of one article. Observe the banned tics in
  `docs/WRITING_RULES.md`, including the antithesis close "It is not X. It is Y."

## Format

```
---
source_ids:
- <source-id>                     # one entry per source, always a list
content_mode: faithful_synthesis
label: FAITHFUL SYNTHESIS
---
```

The title, byline, and `source_body_sha256` pins live in the article's
`edition.yaml` row, not here. The body follows the closing `---` and must begin
with a paragraph, never a heading, so the illustrated opener can set it. Use
`##` for section headings; no H1. A heading names what its section argues, in
the author's own words where they exist, and may not assert a framing the author
did not offer: if you cannot title a section without adding an idea, keep the
source's heading.

## Working notes

End your reply with a line containing exactly:

    <!-- SCRATCH: not part of the manuscript -->

and put your working notes below it: the claim ladder from step 1, the voice signature from step 2, and what step 3 dropped. Everything above that line is the
manuscript and is written to disk as it stands; everything below it is stripped
before the file is written and is never shown to a judge or to a reader.

Write the notes for the person who revises this piece next, which may be you in
another session. A review finding names the sentence where a defect *surfaces*;
your notes are usually the only record of where it was *made*, and a reviser
working from findings alone can patch a symptom without ever finding its cause.
Say what you decided, what you cut and why, and which choices the piece is
resting on.

## How this will be judged

A fact-checker reads the manuscript against the extraction claim by claim. A
line editor checks structure, duplication, the opening, the ending, the house
style, and whether the author's voice survived. Check this yourself first: a
developer and an engineering manager must each be able to state the piece's
central claim and its main caveat after one read.

---

# The assignment

The prompt above governs. This section names the piece, supplies its complete inputs, and states the output contract.

- Edition: `rerun-004-the-systems-around-the-model` (The Systems Around the Model)
- Piece id: `mcp-protocol-update`
- content_mode: `faithful_synthesis`
- Title: The MCP Protocol Update
- Byline: David Soria Parra, Den Delimarsky
- Page budget: 7 rendered A5 reader page(s)

## Source extractions

1 extraction(s), each complete. You are drafting the whole piece in this one pass from all of it: nothing else will be sent, and no later call will stitch a second half on.

### Extraction `the-2026-07-28-mcp-specification-release-candida-1a1752b8` (306 lines, complete)

```
    Model Context Protocol Blog
Documentation        Posts Archives Search


   Home / Posts
   The 2026-07-28 MCP Specification
   Release Candidate
   The release candidate for the next Model Context Protocol (MCP) specification is now
   available: a stateless protocol core, the Extensions framework, Tasks, MCP Apps,
   authorization hardening, and a formal deprecation policy.
   May 21, 2026 · 9 min · David Soria Parra (Lead Maintainer), Den Delimarsky (Lead Maintainer)
         Table of Contents
   The release candidate for MCP                is now available. It is the largest revision of
                                           2026-07-28

   the protocol since launch and delivers on the 2026 roadmap:
     a stateless core that scales on ordinary HTTP infrastructure
     extensions including server-rendered UIs through MCP Apps and long-running work
     through the Tasks extension
     authorization that aligns more closely with OAuth and OpenID Connect deployments
     a formal deprecation policy so the protocol can evolve without breaking what you’ve
     built,
   and many other changes.
   The practical effect on a production deployment is immediate. A remote MCP server that
   previously needed sticky sessions, a shared session store, and deep packet inspection at
   the gateway can now run behind a plain round-robin load balancer, route traffic on an
    Mcp-Method   header, and let clients cache              responses for as long as the
                                                         tools/list

   server’s         permits.
                ttlMs
     The release candidate is available today and the final specification ships on July 28,
     2026. This release contains breaking changes; see Release Timeline and Validation
     for the details.

A Stateless Protocol
The headline change is that MCP is now stateless at the protocol layer. Six Specification
Enhancement Proposals (SEPs) work together to get there, completing the plan we laid
out in The Future of MCP Transports in December.
                              BEFORE                                                  AFTER
                            2025-11-25                                             2026-07-28



                               Client                                                 Client

                          Load balancer                                          Load balancer
                                    Sticky route

           MCP server       MCP server        MCP server            MCP server     MCP server        MCP server


                           Shared session                                    Any request, any instance
                               store




Before and after
In    2025-11-25        , calling a tool over Streamable HTTP means establishing a session first:
 POST /mcp HTTP/1.1
 Content-Type: application/json


 {"jsonrpc":"2.0","id":1,"method":"initialize",
  "params":{"protocolVersion":"2025-11-25","capabilities":{},
            "clientInfo":{"name":"my-app","version":"1.0"}}}


The server responds with an                    that every subsequent request must carry,
                                                   Mcp-Session-Id

pinning the client to whichever instance issued it:
 POST /mcp HTTP/1.1
 Mcp-Session-Id: 1868a90c-3a3f-4f5b
 Content-Type: application/json

 {"jsonrpc":"2.0","id":2,"method":"tools/call",
  "params":{"name":"search","arguments":{"q":"otters"}}}


In          , the same call is a single self-contained request that any server instance
   2026-07-28

can handle:
 POST /mcp HTTP/1.1
 MCP-Protocol-Version: 2026-07-28
 Mcp-Method: tools/call
 Mcp-Name: search
 Content-Type: application/json

 {"jsonrpc":"2.0","id":1,"method":"tools/call",
  "params":{"name":"search","arguments":{"q":"otters"},
            "_meta":{"io.modelcontextprotocol/clientInfo":{"name":"my-app","version":




The handshake and session are gone
The  initialize     /
                   initialized       handshake is removed (SEP-2575). The protocol version,
client info, and client capabilities that used to be exchanged once at connection time now
travel in_meta     on every request, and a new server/discover     method lets clients fetch
server capabilities when they need them up front.
The  Mcp-Session-Id      header and the protocol-level session that came with it are also
removed (SEP-2567). With both gone, any MCP request can land on any server instance,
and the sticky routing and shared session stores that horizontal deployments needed
before are no longer required at the protocol layer.

Stateless protocol, stateful applications
Removing the protocol-level session does not mean your application has to be stateless.
Servers that need to carry state across calls can do what HTTP APIs have always done:
mint an explicit handle (a basket_id  ,a  browser_id  ) from a tool and have the model
pass it back as an ordinary argument on later calls.
                 Model                                                  MCP server
                                       create_basket()




                                  { basket_id: "b_123" }




                          add_item(basket_id: "b_123", sku: …)




                      The model threads "b_123" back as an ordinary argument

In practice, we’ve found this pattern (the model threading an identifier from one tool call
to the next) to be more than just a workable substitute for session state. It’s often a more
powerful one. The model can compose handles across tools, reason about them, and
hand them off between steps in ways that externally managed session state, hidden in
transport metadata, never really allowed.
The protocol no longer manages that state for you, but it doesn’t prevent you from
managing it yourself. The explicit-handle pattern simply makes the state visible to the
model rather than hidden away.
Server-to-client requests, restructured
A stateless protocol still needs a way for servers to ask the client for something mid-call,
such as an elicitation prompt. Two SEPs rebuild that flow so it works without a persistent
connection.
Server-initiated requests may now only be issued while the server is actively processing a
client request (SEP-2260). Earlier spec versions recommended this; it’s now required. A
user is never prompted out of nowhere, and every elicitation traces back to something
they (or their agent) started.
Multi Round-Trip Requests (SEP-2322) change how those prompts are delivered. Instead
of holding a Server-Sent Events (SSE) stream open, the server returns an
 InputRequiredResult  :
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


The client gathers the answers and re-issues the original call with      inputResponses   and
the echoed    requestState   . Any server instance can pick that retry up because
everything it needs is in the payload.

Routable, cacheable, traceable
Three smaller changes make the resulting traffic easier to operate.
The Streamable HTTP transport now requires                    and
                                                     Mcp-Method                headers (SEP-
                                                                        Mcp-Name

2243) so load balancers, gateways, and rate-limiters can route on the operation without
inspecting the body. Servers reject requests where the headers and body disagree.
List and resource read results now carry     ttlMs  and    cacheScope (SEP-2549), modeled
on HTTP    Cache-Control   . Clients know exactly how long a      tools/listresponse is
fresh and whether it’s safe to share across users, and a long-lived SSE stream is no longer
the only way to learn that a list changed.
W3C Trace Context propagation in     _meta    is now documented (SEP-414), locking down
the   traceparent ,  tracestate    , and
                                       baggage     key names so distributed traces correlate
across SDKs and gateways. Several SDKs and tools were already doing this; with the key
names fixed in the spec, a trace that starts in a host application can follow a tool call
through the client SDK, the MCP server, and whatever the server calls downstream, and
show up as a single span tree in an OpenTelemetry-compatible backend.
Extensions Become First-Class
Extensions existed in the  2025-11-25   release but had no formal process behind them.
SEP-2133 adds that: extensions are identified by reverse-DNS IDs, negotiated through an
 extensions   map on client and server capabilities, live in their own ext-*repositories
with delegated maintainers, and version independently of the specification. A new
Extensions Track in the SEP process gives them a path from experimental to official.
This release includes two official extensions.

MCP Apps: server-rendered user interfaces
MCP Apps (SEP-1865) lets servers ship interactive HTML interfaces that hosts render in a
sandboxed iframe. Tools declare their UI templates ahead of time so hosts can prefetch,
cache, and security-review them before anything runs. The rendered UI talks back to the
host over the same JSON-RPC base protocol used everywhere else in MCP, so every UI-
initiated action goes through the same audit and consent path as a direct tool call.

Tasks graduates to an extension
Tasks shipped as an experimental core feature in    2025-11-25  . Production use surfaced
enough redesign that the right home for it is an extension rather than the specification.
The Tasks extension reshapes the lifecycle around the stateless model: a server can
answer   tools/call   with a task handle, and the client drives it with tasks/get   ,
 tasks/update  , and  tasks/cancel   . Task creation is server-directed: the client advertises
the extension and the server decides when a call should run as a task.    tasks/list    is
removed because it can’t be scoped safely without sessions.
Anyone who shipped against the     2025-11-25   experimental Tasks API will need to
migrate to the new lifecycle.

Authorization Hardening
Six SEPs harden the authorization specification to align more closely with how OAuth 2.0
and OpenID Connect are deployed in practice.
Clients must now validate the   iss   parameter on authorization responses per RFC 9207
(SEP-2468). This is a low-cost mitigation for a class of mix-up attack that is more
prevalent in MCP’s single-client, many-server deployment pattern. In a future version,
clients will be expected to reject responses that omit , so authorization servers
                                                        iss

should begin supplying it now if they don’t already.
Clients now declare their OpenID Connect      application_type    during Dynamic Client
Registration (SEP-837), avoiding the common case where an authorization server
defaults a desktop or CLI client to   "web" and rejects its localhost redirect URI. Clients
bind registered credentials to the issuing authorization server’s issuer    and re-register
when a resource migrates between authorization servers (SEP-2352). The spec also
documents how to request refresh tokens from OpenID Connect-style authorization
servers (SEP-2207), and clarifies scope accumulation during step-up (SEP-2350) and the
 .well-known     discovery suffix (SEP-2351).

Roots, Sampling, and Logging Are Deprecated
Three core features are deprecated under the new feature lifecycle policy (SEP-2577):
Feature Replacement
Roots Tool parameters, resource URIs, or server configuration
Sampling Direct integration with LLM provider APIs
Logging     stderr for stdio transports; OpenTelemetry for structured observability
These are annotation-only deprecations. The methods, types, and capability flags
continue to work in this release and in every specification version published within a year
of it, and removing any of them will require a separate SEP under the lifecycle policy.

Full JSON Schema 2020-12 for Tools
Tool  inputSchema   and   outputSchema   are lifted to full JSON Schema 2020-12 (SEP-
2106). Input schemas keep the     type: "object"     root constraint but now allow
composition (  oneOf  ,  anyOf ,   allOf ), conditionals, and references ( , $ref    $defs  ).
Output schemas are unrestricted, and        structuredContent  can now be any JSON value
rather than only an object. Implementations must not auto-dereference external        $ref

URIs and should bound schema depth and validation time.
Separately, the error code for a missing resource changes from the MCP-custom
 -32002   to the JSON-RPC standard         -32602 Invalid Params (SEP-2164). If your client
matches on the literal  -32002   value, update it.

How the Protocol Evolves From Here
This release contains breaking changes. We don’t intend for that to be the norm.
Three governance SEPs in this release are designed so that future revisions can evolve
the protocol without breaking core capabilities. The feature lifecycle policy gives every
feature an Active, Deprecated, and Removed lifecycle with at least twelve months
between deprecation and the earliest possible removal. The Extensions framework means
new capabilities can ship as opt-in extensions and stabilize there before, if ever, moving
into the specification. And a Standards Track SEP can no longer reach Final status until a
matching scenario lands in the conformance suite (SEP-2484), which is the same suite
the new SDK tier system scores official SDKs against.
The stateless rework in this release is the kind of foundational change that needed a clean
break. With it landed, and with deprecation windows and extensions as the standard tools
going forward, our expectation is that implementers targeting      2026-07-28  will be able to
adopt future revisions without rewriting their transport or lifecycle code.

Release Timeline and Validation
The release candidate is locked as of May 21, 2026. The final specification will be
published on July 28, 2026. The ten-week window is for SDK maintainers and client
implementers to validate the changes against real workloads; under the SDK tier system,
Tier 1 SDKs are expected to ship support within this window.
The full release candidate is in the draft specification, and the changelog will list every
change against       2025-11-25.
If you find a problem, open an issue in the specification repository. For implementation
questions, the relevant Working Group channel in the contributor Discord is the fastest
path to an answer.

Looking Ahead
This release gives MCP the foundation we expect it to grow on for a long time: a protocol
that runs statelessly on commodity HTTP infrastructure, an extensions framework where
capabilities like Tasks and MCP Apps can ship on their own timeline, and a lifecycle policy
that lets implementers build on                knowing what they ship will keep working.
                                           2026-07-28


Thank you to everyone who shaped these proposals through the Working Groups and a
great deal of patient review. We’re looking forward to making this final with the community
on July 28.
 mcp       spec         release        protocol

                       Documentation · Posts · Archives · Search · Tags · GitHub · LinkedIn · RSS
                           Copyright © Model Context Protocol a Series of LF Projects, LLC.
         For web site terms of use, trademark policy and other project policies please see https://lfprojects.org.
```

## Output contract

Return the complete manuscript first: the frontmatter the prompt specifies, then the body, and nothing before it. Then a line containing exactly:

    <!-- SCRATCH: not part of the manuscript -->

Then your working notes for that draft: the concept graph or claim ladder you built the piece from, what you cut and why, and anything a later reviser would otherwise have to reconstruct. Everything below the marker is stripped before the manuscript is written and is never shown to a judge, so write it for the next writer, not for a reader. Return no other commentary, and do not wrap the manuscript in a code fence.
