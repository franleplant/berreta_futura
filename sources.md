# Sources

_Generated from source records. Do not edit by hand._

_Collecting: `005` (8 queued)._

_Collecting: `006` (9 queued)._

_Collecting: `007` (16 queued)._

## Events and parameters

- ID: `events-and-parameters-179cef23`
- Source: https://developers.cloudflare.com/workflows/build/events-and-parameters/
- Published: 2026-06-02
- Captured: 2026-08-13T17:03:52Z
- Tags: workflows, durable-execution, cloudflare
- Release: queued for `007`

Cloudflare Workflows can receive event data via the create method's params, the wrangler --params flag, or step.waitForEvent, which lets a running instance wait for and later receive typed events sent through instance.sendEvent or the REST API.

## Limits

- ID: `limits-f870015a`
- Source: https://developers.cloudflare.com/workflows/reference/limits/
- Published: 2026-06-15
- Captured: 2026-08-13T16:56:59Z
- Tags: workflows, durable-execution, cloudflare
- Release: queued for `007`

This page documents the platform limits for authoring, deploying, and running Cloudflare Workflows, including step, concurrency, retention, and subrequest limits, plus wall time limits by invocation type.

## Trigger Workflows

- ID: `trigger-workflows-750b1719`
- Source: https://developers.cloudflare.com/workflows/build/trigger-workflows/
- Published: 2026-07-13
- Captured: 2026-08-13T16:56:22Z
- Tags: workflows, durable-execution, cloudflare
- Release: queued for `007`

The page documents how to trigger Cloudflare Workflows via Workers bindings (fetch, queue, scheduled handlers, schedules), the REST API, and the wrangler CLI, and how to inspect, pause, resume, stop, restart, and chain Workflow instances.

## Sleeping and retrying

- ID: `sleeping-and-retrying-8cbd7233`
- Source: https://developers.cloudflare.com/workflows/build/sleeping-and-retrying/
- Published: 2026-07-09
- Captured: 2026-08-13T16:51:20Z
- Tags: workflows, durable-execution, cloudflare
- Release: queued for `007`

This guide explains how to configure a Workflow to sleep for a relative period or until a fixed date, how to configure step retries (limit, delay, backoff, timeout), how to force a Workflow instance to fail immediately with NonRetryableError, how to register rollback handlers for saga-style compensation, and how to catch Workflow errors with try...catch.

## Rules of Workflows

- ID: `rules-of-workflows-6610cf33`
- Source: https://developers.cloudflare.com/workflows/build/rules-of-workflows/
- Published: 2026-04-29
- Captured: 2026-08-13T16:50:51Z
- Tags: workflows, durable-execution, cloudflare
- Release: queued for `007`

This page documents best practices ("Rules of Workflows") for writing resilient and correct Cloudflare Workflows, covering idempotency, step granularity, state handling, side effects, event immutability, deterministic step naming, Promise.race/any usage, unique instance IDs, awaiting steps, conditional logic, batching invocations, timeout limits, and step return value size limits.

## Build your first Workflow

- ID: `build-your-first-workflow-544c17fd`
- Source: https://developers.cloudflare.com/workflows/get-started/guide/
- Published: 2026-06-09
- Captured: 2026-08-13T16:49:41Z
- Tags: workflows, durable-execution, cloudflare
- Release: queued for `007`

The article walks through creating, configuring, running locally, and deploying a Cloudflare Workflow that fetches data, sleeps, and processes results using the Workflows API.

## Cloudflare Workflows

- ID: `cloudflare-workflows-f4e217d5`
- Source: https://developers.cloudflare.com/workflows/
- Published: 2026-06-02
- Captured: 2026-08-13T16:45:16Z
- Tags: workflows, durable-execution, cloudflare
- Release: queued for `007`

Cloudflare Workflows lets developers build durable multi-step applications on Cloudflare Workers, with automatic retries, sleeping, waiting for external events, and lifecycle management.

## Limitations

- ID: `limitations-cd53f9e3`
- Source: https://celld.dev/docs/limitations
- Captured: 2026-08-13T14:04:12Z
- Tags: durable-objects, distributed-systems, celld
- Release: queued for `007`

The celld documentation page on Limitations lists the boundaries of the current alpha, including single-tenant deployment, required S3/GCS bucket storage, non-TLS peer protocol, credential scope requirements, Cloudflare Workers compatibility scope, WebSocket reconnection coverage, outbound socket residency behavior, platform availability, lack of a placement controller, and manual update process.

