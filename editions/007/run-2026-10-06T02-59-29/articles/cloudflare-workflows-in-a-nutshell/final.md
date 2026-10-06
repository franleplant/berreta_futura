---
source_ids:
- cloudflare-workflows-f4e217d5
- build-your-first-workflow-544c17fd
- rules-of-workflows-6610cf33
- sleeping-and-retrying-8cbd7233
- trigger-workflows-750b1719
- limits-f870015a
- events-and-parameters-179cef23
content_mode: in_a_nutshell
label: IN A NUTSHELL
---

Cloudflare Workflows lets you build multi-step programs on Workers that survive failure. You break the work into named steps. Each step that finishes has its result saved. If the program is interrupted, it resumes from the last successful step instead of starting over. Steps retry on their own. A Workflow can sleep for hours or days, or stop and wait for an outside event such as a human approval. There is no infrastructure to manage, and it is available on Free and Paid plans. Cloudflare calls this "durable execution": state persists without your writing it to a store.

## The example

Take a hypothetical bakery that sells bread online. Each order runs through four steps: charge the card, wait for the baker to confirm the bread is baked, wait two hours for the pickup window, then email the customer. The helpers `chargeOnce` and `sendReadyEmail` are invented for this example.

```ts
import { WorkflowEntrypoint, WorkflowStep } from "cloudflare:workers";
import type { WorkflowEvent } from "cloudflare:workers";

type Order = { orderId: string; email: string };

export class OrderWorkflow extends WorkflowEntrypoint<Env, Order> {
	async run(event: WorkflowEvent<Order>, step: WorkflowStep) {
		const charge = await step.do("charge card", async () => {
			return await chargeOnce(event.payload.orderId);
		});

		await step.waitForEvent("baker confirms", {
			type: "baked",
			timeout: "24 hours",
		});

		await step.sleep("pickup window", "2 hours");

		await step.do("email customer", async () => {
			await sendReadyEmail(event.payload.email, charge.receiptId);
		});
	}
}
```

The class extends `WorkflowEntrypoint` and implements `run`. In the Wrangler configuration, a `workflows` entry gives it a `name`, a `binding` (say, `ORDERS`), and a `class_name` that must match the exported class.

## Steps

`step.do(name, callback)` runs code and persists what it returns. If the email step fails, the bakery's Workflow retries from there. The card is not charged again, because "charge card" already finished and its result is saved.

The test for where to cut a step is one question: do I want all of this code to run again if just one part fails? External API calls, database queries, and file reads belong in separate steps.

A step's name is its cache key. Name steps deterministically: no timestamps, no randomness. A name built from a previous step's output, traversed in a fixed order, is fine.

## Sleeping and waiting

`step.sleep` pauses for a relative period, such as `"2 hours"`. `step.sleepUntil` pauses until a fixed `Date` or UNIX timestamp. The longest sleep is 365 days.

`step.waitForEvent` pauses until an event of a matching `type` arrives. The type allows only letters, digits, `-`, and `_`. The default timeout is 24 hours, and you can set it between 1 second and 365 days. When it times out, the Workflow throws and the instance fails; wrap the call in `try...catch` to continue anyway.

The baker's tablet would send the event through the binding:

```ts
const instance = await env.ORDERS.get(orderId);
await instance.sendEvent({ type: "baked", payload: {} });
```

An event sent before the Workflow reaches `waitForEvent` is buffered and delivered when it gets there.

Instances that are sleeping, waiting for a retry, or waiting for an event do not count toward concurrency limits.

## Retries and failure

Without your own configuration, a step retries with these defaults:

```ts
{ retries: { limit: 5, delay: 10000, backoff: "exponential" }, timeout: "10 minutes" }
```

You can pass a config as the second argument to `step.do`. Backoff is `constant`, `linear`, or `exponential`. The delay can be a function of the attempt and the error, useful for rate limits. Keep step timeouts at 30 minutes or less; for longer waits, use `waitForEvent`.

Throw a `NonRetryableError` for a permanent failure, such as a card the processor rejects. The instance fails at once and is not retried.

A step can register a rollback handler. When the Workflow later fails, rollbacks run in reverse order of when their steps started. The bakery could release a reservation this way, saga-style. Uncaught errors, or a step that exhausts its retries, end the instance in an `Errored` state unless you catch them.

## Rules

A step may run more than once, so make it idempotent. Before charging, `chargeOnce` should check whether the order was already charged; the processor may have committed the charge before the request died.

Keep each step small. Do not put all logic in one step, call separate services in one step, or do heavy CPU work in one step; on restart, the step begins again from its start.

Workflows may hibernate and lose in-memory state. Build state only from what steps return. A list filled outside a step will be empty after a long sleep.

Code outside `step.do` may repeat. A `console.log` there may print twice. Creating instances, calling `Math.random()`, or branching on `Date.now()` belongs inside a step. Conditions outside steps must rest on the event payload or earlier step results.

The event is immutable. Changes to it are not persisted.

Always `await` steps. A dangling promise can swallow errors and lose return values.

Wrap `Promise.race()` and `Promise.any()` in a `step.do`, or the cached winner may differ from the first one.

A non-stream step result can be at most 1 MiB. In JavaScript, a step may return a `ReadableStream<Uint8Array>` for larger binary output; that still counts toward instance storage. For bigger data, store it in R2 and return a key.

## Triggering

Create an instance from a Worker through the binding:

```ts
const instance = await env.ORDERS.create({ id: orderId, params: order });
```

Instance IDs are unique per Workflow and cannot be reused. The order ID suits the bakery. A user ID alone does not, since one user places many orders. To create many instances, use `createBatch`, which skips IDs that still exist within retention.

You can also trigger through the REST API, `wrangler workflows trigger`, or `schedules`: cron expressions on the Workflow binding, each match creating a new instance.

`instance.status()` returns one of `queued`, `running`, `paused`, `errored`, `terminated`, `complete`, `waiting`, `waitingForPause`, or `unknown`. Instances can also be paused, resumed, terminated (optionally with rollback), or restarted.

## Limits

| | Free | Paid |
| --- | --- | --- |
| CPU time per step | 10 ms | 30 s default, up to 5 min |
| Steps per Workflow | 1,024 | 10,000 default, up to 25,000 |
| Concurrent instances per account | 100 | 50,000 |
| State per instance | 100 MB | 1 GB |
| Retention of completed state | 3 days | 30 days |

Wall-clock time per step is unlimited. Time spent waiting on the network does not count as CPU time.
