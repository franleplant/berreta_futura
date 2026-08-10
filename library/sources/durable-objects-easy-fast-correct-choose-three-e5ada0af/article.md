# Durable Objects: Easy, Fast, Correct — Choose three

By Kenton Varda · The Cloudflare Blog · August 3, 2021

![](media/001.png)

Storage in distributed systems is surprisingly hard to get right. Distributed databases and consensus are well-known to be extremely hard to build. But, application code isn't necessarily easy either. There are many ways in which apps that use databases can have subtle timing bugs that could result in inconsistent results, or even data loss. Worse, these problems can be very hard to test for, as they'll often manifest only under heavy load, or only after a sudden machine failure.

Up until recently, Durable Objects were no exception. A Durable Object is a special kind of Cloudflare Worker that has access to persistent storage and processes requests in one of Cloudflare’s points of presence. Each Object has its own private storage, accessible through a classical key/value storage API. Like any classical database API, this storage API had to be used carefully to avoid possible race conditions and data loss, especially when performance mattered. And like any classical database API, many apps got it wrong.

However, rather than fix the apps, we decided to fix the model. Last month, we rolled out deep changes to the Durable Objects runtime such that many applications which previously contained subtle race conditions are now correct by default, and many that were previously slow are now fast. Developers can now write their code in an intuitive way, and have it work. No changes at all are needed to your code in order to take advantage of these new features.

So, let me tell you about what changed…

## Background: Durable Objects are Single-Threaded

To understand what changed, it's necessary to first understand Durable Objects. For a full introduction, see the [Durable Objects announcement blog post](https://blog.cloudflare.com/introducing-workers-durable-objects/).

The most important point is: Each Durable Object runs in exactly one location, in one single thread, at a time. Each object has its own private on-disk storage. This is a very different situation from a typical database, where many clients may be accessing the same data. In Durable Objects, any particular piece of data belongs to exactly one thread at a time.

Because a single Durable Object is single-threaded, it's possible, and even encouraged, to keep state and perform synchronization in memory. This is, indeed, the killer feature of Durable Objects. With classical databases, in-memory state is extremely difficult to keep synchronized between all database clients. But with Durable Objects, since each piece of data belongs to a specific thread, this synchronization is easy.

However, interacting with the disk is still an I/O (input/output) operation, which means that each operation returns a `Promise` which you must `await`. As we'll see, this re-introduces some of the synchronization difficulties that we were trying to avoid. However, it turns out, we can solve these difficulties within the system itself, without bothering application developers.

## An Example

Consider this code:

```
// Used to be slow and racy -- but not anymore!
async function getUniqueNumber() {
  let val = await this.storage.get("counter");
  await this.storage.put("counter", val + 1);
  return val;
}
```

At first glance, this seems like reasonable code that returns a unique number each time it is called (incrementing each time).

Unfortunately, before now, this code had two problems:

1. It had a subtle race condition (even though Durable Objects are single-threaded!).
2. It was kind of slow.

### The Race Condition

A race condition occurs when two operations running concurrently might interfere with each other in a way that makes them behave incorrectly. Race conditions are commonly associated with code that uses multiple threads.

JavaScript, however, famously does not use threads. Instead, it uses event-driven programming, with callbacks. It's not possible for two pieces of JavaScript code to be running "at the same time" in the same isolate (and Durable Objects promises that no other isolate could possibly be accessing the same storage). Does that mean that race conditions aren't a problem in JavaScript, the way they are in multi-threaded apps?

Unfortunately, it does not. The problem is, the code above is an `async` function, containing two `await` statements. Each time `await` is used, execution pauses, waiting for the specified `Promise` to complete.

In the meantime, though, other code can run! For example, the Durable Object might receive two requests at the same time. If each of them calls `getUniqueNumber()`, then the two calls might be interleaved. Each time one call performs an `await`, execution may switch to the other call. So, the two calls might end up looking like this:

