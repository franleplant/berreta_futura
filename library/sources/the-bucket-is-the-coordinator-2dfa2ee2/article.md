# The bucket is the coordinator
celld: Durable Objects on Your Own Storage

This is the architectural centerpiece. There is **no membership protocol, no failure detector, and no consensus service**. A **node** is one celld process; a **fleet** is the set of nodes sharing one **fleet bucket**. Ownership of a cell is a record in that bucket, claimed with one atomic write. celld's built-in replicator continuously ships each cell's SQLite state to the bucket as **LTX segments**, Litestream's replica format from Ben Johnson. The loss of a node cannot lose an acknowledged write, because celld does not answer a write until the data survives a failure (**RPO=0**).

The bucket supplies discovery and authority: nodes find each other through the leases in it, a node acquires a cell with one atomic write, and every cell's state is continuously replicated there as LTX segments. What it does *not* supply is network reachability. Peers talk over a private network or an encrypted overlay. Note the consequence of one-owner-per-cell: any node can take the request, but only the owner can run the cell, so a call that lands elsewhere is proxied to the owner over the versioned peer tunnel. That hop is why routing a cell's traffic to its owner is worth doing when latency matters.

## How RPO=0 is earned: bucket proof vs. fleet proof

The durability mechanism depends on fleet size, and it is explicit.

- **With one node**, every write waits for the bucket. This is the **bucket proof**: one storage round trip, which is the minimum latency for a durable write.
- **With two or more nodes**, the node serving the cell sends each write to another node and answers as soon as that node has the data on its own disk; the bucket upload finishes afterwards. This is the **fleet proof**. The owner and the nodes it sends to form the cell's **ensemble**, and each of those nodes is a **follower**. A node picks one or two followers (never itself), so a fleet of three or more nodes holds *three copies* of an acknowledged write, and the ensemble keeps acknowledging while one follower remains.

`CELLD_DURABILITY` selects the mode (default `fleet`). A single node requests the fleet posture and does not get it, falling back to bucket proof. Run two or more nodes if write latency matters.

RPO=0 is earned differently by fleet size, and the whole difference is *where the acknowledgement falls*. The bucket is the long-term store in both modes; the fleet proof simply takes the upload off the response path.

Four properties make this possible, and they are non-negotiable requirements on the store:

- **Conditional create**: creating an ownership record fails when the object already exists.
- **Conditional overwrite**: a compare-and-swap on the prior record fails when the object changed after the read.
- **Read-after-write consistency**: a read after a successful write returns that write.
- **Exact ranged reads**: a `Range` request returns precisely the requested bytes. A large cell is restored *page by page* through a fault-in SQLite VFS that reads each page from the bucket on first use, so a wrong range is a correctness failure, and the startup probe checks it.

| Store | Fleet-qualified? | Conditional-write path |
| --- | --- | --- |
| Amazon S3 | Yes | `If-None-Match: *` / `If-Match` etag CAS |
| Cloudflare R2 | Yes | same headers; celld's release tests run here |
| Google Cloud Storage | Yes | XML API `x-goog-if-generation-match` |
| Tigris | Yes | documented conditional operations |
| Azure Blob Storage | Yes | `If-None-Match: *` / `If-Match` on Put Blob; qualified 2026-08-18 |
| MinIO (community) | Passes test, not qualified | conditional writes work on RELEASE·2025-09-07 or later (#162 pinned one broken release) |
| Backblaze B2 | No | — |
| Hetzner Object Storage | No | — |
| DigitalOcean Spaces | No | — |

Caveat · storage probe

No object store publishes whether it honors conditional writes, so celld asks. Each node runs a probe at startup: conditional writes that must succeed and fail in the right places, plus a ranged read that must return exactly the requested bytes. A clear contract violation (an unsupported operation, wrong bytes, an ignored condition) stops the node at once rather than risk a second owner for a cell. An ambiguous failure gets three attempts and then a warning, since a transient outage can clear. `celld diagnose` runs the same probe on demand, and `--read-only` skips it there. The startup probe cannot be disabled: a node with `CELLD_STORAGE_PROBE` set does not start.

A bucket value can carry a key prefix (`s3://bucket/team-a`), so two fleets can share one bucket. A value without a prefix keeps objects at the bucket root, so an existing fleet never moves its data. The bucket also holds the deployments (with container images under `deploy/images/`), node leases, the shared peer-authentication secret, the fleet capacity sample, the alarm wake entries, large KV values, and all R2 objects: **whoever holds the bucket credentials controls the fleet**.
