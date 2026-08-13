# Cloudflare Workflows

Build durable multi-step applications on Cloudflare Workers with Workflows.

Available on Free and Paid plans

With Workflows, you can build applications that chain together multiple steps, automatically retry failed tasks,
and persist state for minutes, hours, or even weeks - with no infrastructure to manage.

Use Workflows to build reliable AI applications, process data pipelines, manage user lifecycle with automated emails and trial expirations, and implement human-in-the-loop approval systems.

**Workflows give you:**

- Durable multi-step execution without timeouts
- The ability to pause for external events or approvals
- Automatic retries and error handling
- Built-in observability and debugging

## Example

An image processing workflow that fetches from R2, generates an AI description, waits for approval, then publishes:

```ts
export class ImageProcessingWorkflow extends WorkflowEntrypoint {
	async run(event: WorkflowEvent, step: WorkflowStep) {
		const imageData = await step.do('fetch image', async () => {
			const object = await this.env.BUCKET.get(event.payload.imageKey);
			return await object.arrayBuffer();
		});

		const description = await step.do('generate description', async () => {
			const imageArray = Array.from(new Uint8Array(imageData));
			return await this.env.AI.run('@cf/llava-hf/llava-1.5-7b-hf', {
				image: imageArray,
				prompt: 'Describe this image in one sentence',
				max_tokens: 50,
			});
		});

		await step.waitForEvent('await approval', {
			event: 'approved',
			timeout: '24 hours',
		});

		await step.do('publish', async () => {
			await this.env.BUCKET.put(`public/${event.payload.imageKey}`, imageData);
		});
	}
}
```

## Features

**Durable step execution**

Break complex operations into durable steps with automatic retries and error handling.

**Sleep and scheduling**

Pause workflows for seconds, hours, or days with `step.sleep()` and `step.sleepUntil()`.

**Wait for external events**

Wait for webhooks, user input, or external system responses before continuing execution.

**Workflow lifecycle management**

Trigger, pause, resume, and terminate workflow instances programmatically or via API.
