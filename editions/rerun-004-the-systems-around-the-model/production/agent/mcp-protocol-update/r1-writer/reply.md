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

<!-- SCRATCH: not part of the manuscript -->

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
