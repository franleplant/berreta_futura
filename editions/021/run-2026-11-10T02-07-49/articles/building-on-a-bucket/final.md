---
source_ids:
- the-bucket-is-the-coordinator-2dfa2ee2
- github-denoland-celld-self-hosted-distributed-du-b51fc922
- add-preconditions-to-s3-operations-with-conditio-8c695bf4
- leader-election-with-s3-conditional-writes-fb7d9e5f
- how-to-build-a-distributed-queue-in-a-single-jso-ada83d75
- kafka-is-dead-long-live-kafka-the-case-for-diskl-71c62a75
content_mode: in_a_nutshell
label: IN A NUTSHELL
---

celld runs a Cloudflare Workers application, Durable Objects included, on your own machines. It has no membership protocol, no failure detector, and no consensus service; the bucket does that work. A node owns a cell because it won one atomic write to the bucket, and every cell's SQLite state is replicated there. With one node, a write is acknowledged once it reaches the bucket. With two or more, it is acknowledged once another node holds it on disk, and the upload follows. Either way, losing a node cannot lose an acknowledged write. The price is a strict contract on the store, checked at every startup.

## The example

Take a hypothetical shop with one Durable Object per cart. The cart `Cart:alice` is a cell: a named server with its own SQLite database. Two nodes, A and B, start against the same bucket, `s3://shop-cells`. Neither is configured with the other's address. Each finds the other through the node leases in the bucket.

## Who owns the cart

When the first event reaches `Cart:alice`, its owner writes an ownership record with a conditional create, which fails if the record already exists. Say A wins. If B tried the same create, it would fail. Exactly one node owns a cell at a time.

Alice's next request lands on B. Any node can take a request, but only the owner can run the cell, so B proxies the call to A over the peer tunnel. That hop is why routing a cell's traffic to its owner is worth doing when latency matters.

## When a write counts

Alice adds a book. A commits it, captures the change as LTX, Litestream's replica format, and sends it to B. When B has it on its own disk, A answers Alice. The bucket upload finishes afterwards. This is the fleet proof. In a fleet of three or more, A picks two followers, and an acknowledged write exists in three copies.

Run A alone and the rule changes. A has no one to send to, so every write waits for the bucket: one storage round trip. This is the bucket proof. `CELLD_DURABILITY` defaults to `fleet`; a lone node requests it and falls back.

The numbers: about 90 ms for a write to a region-local store. One loaded lab fleet measured about 600 ms against a store that was not region-local, and about 25 ms once a second node held the write.

In both modes the bucket keeps the long-term state. The bucket holds the truth; nodes only borrow it. If A dies, another node acquires the cart through the same bucket protocol. Before the takeover restores the cell, celld recovers the open log from the prior owner. A large cell comes back page by page, each page read from the bucket on first use.

## What the store must promise

- **Conditional create:** creating a record fails when it already exists.
- **Conditional overwrite:** a compare-and-swap fails when the object changed since the read.
- **Read-after-write consistency:** a read after a successful write returns that write.
- **Exact ranged reads:** a `Range` request returns precisely those bytes. Restore reads pages by range, so a wrong range is a correctness failure.

No store publishes whether it honors conditional writes, so every node probes at startup. A clear violation stops the node rather than risk a second owner. An ambiguous failure gets three attempts, then a warning. The probe cannot be disabled.

Amazon S3, Cloudflare R2, Google Cloud Storage, Tigris, and Azure Blob Storage qualify. MinIO community passes the test but is not qualified. Backblaze B2, Hetzner Object Storage, and DigitalOcean Spaces do not.

The bucket also holds deployments, node leases, the peer-authentication secret, alarm wake entries, large KV values, and all R2 objects. Whoever holds the bucket credentials controls the fleet.

## Where the pattern comes from

S3 notoriously lacked compare-and-swap. In August 2024, AWS added `If-None-Match` to `PutObject`: the put succeeds only if no object has that key, and otherwise returns `412 Precondition Failed`. Gunnar Morling showed this is enough for leader election. Nodes race to create a lock file for the next epoch, `lock_0000000001.json`, then `lock_0000000002.json`, an endless numbered succession; the winner leads. Checking a lock's validity and doing the work are never atomic, so work by a stale leader must be detected and fenced off, with the epoch as the fencing token. S3's guide now also describes checking an object's ETag before updating it.

turbopuffer built its indexing queue as one file, `queue.json`, rewritten by CAS. A replace can take up to 200 ms, so it batches writes with group commit, and a stateless broker runs the single commit loop so no one contends for the object. The broker does not acknowledge a write until it lands in object storage. If two brokers exist briefly, CAS keeps the queue correct; the old one learns it was replaced when its CAS fails.

WarpStream made the same bet for Kafka: stateless agents, data in S3, no local disks. It says this makes it 5 to 10 times cheaper than Kafka in the cloud, because inter-zone bandwidth fees can be over 80% of a Kafka deployment's infrastructure cost at scale. The trade was latency: a P99 of about 400 ms for produce requests, since nothing is acknowledged until it is durable in S3. Produce latency is now tunable down to about 33 ms median with Lightning Topics.

celld faces the same latency. Its fleet proof takes the upload off the response path.
