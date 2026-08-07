---
source_ids:
- your-agent-needs-a-computer-not-a-container-intr-4851b3c5
content_mode: article
label: ARTICLE
---

The best agents have a computer: files, a shell, the ability to run code and check the result. Today most people supply that with a container each. There is not enough compute on earth to give a container to every agent of every user of every company — the shortage is CPU, not GPU.

So we are shipping an early preview of **@cloudflare/computer**, open source. It gives an agent one declared filesystem and several ways to run code against it: an isolate for most work, a container when the work needs Linux. The agent chooses. Every operation is gated, audited, logged.

## The shortage

Six months ago the norm was to boot a container and run the agent inside it. Since then harnesses have moved the work outward: the brain runs in the agent loop, the hands run in a sandbox reached through a tool. That split is right. Handing each pair of hands a container is not. It cannot reach hundreds of millions of concurrent agents, let alone billions.

Isolates can. We bet on them with Workers nearly ten years ago and again with Durable Objects six years ago, because they start and stop almost instantly, scale sideways without limit, hibernate while the agent is idle, hold the agent's own state in SQLite, and spawn further isolates to run untrusted code. Last year we let an isolate start a container of its own and call it as a tool — infinite horizontal scale, with vertical scale on demand. It works, and it leaves our customers stitching two primitives together by hand. We think one abstraction is better.

## The workspace

A virtual filesystem backed by SQLite, primed from a git repository, a storage bucket, or files you name. Around it, execution runtimes that all answer to `exec(string, options)`:

- **Isolate.** [just-bash](https://justbash.dev/) turns shell into JavaScript inside a dynamic worker; the filesystem arrives through bindings.
- **Container.** Full Linux, mounted over FUSE, changes synced back.

The same file sits in two environments and remains one file. Write your own backend if neither suits.

For direct use there is an API and a `node:fs`-compatible wrapper, so existing JavaScript libraries work unchanged. For agents there is an AI SDK toolkit: read, write, edit, ls, exec. Only `exec` is peculiar — it takes a `backend`, and the tool description tells the model what each one is for. Frontier models pick well, and reach for the container only when they must.

## Using it

```
npm install @cloudflare/computer
```

Attach a `Workspace` to any Durable Object, passing `this.ctx.storage`; add a container backend if you want one; expose `createAITools` beside your own tools. You can also drive the workspace before the model ever speaks — clone the repo, write the bug report to disk, then submit the message that points the agent at both paths.

```ts
await this.workspace.git.clone({ url: report.repoUrl, dir: "/workspace/repo" });
```

The [repository](https://github.com/cloudflare/computer) has the full examples and a step-by-step tutorial.

## What we are aiming at

Agents here already build, test and deploy JavaScript with modern tooling using isolates alone, write per-customer documentation, and drive browsers. We want a runtime where the container is needed for less than a tenth of the work, and coding, audio and video, and document creation are all done in isolates.

Try the [early preview](https://github.com/cloudflare/computer). Tell us what breaks.
