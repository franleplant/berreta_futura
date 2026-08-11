---
source_ids:
- durable-objects-easy-fast-correct-choose-three-e5ada0af
content_mode: article
label: ARTICLE
---

A Durable Object is a Worker with a disk: one location, one thread, its own private keys. That ought to make storage simple. It didn't, because every disk operation is an `await`, and an `await` lets another request slip in. Written the obvious way, code handed out the same "unique" number twice. Written carefully, it was slow. So we changed the runtime rather than the advice. Input gates hold back incoming events while storage is in flight. Output gates hold back outgoing messages until writes are confirmed. An in-memory cache makes both nearly free. Your code does not change at all.

## The object that owns its data

In a classical database, many clients touch the same rows, and keeping anything in memory is hopeless. Here, each piece of data belongs to exactly one thread at a time. That is the whole point: you can hold state in memory and synchronise there.

But disk access is I/O, and I/O returns a promise.

```
async function getUniqueNumber() {
  let val = await this.storage.get("counter");
  await this.storage.put("counter", val + 1);
  return val;
}
```

JavaScript has no threads, so this looks safe. It isn't. Each `await` is a door. Two requests arriving together can both read the counter before either writes it, and both leave with the same number. Two readers of one ledger, each certain of being alone.

The bug only appears under load, only sometimes, and never in your tests.

## Why the write is slow

`get()` costs a millisecond or two. `put()` costs tens. The worst thing an application can do is tell a user their action succeeded when it did not, so `await put()` must not return until the data is genuinely safe: written to several disks, on several machines, replicated to more than one Cloudflare location. Disks fail, and data centres lose power. Light travels no faster for our convenience.

## What we chose not to do

A transaction fixes the race. It also adds coordination, retries under exactly the load that caused the conflict, and a callback that may run more than once. Developers who mutate in-memory state inside that callback must make it idempotent, will not think to, and cannot test it. A fix you must remember to apply correctly is a foot-gun.

Caching the counter in memory is fast and, oddly, more correct: calls that return without I/O cannot interleave. But initialisation still races, and an unawaited `put()` can vanish in a power failure, handing out numbers a second time on the new machine.

## Input gates

> While a storage operation is executing, no events are delivered to the object except storage completions. Everything else waits until the object is neither running JavaScript nor awaiting storage.

Concurrent requests now queue behind each other's reads and writes, so the naive function is correct. This covers returning `fetch()` calls too, not just new requests.

One caveat remains. If a single event starts two calls without awaiting the first, they run in parallel, and the system cannot tell that apart from deliberate parallel I/O. That bug is deterministic, and testing will find it.

## Output gates

> While a write is in progress, outgoing network messages are held back. If the write fails, those messages are replaced with errors and the object is restarted from scratch.

So stop awaiting `put()`. Assume it works. If it doesn't, nothing you did afterwards was ever observed: the premature confirmation is never delivered, and by the time the user reads it, it is no longer premature.

## Caching

Several megabytes of an object's data now live in the process that runs it. A cached `get()` returns without leaving the thread. A `put()` writes to cache and completes at once, safe because the output gate holds the door. Writes coalesce, so the gate waits on O(1) round trips, not O(n). And because operations rarely block, input gates cost you little throughput.

Two guarantees come free. Unawaited writes are grouped and stored atomically, so a `delete()` and its following `put()` cannot leave you with neither. And overlapping operations now execute in the order you initiated them, whatever order they finish in.

## When you would rather we didn't

```
this.storage.get("foo", {allowConcurrency: true, noCache: true});
this.storage.put("foo", "bar", {allowUnconfirmed: true, noCache: true});
```

For those who have thought carefully about their access patterns. For everyone else, the defaults are the thinking.