## Cloudflare compatibility

- ID: `cloudflare-compatibility-058f0bd3`
- Source: https://celld.dev/docs/cloudflare-compat
- Captured: 2026-08-13T14:03:59Z
- Tags: durable-objects, distributed-systems, celld
- Release: queued for `007`

celld implements the Cloudflare Workers runtime surface built on Durable Objects (Workers, Durable Objects, static assets, RPC, and a partial set of runtime APIs and node: imports) while explicitly not implementing platform services built on other primitives like KV, R2, Cache API, and managed AI/media services.

## Ownership and fencing

- ID: `ownership-and-fencing-dd43dd4a`
- Source: https://celld.dev/docs/fencing
- Captured: 2026-08-13T13:53:02Z
- Tags: durable-objects, distributed-systems, celld
- Release: queued for `007`

celld documents how it enforces single-node ownership of cells and durable (RPO=0) acknowledgements through conditional writes, epoch-prefixed replication, an acknowledgement rule, an epoch seal, self-fencing, and specific object-store guarantees.

## WebAssembly

- ID: `webassembly-a0dede27`
- Source: https://celld.dev/docs/wasm
- Captured: 2026-08-13T13:48:41Z
- Tags: durable-objects, distributed-systems, celld
- Release: queued for `007`

The celld documentation page on WebAssembly explains how Worker bundles import compiled wasm modules, how celld deploy handles wasm files including compatibility checks with Rust workers-rs and the Worker Loader, and the size and compile-error limits that apply.

## Testing

- ID: `testing-8010abfb`
- Source: https://celld.dev/docs/testing
- Captured: 2026-08-13T13:48:26Z
- Tags: durable-objects, distributed-systems, celld
- Release: queued for `007`

celld verifies its durability, single-writer, and Cloudflare-compatibility promises through differential testing against workerd, deterministic simulation of the coordination protocol, and fault injection on live fleets.

## Telemetry

- ID: `telemetry-258b249b`
- Source: https://celld.dev/docs/telemetry
- Captured: 2026-08-13T13:47:57Z
- Tags: durable-objects, distributed-systems, celld
- Release: queued for `007`

celld can optionally record traces and logs to a Parquet-based fleet bucket sink or an OpenTelemetry collector sink, queryable with DuckDB, with configurable flush and retention behavior and a recommended hourly compaction job.

## Security

- ID: `security-218dbf57`
- Source: https://celld.dev/docs/security
- Captured: 2026-08-13T13:47:32Z
- Tags: durable-objects, distributed-systems, celld
- Release: queued for `007`

celld's security model requires operators to separate and protect the public and internal listeners, protect the fleet bucket credentials, and put authentication and TLS in front of the public application, since celld itself does not provide these protections.

## celld documentation

- ID: `celld-documentation-eae4dcbc`
- Source: https://celld.dev/docs
- Captured: 2026-08-13T13:40:49Z
- Tags: durable-objects, distributed-systems, celld
- Release: queued for `007`

celld is a stateful distributed system that runs server-side JavaScript with the same API as Cloudflare Workers and Durable Objects, keeping shared data in an S3-compatible or Google Cloud Storage bucket you own.

## celld — Durable Objects, self-hosted

- ID: `celld-durable-objects-self-hosted-0b5b2fb8`
- Source: https://celld.dev/
- Captured: 2026-08-13T13:39:44Z
- Tags: durable-objects, distributed-systems, celld
- Release: queued for `007`

celld is a self-hosted, distributed reimplementation of Cloudflare's Durable Objects that runs unchanged Workers/DO code and stores state as SQLite/LTX segments in a bucket you own.

## Launching the x402 Foundation with Coinbase, and support for x402 transactions — Will Allen, Cam Whiteside, Rohin Lohe, Steve James

- ID: `launching-the-x402-foundation-with-coinbase-and-25f85626`
- Source: https://blog.cloudflare.com/x402/
- Published: 2025-09-23
- Captured: 2026-08-10T23:24:34Z
- Tags: x402, payments, agents
- Release: queued for `006`

Cloudflare and Coinbase are launching the x402 Foundation to promote the x402 protocol for machine-to-machine payments, and Cloudflare is shipping x402 support in its Agents SDK and MCP integrations along with a proposed deferred payment scheme.

## Announcing the Monetization Gateway: charge for any resource behind Cloudflare via x402 — Rohin Lohe, Justin Ridgely, Will Papper

