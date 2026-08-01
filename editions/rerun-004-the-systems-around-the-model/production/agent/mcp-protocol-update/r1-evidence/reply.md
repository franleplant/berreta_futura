result: approved
findings: []
scores:
  claim_support: 5
  qualification_survival: 4
  quote_accuracy: 5
  attribution: 5
notes: |
  I read the complete pinned extraction of
  the-2026-07-28-mcp-specification-release-candida-1a1752b8 in full before the
  manuscript, confirmed the manuscript's declared source_ids matches it, then
  enumerated every checkable assertion in the piece: the opening claim that a
  server that needed sticky sessions, a shared session store, and deep packet
  inspection can now run behind a plain round-robin load balancer and that this
  is the largest revision since launch; all six section headings; the removal
  of the initialize/initialized handshake and of the Mcp-Session-Id header; the
  migration of protocol version, client info, and client capabilities into
  _meta; server/discover; the SEP-2260 rule that server-initiated requests may
  issue only while the server is processing a client request (recommended
  before, now required); InputRequiredResult and the echoed requestState
  replacing a held-open SSE stream; the explicit-handle pattern with basket_id
  and browser_id; the Mcp-Method and Mcp-Name header requirement; ttlMs and
  cacheScope modeled on HTTP Cache-Control with tools/list freshness and
  cross-user sharing; the fixed traceparent, tracestate, and baggage key names
  and the single OpenTelemetry span tree; the extensions map, ext-*
  repositories, independent versioning, and the Extensions Track; two official
  extensions; MCP Apps' sandboxed iframe, ahead-of-time template declaration
  for security review, and the shared JSON-RPC audit and consent path; Tasks
  shipping experimentally in the last release, moving to an extension, the
  removal of tasks/list for want of session scoping, and the migration burden;
  the Roots, Sampling, and Logging deprecations with all three replacements and
  the annotation-only, one-year, separate-SEP conditions; iss validation per
  RFC 9207, the mix-up-attack rationale tied to the single-client, many-server
  pattern, and the future rejection of responses omitting iss; the -32002 to
  -32602 Invalid Params change; the three governance SEPs, the Active /
  Deprecated / Removed lifecycle with at least twelve months to earliest
  removal, extension-first stabilization, and the conformance-suite gate on
  Final status tied to the SDK tier system; and the May 21, 2026 lock, July 28,
  2026 publication, and ten-week validation window. Every one of them has a
  directly corresponding passage in the extraction; no number, date, version
  string, header name, method name, error code, or RFC number is altered, and
  the byline matches the extraction's two lead maintainers, which also licenses
  the manuscript's first-person "we". The reverse pass found the source's
  hedges intact: "annotation-only", "at least twelve months", "before, if
  ever", "our expectation is", "we don't intend for that to be the norm", and
  the concession that this release contains breaking changes all survive, and
  the manuscript reaches no thesis the source does not. Two compressions I
  examined and judged sub-threshold rather than findings: the closing sentence
  drops the source's co-condition "and with deprecation windows and extensions
  as the standard tools going forward", but the immediately preceding paragraph
  states both of those mechanisms explicitly, so the condition still reads; and
  "never really allowed" becomes "never allowed", which is not presented as a
  quotation and does not change the meaning. Omissions elsewhere are the
  permitted kind: the Authorization Hardening section beyond iss, the JSON
  Schema 2020-12 section, all SEP numbers, the Tier 1 SDK expectation, the
  header/body disagreement rule, and inputResponses alongside requestState are
  dropped detail, not dropped qualification, counterargument, or conclusion.
  What I could not check: the manuscript carries no title, deck, figure
  caption, or pull quote, so any furniture added downstream is outside this
  audit, and the extraction is a lossy text capture of a blog post whose two
  diagrams and one truncated JSON body I could only read as far as the capture
  preserves them, though no manuscript claim depends on the truncated portions.
