---
source_ids:
- 22580-from-gpt2-to-kimi3-explained-8f01b0fe
content_mode: faithful_synthesis
label: FAITHFUL SYNTHESIS
---

Twenty-two thousand five hundred and eighty. That's how many GPT-2 models from 2019 fit inside KimiK3 from 2026, 124 million parameters against 2.8 trillion. But is it just... scale?

**Editor's note.** Condensed from a worklog ali posted on 27 July 2026, reading forward from GPT-2 to KimiK3 through the papers as they arrived: linear attention, Parallelizing Linear Transformers with Delta Rule, Mamba-2 and Kimi Linear. The first person below is his.

## GPT-2 and the cache

GPT-2 is a decoder-only architecture with one built-in inefficiency. It computes representations for every input position, but during autoregressive decoding only the logits at the final position select the next token. Without a cache, appending each generated token makes the model recompute projections for all the previous ones.

The KV cache stores those key and value vectors instead. It retains vectors for the previous N-1 tokens, grows in O(N) with the sequence length, and can become large enough to create a memory-bandwidth bottleneck.

## From linear attention to DeltaNet

Softmax attention applies its nonlinearity after the q·k product, coupling every query to every key. Linear attention instead applies a feature map, such as ELU+1, to q and k separately. This makes the product re-associable, so the growing set of K and V vectors folds into a fixed D×D state.

The paper's O(N²) framing threw me off until I checked its date. It's not true that "the cost per time-step for transformers scales with the square of the current sequence length". That's what FlashAttention fixes... then I saw the paper itself was released in 2020. At the time, training commonly materialized the full N×N attention matrix, FlashAttention did not exist, and reference implementations often recomputed the token history without a KV cache.

The trade-off is fidelity. The feature map is a less expressive approximation of the softmax kernel, and that can reduce accuracy, although the practical loss depends on the architecture and workload.

A finite cache must overwrite or combine with information already stored. The state from token i-1 gets no slot of its own; it is added to the same D×D matrix, so new queries can no longer retrieve a perfectly isolated representation of each earlier token. That addition is also the efficiency gain, since updating additively rather than by concatenation keeps the cache from growing in O(N). The regime that makes linear attention attractive, N much larger than D, is where the interference shows.

DeltaNet addresses this loss of recoverability. Its update first asks what the current key retrieves from the cache, subtracts that from the value we want to store, multiplies the key by the difference, and adds the result back. The rule removes the old information and writes the new in its place.

Parallelizing that was the hardest part. It took me about seven hours to develop a working understanding of it. Prefill is where it hurts, the pass over a whole input sequence before the first token comes out. The delta rule needs a correction at every key vector, so the obvious implementation walks the tokens one at a time and never collapses into a single matrix multiply.

Purely additive linear attention has a way out. Split the sequence into blocks of C tokens. Inside a block I do real attention (the masked QKᵀ times V), and across blocks I fold everything into the state and read it back with one matmul. Within a block that means comparing every query against every key, masked so no token sees the ones after it; everything before the block arrives as one matrix multiply against the running state. The quadratic term is now the score matrix inside a block and nothing else, so the smaller I make C, the fewer FLOPs (arithmetic operations) I do. Set C to the whole sequence and you are back to standard attention. Set it to 1 and you have regular linear attention, the cheapest in pure FLOP terms but not necessarily in wall-clock time, because a GPU completes more arithmetic faster when the work maps onto its matrix-multiply hardware.

That block trick does not directly apply to the delta updates. We need every single state in order to compute the information that needs to be subtracted out, and we can't parallelize it the same way without some mathematical re-parameterization. The authors therefore rewrite the delta updates as a first-order linear recurrence, and that form lets the blocked code compute all C deltas at once.

## Gated DeltaNet and Kimi Linear

The delta rule can forget only an association for which it has a specific replacement. It cannot clear several associations during a context switch or decay memory generally to free capacity. Mamba-2 supplies the other half: decay the previous cache, then add the new one at full strength, so the state stops growing without bound. But one dynamic decay ratio applied to every association ignores their varying importance. The Gated Delta rule combines the two through an alpha that switches to the pure delta rule at one and clears the memory at zero.

Kimi Linear drew attention for one central claim, that under controlled comparisons it outperformed full attention. The authors presented it as a drop-in architectural replacement with better quality and up to 6x higher decode throughput. It improves on Gated DeltaNet with fine-grained gating, a separate decay value for each channel instead of a single scalar. Scaling laws remain relevant, but capacity must be added in the right place and in a form the system can use.

## KimiK3

The KimiK3 language backbone looks similar to Kimi Linear, 23 four-layer macrocycles with three layers of Kimi Delta Attention (KDA) and a fourth of Multi-head Latent Attention (MLA) in each. KDA supplies constant-state recurrent memory, while the periodic MLA layers retain full softmax retrieval over the context. Every layer after the first swaps the feed-forward network for a latent Mixture-of-Experts, 898 in all, two shared and run on every token, with the router picking 16 of the remaining 896. The experts work in a compressed latent space, which nearly halves their FLOPs.

At first glance the changes from Kimi Linear appear modest, until the last of them, blockwise attention residuals (AttnRes).

Normally the input to each layer is the sum of the original embedding and every preceding layer's output, all weighted equally, which gives no selective access. Because that recurrence is purely additive, later layers must also learn increasingly large outputs to influence the accumulated residual, which can destabilize training. AttnRes weights each term of that sum by a query-key dot product, so a layer's learned query retrieves the earlier representations most useful to it. Running that at every layer would cost too much, so KimiK3 runs it every 12 decoder layers, eight blocks in all, for roughly 2% added inference latency against a 1.25x compute advantage.

AttnRes and MLA address the same limitation from different directions. KDA layers must inevitably discard information; MLA retrieves from the token context, AttnRes from earlier depth-wise representations.

So, not just scale. A fixed-capacity associative memory needs an eviction policy, since a purely additive linear operation eventually adds interference once at capacity, and learned selection is what supplies one. Every step since GPT-2 buys a better way to decide what to throw away. The best selective-read mechanism we have is still attention.