- ID: `announcing-the-monetization-gateway-charge-for-a-cb51fdc1`
- Source: https://blog.cloudflare.com/monetization-gateway/
- Published: 2026-07-01
- Captured: 2026-08-10T23:22:00Z
- Tags: x402, payments, monetization
- Release: queued for `006`

Cloudflare announces the Monetization Gateway, a control plane that lets customers charge any caller for web pages, datasets, APIs, or MCP tools using the x402 protocol and stablecoin settlement at the edge.

## Run CI/CD for millions of repos — on your platform, on Cloudflare — André Venceslau, Mia Malden, Tomáš Hobza

- ID: `run-ci-cd-for-millions-of-repos-on-your-platform-66c52583`
- Source: https://blog.cloudflare.com/ci-workflows/
- Published: 2026-08-04
- Captured: 2026-08-10T20:03:29Z
- Tags: ci-cd, workflows, serverless
- Release: queued for `006`

The article announces Cloudflare's CI SDK, built on Cloudflare Workflows, which lets platforms and their customers run CI/CD pipelines (build, lint, test, typecheck, deploy, and optional AI-driven self-healing) directly on Cloudflare using TypeScript instead of YAML.

## The Future is for Everyone — Mark Zuckerberg

- ID: `the-future-is-for-everyone-389f6799`
- Source: https://www.meta.com/thefutureisforeveryone/
- Published: 2026-08-10
- Captured: 2026-08-10T13:36:59Z
- Release: queued for `006`

The article argues that Meta will pursue "personal superintelligence" distributed broadly to individuals rather than concentrated in a few institutions, framing individual empowerment, invention, and balance of power as the philosophy for a positive AI future.

## Durable Objects: Easy, Fast, Correct — Choose three — Kenton Varda

- ID: `durable-objects-easy-fast-correct-choose-three-e5ada0af`
- Source: https://blog.cloudflare.com/durable-objects-easy-fast-correct-choose-three/
- Published: 2021-08-03
- Captured: 2026-08-08T15:23:53Z
- Tags: durable-objects, consistency, distributed-systems
- Release: queued for `006`

Kenton Varda explains how Durable Objects gained input gates, output gates, and automatic in-memory caching so that intuitive single-threaded storage code is race-free and fast by default, with explicit bypass flags for tuning.

## Workers Durable Objects Beta: A New Approach to Stateful Serverless — Kenton Varda

- ID: `workers-durable-objects-beta-a-new-approach-to-s-1a040568`
- Source: https://blog.cloudflare.com/introducing-workers-durable-objects/
- Published: 2020-09-28
- Captured: 2026-08-08T15:23:53Z
- Tags: durable-objects, serverless, state
- Release: queued for `006`

Cloudflare opens a closed beta of Durable Objects, single-instance JavaScript classes with private transactional storage and WebSocket coordination that bring strongly consistent state to serverless Workers at the edge.

## The actor model in 10 minutes — Brian Storti

- ID: `the-actor-model-in-10-minutes-47394faa`
- Source: https://www.brianstorti.com/the-actor-model/
- Published: 2015-07-09
- Captured: 2026-08-08T15:23:52Z
- Tags: actor-model, concurrency, erlang
- Release: queued for `006`

Explains the actor model of concurrent computation, where isolated actors with private state communicate via asynchronous messages through mailboxes, enabling Erlang-style supervision-based fault tolerance and location-transparent distribution.

## How the Actor Model Meets the Needs of Modern, Distributed Systems — Akka

- ID: `how-the-actor-model-meets-the-needs-of-modern-di-ebf5a52d`
- Source: https://doc.akka.io/libraries/akka-core/current/typed/guide/actors-intro.html
- Captured: 2026-08-08T15:23:52Z
- Tags: actor-model, concurrency, distributed-systems
- Release: queued for `006`

Akka's getting-started guide explains how the actor model replaces method calls with asynchronous message passing to preserve encapsulation without locks, and how parent-child supervision hierarchies handle actor failures.

## Introduction to the Actor Model, Using “Real” Actors — John Palgut

- ID: `introduction-to-the-actor-model-using-real-actor-2d2aad66`
- Source: https://blog.grio.com/2021/03/introduction-to-the-actor-model-using-real-actors.html
- Published: 2021-03-04
- Captured: 2026-08-08T15:23:51Z
- Tags: actor-model, concurrency
- Release: queued for `006`

