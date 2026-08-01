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

- Article id: `mcp-in-a-nutshell`
- content_mode: `in_a_nutshell`
- Byline: The editors
- Page budget: 7 rendered A5 reader page(s)

The source extraction is deliberately withheld. Judge how this reads, not whether it is true.

## Manuscript

```
---
source_id: architecture-overview-ce5cb1d1
content_mode: original_synthesis
label: IN A NUTSHELL
---

A model can only work with what is put in front of it. The useful material sits
outside: the rows in a database, the schema that explains them, the contents of
a file, whatever an API would say if asked. Something has to fetch that material
and hand it over, and the Model Context Protocol is an agreement about the
handover.

The picture to keep in your head has two halves and one wire. On one side is the
AI application, which owns the model, the conversation, and every decision about
what to do with what it learns. On the other side is a program that owns some
corner of the outside world and offers it as a short, self-describing menu. The
wire carries messages in one fixed format, and each end states what it can do
rather than assuming.

## The host keeps one client per server

Picture Visual Studio Code with a server in front of your team's database.
Visual Studio Code is the host: the AI application that coordinates connections.
It builds a small component, a client, whose only job is to hold one connection
to that one server and pull context back for the host. Connect a second server, say the filesystem server on
the same laptop, and the host builds a second client, one to one.

The fussiness buys separation: each connection carries its own capabilities and
its own version agreement. A server on your machine, talking over standard input
and output, normally serves that one client; a server a vendor runs, such as the
one Sentry operates on its own platform, typically serves many at once. The word
"server" says nothing about where the program runs.

## What a server is allowed to offer

Your database server has three kinds of thing to give away, and the difference
is worth memorizing. It can do something on request: run a query,
take an action with an effect in the world. It can hand over material to read,
such as the schema, which is context and nothing more. And it can supply a
worked template for talking to it, few-shot examples that show a model how to
drive those queries. The specification calls the three tools, resources and
prompts, and calls them primitives: what the two sides can offer each other.

Traffic is not all one way. A server can put a question to the person at the far
end, either because it needs information it lacks or because it wants an action
confirmed before taking it. The request travels back through the client to the
user, which is why the client says up front whether it can collect input at all.
The specification calls this elicitation.

## Every request introduces itself

MCP is stateless. No session is held open on your behalf, so each request
arrives carrying what is needed to judge it: the protocol version the client
speaks, the capabilities relevant to that request and, unless configured
otherwise, who the client is. It rides in a `_meta` field on every request.

Because nothing is remembered, learning what the other side supports is just
another request. A client may open with `server/discover` and get back the
versions the server accepts and its capabilities: which primitives it can
handle, and whether it will report changes to them. Every server must implement
that request. No client is obliged to send it. A client can fire off the request
it wanted and handle a version rejection, which names the versions the server
does accept. The discovery answer is usually cacheable, so it need not be asked
again before every call. The exchange prevents guesswork: each end learns what
the other can handle, so neither attempts an operation the other has never heard
of.

## One morning on one connection

Visual Studio Code starts. Its client manager opens the connection to the
database server, discovery reports that the server offers tools and will
announce changes to them, and the host marks the server ready.

The client asks for the tool list and gets an entry for each one: a unique name
to call it by, a description of what it does and when to use it, and a schema
for its arguments. The host folds those into one registry covering every server
it has connected, and that registry is what the model can reach this
morning. Mid-conversation the model picks one. The application intercepts the
call, routes it to the client that owns that tool, and sends the exact name from
the listing with arguments matching the declared schema. The result comes back
as an array of content, text in the ordinary case though other types are
allowed, and goes into the conversation as material for the next turn.

Later the server's tool list changes. The client hears about it only because it
asked to: change notifications are opt-in, and a client subscribes by opening a
long-lived stream naming the event types it wants. The notice arrives with no
reply expected, the client re-lists the tools, and the registry updates while the
conversation is still running. Delivery is best effort and a notice can be lost
across a reconnect, so a careful client keeps polling anyway.

Nothing in that morning depended on where the server ran. The messages are the
same either way: a local server exchanges them over standard input and output
with no network in the way, a remote one over HTTP posts with an optional event
stream for anything that arrives in pieces, carrying bearer tokens or API keys
that the local case never needs, obtained through OAuth by preference.
Connecting, framing and authorizing belong to that outer layer, and the protocol
proper never looks at it.

## What the protocol declines to decide

MCP covers the exchange of context and stops there. It has nothing to say about
which model you run, how you use it, or what you do with the context once you
have it.

The agreement is small enough to retire parts of itself. A server used to be
able to borrow the host's model for a completion, and to push log lines at the
client; both went out with the 2026-07-28 version, with advice to call a
provider's API directly and to log to standard error or through OpenTelemetry
instead. It grows sideways: an extension lets a server hand back a durable
handle for slow work, so the client can collect the result later instead of
holding a request open.

A server that remembers nothing about you between requests is a server you can
hang up on and call back.
```

## Output contract

Return one YAML document and nothing else, in exactly the shape the line review prompt above specifies. No preamble, no commentary after it. The document may carry only `result`, `findings`, `scores`, `notes`: any other key is refused by the recorder.
