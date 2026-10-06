---
source_ids:
- celld-durable-objects-self-hosted-0b5b2fb8
- celld-documentation-eae4dcbc
- cloudflare-compatibility-058f0bd3
- webassembly-a0dede27
content_mode: article
label: ARTICLE
---

celld runs your Cloudflare Workers and Durable Objects code unchanged on your own machines, keeps your data in a bucket you own, and claims to cost orders of magnitude less at scale. The bucket is the coordinator: there is no membership protocol, no failure detector, no consensus. One atomic write gives a node ownership of a cell, and celld does not acknowledge a write until the cell's SQLite data is in the bucket (RPO=0). Self-hosting is not automatically more reliable. It makes the failure domain explicit and inspectable: your nodes, your bucket provider, and your operational choices.

## What a cell is

In Cloudflare terms, a cell is a Durable Object: a small server with a name and a private SQLite database. You make one cell for each user, document, chat room, or AI agent. A cell serves HTTP, holds WebSocket connections, sets alarms, and makes outbound connections.

Each cell runs on one thread. A second request can interleave only while the first awaits, and storage operations are synchronous, so a storage operation never interleaves at all. The data in a cell therefore stays consistent. Cells share no database, and the application divides into cells from the start.

A cell is **resident** when in memory: **active** while working, **idle** while waiting. celld removes an idle cell from memory. If it keeps its hibernatable WebSocket clients and stays on its node, it is **hibernated**. A cell no node holds is **inactive**: only an object in the bucket, costing almost zero. Every cell starts there. Memory holds nothing across these transitions, so the constructor runs again on the next event.

Cells fit real-time applications (one room, one cell, no lock, no message bus), agents (memory, schedule, and inbox in one database, hibernating between events), and sharded web applications, where the contention of one shared database does not appear, because no shared database exists.

## How it works

Ownership is a lease in your bucket, granted by compare-and-swap. celld's built-in replicator continuously ships each cell's SQLite state to the bucket as LTX segments, Litestream's replica format from Ben Johnson. Lose a node and another acquires the lease and restores the cell in seconds. To add a node, point it at the bucket; there is no join command and no fixed membership list.

The store must provide conditional writes and read-after-write consistency. Amazon S3, Cloudflare R2, Google Cloud Storage, Azure Blob Storage, and Tigris qualify; MinIO (community edition), Backblaze B2, Hetzner, and DigitalOcean Spaces do not. The bucket credentials give full control of the fleet.

## The numbers

| | |
|---|---|
| Acknowledged writes lost on kill | 0 |
| Durable write latency (region-local) | ~90 ms |
| Failover after node loss, 0 lost | ~20 s |
| Stateless request p50 / p99 | 0.2 / 0.3 ms |
| Wake a hibernated cell | ~4 ms |
| RAM per resident cell | 0.47 MB |
| Resident cells per 8 GB node | 2,500 |
| $ per resident cell-month | ~$0.02 |

Speed and density were measured on one node with trivial cells, on an Apple M-series laptop over loopback. Fleet vCPUs are slower: activation p50 is 35.9 ms on a 2 vCPU node. Durability was measured on a 4 vCPU / 8 GB fleet in one region, by SIGKILL of a loaded node, with every room verified after recovery. The documentation gives a lower figure: 1,000 resident cells per 8 GB node, approximately $0.05 each month.

The cost comparison sets Durable Objects at $5/mo plus $4.15 per resident cell-month against whole $48 DigitalOcean nodes, added in steps. Both are base costs before workload; traffic and writes add compute and bucket usage.

## Reliability

Cloudflare's model stays; placement, state, and evidence move to infrastructure you choose. No shared Durable Objects scheduler can couple your application to another customer's workload. When a cell misbehaves, the evidence is on your disk: the ownership record, the SQLite and LTX files, the logs. You answer "what happened to my cell" with sqlite3 and grep, not a status page that declines to say.

The tone is not hostile. The page is served by a Cloudflare Worker, and the Durable Objects model is Kenton Varda's and the Cloudflare Workers team's design. celld calls itself a love letter to their idea; a primitive this good deserves to run anywhere.

## Running a fleet

Install with `curl -fsSL https://celld.dev/install.sh | sh`, set the bucket variables, and run `celld deploy` from a Wrangler project (esbuild needed if there is Worker code). A fleet node binds a public listener and a separate internal one for peers. celld does not terminate TLS, and the internal listener carries an unauthenticated operator API, so keep peer addresses on a private network or an overlay such as WireGuard or Tailscale.

On SIGTERM a node reports unhealthy, answers new requests with 503, hands each resident cell to a peer, and finishes in-flight requests, within `CELLD_SHUTDOWN_DRAIN_MS` (default 25000). Set it below your orchestrator's stop grace. Roll out with your orchestrator's rolling update, waiting for `restoring=0` before the next restart. The upgrade from v0.1.0 to v0.2.0 must not be rolling: stop every old node first.

## What runs

celld runs the Workers runtime with Durable Objects at its core: module Workers, fetch, JS RPC, service bindings, static assets, WebAssembly, and an experimental Worker Loader. The scope rule: what Cloudflare builds on Durable Objects, celld can get. D1, Workflows, and Queues are planned. KV, R2, Cache API, Workers AI, cron triggers, and custom domains are not.

A missing feature must fail loudly; a silent gap is a bug. The known silent gaps remain: `cloudflare:sockets` `connect()` gives an inert stub, and unimplemented `node:` modules such as `node:http` load as stubs instead of failing. Stubs cannot yet cross an isolate boundary, so a Durable Object method takes and returns only structured-cloneable values. `celld deploy` reads `wrangler.jsonc` or `wrangler.json`, not `wrangler.toml`, and stops on any unknown key.
