---
source_ids:
- run-ci-cd-for-millions-of-repos-on-your-platform-66c52583
content_mode: article
label: ARTICLE
---

We're moving toward a world in which you can store, build, test, and deploy your code fully on Cloudflare. Artifacts, versioned code storage that scales to millions of repos, was the first piece. The CI SDK, built on Cloudflare Workflows, stitches store, build, and deploy together: an `artifact push` event can now trigger a Workflow instance directly, and each CI step runs in its own isolated sandbox. A platform can write one pipeline and share it across every customer's repo, while customers who want their own CI can run it at the same time, in the same namespace.

## A CI/CD pipeline is just a Workflow

A CI/CD pipeline is a series of steps run in a specific order; if any step fails, you stop and report the error. Each step translates to a Workflow `step.do()`, written in TypeScript instead of YAML. Previously, you'd call the Sandbox API directly and manage state yourself across steps. The SDK runs each sandboxed command in its own Workflow step, with the retries and timeouts built into Workflows.

A job needs three things: an `install` step, a command for each check, and a `deploy` step that runs only when the pipeline passes. The install is cached as a sandbox snapshot, stored in an R2 bucket on your account, so later steps don't reinstall and can run in parallel:

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

Steps start independently and run concurrently unless you say otherwise; `Promise.all()` makes every check finish before deploy starts.

## Triggering on push

You could already subscribe to Artifacts through Queues, but that meant an event subscription, a Queue, a consumer, and a queue handler. Now a new `events` field inside `triggers` in your wrangler configuration targets a Workflow directly. Every `cf.artifacts.repo.pushed` event starts an instance, which you can follow step by step in the Workflows dashboard. Omit `repoName` to run the same Workflow on every repo in a namespace:

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

The pipeline also needs `artifacts`, `workflows`, `containers`, and `durable_objects` (plus `exports` config) bindings, and an `r2` binding if you use `cache`. This is an Artifacts-first integration; coming soon, `types` will support events from sources across your Cloudflare account.

## Self-healing

Because the pipeline is code, a step can call an agent. Our example uses a Think agent on Workers AI: you extend `HealingAgent`, pass it whichever model you'd like, and call its `heal` method when a runner fails. It runs in the cloud alongside the CI steps in a container, so instead of babysitting the job, you merge the commit after the agent has made the fix. The source run stays failed; its verified fix lives on another branch.

## What a Workflow gives you

- **Durable execution:** a failed step retries with state persisted, each step has its own retry and timeout logic, and you can restart from a specific step, so if just lint fails, you don't rerun the entire pipeline.
- **Observability:** each instance shows its steps with inputs, outputs, and wall and CPU time, plus diagrams of what runs concurrently, and logs through Workers Observability and GraphQL.
- **Code:** a step can do anything you can put into code, such as an AI code review, writing build artifacts to R2, or sending an email when CI fails, completes, or merges to main.

## What's next

Artifacts is in private beta. Coming next: `build.preview()` and `build.deploy()` for Workers and Workers for Platforms, percentage-based gradual deployments with rollback logic, one CI pipeline for multi-Worker monorepos, and push triggers from any version control system, not just Artifacts.