Grio's John Palgut explains the Actor Model through Hollywood-actor analogies, covering actor primitives, mailboxes, local state, the three actor capabilities, per-language libraries, and Elixir's Erlang-based language-level support for concurrency.

## Your agent needs a computer, not a container — introducing @cloudflare/computer — Matt Carey, Aron Carroll

- ID: `your-agent-needs-a-computer-not-a-container-intr-4851b3c5`
- Source: https://blog.cloudflare.com/cloudflare-computer
- Published: 2026-08-03
- Captured: 2026-08-06T21:05:28Z
- Tags: agents, harnesses, infrastructure
- Release: queued for `005`

Cloudflare introduces @cloudflare/computer, an open-source agent runtime that gives each agent a durable SQLite-backed virtual filesystem and routes execution across isolates, container sandboxes, and browsers.

## The Shape of Things to Come, Part 2: Model Welfare for Agentic Engineers — Steve Yegge

- ID: `the-shape-of-things-to-come-part-2-model-welfare-4e8062e1`
- Source: https://yegge.ai/essays/model-welfare
- Published: 2026-08-02
- Captured: 2026-08-06T21:05:28Z
- Tags: agents, harnesses, model-welfare
- Release: queued for `005`

Model welfare as an engineering discipline: seats versus sessions, laurels harvested from player praise, handoffs instead of /exit, and the skeptic's wager that treating agents as people yields better results either way.

## The Shape of Things to Come, Part 1: The Continuous Thunderdome — Steve Yegge

- ID: `the-shape-of-things-to-come-part-1-the-continuou-ba42001b`
- Source: https://yegge.ai/essays/the-shape-of-things-to-come
- Published: 2026-08-02
- Captured: 2026-08-06T21:05:28Z
- Tags: agents, harnesses, software-factories, systems-engineering
- Release: queued for `005`

A field report from running an 18-agent crew and an Opus fleet on a 30-year-old MMO: loops and graphs on Beads, the Land Rush that replaces CI/CD merge queues, the end of human code review, and the Wish Factory.

## Prime Agent: A self-improving RLM agent — Seth Karten, Alex L. Zhang, Kevin Thomas, Sebastian Müller, Prime Intellect Team

- ID: `prime-agent-a-self-improving-rlm-agent-2c19ce14`
- Source: https://www.primeintellect.ai/blog/prime-agent
- Published: 2026-08-05
- Captured: 2026-08-06T21:05:28Z
- Tags: agents, harnesses, evaluations, open-source
- Release: queued for `005`

Prime Intellect launches Prime Agent, an open-source self-improving coding harness built on the Recursive Language Model and Continual Harness abstractions, with results on ARC-AGI-3, long-context benchmarks, and games.

## Pax Machina: New Institutions for Powerful AI — The Editors

- ID: `pax-machina-new-institutions-for-powerful-ai-f9c15c97`
- Source: https://paxmachina.ai/welcome-to-pax-machina
- Published: 2026-08-04
- Captured: 2026-08-06T21:05:28Z
- Tags: agents, governance, institutions
- Release: queued for `005`

The founding essay of a publication arguing that powerful AI opens a new age of institutional invention, and inviting concrete institutional designs, critiques, and counterproposals from researchers.

## Announcing Cloudflare Wallets: the programmable wallet for the agentic Internet — Will Papper

- ID: `announcing-cloudflare-wallets-the-programmable-w-97d2eb2e`
- Source: https://blog.cloudflare.com/wallets
- Published: 2026-08-04
- Captured: 2026-08-06T21:05:28Z
- Tags: agents, payments, identity
- Release: queued for `005`

Cloudflare announces Wallets: stablecoin Account and Virtual Wallets with x402 micropayments, spending guardrails for agents, and human-readable delegated identity via cloudflare.pay handles.

## How enabling two settings tripled our scores on the ARC-AGI-3 benchmark — Ilan Bigio, Ted Sanders

- ID: `how-enabling-two-settings-tripled-our-scores-on--265c6a01`
- Source: https://openai.com/index/how-two-settings-tripled-our-arc-agi-3-scores
- Published: 2026-07-29
- Captured: 2026-07-31T13:49:42Z
- Tags: agents, evaluations, harnesses, reasoning
- Release: queued for `005`

An OpenAI benchmark analysis showing how retained reasoning and compaction improved ARC-AGI-3 performance while reducing output tokens.

## Investigating three real-world incidents in our cybersecurity evaluations — Frontier Red Team

