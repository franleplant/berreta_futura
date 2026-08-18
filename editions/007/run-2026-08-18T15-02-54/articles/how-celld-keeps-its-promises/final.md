---
source_ids:
- ownership-and-fencing-dd43dd4a
- limitations-cd53f9e3
- security-218dbf57
- testing-8010abfb
- telemetry-258b249b
content_mode: article
label: ARTICLE
---

One cell has one writer. Ownership lives in a record in the bucket, and every activation advances an epoch. Replication writes under the epoch prefix, so a fenced node's writes land in a superseded path. A write is acknowledged only after it is in the bucket and a fresh read of the ownership record still names this node at this epoch. The first restore of an epoch seals it, so the tail a fenced node appended after the takeover never returns. celld is an alpha: it requires a bucket with conditional writes, it authenticates neither the operator API nor the application, and it tests its promises three ways, against workerd, against a deterministic simulator, and against live fleets under injected faults.

## Ownership

A node acquires a cell with a conditional write: a create when no record exists, a compare-and-swap when one does. The bucket accepts one such write, so two nodes cannot acquire the same cell. Every activation advances the epoch, a takeover and a local wake alike, so an epoch never has two writers.

The replicator copies each cell's SQLite data under `cells/<cell>/ltx/e<epoch>/` with plain unconditional PUTs. The fence is the epoch in the key, not a condition on the request. A node that lost ownership can keep writing, into a prefix no restore selects. The data path pays no conditional-write cost.

The prefix protects the data. It does not protect the promise to the client.

## The two rules that protect the promise

A gate holds each write's response until the replicator proves the write is in the bucket. celld then reads the ownership record once, and acknowledges only if the record still names this node at this epoch. A read, not a clock comparison: a paused process or a skewed clock cannot pass it.

A restore selects the newest epoch prefix that has data, and a fenced node can still append to it. So the first activation that restores from an epoch writes `e<epoch>.seal.json` with a conditional create, fixing the highest transaction any restore of that epoch can read. First restorer wins, every later restore reads the same cut. Acknowledged writes sit at or below the seal, because the acknowledgement required an ownership read and the takeover preceded the seal. If the seal write fails, the activation fails.

A node that cannot reach the bucket cannot replicate, so it fences itself: stops writes, releases residency. Node failure is a normal input, not a recovery procedure.

## What the bucket must provide

A conditional create, a conditional overwrite, read-after-write consistency. On S3-compatible stores celld sends `If-None-Match: *` and `If-Match`; release tests run against Cloudflare R2, and AWS S3 uses the same client and headers. A `gs://` bucket uses the Cloud Storage XML API with `x-goog-if-generation-match`, because Cloud Storage does not apply `If-Match` to a PUT.

MinIO community edition, Backblaze B2, Hetzner Object Storage, and DigitalOcean Spaces do not implement the required conditional writes. celld is not correct on such a store: two nodes can own one cell. A store can also accept the headers and ignore the condition, failing late and silently. Test a store before you trust a fleet to it.

## Two listeners

`--listen` is public and serves the Worker. `--internal-listen` serves the peer protocol and the operator API, defaults to `127.0.0.1:0`, and must not reach the public internet. `--advertise` gives peers its address, and an explicit advertised address requires an explicit internal-listener address. celld cannot verify that the advertised address reaches the internal listener; you must route it.

The operator API does not authenticate its requests. Whoever reaches it can inspect state, evict a cell, or stop the process, so restrict it with a firewall or a private overlay. Peer requests keep their own HMAC, body signature, clock limit, and replay protection. celld terminates no TLS on either listener.

The fleet bucket holds the deployments, the cell state, the leases, and the shared peer secret. Whoever holds its credentials controls the fleet. Scope each credential to one bucket.

## Testing

Conformance runs each Workers program twice on identical bytes, on workerd and on celld, and the outputs must be equal. That shows the program is real Cloudflare code and that celld obeys the contract. The corpus only grows.

The coordination protocol is a pure decision core with the clock, the randomness, and the store behind interfaces. A simulator injects latency, compare-and-swap races, lost responses, drifting clocks, and a crash at any await point. A seeded scheduler replays every failure exactly. Properties must survive tens of thousands of seeds, and the core protocols have run through millions of schedules. Because a checker that cannot fail is worthless, deliberately broken protocol variants are run against the properties, and the properties must find the damage.

Live fleets catch what simulation cannot see: S3 tail latency, kernel and filesystem behavior, V8 under memory pressure. Nodes are killed mid write-stream with their local database deleted, frozen and thawed, cut off from the bucket, throttled to 429s, and stopped at the host level. Verification passes fetch each cell through different nodes and compare status, body, and the full message ledger. Across every run of every scenario, no acknowledged write was lost and no committed state was damaged: zero body faults, zero status faults, zero lost messages. A red run is archived with the same care as a green one.

## Numbers, with their conditions

Five hundred claimants raced for the same cells: 5,500 attempts, one writer for each epoch, zero violations. A request to a resident cell does zero bucket operations, p50 ~1.1 ms and p99 ~7 ms on a fixed host. A durable write costs one bucket round trip, which is what RPO=0 means; concurrent writes to one cell join one shared upload. Ten nodes at 4 vCPU and 8 GB held 10,000 resident cells and 20,000 concurrent WebSocket connections, and after two of the ten were stopped every cell's data was available again on another node in ~11 s at the tail, with reserve headroom. Restore times are not quoted, because the measurements come from the retired external replicator.

The clearest known edge is that headroom. A fleet full to its resident limit has no space for a lost node's cells, so losing more than one node at the limit degrades the service. Both sides of that line get measured.

## Alpha boundary

One application deployment per fleet, no multi-tenant scheduler, no managed ingress. A real bucket is required even on a laptop. Credentials come from the `AWS_*` environment or explicit managed credentials, not from `~/.aws` profiles or SSO. Any node can be WebSocket ingress for any cell, though coverage for close codes and cross-node reconnection is thinner; send a cell's traffic to its owner if latency matters. An outbound Durable Object WebSocket does not survive the cell moving: keep the intent in storage and reconnect after activation. No Windows, no prebuilt Intel Mac binaries, no rebalancing when a node joins, no update agent. The installer keeps immutable releases behind one `current` pointer, so the previous SHA is the rollback.

## Telemetry

Off by default and free when off; `CELLD_OTEL=1` turns it on. The default sink writes Parquet under `telemetry/` in the fleet bucket, partitioned by node and hour, and DuckDB queries it directly. The `otlp` sink sends the same data to a collector. Schema is `v0-unstable` and column names can change.

celld records a span for each Worker request, each cell event, each outbound `fetch()`, and each cell start, and each `console.log` line as a log record carrying the trace and span id, so logs join traces across `await`. It reads and sends `traceparent`, so a Worker call to a Durable Object stays in one trace. The sampler decides at request start. Under load, telemetry sheds before requests do, and celld counts what it sheds. There are no metrics yet, a known gap rather than a silent one.

Defaults flush at 5 minutes or 5 MB, whichever comes first: good for investigation after the fact, and safe with no compaction job. `CELLD_OTEL_FLUSH_MS=10000` gives a near-live view but many small files, so turn on compaction first, then shorten the flush. Compaction rewrites one finished past hour into one sorted zstd file, on a maintenance node, never on a celld node and never on the current hour.
