result: changes_required
findings:
  - severity: major
    article: mcp-in-a-nutshell
    locator: "What the protocol declines to decide | both went out with the 2026-07-28 version | 1"
    repair_from: "What the protocol declines to decide | The agreement is small enough to retire parts of itself. | 1"
    category: qualification_loss
    note: |
      The source deprecates; the manuscript removes. The extraction says
      "Sampling is deprecated as of protocol version 2026-07-28" and, under
      Primitives, "Deprecated: The following client primitives are deprecated
      as of protocol version 2026-07-28" for both Sampling and Logging. It
      nowhere says either primitive was withdrawn from the protocol. The
      manuscript writes "A server used to be able to borrow the host's model
      for a completion, and to push log lines at the client; both went out with
      the 2026-07-28 version", and the preceding sentence frames the whole move
      as the protocol being "small enough to retire parts of itself". A reader
      comes away believing sampling and logging no longer exist in 2026-07-28,
      whereas the source describes them as present but discouraged, with the
      "New implementations should..." advice the manuscript correctly relays
      applying to new code rather than to a removal. The defect is structural:
      the retirement framing is set up one sentence earlier, so the repair
      starts there.
  - severity: minor
    article: mcp-in-a-nutshell
    locator: "The host keeps one client per server | The fussiness buys separation | 1"
    category: invented_claim
    note: |
      No passage supports capabilities or a version agreement being held per
      connection, and the source's design point runs the other way: "MCP is a
      stateless protocol. Every request carries the protocol version and the
      capabilities relevant to that request in its _meta field, so the server
      can process each request on its own." The source states one client per
      server ("Each MCP client maintains a dedicated connection with its
      corresponding MCP server") but offers no rationale for it; "The fussiness
      buys separation" and the per-connection capability and version state are
      the manuscript's own. The loose reading, that each client-server pairing
      declares its own capabilities and settles its own version, survives, and
      the manuscript states the statelessness correctly two sections later,
      which is why this is minor rather than a contradiction of the source.
  - severity: minor
    article: mcp-in-a-nutshell
    locator: "One morning on one connection | text in the ordinary case | 1"
    category: invented_claim
    note: |
      The source makes no claim about which content type is typical. It says
      only "In this example, \"type\": \"text\" indicates plain text content,
      but MCP supports various content types for different use cases." The
      manuscript promotes one example to the ordinary case. The second half of
      the clause is well grounded; only the typicality claim is unsupported.
scores:
  claim_support: 4
  qualification_survival: 4
  quote_accuracy: 5
  attribution: 5
notes: |
  I checked every assertion in the manuscript against the single pinned
  extraction: the host/client/server definitions and the one-client-per-server
  rule, the Visual Studio Code and Sentry examples, the STDIO-serves-one versus
  Streamable-HTTP-serves-many split, the "regardless of where it runs" point,
  the three server primitives and the database server that exposes all three,
  elicitation and the client capability that gates it, statelessness and the
  _meta contents, server/discover being mandatory for servers and optional for
  clients, the version-rejection fallback, the cacheable discovery response,
  the tool list fields, the unified registry, the intercept-and-route execution
  path, the content array, opt-in subscriptions via a long-lived stream, the
  no-reply notification and re-list cycle, best-effort delivery with polling as
  backstop, both transports with bearer tokens, API keys and OAuth, the
  inner/outer layer split, the "does not dictate how AI applications use LLMs"
  scope limit, and the Tasks extension. All check out except the three findings
  above. Numbers, names and versions are clean: 2026-07-28, server/discover,
  _meta, Sentry, Visual Studio Code, OpenTelemetry, and the three primitive
  names all match the extraction. Nothing is presented as verbatim quotation,
  so quote accuracy is untested rather than strong. Furniture is sound: the
  label, all five headings and the closing aphorism stay within what the
  extraction supports. The reverse pass found the source's own hedges largely
  intact ("typically" for the serve-one/serve-many split, discovery being
  optional and its answer cacheable, identity sent "unless configured not to",
  best-effort delivery); the one hedge lost is the deprecation. Two source
  asides are dropped without harm under the omission rule, since the piece
  narrates one morning on one connection rather than the general case: the
  progressive tool discovery note for clients federating many servers, and the
  server acknowledging only the subset of a subscription filter it will honor.
  Two things I could not check. The extraction is a rendered documentation page
  whose JSON response bodies are missing (only the request payloads survive),
  so the tool list response fields, the discovery response's supportedVersions
  and server capabilities, and the content array shape are verifiable only
  through the surrounding prose, which was sufficient for every claim the
  manuscript makes about them. Separately, the pipeline handed me conflicting
  content_mode values, in_a_nutshell in the article header and
  original_synthesis in the manuscript frontmatter; I judged truth-grounding
  against the extraction under either reading, which is the part both modes
  share, but the wording bar is nominally unsettled. That is a metadata
  discrepancy for the operator, not a defect in the piece.