| Request 1 timeline | Request 2 timeline |
| --- | --- |
| `async function getUniqueNumber() { let val = await this.storage.get("counter");` |   |
|   | `async function getUniqueNumber() { let val = await this.storage.get("counter");` |
| `await this.storage.put("counter", val + 1);` |   |
|   | `await this.storage.put("counter", val + 1);` |
| `return val; }` |   |
|   | `return val; }` |

There's a big problem here: Both of these two calls will call `get("counter")` before *either* of them calls `put("counter", val + 1)`. That means, both of them will return the same value!

This problem is especially bad because it only happens when multiple requests are being handled at the same time -- and even then, only sometimes. It is very hard to test for this kind of problem, and everything might seem just fine when the application is deployed, as long as it isn't getting too much traffic. But one day, when a lot of visitors try to use the same object at the same time, all of a sudden `getUniqueNumber()` starts returning duplicates!

### The Slowness

To add insult to injury, `getUniqueNumber()` was (until recently) pretty slow. The problem is, it has to do two round trips to storage -- a `get()` and a `put()`. The `get()` might typically take a couple milliseconds. The `put()`, however, will take much longer, probably tens of milliseconds.

Why is `put()` so slow? Because we don't want to lose data. The worst thing an application can do is tell the user that their action was successful when it wasn't. If, for some reason, a write cannot be completed, then it's imperative that the application presents an error to the user, so that the user knows that something is wrong and they'll have to try again or look for a fix.

In order to make sure an application does not prematurely report success to the user, `await put()` has to make sure it doesn't return until the data is actually safe on disk. Disks are slow, so this might take a while.

But that's not all. Disks can fail. In order for the data to be really safe, we have to write the same data on multiple disks, in multiple machines. That means we have to wait for some network traffic.

But that's still not all. What if a meteor were to come out of the sky and land on a Cloudflare data center, completely destroying it? Or, more likely, what if the power or network connection failed? We don't want a user's data to be lost in this case, or even temporarily become unavailable. Therefore, Durable Object data is replicated to multiple Cloudflare locations. This requires communicating across long distances before any write can be confirmed. There is little we can do to make this faster, the speed of light being what it is.

A call to `getUniqueNumber()` will therefore always take tens of milliseconds. If an application calls it multiple times, `await`ing each call before beginning the next, it can easily become very slow very quickly. Or, at least, that was the case before our recent changes.

## The Wrong Fixes

There are several ways that an application could fix these problems, but all of them have their own issues.

### Transactions?

Many databases offer "transactions". A transaction allows an application to make sure some operation completes "atomically", with no interference from concurrent operations.

The Durable Objects storage API has always supported transactions. We could use them to fix our `getUniqueNumber()` implementation like so:

```
// No more race condition... but slow and complicated.
async function getUniqueNumber() {
  let val;
  await this.storage.transaction(async (txn) => {
    val = await txn.get("counter");
    await txn.put("counter", val + 1);
  });
  return val;
}
```

This fixes our race condition. Now, if `getUniqueNumber()` is called multiple times concurrently such that the storage operations interleave, the system will detect the problem. One of the concurrent calls will be chosen to be the "winner", and will complete normally. The other calls will be canceled and retried, so that they can see the value written by the first call.

This fixes our problems! But, at some cost:

- `getUniqueNumber()` is now even slower than it was before. The difference typically won't be huge, but setting up a transaction does require some additional coordination in the database. Of course, if the transaction needs to be retried, then it may end up being much slower. And retries will tend to happen more when load gets high… the worst possible time.
- Speaking of retries, many developers might not realize that the transaction callback can be called multiple times. It's difficult to test for this, since retries will only happen when concurrent operations cause conflicts. The problem is especially acute when the application is trying to synchronize not just on-disk state, but also in-memory state -- if the transaction callback modifies in-memory state, it must be careful to ensure that its changes are idempotent. The need for idempotency may not be top of mind for most developers, and tests won't catch the problem, making it very easy to end up deploying buggy code.

So we solved our problem, but we did it with a foot-gun. If we keep using the foot-gun, we're probably going to shoot our own feet eventually.

Is there another way?

### In-memory caching?

Durable Objects' superpower is their in-memory state. Each object has only one active instance at any particular time. All requests sent to that object are handled by that same instance. That means, you can store some state in memory.

