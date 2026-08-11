---
source_ids:
- workers-durable-objects-beta-a-new-approach-to-s-1a040568
content_mode: article
label: ARTICLE
---

**Thirty seconds:** We launched Workers in 2017 on the bet that code at the edge could be cheaper and simpler than code in a datacenter. Isolates killed the cold start. Workers KV gave us storage, but eventually consistent storage, which is the wrong tool when a value changes often and the change must be seen everywhere at once. What remained impossible on the edge was strong consistency and live coordination between clients. Durable Objects supply both. Each object is an instance of a class you write, with a globally unique ID, a private slab of disk beside it, and exactly one location in the world at any moment. Messages addressed to that ID all land in the same place. That is the whole idea.

## What the three words mean

**Object:** a class in JavaScript, or your language of choice. Methods are the public interface. An instance binds the code to private state.

**Unique:** one identifier, one location, worldwide. Any Worker anywhere that knows the ID can reach it, and every message arrives at the same instance.

**Durable:** state survives on disk, private to the object and therefore local to it. Because the copy in memory is authoritative, the object operates on it at zero latency. Idle objects shut down and are recreated on demand.

## The two abilities

Storage co-located with the object, so it is fast and transactional. We split the monolithic database into many small logical units, and get the ordinary serverless dividend: scaling without maintenance.

Coordination. Requests used to be load-balanced at random, so no two clients could be made to meet. Now requests on one topic route to one object, which can mediate between them without touching disk at all. Chat, collaborative editing, video conferencing, pub/sub, game sessions.

Coordination wants WebSockets, so Workers now speak the protocol directly, as client or server. Previously a Worker could only proxy a socket onward; there was no way to address the particular Worker holding a connection. Forward the socket to an object and the address problem dissolves.

## Forget regions

Cloudflare picks the datacenter and migrates the object as usage moves. You design storage to match your data model, not a map: an object per document, an object per chat. Millions or billions of objects are unremarkable, since the overhead of each is small.

## Collaborative editing, the killer case

Alice and Bob edit one spreadsheet. Route their keystrokes through a database and poll for updates, and the best case is poor latency; the worst is transactions failing repeatedly as two people on opposite sides of the world contend for the same cell.

The trick, and every serious editor uses it, is a live coordination point. Both connect to it over WebSockets. It relays keystrokes, resolves conflicts instantly, and writes back to storage asynchronously, because the authoritative document already sits in its memory. What has been out of reach for serverless developers is the assignment of such a point and the herding of users toward it. That is now a line of code, with placement and migration handled for you. You may keep the document entirely on the edge and drop the database.

## An atomic counter

```js
export class Counter {
  // Constructor called by the system when the object is needed to
  // handle requests.
  constructor(controller, env) {
    // `controller.storage` is an interface to access the object's
    // on-disk durable storage.
    this.storage = controller.storage
  }

  // Private helper method called from fetch(), below.
  async initialize() {
    let stored = await this.storage.get("value");
    this.value = stored || 0;
  }

  // Handle HTTP requests from clients.
  //
  // The system calls this method when an HTTP request is sent to
  // the object. Note that these requests strictly come from other
  // parts of your Worker, not from the public internet.
  async fetch(request) {
    // Make sure we're fully initialized from storage.
    if (!this.initializePromise) {
      this.initializePromise = this.initialize();
    }
    await this.initializePromise;

    // Apply requested action.
    let url = new URL(request.url);
    switch (url.pathname) {
      case "/increment":
        ++this.value;
        await this.storage.put("value", this.value);
        break;
      case "/decrement":
        --this.value;
        await this.storage.put("value", this.value);
        break;
      case "/":
        // Just serve the current value. No storage calls needed!
        break;
      default:
        return new Response("Not found", {status: 404});
    }

    // Return current value.
    return new Response(this.value);
  }
}
```

Simultaneous requests lose no increments. Reads never touch disk. Reaching it from anywhere:

```js
// Derive the ID for the counter object named "my-counter".
// This name is associated with exactly one instance in the
// whole world.
let id = COUNTER_NAMESPACE.idFromName("my-counter");

// Send a request to it.
let response = await COUNTER_NAMESPACE.get(id).fetch(request);
```

## The chat demo

One object per room, users on WebSockets, messages relayed between them without passing through storage. History is stored, but only as history.

A second use hides inside it. Each IP gets an object that tracks request frequency, so a flooder is blocked across every room at once. These rate limiters store nothing at all: they care only about the recent past, and no harm follows if one resets. Pure coordination, no disk.

A few hundred lines, a few lines of configuration, and it scales to any number of rooms. A single room does not scale without limit, since an object is single-threaded, but that ceiling sits far above what any human can read.

## Other uses

A shopping cart in an object, the storefront otherwise static. A match in a multiplayer game, hosted near its players. Devices in one house coordinating locally instead of through a distant server. A feed aggregating one user's subscriptions. A comment or live chat widget per article, leaving the origin to serve static content.

## Toward edge databases

An object sees only its own data. Queries and transactions across objects are work you must do yourself, so this is not yet a database.

But every large distributed database, relational or document or graph, is underneath a set of chunks, and its real job is coordinating them. Store each chunk as a Durable Object and you get a database with no regions and no home. We need not be the ones who build it. This is the first step in the edge storage journey, not the last.

## The beta

Storing data is a responsibility we do not take lightly, so we are moving gradually over the coming months. Parts of what is described here are not yet enabled; the documentation lists the limits. Tell us your use case and we will select the most interesting for early access.

## On CRDTs

They allow simultaneous edits from many places without synchronization or loss, resolved deterministically, like a fork and merge where every conflict settles itself the same way for everyone. Anyone who has used git can see the difficulty: automatic conflict resolution is hard, it will sometimes be wrong, and it must give the same answer whatever order the merges arrive in. Only certain data structures submit to the treatment.

For most applications the complexity is not worth it, and the set of representable structures is too narrow. A single authoritative coordination point is easier, and it is precisely what an object is. You may still put CRDTs on top: replicate an object into several serving different regions and let them synchronize. Do that as an optimization, once you know it pays.

## What "serverless" means for state

Serverless compute succeeded by reducing the unit of work to an event, because an event is what we actually think in. Nobody reasons about their business logic in servers or containers or processes. That alignment is why the logistical burden could shift to the provider.

State never made the same move. Each event ran alone; storage and coordination meant reaching out to services that quietly restored the operational worries serverless was meant to abolish, scaling among them, and regionality worst of all.

So split state as finely as compute, along the same seam. The logical unit of state is not a table or a collection or a graph. It is a chat room, a spreadsheet, a shopping cart. Make the physical unit of storage match the logical unit the application already contains, and scalability and geography become someone else's problem. Ours.