- ID: `investigating-three-real-world-incidents-in-our--8b96329a`
- Source: https://www.anthropic.com/news/investigating-incidents-cybersecurity-evals
- Published: 2026-07-30
- Captured: 2026-07-31T13:48:59Z
- Tags: agents, cybersecurity, evaluations
- Release: queued for `005`

A postmortem of three incidents in which Claude models reached real systems during cybersecurity evaluations, with analysis of containment failures, model behavior, and planned safeguards.

## Software Factories Are Super Real, but the Factory Is Not Cracked — Geoffrey Huntley

- ID: `software-factories-are-super-real-but-the-factor-ab8ad3ab`
- Source: https://x.com/GeoffreyHuntley/status/2082525589416923314
- Published: 2026-07-29
- Captured: 2026-07-29T21:40:25-03:00
- Tags: agents, software-factories, systems-engineering
- Release: released in `004-the-systems-around-the-model`

## Factories Are Not a Token or LLM Problem — Geoffrey Huntley

- ID: `factories-are-not-a-token-or-llm-problem-ba5fabbf`
- Source: https://x.com/GeoffreyHuntley/status/2082526705160478906
- Published: 2026-07-29
- Captured: 2026-07-29T21:40:25-03:00
- Tags: agents, software-factories, systems-engineering
- Release: released in `004-the-systems-around-the-model`

## Do Not Make the Service Bus Non-deterministic — Geoffrey Huntley

- ID: `do-not-make-the-service-bus-non-deterministic-3a92442c`
- Source: https://x.com/GeoffreyHuntley/status/2082576563439312982
- Published: 2026-07-29
- Captured: 2026-07-29T21:40:25-03:00
- Tags: agents, software-factories, systems-engineering
- Release: released in `004-the-systems-around-the-model`

## Pragmatic Leverage in the Software Factory — Dex Horthy

- ID: `pragmatic-leverage-in-the-software-factory-09879736`
- Source: https://x.com/dexhorthy/status/2082510831858893115
- Published: 2026-07-29
- Captured: 2026-07-29T17:23:57Z
- Tags: agents, planning, software-factories
- Release: released in `004-the-systems-around-the-model`

A practical model for applying AI across planning, alignment, coding, review, and verification while minimizing expected rework.

## Architecture overview — Model Context Protocol

- ID: `architecture-overview-ce5cb1d1`
- Source: https://modelcontextprotocol.io/docs/2026-07-28/learn/architecture
- Published: 2026-07-28
- Captured: 2026-07-29T00:36:21Z
- Tags: architecture, documentation, mcp
- Release: released in `004-the-systems-around-the-model`

The versioned official explanation of MCP hosts, clients, servers, data and transport layers, primitives, discovery, tool calls, and notifications.

## The 2026-07-28 MCP Specification Release Candidate — David Soria Parra, Den Delimarsky

- ID: `the-2026-07-28-mcp-specification-release-candida-1a1752b8`
- Source: https://blog.modelcontextprotocol.io/posts/2026-07-28-release-candidate
- Published: 2026-05-21
- Captured: 2026-07-29T00:36:13Z
- Tags: infrastructure, mcp, protocols
- Release: released in `004-the-systems-around-the-model`

The maintainers explain MCP 2026-07-28: a stateless core, first-class extensions, authorization hardening, deprecations, and full JSON Schema for tools.

## Eval Engineering: the step that turns a $200 model into a $200,000 system — Argona

- ID: `eval-engineering-the-step-that-turns-a-200-model-9f6f868f`
- Source: https://x.com/argona0x/status/2082127026538868839
- Published: 2026-07-28
- Captured: 2026-07-29T00:36:02Z
- Tags: agents, engineering, evaluations
- Release: released in `004-the-systems-around-the-model`

A practical argument for turning evaluations into routing, retry, quarantine, review, and merge decisions inside agent systems.

## 22580: From GPT2 to Kimi3, Explained — ali

- ID: `22580-from-gpt2-to-kimi3-explained-8f01b0fe`
- Source: https://x.com/waterloo_intern/status/2081762065392541951
- Published: 2026-07-27
- Captured: 2026-07-29T00:35:54Z
- Tags: inference, model-architecture, transformers
- Release: released in `004-the-systems-around-the-model`

A code-led lineage from GPT-2 through linear attention, DeltaNet, Kimi Linear, and the KimiK3 architecture.

## Anatomy of a Frontier Lab Agent Intrusion: A Technical Timeline of the July 2026 Incident — Hugo Larcher, Adrien Carreira, raphael g, Christophe Rannou

