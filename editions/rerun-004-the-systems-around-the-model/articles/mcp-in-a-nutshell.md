---
source_ids:
- architecture-overview-ce5cb1d1
content_mode: in_a_nutshell
label: IN A NUTSHELL
---

A model can only work with what is put in front of it. The useful material sits
outside. Rows in a database, the schema that explains them, the contents of a
file, whatever an API would say if asked. Something has to fetch that material
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
Visual Studio Code is the host, the AI application that coordinates connections.
It builds a small component, a client, whose only job is to hold one connection
to that one server and pull context back for the host. Connect a second server,
say the filesystem server on the same laptop, and the host builds a second
client, one to one.

Each client holds a connection dedicated to one server and nothing else. The
host is the only place those connections meet, and managing them is its job.

## What a server is allowed to offer

Your database server has three kinds of thing to give away. It can do something
on request, running a query or taking any other action with an effect in the
world. It can hand over material to read, the schema for instance, which is
context and nothing more. And it can supply a worked template for talking to it,
few-shot examples showing a model how to drive those queries. The specification
names these three tools, resources and prompts, and groups them as primitives,
meaning what the two sides can offer each other.

Traffic is not all one way. A server can put a question to the person at the far
end, either because it needs information it lacks or because it wants an action
confirmed before taking it. The request travels back through the client to the
user, which is why the client says up front whether it can collect input at all.
The specification calls this elicitation.

## Every request introduces itself

MCP is stateless. No session is held open on your behalf, so each request
arrives carrying what is needed to judge it. The protocol version the client
speaks, the capabilities relevant to that request and, unless configured
otherwise, who the client is. All of it rides in a `_meta` field.

Because nothing is remembered, learning what the other side supports is just
another request. A client may open with `server/discover` and get back the
versions the server accepts along with its capabilities, which primitives it can
handle and whether it will report changes to them. Every server must implement
that request. No client is obliged to send it. A client can instead fire off the
request it wanted and handle a version rejection, which names the versions the
server does accept. The discovery answer is usually cacheable, so it need not be
asked again before every call. Guesswork drops out either way, and neither end
attempts an operation the other has never heard of.

## One morning on one connection

Visual Studio Code starts. Its client manager opens the connection to the
database server, discovery reports that the server offers tools and will
announce changes to them, and the host marks the server ready.

The client asks for the tool list and gets an entry for each one, a unique name
to call it by, a description of what it does and when to use it, and a schema
for its arguments. The host folds those into one registry covering every server
it has connected, and that registry is what the model can reach this morning.
Mid-conversation the model picks one. The application intercepts the call,
routes it to the client that owns that tool, and sends the exact name from the
listing with arguments matching the declared schema. The result comes back as an
array of content, plain text here, though the format carries other types too,
and goes into the conversation as material for the next turn.

Later the server's tool list changes. The client hears about it only because it
asked to. Change notifications are opt-in, and a client subscribes by opening a
long-lived stream naming the event types it wants. The notice arrives with no
reply expected, the client re-lists the tools, and the registry updates while the
conversation is still running. Delivery is best effort and a notice can be lost
across a reconnect, so a careful client keeps polling anyway.

Nothing in that morning depended on where the server ran. The database server
sits on the same laptop, and its messages travel over standard input and output
with no network in the way. A server a vendor runs, such as the one Sentry
operates on its own platform, receives the same messages over HTTP posts. What
it adds is only what the local case lacks. An optional event stream for anything
that arrives in pieces, and a bearer token or API key, obtained through OAuth by
preference. The local server usually serves that one client and the remote one
serves many, and the word "server" says nothing about where the program runs.
Connecting, framing and authorizing belong to that outer layer, and the protocol
proper never looks at it.

## What the protocol declines to decide

MCP covers the exchange of context and stops there. It has nothing to say about
which model you run, or what you do with the context once you have it.

The same restraint governs how it changes. The 2026-07-28 version deprecated two
of the abilities a client can offer. A server can still borrow the host's model
for a completion, and can still send log lines to the client for debugging. Both
methods remain in the protocol and both still work. What changed is the advice
for new code, which is to call a language-model provider directly, and to log to
standard error or through OpenTelemetry.

Growth happens sideways instead. An extension lets a server hand back a durable
handle for slow work, so the client can ask after it and pick up the result later
rather than hold a request open.

It loses nothing by going away, because nothing was being held for it. A server
that remembers nothing about you between requests is a server you can hang up on
and call back.
