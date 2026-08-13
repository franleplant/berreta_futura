---
source_ids:
- run-ci-cd-for-millions-of-repos-on-your-platform-66c52583
content_mode: article
label: ARTICLE
---

You can now run your CI pipeline on Cloudflare. Artifacts stores the code, versioned, and scales to millions of repos; the CI SDK, built on Workflows, carries a push event straight into a Workflow through a new `events` field in your wrangler configuration. Each push triggers an instance: a CI job. Each step runs a command in an isolated sandbox, the install step's dependencies are cached in a snapshot so later steps don't reinstall, and the deploy runs only if the build succeeded. Because a CI/CD pipeline is just a Workflow, you define it in TypeScript rather than YAML, and you inherit durable retries, per-step timeouts, and step-by-step observability. Wrap the steps in a `try/catch` and an agent can fix a failed step and push a commit for your approval. Artifacts is in private beta.

## The pipeline

A CI/CD pipeline is a series of steps that run in order; if one fails, you stop and report the error. Each step translates to a Workflow `step.do()`. Previously you'd call the Sandbox API directly and manage state yourself across steps. Now the SDK runs each sandboxed command in its own Workflow step, with the retries and timeouts built into Workflows.

Define the `install` step and its lockfile, cache it, then name a command per step. Steps start independently and run concurrently unless specified otherwise, so wrap the checks in `Promise.all()` to make them all finish before the deploy.

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

## Triggering on push

You could already subscribe to Artifacts through Queues, but that meant an event subscription, a Queue, a consumer, and a handler. Now you target the Workflow with the event itself.

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

Omit `repoName` and the same Workflow runs on every repo in the namespace: the shape a platform wants when it writes one pipeline and shares it across all its customers' applications. Customers who want their own CI write their own Workflow, through dynamic workflows; platform-managed and custom CI run at the same time, in the same namespace. This is an Artifacts-first integration; coming soon, the `types` will support events from sources across your Cloudflare account.

The Workflow needs bindings for each piece underneath it: `artifacts`, `workflows`, `containers` and `durable_objects` (+ `exports` config) for the sandboxes, plus `r2`, since the install snapshot is stored in a bucket.

## Self-healing

Self-healing takes two pieces, the LLM and its agent harness. Add a Durable Object binding for the agent, extend `HealingAgent`, and name a model:

```
export class Healer extends HealingAgent {
 getModel() {
   return '@cf/moonshotai/kimi-k2.7-code';
 }
}
```

Then wrap the steps so a failure calls `heal`, passing the error along. The job runs and re-runs remotely, with the healer agent alongside the CI steps in a container; instead of babysitting the run, making a manual fix and rerunning, you merge the commit after the agent has made the fix. The Bring Your Own Workflow model is the general point here: security rules, filters, conditional steps, whatever the team, customer, or application needs.

## What you inherit

Durable execution: a failed step retries with state persisted, no progress lost, each step with its own retry and timeout behavior, and you can restart from a specific step, so a failing lint doesn't cost you the whole pipeline. Observability: every instance shows its steps with inputs, outputs, wall and CPU time, diagrams of what ran concurrently, and logs through Workers Observability and GraphQL. And the power of code: a step can be anything you can write, an AI code reviewer, build artifacts to R2, an email when CI fails.

## Next

Direct `build.preview()` and `build.deploy()` primitives for Workers and Workers for Platforms, percentage-based gradual deployments with custom rollback logic, monorepo support for multi-Worker deployments on one pipeline, and triggers that accept push events from any version control system, not just Artifacts.

Request to join the Artifacts private beta, follow the Workflows CI guide, and send feature requests or bugs to the Cloudflare Developers community on Discord.
