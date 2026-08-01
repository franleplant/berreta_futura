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

## Round 2: revise the draft below

A previous round of this piece was judged and did not pass. Your job is to produce the whole manuscript again, with every defect below gone. Rewrite as much as the repair needs; you are not patching sentences.

### Your predecessor's working notes

These are the notes from the draft below, not a judgment of it. A finding says where a defect *surfaces*; these notes are usually the only way to see where it was *made*. Read them before the findings.

```
## Step 1: claim ladder

**Central claim.** The `2026-07-28` release candidate spends one deliberate round of breaking changes to make MCP stateless at the protocol layer, and ships the governance machinery (feature lifecycle policy, Extensions framework, conformance gate) intended to make that the last break of its kind.

**Supporting claims, in the order the argument needs them.**

1. The practical effect on a production deployment is immediate: a server that needed sticky sessions, a shared session store, and deep packet inspection at the gateway now runs behind a plain round-robin load balancer, routes on `Mcp-Method`, and lets clients cache `tools/list` for as long as `ttlMs` permits. (Source lede plus the before/after diagram.)
2. MCP is now stateless at the protocol layer. Six SEPs get there, completing the plan in "The Future of MCP Transports" (December).
3. The `initialize`/`initialized` handshake is removed (SEP-2575); protocol version, client info, and capabilities move into `_meta` on every request; `server/discover` fetches server capabilities up front.
4. `Mcp-Session-Id` and the protocol-level session are removed (SEP-2567). Consequence: any request lands on any instance, and sticky routing and shared stores are no longer required at the protocol layer.
5. Server-initiated requests only while the server is actively processing a client request (SEP-2260). Claim strength changed: previously recommended, now required. Rationale: no prompt out of nowhere, and every elicitation traces to something the user or their agent started.
6. Multi Round-Trip Requests (SEP-2322) replace the held-open SSE stream with `InputRequiredResult` plus `inputResponses` and an echoed `requestState`; any instance can pick up the retry because everything it needs is in the payload.
7. Stateless protocol does not mean stateless application: explicit handles (`basket_id`, `browser_id`) minted by a tool and threaded back by the model. Author's judgment: often more powerful than session state, because the model can compose handles, reason about them, and hand them off.
8. Three smaller operational changes. `Mcp-Method`/`Mcp-Name` routing without body inspection, and servers reject header/body disagreement (SEP-2243). `ttlMs` and `cacheScope` modeled on `Cache-Control`, so a long-lived SSE stream is no longer the only way to learn a list changed (SEP-2549). W3C Trace Context key names fixed, several SDKs already did this, result is one span tree in an OpenTelemetry-compatible backend (SEP-414).
9. Extensions get a formal process (SEP-2133): reverse-DNS IDs, `extensions` capability map, `ext-*` repositories with delegated maintainers, independent versioning, a new Extensions Track from experimental to official.
10. MCP Apps (SEP-1865): sandboxed iframe, templates declared ahead so hosts can prefetch, cache, and security-review them, UI talks back over the same JSON-RPC base protocol so UI actions share the audit and consent path of a direct tool call.
11. Tasks demoted from experimental core feature to extension because production use surfaced enough redesign; task handle returned from `tools/call`, driven by `tasks/get`, `tasks/update`, `tasks/cancel`; creation is server-directed; `tasks/list` removed because it can't be scoped safely without sessions; shippers of the experimental API must migrate.
12. Six SEPs harden authorization toward real OAuth 2.0 and OpenID Connect deployments: `iss` validation per RFC 9207 against mix-up attacks that MCP's single-client, many-server pattern makes more prevalent (SEP-2468); `application_type` in Dynamic Client Registration, fixing the rejected localhost redirect URI (SEP-837); credential binding to the issuer (SEP-2352); refresh tokens (SEP-2207); scope accumulation on step-up (SEP-2350); the `.well-known` suffix (SEP-2351).
13. Roots, Sampling, and Logging deprecated with replacements (SEP-2577). Annotation-only: they keep working in this release and in every spec version published within a year of it, and removal needs a separate SEP.
14. Full JSON Schema 2020-12 for tool schemas (SEP-2106): composition, conditionals, references, unrestricted output schemas, `structuredContent` as any JSON value, no auto-dereferencing of external `$ref`, bounded depth and validation time. Separately, a missing resource returns `-32602 Invalid Params` instead of the MCP-custom `-32002` (SEP-2164).
15. Governance: Active, Deprecated, Removed lifecycle with at least twelve months before the earliest possible removal; extensions as the opt-in path to stability; a Standards Track SEP cannot reach Final without a matching conformance-suite scenario (SEP-2484), the suite the SDK tier system scores official SDKs against.
16. Timeline: RC locked May 21, 2026; final July 28, 2026; ten-week window for validation; Tier 1 SDKs expected to ship support inside it.

**Qualifications, limits, admissions.**

- "This release contains breaking changes. We don't intend for that to be the norm." The hinge of the whole argument, kept verbatim.
- Statelessness is claimed "at the protocol layer" only. That qualifier appears twice in the manuscript on purpose. Dropping either instance hardens the claim.
- "In practice, we've found" and "often a more powerful one" are hedged first-person judgments, not measurements. Kept hedged.
- Deprecations are annotation-only, with a one-year floor and a separate SEP required for removal.
- Rejecting responses that omit `iss` is a future expectation, not a requirement of this release. The manuscript keeps "in a future version" and "should begin supplying it now".
- "our expectation is that implementers ... will be able to adopt future revisions" is an expectation, not a promise. It is the last sentence of the piece for that reason.
- Tasks moved to an extension because production use surfaced redesign: an admission that the core-feature version was wrong, and it carries a migration cost for anyone who shipped against it. Both kept.

## Step 2: voice signature (carried verbatim)

1. "This release contains breaking changes. We don't intend for that to be the norm."
2. "In practice, we've found this pattern (the model threading an identifier from one tool call to the next) to be more than just a workable substitute for session state. It's often a more powerful one."
3. "If your client matches on the literal `-32002` value, update it."

Also carried word for word because they are voice rather than content: "The protocol no longer manages that state for you, but it doesn't prevent you from managing it yourself", "Three smaller changes make the resulting traffic easier to operate", and "a user is never prompted out of nowhere" (demoted to a subordinate clause, wording untouched).

Note for the next reviser: voice sentence 2 sits close to the banned "not merely X but Y" antithesis. It is the source author's own retained sentence, which `docs/WRITING_RULES.md` explicitly allows ("the ban is on writing it yourself"). If a line editor flags it, quote it more visibly rather than paraphrasing. It is the only first-person judgment in the piece, and paraphrase would turn a maintainer's opinion into the magazine's.

## Step 3: shape, and what was dropped

**Shape.** The edition-004 version organised by release-note category (Extensions / Authorization / Deprecations), which is the source's table of contents, not its argument. The argument here is that one break is being spent deliberately, on a foundation, next to the machinery built to avoid repeating it. So the spine is: what a deployment looks like now (opener), then why, mechanically (handshake and session gone), then what you lose and what replaces it (explicit handles), then what ordinary infrastructure gains (routable, cacheable, traceable), then where change goes from now on (extensions), then the bill you actually pay (what you have to change now), then why this is meant to be the last break (evolves from here). Sections five and six still carry release-note material, but each is subordinated to a claim instead of to a chapter title, and each ends on the obligation it creates for the reader rather than on a summary.

Four of the six headings are the author's own words. "Extensions become first-class" and "What you have to change now" are lightly adapted: the first from the source's own "Extensions Become First-Class", the second built out of the source's imperatives ("should begin supplying it now", "update it", "will need to migrate"). Neither asserts a framing the author did not offer.

**Dropped, in the prompt's cut order. Stopped as soon as the piece fit (999 body words).**

1. *Second and third examples of a point the first carried.* Five of the six authorization SEPs: `application_type` in Dynamic Client Registration (SEP-837), credential binding to the issuer (SEP-2352), refresh tokens (SEP-2207), scope accumulation on step-up (SEP-2350), the `.well-known` suffix (SEP-2351). The `iss` change carries the section's point (align with how OAuth and OpenID Connect are actually deployed) and is the one with an action attached. `application_type` was the hardest of these to lose: it is the most concretely developer-visible authorization fix in the release, and it is the first thing to restore if this piece ever gets a page back. Also dropped as repetition or chrome: the "Several SDKs and tools were already doing this" aside, the diagram captions, the "open an issue / ask in the contributor Discord" pointers, the draft-spec and changelog pointers, "and many other changes", and the thank-you to the Working Groups.
2. *Supporting evidence, before its claim.* Every SEP identifier, and the "six SEPs" count in both places it appears. This is the piece's main structural bet: a wall of SEP-XXXX is precisely what makes a release note read as a changelog, and no claim in the manuscript changes when the identifier is absent. The ladder above keeps all of them so a reviser can re-attach any one cheaply. Also cut as evidence for claims that survive without it: the Tasks method names and the server-directed creation detail (the claim that the lifecycle was reshaped survives), `inputResponses` (the `requestState` echo carries the mechanism), MCP Apps prefetch and cache (security review carries the point), the full trace path from host application through SDK and server to downstream (the single span tree carries it), "gateways" in the routing list, the elicitation rationale "every elicitation traces back to something they (or their agent) started", the "long-lived SSE stream is no longer the only way to learn that a list changed" clause, the Tier 1 SDK expectation, and "completing the plan we laid out in The Future of MCP Transports in December".
3. *Whole claims, least load-bearing first.* Full JSON Schema 2020-12 for tool schemas (SEP-2106) went whole: composition, conditionals, `$ref`/`$defs`, unrestricted output schemas, `structuredContent`, and the guidance not to auto-dereference external `$ref` URIs. It is a real capability change, but it hangs off nothing in the argument, and the error-code change from the same source section (which does create an obligation) says what needed saying about that part of the release. This is the largest single omission and the second thing to restore if the budget grows.
4. *Qualifications and the author's own conclusions.* Nothing dropped.

**Code.** All four fenced blocks in the source were dropped whole rather than trimmed. The prompt allows character-for-character reproduction or nothing, and the pdftotext extraction has wrapped and re-indented them (the `_meta` line in the `2026-07-28` example is truncated mid-token, and several header lines are split by the PDF's column artefacts), so no block could be reproduced faithfully. Inline identifiers carry the same information. Do not reconstruct these from the extraction; take a clean copy from the spec if a future revision wants them.

**Duplication watch.** Two near-misses. First, the opener keeps only the load-balancer half of the source's "practical effect" sentence. The `Mcp-Method` routing and `ttlMs` caching halves were removed from it so that "Routable, cacheable, traceable" can deliver them once. If anyone lengthens the opener, read that section first. Second, "published within a year of it" (deprecations) and "at least twelve months between deprecation and the earliest possible removal" (governance) are the same fact in two units. Both survive because the first is what a maintainer needs at the point of decision and the second is the policy itself, but the "under the lifecycle policy" tail was trimmed off the first so the policy is only spelled out once.

**Budget.** 999 body words, 53-word opener, first body block is a paragraph, six `##` headings, no H1, no U+2014, one three-item list (the deprecation replacements, licensed because the reader acts on them) and it is not the last thing in its section.

