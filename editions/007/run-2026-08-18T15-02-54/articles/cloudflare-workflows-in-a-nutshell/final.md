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

A Workflow is a Worker that can be stopped and resumed. You break the job into steps. Each step runs once, and what it returns is written down. If the engine restarts, finished steps are not run again; execution picks up at the last one that succeeded. Steps retry on a schedule you set, sleep for up to a year, and wait for events from outside. State that lives outside a step does not survive. Available on Free and Paid plans.

## The example

A library lends a book. Take the deposit, wait out the loan, wait for the book to come back, refund.

```ts
export class LoanWorkflow extends WorkflowEntrypoint<Env, Params> {
  async run(event: WorkflowEvent<Params>, step: WorkflowStep) {
    const book = await step.do("fetch book record", async () => {
      return await this.env.KV.get(event.payload.bookId);
    });

    await step.do("charge deposit", async () => {
      // check whether this loan was already charged, then charge
    });

    await step.sleep("loan period", "14 days");

    await step.waitForEvent("wait for return", {
      type: "book-returned",
      timeout: "7 days",
    });

    await step.do("refund deposit", async () => { /* ... */ });
  }
}
```

## What a step buys you

`step.do(name, callback)` runs code and persists the result. Its name is the cache key. Name it deterministically, never with `Date.now()`, or the step re-runs when a later one fails.

Keep steps granular. Fetching the book record and charging the deposit are separate calls to separate services, so they are separate steps. Bundle them and a failure in the charge drags the lookup back through with it.

Ask: do I want all of this to run again if one part fails?

## Sleeping and waiting

`step.sleep("loan period", "14 days")` takes milliseconds or a readable duration. `step.sleepUntil` takes a `Date` or a UNIX timestamp. Maximum sleep is 365 days.

`step.waitForEvent` blocks until something outside sends a matching event. The library's return desk calls `instance.sendEvent({ type: "book-returned", payload })`, over the Workers binding or the REST API. Types must match, and are limited to letters, digits, `-` and `_`. Default timeout is 24 hours; you can set anything from one second to 365 days. On timeout it throws and the instance fails, so wrap it in `try...catch` if the loan should proceed to a late-fee path instead.

An event sent before the Workflow reaches the wait is buffered and delivered when it gets there.

Sleeping and waiting instances do not count toward concurrency limits.

## When things fail

Without configuration, a step retries five times, ten seconds apart, exponential, with a ten-minute timeout per attempt. You can change the limit, the delay, the backoff (`constant`, `linear`, `exponential`), and the timeout. The delay can be a function receiving `ctx.attempt` and the thrown error, useful when the payment processor answers with a rate limit.

Throw `NonRetryableError` for permanent failures. Bad credentials will not improve on the fourth attempt.

Attach a `rollback` handler to `step.do` and it runs when the Workflow later fails, in reverse step-start order. If the return event times out and the instance errors, the rollback on "charge deposit" can release the hold. Check `rollback` on the instance status afterwards to see whether compensation completed.

## Rules the engine imposes

Steps may be retried, so make them idempotent. Check whether the deposit was charged before charging it.

Do not keep state in ordinary variables between steps. The engine hibernates during a long sleep and comes back with memory blank; an array you pushed into across two steps will be empty on the far side of the fourteen days. Build top-level state only from step returns.

Do not mutate `event`. It is immutable across steps and restarts.

`await` every step. An un-awaited `step.do` swallows its errors and loses its return value.

Side effects belong inside steps. A `console.log` outside them may print twice.

The engine forgets; the record remembers.

## Starting one

Bind the Workflow in your Wrangler config with `name`, `binding`, and `class_name` matching the exported class. Then `env.LOAN_WORKFLOW.create({ id, params })` from a `fetch` handler, a queue consumer, a Cron Trigger, or a Durable Object. Instance IDs are unique and cannot be reused, so a loan ID works and a borrower ID does not; compose one, or store a mapping in D1.

For many at once, `createBatch` reduces requests and is idempotent, unlike `create`.

`get(id)` returns an instance you can `status()`, `pause()`, `resume()`, `terminate()`, or `restart()`. Pass `{ rollback: true }` to `terminate` to run compensating handlers first. From the terminal, `npx wrangler workflows instances describe my-workflow latest` shows each step's status, emitted state, sleeps, retries, and errors.

Add `schedules: ["0 * * * *"]` to the binding and each matching cron expression creates an instance, with the expression and scheduled time on `event.schedule`.

## Limits worth knowing

A non-stream step return persists up to 1 MiB. Larger output goes to R2, and the step returns the key. In JavaScript Workflows you can return a `ReadableStream<Uint8Array>` instead; chunks under 16 MB, fresh and unlocked, and it still counts against instance storage.

Event payloads: 1 MiB. Steps per instance: 1,024 free, 10,000 paid and configurable to 25,000. Step timeouts should stay at 30 minutes or less; for longer waits use `waitForEvent`. Retention of completed instance state is 3 days free, 30 days paid.

Wall time per step is unlimited. CPU time is not: 30 seconds by default on paid, raised to five minutes with `limits.cpu_ms`. Subrequests default to 10,000 per instance on paid, configurable up to 10 million.
