---
source_ids:
- architecture-overview-ce5cb1d1
content_mode: faithful_synthesis
label: FAITHFUL SYNTHESIS
---

Visual Studio Code connects to the Sentry MCP server, and the VS Code runtime creates one MCP client object dedicated to that connection. Connect the local filesystem server next, and the runtime creates a second client, wired to nothing but the filesystem server. Every server VS Code talks to gets its own client, one connection each, never shared between them. VS Code is what the protocol calls the host: the application that opens and manages every one of these client-server pairs. The Sentry server runs on Sentry's own platform and speaks Streamable HTTP. The filesystem server runs on the same laptop as VS Code and speaks stdio, standard input and output passed directly between two local processes. That distinction is only about where the server runs. Note that MCP server refers to the program that serves context data, regardless of where it runs.

MCP focuses solely on the protocol for context exchange—it does not dictate how AI applications use LLMs or manage the provided context. Underneath the host-client-server picture sit two layers. The data layer is a JSON-RPC 2.0 exchange: the message format, the request and response shapes, and the primitives a server can offer. The transport layer carries those messages between processes: stdio for two processes on the same machine, with no network in between, and Streamable HTTP for everything remote, plain HTTP POST with an optional Server-Sent Events stream layered on top. Streamable HTTP also carries authorization, bearer tokens, API keys, or custom headers, with MCP recommending OAuth as the way to obtain those tokens. Whichever transport a server uses, the JSON-RPC messages crossing it look the same, so a client written against the data layer doesn't change when a server moves from a laptop to a remote deployment.

## No memory between requests

MCP is stateless. Every request a client sends carries the protocol version it's speaking and its declared capabilities in a `_meta` field, along with its identity unless it's been configured to withhold it, so a server can answer the request in front of it without needing to remember any of the ones before it. A client can send `server/discover` first to get a server's supported versions, capabilities, and identity in one round trip, but it's optional: since every other request already carries the same information, a client can just send the request it wants and handle a version mismatch if one comes back. When it does mismatch, the server rejects the request with an `UnsupportedProtocolVersionError` listing the versions it will accept, and the client retries with one of those. The discovery response is also typically cacheable, so a client that has already called `server/discover` doesn't need to call it again before every request.

## What a server can offer

A server exposes context through three primitives: tools it can execute, resources it can hand over, and prompts, reusable templates for structuring an interaction with a model. A server built around a database, for instance, can expose tools for querying it, a resource holding its schema, and a prompt with few-shot examples for using the tools correctly. Each primitive follows the same pattern: a client calls `tools/list`, `resources/list`, or `prompts/list` to see what's on offer, then `tools/call` to run one. A tool's `name` is what the client will use to call it again, which is why the spec asks for something like `calculator_arithmetic` rather than just `calculate`: the name has to stay unique and identifiable inside the server's own namespace, not just readable in the moment. Its `inputSchema` is what lets the client validate arguments before the call ever leaves, and a response can say how long it's safe to treat as current, so a client isn't forced to refetch a list that hasn't changed.

## What a client can offer back

A client has its own primitive to offer: elicitation, which lets a server ask the user directly for something it needs, through `elicitation/create`. The specification deprecated two more client primitives as of protocol version `2026-07-28`. Sampling let a server ask the client's own model to finish a completion, useful for a server author who wanted a model without shipping an LLM SDK inside their own server; new servers should call an LLM provider's API directly instead. Logging let a server send log messages to the client for debugging; new servers should write to stderr over stdio or use OpenTelemetry instead. Both went in the same release, and both point the same direction: a server should reach the infrastructure it needs on its own rather than borrowing the client's.

## Extensions on top of the core

Optional extensions build on top of the core primitives without changing them. The Tasks extension is one already shipping: it lets a server hand back a durable handle for a request that will take a while, instead of holding the connection open until it finishes, so the client can poll that handle for status and come back for the result whenever it's ready.

## Changes nobody has to poll for

Notifications are opt-in. A client that wants them opens a long-lived stream with `subscriptions/listen`, naming the event types it wants, `toolsListChanged` among them, and the server acknowledges with the subset of that filter it actually supports. From then on, when the server's tools change, it sends a notification on that stream tagged with the subscription's own ID, so a client juggling several subscriptions knows which one just fired. A client that gets one typically responds by calling `tools/list` again, which is what turns a single notification into a refreshed registry the model can act on. None of it is guaranteed: there are no guarantees that every notification will be sent or received, particularly across transport reconnects. A client still has to poll on its own to keep results fresh, which means nothing downstream was ever depending on the notification showing up in the first place.

