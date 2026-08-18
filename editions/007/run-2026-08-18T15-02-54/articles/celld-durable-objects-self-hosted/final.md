---
source_ids:
- celld-durable-objects-self-hosted-0b5b2fb8
- celld-documentation-eae4dcbc
- cloudflare-compatibility-058f0bd3
- webassembly-a0dede27
content_mode: article
label: ARTICLE
---

celld runs your Workers and Durable Objects code unchanged on your own machines, and keeps all shared data in an S3-compatible or Google Cloud Storage bucket you own. A cell is a Durable Object: a small server with a name and a private SQLite database, one thread, one writer. The bucket is the coordinator. There is no membership protocol, no failure detector, no consensus service. One atomic write to the bucket gives a node ownership of a cell, and the built-in replicator ships that cell's SQLite state to the bucket as LTX segments. celld does not acknowledge a write before the data is there, so the loss of a node cannot lose an acknowledged write. To add a node, point it at the bucket. celld = V8 + SQLite + LTX, a stateful distributed system that rests entirely on S3.

## The cell

You make one cell for each user, document, chat room, or AI agent. Two requests to the same cell never run at the same instant; a second can interleave only while the first awaits, and storage operations are synchronous, so they never interleave at all.

A cell is **resident** when it is in memory, **active** while working, **idle** while waiting. An idle cell leaves memory. If it keeps its hibernatable WebSocket clients and stays on its node, it is **hibernated**; if no node holds it, it is **inactive**, an object in the bucket costing almost zero. Every cell starts there. Memory holds nothing across these transitions, so the constructor runs again on the next event: a hibernated cell starts as a cold start does, and only two facts separate them, the clients stay connected and the cell stays on its node.

Cells fit workloads that divide into named, stateful units: a room holding its own WebSockets needs no lock and no message bus; an agent holds its memory, schedule, and inbox in its own database and hibernates between events; one cell per user or tenant shards the application from the start, and the contention of a shared database does not appear, because none exists.

## The numbers, and their conditions

Warm stateless requests run 0.2 ms p50 and 0.3 ms p99, about 94k req/s per worker thread, and a hibernated cell wakes in about 4 ms. Those speed and density figures come from one node, trivial cells, an Apple M-series laptop over loopback. Fleet vCPUs are slower: activation p50 is 35.9 ms on a 2 vCPU node.

Durability was measured on a 4 vCPU / 8 GB fleet in one region against a region-local bucket: one writer per cell, epoch-fenced; zero acknowledged writes lost on kill (RPO=0); about 90 ms region-local durable write latency; failover after node loss in about 20 s with none lost. Failover is a SIGKILL of a loaded node, with every room verified after recovery.

On density and price, the summary gives 0.47 MB of RAM per resident cell, 2,500 resident cells per 8 GB node, and about $0.02 per resident cell-month against whole $48 / 8 GB nodes at DigitalOcean list, capacity added in steps; the reference prose gives 1,000 resident cells on an 8 GB node, so approximately $0.05 each month. Either way it is a base cost before workload: traffic and writes add compute and bucket usage. Durable Objects is quoted at Workers Paid, $5/mo plus $4.15 per resident cell-month, with a free plan that covers toy scale.

## What the bucket must be

Ownership records depend on conditional writes and read-after-write consistency. Amazon S3, Cloudflare R2, Google Cloud Storage, Azure Blob Storage, and Tigris qualify. MinIO community edition, Backblaze B2, Hetzner, and DigitalOcean Spaces do not. The bucket credentials give full control of the fleet: they hold the deployments, the SQLite replicas, the ownership records, the node leases, and the peer-authentication secret. Keep them safe.

## What changes when you run the model yourself

A cell's identity isn't fused to a machine. Ownership is a lease in your bucket, granted by compare-and-swap; lose a node and another acquires the lease and restores the cell in seconds, your fleet reading your storage rather than a vendor restoring a placement you can't see. Your fleet still depends on its machines, network, and bucket provider. What changes is tenancy: no shared scheduler or placement layer can couple your application to another customer's workload. And when a cell misbehaves the evidence is on your disk, the ownership record, the SQLite and LTX files, the logs, so you answer "what happened to my cell" with sqlite3 and grep.

Self-hosting is not automatically more reliable. It makes the failure domain explicit and inspectable: your nodes, your bucket provider, your operational choices.

## The compatibility boundary

celld runs the Workers runtime with Durable Objects as the stateful core: module Workers, fetch, JS RPC, service bindings, static assets, alarms, hibernatable inbound and outbound WebSockets. The scope rule is simple. If Cloudflare builds a function on Durable Objects, celld can get that function; a function on a different primitive is out of scope. So D1, Workflows, and Queues are planned, while KV (a global cache with eventual consistency) and R2 (celld runs *on* blob storage) are not, along with the Cache API, the managed platform services, cron triggers, custom domains, and TLS termination.

A configuration or binding that is not available must fail loudly, at deploy or at first use. A silent gap is a bug, and two are marked as known: `connect()` on `cloudflare:sockets` gives an inert stub instead of throwing, and the unimplemented `node:` modules give inert stubs rather than failing the import. Also absent: facets, HTMLRewriter, `setInterval`, `getTags()`, and stubs crossing an isolate boundary, which means a Durable Object method takes and returns structured-cloneable values. Web Crypto and `node:crypto` are partial, and an unavailable algorithm throws. In Wrangler config only `name`, `main`, `compatibility_date`, `compatibility_flags`, `durable_objects`, `migrations`, `assets`, `services`, and `vars` are accepted; any other key stops the deploy and names itself.

## Running a fleet

For a fleet node, bind the public and internal listeners separately and set `--advertise` to the internal address. An explicit advertised address requires an explicit internal listener, and celld rejects an explicit non-loopback public listener without one. celld cannot verify that an advertised hostname reaches the internal listener; you must route it there, and not to the public Worker listener. Nodes find each other through the leases in the bucket. There is no join command and no fixed membership list.

The bucket supplies discovery and authority, not network reachability. celld does not terminate TLS. Put the advertised addresses on a private network you trust or an encrypted overlay such as WireGuard or Tailscale; the internal listener also has an unauthenticated operator API, so do not show it to the public internet.

On SIGTERM or SIGINT the node reports itself unhealthy, answers new requests with 503, hands every resident cell to a peer by releasing ownership, and finishes what is in flight. `CELLD_RELEASES` bounds concurrent releases at 128 by default so a large node doesn't flood the object store; `CELLD_SHUTDOWN_DRAIN_MS` bounds the whole drain at 25000, and you must set it below your orchestrator's stop grace. There is no rollout command, because the health signal lets the orchestrator pace the roll. During a rolling update, wait for every node to report `restoring=0` before restarting the next, so one restart's cold work finishes before the next removes more warm capacity. The upgrade from v0.1.0 to v0.2.0 is the exception: stop every v0.1.0 node first. A fleet must not mix the two versions.

`celld diagnose` reads the node leases and probes each live peer without taking a lease or changing ownership, reporting expired records, unsafe or incorrect advertised addresses, unreachable peers, authentication failures, and protocol versions that do not agree.

## The tone

We love Cloudflare; this very page is served by a Cloudflare Worker. The Durable Objects model, a single-threaded object with its own storage, addressed by name, is one of the best primitives distributed systems has been handed in years, and that design is Kenton Varda's and the Cloudflare Workers team's. A primitive this good deserves to run anywhere.

---

One note from me, outside the piece: the density and cost figures conflict between the summary tables (2,500 cells per 8 GB node, ~$0.02 each) and the reference prose (1,000 cells, ~$0.05 each). I printed both as they stand rather than pick one.
