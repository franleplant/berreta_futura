---
source_ids:
- workers-durable-objects-beta-a-new-approach-to-s-1a040568
content_mode: article
label: ARTICLE
---

Workers could run code at the edge, but not hold state with strong consistency or coordinate clients in real time, so those parts of your application still had to be hosted elsewhere. Durable Objects close that gap. Each object is an instance of a class, with a globally unique ID, existing in only one location in the world at a time, and with private durable storage on disk beside it. Any Worker that knows the ID can send it a message, and every such message lands in the same place. That is what makes coordination possible: chat rooms, collaborative documents, rate limiters. Today we begin a closed beta. Objects are a low-level primitive, not yet a complete database.

## What an object is

Three words, each doing work. It is an *object* in the sense of object-oriented programming: a class definition in JavaScript, methods forming a public interface, code married to private state. It is *unique*: one globally unique identifier, one instance anywhere in the world, all messages converging on it. It is *durable*: state persists on disk, private to that object, so access is fast and the object can safely hold a consistent copy in memory and operate on it with zero latency. When idle it shuts down; when needed again it is recreated.

Reaching one from anywhere looks like this:

```js
// Derive the ID for the counter object named "my-counter".
// This name is associated with exactly one instance in the
// whole world.
let id = COUNTER_NAMESPACE.idFromName("my-counter");

// Send a request to it.
let response = await COUNTER_NAMESPACE.get(id).fetch(request);
```

## Why coordination is the point

Take a spreadsheet two people edit at once. Store keystrokes in a database and poll for updates, and at best latency is poor, at worst transactions fail as users on opposite sides of the world fight over the same content. The secret is a live coordination point: both users connect to it, usually over WebSockets, it forwards keystrokes each way, resolves conflicts instantly, and writes back to storage asynchronously from its in-memory copy. Every big-name collaborative editor works this way. Standard serverless infrastructure has never made it easy to assign such a point.

Our open source chat demo does it in a few hundred lines: one object per room, users on WebSockets, messages relayed directly between them, history kept in storage. A second kind of object rate-limits each IP and stores nothing at all, since it only cares about recent history. Any single room's scalability has a limit, because each object is single-threaded, but that limit is far beyond what a human participant could keep up with.

## No regions

Cloudflare picks the datacenter an object lives in and can migrate it transparently toward the users using it. So you design storage to match your application's logical data model: an object per document, an object per chat. Millions or billions of them are no problem, as each carries minimal overhead. Clients on the far side of the world from a transaction still pay for the speed of light; auto-migration is how we intend to fight that.

## What is missing

Each object sees only its own data. Queries or transactions across objects take extra work from the application. But every large distributed database is, underneath, composed of chunks, and its real job is coordinating them. We see a future of edge databases that store each chunk as a Durable Object, built by us or by anyone.

Serverless compute succeeded by cutting compute into the unit developers already think in: the event. Serverless state means cutting state into the unit the application already has, which is not a table or a graph but a room, a spreadsheet, a shopping cart. That is what Durable Objects do.

Storing data is a responsibility we do not take lightly, so we are being careful and will open access gradually over the next several months. Some of what I have described is not fully enabled yet; the documentation lists the beta's limits. There is no longer any reason to make users refresh for updates.