<!-- SCRATCH: not part of the manuscript -->

**The sentence.** A reader leaves knowing which of the six moving pieces, host, client, server, data layer, transport layer, primitive, does what and how they connect, in the order someone deciding what a server should expose needs them, without reading a single JSON-RPC payload to get there.

**The two absences.**
1. The full request/response walkthrough: all five JSON-RPC message bodies (discover, tools/list, tools/call, subscriptions/listen, notification) and the paired "Understanding the X Request/Response" field-by-field breakdowns.
2. The "Scope" section listing MCP's four sub-projects (Specification, SDKs, Development Tools, Reference Server Implementations), the "How This Works in AI Applications" pseudo-code blocks, and the "Why Notifications Matter" four-item list.

**Claim ladder.**
- Central claim: MCP is a stateless, JSON-RPC-based client-server protocol, wrapped in a swappable transport, structured around three server primitives and a smaller set of client primitives, with opt-in notifications layered on top but never load-bearing.
- Host creates one client per server; local servers use stdio, remote servers use Streamable HTTP (evidence: VS Code + Sentry + filesystem example).
- Two layers: data layer (JSON-RPC, primitives, discovery) is transport-independent; transport layer (stdio / Streamable HTTP) carries auth.
- Statelessness: `_meta` on every request carries version + capabilities + identity; `server/discover` is an optional, cacheable convenience, not a requirement; version mismatch handled via `UnsupportedProtocolVersionError`.
- Server primitives: tools, resources, prompts; discovered via `*/list`, invoked via `tools/call`; naming convention example (`calculator_arithmetic` vs `calculate`); `inputSchema` validates before the call; responses can carry cache guidance.
- Client primitives: elicitation is current; sampling and logging deprecated as of `2026-07-28`, each with a stated replacement (call the LLM API directly; log to stderr/OpenTelemetry).
- Extensions are optional and additive; Tasks extension is the one example given (durable handle, poll for status).
- Notifications are opt-in via `subscriptions/listen`, acknowledged with the supported subset, tagged with a subscription ID; explicitly best-effort, so clients must still poll.
- Qualifications preserved: discovery is optional not mandatory; caching is "typically" available, not guaranteed; notification delivery has no guarantee, especially across reconnects.

**Voice signature (retained verbatim).**
1. "MCP focuses solely on the protocol for context exchange—it does not dictate how AI applications use LLMs or manage the provided context."
2. "Note that MCP server refers to the program that serves context data, regardless of where it runs."
3. "There are no guarantees that every notification will be sent or received, particularly across transport reconnects."
This source is institutional documentation with little personal register; these three are its closest thing to a voice, each a candid scope- or limits-admission rather than a boast, so I kept the strongest ones and let the rest of the piece run in plain declarative sentences rather than manufacturing personality that isn't there.

**What step 3 dropped and why.**
- All five JSON-RPC example payloads and their field-by-field commentary: the argument survives on what each call does and what identifiers matter (`tools/call`, `name`, `inputSchema`), not on the exact envelope.
- The four pseudo-code snippets ("How This Works in AI Applications"): illustrate implementation, not the protocol; the sentence in each ("register tools", "refresh on notification") is already carried by the surrounding prose.
- The "Scope" section (four sub-projects: Specification, SDKs, Dev Tools, Reference Servers): orients a contributor to the GitHub org, not a reader learning the protocol.
- The specific `ttlMs`/"five minutes" cache example and `cacheScope`: the argument (responses can say how long they're good for) doesn't change if the number does, so I kept the mechanism and cut the number, per Move 7.
- The `weather_current` / San Francisco tool-call example: redundant with the `calculator_arithmetic` naming example already carrying the "why names matter" point; two illustrations of the same idea, so I kept one (Move 1).
- Identity exchange (`clientInfo`/`serverInfo` for debugging) and progressive tool discovery for federated clients: real but secondary; neither changes what a first-time reader needs to build a mental model.
- "Why Notifications Matter" four-item list: each item restates a property already demonstrated in the walkthrough (opt-in, best-effort); folded the surviving content into the closing paragraph instead of reproducing the list.
