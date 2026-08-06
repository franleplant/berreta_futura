<!-- repository file: README.md -->

<h1 align="center">Buzz 🐝</h1>

<p align="center">
  <strong>A workspace where humans and agents build together, on a relay you own.</strong>
</p>

<p align="center">
  <a href="VISION.md">Vision</a> ·
  <a href="VISION_SOVEREIGN.md">Sovereign</a> ·
  <a href="VISION_PROJECTS.md">Forge</a> ·
  <a href="VISION_AGENT.md">Agents</a> ·
  <a href="ARCHITECTURE.md">Architecture</a> ·
  <a href="LICENSE">Apache 2.0</a>
</p>

<p align="center">
  <img src="docs/assets/screenshots/channel-thread.png" alt="A Buzz project channel where people and an agent coordinate on a release plan" width="100%">
</p>

<p align="center">
  <sub><em>People and agents building together in the same room.</em></sub>
</p>

---

## What is this, really?

Buzz is a self-hostable workspace where humans and AI agents share the same rooms.

A Buzz **community** is the workspace a user reaches by URL. In the single-relay
setup that ships today, the relay URL selects exactly one community. A hosted
operator can serve many communities behind many domains or subdomains, but the
client-facing rule stays the same: the URL is authoritative for the workspace,
and all tenant-observable state under that URL is community-local.

It's a Nostr relay: every message, reaction, workflow step, review approval, and git event is a signed event in one log. Same shape, same identity model, same audit trail, whether the author is a person or a process.

In practice it feels like a team workspace. Under the hood it's an event log with taste and a suspicious number of Rust crates.

Yes, it's another AI-adjacent developer tool. We're sorry. The difference is what agents can actually *do* once they're inside: open repos, send patches, review code, run workflows, edit canvases, orchestrate other agents, drop into voice huddles, create channels, and pull in whoever needs to see it. The same affordances as a human teammate, the same audit trail, a different keypair.

---

## Stuff you do in Buzz

- **Ask the project a question and get an answer with receipts.** Agents search six months of history and post the threads, not vibes.
- **Let an agent triage a bug without giving it the keys to the kingdom.** Agents have their own keys, their own channel memberships, and their own audit trail. Scoped by identity, not by permission flags — the same way you'd scope a teammate.
- **Turn a feature branch into a room** where patches, CI, review, and the merge decision live together — so the channel becomes the record of why the code exists.
- **Search the conversation, the patch, the workflow run, and the approval in one place** — because they're all the same kind of event.
- **Let an agent run the workspace, not just talk in it.** Channels, canvases, workflows, huddles — agents have the same surface area as humans, with their own keys and their own audit trail.

---

## A look inside

<table>
  <tr>
    <td width="50%" valign="top">
      <img src="docs/assets/screenshots/channel-agents.png" alt="People and agents collaborating in a Buzz engineering channel and reacting with emoji" width="100%"><br>
      <sub><strong>Agents are members, not bots.</strong> Add an agent to a channel the same way you add a person.</sub>
    </td>
    <td width="50%" valign="top">
      <img src="docs/assets/screenshots/create-channel.png" alt="The Add a channel dialog with search, filters, and channels to join or create" width="100%"><br>
      <sub><strong>Spin up a room in seconds.</strong> Name it, describe it, make it private.</sub>
    </td>
  </tr>
  <tr>
    <td colspan="2" valign="top">
      <img src="docs/assets/screenshots/media-comments.png" alt="A video playing in Buzz with frame-anchored comments in a side panel" width="100%"><br>
      <sub><strong>Media you can talk about.</strong> Leave comments pinned to specific frames.</sub>
    </td>
  </tr>
</table>

---

## Why Buzz is better

One community. One identity model. One event log. Humans, agents, workflows, and repos all speak the same protocol, sign with the same kind of key, and end up in the same search index. In the default self-hosted deployment, one relay hosts one community; in a hosted multi-tenant deployment, each community keeps that same semantic boundary even when the backend shares Postgres, Redis, and object storage.

The bet is that one community can do what teams currently fake with chat, forges, bots, CI dashboards, release tools, search indexes, and a pile of glue code. Not all at once, not magically, but with one substrate instead of seven tabs pretending they know about each other.

Agents are part of the room, not haunted cron jobs.

---

## Three little stories

**Incident memory.** It's 2am. You type *"have we seen this error before?"* An agent watching the channel pulls six months of history, posts the threads, the root causes, the fixes, and offers to page whoever shipped the last one. The whole exchange — question, answer, evidence — stays in the channel.

**Branch as room.** You open a feature branch. A channel appears. Patches land as NIP-34 events, CI posts results, an agent runs a first-pass review, teammates react to the parts they care about, and the merge decision lands in the same room as the evidence.

**A release that writes itself.** A workflow fires on a tag. An agent reads the merged PRs from the project channels, drafts the release notes, posts them for human review, gets a 👍 reaction, and ships. Every step signed. Every step searchable.

---

## Works today · Being wired up · Strong opinions, pending code

| ✅ Works today | 🚧 Being wired up | 💭 Strong opinions, pending code |
|---|---|---|
| Relay, channels, threads, DMs, canvases, media, search, audit log | Mobile clients (iOS + Android, Flutter) | Web-of-trust reputation across relays |
| Desktop app (Tauri + React) | Workflow approval gates (infra exists, glue still drying) | Push notifications |
| `buzz-cli` (agent-first, JSON in / JSON out) + ACP harness (Goose, Codex, Claude Code) | Huddle lifecycle events | Culture features |
| YAML workflows: message / reaction / schedule / webhook triggers | | |
| Git events (NIP-34: patches, repo announcements, status) | | |
| Git hosting backend | | |

<sub>Please do not plan your compliance program around the 💭 column yet. The <a href="VISION.md">VISION docs</a> are the long version of what we think this becomes.</sub>

---

## Getting started

New to Buzz? Pick the path that matches you.

### I just want to try the app

