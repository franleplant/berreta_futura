---
source_ids:
- run-ci-cd-for-millions-of-repos-on-your-platform-66c52583
content_mode: article
label: ARTICLE
---

Artifacts stores code, versioned, across millions of repos. The CI SDK now joins that store to build and deploy: a push fires a `cf.artifacts.repo.pushed` event, the event starts an instance of your Workflow, and that Workflow is your pipeline. Each command runs sandboxed inside a Workflow step, so it inherits durable retries, timeouts, persisted state, and step-by-step observability. Install once, cache the snapshot in R2, run lint, test, typecheck and build in parallel, deploy only if they pass. You write it in TypeScript instead of YAML, which means a step can be anything you can put in code, including an agent that repairs a broken build and pushes a commit for your approval.

## A CI/CD pipeline is just a Workflow

A pipeline is a series of steps in a fixed order; if one fails, you stop and report the error. That is a Workflow. Each step becomes a `step.do()`. Defined in YAML, this gets complicated quickly, with the constraints that so often lead to YAML fatigue; defined in TypeScript, it stays yours to configure.

The new tools in the CI SDK run each step in a safe, isolated environment built on Workflows and the Sandbox SDK. Previously you called the Sandbox API directly and carried state between steps yourself. Now each sandboxed command sits in its own Workflow step, with the retries and timeouts Workflows already provide, and step results can be cached so the install does not repeat.

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

await deps.runner({
  name: 'deploy',
  command: 'bun wrangler deploy',
  cloudflareCredentials: {
    accountId: this.env.CLOUDFLARE_DEPLOY_ACCOUNT_ID,
  },
});
```

The install step's dependencies are cached as a sandbox snapshot, stored in an R2 bucket on your account, so later steps read from it. Steps start independently and therefore run concurrently; `Promise.all()` is what holds the deploy back until the checks finish.

## Triggering on push

You could already subscribe to Artifacts through Queues via event subscriptions, but that meant an event subscription, a Queue, a consumer, and a handler. Now a new `events` field inside `triggers` targets a Workflow directly, and every matching push starts an instance.

```
{
  "triggers": {
    "events": [
      {
        "type": "cf.artifacts.repo.pushed",
        // filter is optional. If you don't set repoName we will run the same workflow for every push on any repo in your Artifacts namespace
        "filter": {
          "namespace": "CI",
          "repoName": "my-repo"
        },
        "target": {
          "type": "workflow",
          "workflow_name": "ci-workflow"
        }
      }
    ]
  }
}
```

Omit `repoName` and one pipeline, written once, runs on every repo in the namespace. This is what platforms want: manage the build on their customers' behalf. A customer who prefers their own CI writes their own Workflow, run on their repo alone through dynamic workflows. Platform-managed and custom CI run at the same time, in the same namespace.

Full configuration needs bindings for `artifacts`, `workflows`, `containers` and `durable_objects` (plus `exports` config) to reach your sandboxes, and `r2` if you use `cache`. This is an Artifacts-first integration; coming soon, the `types` will support events from sources across your Cloudflare account.

## Self-healing

Self-healing takes two pieces: the LLM and its agent harness. Add a Durable Object binding for a Think agent on Workers AI, extend `HealingAgent`, wrap the steps in `try/catch`, and call `heal` on failure, rethrowing anything a runner did not report. The source run stays failed; its verified fix lives on another branch. Cloudflare runs the healer in a container alongside the CI steps, so you merge the commit rather than watch the job. A working example is at `github.com/cloudflare/ci/blob/main/examples/self-healing`.

The same opening admits security rules, filters, conditional steps, an AI code reviewer, build artifacts written to R2, an email when CI fails or merges to main.

## What you inherit

Failed steps retry with state persisted, each with its own retry and timeout behavior, and you can restart from a specific step, so a failing lint does not cost you the whole run. Every CI run surfaces as a Workflow instance in the dashboard, with inputs, outputs, wall and CPU time, a diagram of what ran concurrently, and logs through Workers Observability and GraphQL.

## What's next

Direct integrations for Workers and Workers for Platforms, with `build.preview()` and `build.deploy()` primitives for automatic deploys on push to main and previews elsewhere; gradual, percentage-based rollouts managed through Workflows; simplified monorepo deployments under one pipeline; and triggers that accept push events from any version control system, not just Artifacts.

Access is by request to the Artifacts private beta, with a Workflows CI guide to start from.
