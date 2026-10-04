---
source_ids:
- introducing-clef-our-open-source-decision-models-c0a0a5f5
content_mode: article
label: ARTICLE
---

Today we're releasing two Cloudflare-trained decision models, Clef and Clef-flash. They're hosted on Workers AI and open-sourced on Hugging Face under Apache 2.0. A decision model doesn't write prose. It returns typed answers with probabilities that your code can act on. Clef currently leads the Jev Decision Index. It's fully Jev-API compatible, reads images, and takes 64k of context. It doesn't win everywhere: Jev leads some benchmarks, and Laya is faster. We're also debuting an RL product to fine-tune Clef. It starts hands-on with our forward-deployed engineers, and a self-serve platform comes later.

## What a decision model does

Suppose you pass in a support message and ask two things: is it urgent, and which team should handle it? The model returns typed answers with probabilities. Your code then routes the ticket, triggers an escalation, or defers to a human. A human doesn't necessarily need to be in the loop anymore. Agents can gather context, decide, and act, or defer to a human when needed.

Our Threat Intelligence team has been testing Clef to classify domains. Given a domain, and using Browser Run, Clef might return:

- 95% fashion
- 85% ecommerce
- under 1% phishing

It took 2.2s to fetch, render, and classify. Our fastest general LLM, gpt-oss-120b, took 4.7s in the same workflow and returned only two classifications.

In music, a clef sits at the start of the staff and assigns names to its lines and spaces. A decision model does the same work: it defines the domain and the notes, the actions, that follow.

## How Clef differs

Clef has three distinguishing properties:

- **Vision.** It has a vision encoder. Jev only classifies text today.
- **Context.** Its window is 64k, against Jev's 32k.
- **Accuracy.** It scores competitively against other decision models.

The results are mixed:

- **Jev Decision Index benchmarks.** Clef or Clef-flash leads seven of ten. Jev leads When2Call and BRIGHT, and DiffusionGemma Jev leads PhishNChips. The two Clefs also differ a lot on some benchmarks. On CLINC150+OOS, Clef scores 97.43 and Clef-flash 66.77. On home appliances, Clef-flash scores 97.73 and Jev 52.27.
- **Typesafe's workflow suite.** Clef models beat Jev in three of four areas. Jev wins agent trace observability (71.6, against Clef-flash's 69.8).
- **Latency.** Across 43 benchmarks, Clef models beat the other decision models, except Laya. Laya is very fast but trades off quality. Median latencies:

| Model | Median latency (ms) |
| --- | --- |
| Laya | 5.8 |
| Clef-flash | 38.8 |
| Clef | 209.3 |
| Jev | 524.1 |

At p95, Clef-flash is fastest, at 122.4 ms.

Workers AI runs on our GPUs at the edge, which keeps network latency low. That means you could put Clef in an agent's hot path and pair it with one of our LLMs to take the action.

A request sends a `state` and named `questions`. Each question is typed: a yes/no, a choice among labelled criteria, or a score on an ordered scale.

Use Clef when you need precision and Clef-flash when the decision is latency-critical. We don't read, store, or train on your requests or responses, unless you use our fine-tuning product.

## How we trained it

The week Jev came out, we posted experiments that adapted DiffusionGemma to output deterministic probabilities by exposing an LLM's logprobs. That work built on independent research by Matt Mastracci.

Clef keeps the idea but uses Qwen as the backbone. At inference, Qwen runs a prefill-only pass, and then the valid schema choices are scored in parallel. Nothing is generated token by token, so Clef is significantly faster than autoregressive LLMs. A two-stage attention routing step comes before scoring. Each choice extracts the context relevant to it, and the fields cross-attend with one another and with the original payload.

For the backbones, we froze Qwen3.8-27B for Clef and Qwen3.5-9B for Clef-flash. On top of them, we trained a routing head with rank-256 low-rank adapters. The training data is internal and synthetic, and it permutes field orders, prompts, and schemas. The losses are label-smoothed cross-entropy, plus a Brier loss for calibration.

A secondary target, Reinforcement Learning for Calibrated Decisions (RLCD), does three things:

- gives partial credit for adjacent ordinal choices
- rewards fully precise records
- penalizes drift from the reference

The result has three parts: better classification accuracy, output constrained to probabilities, and speed beyond both Jev and the base Qwen models.

## Fine-tuning and RL

Internal teams want Clef tuned for specific jobs:

- evaluating Trust & Safety submissions
- triaging Support requests
- telling good bots from bad in our Bot products

Fine-tuning may give up some general performance in exchange for accuracy in one domain. We have more than 15 years of network data, so we can tune models that are more accurate and faster than generic Clef for these cases.

Customers get the same service, first hands-on with our FDE team. What we learn there goes into a self-serve platform for capturing data, fine-tuning, and redeploying, all on Cloudflare. It's built from work-in-progress pieces:

- **AI Gateway:** turns your AI traffic into a dataset.
- **Workers AI:** generates rollouts against base Clef.
- **Containers:** an RL sandbox for scoring and replaying agent actions.
- **Trainer (new):** updates the fine-tuned weights.
- **Workers AI + Bring Your Own Model:** redeploys the model, using the Cog work that has been progressing since our acquisition of Replicate.

We're still early. We believe Clef has the ability to disrupt the way we use agents. The models are on Workers AI and the weights are on Hugging Face. If you have a fine-tuning use case, reach out.
