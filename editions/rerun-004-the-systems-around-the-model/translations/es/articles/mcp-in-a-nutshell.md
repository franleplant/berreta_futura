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
