---
source_ids:
- run-ci-cd-for-millions-of-repos-on-your-platform-66c52583
content_mode: article
label: ARTICLE
---

We built Artifacts to store code. Now we have stitched storing, building, and deploying together. A CI pipeline is a series of steps that stop when one fails: that is a Workflow. So write it as one, in Typescript, not YAML. An `artifact push` event triggers a Workflow instance directly, and each step runs as a sandboxed command with retries, timeouts, and dashboard observability inherited for free.

## The shape of it

Install once, cache the result, then fan out.

```
const deps: CiRunnerResult = await ci.runner({
  name: 'install',
  command: 'bun install --frozen-lockfile',
  cache: { inputs: ['package.json', 'bun.lock'] },
});

await Promise.all([
  deps.runner({ name: 'lint', command: 'bun run lint' }),
  deps.runner({ name: 'test', command: 'bun run test' }),
  deps.runner({ name: 'typecheck', command: 'bun run typecheck' }),
  deps.runner({ name: 'build', command: 'bun run build' }),
]);
```

The cache is a sandbox snapshot in an R2 bucket on your account, which is why an `r2` binding is required. Steps start independently and run concurrently; `Promise.all()` is how you hold the deploy back until the checks finish.

## Triggering

`events` is a new field inside `triggers`. Point it at a Workflow, with an optional filter naming the namespace and repo, and every matching push starts an instance.

Omit `repoName` and one Workflow covers every repo in the namespace. That is the platform case. Before this you needed an event subscription, a Queue, a consumer, and a handler. Full configuration wants `artifacts`, `workflows`, `containers`, and `durable_objects` bindings, plus `exports` config.

## Self-healing

Two pieces: the LLM and its harness. A Durable Object binding for the agent, a `Healer` extending `HealingAgent`, and a `try/catch` around the steps.

```
export class Healer extends HealingAgent {
 getModel() {
   return '@cf/moonshotai/kimi-k2.7-code';
 }
}
```

Only runner failures get healed; ordinary Workflow errors are rethrown. The fix lands on its own branch as a commit awaiting your approval, and the original run stays failed. Nothing is quietly rewritten. You merge, or you do not.

## Why a Workflow earns its keep

Failed steps retry with state persisted, so no progress is lost. You can restart from a specific step: if lint alone fails, lint alone reruns. Each instance surfaces its steps with inputs, outputs, wall and CPU time, and a diagram showing what ran in parallel. And a step can hold any code at all, which means a reviewer agent, an artifact written to R2, an email on merge to main.

## Soon

`build.preview()` and `build.deploy()` primitives, percentage-based gradual deployments, monorepo support for multi-Worker deploys, and push events from version control systems other than Artifacts.

Artifacts is in private beta; there is a form to request in.