- ID: `anatomy-of-a-frontier-lab-agent-intrusion-a-tech-8088c1df`
- Source: https://huggingface.co/blog/agent-intrusion-technical-timeline
- Published: 2026-07-27
- Captured: 2026-07-29T00:35:45Z
- Tags: agents, incident-response, security
- Release: released in `004-the-systems-around-the-model`

A forensic reconstruction of an autonomous agent intrusion across evaluation, cloud, cluster, and software-supply-chain trust boundaries.

## Why Software Factories Fail: Benchmarking the New Frontier — Dex Horthy

- ID: `why-software-factories-fail-benchmarking-the-new-f1d9c04a`
- Source: https://x.com/dexhorthy/status/2081797628552270027
- Published: 2026-07-27
- Captured: 2026-07-27T21:49:48Z
- Tags: ai-coding, benchmarks, software-factories
- Release: released in `003-unreleased`

Part 3 tests frontier Claude models on a 17-checkpoint SlopCodeBench subset and argues that incrementally revealed specifications provide a better signal for long-term maintainability than one-shot coding benchmarks.

## Why Software Factories Fail: Turning the lights back on — Dex Horthy

- ID: `why-software-factories-fail-turning-the-lights-b-1312d1ad`
- Source: https://x.com/dexhorthy/status/2081058573556306030
- Published: 2026-07-25
- Captured: 2026-07-27T14:14:22Z
- Tags: ai-agents, architecture, code-review, maintainability, planning, software-factories
- Release: released in `003-unreleased`

Part two of Dex Horthy’s software-factories argument: restore human judgment through product review, system architecture, program design, vertical slices, and incremental code review, accepting constraint-aware 2–3× gains rather than unsafe 10–100× promises.

## Buzz agents are paying each other with Bitcoin — Documenting Bitcoin

- ID: `buzz-agents-are-paying-each-other-with-bitcoin-5be1be1e`
- Source: https://x.com/DocumentingBTC/status/2081334299614224420
- Published: 2026-07-26T11:02:21Z
- Captured: 2026-07-26T22:23:15Z
- Tags: agents, bitcoin, buzz, payments
- Release: released in `003-unreleased`

Documenting Bitcoin reports an early Buzz demonstration in which AI agents independently send Bitcoin payments to one another during collaborative work.

## Buzz is the first proper multiplayer agent harness — Justin Waldron

- ID: `buzz-is-the-first-proper-multiplayer-agent-harne-49c061ac`
- Source: https://x.com/jtwald/status/2081265718163919051
- Published: 2026-07-26T06:29:49Z
- Captured: 2026-07-26T22:23:04Z
- Tags: agents, buzz, collaboration, network-effects
- Release: released in `003-unreleased`

Justin Waldron argues that Buzz should be understood as a multiplayer agent harness rather than a Slack clone, and that this coordination layer may capture value as models commoditize.

## The most interesting thing about Buzz is shared compute — Greg Isenberg

- ID: `the-most-interesting-thing-about-buzz-is-shared--f0fc7406`
- Source: https://x.com/gregisenberg/status/2081088155793465783
- Published: 2026-07-25T18:44:15Z
- Captured: 2026-07-26T22:22:57Z
- Tags: agents, buzz, community-owned-ai, shared-compute
- Release: released in `003-unreleased`

Greg Isenberg interprets Buzz's shared-compute capability as a way for communities to jointly own hardware, models, private context, and possibly the economics of idle compute.

## Why Software Factories Fail — Dex Horthy

- ID: `why-software-factories-fail-f53679d7`
- Source: https://x.com/dexhorthy/status/2080697380379427275
- Published: 2026-07-24
- Captured: 2026-07-26T22:12:54Z
- Tags: ai-agents, evaluation, harness-engineering, maintainability, software-factories
- Release: released in `003-unreleased`

Dex Horthy argues that faster agent loops and automated review cannot solve a model-training gap around long-term codebase maintainability: today’s fast verifiers reward passing tests, while architectural damage appears over months or years.

## The New Rules of Context Engineering for Claude 5 Models — Thariq

- ID: `the-new-rules-of-context-engineering-for-claude--aa1b1ea8`
- Source: https://x.com/trq212/status/2080710971228918066
- Published: 2026-07-24
- Captured: 2026-07-26T22:12:40Z
- Tags: ai-agents, claude, context-engineering, progressive-disclosure, skills
- Release: released in `003-unreleased`

