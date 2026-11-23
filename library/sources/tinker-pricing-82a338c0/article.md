# Pricing that follows your usage

Thinking Machines Lab · Tinker

## Training

Pricing per

1M tokens

Training, sampling, and prefill.
Rates vary by model and context length.

## Storage

Storage rate per

$0.10 / GB / month

Checkpoint storage for all models

## Serverless inference Beta

Pricing per

1M tokens

Input, output, and cached input.
Available for Inkling 2 Small, Inkling, and Inkling-Small.

## Training & sampling

USD per 1M tokens

| Model | Context | Prefill | Cached | Sample | Train |
|---|---|---|---|---|---|
| Inkling 2 Mini New | 64K | $0.15 | $0.015 | $0.50 | $0.75 |
| Inkling 2 Mini | 256K | $0.15 | $0.015 | $0.50 | $1.50 |
| Inkling 2 Small New | 64K | $0.30 | $0.03 | $1.00 | $1.50 |
| Inkling 2 Small | 256K | $0.30 | $0.03 | $1.00 | $3.00 |
| Inkling | 64K | $1.87 | $0.374 | $4.68 | $5.61 |
| Inkling | 256K | $1.87 | $0.374 | $4.68 | $11.23 |
| Inkling-Small | 64K | $0.58 | $0.116 | $1.44 | $1.73 |
| Inkling-Small | 256K | $0.58 | $0.116 | $1.44 | $3.47 |
| Nemotron-3.5-Super-VL-120B-A12B New 50% off* | 64K | $0.57 | $0.114 | $1.44 | $1.276 |
| Nemotron-3.5-Super-VL-120B-A12B | 256K | $0.57 | $0.114 | $1.44 | $2.32 |
| Nemotron-3.5-Lightning-30B-A3B 50% off* | 64K | $0.184 | $0.0368 | $0.495 | $0.44 |
| Nemotron-3.5-Lightning-30B-A3B | 256K | $0.184 | $0.0368 | $0.495 | $0.80 |
| Nemotron-3-Ultra-550B-A55B 50% off* | 64K | $1.80 | $0.36 | $6.225 | $5.478 |
| Nemotron-3-Ultra-550B-A55B | 256K | $1.80 | $0.36 | $6.225 | $9.96 |
| Nemotron-3-Super-120B-A12B 50% off* | 64K | $0.57 | $0.114 | $1.44 | $1.276 |
| Nemotron-3-Super-120B-A12B | 256K | $0.57 | $0.114 | $1.44 | $2.32 |
| GLM-5.3 | 256K | $3.78 | $0.756 | $12.15 | $14.58 |
| GLM-5.3-Flash New | 256K | $0.84 | $0.168 | $2.11 | $5.58 |
| Kimi-K3.1-Pro New | 256K | $6.00 | $1.20 | $25.00 | $32.00 |
| Kimi-K2.6 | 32K | $2.205 | $0.441 | $5.49 | $4.84 |
| Kimi-K2.6 | 128K | $2.205 | $0.441 | $5.49 | $15.40 |
| Qwen3.8-27B | 64K | $0.6975 | $0.1395 | $5.595 | $4.103 |
| Qwen3.8-27B | 256K | $0.6975 | $0.1395 | $5.595 | $7.46 |
| Qwen3.6-35B-A3B | 64K | $0.45 | $0.09 | $1.335 | $1.177 |
| Qwen3.6-35B-A3B | 256K | $0.45 | $0.09 | $1.335 | $2.14 |
| Qwen3.5-397B-A17B | 64K | $1.65 | $0.33 | $7.50 | $6.60 |
| Qwen3.5-397B-A17B | 256K | $1.65 | $0.33 | $7.50 | $12.00 |
| Qwen3.5-35B-A3B-Base | 64K | $0.54 | $0.108 | $1.335 | $1.177 |
| Qwen3.5-9B | 64K | $0.30 | $0.06 | $0.807 | $1.463 |
| Qwen3.5-9B-Base | 64K | $0.30 | $0.06 | $0.807 | $1.463 |
| Qwen3.5-4B | 64K | $0.33 | $0.066 | $1.005 | $0.737 |
| Qwen3.5-4B | 256K | $0.33 | $0.066 | $1.005 | $1.34 |
| Qwen3-8B | 32K | $0.195 | $0.039 | $0.60 | $0.44 |
| GPT-OSS-120B | 32K | $0.33 | $0.066 | $0.84 | $0.737 |
| GPT-OSS-120B | 128K | $0.33 | $0.066 | $0.84 | $2.33 |
| GPT-OSS-20B | 32K | $0.18 | $0.036 | $0.45 | $0.396 |
| DeepSeek-V4.1-Flash | 256K | $0.60 | $0.12 | $3.60 | $4.98 |
| DeepSeek-V4.1-Flash-1017 New | 256K | $0.60 | $0.12 | $3.60 | $4.98 |

## Serverless inference Beta

USD per 1M tokens

| Model | Context | Input | Cached | Output |
|---|---|---|---|---|
| Inkling 2 Small New | 256K | $0.30 | $0.03 | $1.00 |
| Inkling | 256K | $1.00 | $0.17 | $4.05 |
| Inkling-Small | 256K | $0.30 | $0.06 | $1.20 |

Cached prefill

When sampling, input tokens reused from the prompt cache are billed at the cached prefill rate shown for each model.

Forward passes

Forward-only requests from a training client are charged at the training rate.

Mixture of experts

Mixture-of-experts models are priced by active parameters, rather than total model size.

Beta

Serverless inference is currently in beta.

Models

Currently available for Inkling 2 Small, Inkling, and Inkling-Small only.

Production use

If you're interested in production use, email us at [email protected] to join the waitlist. Please include which models you need, your expected volume and latency requirements, and your use case.

**Inkling 2 Small:** Both the 64K and 256K training options support sampling contexts up to 1M tokens (1,048,576).

[Pricing documentation](https://tinker-docs.thinkingmachines.ai/tinker/models/)

\* Discount reflected in pricing.
