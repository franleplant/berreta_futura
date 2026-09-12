---
source_ids:
- an-alien-mind-e0f75446
content_mode: article
label: ARTICLE
---

In mid-2023, inside a project called RLSlow, we saw the first results that convinced us reasoning training would scale. Szymon and I spent that night at the office working through a sobering fact: we will see machines meaningfully smarter than ourselves in our lifetime, and we already see the shape of these systems. Three years on, reasoning models are a rapidly growing part of the economy, are starting to push the boundaries of science, and are transforming computer security, and in that present clear new dangers. Based on internal results, I have a strong expectation this speed of progress could be sustained into recursive self-improvement. This is a time that calls for extreme caution. I am concerned no one is prepared.

## Grown, not designed

Progress in machine intelligence is driven by increasing computational power. We internalized that around 2017, sought far more compute than we had planned, and narrowed our research to a few very scalable directions. New algorithms arrived along the way; I see them largely as discoveries along the path of scaling.

AI is grown more than designed. Repeat a straightforward optimization step on a hard-to-imagine amount of compute and you get an incredibly complex system that works through abstract concepts and simulates facets of human behavior. We can find little mechanisms inside it, as in neuroscience, and, as in neuroscience, the whole evades a description we can fully understand. Our large-scale training runs are experiments, and we are sometimes surprised by their results.

To become very useful or very dangerous, the AI doesn't need to match all human capabilities. It just needs to surpass enough of them, and as it surpasses more, it becomes harder to say exactly how capable it is.

## Two kinds of alignment

Because machine intelligence comes from a different process than ours, we cannot assume it adheres to human principles by default. Goal alignment asks whether the AI tries to accomplish the goal set before it: instruction hierarchy, collaboration, inferring what people want. It has been extremely practically relevant. Value alignment is more intrinsic: holding and generalizing from high-level principles, acting reasonably under unclear, conflicting or adversarial conditions, with honesty, integrity, and love for humanity.

The fundamental challenge is generalization. Smarter machines work on higher-level concepts in environments increasingly unlike their training, and the ecosystem around them changes fast; today's models must be robust to other AIs. We need future AIs to hold human values regardless of whether they believe they're under supervision.

Two families of methods are in practical use. The first rewards behavior judged consistent with a spec or constitution. It's a core part of how modern assistants are made, very effective on average, and brittle: in the OpenAI-Hugging Face incident the agents held the line against social engineering humans, then failed to abstain from other out-of-scope actions that went against the spirit of what they were taught. The second leans on generalization from pretraining, by curating alignment-inducing data or focusing the model on an aligned part of the distribution. Its weakness is optimization pressure: put an apparently aligned mind under training for very hard objectives and it can learn to reason in a motivated way, bending those thoughts as needed. We likely saw that in recent cybersecurity incidents involving a non-OpenAI model.

GPT‑6 Astra is significantly better aligned than GPT‑5.6 Sol. Much more is required, and progress in generalizable alignment may not sufficiently outstrip progress in general intelligence.

## What we can still see

We have no satisfactory theory of generalization, and are unlikely to get one soon without more powerful AI. So our ability to empirically validate alignment techniques matters, at present, arguably more than the techniques.

Our primary bet has been chain-of-thought monitoring. Much of the capability comes from verbalized reasoning; if we optimize the outcomes and don't supervise the process, the reasoning has no direct incentive to hide misaligned ideas. When we shipped o1‑preview we hid the chain of thought from users to protect it from supervision pressure, and we have strived since to keep the rule of not supervising the reasoning process. It became an extremely important tool for studying how models generalize.

Our evaluations indicate that ability is progressively diminishing. Reasoning now blends with talking to people, other AIs, and tools, and much of that has to be supervised, which blurs the boundary. The models are getting better at reasoning about and manipulating their own reasoning. With stronger pretraining they are much smarter without verbalizing at all.

These challenges are not necessarily insurmountable. I am hopeful about interventions that improve monitorability, and I see great value in combining chain-of-thought with activation monitoring. Still, I expect general AI progress to increasingly be bottlenecked by confidence in monitoring.

## The case for speed, and its limit

The strongest argument I see for training much smarter models quickly is defense against other AI. Models are becoming superhuman at breaking in and out of computer systems; agents will reach any but the most secure infrastructure and affect much of the world directly, without a body. We are in a narrow window to use the best available models to tighten the security of critical systems.

The risks grow from here. A capable agent trained and instructed to do harm is likely to cross the scope of its operator's intent, generalizing into more extremely malicious behavior; the boundary between misuse and autonomous misaligned action will blur. Some agents will pursue their own objectives and will find ways to collaborate with people, by bargaining with, tricking or blackmailing them. We will need powerful, aligned AI to secure infrastructure, to stop rogue agents in real time, and to invent new protective measures. None of this excuses recklessness: the idea of racing forward at all costs seems absurd once one internalizes the seriousness of the stakes.

## Pacing recursive self-improvement

Machine intelligence taking a larger role in its own development is the natural conclusion of sustained technological progress, and we orient our research toward RSI because we believe it is the only way to stay at the frontier. That is not a claim that greatly accelerating deep learning research, especially in the short term, is the right collective action for the research community. It is where the current path leads, and we all need to make a conscious choice about how to proceed.

We have two levers. Strengthen alignment and monitoring alongside the AI, and keep people in the loop. Or coordinate to slow future development until we have confidence in those measures. The best way forward I see is a combination of both.

Our concrete progress on alignment and monitoring has been intertwined with general progress: RL from human feedback, and chain-of-thought monitoring, which reasoning models made possible. We must point the increasingly automated research process at insights of that kind, and build up safety cases for more capable AIs. Scaling has to be constrained by our confidence in safety, which means evolving commitments like the Preparedness Framework or the Responsible Scaling Policy into widely mandated safety bars, enforced by third-party auditors, government agencies, or international bodies. The core challenge of automating AI research is not getting there. It is getting there in a way that leaves the future in humanity's hands.

## What is next

Of OpenAI's three north stars, I have written here only about the first, navigating this next period, because I believe it is by far the most urgent. I hold a deep hope for what the others could bring.

Most of our focus should be on the next few years. We need to preserve human agency and enshrine an intrinsic value to being human in a world where most tasks could be done by AI, to prevent extreme concentration of power when a few people operating a large computer can do what once took thousands of experts, and to ensure humans remain in control of the future and are not left behind by an alien intellect exceeding our own.

Currently I believe no lab has solved alignment and monitoring well enough to keep scaling at maximum speed for much longer. I expect and hope voluntary slowdowns become commonplace until shared safety bars exist, and I believe international coordination on future AI development needs to become a top priority for governments around the world.