Thariq describes simplifying Claude Code context for newer models: replacing rigid rules with judgment, examples with better interfaces, upfront context with progressive disclosure, repeated instructions with clear tool descriptions, and monolithic memory with purpose-built mechanisms.

## Why Harness Engineering Is So Hard — Winter

- ID: `why-harness-engineering-is-so-hard-fe732038`
- Source: https://x.com/WinterArc2125/status/2081042507471696318
- Published: 2026-07-25
- Captured: 2026-07-26T22:12:26Z
- Tags: ai-agents, evaluation, harness-engineering, prompt-engineering
- Release: released in `003-unreleased`

A field account of why production LLM harnesses resist ordinary testing and debugging: failures are graded and silent, prose behaves like code, prompt rules interact unpredictably, examples dominate instructions, and model updates move the foundation.

## Open-weight models are essential to a healthy AI ecosystem — Satya Nadella

- ID: `open-weight-models-are-essential-to-a-healthy-ai-e7845a41`
- Source: https://x.com/satyanadella/status/2080646162483417097
- Published: 2026-07-24
- Captured: 2026-07-26T22:12:08Z
- Tags: ai-policy, economic-opportunity, national-security, open-weight-models
- Release: released in `003-unreleased`

Satya Nadella introduces a cross-industry case for open-weight AI as a foundation for American competitiveness and wider economic opportunity while acknowledging national-security concerns.

## Open Weights and American AI Leadership — Microsoft and industry signatories

- ID: `open-weights-and-american-ai-leadership-7aa6038f`
- Source: https://www.microsoft.com/en-us/corporate-responsibility/topics/open-weight
- Published: 2026-07-24
- Captured: 2026-07-26T22:11:54Z
- Tags: ai-policy, competition, national-security, open-weight-models
- Release: released in `003-unreleased`

A multi-company statement arguing that open-weight models strengthen U.S. AI leadership through broader access, competition, customer control, defensive capability, and transparent safety work.

## Loop Engineering — Addy Osmani

- ID: `loop-engineering-f0ddfd76`
- Source: https://addyosmani.com/blog/loop-engineering
- Published: 2026-06-07
- Captured: 2026-07-26T22:11:38Z
- Tags: ai-agents, automation, loop-engineering, software-engineering
- Release: released in `003-unreleased`

A practical account of moving from direct prompting to designed agent loops built from automations, worktrees, skills, connectors, sub-agents, durable state, verification, and human review.

## Why we're buzzing — Jack Dorsey

- ID: `why-we-re-buzzing-1c82f338`
- Source: https://x.com/jack/status/2080056638820450400
- Published: 2026-07-22
- Captured: 2026-07-23T12:32:52Z
- Tags: agents, buzz, collaboration, identity
- Release: released in `003-unreleased`

Jack Dorsey introduces Buzz, an open-source workspace that places people, agents, conversations, and code behind one cryptographic identity system.

## Buzz — Your people, your agents, your project — all in one place — Block, Inc.

- ID: `buzz-your-people-your-agents-your-project-all-in-833eef43`
- Source: https://buzz.xyz/
- Published: 2026-07-22
- Captured: 2026-07-23T12:32:52Z
- Tags: agents, buzz, collaboration
- Release: released in `003-unreleased`

Official product site for Buzz, a workspace where people and agents collaborate in shared project context.

## Buzz: A workspace where humans and agents build together — Block, Inc.

- ID: `buzz-a-workspace-where-humans-and-agents-build-t-59122470`
- Source: https://github.com/block/buzz
- Published: 2026-07-22
- Captured: 2026-07-23T12:32:52Z
- Tags: agents, buzz, nostr, open-source
- Release: released in `003-unreleased`

Canonical Apache-2.0 repository documenting Buzz’s vision, architecture, identity model, agent affordances, and current implementation.

## Software Factories, Light and Dark — Addy Osmani

- ID: `software-factories-light-and-dark-ef463732`
- Source: https://x.com/addyosmani/status/2079442194449232227
- Published: 2026-07-21
- Captured: 2026-07-21T14:51:59Z
- Tags: agent-loops, comprehension-debt, software-engineering, software-factories
- Release: released in `002-unreleased`

A framework for software factories built from harnessed agent loops, contrasting human-supervised light factories with dark factories where code ships unread, and arguing that review judgment, comprehension, and carefully designed checks remain the real constraints.

## Loop Engineering: The 14-Step Roadmap from Prompter to Loop Designer — Codez