```
// Much faster! But (used to be) wrong.
async function getUniqueNumber() {
  if (this.val === undefined) {
    this.val = await this.storage.get("counter");
  }

  let result = this.val;
  ++this.val;
  this.storage.put("counter", this.val);
  return result;
}
```

This code is MUCH faster than the previous implementation, because it stores the value in memory. In fact, after the function runs once, further calls won't wait for any I/O at all -- they will return immediately. This is because by caching the value in memory, we avoid waiting for a `get()` (except for the first time), and we don't wait for the `put()` either, trusting that it will complete asynchronously later on.

Returning immediately also means that there's no opportunity for concurrency, so the calls that return immediately will always return unique numbers! This means that not only is this implementation faster than our original implementation, it is also *more correct*. This is only possible because the Durable Objects platform guarantees that there will only be one instance, and therefore only one copy of `this.val`.

Unfortunately, there are two problems with this code:

- We still have a race condition on initialization. If the *first* two calls to `getUniqueNumber()` happen to occur at about the same time, then initialization will be performed multiple times. The second call will likely clobber what the first call did, and the two calls will end up returning the same number. We could solve this problem by making initialization more complicated -- the first call could create an initialization promise, and other concurrent calls could wait on it, so that initialization really only happens once. But this creates even deeper complexity: What if initialization fails for some reason? The object could be placed in a permanently broken state. It's possible to get this right, but it's surprisingly tricky.
- Because we don't wait for the `put()` to report success, it's possible that it could be silently lost. For example, if the machine hosting the Durable Object suffered a sudden power failure, then the Durable Object would be transferred to some other machine. When it starts up there, calls to `getUniqueNumber()` might return numbers that had already been returned under the old instance before it failed, because the `put()`s hadn't actually completed before the failure occurred. But if we `await` the `put()`, then our function becomes slow again, and creates more opportunities for race conditions (e.g. in the calling code).

## Our answer: Make it automatic

When looking at this, we had two options:

1. Try to carefully document these problems and educate developers about them, so that they could write code that does the right thing.
2. Change the system so that naturally-written code just does the right thing by default -- and runs quickly.

We chose option 2. We accomplished this in three parts.

### Part 1: Input Gates

Let's go back to our original example. Can we make this example "just work", even in the face of concurrent requests?

```
// Can this "just work" please?
async function getUniqueNumber() {
  let val = await this.storage.get("counter");
  await this.storage.put("counter", val + 1);
  return val;
}
```

It turns out we can! We create a new rule:

> **Input gates:** While a storage operation is executing, no events shall be delivered to the object except for storage completion events. Any other events will be deferred until such a time as the object is no longer executing JavaScript code *and* is no longer waiting for any storage operations. We say that these events are waiting for the "input gate" to open.

If we do this, then our storage operations above are no longer an opportunity for concurrency. Our concurrent requests now look like this:

| Request 1 timeline | Request 2 timeline |
| --- | --- |
| `async function getUniqueNumber() { let val = await this.storage.get("counter");` |   |
|   | `// Request 2 delivery is blocked because // request 1 is waiting for storage.` |
| `await this.storage.put("counter", val + 1);` |   |
|   | `// Request 2 delivery is blocked because // request 1 is waiting for storage.` |
| `return val; }` |   |
|   | `async function getUniqueNumber() { let val = await this.storage.get("counter"); await this.storage.put("counter", val + 1); return val; }` |

