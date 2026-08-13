---
source_ids:
- durable-objects-easy-fast-correct-choose-three-e5ada0af
content_mode: article
label: ARTICLE
---

A Durable Object runs in one place, in one thread, with its own private disk. That should make state easy. But storage is still I/O, so every call returns a promise, and every `await` is a door through which another request can walk. Code that looked obviously correct handed out duplicate numbers under load; code that was correct was slow, because a confirmed write has to reach several disks in several locations before it can be called safe. Rather than fix the applications, we fixed the model. Last month we rolled out changes to the runtime: input gates defer other events while storage is in flight, output gates hold back outgoing messages until writes are confirmed, and an in-memory cache makes most reads and all writes return immediately. Intuitive code is now correct by default, and fast. No changes to your code are needed.

## The example

```
// Used to be slow and racy -- but not anymore!
async function getUniqueNumber() {
  let val = await this.storage.get("counter");
  await this.storage.put("counter", val + 1);
  return val;
}
```

Two problems. First, a race condition, despite JavaScript having no threads: at each `await`, execution can switch to another request. Two concurrent calls can both `get("counter")` before either one `put`s, and both return the same value. This only happens under simultaneous requests, and then only sometimes, which makes it very hard to test for. Everything seems fine until the day a lot of visitors hit the same object at once.

Second, slowness. Two round trips: the `get()` typically takes a couple milliseconds, the `put()` probably tens. The `put()` is slow because we refuse to report success falsely. Data must be on multiple disks, in multiple machines, and replicated to multiple Cloudflare locations, so a write cannot be confirmed without crossing long distances. The speed of light being what it is, there is little we can do about that.

## The wrong fixes

A transaction removes the race: one concurrent call wins, the others are canceled and retried. But it is slower still, and retries grow more common exactly when load is high. Worse, many developers do not realize the callback can run more than once, so a callback that touches in-memory state must be idempotent. Tests will not catch it. We would have solved the problem with a foot-gun.

Manual in-memory caching is much faster, and, because cached calls return without any I/O, there is no opportunity for concurrency at all, so it is also more correct. Only the platform's guarantee of a single instance makes that possible. But initialization is still racy: the first two concurrent calls can both initialize, and getting that right is surprisingly tricky. And an unawaited `put()` can be silently lost, so after a power failure the new instance may hand out numbers already given away.

## Input gates

While a storage operation is executing, no events are delivered to the object except storage completions. Other events wait for the input gate to open, which happens once the object is neither running JavaScript nor waiting on storage.

Now the second request is simply held until the first is done, and the numbers are unique. You may still issue several storage operations concurrently on purpose; the rule only prevents unrelated events, including the returns of concurrent `fetch()` calls, from arriving in the gaps.

One catch remains. If the same event starts two calls without awaiting the first, they run concurrently and interfere, because there is no incoming event to defer and no way to distinguish this from deliberate parallelism. That bug is deterministic and easy to catch in testing, which we consider an acceptable caveat.

## Output gates

When a write is in progress, new outgoing network messages are held back until it completes. If the write ultimately fails, the messages are discarded and replaced with errors, and the object is shut down and restarted from scratch.

So you need not `await` a `put()`. Assume it will succeed: if it does not, nothing the application did can be observed by the outside world. A response sent prematurely is not delivered until the write lands, so by the time the user receives it, it is no longer premature. This applies to outgoing `fetch()` requests too.

## Automatic caching

The classic answer, borrowed from operating systems. Our new layer keeps up to several megabytes per object directly in memory in the process where the object runs. A cached `get()` returns without even leaving the thread and isolate. A `put()` now always completes instantaneously by writing to cache, with the output gate holding external observers back; writes are coalesced, so the gate waits O(1) network round trips, not O(n). Because operations complete instantly in most cases, the throughput cost of input gates is largely mitigated: the gate spends little time blocked.

Coalescing also buys atomicity. Successive `put()` and `delete()` calls with no `await` between them are stored as one group, so a power failure leaves you either all of them or none. Ordering is stronger too: operations now take effect in the order they were initiated, regardless of when they complete, where overlapping operations on the same key previously had no guaranteed order.

## Bypass

Sometimes concurrency is harmless, premature confirmation is acceptable, or caching only wastes memory. So the flags are explicit:

```
this.storage.get("foo", {allowConcurrency: true, noCache: true});
this.storage.put("foo", "bar", {allowUnconfirmed: true, noCache: true});
```

For those who would rather not think about it, the defaults should work well.

## Why it matters

The traditional answer to concurrency is to make applications stateless and push all control into database transactions, which is a big reason so many web applications take hundreds of milliseconds to respond to basic actions. Durable Objects are all about state: keeping it in memory as well as on disk, and routing requests for the same data through the same instance, makes applications much faster. Until recently that was extremely tricky to get right. With the gates and the cache, the most intuitive code works and runs fast.
