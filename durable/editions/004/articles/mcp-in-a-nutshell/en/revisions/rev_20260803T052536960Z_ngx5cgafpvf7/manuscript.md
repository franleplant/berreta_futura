---
source_ids:
- architecture-overview-ce5cb1d1
content_mode: in_a_nutshell
label: IN A NUTSHELL
---

A language model cannot look anything up. Ask one for the weather in San Francisco this afternoon and it has no way to find out, so another program has to go and get it and hand it back in a form the model can act on. The Model Context Protocol is the agreement covering that handover: what the fetching program may offer, and how the two ends talk about it.

Underneath are two programs and one wire. At one end is the AI application, which owns the model and every decision about what to do next. At the other is a small program that owns one corner of the outside world, a weather service here, and publishes a short menu of what it holds and what it can do. The wire carries requests and answers in one fixed format, JSON-RPC, and forgets each exchange as soon as it is answered. No session is held open on your behalf, and that one decision explains most of the rest.

## One client per server, and a menu at the far end

Picture Visual Studio Code with a weather server connected to it. The specification calls the editor the host, the AI application at that end of the wire. The editor builds a small component whose whole job is to hold that one connection and bring context back: the client. Connect a second server, the filesystem server on the same laptop say, and the editor builds a second client for it. One per server, and the host is the only place the connections meet.

The weather server has one thing to offer: an action someone can ask it to take, with an effect out in the world. Other servers have material to hand over and nothing more, the contents of a file or a row from a database. A third kind is a template for driving the other two, few-shot examples showing a model how to phrase a query. The specification names them tools, resources and prompts, and calls the three primitives. Learn the shape once and it covers all three: a `*/list` call to see what is there, a `*/get` to pull one back, and for tools a `tools/call` to run it. What a server offers can change between conversations.

Offers run both ways. A server about to do something it cannot undo can put a question back through the client to the person at the keyboard. The specification calls that elicitation, and a client that can collect input says so in the capabilities it attaches to every request.

## Nothing is remembered, so every request introduces itself

Each request has to arrive judgeable on its own. Every one carries the protocol version the client is speaking and the capabilities that bear on it, plus, unless the client has been configured to stay quiet about it, its own name and version. All of that rides in a field called `_meta`. You will probably never type its contents: the field names are long reverse-DNS strings and the SDKs exist to abstract that sort of thing away, which is why the specification points most developers at the data layer rather than at the plumbing under it.

Finding out what the other end supports is then just another request. A client that wants to know up front sends `server/discover` and gets back the versions the server accepts, which primitives it handles, and whether it will announce changes to them. Every server must implement that request. No client has to send it: a client can go straight to the request it wanted and handle a version rejection, which names the versions the server does accept. The answer is usually cacheable, so it is asked once and reused.

## From a cold start to a temperature

Visual Studio Code starts, the client manager opens the connection, discovery reports that the server has tools and will announce changes to them, and the editor marks it ready. The client asks what those tools are with `tools/list`. Back comes an entry for each one: the name to call it by, a description of what it does and when to use it, a JSON Schema for its arguments, and a hint about how long the list may be cached. The editor folds the entries from every connected server into one registry, and that is what the model can reach this morning.

Mid-conversation the model picks the weather tool. The application intercepts the call, finds the client that owns that tool, and sends `tools/call`, where two things have to be right. The name must be the exact string from the listing, `weather_current`, longer than anyone would guess and deliberately so: the specification tells server authors to name a tool `calculator_arithmetic` rather than `calculate`. The arguments must match the schema, a required location, San Francisco, and an optional units, imperial here, which would otherwise default to metric. Back comes an array of content blocks, plain text this time, and into the conversation it goes as material for the next turn.

Then the tool list changes on the server. The editor hears about it only because it asked to. A client subscribes by opening a long-lived stream with `subscriptions/listen`, naming the events it wants, `toolsListChanged` here, and the server acknowledges with the subset of that filter it will honour. The notice, when it comes, has no id and expects no reply. The client re-lists the tools, and the registry changes while the conversation is still running. None of this is guaranteed: delivery is best effort, a notice can be lost across a reconnect, and a careful client keeps polling after it subscribes.

## What it will not decide for you

MCP covers the exchange and stops there. It has nothing to say about which model you run or what you do with the context once it arrives.

Where the server runs is barely a decision either. One on your own machine speaks over standard input and output, with no network in the way. One a vendor operates takes HTTP posts, adds an optional event stream for answers arriving in pieces, and wants a bearer token or an API key, by preference obtained through OAuth. The messages are identical either way, which is the point of splitting the data layer from the transport under it. Until you deploy something remote, that is a chapter you can skip.

Two more you can skip outright. A server used to be able to borrow the host's model for a completion, and to send its log lines to the client for debugging. The specification calls those sampling and logging, and the 2026-07-28 version deprecated both: new code calls a model provider directly and logs to standard error or through OpenTelemetry. The protocol grows sideways instead, through extensions, one of which lets a server answer slow work with a durable handle the client comes back for, so nothing sits holding a request open.

A client that only ever sends `tools/list` and `tools/call` is a working client. The rest of the specification is what you read the week one of those two surprises you.

```yaml
comprehension_questions:
- What does MCP define, and what does it deliberately leave to the AI application?
- One AI application is connected to three servers. How many clients exist, and who manages them?
- Which request asks a server what protocol versions and capabilities it supports? Must every server implement it, and must every client send it?
- Which two calls take a client from knowing nothing about a server to holding a result, and what must match exactly between them?
- What must a client do to be told when a server's tool list changes, and why should it keep polling anyway?
- Since no session is held open, what does every request have to carry, and in which field?
```
