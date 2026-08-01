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

<!-- SCRATCH: not part of the manuscript -->

## 1. Pre-writing, as the prompt required

**Q1. What did people do before this existed, and what broke?**
The extraction does not answer this. There is no history, no prior art, no
account of bespoke connectors, no combinatorial framing. The nearest material is
the scope note ("MCP focuses solely on the protocol for context exchange") and
the data-layer note that the primitives are "the ways developers can share
context from MCP servers to MCP clients." So I answered in the only form the
source supports: the problem is structural, not historical. A model works on
what is placed in front of it, the material worth placing there lives outside
the application, and somebody has to define the handover. Anything sharper would
have been my own knowledge, which hard rule 5 forbids.

**Q2. The mental model, in two or three plain sentences.**
Two halves and one wire. The AI application owns the model, the conversation and
every decision about what to do with context; the server owns a corner of the
outside world and publishes it as a self-describing menu. Neither side knows how
the other is built, so both announce their capabilities on every request instead
of assuming.

**Q3. The single concrete scenario that carries the piece.**
Visual Studio Code as the host, connected to a server that fronts a database.
Both halves are in the source: VS Code is the source's named example of a host,
and a local database server is named in the participants diagram, with the
source's own worked example of what such a server exposes (query tools, a schema
resource, a few-shot prompt). It is the only candidate that reaches every
concept: participants, one client per server, all three server primitives,
discovery, a tool call and a tool-list change. The filesystem server appears
once, to show a second client being built. Sentry appears once, for the contrast
the primary example cannot draw: a remote server serving many clients. The
source's weather tool and its San Francisco call were left out on purpose,
because importing them would have created the second running example the prompt
bans; the walkthrough uses the database server's own tools instead.

**Q4. Six things the reader must be able to answer at the end.**
1. What does MCP standardize, and what does it leave alone? (Context exchange
   only; not model choice, not context management.)
2. Who are the participants? (Host = the AI application; one client per server,
   each holding a dedicated connection; server = the program serving context,
   wherever it runs.)
3. What can a server offer? (Actions, readable context, interaction templates:
   tools, resources, prompts.)
4. How does either side find out what the other supports? (Version and
   capabilities in `_meta` on every request; `server/discover` mandatory to
   implement, optional to send, answer usually cacheable.)
5. Why does the transport not change the protocol? (Same messages over stdio
   locally or HTTP remotely; connection, framing and auth live in the outer
   layer.)
6. What follows from statelessness? (Every request self-contained; change
   notifications opt-in and best effort, so clients still poll.)

Running example fixed: **VS Code plus the database server.** Every section
returns to it.

## 2. Assessment of the prompt contract

**Clear and load-bearing.**
- "The mental model appears within the first 150 words." The single most useful
  instruction. It forced the structure: the problem paragraph had to be short
  and the who-owns-what passage had to lead. It lands at word 62 here.
- "Never mirror the source's own table of contents," with a worked example of a
  good heading. Concrete enough to act on. I checked my headings against the
  source's contents (Scope, Participants, Layers, Data layer, Transport layer,
  Statelessness and discovery, Primitives, Notifications, Example) and none
  survives; layers and transports are folded into the walkthrough, where they
  answer a question the scene has already raised.
- "No enumeration of method names... a method name appears only where the reader
  needs to recognize it in the wild, inside a sentence." Sharp and testable. Two
  survive (`server/discover`, `_meta`), both inside sentences, neither as a
  section subject. The source's JSON-RPC blocks, roughly half its length, drop
  out.
- "One running example throughout. A second example only to draw a contrast the
  first cannot, and only once." This is what kills the duplicate-example
  failure, because it makes the writer name the example before drafting.
- "Concept first, term second, in the same sentence." Easy to apply and it
  visibly changes the prose.
- The anti-exemplar section. Naming the failure and its symptoms was more useful
  than any positive instruction.

**Vague, unhelpful or missing.**
- Procedure question 1 assumes a source with a history. This one has none. The
  prompt offers no fallback, so it pushes the writer toward inventing a
  before-state that hard rule 5 then forbids. Two rules collide and the
  collision is invisible until you are drafting. It needs a clause: if the source
  does not describe the prior state, state the problem structurally and do not
  reconstruct history.
- Length is stated in three disagreeing ways: my brief said 700 to 1,100, the
  prompt says roughly 800 to 1,100 body words, and both say seven A5 pages hard
  maximum. Word counts do not map cleanly onto pagination and the writer cannot
  run the renderer. My first draft came in at 1,220 and had to be cut on a rule
  I could not verify.
- Step 3 prescribes five sections in a fixed order, which is close to a template
  and sits awkwardly beside the ban on mirroring a table of contents. It is a
  good order, but a piece that follows it literally has a predictable shape. I
  merged parts of (c) and (d) and put the transport material inside the
  walkthrough; the prompt does not say whether that is allowed.
- "Every claim must be traceable to the source" is right but silent on obvious
  inferences. I dropped several useful sentences the source implies but never
  states, for instance that a server written once works under any host.
- Nothing is said about deprecated features. A newcomer meets sampling and
  logging only as tombstones. I gave them two clauses because the deprecation
  shows where the seam is, but that was my call.