**Unclear instructions.** Three.

- The prompt's budget says "roughly 700 to 1,100 body words"; the commission says 700 to 1,000. I wrote to the narrower one, which is what cost the JSON Schema claim above.
- The prompt bans "framing the author did not offer" but requires headings that name what a section argues, while steps 3 and 4 require a shape other than the source's order. Any heading spanning two source sections is therefore a judgment call. The two adapted headings are flagged above so a reviser can revert them cheaply.
- "Nothing appears twice" is unclear about deliberate repetition of a qualifier. "At the protocol layer" appears twice because dropping either instance would overstate the claim. I read the rule as a ban on repeated examples and sentences, not on repeated hedges.
```

### The draft under revision

```
---
source_ids:
- the-2026-07-28-mcp-specification-release-candida-1a1752b8
content_mode: faithful_synthesis
label: FAITHFUL SYNTHESIS
---

A remote MCP server that needed sticky sessions, a shared session store, and deep packet inspection at the gateway can now run behind a plain round-robin load balancer. That is the immediate effect of the `2026-07-28` release candidate on a production deployment, and it is the largest revision of the protocol since launch.

## The handshake and session are gone

The headline change is that MCP is now stateless at the protocol layer. The `initialize`/`initialized` handshake is removed. The protocol version, client info, and client capabilities once exchanged at connection time now travel in `_meta` on every request, and a new `server/discover` method lets clients fetch server capabilities up front. The `Mcp-Session-Id` header and the protocol-level session that came with it are also removed. With both gone, any MCP request can land on any server instance, and the sticky routing and shared session stores that horizontal deployments needed are no longer required at the protocol layer.

