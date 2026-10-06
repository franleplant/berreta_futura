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

celld promises three things: an acknowledged write is durable, a cell has one writer at a time, and code written for Cloudflare Workers and Durable Objects operates the same on celld. Each cell is a SQLite database. The bucket holds the authority: a conditional write decides who owns a cell, an epoch in the key fences stale writers, a write is acknowledged only after it is in the bucket and the ownership record still names the node, and a seal keeps a fenced node's late writes from ever returning. celld is an alpha and is not safe for hostile multi-tenant use. Across every live-fleet run of every scenario, no acknowledged write was lost.

## Ownership and fencing

Each cell has one ownership record in the bucket, naming the owner's session and a fencing epoch. A node acquires a cell with a conditional write: a create when no record exists, a compare-and-swap when one does. The bucket accepts one such write, so two nodes cannot acquire the same cell. Every activation, takeover or local wake, advances the epoch, so an epoch never has two writers.

The replicator copies each cell's data to `cells/<cell>/ltx/e<epoch>/` with plain, unconditional PUTs. The fence is the epoch in the key, not a condition on the request. A node that lost ownership can keep writing, but into a superseded prefix; a restore selects the current lineage, and the data path pays no conditional-write cost.

The prefix protects the data, not the promise to the client. Two rules close that gap:

- **The acknowledgement rule (RPO=0).** A gate holds each response until the replicator proves the write is in the bucket. celld then reads the ownership record once and acknowledges only if it still names this node at this epoch. The check is a read, not a clock comparison, so a paused process or a skewed clock cannot pass it.
- **The epoch seal.** A fenced node can append to the newest prefix after a takeover, and a later restore could read that tail. The first activation that restores from an epoch writes `e<epoch>.seal.json` with a conditional create, fixing the highest transaction any restore of that epoch can read. Every acknowledged write sits at or below the seal; the fenced node's later writes sit above it and never return. If the seal write fails, the activation fails.

A node that cannot reach the bucket cannot renew its lease or replicate, so it fences itself: it stops writes and releases its residency.

## What the bucket must provide

A conditional create, a conditional overwrite, and read-after-write consistency. On S3-compatible stores celld sends `If-None-Match: *` and `If-Match`, comparing the etag; Amazon S3, Cloudflare R2, and Tigris document these, and release tests run against R2. A `gs://` bucket uses the Cloud Storage XML API with `x-goog-if-generation-match`, because Cloud Storage does not apply `If-Match` to a PUT.

MinIO (community edition), Backblaze B2, Hetzner Object Storage, and DigitalOcean Spaces do not implement the required conditional writes, and on them two nodes can own one cell. A store can also accept the headers without applying the condition and fail late and silently, so test a store before you trust a fleet to it.

## Limits and security

- One application deployment per fleet; no multi-tenant scheduler, account service, or managed ingress.
- A bucket is required, also on a laptop. There is no local filesystem mode.
- celld terminates no TLS, on either listener, and does not authenticate the application's users. Put TLS and authentication in front of the public listener (`--listen`).
- The internal listener (`--internal-listen`, default `127.0.0.1:0`) serves the peer protocol and the operator API. The operator API does not authenticate: anyone who reaches it can inspect state, evict a cell, or stop the process. Keep it on a private network or an overlay such as WireGuard or Tailscale. Peer requests keep their own HMAC, body signature, clock limit, and replay protection.
- The bucket stores deployments, cell state, leases, and the shared peer secret. Whoever holds its credentials controls the fleet; scope each credential to one bucket.
- Credentials come from `AWS_*` or managed credentials, not `~/.aws` profiles or SSO; `gs://` uses Google Application Default Credentials or a key from `GOOGLE_*`.
- Cross-node WebSocket ingress works, but its test coverage is thinner than for one node. An outbound Durable Object WebSocket does not follow its cell to another node; keep the intent in storage and reconnect.
- No rebalancing when a node joins, no automatic updates (the previous SHA is the rollback), no Windows, and no prebuilt binaries for Intel Macs.
- Security fixes apply to the latest release only.

## Testing

Each promise is attacked at the layer where a failure shows most clearly.

- **Conformance.** Each program runs on workerd, Cloudflare's production runtime, and on celld, on identical bytes; the outputs must be equal. The corpus only grows, and it includes suites ported from workerd.
- **Simulation.** The coordination protocol is a pure decision core with no I/O. A seeded simulator injects latency, compare-and-swap races, lost responses, drifting clocks, and crashes at each await point, and the seed replays any failure exactly. Properties must survive tens of thousands of seeds; the core protocols have run through millions of schedules. Deliberately broken protocol variants must be caught, because a suite that stays green against a broken protocol is a broken suite.
- **Live fleets.** Real VMs and a real bucket, with faults injected between verification passes that compare each cell's durable state exactly. A node killed with `SIGKILL` mid-stream, its local database deleted, recovers every acknowledged write from the bucket. A frozen owner, once unfrozen, sees its lease moved and refuses to serve old state. A node cut off from the bucket fences itself. A throttled bucket slows the engine to the store's rate without amplifying the throttle. The sweeps show zero body faults, zero status faults, and zero lost messages.

Numbers, with their conditions:

- 500 claimants, 5,500 attempts on the same cells: one writer per epoch, zero violations.
- A warm resident request does zero bucket operations: p50 ~1.1 ms, p99 ~7 ms on a fixed host.
- A durable write costs one bucket round trip; concurrent writes to one cell share one upload.
- No restore time is given until a fleet run measures `celld-ltx`.
- Ten nodes of 4 vCPU and 8 GB held 10,000 resident cells and 20,000 WebSocket connections; after two nodes were stopped, every cell's data was available again in ~11 s at the tail, with reserve headroom.

The recorded edge: a fleet full to its resident limit has no room for a lost node's cells, so losing more than one node at the limit degrades service. Bug reports go to [github.com/denoland/celld/issues](https://github.com/denoland/celld/issues).

## Telemetry

Off by default, at no cost; `CELLD_OTEL=1` turns it on. The default sink writes Parquet to the fleet bucket under `telemetry/`, partitioned by node and hour, and DuckDB queries it directly; `CELLD_OTEL_SINK=otlp` sends to a collector instead. The schema is `v0-unstable`.

celld records a span per Worker request, cell event, outbound `fetch()`, and cell start, and each `console.log` line as a log carrying its trace and span ids. It reads and sends `traceparent`. Under load, telemetry sheds before requests do. There are no metrics yet, a known gap.

Files flush every 5 minutes or 5 MB, whichever comes first. For a near-live view, set `CELLD_OTEL_FLUSH_MS=10000`, but turn on an hourly compaction job first, run on a maintenance node and never on the current hour, or queries grow slow within hours.
