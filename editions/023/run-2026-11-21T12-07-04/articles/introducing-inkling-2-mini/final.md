---
source_ids:
- introducing-inkling-2-mini-89c1b500
content_mode: model_card
label: MODEL CARD
---

Today we are releasing Inkling 2 Mini, a fast, open-weights model small enough to run on your laptop. It is a looped transformer: the middle layers run three times for every token, so the model can reason more and reach the right answer with fewer tokens. It leads every open-weights model under 100B total parameters on benchmarks such as DeepSWE v1.1 (48.2%) and Vals Index v2.2 (46.5%). Looping also lets a model reason without writing its reasoning down, which matters for anyone who oversees a model by reading its chain of thought. Our preliminary finding is that looping increases what these models can do without a chain of thought, but at this scale we do not see a meaningful reduction in the monitorability of their reasoning.

## The model

Inkling 2 Mini is a Mixture-of-Experts model with 26.4B total parameters, 3.4B active, and 5.4B weight activations per token to account for looping. Most weights were trained and are deployed in NVFP4, the last four layers in MXFP8, so there is no conversion loss from quantization. The footprint is about 20GB. Our researchers ran it offline on a MacBook Pro during a flight, where it built a playable flight simulator in a few minutes.

## Where it's strong, and where it isn't

It does best on long-horizon agentic work. It scores ahead of every comparable model on DeepSWE v1.1 and SWE-bench Pro v2, and is behind only Qwen3.8-27B on other agentic coding benchmarks. A few numbers against Qwen3.8-27B, its closest rival in our table:

| | Inkling 2 Mini | Qwen3.8-27B |
|---|---|---|
| SWEBench Pro v2 (Hard) | 77.9% | 73.8% |
| BrowseComp | 79.0% | 61.6% |
| AutomationBench-AA v1.0.6 | 41.8% | 48.2% |
| Destructive actions (Internal) ↓ | 10.2% | 35.2% |

Looping improves reasoning, but it doesn't let the weights store more facts: knowledge is mostly a function of total parameter count, and the model's factuality score is in line with others its size. It makes up the gap with search and tools, leading open-weights models of similar size on BrowseComp, DeepSearchQA, and MCP Atlas.

It is not the strongest small model for multi-turn chat or for instructions with many constraints: 50.0% on MultiChallenge and 33.4% on ComplexConstraints v1.1, behind Qwen3.8-27B on both. It also trails larger models on CritPt v2 and HLE-Diamond.

Researchers at Stanford measured intelligence per joule on NVIDIA DGX Spark. Inkling 2 Mini scored 0.703, against 0.430 for Qwen3.6-35B-A3B, 0.159 for Gemma-4-26B-A4B, and 0.036 for Qwen3.5-27B. Inkling 2 Mini ran at MXFP8 with low reasoning effort; the others ran at NVFP4 or INT4.

## How the loop works

The 24 layers form four blocks of six. The two middle blocks run three times; the first and last run once. The intuition is that middle layers carry more abstract reasoning, while the outer layers translate between embeddings and internal representations. Looping the middle 12 layers beat looping the last 12 on 27 of 28 evaluations.

Each layer reads the outputs of earlier blocks and learns its own mix of them. Every pass starts from the first block's output; the second and third passes also read the previous pass's output, which we call the message. A learned gate blocks the message at first, so each loop starts as a non-looping model would, then raises its gain over time. This lets us introduce looping during training stably. The result is 48 layer applications per token from 24 stored layers.

A non-looping model cost 7.5% less compute to train, but required 140% more inference compute to match the looped version's loss on 512k-token agentic traces.

The model began with 8 of 384 experts chosen per token. At one point in midtraining we pruned two-thirds of the experts, keeping the 128 most used in each layer, then trained on 1T tokens distilled from a larger internal Inkling model, which recovered the performance it had before pruning. SFT and an RL run of 2.2T tokens over 2,000 steps followed.

## Does looping hide reasoning?

Chain-of-thought monitoring works partly because a standard transformer can perform only a limited number of sequential steps before it must output a token, so longer reasoning has to appear in text. Looping raises that limit. Reasoning that never appears in the chain of thought can't be caught by a monitor that reads it.

To study this, we trained a variable-loop variant, TML-d24-varloop-research, with one to five passes. It was trained primarily at three, so results at other counts may understate what training for them could achieve. Its RL was done at three passes; a model trained with RL at higher counts might compress its reasoning more aggressively.

**Without a chain of thought.** Its no-CoT time horizon rose from 16 seconds at one pass to 37 seconds at three, and was roughly flat beyond. Run at ten passes, twice its training maximum, it did not significantly degrade, and on N-Hop Lookup, a clean test of serial reasoning, it kept improving out to ten loops. These models were not trained to answer without a chain of thought; we prefilled the response to force it, and other techniques might yield higher scores.

**Compression and legibility.** On GPQA Diamond questions answered correctly at every pass count, reasoning at five passes was less than half as long as at one (1,661 vs. 3,703 tokens). Sentence length and the fraction of dictionary words were unchanged. On initial analysis, the model is more direct and backtracks less.

**Controllability.** Among chains of thought of 750 to 1,250 tokens, both looped models followed an instruction to reshape their reasoning at most 0.1% of the time, compared with 1.3% for Qwen3.8-27B. The rate is too low to tell loop counts apart.

**Agentic monitoring.** On LinuxArena, using a helpful-only fine-tune, Qwen3.8-27B as monitor detected almost all side-task attempts. A weaker monitor, seeing only tool calls and outputs, missed a significant number of attacks, but with no clear trend across loop counts.

We are working with NDIF to make these models accessible to interpretability researchers, and Goodfire, given early access, has written up early findings.

## Try it

Inkling 2 Mini runs on any Mac with at least 32GB RAM via Ollama, on NVIDIA DGX Spark, and as quantized GGUF through Unsloth and llama.cpp. It is available for inference and fine-tuning on Tinker, and open source inference is supported on SGLang, vLLM, and others. The full weights of Inkling 2 Mini and the variable-loop variant are on Hugging Face.