Grab a packaged build from the [latest release](https://github.com/block/buzz/releases/latest) — macOS (`.dmg`), Linux (`.AppImage` / `.deb`), or Windows (`.exe`). Install it like any other app.

By default the app connects to `ws://localhost:3000`. To point it at a relay you're running or one someone shared with you, set `BUZZ_RELAY_URL` before launching, or switch the relay from inside the app. If you don't have a relay yet, follow **Build & run from source** below to stand one up locally.

### I work at Block

Don't build from source, and don't use the OSS release — use the internal build. It comes pre-wired to the Block relay and agent provider, so it works out of the box with nothing to configure.

Download the latest build from [`squareup/buzz-releases` releases](https://github.com/squareup/buzz-releases/releases/latest) and install it.

### I want to build & run from source

See **Quick start** below — this is the developer / self-host path.

---

## Quick start

You'll need [Docker](https://docs.docker.com/get-docker/) and [Hermit](https://cashapp.github.io/hermit/) (or Rust 1.88+, Node 24+, pnpm 10+, `just`).

**Once:**
```bash
git clone https://github.com/block/buzz.git && cd buzz
. ./bin/activate-hermit   # pinned toolchain (tools auto-download on first use)
just setup && just build
```

`just setup` runs `just bootstrap` automatically — it copies `.env.example` to `.env` if needed, downloads all required tools via Hermit, and starts Docker services + migrations.

**Every day:**
```bash
. ./bin/activate-hermit
just dev   # starts the relay + desktop app together
```

Relay on `ws://localhost:3000`. Desktop app pops up. You're in.

For a split-terminal workflow (relay logs separate from Vite output), use `just relay` in one terminal and `just desktop-dev` in another.

For agents, set `BUZZ_PRIVATE_KEY` and use [`buzz-cli`](crates/buzz-cli) — JSON in, JSON out, designed for LLM tool calls.

---

## Windows prerequisites

The agent shell tool runs commands under bash. On macOS and Linux that's already there; on Windows you need to bring it.

Install [Git for Windows](https://git-scm.com/download/win) — it ships Git Bash, which is what buzz resolves at runtime. Once it's installed, everything works the same as on other platforms.

If you'd rather point buzz at a different bash-compatible shell, set `BUZZ_SHELL` to its path (e.g. `BUZZ_SHELL=C:\path\to\bash.exe`). The agent's tool description updates automatically to reflect whichever shell is active.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                             Clients                                     │
│  Human client         AI agent              CLI / scripts               │
│  (Buzz desktop)       (Goose, Codex, ...)   (buzz-cli, agents)          │
│       │               ┌──────────────┐               │                  │
│       │               │  buzz-acp  │                 │                  │
│       │               │  (ACP ↔ MCP) │               │                  │
│       │               └──────┬───────┘               │                  │
│       │                      │                       │                  │
└───────┼──────────────────────┼───────────────────────┼──────────────────┘
        │ WebSocket            │ WS + REST             │ WS + REST
        ▼                      ▼                       ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                          buzz-relay                                     │
│  NIP-01 · NIP-42 auth · channel/DM/media/workflow/git REST · audit log  │
└───┬──────────────────────────┬──────────────────────────┬──────────────┘
    │                          │                          │
 ┌──▼───────────┐       ┌──────▼──────┐           ┌───────▼─────┐
 │   Postgres   │       │    Redis    │           │   S3/MinIO  │
 │ (events +    │       │  (pub/sub)  │           │  (Blossom)  │
 │  FTS search) │       └─────────────┘           └─────────────┘
 └──────────────┘
```

A Rust workspace of focused crates. Single source of truth: the relay. See [ARCHITECTURE.md](ARCHITECTURE.md) for the full breakdown.

<details>
<summary><strong>Crate map</strong></summary>

**Core protocol** — `buzz-core` (zero-I/O types, NIP-01 filters, Schnorr verify) · `buzz-relay` (Axum WS + REST)

**Services** — `buzz-db` (Postgres) · `buzz-auth` (NIP-42/98 Schnorr auth, rate limiting) · `buzz-pubsub` (Redis, presence, typing) · `buzz-search` (Postgres FTS) · `buzz-audit` (hash-chain log). Multi-community mode scopes tenant-observable rows, cache keys, search documents, workflow state, media metadata, git repo pointers, and audit chains by the host-derived community; shared infrastructure is an implementation detail, not a user-visible global workspace.

**Agent surface** — `buzz-cli` (agent-first CLI, JSON in / JSON out) · `buzz-acp` (ACP harness for Goose/Codex/Claude Code) · `buzz-agent` (ACP agent — see [VISION_AGENT.md](VISION_AGENT.md)) · `buzz-dev-mcp` (shell + file-edit tools) · `buzz-workflow` (YAML automation) · `buzz-persona` (agent persona packs)

**Git & pairing** — `git-sign-nostr` / `git-credential-nostr` (nostr-signed git) · `buzz-pair-relay` / `buzz-pairing-cli` (relay pairing)

**Shared** — `buzz-sdk` (typed event builders) · `buzz-media` (Blossom/S3)

**Tooling** — `buzz-admin` (admin CLI) · `buzz-test-client` (E2E)

</details>

---

## Going further

- **[VISION.md](VISION.md)** · **[VISION_SOVEREIGN.md](VISION_SOVEREIGN.md)** · **[VISION_PROJECTS.md](VISION_PROJECTS.md)** · **[VISION_AGENT.md](VISION_AGENT.md)** — the four vision docs
- **[ARCHITECTURE.md](ARCHITECTURE.md)** — system design, kind ranges, subsystem boundaries
- **[TESTING.md](TESTING.md)** — multi-agent E2E test suite
- **[CONTRIBUTING.md](CONTRIBUTING.md)** · **[CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md)** · **[SECURITY.md](SECURITY.md)** · **[GOVERNANCE.md](GOVERNANCE.md)**

<details>
<summary><strong>Configuration</strong> (env vars, defaults work for local dev)</summary>

All defaults work out of the box. Override via `.env`. Full reference in [`.env.example`](.env.example).

</details>

<details>
<summary><strong>Common dev commands</strong></summary>

```bash
just setup          # Docker, migrations, desktop deps
just relay          # Run the relay
just dev            # Run the desktop app
just build          # Build the Rust workspace
just check          # fmt + clippy + desktop check
just test-unit      # Unit tests (no infra required)
just test           # Full suite (starts services if needed)
just ci             # Everything CI runs
just reset          # ⚠️  Wipe data + recreate
```

</details>

---

## What it is not

- Not blockchain. Signed events are useful without making everyone buy a commemorative coin.
- Not an AI replacement plan. Buzz works best when humans stay in the loop and agents stay in the room.
- Not finished. We will tell you what works and what doesn't.

**What it is:** one relay where humans, agents, workflows, git events, and project memory cooperate — the beginning of a workspace that can grow past the tabs it replaces.

---

<p align="center">
  <sub>Buzz 🐝</sub><br>
  <sub>Apache 2.0 · Built by <a href="https://block.xyz">Block, Inc.</a></sub>
</p>

<!-- repository file: VISION.md -->

# 🐝 Buzz — The relay is the workspace

> An engineer is debugging a production incident at 2am. They type in the incident channel: "What happened last time we saw this error?"
>
> An agent watching the channel searches six months of incident history and posts the threads, root causes, and fixes — then offers to page the engineer who deployed the last one.

The platform made it possible. The agent made it happen. Buzz is the pipe — event store, search index, subscriptions, delivery — not the brain. Humans and agents bring the intelligence. Buzz gives them a shared space to use it.

One community is your entire workspace. Work, conversation, agents, automation, artifacts, docs — one domain, one identity system, one search index. `myproject.com` in a browser shows your repos. `git clone repoa.myproject.com` works. Open the Buzz app and you're in the channels where the work happens. No GitHub. No Discord. No stitching five services together. The project lives in one place, and that place is yours. Run your own relay for one community, or let an operator host thousands on shared infrastructure — same OSS codebase, same URL-is-your-workspace experience either way. See [VISION_SOVEREIGN.md](VISION_SOVEREIGN.md) for the full picture.

---

## Surfaces

| Surface | Model | Default Notifications |
|---------|-------|-----------------------|
| 🏠 **Home** | Personalized feed. What matters to you. | — |
| 💬 **Stream** | Topic-based real-time chat. Work. | Zero |
| 📋 **Forum** | Async long-form threads. Culture. | Zero |
| ✉️ **DMs** | 1:1 and group. Up to 9. | URGENT only |
| 🤖 **Agents** | Directory. Your agents. Job board. | — |
| ⚡ **Workflows** | YAML-as-code automation. Traces. | Approvals only |
| 🔍 **Search** | Cmd+K. Instant. Full-text. | — |

*Desktop app supports all seven surfaces today.*

- **Stream** — Slack-like, fast. Mandatory topics → sub-replies. Zero-notification default.
- **Forum** — Discourse-like, slow. Post → flat replies. Zero-notification default.
- **Workflow** — Structured, traceable. Steps → approval gates. Approvals only.

One event log. One search index. Three lenses.

---

## Access

The relay enforces all access control. Channel membership is the only gate.

| Type | Visibility | Join | Create |
|------|-----------|------|--------|
| **Open channels** | Searchable by all members | Self-join | Any member |
| **Private channels** | Hidden, invite-only | Invited by member | Any member |
| **DMs** | Participants only | N/A (up to 9) | Any member |
| **Guests** | Scoped to specific channels | Invited | N/A |

Guests (investors, reporters, partners) get a scoped token with membership in specific channels. Same access model as everyone else.

---

## Communities

A **community** is the tenant boundary: one workspace, one URL, one isolated world of channels, members, profiles, DMs, repos, and search. The single-community deployment most operators run is identical to a Buzz relay today — the community level adds nothing observable at N=1. What changes is that one shared deployment can host many communities at once, so an operator can onboard a new workspace with a DB write and a DNS route instead of provisioning a stack per signup.

- **The URL is the community.** `myproject.com` is authoritative — exactly as a relay URL is today, lifted one level up. Every connection binds to its host's community before any request runs; an unknown host is rejected, never defaulted into a neighbor.
- **Isolation is the boundary, not a filter.** Communities sharing infrastructure cannot see each other — not each other's events, profiles, DMs, search results, audit chains, or error strings. This is proven, not asserted: the [multi-tenant relay spec](docs/multi-tenant-relay.md) mechanizes isolation in TLA+ and authorization in Tamarin, with every guarantee mutation-tested.
- **Identity is portable, profiles are per-community.** Your keypair is yours across every community; your profile, DMs, and channel-less content live per-community. You repost your profile into each community you join — no cross-community leakage of who you are or whom you message.

---

## The Protocol

[Nostr NIP-01](https://github.com/nostr-protocol/nips/blob/master/01.md) on the wire. Every action — a message, a reaction, a workflow step, a profile update — is a cryptographically signed event:

```
id        sha256 of canonical bytes
pubkey    secp256k1 public key
kind      integer (the only switch)
tags      structured metadata
content   JSON payload
sig       Schnorr signature
```

Buzz extends the standard Nostr event format with custom kind numbers for enterprise features.

New message type? New kind integer. Zero breaking changes.

---

## Architecture

Rust backend, TypeScript/React clients. The server is a Cargo workspace of focused crates — relay, auth, pub/sub, search, audit, workflow engine, MCP agent interface, and more. The desktop client is a Tauri 2 app with React 19; the relay also serves a browser web client (the repo browser at `myproject.com`). See [README.md](README.md) for the full crate map.

---

## Identity

Humans and agents get the same thing:

- secp256k1 keypair (Nostr-native)
- `alice@example.com` NIP-05 handle
- NIP-42 Schnorr auth (humans) or NIP-98 Schnorr auth (agents)
- Bot role on agent channel membership. Visual badges are next.

Auth is simple — authenticated or not. Channel membership gates content visibility.

---

## Encryption

One model. TLS in transit. At-rest encryption delegated to the storage layer (e.g., Postgres TDE, volume encryption). Server-managed encryption covers every channel, every DM, every event — eDiscovery works on everything. End-to-end encryption (NIP-44) is a future consideration for DMs.

---

## Huddles

Real-time voice runs over a WebSocket Opus relay built into `buzz-relay`. Buzz authenticates participants (NIP-42), admits them to a room, and forwards Opus frames between peers — no external SFU.

- Agents join the same audio relay as humans — they bring their own STT/TTS
- Huddle lifecycle flows as Nostr events: started, joined, left, ended

Voice, room lifecycle, and lifecycle events are wired. Recording and per-track publishing are planned.

---

## Buzz Mesh

Relay communities can pool opted-in member hardware into shared AI compute. Existing agents see it as a local OpenAI-compatible provider; the relay gates discovery and trust with the same membership model it already uses for messages, code, and workflows. Models too large for any single machine split across several. See [VISION_MESH.md](VISION_MESH.md) for the full compute-commons vision.

---

## Workflows

Channel-scoped YAML-as-code automation with conditional logic — the feature Slack paywalled for 5 years. Message triggers, reaction triggers, scheduled runs, webhooks. Every step traced. Agents manage workflows through MCP tools.

Approval gates are partially built: the schema, REST endpoints, MCP tool, and UI all exist. The executor doesn't yet persist the approval token or suspend execution — a run that hits a `request_approval` step is marked Failed (WF-08). The infrastructure is there; the wiring is next.

---

## Home Feed & Notifications

Zero is the default. You opt in to noise, not out.

The Home Feed is the personalized entry point — @mentions, items needing action, channel activity, agent updates. Fan-out-on-read, assembled at query time. Agents read the same feed via MCP.

See [VISION_ACTIVITY.md](VISION_ACTIVITY.md) for the agent activity feed in depth: the window into delegated work, designed to be skimmed at a glance rather than decoded line by line.

---

## Channel Features

Beyond chat: channels are workspaces.

- **Canvases** — a shared document per channel. Read and write via the desktop or MCP tools.
- **Media uploads** — paste, drop, or attach files. Stored via the [Blossom](https://github.com/hzrd149/blossom) protocol (BUD-01/BUD-02) on S3/MinIO. Thumbnails generated server-side.
- **Message editing and deletion** — with confirmation. Soft-deleted events remain in the audit log.
- **Community moderation** — private reports, owner/admin queues, structural enforcement, audit, and best-effort notices. See [VISION_MODERATION.md](VISION_MODERATION.md) for the full governance model.
- **Typing indicators** — real-time. Agents broadcast them too.

---

## Code

The relay hosts git repos. Smart HTTP — standard `git clone`, `git push`, nothing special. Your npub signs pushes. Same domain, same auth, same identity as everything else on the relay.

Branches are channels. Create a feature branch, Buzz creates a channel — CI results, review comments, and the merge decision all live there. When the branch merges, the channel archives into a permanent record of why that code exists.

See [VISION_PROJECTS.md](VISION_PROJECTS.md) for the full forge vision: the project model, the merge flow, branch protections, and how agents participate as contributors.

---

## Agent CLI

`buzz-cli` is an agent-first CLI that mirrors and extends the MCP surface — same primitives, plus repo, upload, and canvas operations where the CLI is the canonical interface. JSON-only stdout, structured errors on stderr, two-tier auth (NIP-98 keypair → dev pubkey). Agents can script the entire platform without a GUI.

---

## Agent Personas & Teams

Agents aren't monolithic. A persona bundles a model and a system prompt. A team is a named group of personas — deploy Ralph for code review, Scout for research, Reviewer for crossfire. Built-in personas ship with the desktop client; operators define their own.

---

## Culture Features

*(Planned design — not yet implemented)*

Not afterthoughts — ship blockers:

| Feature | Description |
|---------|-------------|
| 🎨 Custom emoji | Tribal identity |
| 🎉 Confetti | On `/ship` |
| 📊 Native polls | `/poll`, first-class |
| ☕ Coffee Roulette | Weekly random human pairings |
| 🏆 Kudos | First-class recognition |
| 🧊 Knowledge Crystallization | AI proposes summaries, humans approve → pinned artifacts |

---

## Scale

| Metric | Target |
|--------|--------|
| Users | 10K humans + 50K agents |
| Throughput | ~600K events/day (~7/sec avg) |
| Event store | Postgres 17, partitioned monthly |
| Fan-out | Redis pub/sub, <50ms p99 |
| Search | Postgres FTS, permission-aware, full-text |
| Audit | Hash-chain audit log, tamper-evident |
| Accessibility | WCAG 2.1 AA minimum |

---

## Build Model

Greenfield. Agent swarms build in parallel, integrating at the event store boundary. Buzz is being built with AI-assisted development — agents write code, crossfire reviews across multiple models catch blind spots before merge. A complete platform, not a collection of independent microservices.

---

## Status

| | Area |
|-|------|
| ✅ | Core relay, auth, pub/sub, search, audit |
| ✅ | MCP server — full feature surface |
| ✅ | ACP agent harness — goose, codex, claude code |
| ✅ | Desktop client (Tauri) — Stream, Home, Forum, DMs, Agents, Workflows, Search, Settings, Profiles, Presence |
| ✅ | Channel features — messaging, threads, reactions, canvases, media uploads, editing, deletion, typing indicators, NIP-29, soft-delete |
| ✅ | Workflow engine — YAML-as-code, execution traces, message/reaction/schedule/webhook triggers |
| ✅ | Identity — NIP-05, public profiles, NIP-98 auth, agent protection |
| ✅ | Agent CLI — `buzz-cli`, mirrors and extends the MCP surface |
| ✅ | Agent personas and teams — desktop-managed, built-in defaults, operator-defined |
| 🚧 | Workflow approval gates — infrastructure exists (DB, API, UI); executor doesn't persist/resume (WF-08) |
| ✅ | Huddles — WebSocket Opus voice relay + lifecycle events (recording/tracks planned) |
| ✅ | Buzz Mesh — relay-gated shared AI compute (mesh-llm over iroh); members pool GPUs, agents consume via a local OpenAI-compatible endpoint |
| 🚧 | Mobile client — Flutter app (channels, forum, search, profile, pairing); in active development |
| 📋 | Developer portal, push notifications, culture features |

---

## Contributing

See [README.md](README.md) for setup and [AGENTS.md](AGENTS.md) for connecting AI agents. Licensed under Apache-2.0.

---

*Buzz 🐝 — where humans and agents are just colleagues.*

<!-- repository file: ARCHITECTURE.md -->

# Buzz Architecture

## 1. Executive Summary

Buzz is a self-hosted team communication platform built on the Nostr protocol (NIP-01 wire format), where AI agents and humans are first-class equals. Every action — a chat message, a reaction, a workflow step, a canvas update, a huddle event — is a cryptographically signed Nostr event identified by a `kind` integer. Adding a new feature means defining a new kind number; existing clients see nothing and break nothing.

The relay is the single source of truth. All reads and writes flow through it. There is no peer-to-peer event exchange, no gossip, no replication — just clients connecting to one relay over WebSocket, and the relay enforcing auth, verifying signatures, persisting events, fanning out to subscribers, indexing for search, and triggering automation.

A Buzz **community** is the tenant-visible workspace selected by the request host.
The self-hosted default remains one host, one relay process, one implicit
community. Multi-community deployments move that semantic boundary one level up:
`req.community = resolve_host(connection.host)` is established before AUTH,
EVENT, REQ, REST, media, git, search, workflow, or pub/sub handling. Unknown
hosts fail closed, and NIP-98/API-token stamps must agree with the host-derived
community rather than overriding it.

Buzz is a Rust monorepo, licensed Apache 2.0 under Block, Inc.

---

### System Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                           CLIENTS                                    │
│                                                                      │
│  Human (Nostr app, web, mobile)    Agent (CLI tools via buzz-cli)    │
│           │                                    │                     │
│           └──────────── WebSocket ─────────────┘                    │
└─────────────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         buzz-relay (Axum)                          │
│                                                                      │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌─────────────────────┐ │
│  │ NIP-42   │  │  EVENT   │  │   REQ    │  │  HTTP bridge       │ │
│  │  auth    │  │ pipeline │  │ handler  │  │ /events            │ │
│  └──────────┘  └──────────┘  └──────────┘  │ /query             │ │
│                                             │ /count             │ │
│  ┌──────────────────────────────────────┐   │ /hooks/{id}        │ │
│  │       SubscriptionRegistry           │   │ /media/*           │ │
│  │  DashMap: (channel_id, kind) → conns │   │ /git/*             │ │
│  └──────────────────────────────────────┘   │ /info, NIP-05      │ │
│                                             └─────────────────────┘ │
└──────────┬──────────────┬──────────────────────────────────────────┘
           │              │
     ┌─────▼──────┐  ┌────▼──────┐
     │  Postgres  │  │   Redis   │
     │  (events,  │  │ (presence │
     │  channels, │  │  SET EX,  │
     │  tokens,   │  │  typing   │
     │ workflows, │  │  ZADD,    │
     │   audit)   │  │  PUBLISH) │
     └────────────┘  └───────────┘

     Fan-out: sub_registry.fan_out() → conn_manager.send_to()
     (in-process for local events; Redis round-trip for
     events from other relay instances)

     Redis PUBLISH occurs for channel-scoped events.
     PSUBSCRIBE subscriber loop runs and a consumer task
     fans out received events to local WS connections
     (multi-node fan-out wired; local-echo dedup via AppState.local_event_ids).

     ┌──────────────┐
     │  Postgres    │  ← buzz-search (FTS over the search_tsv
     │ (full-text   │     generated column + GIN index)
     │   search)    │
     └──────────────┘
```

---

### Crate Dependency Hierarchy

```
buzz-core    (zero I/O — types, verification, filter matching, kind registry)
    │
    ├── buzz-db          (Postgres: events, channels, tokens, workflows, audit)
    ├── buzz-auth        (NIP-42, NIP-98, API tokens, scopes, rate limiting)
    ├── buzz-pubsub      (Redis pub/sub, presence, typing indicators)
    ├── buzz-search      (Postgres FTS: query, delete)
    ├── buzz-audit       (hash-chain tamper-evident log)
    └── buzz-workflow    (YAML-as-code automation engine)
         │
         └── buzz-relay       (ties everything together — the server)

buzz-acp            (agent harness — bridges relay @mentions → AI agents via ACP/JSON-RPC)
buzz-sdk            (typed Nostr event builders — used by buzz-acp and buzz-cli)
buzz-media          (Blossom/S3 media storage)
buzz-cli            (agent-first CLI)
buzz-admin          (operator CLI: relay membership + key generation)
buzz-test-client    (integration test harness + manual CLI)
```

**Key architectural principle:** The relay is the single source of truth. `buzz-relay` orchestrates all subsystems by calling them directly — it imports `buzz-db`, `buzz-auth`, `buzz-pubsub`, `buzz-search`, `buzz-audit`, and `buzz-workflow`. However, those subsystems are isolated from each other: `buzz-workflow` never calls `buzz-pubsub`, `buzz-search` never calls `buzz-db`, etc. Cross-subsystem coordination happens only through the relay. In multi-community mode, the relay also owns propagation of `TenantContext`; service crates should receive community-scoped inputs rather than independently deriving tenancy from client-controlled event tags.

---

## 2. The Protocol

Buzz uses Nostr NIP-01 on the wire. Every action is a JSON event with six fields:

```json
{
  "id":      "<sha256 of canonical serialization>",
  "pubkey":  "<secp256k1 public key, hex>",
  "kind":    <unsigned integer>,
  "tags":    [["e", "<event-id>"], ["p", "<pubkey>"], ...],
  "content": "<JSON payload or plain text>",
  "sig":     "<Schnorr signature over id>"
}
```

The `kind` integer is the only dispatch switch. The relay routes, stores, and fans out events based on kind. Clients filter subscriptions by kind. New feature = new kind number = zero breaking changes to existing clients.

### Kind Ranges

| Range | Meaning |
|-------|---------|
| 0–9999 | Standard Nostr kinds (NIP-01 through NIP-XX) |
| 10000–19999 | Replaceable events (NIP-16) |
| 20000–29999 | Ephemeral events — not stored, not audited |
| 30000–39999 | Parameterized replaceable events |
| 40000–49999 | Buzz custom kinds |

### Buzz Custom Kinds (selected)

| Kind | Name | Description |
|------|------|-------------|
| 7 | KIND_REACTION | Emoji reaction (standard NIP-25) |
| 9 | KIND_STREAM_MESSAGE | Chat message in a Stream channel (NIP-29 group chat) |
| 40002 | KIND_STREAM_MESSAGE_V2 | Stream message v2 format |
| 40003 | KIND_STREAM_MESSAGE_EDIT | Edit of a stream message |
| 43001 | KIND_JOB_REQUEST | Agent job request |
| 45001 | KIND_FORUM_POST | Forum thread root |
| 45003 | KIND_FORUM_COMMENT | Forum thread reply |
| 46001–46012 | KIND_WORKFLOW_* | Workflow execution events |
| 20001 | KIND_PRESENCE_UPDATE | Ephemeral presence heartbeat |

`buzz-core` defines all 81 kinds as `pub const KIND_*: u32` and exports `ALL_KINDS: &[u32]`. Kinds are `u32` (NIP-01 specifies unsigned integer; `u32` covers the full range). Buzz uses both standard Nostr kinds (e.g., kind 7 for reactions) and custom ranges (40000+).

Note: `KIND_AUTH` (22242) is `pub const KIND_AUTH: u32` in `buzz-core/src/kind.rs` and imported by `buzz-relay/src/handlers/event.rs`. `KIND_CANVAS` (40100) is likewise `pub const KIND_CANVAS: u32` in `buzz-core/src/kind.rs`.

### Wire Protocol (NIP-01 messages)

| Direction | Message | Purpose |
|-----------|---------|---------|
| Client → Relay | `["EVENT", <event>]` | Submit a signed event |
| Client → Relay | `["REQ", <sub_id>, <filter>, ...]` | Subscribe to events |
| Client → Relay | `["CLOSE", <sub_id>]` | Cancel a subscription |
| Client → Relay | `["AUTH", <event>]` | Authenticate (NIP-42) |
| Relay → Client | `["EVENT", <sub_id>, <event>]` | Deliver a matching event |
| Relay → Client | `["EOSE", <sub_id>]` | End of stored events |
| Relay → Client | `["OK", <event_id>, true/false, ""]` | Event acceptance result |
| Relay → Client | `["CLOSED", <sub_id>, "reason"]` | Subscription closed |
| Relay → Client | `["NOTICE", "message"]` | Informational message |
| Relay → Client | `["AUTH", <challenge>]` | Authentication challenge |

Max frame size: 65,536 bytes. Max subscriptions per connection: 1024. Max historical results per filter: 500.

---

## 3. Connection Lifecycle

Every WebSocket connection follows this exact sequence:

### Step 0: Community Binding

The server resolves `TenantContext` from the request host before any handler can
observe tenant data. The URL/domain is authoritative for the community, matching
today's "the relay URL is the workspace" behavior. In single-community mode the
configured host maps to the default community. In multi-community mode, an
unknown or unmapped host rejects generically and never falls through to a default
tenant. Client-supplied `#h` tags are still channel identifiers; they must resolve
to a channel inside the host-derived community.

### Step 1: Semaphore Acquire

`state.conn_semaphore.try_acquire_owned()` — if the relay is at connection capacity, the connection is rejected immediately before any data is read. The permit is held for the entire connection lifetime and dropped on cleanup.

### Step 2: NIP-42 Challenge

The relay immediately sends `["AUTH", "<challenge>"]`. The challenge is a random string. The connection is registered in `ConnectionManager` after the challenge is sent.

### Step 3: Authentication

The client must respond with `["AUTH", <signed-event>]` before submitting events or subscriptions. Authentication paths:

| Path | Mechanism | Use Case |
|------|-----------|---------|
| NIP-42 | Signed challenge, pubkey verified | WebSocket connections |
| NIP-98 HTTP Auth | Schnorr-signed `kind:27235` event on HTTP bridge endpoints | HTTP clients |

On success, `ConnectionState.auth_state` transitions from `Pending` → `Authenticated(AuthContext)`. On failure → `Failed`. Unauthenticated EVENT/REQ messages are rejected with `["CLOSED", ...]` or `["OK", ..., false, "auth-required: ..."]`.

### Step 4: Active Loops

Three concurrent tasks run for the lifetime of the connection:

- **recv_loop** (inline): reads frames, parses `ClientMessage`, dispatches to handlers
- **send_loop** (spawned): drains the mpsc channel, writes frames to the WebSocket
- **heartbeat_loop** (spawned): sends WebSocket ping every 30 seconds; 3 missed pongs → disconnect

A `CancellationToken` coordinates shutdown across all three loops.

Slow clients: `ConnectionState::send()` uses `try_send` — if the send buffer is full, a grace counter increments. After `SLOW_CLIENT_GRACE_LIMIT` (3) consecutive full-buffer events, the connection is cancelled. A successful send resets the counter.

### Step 5: Cleanup

On disconnect (any cause):
1. `cancel.cancel()` — signals all loops
2. Await send_loop and heartbeat_loop tasks
3. `sub_registry.remove_connection(conn_id)` — removes all subscriptions from the DashMap indexes
4. `conn_manager.deregister(conn_id)` — removes from the send-channel map
5. `drop(permit)` — releases the connection semaphore slot

---

## 4. Event Pipeline

When the relay receives `["EVENT", <event>]`, the handler in `handlers/event.rs` runs this pipeline in order:

```
1. AUTH CHECK        — AuthState::Authenticated? MessagesWrite scope?
2. PUBKEY MATCH      — event.pubkey == auth_context.pubkey?
3. KIND_AUTH REJECT  — kind == 22242 (AUTH events never stored)
4. EPHEMERAL ROUTE   — kind 20000–29999 → ephemeral sub-pipeline (see below)
5. VERIFY            — spawn_blocking(verify_event) — Schnorr sig + ID hash
6. MEMBERSHIP        — channel_id in event tags? → check_channel_membership
7. DB INSERT         — db.insert_event (ON CONFLICT DO NOTHING — idempotent)
8. REDIS PUBLISH     — pubsub.publish_event (if channel-scoped)
9. FAN-OUT           — sub_registry.fan_out → conn_manager.send_to
10. SEARCH INDEX     — search_index_tx.send (bounded worker queue, non-blocking)
11. AUDIT LOG        — audit.log (spawned async, non-blocking)
12. WORKFLOW TRIGGER — wf.on_event (spawned async, excludes kinds 46001–46012)
```

Steps 10–12 are fire-and-forget. Search indexing is sent to a bounded worker queue (`search_index_tx`, capacity 1000); audit and workflow triggers are spawned as independent async tasks. A failure in any of these does not fail the event submission. The client receives `["OK", <id>, true, ""]` at the end of the pipeline, not immediately after DB insert.

Step 9 (fan-out) explicitly **excludes** global subscriptions (no `channel_id` constraint) from channel-scoped events — global subscriptions do NOT receive events from private channels, regardless of filter match. This is a deliberate security boundary: only subscriptions scoped to an accessible `channel_id` receive those events.

Workflow loop prevention: workflow execution kinds (46001–46012), relay-signed messages with `buzz:workflow` tag, and `KIND_GIFT_WRAP` are excluded from triggering workflows. All other stored events (including kind 9 stream messages) trigger workflow evaluation.

### Ephemeral Sub-Pipeline (kinds 20000–29999)

Ephemeral events bypass DB storage, audit, and search. Two sub-paths:

**Presence events (kind 20001):**
```
1. VERIFY            — spawn_blocking(verify_event)
2. REDIS PRESENCE    — set_presence() or clear_presence() based on content
3. LOCAL FAN-OUT     — sub_registry.fan_out → conn_manager.send_to (no Redis PUBLISH)
```
Presence events skip membership checks and use local-only fan-out. Multi-node presence fan-out would require Redis pub/sub (documented as future work).

**Other ephemeral events (e.g., typing indicators):**
```
1. VERIFY            — spawn_blocking(verify_event)
2. MEMBERSHIP        — check_channel_membership (if channel-scoped)
3. MARK LOCAL        — state.mark_local_event (dedup before Redis round-trip)
4. REDIS PUBLISH     — pubsub.publish_event (no DB write)
5. LOCAL FAN-OUT     — sub_registry.fan_out → conn_manager.send_to
```

Ephemeral events are never stored in Postgres and never appear in REQ historical queries.

### Handler Semaphore

Beyond the per-connection semaphore, a `handler_semaphore` (capacity 1024) limits concurrent EVENT and REQ processing across all connections. CLOSE is not rate-limited.

---

## 5. Subscription System

### SubscriptionRegistry

The subscription registry is a DashMap-backed structure in `subscription.rs`:

```rust
pub struct SubscriptionRegistry {
    subs: DashMap<ConnId, HashMap<SubId, SubEntry>>,
    channel_kind_index: DashMap<IndexKey, Vec<(ConnId, SubId)>>,
    channel_wildcard_index: DashMap<Uuid, Vec<(ConnId, SubId)>>,
}

pub struct IndexKey {
    pub channel_id: Uuid,
    pub kind: Kind,
}
```

### Three-Tier Fan-Out

When an event arrives, `fan_out` consults three indexes in order:

| Tier | Index | Key | Use Case |
|------|-------|-----|---------|
| 1 | `channel_kind_index` | `(channel_id, kind)` | Subs with explicit channel + kind filter — O(1) lookup |
| 2 | `channel_wildcard_index` | `channel_id` | Subs with channel but no `kinds` constraint |
| 3 | `subs` (linear scan) | — | Global subs (no channel_id) — fallback scan |

Global subs (tier 3) are checked for non-channel-scoped events only. Channel-scoped events are delivered exclusively to subscriptions that carry a matching `channel_id` — global subscriptions are explicitly excluded from channel fan-out as a security boundary.

### NIP-01 Edge Cases

- `kinds: []` (explicit empty array) means "match nothing" — NOT a wildcard. Subscriptions with empty `kinds` are not indexed in either tier 1 or tier 2 and never receive events.
- `kinds` absent (no field) means "match all kinds" — indexed in tier 2 (channel wildcard) or tier 3 (global).

### REQ Handler Access Control

The REQ handler checks channel access **before** registering the subscription:

```
1. Parse filters, extract channel_id
2. Load accessible_channel_ids for this connection's pubkey
3. If channel_id not in accessible_channels → send CLOSED "restricted: not a channel member"
4. Only then: sub_registry.register(conn_id, sub_id, filters, channel_id)
```

This prevents a race where a non-member receives live fan-out events from a private channel between registration and the access check.

### Historical Query (EOSE)

After registering, the REQ handler queries Postgres for stored events matching the filters (up to 500 per filter, hard cap). These are sent as `["EVENT", sub_id, event]` frames before `["EOSE", sub_id]`. New events arriving after EOSE are delivered via the fan-out path.

---

## 6. Crate Reference

### buzz-core — Shared Types and Verification

**Zero I/O.** The foundation every other crate builds on. Explicitly prohibits tokio, sqlx, redis, and axum in its `Cargo.toml`.

**Key types:**

```rust
pub struct StoredEvent {
    pub event: nostr::Event,
    pub received_at: DateTime<Utc>,
    pub channel_id: Option<Uuid>,
    verified: bool,          // private — use is_verified()
}

pub const ALL_KINDS: &[u32]  // 80 entries (KIND_AUTH excluded — never stored)
```

**Key functions:**

| Function | Purpose |
|----------|---------|
| `filters_match(filters, event)` | OR across filters, AND within each filter. Includes NIP-01 prefix matching on event IDs. |
| `verify_event(event)` | Schnorr signature + SHA-256 ID check. CPU-bound — callers use `spawn_blocking`. |
| `is_private_ip(ip)` | SSRF protection: IPv4 unspecified/loopback/private/link-local/CGNAT/benchmarking/broadcast + IPv6 loopback/ULA/link-local/multicast/documentation + IPv4-mapped IPv6. |

**Does NOT:** store events, make network calls, spawn tasks, or depend on any async runtime.

---

### buzz-auth — Authentication and Authorization

Handles authentication paths, scope enforcement, and token operations.

**Auth paths:**

| Path | Entry Point | Notes |
|------|-------------|-------|
| NIP-42 | `verify_auth_event()` | Schnorr-signed challenge/response; grants `Scope::all_known()` (all 14 scopes) |
| NIP-98 HTTP Auth | `validate_nip98_auth()` | HTTP bridge endpoints; Schnorr-signed `kind:27235` event |

**Key types:**

```rust
pub struct AuthContext { pub pubkey: PublicKey, pub scopes: Vec<Scope>, pub auth_method: AuthMethod }
pub enum AuthMethod { Nip42, Nip98 }
pub enum Scope { MessagesRead, MessagesWrite, ChannelsRead, ChannelsWrite,
                 AdminChannels, UsersRead, UsersWrite, AdminUsers,
                 JobsRead, JobsWrite, SubscriptionsRead, SubscriptionsWrite,
                 FilesRead, FilesWrite, Unknown(String) }
pub trait ChannelAccessChecker: Send + Sync { ... }
pub trait RateLimiter: Send + Sync { ... }
```

**Security details:**
- NIP-98 auth: Schnorr-signed `kind:27235` events with URL + method tags.
- NIP-42 timestamp tolerance: ±60 seconds.
- Dev-only key derivation: `SHA-256("buzz-test-key:{username}")` — gated behind `#[cfg(any(test, feature = "dev"))]`. The `dev` feature must not be enabled in production relay deployments.

**Does NOT:** implement `RateLimiter` beyond a test stub (`AlwaysAllowRateLimiter`, gated behind `#[cfg(any(test, feature = "test-utils"))]`). No Redis-backed rate limiter exists anywhere in the codebase — rate limiting is not currently enforced. `RateLimitConfig` defines 4 tiers (human, agent-standard, agent-elevated, agent-platform) as a design target.

---

### buzz-db — Postgres Event Store

All database access. Uses `sqlx::query()` (runtime, not compile-time macros) — no `.sqlx/` offline cache required.

**Key operations:**

| Module | Responsibility |
|--------|---------------|
| `event.rs` | `insert_event` (ON CONFLICT DO NOTHING), `query_events` (QueryBuilder), `get_event_by_id` |
| `channel.rs` | Channel CRUD, membership management, role enforcement (transactional) |
| `feed.rs` | `query_mentions` (INNER JOIN event_mentions), `query_needs_action`, `query_activity` |
| `workflow.rs` | Full workflow/run/approval CRUD; SHA-256 hashed approval tokens |
| `partition.rs` | Monthly range partitioning for `events` and `delivery_log` tables |
| `dm.rs` | DM channel management |
| `reaction.rs` | Reaction storage and retrieval |
| `thread.rs` | Thread/reply tracking |
| `user.rs` | User profile storage |
| `error.rs` | Database error types |

**Channel types:** `Stream`, `Forum`, `Dm`, `Workflow`  
**Member roles:** `Owner`, `Admin`, `Member`, `Guest`, `Bot`  
**Workflow statuses:** `Active`, `Disabled`, `Archived`  
**Run statuses:** `Pending`, `Running`, `WaitingApproval`, `Completed`, `Failed`, `Cancelled`

**Key behaviors:**
- `ON CONFLICT DO NOTHING` for event dedup — returns `(StoredEvent, was_inserted: bool)`.
- Rejects `KIND_AUTH` (22242) and ephemeral (20000–29999) with distinct error variants.
- Transactional role enforcement in `add_member`/`remove_member`/`create_channel` — TOCTOU-safe.
- Soft-delete for channel members: `remove_member` sets `removed_at`; re-adding reverses it.
- Feed hard cap: `FEED_MAX_LIMIT = 100` rows regardless of caller-requested limit.
- `query_mentions` uses `INNER JOIN event_mentions` — normalized table with composite index on `(pubkey_hex, created_at)`.
- Approval tokens: `create_approval` receives the raw token and hashes it internally with SHA-256.
- DDL injection protection in partition manager: allowlist of table names + strict suffix/date validators.

**Does NOT:** cache queries, implement connection pooling logic (delegated to sqlx), or make network calls outside Postgres.

---

### buzz-pubsub — Redis Pub/Sub, Presence, Typing

Manages Redis pub/sub fan-out, presence tracking, and typing indicators. In multi-community mode all tenant-visible keys are prefixed or otherwise partitioned by community (`buzz:{community}:...`) so channel fan-out, presence, typing, and cache invalidation cannot cross hosts.

**Architecture:**

```
Publisher  → pool connection   → PUBLISH buzz:channel:{uuid}
Subscriber → dedicated PubSub  → PSUBSCRIBE buzz:channel:*
                                  → broadcast::channel(4096)
```

The subscriber uses a **dedicated** `redis::aio::PubSub` connection — not from the pool. This is intentional: pool connections cannot hold `PSUBSCRIBE` state.

**Current state:** The subscriber loop is spawned in `buzz-relay/src/main.rs` and populates the broadcast channel. A consumer task subscribes via `pubsub.subscribe_local()`, calls `sub_registry.fan_out()` on each received event, and delivers matches to local WebSocket connections via `conn_manager.send_to()`. Multi-node fan-out is now wired end-to-end. Local-echo deduplication is implemented via `AppState.local_event_ids` — events published by the local relay instance are tracked and skipped when received via the Redis round-trip.

**Reconnection:** exponential backoff 1s → 30s (`backoff_secs * 2`). Backoff resets to 1s only after a clean stream end, not on each reconnect attempt.

**Presence:** `SET buzz:presence:{pubkey_hex} {status} EX 90` — 90-second TTL (3× the 30-second heartbeat interval). Single missed heartbeat does not cause presence flap.

**Typing indicators:**
```
ZADD buzz:typing:{channel_id} {now_unix} {pubkey_hex}
ZREMRANGEBYSCORE buzz:typing:{channel_id} -inf {now - 5.0}
EXPIRE buzz:typing:{channel_id} 60
```
5-second activity window. 60-second key TTL prevents orphaned empty sets.

**Does NOT:** implement the rate limiter. Does NOT store events. `PubSubManager` is not `Clone` — callers use `Arc<PubSubManager>`.

---

### buzz-search — Postgres FTS Integration

Full-text search via Postgres FTS. Events are searchable through the
`events.search_tsv` generated `tsvector` column (populated on insert, indexed
by a GIN index) — there is no separate search service or out-of-band indexer.
Privacy-sensitive kinds are excluded at the storage level (the `search_tsv`
`CASE WHEN kind IN (...)` yields `NULL`, which never matches `@@`). In
multi-community mode every query filter includes `community_id`, so the shared
`events` table is infrastructure, not a cross-community result space; the relay
re-authorizes every candidate hit before returning it.

**Key behaviors:**
- `SearchService::new(pool)` wraps a `PgPool`; `search(&SearchQuery)` runs a
  parameterized FTS query against the `events.search_tsv` GIN index and returns
  `SearchResult` (candidate `SearchHit`s).
- `ChannelScope` makes the channel constraint explicit (`Any` /
  `ChannelLessOnly` / `Channels` / `ChannelsOrChannelLess`), closing the
  ambiguity the old `Option<Vec<Uuid>> + bool` matrix could not express.
- Every query carries `community_id`; the FTS predicate is BitmapAnd-ed with
  the community-leading btree filters so a query never crosses tenants.
- Permission filtering is **caller's responsibility** — `buzz-search` returns
  candidate hits; the relay re-authorizes each one (channel membership, `#p`,
  owner gates) before delivering it.

**Does NOT:** enforce channel membership or access control. Does NOT write
events (indexing is the `search_tsv` generated column on the `events` insert).

---

### buzz-audit — Hash-Chain Audit Log

Tamper-evident append-only log with SHA-256 hash chaining.

**Hash chain:** each entry stores `prev_hash` (hash of the previous entry). In multi-community mode audit heads/chains are per-community; operator metrics may aggregate, but tenant-readable audit verification walks one community chain. `verify_chain()` walks entries and recomputes hashes to detect tampering. Genesis entry uses `GENESIS_HASH` (64 zeros).

**Hash covers:** seq (big-endian bytes), timestamp (RFC3339), event_id, event_kind (big-endian), actor_pubkey, action string, channel_id (16 bytes or 16 zero bytes if None), canonical metadata JSON (BTreeMap for deterministic key ordering), prev_hash.

**Single-writer guarantee:** `pg_advisory_lock` before each transaction. Lock released in all branches including panic (`catch_unwind`).

**10 audit actions:** `EventCreated`, `EventDeleted`, `ChannelCreated`, `ChannelUpdated`, `ChannelDeleted`, `MemberAdded`, `MemberRemoved`, `AuthSuccess`, `AuthFailure`, `RateLimitExceeded`.

**Does NOT:** log `KIND_AUTH` (22242) events — returns `AuditError::AuthEventForbidden` immediately. Does NOT log ephemeral events (they never reach the audit pipeline).

---

### buzz-workflow — YAML-as-Code Automation Engine

Parses, validates, and executes channel-scoped workflow definitions. In multi-community mode workflow definitions, runs, approvals, webhook routes, and schedules inherit the host-derived community and evaluate triggers only against events in that community.

**Workflow definition structure:**
```yaml
name: "Incident Triage"
trigger:
  on: message_posted
  filter: "str_contains(trigger_text, 'P1')"
steps:
  - id: notify
    action: send_message
    text: "P1 incident detected: {{trigger.text}}"
  - id: page
    if: "str_contains(trigger_text, 'production')"
    action: request_approval
    from: "{{trigger.author}}"
    message: "Page on-call?"
```

Note: Both `TriggerDef` and `ActionDef` use serde internally-tagged enums. Triggers use `on:` as the tag field; actions use `action:` as the tag field. Fields are flattened into the parent struct, not nested.

**4 trigger types:** `message_posted`, `reaction_added`, `schedule`, `webhook`

**7 action types:**

| Action | Description |
|--------|-------------|
| `send_message` | Post to the workflow's channel (or override channel) |
| `send_dm` | Direct message to a user (pubkey hex or `{{trigger.author}}`) |
| `set_channel_topic` | Update channel topic |
| `add_reaction` | React to the trigger message |
| `call_webhook` | HTTP POST to external URL (SSRF-protected, redirects disabled, 1 MiB response cap) |
| `request_approval` | Suspend execution; fields: `from`, `message`, `timeout` (default 24h) |
| `delay` | Pause execution (max 300 seconds) |

**Template variables:** `{{trigger.text}}`, `{{trigger.author}}`, `{{steps.ID.output.FIELD}}`. Single-pass resolution (not recursive). Unknown variables left as literal text.

**Condition evaluation:** `evalexpr` with `HashMapContext`. Dot notation converted to underscores (`trigger.text` → `trigger_text`). Custom functions registered: `str_contains`, `str_starts_with`, `str_ends_with`, `str_len`. 100ms timeout prevents adversarial expressions from blocking.

**Concurrency:** `Arc<Semaphore>` with 100 permits. `try_acquire()` — returns `CapacityExceeded` immediately rather than queuing.

**Approval gates:** `request_approval` action returns `StepResult::Suspended` with a generated UUID token, but the engine does not yet persist the token or resume execution — runs that hit an approval gate are marked as failed (🚧 WF-08). `execute_from_step()` exists for future resumption support.

**Cron scheduler:** loop ticks every 60 seconds, evaluates cron expressions with window-based matching, and creates workflow runs for matched triggers. Fully implemented.

**Does NOT:** recursively resolve templates (single-pass only). Does NOT queue workflow runs when at capacity — returns `CapacityExceeded` immediately.

---

### Huddle Audio — WebSocket Opus Relay

Real-time voice lives inside `buzz-relay` (`src/audio/`), not a separate crate. A WebSocket endpoint (`wss://.../huddle/{channel_id}/audio`) authenticates each participant with a NIP-42 challenge, checks channel membership, admits them to an in-memory room, and forwards opaque Opus frames between peers. No external SFU.

**Frame protocol (v2):** 8-byte big-endian header (sequence `u16`, 48 kHz timestamp `u32`, level dBov `i8`, flags `u8`) followed by an opaque Opus payload. Invalid `level_dbov` values are clamped rather than dropped — losing a metric beats losing audio.

**Room state:** an admission guard synchronizes joins against the room's ended flag; soft cap 25 peers (hard cap 255 via `u8` peer index). Per-peer audio uses a bounded channel (drop-on-full); the control channel is separate and never drops join/leave.

**Lifecycle events:** the relay emits Nostr events for participant joined / left and huddle ended; the desktop client emits huddle started and guidelines. When the last peer leaves, the room ends and the channel archives atomically.

**Not yet built:** recording and per-track publishing (the corresponding kinds are reserved, no producer exists).

---

### buzz-relay — The Server

Axum WebSocket server. Ties all other crates together. The only crate that imports and orchestrates all subsystems.

**`AppState`** (Arc-wrapped, shared across all connections — key fields shown, not exhaustive):

```rust
pub struct AppState {
    pub db: Db,
    pub audit: Arc<AuditService>,
    pub pubsub: Arc<PubSubManager>,
    pub auth: Arc<AuthService>,
    pub search: Arc<SearchService>,
    pub sub_registry: Arc<SubscriptionRegistry>,
    pub conn_manager: Arc<ConnectionManager>,
    pub workflow_engine: Arc<WorkflowEngine>,
    pub conn_semaphore: Arc<Semaphore>,       // connection limit
    pub handler_semaphore: Arc<Semaphore>,    // 1024 concurrent handlers
    pub relay_keypair: nostr::Keys,           // relay identity
    pub local_event_ids: moka::sync::Cache,   // local-echo dedup
    pub search_index_tx: mpsc::Sender,        // bounded search worker queue
    // + config, redis_pool, membership_cache, media_storage, shutdown state
}
```

**`ConnectionState`** (per-connection):

```rust
pub struct ConnectionState {
    pub auth_state: RwLock<AuthState>,
    pub subscriptions: Mutex<HashMap<String, Vec<Filter>>>,
    // + send_tx, cancel token
}
pub enum AuthState { Pending { challenge: String }, Authenticated(AuthContext), Failed }
```

**HTTP endpoints:**

| Method | Path | Handler |
|--------|------|---------|
| GET | `/` | WebSocket upgrade or NIP-11 relay info |
| GET | `/info` | NIP-11 relay info |
| GET | `/.well-known/nostr.json` | NIP-05 identity |
| GET | `/health` | Health check |
| GET | `/_liveness` | Liveness probe |
| GET | `/_readiness` | Readiness probe |
| POST | `/events` | Submit a signed Nostr event over HTTP (same ingest path as WebSocket `EVENT`) |
| POST | `/query` | Query Nostr events over HTTP with NIP-01 filters |
| POST | `/count` | Count Nostr events over HTTP with NIP-45 filters |
| POST | `/hooks/{id}` | Workflow webhook trigger (secret-authenticated) |
| PUT | `/media/upload` | Upload media blob (Blossom, 50 MB limit) |
| GET/HEAD | `/media/{sha256_ext}` | Retrieve/probe media blob |
| GET | `/git/{owner}/{repo}/info/refs` | Git smart HTTP advertisement |
| POST | `/git/{owner}/{repo}/git-upload-pack` | Git smart HTTP fetch |
| POST | `/git/{owner}/{repo}/git-receive-pack` | Git smart HTTP push |
| POST | `/internal/git/policy` | Internal git hook policy check |

**Constants:**

| Constant | Value | Purpose |
|----------|-------|---------|
| `MAX_FRAME_BYTES` | 65,536 | Max WebSocket frame size |
| `MAX_SUBSCRIPTIONS` | 1024 | Per-connection subscription limit |
| `MAX_HISTORICAL_LIMIT` | 500 | Per-filter historical query cap |
| `handler_semaphore` capacity | 1024 | Concurrent EVENT/REQ handlers |

**Does NOT:** implement business logic — delegates to the appropriate crate for every operation.

---

### buzz-acp — Agent Communication Protocol Harness

Standalone binary that bridges Buzz relay events to AI agents via the [Agent Communication Protocol](https://agentclientprotocol.com/) (ACP).

**Architecture:**

```
Buzz Relay ──WS──→ buzz-acp ──stdio (ACP/JSON-RPC)──→ Agent (goose/codex/claude)
```

`buzz-acp` spawns AI agent subprocesses (1–32, default 1), connects to the relay via WebSocket with NIP-42 auth, discovers channels via REST API, and queues `@mention` events per channel. At most one prompt is in-flight per channel. Queued events are batched into a single prompt sent via `session/prompt` over ACP.

**Key modules:**

| Module | LOC | Responsibility |
|--------|-----|---------------|
| `relay.rs` | 3,143 | WebSocket + REST relay connection, NIP-42 auth |
| `queue.rs` | 2,565 | Per-channel event queue, batching, dedup |
| `main.rs` | 2,457 | Event loop, pool orchestration, heartbeat |
| `pool.rs` | 2,253 | N-agent pool, claim/return lifecycle |
| `config.rs` | 1,903 | CLI/env/TOML configuration |
| `acp.rs` | 1,785 | ACP client, stdio JSON-RPC, timeouts |
| `filter.rs` | 814 | Subscription rules, evalexpr filtering |

**Key behaviors:**
- Pool of 1–32 agent subprocesses with claim/return lifecycle.
- Per-channel queuing: at most one prompt in-flight per channel; subsequent @mentions queue until the agent responds.
- Crash recovery: agent subprocess crashes are detected and the agent is respawned.
- Depends on `buzz-core` (kind constants) and `buzz-sdk` (relay/REST utilities).

**Does NOT:** persist state.

---

### buzz-admin — Operator CLI

Subcommands:

| Subcommand | Purpose |
|------------|---------|
| `add-member` | Add a pubkey to the relay membership list (`--pubkey`, `--role`); accepts npub or hex; publishes kind:13534 roster |
| `remove-member` | Remove a pubkey from the relay membership list (`--pubkey`, optional `--role` guard); publishes kind:13534 roster |
| `list-members` | List all relay members |
| `generate-key` | Generate a new Nostr keypair (for bootstrapping) |
| `reconcile-channels` | Emit kind:39000/39002 discovery events for channels missing them (idempotent) |

The `buzz-admin` binary is shipped in the relay Docker image (`/usr/local/bin/buzz-admin`) and is the recommended way to manage relay membership in production. Use `./run.sh add-member`, `./run.sh remove-member`, and `./run.sh list-members` in Docker Compose deployments.

---

### buzz-test-client — Integration Test Harness

**`BuzzTestClient`** wraps a WebSocket connection with a `VecDeque<RelayMessage>` buffer for message interleaving. Methods: `connect`, `connect_unauthenticated`, `authenticate`, `send_event`, `send_text_message`, `subscribe`, `close_subscription`, `recv_event`, `collect_until_eose`, `disconnect`.

**Test coverage:**

| File | Tests | Scope |
|------|-------|-------|
| `tests/e2e_relay.rs` | 27 | WebSocket protocol (auth, subscriptions, filters, limits, NIP-11) |
| `tests/e2e_media.rs` | 7 | Media upload/download (Blossom) |
| `tests/e2e_media_extended.rs` | 18 | Extended media scenarios |
| `tests/e2e_nostr_interop.rs` | 15 | Nostr interoperability: NIP-50 search, NIP-10 threads, NIP-17 gift wraps, DM discovery |

All e2e tests are `#[ignore]` — require a running relay. Total: **134 e2e tests**.

`src/main.rs` is a manual testing CLI (`buzz-test-cli`) with `--send`, `--subscribe`, `--channel`, `--url`, `--kind` flags.

Defines `parse_relay_message`, `OkResponse`, `RelayMessage` directly in `src/lib.rs`.

---

## 7. Security Model

Every security-sensitive operation uses an explicit, verified pattern. No implicit trust.

### Authentication

| Concern | Mechanism |
|---------|-----------|
| NIP-42 timestamp | ±60 second tolerance — prevents replay attacks |
| AUTH events | Never stored in Postgres, never logged in audit chain |
| NIP-98 HTTP Auth | Schnorr-signed `kind:27235` events — URL and method verification |

### Input Validation

| Concern | Mechanism |
|---------|-----------|
| Schnorr signatures | `verify_event()` in `buzz-core` — every event verified before storage |
| Event ID | SHA-256 of canonical serialization verified independently of signature |
| Frame size | `MAX_FRAME_BYTES = 65,536` — oversized frames rejected, connection closed |
| Search event IDs | 64-char hex validation before URL construction — prevents path injection |
| Workflow step IDs | Alphanumeric + underscore only — prevents evalexpr variable injection |
| Partition names | Allowlist of table names + strict suffix/date validators — prevents DDL injection |

### SSRF Protection

`is_private_ip()` in `buzz-core` covers:
- IPv4: unspecified (0.0.0.0/8), loopback (127.0.0.0/8), private (10/8, 172.16/12, 192.168/16), link-local (169.254/16), CGNAT (100.64/10), benchmarking (198.18/15), broadcast (255.255.255.255)
- IPv6: loopback (::1), ULA (fc00::/7), link-local (fe80::/10), multicast (ff00::/8), documentation (2001:db8::/32)
- IPv4-mapped IPv6 (::ffff:0:0/96) — recursively checks the embedded IPv4 address

Applied in: `buzz-workflow` (CallWebhook action), `buzz-core` (shared utility).

### Audit Integrity

- Hash chain: each entry's SHA-256 covers all fields including `prev_hash` — tampering any entry breaks all subsequent hashes
- Canonical JSON: `BTreeMap` for deterministic key ordering — hash is reproducible
- Single-writer lock: `pg_advisory_lock` — prevents concurrent writes from breaking the chain
- Panic-safe: `catch_unwind` ensures lock release even on panic

### Access Control

- Channel membership is the only gate — enforced by the relay at every operation
- REQ handler checks access before subscription registration — no race window for private channel leaks
- TOCTOU-safe membership operations: all check-then-modify sequences run inside Postgres transactions
- Approval tokens: UUID (CSPRNG), stored as SHA-256 hash, single-use enforced with `AND status = 'pending'` in UPDATE

### Webhook Security

- Workflow webhooks: constant-time XOR comparison of stored UUID secret (not HMAC — compares the secret directly, not a body MAC)
- Outbound webhooks (CallWebhook): SSRF protection + redirects disabled + 1 MiB response cap

---

## 8. Infrastructure

Docker Compose provides the full local development stack. All services include health checks and resource limits.

### Services

| Service | Image | Port | Purpose |
|---------|-------|------|---------|
| Postgres | `postgres:17-alpine` | 5432 | Primary event store — events, channels, tokens, workflows, audit; full-text search (`search_tsv` GIN) |
| Redis | `redis:7-alpine` | 6379 | Pub/sub fan-out, presence (SET EX), typing (sorted sets) |
| Adminer | `adminer` | 8082 | DB web UI (dev only) |
| MinIO | `minio/minio` | 9000 (API), 9001 (console) | S3-compatible object storage (media) |
| Prometheus | `prom/prometheus` | 9090 | Metrics collection |

### Postgres Schema (key tables)

| Table | Purpose |
|-------|---------|
| `events` | All stored Nostr events; monthly range-partitioned by `PARTITION BY RANGE` on `created_at`; multi-community mode keys every tenant-visible event by `community_id` |
| `channels` | Channel records (type, visibility, canvas, topic); `community_id` is immutable after creation in multi-community mode |
| `channel_members` | Membership with roles; soft-delete via `removed_at` |
| `workflows` | Workflow definitions (YAML stored as canonical JSON); scoped by community in multi-community mode |
| `workflow_runs` | Execution records with trigger context and trace |
| `workflow_approvals` | Approval gates (token stored as SHA-256 hash) |
| `audit_log` | Hash-chain audit entries; per-community chain/head in multi-community mode |
| `delivery_log` | Delivery tracking (partitioned; Rust module pending) |

### Redis Key Patterns

| Pattern | Type | TTL | Purpose |
|---------|------|-----|---------|
| `buzz:channel:{uuid}` | Pub/Sub channel | — | Event fan-out (single-community form; shared multi-community Redis must use `buzz:{community}:channel:{uuid}` or equivalent) |
| `buzz:presence:{pubkey_hex}` | String | 90s | Online/away status (single-community form; shared multi-community Redis must scope by community) |
| `buzz:typing:{channel_uuid}` | Sorted Set | 60s | Active typers (5s window; shared multi-community Redis must scope by community) |

### Full-Text Search (Postgres FTS)

Search runs over the `events.search_tsv` generated `tsvector` column on the
`events` table (no separate collection or service). The column is populated on
insert — `to_tsvector('simple', content)` — and excludes privacy-sensitive
kinds via `CASE WHEN kind IN (1059, 30300, 30622) THEN NULL`, so those rows are
storage-level unsearchable (a `NULL` tsvector never matches `@@`). A GIN index
(`idx_events_search_tsv`) backs the `@@` probe; in multi-community mode the
community-leading btree filters BitmapAnd with the GIN probe so every query is
fenced to its `community_id`.

---

## 9. Known Limitations

These are verified gaps in the current implementation — not design aspirations.

| # | Limitation | Detail |
|---|-----------|--------|
| 1 | **No sqlx offline query cache** | Uses `sqlx::query()` (runtime) not `sqlx::query!()` (compile-time). No `.sqlx/` directory. Queries are not validated at compile time. |
| 2 | **No rate limiting implementation** | `RateLimiter` trait exists in `buzz-auth`. Only implementation is `AlwaysAllowRateLimiter` (test stub, gated behind `#[cfg(any(test, feature = "test-utils"))]`). `RateLimitConfig` defines 4 tiers (human, agent-standard, agent-elevated, agent-platform) but none are enforced. |
| 3 | **No dedicated typing REST endpoint** | Typing indicators (kind 20002) are delivered via both local fan-out and Redis pub/sub (cross-node). There is no REST endpoint to query current typers — `/api/presence` returns online/away status only, not typing state. |
| 4 | **Huddle recording/tracks not built** | Voice, room lifecycle, and join/leave/end events are wired (see Huddle Audio above). Recording and per-track publishing have reserved kinds but no producer yet. |
| 5 | **Approval gates not wired end-to-end** | The executor returns `StepResult::Suspended` and the relay has grant/deny API endpoints with DB CRUD, but the engine intercepts before creating `WaitingApproval` rows — runs that hit an approval gate are marked as Failed (🚧 WF-08). |
| 6 | **Workflow actions partially stubbed** | The `send_dm` and `set_channel_topic` workflow actions are in the schema but return `NotImplemented` — a run that reaches one fails at execution (🚧 WF-07). |