The two calls return unique numbers, as expected. Hooray! (Unfortunately, we did it by delaying the second request, creating latency and reducing throughput -- but we'll address that in part 3, below.)

Note that our rule does not preclude making multiple concurrent requests to storage at the same time. You can still say:

```
let promise1 = this.storage.get("foo");
let promise2 = this.storage.put("bar", 123);
await promise1;
frob();
await promise2;
```

Here, the `get()` and `put()` execute concurrently. Moreover, the call to `frob()` may execute before the `put()` has completed (but strictly after the `get()` completes, since we `await`ed that promise). However, no *other* event -- such as receiving a new request -- can unexpectedly happen in the meantime.

On the other hand, the rule protects you not just against concurrent incoming requests, but also concurrent responses to outgoing requests. For example, say you have:

```
async function task1() {
  await fetch("https://example.com/api1");
  return await this.getUniqueNumber();
}
async function task2() {
  await fetch("https://example.com/api2");
  return await this.getUniqueNumber();
}
let promise1 = task1();
let promise2 = task2();
let val1 = await promise1;
let val2 = await promise2;
```

This code launches two `fetch()` calls concurrently. After each fetch completes, getUniqueNumber() is invoked. Could the two calls interfere with each other?

No, they will not. The completion of a `fetch()` is itself a kind of event. Our rule states that such events cannot be delivered while storage events are in progress. When the first of the two fetches returns, the app calls `getUniqueNumber()`, which starts performing some storage operations. If the second `fetch()` also returns while these storage operations are still outstanding, that return will be deferred until after the storage operations are done. Once again, our code ends up correct!

At this point, the async programming experts in the audience are probably starting to feel like something is fishy here. Indeed, there is a catch. What if we do:

```
// Still a problem even with input gates.
let promise1 = getUniqueNumber();
let promise2 = getUniqueNumber();
let val1 = await promise1;
let val2 = await promise2;
```

In this case, there is, in fact, a problem. Two calls to `getUniqueNumber()` are initiated *by the same event*. The application does not `await` the first call before starting the second, so the two calls end up running concurrently. Our special rule doesn't protect us here, because there is no incoming event that can be deferred between when the two calls are made. From the system's point of view, there's no way to distinguish this code from code which legitimately decided to perform two storage operations in parallel.

As such, in this case, the two calls to `getUniqueNumber()` will interfere with each other. However, this problem is far less likely to come about by accident, and is far easier to catch in testing. This bug is *deterministic*, not caused by the unpredictable timing of network events. We consider this an acceptable caveat in order to solve the larger problem posed by concurrent requests.

### Part 2: Output Gates

Let's go back to our in-memory caching example. Can we make it work?

```
// Can we make this "just work"?
async function getUniqueNumber() {
  if (this.val === undefined) {
    this.val = await this.storage.get("counter");
  }

  let result = this.val;
  ++this.val;
  this.storage.put("counter", this.val);
  return result;
}
```

With input gates (part 1), we've solved one of the two problems this code had: the race condition of initialization. We no longer need to worry that two requests will call this at the same time, leading `this.val` to be initialized twice.

However, the problem with not `await`ing the `put()` is still there. If we don't `await` it, then we could lose data. If we do `await` it, then the call is slow.

We make another new rule:

> **Output gates:** When a storage write operation is in progress, any new outgoing network messages will be held back until the write has completed. We say that these messages are waiting for the "output gate" to open. If the write ultimately fails, the outgoing network messages will be discarded and replaced with errors, while the Durable Object will be shut down and restarted from scratch.

With this rule, we no longer have to `await` the result of `put()`. Our code can happily continue executing and just *assume* the put() will succeed. If the `put()` doesn't succeed, then anything the application does here will never be observable to the rest of the world anyway. For example, if the app prematurely sends a response to the user saying that the operation succeeded, this response will not actually be delivered until after the `put()` completes successfully. So, by the time the user *receives* the message, it is no longer "premature"! In the very rare event that the write operation fails, the user will not receive the premature confirmation at all.

Note that output gates apply not only to responses sent back to a client, but also to new outgoing requests made with `fetch()` -- those requests will be delayed from being sent until all prior writes are confirmed. So, once again, it is impossible for anything else in the world to observe a premature confirmation.

With this change, our `getUniqueNumber()` implementation with in-memory caching is now fully correct, while retaining most of its speed advantage over the non-caching implementation. Except for the very first call, the application will never be blocked waiting for `getUniqueNumber()` to finish. The final response from the app to the client will be delayed pending write confirmation, but that write can be performed in parallel with any writes the application performs after `getUniqueNumber()` completes.

### Part 3: Automatic in-memory caching

Our in-memory caching example now works great. But, it's still a little bit complicated and unnatural to write. Let's go back to our original, simple code one more time… can we make it fast by default?

```
// Can we make this not just work, but just work FAST?
async function getUniqueNumber() {
  let val = await this.storage.get("counter");
  await this.storage.put("counter", val + 1);
  return val;
}
```

The answer to this part is a classic one: we can add automatic caching to the storage layer, just like most operating systems do for disk storage.

We have rolled out an in-memory caching layer for Durable Objects. This layer keeps up to several megabytes worth of data directly in memory in the process where the object runs.

When a `get()` requests a key that is in cache, the operation returns immediately, without even context-switching out of the thread and isolate where the object is hosted. If the key is not in cache, then a storage request will still be needed, but reads complete relatively quickly.

Better yet, `put()` requests now always complete "instantaneously". A `put()` simply writes to cache. We rely on output gates ("part 2", above) to prevent the premature confirmation of writes to any external party. Writes will be coalesced (even if you `await` them), so that the output gate waits only for O(1) network round trips of latency, not O(n).

Moreover, because `get()` and `put()` now complete instantly in most or all cases, the negative impact of input gates on throughput is largely mitigated, because the gate now spends relatively little time blocked.

With Durable Objects built-in caching, our simple code is now *just as fast* as our code that manually implemented in-memory caching. Combined with input and output gates, our code is now simple, fast, *and* correct, all at the same time.

#### Bonus Correctness

Our caching layer provides some bonus consistency guarantees, in addition to performance.

First, writes are automatically coalesced. That is, if you perform multiple `put()` or `delete()` operations without `await`ing them or anything else in between, then the operations are automatically grouped together and stored atomically. In the case of a sudden power failure, after coming back up, either all of the writes will have been stored, or none of them will. For example:

```
// Move a value from "foo" to "bar".
let val = await this.storage.get("foo");

this.storage.delete("foo");
this.storage.put("bar", val);
// There's no possibility of data loss, because the delete() and the
// following put() are automatically coalesced into one atomic
// operation. This is true as long as you do not `await` anything
// in between.
```

Second, the API is also able to provide stronger ordering guarantees for reads. Previously, overlapping storage operations did not have guaranteed ordering. For example, if you issued a `get()` and a `put()` on the same key at the same time (without `await`ing one before starting the other), then it was not deterministic whether the `get()` might return the value written by the `put()` -- regardless of the ordering of the statements in your code. The caching layer fixes this. Now, operations are performed in exactly the order in which they were initiated, regardless of when they complete.

These two features eliminate more subtle bugs that might otherwise be hard to catch in testing, so that you don't have to be a database expert to write code that works.

### Optional Bypass

We expect gates and caching will be a win in the vast majority of use cases, but not always. In some use cases, concurrency won't lead to any problems, and so blocking it may be a loss. Sometimes, the application is OK with prematurely confirming writes in order to minimize latency. And sometimes, caching may just waste memory because the same keys are not frequently accessed.

For those cases, we offer explicit bypasses:

```
this.storage.get("foo", {allowConcurrency: true, noCache: true});
this.storage.put("foo", "bar", {allowUnconfirmed: true, noCache: true});
```

Developers who have taken the time to think carefully about these issues can use these flags to tune performance to their specific needs. For those who don't want to think about it, the defaults should work well.

## Conclusion

Concurrency is hard. It doesn't matter if you're a novice or an expert: even experts regularly get it wrong. It's difficult to think about all the ways that concurrent operations might overlap to corrupt your application state.

The traditional answer has been to make applications stateless, and defer all concurrency control to the database layer using transactions. However, transactions are slow, which is a big reason why so many web applications today take hundreds of milliseconds or more to respond to basic actions.

Durable Objects are all about state. By keeping state in memory in addition to on disk, and directing requests for the same data to be coordinated through the same instance, we can make applications much faster. But until recently, this was extremely tricky to get right.

With input gates, output gates, and caching, code written in the most intuitive way now "just works", and runs fast. This means you can focus on building your application, without wasting time optimizing I/O performance and debugging obscure race conditions.
