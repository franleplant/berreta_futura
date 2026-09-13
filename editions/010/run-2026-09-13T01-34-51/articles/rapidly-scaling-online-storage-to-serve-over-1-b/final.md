---
source_ids:
- rapidly-scaling-online-storage-to-serve-over-1-b-9132274d
content_mode: article
label: ARTICLE
---

Habitat is our online storage platform: more than 70 million requests a second, more than 1 billion people a week, 500 petabytes, across almost 40 regions. It began at DevDay 2023 as a small Python library over Azure Cosmos DB. Coordinating client changes across dozens of services became brittle, so we pulled it into a service, kept Python as deliberate debt, and spent our attention on tail latency: asyncio scheduling delay, a config parsed every minute on the minute, a connection pool that fed its own overload. In Q2 2026, two engineers with Codex and GPT‑5.5 rewrote the whole thing in Rust.

## Why we grew this way

Building at this scale is no easy feat, but also not particularly challenging. What was unusual was the rate: more than 10x year over year for three years. So Habitat has been a sequence of tactical decisions, squeezing the existing stack while fending off capacity crunches to buy time for foundational work.

## From library to service

By mid‑2025 the client-side design had reached its limit. To reduce the blast radius of a regional outage, we wanted to move critical data onto regionally distributed Cosmos DB accounts. That meant routing logic in the client, behind a flag, rolled out everywhere. Days. Then shadowing to check the sharding: another couple of days. A bug fix: another couple. When we finally enabled the flag, one team rolled back to an older buggy client and caused the outage we had worked to avoid.

A service gave us one point of control for deployments, observability, and enhancements, and one chokepoint for access control, audit logging, and limiting access to the storage underneath.

## Python, knowingly

Python as a service cost us latency, CPU, and memory, and we knew its inefficiencies wouldn't hold at 100x, making an eventual rewrite almost certain. We took it as a strategic incursion of technical debt: unblock product developers, settle the core APIs. We also wagered our own coding models would make the migration achievable by the time we needed it. That bet proved correct.

When the average user request results in hundreds of database calls, the slowest database call is the one the user feels.

## Where the tail lived

Asyncio gives concurrency, not parallelism, and Habitat does CPU work: routing, compression, encryption, checksumming, health checks, shadowing, hedging. We measure event loop delay directly, by scheduling background tasks and recording the gap between expected and actual execution. Under load it reached hundreds of milliseconds, sometimes seconds. So each process serves few concurrent requests and we scale out processes instead.

CPU profiling found one cause: Statsig polling a config containing every production rule across every service, every minute, without jitter, on up to 8 processes per pod. Every minute, every worker stopped serving and parsed a giant file. We shipped a smaller config, a longer interval, and jitter.

Another: aiohttp's TCPConnector reuses connections LIFO. Slow, overloaded servers returned connections later, so they were picked more often, and traffic concentrated on the pods already struggling. A metastable failure. FIFO reuse broke the loop and cut steady-state variance too. Today Istio and Envoy handle pooling and load-aware balancing, and Envoy upgrades our HTTP/1 to HTTP/2, extends connection lifetimes, and holds our rate limits and circuit breakers.

## Habitat does less

Clients get a simple NoSQL API, not SQL. It is cheap and easy to write queries that are expensive and hard to run; on Postgres, one new query on a hot path took out the database often enough. Habitat has no unbounded queries, and complex joins push work back to product teams.

The API is modeled on client-defined objects and edges, inspired by TAO. Each object sits with its edges in one partition, but not with the objects its edges point to: the shape resembles a graph and declines to be walked, since a single hop may cross accounts in different regions. For complex querying we stream changes by CDC into per-team Rockset instances. That friction is, we think, the right tradeoff at this particular moment.

## Rust

Deferring the rewrite for a year let us spend that year elsewhere. At its peak Python served more than 20 million requests a second. The Rust service now takes 95% of production traffic, at 6x the CPU efficiency and 15x the memory efficiency, with lower average and tail latencies; Python goes away in the coming weeks. The storage layer is part II.
