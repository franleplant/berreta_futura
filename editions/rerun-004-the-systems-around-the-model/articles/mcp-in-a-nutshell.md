---
source_ids:
- architecture-overview-ce5cb1d1
content_mode: in_a_nutshell
label: IN A NUTSHELL
---

A model can only work with what is put in front of it, and the useful material sits outside. It is in your team's database, or in the files on your laptop, or behind an API nobody has asked yet. Something has to fetch it and hand it over, and the Model Context Protocol is an agreement about the handover.

The picture to keep in your head has two halves and one wire. On one side is the AI application, which owns the model and every decision about what to do with what it learns. On the other side is a program that owns some corner of the outside world and offers it as a short, self-describing menu. The wire carries messages in one fixed format, and each end states what it can do rather than assuming.

## The host keeps one client per server

Picture Visual Studio Code with a server in front of your team's database. The specification calls it the host, the AI application at that end of the wire. It builds a small component, a client, whose only job is to hold one connection to that one server and pull context back. Connect a second server, say the filesystem server on the same laptop, and the host builds a second client, one to one. The host is the only place those connections meet, and managing them is its job.

## What a server is allowed to offer

Your database server has three kinds of thing to give away. It can take an action on request, running a query or anything else with an effect in the world. Then there is material to read, the schema for instance, which is context and nothing more. Last comes a worked template for talking to it, few-shot examples that show a model how to drive those queries. The specification names these three: tools, resources and prompts. It groups them as primitives, meaning what the two sides can offer each other.

Traffic is not all one way. A server can put a question to the person at the far end, either because it needs information it lacks or because it wants an action confirmed first. The request travels back through the client to the user, which is why the client says up front whether it can collect input at all. Collecting input is the client's own offer back, and the specification calls it elicitation.

## Every request introduces itself

MCP is stateless. No session is held open on your behalf, so each request arrives carrying what is needed to judge it. Every one carries the protocol version the client speaks and the capabilities that matter for it. Unless configured otherwise, the client says who it is as well. All of it rides in a `_meta` field.

Because nothing is remembered, learning what the other side supports is just another request. A client may open with `server/discover` and get back the versions the server accepts along with its capabilities, which primitives it can handle and whether it will report changes to them. Every server must implement that request. No client is obliged to send it. A client can instead send the request it wanted and handle a version rejection, which names the versions the server does accept. The discovery answer is usually cacheable, so it need not be asked again. Either way, neither end attempts an operation the other has never heard of.

## One morning on one connection

Visual Studio Code starts. Its client manager opens the connection to the database server, discovery reports that the server offers tools and will announce changes to them, and the host marks the server ready.

The client asks for the tool list and gets an entry for each one, a unique name to call it by, a description of what it does and when to use it, and a schema for its arguments. The host folds those into one registry covering every server it has connected, and that is what the model can reach this morning. Mid-conversation the model picks one. The application intercepts the call, routes it to the client that owns that tool, and sends the exact name from the listing with arguments matching the declared schema. The result comes back as an array of content, plain text here, and goes into the conversation as material for the next turn.

Later the server's tool list changes. The client hears about it only because it asked to. Notifications are opt-in, and a client subscribes by opening a long-lived stream naming the event types it wants. The notice arrives with no reply expected, the client re-lists the tools, and the registry updates while the conversation is still running. Delivery is best effort and a notice can be lost across a reconnect, so a careful client keeps polling anyway.

Nothing in that morning depended on where the server ran. The database server sits on the same laptop, and its messages travel over standard input and output with no network in the way. A server a vendor runs, such as the one Sentry operates on its own platform, receives the same messages over HTTP posts. What it adds is only what the local case lacks. An optional event stream for anything arriving in pieces, and a bearer token or API key, obtained through OAuth by preference. The local server usually serves that one client and the remote one serves many, and the word "server" says nothing about where the program runs. Making the connection and proving who you are belong to the transport underneath, and the protocol proper never looks down there.

## What the protocol declines to decide

MCP covers the exchange of context and stops there. It has nothing to say about which model you run, or what you do with the context once you have it.

The same restraint governs how it changes. Collecting input is not the only offer a client makes. A client can also lend the host's model to a server that wants a completion written without carrying a model of its own, and it can take log lines from a server for debugging. The 2026-07-28 version deprecated both of those. Deprecated is all it did. Both methods are still in the protocol and both still work, and what changed is the advice for new code, which is to call a language-model provider directly and to log to standard error or through OpenTelemetry.

Growth happens sideways instead. An extension lets a server hand back a durable handle for slow work, so the client can pick up the result later rather than hold a request open. Nothing waits on the connection while that work runs, so the connection can go away and cost nobody anything.

A server that remembers nothing about you between requests is a server you can hang up on and call back.
