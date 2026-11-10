---
source_ids:
- the-bucket-is-the-coordinator-2dfa2ee2
- github-denoland-celld-self-hosted-distributed-du-b51fc922
- add-preconditions-to-s3-operations-with-conditio-8c695bf4
- leader-election-with-s3-conditional-writes-fb7d9e5f
- how-to-build-a-distributed-queue-in-a-single-jso-ada83d75
- kafka-is-dead-long-live-kafka-the-case-for-diskl-71c62a75
content_mode: explainer
label: EXPLAINER
---

celld is an open-source daemon from Deno that runs a Cloudflare Workers application on your own machines. Each object in it is a **cell**: a named server with its own SQLite database. You run one celld process on each machine and point them all at one object storage bucket. Nothing else coordinates them. A machine takes charge of a cell with one atomic write of a small record into the bucket, so only one machine runs a cell at a time. celld does not answer a write until the data would survive the loss of a machine. With one machine, that means the bucket holds the data. With two or more, another machine holds it on disk and the bucket catches up afterwards, which is much faster.

**The example.** This app is invented for this piece. An office has a small Workers app called Shelf for lending things off shared shelves. It has one Durable Object class, `Shelf`, with one instance per physical shelf. The third-floor shelf is the cell `Shelf:third-floor`. When someone borrows the stapler, the app records the loan in that cell's SQLite database. The office runs two machines, `node-a` and `node-b`, against the bucket `s3://office-cells`.

## As a user

A **node** is one celld process. A **fleet** is the set of nodes that share one bucket, the **fleet bucket**. Every node embeds V8, the JavaScript engine, and runs the bundles Wrangler produces. A **Durable Object** is a Cloudflare Workers object with its own storage. On celld, each one is a cell.

You touch four things.

- **Your existing `wrangler.json`.** celld deploys from it. It runs Workers, Durable Objects, KV, Queues, D1, R2, Workflows, Cron Triggers, and static assets. Containers are experimental. The README rules out anything that needs the Cloudflare network, a GPU, or a browser farm.
- **`celld dev`.** It runs one node on your laptop with a local object store, with no Docker and no cloud bucket. Shelf answers at `http://127.0.0.1:9876` and keeps its state in `.celld/dev` between runs.
- **`celld deploy . --bucket s3://office-cells`.** It bundles the Worker code with esbuild, which must be on `PATH`, and writes the deployment into the bucket.
- **`celld --bucket s3://office-cells ...`** on each machine. Each node gets two listeners. The public one, port 8080 in the README's example, sits behind your load balancer. The internal one, 8081, carries traffic between nodes and must stay on a private network or an encrypted overlay such as WireGuard or Tailscale. `node-b` needs no extra configuration, because nodes find each other through the bucket.

You can count on these things. One node owns a cell at a time. Losing a node cannot lose an acknowledged write; the celld documentation calls this **RPO=0**. An inactive cell costs almost nothing. There is no serving control plane to run.

celld qualifies Amazon S3, Cloudflare R2, Google Cloud Storage, Tigris, and Azure Blob Storage. MinIO passes the test but is not qualified. Backblaze B2, Hetzner Object Storage, and DigitalOcean Spaces are not qualified.

## As a developer

A fleet runs one application, and every node loads the latest successful deployment from `deploy/current.json`. `celld diagnose` lists every node **lease** (a node's record of itself in the bucket) and probes each live peer.

The durability mode decides your write latency. `CELLD_DURABILITY` defaults to `fleet`. A single node asks for that mode, does not get it, and falls back to waiting on the bucket. The README gives the figures: about 90 ms per write to a region-local store. One loaded lab fleet measured about 600 ms against a store that was not region-local, and about 25 ms once a second node held the write. For Shelf, `node-b` is worth more as a second witness than as spare capacity.

The mistakes that cost you:

- **Trusting old dev state.** The state in `.celld/dev` survives a configuration change and is not migrated. An object can keep a value the new configuration rejects, and the failure looks unrelated to the change. `celld dev --clean` starts from empty.
- **Using an unqualified store.** Each node probes the store at startup and stops at once on a clear contract violation. The probe cannot be turned off: a node with `CELLD_STORAGE_PROBE` set does not start.
- **Exposing the internal port, or handing out bucket credentials.** celld rejects a literal public advertise address unless you pass `--unsafe-public-advertise`. The bucket holds deployments, leases, the peer secret, and all state. In the documentation's words, "whoever holds the bucket credentials controls the fleet."
- **Upgrading node by node.** Mixed versions cannot share a serving fleet. Stop all old nodes, then start the new ones.

## Inside

### One request

Follow the stapler.

The load balancer hands the borrow request to `node-b`. The ownership record in the bucket says `node-a` owns `Shelf:third-floor`, so `node-b` forwards the call to `node-a` over the peer tunnel, the versioned HTTP path on the internal listener. That hop is why routing a cell's traffic to its owner pays when latency matters.

On `node-a`, the `Shelf` code runs and commits a SQLite write. celld captures that commit as an **LTX segment**, the replica format of Ben Johnson's Litestream. It sends the segment to its **followers**, the one or two other nodes it has picked for this cell; the owner and its followers form the cell's **ensemble**. A node never picks itself, so here the only candidate is `node-b`. When `node-b` has the segment on its disk, `node-a` answers the client. The upload to the bucket finishes afterwards. That is the **fleet proof**. Alone, `node-a` would wait for the bucket before answering, which is the **bucket proof**. In both modes the bucket is the long-term store. The only difference is where the acknowledgement falls.

If `node-a` dies, another node takes over the cell. Before it restores the cell, celld recovers the open log from the prior owner. The README leaves the full protocol to celld's guarantees page, and so does this piece.

### What makes it correct and durable

The documentation names four properties the store must have:

- **Conditional create.** Creating a record fails if the object already exists, so two nodes cannot both claim a cell.
- **Conditional overwrite.** A **compare-and-swap** on the prior record fails if the object changed after it was read; compare-and-swap means "write this only if the object is still what I saw."
- **Read-after-write consistency.** A read after a successful write returns that write.
- **Exact ranged reads.** A request for a byte range returns exactly those bytes. A large cell restores page by page, fetching each page from the bucket the first time it is used, so a wrong range is a correctness failure, not a slow one.

No store publishes whether it honors these, so each node asks at startup. A clear violation (an unsupported operation, wrong bytes, an ignored condition) stops the node rather than risk a second owner for a cell. An ambiguous failure gets three attempts and then a warning, since a transient outage can clear.

In a fleet of three or more nodes, an acknowledged write exists in three copies, and the ensemble keeps acknowledging while one follower remains.

### The primitive underneath

Gunnar Morling wrote in August 2024, the week after S3 gained `If-None-Match`, that S3 had notoriously lacked such an operation, while Google Cloud Storage and Azure had offered compare-and-swap for some time. He built leader election on it: one lock file per **epoch**, a number that only grows, and a `412 Precondition Failed` for the loser. He also warned that leader election "will only ever be eventually correct," because checking a lock and doing the work are never one atomic step. Following Martin Kleppmann, he proposed the epoch as a **fencing token**, so that requests from a stale leader can be recognized and discarded.

Dan Harrison of turbopuffer built a job queue on one JSON file with the same primitive and hit its limit: a file replacement can take up to 200 ms. He answered with **group commit**, which batches waiting requests into the next write.

Each of these designs puts a slow, honest store at the center and then works around its slowness. celld works around it with a second disk on another machine. The bucket still decides who owns what.