A stateless protocol still needs a way for servers to ask the client for something mid-call, such as an elicitation prompt. Server-initiated requests may now only be issued while the server is actively processing a client request, which earlier spec versions recommended and this one requires, so a user is never prompted out of nowhere. Instead of holding a Server-Sent Events stream open, the server returns an `InputRequiredResult` that the client answers by re-issuing the original call with the echoed `requestState`.

## Stateless protocol, stateful applications

Removing the protocol-level session does not mean your application has to be stateless. Servers that need to carry state across calls can do what HTTP APIs have always done: mint an explicit handle (a `basket_id`, a `browser_id`) from a tool and have the model pass it back as an ordinary argument on later calls. In practice, we've found this pattern (the model threading an identifier from one tool call to the next) to be more than just a workable substitute for session state. It's often a more powerful one. The model can compose handles across tools, reason about them, and hand them off between steps in ways that externally managed session state, hidden in transport metadata, never allowed. The protocol no longer manages that state for you, but it doesn't prevent you from managing it yourself.

## Routable, cacheable, traceable

Three smaller changes make the resulting traffic easier to operate. Streamable HTTP now requires `Mcp-Method` and `Mcp-Name` headers, so load balancers and rate-limiters can route on the operation without inspecting the body. List and resource read results carry `ttlMs` and `cacheScope`, modeled on HTTP `Cache-Control`, so clients know exactly how long a `tools/list` response is fresh and whether it is safe to share across users. And the `traceparent`, `tracestate`, and `baggage` key names are now fixed in the spec, so a tool call can show up as one span tree in an OpenTelemetry-compatible backend.