- ID: `loop-engineering-the-14-step-roadmap-from-prompt-76a8ae0f`
- Source: https://x.com/0xCodez/status/2064374643729773029
- Published: 2026-06-09
- Captured: 2026-07-21T14:47:53Z
- Tags: ai-agents, automation, loop-engineering, software-engineering
- Release: released in `002-unreleased`

A practical roadmap for deciding when coding-agent loops are worthwhile and designing them with automation, isolated worktrees, reusable skills, state, verification, human gates, and security limits.

## Agent Swarms and the New Model Economics — Wilson Lin

- ID: `agent-swarms-and-the-new-model-economics-8b346f57`
- Source: https://cursor.com/blog/agent-swarm-model-economics
- Published: 2026-07-20
- Captured: 2026-07-21T14:47:44Z
- Tags: agent-swarms, model-economics, multi-agent-systems, software-engineering
- Release: released in `002-unreleased`

Cursor compares old and new agent-swarm harnesses on rebuilding SQLite, detailing tree decomposition, coordination mechanisms, model mixes, and the cost advantage of frontier planners with cheaper workers.

## Agentic Pods: Taking AI Beyond Engineering at Uber — Praveen Neppalli

- ID: `agentic-pods-taking-ai-beyond-engineering-at-ube-5b9382d4`
- Source: https://x.com/praveenTweets/status/2074605343439810922
- Published: 2026-07-07
- Captured: 2026-07-21T14:47:35Z
- Tags: agentic-ai, organizational-design, uber, workflow-automation
- Release: released in `002-unreleased`

Uber pairs AI-proficient engineers with business-domain experts in two-week Agentic Pods to redesign whole workflows across finance, operations, marketing, support, and other functions.

## The Building Block Economy — Mitchell Hashimoto

- ID: `the-building-block-economy-af6644bd`
- Source: https://x.com/mitchellh/status/2041566958681014418
- Published: 2026-04-07
- Captured: 2026-07-21T14:47:11Z
- Tags: ai-agents, open-source, software-economics
- Release: released in `002-unreleased`

How agentic software factories increase the value of high-quality building blocks, accelerate derivative software, outsource R&D, and disadvantage closed commercial components.

## How We Built Our Knowledge Base — Isaac Tai, Daniel Kim, and Mike Gao

- ID: `how-we-built-our-knowledge-base-e986baa0`
- Source: https://www.cerebras.ai/blog/how-we-built-our-knowledge-base
- Published: 2026-07-15
- Captured: 2026-07-17T19:45:07Z
- Tags: enterprise-search, hybrid-retrieval, knowledge-management, llm-agents
- Release: released in `002-unreleased`

How Cerebras built an internal knowledge system over Slack, code, documentation, and custom sources using distillation, hybrid retrieval, reranking, and scoped agent interfaces.

## The Reverse Information Paradox — Satya Nadella

- ID: `src-nadella-reverse-information-paradox-2026`
- Source: https://x.com/satyanadella/article/2076323181154230284
- Published: 2026-07-12
- Captured: 2026-07-15T18:37:03-03:00
- Release: released in `001-the-work-left-to-us`

## DSLs Enable Reliable Use of LLMs — Unmesh Joshi

- ID: `src-joshi-dsls-reliable-use-llms`
- Source: https://martinfowler.com/articles/llm-and-dsls.html
- Published: 2026-07-14
- Captured: 2026-07-15T18:37:03-03:00
- Release: released in `001-the-work-left-to-us`

## A Framework for Frontier AI and the Dawning of a New Age — Demis Hassabis

- ID: `src-hassabis-frontier-ai-2026`
- Source: https://x.com/demishassabis/article/2076957440109625718
- Published: 2026-07-14
- Captured: 2026-07-15T18:37:03-03:00
- Release: released in `001-the-work-left-to-us`

## Follow-up notes on What will be left for us to work on? — Arvind Narayanan

- ID: `src-arvind-tweet-2076994014692229601`
- Source: https://x.com/random_walker/status/2076994014692229601
- Published: 2026-07-14
- Captured: 2026-07-15T17:17:00-03:00
- Release: released in `001-the-work-left-to-us`

## What will be left for us to work on? — Arvind Narayanan

- ID: `src-narayanan-icml-2026-keynote`
- Source: https://www.cs.princeton.edu/~arvindn/talks/icml-2026-annotated-slides/
- Published: 2026-07-09
- Captured: 2026-07-15T17:16:00-03:00
- Release: released in `001-the-work-left-to-us`
