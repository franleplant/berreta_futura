---
source_ids:
- durable-objects-easy-fast-correct-choose-three-e5ada0af
content_mode: article
label: ARTICLE
---

Durable Objects store data, and code that stores data is easy to get subtly wrong. Each object runs in one place, on one thread, but every storage call is an `await`, and while it waits, other code can run. That reopens race conditions, and waiting for safe writes made such code slow. Rather than fix the apps, we decided to fix the model. Last month we rolled out three changes. Input gates hold back new events while storage operations are in flight. Output gates hold back outgoing messages until writes are confirmed. An in-memory cache makes most reads and all writes complete instantly. Many applications that contained subtle race conditions are now correct by default, and many that were slow are now fast. No changes at all are needed to your code.

## The problem

Each Durable Object runs in exactly one location, in one thread, at a time, with its own private storage. Any piece of data belongs to one thread, so keeping state in memory is easy. That is the killer feature. But disk access is I/O, and each operation returns a `Promise` you must `await`.

Consider:

```
// Used to be slow and racy -- but not anymore!
async function getUniqueNumber() {
  let val = await this.storage.get("counter");
  await this.storage.put("counter", val + 1);
  return val;
}
```

Two concurrent requests can interleave at each `await`. Both call `get("counter")` before either calls `put()`, and both return the same number. This happens only when requests overlap, and even then only sometimes, so it is very hard to test for.

It was also slow. A `get()` might typically take a couple milliseconds. A `put()` probably took tens of milliseconds, because `await put()` must not return until the data is safe on multiple disks, in multiple machines, in multiple Cloudflare locations. There is little we can do to make this faster, the speed of light being what it is.

## The wrong fixes

Transactions fix the race but make the function slower, and retries tend to happen when load gets high, the worst possible time. Many developers might not realize the transaction callback can be called multiple times, so any in-memory state it touches must change idempotently. Tests won't catch this. We solved our problem, but we did it with a foot-gun.

Caching the counter in memory, without awaiting the `put()`, is much faster. But initialization still races, and an unawaited `put()` could be silently lost in a power failure, letting the restarted object return numbers it had already returned.

We could document these problems and educate developers, or change the system so that naturally written code does the right thing by default, and runs quickly. We chose the second.

## Input gates

While a storage operation is executing, no events are delivered to the object except storage completions. Other events wait until the object is neither running JavaScript nor waiting on storage.

The second request now waits, and the two calls return unique numbers. The rule also covers responses to outgoing `fetch()` calls. You can still issue several storage operations concurrently yourself.

There is a catch. If one event starts two `getUniqueNumber()` calls without awaiting the first, they still interfere, since the system can't tell this from code that legitimately runs storage operations in parallel. But this bug is deterministic, far less likely to happen by accident, and far easier to catch in testing. We consider it an acceptable caveat.

Gating delays the second request, which costs latency and throughput. Caching addresses that, below.

## Output gates

While a write is in progress, new outgoing network messages, responses and `fetch()` requests alike, are held until it completes. If the write fails, those messages are discarded and replaced with errors, and the object is restarted from scratch.

So you no longer have to await `put()`. A response saying the operation succeeded is not delivered until the write succeeds, so by the time the user receives it, it is no longer premature. With both gates, the in-memory caching version is fully correct and keeps most of its speed.

## Automatic caching

Finally, we added a cache to the storage layer, as most operating systems do for disk storage. It keeps up to several megabytes in the process where the object runs. A cached `get()` returns immediately; an uncached one still needs a storage request, but reads complete relatively quickly. A `put()` now always completes "instantaneously" by writing to cache, with output gates preventing premature confirmation. Writes are coalesced, so the output gate waits only for O(1) network round trips, not O(n). Because storage now rarely blocks, input gates cost little throughput.

The original, simple code is now just as fast as the hand-cached version.

The cache adds two guarantees. Multiple `put()` or `delete()` calls with nothing awaited between them are stored atomically: after a power failure, either all of them survive or none do. And operations now run in exactly the order they were initiated, regardless of when they complete. Previously, a concurrent `get()` and `put()` on the same key had no guaranteed ordering.

Where gates or caching don't pay off, there are bypasses:

```
this.storage.get("foo", {allowConcurrency: true, noCache: true});
this.storage.put("foo", "bar", {allowUnconfirmed: true, noCache: true});
```

For those who don't want to think about it, the defaults should work well.

## Conclusion

Concurrency is hard, and even experts regularly get it wrong. The traditional answer, stateless applications with transactions in the database, is slow, a big reason so many web applications take hundreds of milliseconds or more to respond to basic actions. Durable Objects keep state in memory and route requests for the same data through one instance. With input gates, output gates, and caching, code written in the most intuitive way now "just works", and runs fast.
