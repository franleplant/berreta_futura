---
source_ids:
- workers-durable-objects-beta-a-new-approach-to-s-1a040568
content_mode: article
label: ARTICLE
---

Workers made compute at the edge cheap, stateless, and quick to deploy, and Workers KV added storage that is eventually consistent. Neither gives you strong consistency or real-time coordination there, so those parts of your application still had to be hosted elsewhere. Durable Objects close that gap. Each one is an instance of a class you write, with a globally unique ID, existing in one location in the world at a time, with private durable storage beside it. Any Worker anywhere that knows the ID can send it messages, and they all end up in the same place. That is enough to run a chat room, a shopping cart, or a shared document with no centralized origin server at all. Today we are beginning a closed beta.

## What the name means

**Objects:** instances of a class, written in JavaScript or your language of choice, combining code with private state, with methods for the public interface. **Unique:** one globally unique identifier, one location at a time, every message to that ID delivered to the same place. **Durable:** state persists on disk, private to the object and therefore co-located with it, so the object can safely keep a consistent copy in memory and operate on it with zero latency. Idle objects shut down and are recreated later on demand.

## Two abilities

Storage is fast and transactionally consistent because it belongs to one object: the traditional monolithic database split into many small logical units, with effortless scaling and zero maintenance burden.

Coordination is the newer thing. Requests were once load-balanced at random, so there was no way to force two clients to talk to the same Worker, and no way for them to coordinate through Workers. Now requests related to the same topic go to the same object, which coordinates between them without touching storage: real-time chat, collaborative editing, video conferencing, pub/sub message queues, game sessions. Most of those want WebSockets, so along with the beta we've made Workers able to speak the protocol directly, as client or as server, rather than only proxying it to a back-end.

## Region: Earth

Cloudflare determines which datacenter each object lives in and can transparently migrate it as needed. You design your storage model to match your application's logical data model instead: an object per document, an object per chat, rather than a map of regions. There is no problem creating millions or billions of them, since each has minimal overhead.

## The case that makes it plain

Alice and Bob edit the same spreadsheet. Store the keystrokes in a database and poll for updates, and at best latency is poor, at worst transactions repeatedly fail as users on opposite sides of the world fight over the same content. The secret is a live coordination point. Alice and Bob connect to it, typically over WebSockets; it forwards her keystrokes to him and his to her, resolves conflicts instantly, keeps the document in memory, and writes back to storage asynchronously. Every big-name real-time collaborative editor works this way, and standard serverless infrastructure, and cloud infrastructure more generally, has not made it easy to assign such a point and direct users to it.

Durable Objects make it easy, and Cloudflare will create the coordinator close to the users using it and migrate it as needed. Reaching one is a matter of a name:

```js
// Derive the ID for the counter object named "my-counter".
// This name is associated with exactly one instance in the
// whole world.
let id = COUNTER_NAMESPACE.idFromName("my-counter");

// Send a request to it.
let response = await COUNTER_NAMESPACE.get(id).fetch(request);
```

Our open source chat demo runs entirely at the edge this way, in a few hundred lines: an object per room, users connected by WebSocket, messages relayed directly rather than through storage, history kept in durable storage. A second use is rate limiting, an object per IP tracking recent request frequency. Those objects store no durable state at all, because they only care about very recent history: pure coordination. Each object is single-threaded, so any individual room's scalability has a limit, but that limit is far beyond what a human participant could keep up with.

## What this is not

Durable Objects today are not a complete database solution. Each object can see only its own data, so a query or transaction across several of them takes extra work from the application. Still, every big distributed database is at some low level composed of chunks, and its job is to coordinate between them. We see a future of edge databases that store each chunk as a Durable Object, fully distributed with no home location, built on top by us or by anyone.

CRDTs can be used on top of Durable Objects, but are not required. We feel that for most applications they are overly complex and not worth the effort, and the set of data structures that can be represented as one is too limited for many. Assigning a single authoritative coordination point per document is usually much easier.

As with any beta, some of what I've described here is not fully enabled yet; the limitations are in the documentation. Storing data is a big responsibility, so we are being careful, and will make this available gradually over the next several months.

## Serverless state

Serverless compute succeeded because the event was already the unit developers think in. No one thinks about their business logic in servers or containers or processes. State needs the same alignment, and its logical unit is not a table or a collection or a graph. It's the chat room, the spreadsheet, the shopping cart. Make the physical unit of storage match the logical unit of state, and scalability and regionality become the storage provider's concern rather than the developer's. This is what Durable Objects do.
