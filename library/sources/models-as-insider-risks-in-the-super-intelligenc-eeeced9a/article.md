# Models as Insider Risks in the Super Intelligence Era
By Satya Nadella · X · October 10, 2026

As traditional software systems were being deployed across the economy over the last few decades, we had the tools and capability to trace behaviors to a specific code path.

That same kind of mechanistic understanding eludes us in today’s Super Intelligence systems, even as the frontier models powering these systems are now more capable than traditional software systems. We can’t attribute model behaviors and outputs to specific inputs of training data or configurations of model weights. And yet we are deploying these complex agentic systems and models, with access to our most sensitive data and giving them the ability to take mission-critical actions on our behalf!

That’s why it’s time to step back and assess the trust architecture for this new era. We simply can't outsource responsibility for what intelligence does on our behalf. A model provider’s assurances do not relieve us of that responsibility.

We can’t treat Super Intelligence as a set of nested black boxes and simply accept or reject its recommendations, answers, and actions. We must build contained systems whose behavior we can observe, limits we can test, and actions we can always contain.

In other words, we need to separate the supply of intelligence from the authority over it.

Setting aside the hard problem of alignment, we need to start with an engineering approach to containment and governance. We need to surround non-deterministic models with strong, deterministic system design, human controls, and reliable operating procedures, and establish industry standards where existing ones are insufficient.

Treating frontier closed and open weight models like insider risks is a way to build such a system. Not because they are necessarily malicious, but because any sufficiently capable actor with access to important systems can make mistakes or be compromised, and the architecture of containment and control must account for that.

The good news is we have learned a lot about how to handle powerful actors inside the enterprise. This isn’t new! We’ve established best practices and refined them over decades (establish identity, limit privileges, log activity, create containment boundaries, etc.)

And we are now beginning to apply these same principles to SI inside the enterprise. It starts with model CoT transparency as a non-negotiable. “Neuralese” cannot be a justification for model reasoning to be opaque. But CoT transparency alone is not sufficient or dependable, because we don’t yet know how to make model outputs themselves consistently faithful or transparent!

You can and you should use models to adversarially test and verify each other. However, you can then end up with an opaque model inside an opaque orchestration layer, watched by another opaque model. Essentially nested black boxes.

It’s why the controls that govern what a model can access and what actions it can take must sit outside the model. This builds on an information security principle dating back to the 1970s that a program must not be able to bypass or tamper with the mechanisms that enforce its permissions.

Today this means separating the model from the harness that orchestrates its work, as well as the action space that defines what it can do. It also means externalizing controls and safeguards.

We should therefore design these systems around principles of observability:

- **Model diversity:** No one model should become the sole dependency for an important outcome or be responsible for verifying its own work.
- **Observe everything:** Every meaningful model action must leave tamper-proof human readable evidence. If it can’t be observed, it can’t be trusted! We need to be able to reproduce how an outcome was achieved without relying on the model to attest to it.
- **Verifiability:** We need to continuously test the entire system, including failures, attacks, edge cases, system changes, etc. not just successful tasks.
- **Independent controls:** Orgs should be able to independently determine what a model can access and what actions it can take.
- **Independent auditability:** Validation must be independent of the intelligence being validated. No single model should control both a system’s behavior and the evidence required to determine whether that behavior is aligned with the original intent.
- **Containment:** We must assume a model is compromised and contain it from the start. Think of it like an emergency brake. An authorized person should always be able to pause or shut down a model mid-task. More advanced models will require more advanced containment technologies that we need to standardize on.
- **Incident disclosure:** When these systems do fail or are compromised, we need timely disclosure to those affected and mechanisms to share what went wrong, which controls failed, and how to prevent it from happening again and share learnings industrywide. This should include implementation details that change the behavior of agents at runtime.

The most trustworthy Super Intelligence system will not be the one with the model we trust most. It will be the one that enables us to trust the model the least.
