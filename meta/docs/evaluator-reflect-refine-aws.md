# Evaluator Reflect-Refine Loop Patterns (AWS Prescriptive Guidance)

> Archived for `meta/plans/graph-execution-model.md`.
> Source: <https://docs.aws.amazon.com/prescriptive-guidance/latest/agentic-ai-patterns/evaluator-reflect-refine-loop-patterns.html>
> Retrieved: 2026-08-01

---

[View a markdown version of this page](evaluator-reflect-refine-loop-patterns.md)

[](/pdfs/prescriptive-guidance/latest/agentic-ai-patterns/agentic-ai-patterns.pdf#evaluator-reflect-refine-loop-patterns "Open PDF")

[Documentation](/index.html)[AWS Prescriptive Guidance](https://aws.amazon.com/prescriptive-guidance/)[Agentic AI patterns and workflows on AWS](introduction.html)

Feedback control loopFeedback control loop (evaluator)EvaluatorTakeaways

# Evaluator reflect-refine loop patterns

Tasks such as code generation, summarization, or autonomous decision-making benefit greatly from runtime feedback, enabling the system to evolve through observation and refinement. To operationalize this, the reflect–refine cycle can be implemented as an event-driven feedback control loop – a pattern inspired by systems engineering, adapted for autonomous, intelligent workflows.

The following diagram is an example of an evaluator reflect-refine feedback loop:

### Feedback control loop

A feedback control loop is a pattern that monitors its own outputs and behaviors, evaluates them against defined criteria or a desired state, and then adjusts its actions accordingly. This architecture is inspired by control theory and is foundational in domains such as automation, continuous integration and continuous delivery (CI/CD) pipelines, and machine learning operations.

The following diagram is an AWS architectural example of a feedback control loop:

  1. A deployment pipeline emits a buildComplete event.

  2. The event triggers an automated test or evaluation job that validates the build.

  3. If validation fails (for example, due to failing tests, security issues, or a policy violation), the system:

     * Emits a buildComplete event

     * Logs the issue or sends a notification

     * Triggers a remediation or corrective action, such as rollback, patching, or retry




The loop continues until it produces an acceptable outcome or escalation, or a time out occurs. This pattern is commonly used for the following:

  * Amazon EventBridge rules to route events to evaluation or remediation tasks

  * AWS Step Functions for iterative retry logic and branching on evaluation outcomes

  * Amazon Simple Notification Service (Amazon SNS) or Amazon CloudWatch alarms for feedback triggers and alerts

  * AWS Lambda functions or containerized workers to apply corrective actions




### Feedback control loop (evaluator)

An evaluator workflow is a cognitive feedback loop that's powered by LLMs or reasoning agents. The process consists of the following:

  1. A generator agent or LLM produces an output (for example, a plan, answer, or draft).

  2. An evaluator agent reviews the result using a critique prompt or evaluation rubric.

  3. Based on the feedback, the original agent or a new optimizer agent revises the output.




The loop repeats until the result meets a set of criteria, is approved, or reaches a retry limit.

### Evaluator

  1. A user asks an agent to write a policy summary.

  2. The generator agent drafts it.

  3. An evaluator agent checks coverage, tone, and legal correctness.

  4. If the response is inadequate, it's refined and resubmitted until the feedback loop converges.




This enables self-assessment, iterative refinement, and adaptive output control—all without human input.

The following diagram is an AWS architectural example of a feedback control loop (evaluator):

  1. A user issues a task (for example, draft a business strategy).

  2. An Amazon Bedrock agent generates an initial draft using an LLM.

  3. A second agent (or a follow-up prompt) performs a structured evaluation (for example, "rate this output by clarity, completeness, and tone").

  4. If the rating falls below a threshold, the response is revised by:

     * Reinvoking the generator with an embedded critique

     * Sending the feedback to a specialized refiner agent

     * Iterating until an acceptable response is reached




Optional components like AWS Lambda controllers or AWS Step Functions can manage feedback thresholds, retries, and fallback strategies.

### Takeaways

Where traditional feedback control loops use events, metrics, and remediation logic to validate and adjust system behavior, agentic evaluator loops use reasoning agents to evaluate, reflect, and revise output dynamically.

In both paradigms:

  * Output is evaluated after it's generated

  * Corrective or refining actions are triggered based on feedback

  * System continuously adapts toward a target quality or goal




The agentic version transforms static validation into semantic reflection, enabling self-improving agents that evaluate their own effectiveness.

**Javascript is disabled or is unavailable in your browser.**

To use the Amazon Web Services Documentation, Javascript must be enabled. Please refer to your browser's Help pages for instructions.

[Document Conventions](/general/latest/gr/docconventions.html)

Did this page help you? - Yes

Thanks for letting us know we're doing a good job!

If you've got a moment, please tell us what we did right so we can do more of it.

Did this page help you? - No

Thanks for letting us know this page needs work. We're sorry we let you down.

If you've got a moment, please tell us how we can make the documentation better.