## Extensions become first-class

Extensions existed in `2025-11-25` but had no formal process behind them. They are now negotiated through an `extensions` map on client and server capabilities, live in their own `ext-*` repositories, and version independently of the specification, with a new Extensions Track in the SEP process to carry them from experimental to official.

Two official extensions ship with this release, and they arrived from opposite directions. MCP Apps lets servers ship interactive HTML interfaces that hosts render in a sandboxed iframe, declared as templates ahead of time so hosts can security-review them before anything runs, and the rendered UI talks back over the same JSON-RPC base protocol, so every UI-initiated action goes through the same audit and consent path as a direct tool call. Tasks went the other way: it shipped as an experimental core feature in the last release, and production use surfaced enough redesign that the right home for it is an extension rather than the specification. Its lifecycle is reshaped around the stateless model, and `tasks/list` is removed because it can't be scoped safely without sessions. Anyone who shipped against that experimental Tasks API will need to migrate.

## What you have to change now

Roots, Sampling, and Logging are deprecated under the new feature lifecycle policy, each with a replacement:

- Roots: tool parameters, resource URIs, or server configuration.
- Sampling: direct integration with LLM provider APIs.
- Logging: `stderr` for stdio transports, OpenTelemetry for structured observability.

These are annotation-only deprecations. The methods, types, and capability flags keep working in this release and in every specification version published within a year of it, and removing any of them will require a separate SEP.

Other changes need attention sooner. Clients must now validate the `iss` parameter on authorization responses per RFC 9207, a low-cost mitigation for a class of mix-up attack that MCP's single-client, many-server deployment pattern makes more prevalent; in a future version, clients will be expected to reject responses that omit `iss`, so authorization servers should begin supplying it now if they don't already. And the error code for a missing resource changes from the MCP-custom `-32002` to the JSON-RPC standard `-32602 Invalid Params`. If your client matches on the literal `-32002` value, update it.

## How the protocol evolves from here

This release contains breaking changes. We don't intend for that to be the norm. Three governance SEPs are designed so that future revisions can evolve the protocol without breaking core capabilities. The feature lifecycle policy gives every feature an Active, Deprecated, and Removed lifecycle with at least twelve months between deprecation and the earliest possible removal. New capabilities can stabilize as opt-in extensions before, if ever, moving into the specification. And a Standards Track SEP can no longer reach Final status until a matching scenario lands in the conformance suite that the new SDK tier system scores official SDKs against.

