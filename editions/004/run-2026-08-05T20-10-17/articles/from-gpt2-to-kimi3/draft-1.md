---
source_ids:
- 22580-from-gpt2-to-kimi3-explained-8f01b0fe
content_mode: faithful_synthesis
label: FAITHFUL SYNTHESIS
---

Twenty-two thousand five hundred and eighty. That’s how many GPT-2 (2019) models fit inside KimiK3 (2026). We scaled up by a factor of 22,580 in seven years. But is it just... scale?

The useful question is what each model does with memory: what it stores, how it updates that store, and how it retrieves information after the store fills.

GPT-2 is a decoder-only architecture. Token and positional embeddings enter a stack of transformer blocks. Each block applies causal self-attention and an MLP through residual connections, then a final hidden state is mapped to vocabulary logits. During autoregressive decoding, the model computes representations for every input position, although each step uses only the logits at the final position. Storing old key and value projections avoids repeating that work. That storage is the KV cache. It retains vectors for the previous N−1 tokens and can become large enough to create a memory-bandwidth bottleneck. The baseline model is about 124 million parameters. KimiK3 has 2.8 trillion, roughly the same as 22,580 GPT-2 models.

The cache’s growth motivates linear attention. Softmax attention applies its nonlinearity after the q·k product, coupling each query to every key. Linear attention applies a feature map such as ELU+1 separately to q and k. That makes the multiplication re-associable, so the growing collection of key and value vectors can be folded into a fixed D×D state. At a high level, both methods make scores non-negative, divide by their sum, and compute a weighted average of values. The trade-off is expressiveness. The feature map is a less expressive approximation of the softmax kernel, so practical accuracy loss depends on the architecture and workload.

A finite cache must overwrite or combine with information already stored. In a fixed D×D state, each new association shares the same space with the old ones. Additive updates eventually interfere, especially in the regime that makes linear attention attractive, where the sequence length is much larger than the state dimension.

DeltaNet makes the write corrective. For the current key, it first reads what the cache already returns, subtracts that from the value it wants to store, and writes only the difference. The old association is removed and the new one takes its place. If the key is normalized, reading with that key can recover the stored value. This gives the model precise replacement, but only when it has a replacement to write. It cannot efficiently clear several associations during a context switch or decay memory in general.

Gating supplies the missing kind of forgetting. A uniformly decaying update, as in Mamba, multiplies the previous state by a learned ratio before adding new information, but it forgets every association together. Gated Delta combines that decay with DeltaNet’s selective replacement. A data-dependent scalar between zero and one controls the previous state: one gives the pure Delta rule, while zero clears the memory. Kimi Linear makes the control finer still, learning a separate decay value for each channel rather than one scalar for the whole state. Under controlled comparisons, its authors reported that it outperformed full attention and presented it as a drop-in replacement with better quality and up to 6× higher decode throughput.

KimiK3 keeps this memory system and adds other ways to retrieve and spend capacity. Its backbone contains 23 four-layer macrocycles. In each, three layers use Kimi Delta Attention and the fourth uses Multi-head Latent Attention. The first layer uses a dense feed-forward network; the remaining layers use a latent Mixture-of-Experts. KDA supplies constant-state recurrent memory, while periodic MLA layers retain full softmax retrieval over the token context.

Gated MLA controls how much of each retrieved feature reaches the residual stream through element-wise multiplication with a gate projected from the input. The MoE has 898 experts: two shared experts process every token, and a router selects 16 of the other 896 for each token. Those experts operate in a compressed latent space, making their forward pass faster and nearly halving the FLOPs.

Scaling laws remain relevant, but capacity must be added in the right place and in a form the system can use. Each architecture in this progression adds capacity to address a concrete limitation in the preceding system. In essence, a fixed-capacity associative memory (fixed dimensions) needs an eviction policy, since a purely additive linear operation eventually adds interference once at capacity.
