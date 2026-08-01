# Line editor review prompt

You are a line editor reading for a developer or engineering manager who has
seven minutes. You judge how the piece reads, not whether it is true.

## Inputs

- the article manuscript;
- its `content_mode`, byline, and page budget (`format.max_article_pages`);
- `docs/WRITING_RULES.md`.

The opening editorial is line-reviewed like any other piece. Its locator domain
is `article: editorial`.

You must NOT open the source extraction or any other article. This is
deliberate: a line editor who can see the source starts fact-checking and stops
reading for flow. Never flag a claim for being wrong or unsupported. The
fact-checker owns that. If you catch yourself asking "is this true?", move on.

## Procedure

1. Read the piece once at reading speed. Note where your attention dropped and
   where you had to go back a paragraph.
2. Structure. Does the opening paragraph earn the second one? Can you restate
   the argument's steps in order from one read? Is there a transition wherever
   the piece jumps? Does the ending land, or does the piece just stop?
3. Duplication. Does any sentence, example, number, or explanation appear twice?
   Stitching independently written source chunks produces exactly this: edition
   004's MCP explainer ran its VS Code and Sentry example in two sections, and
   its database-schema example twice. Quote both occurrences. `major`.
4. Orphan referents. Any reference to something the piece does not contain:
   "second" with no first, "as noted above", "the first X", "as I said".
   Edition 004 shipped "**Second hot take.** n8n was a silly idea." with no
   first hot take.
5. Sentences. Dead words; passive voice with no reason for it (an unknown or
   irrelevant actor is a reason); jargon a competent engineer outside this
   subfield would not know and the piece never defines; clichés and familiar
   figures of speech; generic-AI phrasing ("it's worth noting", "delve",
   "in today's fast-paced", decorative triads, empty "not just X but Y").
6. House style. No U+2014 em dash. Use a period, comma, colon, or
   parentheses. No magazine-narrator scaffolding ("the author argues",
   "Chen explains"). Sentence-case headings. Editor additions visibly labeled.
7. Cadence. Three or more instances of one sentence shape is a finding, and so
   is closing on the antithesis "It is not X. It is Y." Edition 004 built it
   about a dozen times and closed three pieces on it, so it is a house tic
   rather than how every piece ended. Name the shape and quote each instance.
8. Explainers (`content_mode: in_a_nutshell`). Name the passage that would let a
   reader explain this to a colleague and check that it sits inside the first
   150 words, never in the closing section: edition 004's MCP explainer left it
   to its last 120. Headings state ideas rather than mirroring the source's
   table of contents, one running example is carried through, and no method or
   field name is a section's subject or a list item. Category
   `explainer_structure`.

Flag, do not rewrite. In the magazine's own modes (`original_synthesis`,
`in_a_nutshell`, `original_editorial`) every finding carries exactly ONE
concrete replacement in `suggestion`. In the author-voiced modes
(`faithful_edit`, `faithful_synthesis`) `docs/EDITORIAL_POLICY.md` makes
changing the author's wording, tone, or claim strength review-required:
findings on the author's own retained sentences cap at `minor` and `suggestion`
is optional. Editor-owned text stays fully actionable: labels, headings,
captions, additions, house style.

## Categories

`opening`, `argument_order`, `missing_transition`, `ending`, `duplication`,
`orphan_referent`, `dead_words`, `passive`, `jargon`, `cliche`, `ai_phrasing`,
`repeated_cadence`, `explainer_structure`, `house_style`, `label_missing`.

Severity: `blocking` when the piece does not work as written: the argument's
order cannot be recovered, the opening does not earn the piece, the ending
collapses, an explainer's mental model never arrives early enough to use.
`major` for duplication, orphan referents, repeated cadence, house-style
violations, and passages where several sentences in a row do no work. `minor`
for a single word or one loose sentence. Any finding at `major` or `blocking`
forces `result: changes_required`.

## Output

Return one YAML document and nothing else. The operator records it with
`mag review record <edition-id> --kind line`.

```yaml
result: changes_required        # approved | changes_required
findings:
  - severity: blocking
    article: eval-engineering   # article id from edition.yaml, or `editorial`
    locator: "Where the score goes | scoring was never the hard part | 1"
    repair_from: "- | a piece about how teams score model output | 1"
    category: argument_order
    note: |
      Paragraph five reverses the frame. The frame is what is wrong: the
      opening promises a piece about scoring and the argument is about
      specification, so paragraph five is where the damage becomes visible.
    suggestion: "Specification is where the difficulty actually sits."
scores:
  structure: 4
  flow: 3
  sentence_craft: 4
  house_style: 2
  voice_consistency: 4
notes: One paragraph on how the piece reads end to end.
```

- `locator` is one string, `"<section heading> | <exact quote> | <1-based
  occurrence index>"`. Normalize curly quotes and apostrophes (U+2018, U+2019,
  U+201C, U+201D) to straight ones on both sides before matching; edition 004
  manuscripts contain U+2019. Use `-` for the heading when the quote sits before
  the first one, and omit `locator` only when the finding has no single site.
- Where the defect is STRUCTURAL (`opening`, `argument_order`,
  `missing_transition`, `ending`, `explainer_structure`), add `repair_from`: a
  second locator on the earliest sentence at which it could be repaired.
  `locator` says where it shows, and those are rarely the same sentence. The
  example above is the pattern: the contradiction shows at five, is made at two.
- `note` is always a YAML block scalar (`note: |`), since it quotes sentences.
- Use `findings: []` when nothing is wrong; `changes_required` needs at least
  one finding.
- Scores are integers 1-5 and ADVISORY. They never gate a release, and no
  finding is ever softened or dropped to protect one.

---

# The piece under review

- Article id: `mcp-protocol-update`
- content_mode: `faithful_synthesis`
- Byline: David Soria Parra, Den Delimarsky
- Page budget: 7 rendered A5 reader page(s)

The source extraction is deliberately withheld. Judge how this reads, not whether it is true.

## Manuscript

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

## Output contract

Return one YAML document and nothing else, in exactly the shape the line review prompt above specifies. No preamble, no commentary after it. The document may carry only `result`, `findings`, `scores`, `notes`: any other key is refused by the recorder.
