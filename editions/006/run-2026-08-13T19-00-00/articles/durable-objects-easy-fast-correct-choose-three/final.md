---
source_ids:
- durable-objects-easy-fast-correct-choose-three-e5ada0af
content_mode: article
label: ARTICLE
---

A Durable Object is a Worker with its own private storage, running in one location, in one thread, at a time. But storage is still I/O, so every `get()` and `put()` returns a `Promise` you have to `await`, and every `await` is a gap where other code can run. Naturally written code was therefore both racy and slow. Rather than fix the apps, we decided to fix the model: input gates defer other events while storage is in flight, output gates hold outgoing messages back until writes are confirmed, and an in-memory cache makes most reads and all writes return immediately. No changes at all are needed to your code.

## The example that was wrong twice

```
// Used to be slow and racy -- but not anymore!
async function getUniqueNumber() {
  let val = await this.storage.get("counter");
  await this.storage.put("counter", val + 1);
  return val;
}
```

JavaScript famously does not use threads, so it's tempting to think race conditions can't apply. They do. If the object receives two requests at once, each `await` lets execution switch to the other call, and both calls run `get("counter")` before either runs `put("counter", val + 1)`. Both return the same value. Everything seems fine on deployment, as long as the object isn't getting too much traffic.

It was also slow: two round trips, and the `put()` takes tens of milliseconds. That's deliberate. The worst thing an application can do is tell the user their action succeeded when it wasn't, so `await put()` doesn't return until the data is safe on disk, on multiple disks in multiple machines, replicated to multiple Cloudflare locations. There is little we can do to make this faster, the speed of light being what it is.

## The wrong fixes

Transactions fix the race. One concurrent call is chosen as the winner; the others are canceled and retried. But setting one up costs additional coordination, retries make it slower still, and retries happen more when load gets high, the worst possible time. Worse, many developers don't realize the transaction callback can be called multiple times: if it touches in-memory state, that state must be idempotent, and tests won't catch the omission. We solved our problem with a foot-gun.

Caching the counter in memory is much faster, and in a sense more correct, since calls that return immediately offer no opportunity for concurrency. Two problems remain. Initialization still races, and getting that right is surprisingly tricky. And a `put()` nobody awaits can be silently lost, so after a sudden power failure the object may hand out numbers it already gave away.

## Input gates

> **Input gates:** While a storage operation is executing, no events shall be delivered to the object except for storage completion events. Any other events will be deferred until such a time as the object is no longer executing JavaScript code *and* is no longer waiting for any storage operations. We say that these events are waiting for the "input gate" to open.

The second request is now delivered after the first is done, and the two calls return unique numbers. The rule doesn't stop you from issuing several storage operations concurrently yourself, and it covers `fetch()` completions too, since those are events like any other.

There is a catch. If the same event starts two calls to `getUniqueNumber()` without awaiting the first, they still interfere; from the system's point of view that's indistinguishable from code legitimately working in parallel. But the bug is deterministic rather than a matter of network timing, so it's far easier to catch in testing. We consider that acceptable.

## Output gates

> **Output gates:** When a storage write operation is in progress, any new outgoing network messages will be held back until the write has completed. We say that these messages are waiting for the "output gate" to open. If the write ultimately fails, the outgoing network messages will be discarded and replaced with errors, while the Durable Object will be shut down and restarted from scratch.

Now you can stop awaiting `put()` and assume it will succeed. If it doesn't, nothing the application did in the meantime was ever observable. A premature confirmation isn't delivered until the write lands, so by the time the user receives it, it isn't premature. The rule covers outgoing `fetch()` calls as well as responses.

## Caching, by default

We've rolled out an in-memory caching layer holding up to several megabytes of data in the process where the object runs. A cache hit returns without even context-switching out of the thread and isolate. A `put()` now completes instantaneously by writing to cache, and writes are coalesced, so the output gate waits for O(1) network round trips of latency, not O(n). Because operations rarely block now, the throughput cost of input gates is largely mitigated.

Coalescing brings its own guarantee: writes grouped together are stored atomically, so a power failure leaves you either all of them or none, as long as you don't `await` anything in between. Reads are ordered too. Overlapping operations now run in exactly the order they were initiated, regardless of when they complete.

Where any of this is a loss, there are explicit bypasses:

```
this.storage.get("foo", {allowConcurrency: true, noCache: true});
this.storage.put("foo", "bar", {allowUnconfirmed: true, noCache: true});
```

For those who don't want to think about it, the defaults should work well.

## Why it matters

Concurrency is hard, and even experts regularly get it wrong. The traditional answer has been to make applications stateless and push concurrency control down into database transactions, and transactions are slow, which is a big reason so many web applications take hundreds of milliseconds to respond to basic actions. Durable Objects are all about state instead: in memory as well as on disk, with requests for the same data coordinated through the same instance. With gates and caching, the intuitive version of the code is the correct and fast one.