The release candidate is locked as of May 21, 2026, and the final specification will be published on July 28, 2026. The ten weeks between are for SDK maintainers and client implementers to validate the changes against real workloads. The stateless rework is the kind of foundational change that needed a clean break. With it landed, our expectation is that implementers targeting `2026-07-28` will be able to adopt future revisions without rewriting their transport or lifecycle code.
```

### Findings you must clear

Every finding is an obligation: the defect it names must be gone from your draft. A `suggestion` is advisory. You are judged on whether the defect survived, never on whether you took the suggested line, so solve it however the piece is best served.

1. [major] repeated_cadence (from the line)
   - where it shows: Routable, cacheable, traceable | And the `traceparent`, `tracestate`, and `baggage` key names are now fixed in the spec | 1
   - note:
     Three consecutive sections are built by the same engine: announce a count,
     list two items, close with a sentence-initial "And". "Three smaller
     changes make the resulting traffic easier to operate... And the
     `traceparent`, `tracestate`, and `baggage` key names are now fixed in the
     spec". "Clients must now validate the `iss` parameter... And the error
     code for a missing resource changes from the MCP-custom `-32002`".
     "Three governance SEPs are designed so that future revisions can evolve
     the protocol... And a Standards Track SEP can no longer reach Final status
     until a matching scenario lands in the conformance suite". The triad
     framing reinforces it: the heading "Routable, cacheable, traceable",
     "Three smaller changes", "Three governance SEPs", the three-item Roots and
     Sampling and Logging list, "Active, Deprecated, and Removed". Individually
     each is a real list of three; stacked, the back half of the piece reads as
     one paragraph shape run four times, and the reader starts skimming for the
     "And" to know a section is ending. Arrangement is the synthesis's own, so
     this is repairable without touching the authors' wording: vary the
     openings and let one section run on something other than a count.
   - suggestion (advisory): The `traceparent`, `tracestate`, and `baggage` key names are also fixed in the spec now, so a tool call can show up as one span tree in an OpenTelemetry-compatible backend.
2. [major] duplication (from the line)
   - where it shows: The handshake and session are gone | the sticky routing and shared session stores that horizontal deployments needed are no longer required at the protocol layer | 1
   - note:
     The lede's payoff is spent twice with the same two items. Opening: "A
     remote MCP server that needed sticky sessions, a shared session store, and
     deep packet inspection at the gateway can now run behind a plain
     round-robin load balancer." End of the first section: "With both gone, any
     MCP request can land on any server instance, and the sticky routing and
     shared session stores that horizontal deployments needed are no longer
     required at the protocol layer." A lede that asserts an effect and a body
     that derives it is fine, but the derivation here re-enumerates sticky
     routing and shared session stores rather than adding to them, so the
     section ends on a sentence the reader has already read. The repair is a
     cut of the trailing clause, which changes no wording, tone or claim
     strength.
   - suggestion (advisory): With both gone, any MCP request can land on any server instance.
3. [minor] duplication (from the line)
   - where it shows: Stateless protocol, stateful applications | The protocol no longer manages that state for you, but it doesn't prevent you from managing it yourself. | 1
   - note:
     The paragraph opens and closes on the same proposition. First sentence:
     "Removing the protocol-level session does not mean your application has to
     be stateless." Last sentence: "The protocol no longer manages that state
     for you, but it doesn't prevent you from managing it yourself." Nothing
     between them changes the claim, so the closer is a restatement occupying
     the position where the reader expects the consequence. The repair is a
     cut; capped at minor because the sentences are the authors' own.
4. [minor] ai_phrasing (from the line)
   - where it shows: Stateless protocol, stateful applications | to be more than just a workable substitute for session state. It's often a more powerful one. | 1
   - note:
     "In practice, we've found this pattern (the model threading an identifier
     from one tool call to the next) to be more than just a workable substitute
     for session state. It's often a more powerful one." This is the empty "not
     just X but Y" split across a full stop, and the second sentence carries no
     content the first does not already imply. It also lands one beat away from
     the house antithesis tic. The claim that follows ("The model can compose
     handles across tools, reason about them, and hand them off between steps")
     is the actual argument and is strong enough to run without the setup.
     Capped at minor and no replacement offered: the sentences are the authors'
     and the fix touches their claim strength.
5. [minor] jargon (from the line)
   - where it shows: Extensions become first-class | with a new Extensions Track in the SEP process to carry them from experimental to official | 1
   - note:
     SEP is never expanded and appears four times, twice in load-bearing
     positions: "a new Extensions Track in the SEP process", "removing any of
     them will require a separate SEP", "Three governance SEPs are designed so
     that future revisions can evolve the protocol", "a Standards Track SEP can
     no longer reach Final status". An engineer who does not follow this
     working group reaches the closing section, which is entirely about the SEP
     machinery, still guessing. The repair is an editor gloss at first mention
     rather than a change to the authors' sentences; I have not supplied the
     expansion because getting it right is the fact-checker's call, not mine.
6. [minor] orphan_referent (from the line)
   - where it shows: How the protocol evolves from here | the conformance suite that the new SDK tier system scores official SDKs against | 1
   - note:
     "the new SDK tier system" arrives with a definite article and "new", both
     of which promise a prior mention. The piece has none: SDKs appear once
     before this, as "SDK maintainers" in the following paragraph, and no tier
     system is described anywhere. The reader is told a governance rule turns
     on a mechanism they have not been shown.

## Output contract

Return the complete manuscript first: the frontmatter the prompt specifies, then the body, and nothing before it. Then a line containing exactly:

    <!-- SCRATCH: not part of the manuscript -->

Then your working notes for that draft: the concept graph or claim ladder you built the piece from, what you cut and why, and anything a later reviser would otherwise have to reconstruct. Everything below the marker is stripped before the manuscript is written and is never shown to a judge, so write it for the next writer, not for a reader. Return no other commentary, and do not wrap the manuscript in a code fence.
