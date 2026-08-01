---
source_ids:
- 22580-from-gpt2-to-kimi3-explained-8f01b0fe
content_mode: faithful_synthesis
label: FAITHFUL SYNTHESIS
---

Twenty-two thousand five hundred and eighty. That's how many GPT-2 models from 2019 fit inside KimiK3 from 2026, 124 million parameters against 2.8 trillion. We scaled up by a factor of 22,580 in seven years. But is it just... scale? Here is how much, or how little, actually changed.

## GPT-2 and the cache

GPT-2 is a decoder-only architecture, and its inefficiency is this: the model computes representations for every input position, but during autoregressive decoding only the logits at the final position are needed to select the next token.

The KV cache comes from a straightforward observation. After appending the generated token, the model would otherwise recompute projections for all previous tokens, so storing their key and value vectors avoids that work. The cache retains vectors for the previous N-1 tokens, grows linearly with the sequence length, and can become large enough to create a memory-bandwidth bottleneck.

## From linear attention to DeltaNet

Softmax attention applies its nonlinearity after the q·k product, coupling every query to every key. Linear attention instead applies a feature map, such as ELU+1, to q and k separately. This makes the product re-associable, so the growing set of K and V vectors can be folded into a fixed D×D state.

The paper's O(N²) framing threw me off. It's not true that "the cost per time-step for transformers scales with the square of the current sequence length". That's what Flash Attention fixes... then I saw that it was released in 2020.

There is a trade-off. The feature map is a less expressive approximation of the softmax kernel, and that can reduce fidelity, although the practical accuracy loss depends on the architecture and workload.

A finite cache must overwrite or combine with information already stored. The state from token i-1 gets no slot of its own; it is added to the same D by D matrix, so new queries can no longer retrieve a perfectly isolated representation of each earlier token. That addition is also the source of the efficiency gain: updating additively rather than by concatenation prevents the cache from growing in O(N), but the same operation causes information to interfere. The regime that makes linear attention attractive, N much larger than D, is where that happens.

DeltaNet addresses this loss of recoverability. Its update first asks what the current key retrieves from the cache, subtracts that from the value we want to store, multiplies the key by the difference, and adds the result back. Old information is removed and new information is written in its place.

Parallelizing that is the most difficult section of the post. It took me about seven hours to develop a working understanding of it. The problem is prefill: the delta rule needs a correction at every key vector, so the path to a parallel matrix multiplication is not obvious. The answer is chunks of size C. Inside a block I do real attention (the masked QKᵀ times V), and across blocks I fold everything into the state and read it back with one matmul. C=N recovers standard O(N²) attention and C=1 gives regular linear attention, the cheapest option in pure FLOP terms but not necessarily in wall-clock time, because a GPU completes more arithmetic faster when the work maps onto its matrix-multiply hardware.

## Gated DeltaNet and Kimi Linear

The delta rule can forget only an association for which it has a specific replacement. It cannot clear several associations during a context switch or decay memory generally to free capacity. That is the Mamba-2 contribution: decay the previous cache, then add the new one at full strength, keeping the state from growing without bound. Decaying every association by one dynamic ratio works, but it ignores their varying importance, so nothing can be forgotten without forgetting the rest equally. The Gated Delta rule combines the two, through an alpha that switches to the pure delta rule at one and clears the memory at zero.

Kimi Linear drew attention for one central claim: under controlled comparisons, it outperformed full attention, a drop-in architectural replacement with better quality and up to 6x higher decode throughput. It improves on Gated DeltaNet with fine-grained gating, learning a separate decay value for each channel instead of a single scalar. That capacity has a specific mathematical purpose: the per-channel scale gives finer control over memory decay. Scaling laws remain relevant, but capacity must be added in the right place and in a form the system can use.

## Kimi K3

The KimiK3 language backbone looks similar to Kimi Linear: 23 four-layer macrocycles, three layers of Kimi Delta Attention and a fourth of Multi-head Latent Attention in each. KDA supplies constant-state recurrent memory, while periodic MLA layers retain full softmax retrieval over the context. At first glance the remaining changes appear modest: more scale, gated MLA, latent-space MoE, SiTU activations, and blockwise attention residuals every 12 layers.

The last of those reaches the residual stream. Normally the input to each layer is the sum of the original embedding and every preceding layer's output, all weighted equally, which gives no selective access. Because that recurrence is purely additive, later layers must also learn increasingly large outputs to influence the accumulated residual, which can destabilize training. AttnRes weights each term of the sum by a query-key dot product, so a layer's learned query retrieves the earlier representations most useful to it. Running that at every layer would cost too much, so KimiK3 runs it at block boundaries every 12 decoder layers, eight blocks in all, for roughly 2% inference latency and a 1.25x compute advantage.

AttnRes and MLA address the same underlying limitation from different directions. KDA layers must inevitably discard information; MLA retrieves from the token context, while AttnRes retrieves from earlier depth-wise representations.

Each architectural step changes what the model stores, how it updates that state, or how it retrieves information that a fixed-size state cannot preserve. A fixed-capacity associative memory needs an eviction policy, since a purely additive linear operation eventually adds interference once at capacity. Learned selection, like gating, routing, or decay, is necessary. Attention is the most effective selective-read mechanism.