- The frontmatter block shows `source_id` singular with a note about
  `source_ids`, while the live `edition.yaml` row for this article uses the
  plural with one entry. A writer copying the prompt literally produces
  frontmatter that does not match the manifest. I followed the prompt.
- The prompt does not say whether the piece may name the source ("the
  specification calls these..."). In `original_synthesis` this reads as
  attribution rather than the narrator scaffolding banned by tic 6, but it is a
  judgment call the contract should make for the writer.
- The six comprehension answers are generated by the writer and then never used
  as a checklist against the finished draft, even though the novice judge writes
  its own six. Making the writer verify the draft against its own six would
  close that loop.

**Invented because the prompt did not say:** the number of sections and their
boundaries; that the boundary section could absorb the deprecations; that the
closing line should stand alone; and the decision to leave the source's weather
tool out entirely. I also dropped a sentence listing what ships under the MCP
name (specification, SDKs, Inspector, reference servers) purely to make budget,
which is orientation a novice would have valued.

Manuscript body: 1,099 words including headings, 1,065 of prose. The first
draft was 1,220 and had to be cut by hand against a limit I cannot measure.

## 3. After reading the shipped version

Read only after the draft above was finished. It is 1,042 words to my 1,099, so
length is not the difference; what the words do is.

**Concrete differences.**
- Headings. Shipped: "Host, client, server", "Two layers", "The three server
  primitives", "A request from discovery to action", "Practical uses", "Client
  features and notifications", "The useful boundary". Four of the seven are the
  source's own section names or near-paraphrases, and "Host, client, server" is
  the source's bullet list promoted to a heading. Mine are five claims about the
  world, none naming a spec section.
- Where the teaching sits. The shipped piece does state the boundary in its
  first paragraph, which is better than the diagnosis suggested, but the
  ownership model itself ("The host owns intelligence and orchestration. Each
  client owns one protocol relationship. Each server owns a bounded set of
  context and actions") is the final section, 91 words. Mine opens on it, at
  word 62, and the rest of the piece spends it.
- Method and identifier names. Shipped: `tools/call`, `tools/list`,
  `resources/list`, `prompts/list`, `server/discover`, `_meta`, plus invented
  identifiers `query_database`, `diagnose_slow_query`, `weather_current`,
  `location`, `units` and a literal argument object. One sentence enumerates
  three list methods in a row. Mine names two, both inside sentences.
- Examples. Shipped uses four: VS Code with the filesystem and Sentry servers, a
  database server, a weather tool, and then a "Practical uses" section that
  repeats the first two almost verbatim ("A coding host such as Visual Studio
  Code can connect to a local filesystem server and a remote Sentry server. Each
  connection gets its own MCP client" against the earlier "Suppose Visual Studio
  Code connects to a local filesystem server and a remote Sentry server... The
  connections remain separate"). The stdio-versus-Sentry contrast also appears
  twice. Mine has one example, with the filesystem server as a single beat and
  Sentry as a single contrast.
- Accuracy against the source. The shipped piece invents tool and prompt names
  the source never gives, adds "The server validates the input", and opens its
  walkthrough with "First, the client asks the server what protocol versions and
  capabilities it supports through `server/discover`", which contradicts the
  source's statement that calling discovery is optional. It omits statelessness
  as a named idea, the best-effort caveat on notifications, the advice to keep
  polling, cacheability, and the deprecations.
- Ending. Shipped closes on "Tool builders can publish stable typed primitives
  while AI applications compete on how well they use them", which restates the
  separation argument rather than landing. It also opens its last section on
  "MCP is often described as a connector standard. The architecture is more
  precise than that", a cousin of the banned antithesis without being the banned
  form itself. Mine closes on statelessness and does not summarize.
- Mode. The shipped article is `faithful_synthesis` labelled FAITHFUL SYNTHESIS,
  with the protocol project itself as author. The new prompt makes the piece
  `original_synthesis` under an editor byline. That change is upstream of every
  other difference: a faithful synthesis of a specification is close to
  obligated to walk the specification, which is most of why the shipped piece
  reads as a spec dump.

**Did the new prompt prevent the four documented failures?**
1. Headings mirroring the specification: prevented. The rule is explicit, comes
   with a worked example, and the anti-exemplar names the offending headings.
2. Reciting method names: prevented, and this is the sharpest rule in the
   contract because it says exactly where a method name may appear. It would
   also have caught the invented `query_database` and `diagnose_slow_query`,
   which are a fidelity problem the rule catches as a side effect.
3. The duplicated example: prevented for a single writer, because fixing the
   running example is step 2 and precedes drafting. But the documented cause was
   two source chunks processed independently, and the shipped duplication is
   visibly a whole redundant "Practical uses" section rather than a slip. This
   prompt has no defence against chunked processing; it assumes one writer
   holding the whole extraction. If the pipeline still chunks, the rule is a
   hope rather than a mechanism.
4. The mental model arriving last: prevented, and the 150-word rule is the
   reason. A soft instruction to lead with the model would not have survived the
   pull of the source's own order.

**Verdict.** Sufficient for the four failures it was written against, and three
of the four are prevented by mechanism rather than exhortation. Two gaps: the
missing history in this source, where two of the prompt's own rules pull in
opposite directions with no guidance, and the assumption that failure 3 was a
writing failure when the evidence says it was a pipeline failure.
