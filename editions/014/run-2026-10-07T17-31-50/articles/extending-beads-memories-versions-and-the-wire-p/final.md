---
source_ids:
- extending-beads-memories-versions-and-the-wire-p-42b0a8c0
content_mode: article
label: ARTICLE
---

Beads tracks work as Issues joined by Dependencies. But some of what agents need to remember isn't work. A code flow policy can't sensibly be claimed, blocked, or closed. We're extending Beads so Issues and Memories live in one graph of Beads and Links. Citations can pin exact versions, and a protocol, BDP, lets tools read the graph over HTTP and link across stores. A preview runs on our integration branch. None of it has landed in upstream Beads yet.

## Issues that aren't Issues

Steve introduced Beads in October 2025. Less than a year later, the repository has more than 27,000 stars, 1,800 forks, and over 1.5 million downloads as of October 1, 2026. Downloads are not unique users.

An Issue can be claimed, blocked, and eventually closed. Those are useful semantics when the thing you're modeling is work.

Consider a code flow policy: where to branch from, which branch a PR should target, and what checks must pass before merging. An agent needs it while doing the work. But what does it mean to close it? If an implementation Issue depends on the policy, is the work blocked until someone closes it? Treating it as another Issue leaves every caller to remember which Issues aren't really Issues.

Updating the policy is work we can finish. We want an Issue for the change and a Memory for the knowledge it leaves behind, with a Link connecting them.

## Memory

A memory is information we want available beyond the current conversation: a project policy, a decision and its reasoning, or something an agent learned while doing the work. Suppose an agent figures out why an approach won't work, you agree on an alternative, and the session ends. A few days later, another agent proposes the same approach. You get to have the conversation again. Sometimes with the same agent.

Beads already has `bd remember`, `bd recall`, `bd memories`, and `bd prime`. They're useful for a handful of reminders. But a keyed string has no canonical Bead identity, no explicit Links, and no addressable versions with change attribution. An in-flight PR can't cite the exact policy state it followed. And loading every body at startup spends context before the agent knows which ones matter. Chris' Memory Beads proposal is trying to close these gaps.

The proposed Memory Bead has an identity, a title, and a Markdown body. Issues and other memories can link to it. A caller can discover a few promising memories and read only the ones it needs. Changes go into shared Beads History with attribution. A Memory doesn't become ready or blocked, and we don't close it. We can correct it or retire it.

## One graph

We could build a separate memory store, but then every tool would have to learn two answers to the same questions. Instead, we're making the common model explicit.

A Bead is an identified, typed thing with properties. A Link is an identified, typed, directed relationship with properties of its own. An Issue and a Memory are different kinds of Bead. A blocking Dependency is a kind of Link between Issue-typed Beads. Because Links have identity, we can read, change, or remove a particular one without guessing which relationship the caller meant.

Meaning comes from the Type. Closing a prerequisite can make an implementation Issue ready. Editing a policy Memory doesn't. An informational Link to that policy doesn't block just because one endpoint is an Issue. For application-specific data, such as a confidence value or a validity window, both Beads and Links carry an open `metadata` record.

The test is concrete. Can an implementation Issue depend on a prerequisite, cite the policy Memory, and follow that policy's Links to the reasoning behind it, while the existing Issue workflow still makes sense?

## Beads Protocol

The policy might belong to the team and the Issue to one of its repositories. Copying the policy into every project raises a new question: which copy did we use, and which copies need to change?

BDP defines the shared data model and an HTTP interface for it. A tool should be able to read a Bead, inspect its Type, and follow its Links without knowing the database schema behind the server. Each Bead or Link has one Type, identified by a URL, whose descriptor can supply a JSON Schema and endpoint constraints.

BDP calls the owning boundary a Scope. It has a canonical base URL, and each Bead and Link belongs to exactly one. A Link can cross a Scope boundary. The endpoint outside its Scope is carried as a Reference, which is a URL to the Bead elsewhere. Access still requires permission.

There are limits. A local write can't guarantee the other Scope stays online or keeps the policy, and it isn't a transaction across both stores.

## Versioning

Say we introduce a new integration branch and update the policy. Branches and PRs are already in flight under the old one. Read against today's instructions, those choices can look wrong.

So there are two ways to refer to a Bead. You can follow its current state by URL, or you can pin a Reference to one exact retained version. A Type can declare ownership of outgoing Link Types. Changing an owned Link changes the source Bead's version. Merely pointing at another Bead doesn't version the target.

When two agents edit the same record, a guarded write fails if another write has landed. The Memory proposal also allows unguarded writes, but the result must identify the version it replaced and its attribution. Keeping history doesn't excuse a silent overwrite. An old address must keep meaning the same state. A store that can no longer serve that state must say so, never substitute the current version.

## Trying it

The preview is on our integration branch. Some of the model is still being implemented, and the guide and reference may change after publication.

**Danger:** use the preview for new projects only. It may corrupt your Beads data, so keep backups.

You build `bd` from the branch and run an ordinary Dolt SQL server. Then you initialize a fresh directory. BDP serving currently requires shared-server mode. Writes accept the current state by default. `--if-revision` and `--if-source-revision` reject a change based on a stale token. `bd versions` lists versions newest first. Address a version by its token, not its store-local number.

Graph initialization installs guidance in `AGENTS.md`, including Stephanie Jarmak's instructions for remembering useful knowledge, and registers the Claude Stop hook. We'd like your help evaluating whether an agent chooses the right things to remember: what it saves, what it retrieves, and what it misses.

## Where we are

On the integration branch, we can create Issue and Memory Beads and connect them with Links. We can follow those relationships and read and compare exact saved versions, on embedded Dolt and on a shared Dolt server. BDP can read the graph over HTTP. HTTP writes and HTTP History are still ahead. Still ahead too are complete History and lifecycle for Memories, user-installed Types, cross-Scope References, and full compatibility with existing Issue workflows.

Send feedback to the Gas Town Hall Discord's `#beads` and `#memory-beads` channels, or file a Beads issue with a `[Memory]` prefix. Protocol feedback goes to the BDP repo. Include the integration commit you tried.
