---
source_ids:
- introducing-clef-our-open-source-decision-models-c0a0a5f5
content_mode: article
label: ARTICLE
---

Today we're releasing two Cloudflare-trained decision models, Clef and Clef-flash, hosted on Workers AI and open-sourced on Hugging Face under Apache 2.0. A decision model doesn't write prose. It returns typed answers with probabilities, so an agent can route, escalate, or defer to a human. Clef currently leads the Jev Decision Index, is fully Jev-API compatible, and beats the other decision models on latency, except Laya, which is very fast but trades off quality. We're also debuting a reinforcement learning service to fine-tune Clef: first hands-on with our forward-deployed engineers, later self-serve.

## What a decision model does

Pass in a customer support message and ask whether it's urgent and which team should handle it. The model returns typed answers with probabilities, and your code routes the ticket, triggers an escalation, or defers to a human. A human no longer necessarily needs to be in the loop.

Our Threat Intelligence team has been testing Clef on website domains. With Browser Run, Clef might call a domain 95% fashion, 85% ecommerce, under 1% phishing. It took 2.2s to fetch, render, and classify. Our fastest general LLM, gpt-oss-120b, took 4.7s in the same workflow and returned only two classifications.

In music, a clef sits at the start of the staff and assigns names to its lines and spaces. A decision model likewise defines the domain of the context and the notes that follow. The CF hearkens to Cloudflare.

## How Clef differs

Clef has a vision encoder, so it classifies images; Jev only does text today. Its context window is 64k, against Jev's 32k.

On the benchmarks we shortlisted from the Jev Decision Index, Clef scores competitively, though it doesn't win everywhere:

- Clef leads BANKING77 (94.20 against Jev's 79.74), CLINC150+OOS (97.43 against 89.27), ToolRet, and Amazon ESCI.
- Clef-flash leads BFCL, API-Bank, and Home appliances (97.73 against Jev's 52.27).
- Jev leads When2Call (80.97 against Clef's 72.37) and BRIGHT (47.52 against 45.91).
- DiffusionGemma Jev leads PhishNChips (85.35 against Clef's 79.60).

On Typesafe's own workflow evals, our models beat Jev in 3 of 4 areas: invoice processing, customer service, and security incidents. Jev leads agent trace observability.

Across the 43 benchmarks we ran, median latency was 209.3 ms for Clef, 38.8 ms for Clef-flash, and 524.1 ms for Jev. Laya's median is 5.8 ms. Clef-flash has the best p95, at 122.4 ms. Hosting on our edge GPUs also lowers network latency, so Clef can sit in an agent's hot path, paired with one of our LLMs on Workers AI to take the action.

Clef is the precision model; Clef-flash is for latency-critical decisions. We don't read, store, or train on your requests or responses, unless you use our fine-tuning product.

## How we trained it

We began by adapting DiffusionGemma to output deterministic probabilities by exposing its logprobs, building on independent research by Matt Mastracci. Clef uses Qwen as its backbone instead, post-trained for decisions. At inference, Qwen runs a prefill-only pass, then the valid schema choices are scored in parallel. Nothing is generated token by token, which makes Clef significantly faster than autoregressive LLMs. Each valid choice extracts context relevant to the prompt, fields cross-attend with one another and with the payload before scoring, and a lexical prior preserves semantic intent across options.

We froze Qwen3.8-27B for Clef and Qwen3.5-9B for Clef-flash, and jointly optimized a routing head with rank-256 low-rank adapters. Training uses label-smoothed cross-entropy on valid schema outputs plus a Brier loss for calibration, over internal synthetic datasets that permute field orders, prompts, and schemas. A secondary target, Reinforcement Learning for Calibrated Decisions (RLCD), gives partial credit to adjacent ordinal choices, rewards fully precise records, and penalizes drift from a reference to prevent distribution shift.

## Fine-tuning and the RL service

Internal teams want Clef fine-tuned to evaluate Trust & Safety submissions, triage Support requests, and tell good bots from bad. Fine-tuning may give up some general-purpose performance in exchange for accuracy in one domain. With more than 15 years of network data, we can fine-tune models for these cases that are more accurate and faster than the generic Clef.

For customers, we're starting with our hands-on FDE team, and will use what we learn to build a self-serve platform to capture data, fine-tune, and redeploy, all on Cloudflare. It joins primitives we already have, several still in progress:

- AI Gateway builds a dataset from your AI traffic.
- Workers AI generates rollouts against the base Clef.
- Containers provide the RL sandbox for scoring and replaying agent actions.
- Trainer, new, updates the fine-tuned weights.
- Workers AI with Bring Your Own Model redeploys the result.

We're still early, with more improvements in store. The weights are on Hugging Face, and we'd like to hear from customers with fine-tuning use cases.
