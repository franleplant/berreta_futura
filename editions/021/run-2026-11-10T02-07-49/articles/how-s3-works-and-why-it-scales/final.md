---
source_ids:
- building-and-operating-a-pretty-big-storage-syst-7f2204cf
- what-is-amazon-s3-amazon-simple-storage-service-e380da8d
- diving-deep-on-s3-consistency-a5bf47a7
- amazon-s3-update-strong-read-after-write-consist-fb59ed14
- using-lightweight-formal-methods-to-validate-a-k-a1b41482
- best-practices-design-patterns-optimizing-amazon-496d6ca3
- aws-re-invent-2024-dive-deep-on-amazon-s3-stg302-2c5c8e42
content_mode: in_a_nutshell
label: IN A NUTSHELL
---

S3 keeps your objects on tens of millions of hard drives, and a hard drive can do only about 120 random reads a second. Left alone, one customer's data would sit on a few drives and queue. We spread each customer thinly across very many drives, so one customer's burst meets other customers' quiet. We cut each object into shards and add parity, so any large enough subset rebuilds it. A dead drive, a slow drive, or a new release that fails costs a shard, not the object. Since December 2020, a read after a successful write returns that write. As workloads pile up, the total load gets smoother, not wilder.

## The example

Take a hypothetical lab. It keeps a petabyte in one-megabyte objects, about a billion of them. Once a day it wants to read all of it in one hour. That is 275 gigabytes a second. We follow the lab through.

## The drive

A drive is a spinning platter and a swinging arm. To read, the arm moves to the track, which is the seek. Then it waits for the data to come round, which is the rotation. On a 7,200 RPM drive each takes about four milliseconds. Reading a half-megabyte shard adds about two more. That makes ten milliseconds per read, a hundred reads a second, and 50 megabytes a second.

Since IBM's first commercial drive in 1956, capacity has grown 7.2 million times. Seek times have improved only 150 times, because the arm and the platter are mechanical.

At 20 terabytes a drive, the lab's petabyte fits on 50 drives. Reading it at 275 gigabytes a second takes over 5,000. If the lab built this itself, it would pay for a hundred times the drives and leave them idle 23 hours a day.

## Many bursts, one smooth load

Single workloads are bursty: idle for long stretches, then suddenly demanding. Independent workloads do not burst together. Layered by the million, the peak-to-mean ratio collapses and demand becomes predictable. So we spread each customer over far more drives than its bytes need. Tens of thousands of customers have data spread across over a million drives each. The lab's hour runs on spindles that other customers are not using at that moment.

Data cools as it ages, so a fleet left alone drifts cold. We keep moving data to balance heat. A new rack holds about a thousand drives. We first fill it to about 80% with older, cooler data. Fresh writes alone would melt it.

## Placing a write

When the lab writes an object, we pick a random set of drives. The next write, even to the same key, gets a different set. This is shuffle sharding. A large customer escapes the limit of its own footprint. A small one escapes its noisy neighbors, because a hot object elsewhere probably lives on other drives.

Pure randomness has a cost. In our simulation it left some drives 10 to 20% less full than others. So we pick two drives at random and use the less full one. The result is very close to perfect, without looking at tens of millions of drives.

The same idea guards the front door. A DNS lookup returns eight IPs, each pointing to a different set of stateless servers. Two customers resolving the same bucket get different sets. If one server fails, the SDKs retry against a different IP.

Per partitioned prefix, the lab gets at least 3,500 writes or 5,500 reads a second. There is no limit on prefixes, so ten prefixes could reach 55,000 reads a second. Scaling is gradual. While it happens, the lab may see some 503 Slow Down errors.

## Shards and parity

Three copies of an object survive failures but store three bytes for every byte. Erasure coding does better. In one illustration, the lab's object is cut into five shards, and four parity shards are computed. Any five of the nine rebuild the object. Three go to each of three Availability Zones. Any four drives can fail, or a whole zone, and the object survives. The cost is 1.8 bytes stored per byte. Replication would need five copies to survive the same four failures.

Reads gain as well. If one shard is slow, we read another. Our Common Runtime library goes further. It tracks request latency and cancels any request slower than, say, the 95th percentile, then retries it. The retry probably reaches different hosts and drives, and is usually fast. This is a bet, and it does not always pay off.

## Failure as a tool

Once the system tolerates failure, the cause matters less. A broken cable and a software bug cost the same shard. So we ship new software and hardware to a small footprint, expecting them to fail. There is a catch, the birthday paradox. Among enough objects, the unlikely is certain: some object would land too many shards on the new drives. So placement allows each object only one shard on new hardware. ShardStore, the storage software on our drives, rolled out this way. It started at one shard per object, then two, then three, then a zone, then everywhere.

We also scan every stored byte for integrity, all the time. If any byte goes too long unscanned, an engineer gets paged.

## Checking the code

ShardStore is over 40,000 lines of Rust. Next to it sit reference models: small executable specifications, about 1% of the code. A hash map stands in for the LSM tree. Property-based tests run random sequences of operations, including crashes, against both, and the two must agree. Model checkers explore thread interleavings. We run tens of millions of random sequences before every deployment.

These checks kept 16 issues out of production. One of them needed three things at once:

- a random UUID whose lost bytes matched the chunk's magic header,
- a chunk just large enough to spill onto a second page,
- a crash that lost only that page.

Engineers with no prior formal methods experience now update the models. Changes that could affect durability also get a durability review: a threat model listing what could go wrong and how the change resists it.

## Consistency

Until December 2020, the caches in our metadata layer meant that, in rare cases, a read could return an older version of an object. Now a witness component is told of every write and acts as a read barrier. If the cache is stale, the read goes to the persistence tier. When the lab writes a result and lists its bucket, the object is there. When it reads the object back, it gets the new data. We announced this at no extra cost and with no performance impact. Proving it correct took more work than building it.

There are limits:

- Updates to a single key are atomic.
- If two PUTs to one key arrive at once, the latest timestamp wins.
- No update spans keys atomically.
- Bucket configuration is eventually consistent.

## People

S3 is hundreds of microservices, and each is owned by its own team. The teams deal with each other through API-level contracts. The system is software, hardware, and the people who run it, and it keeps changing.
