---
source_ids:
- 22580-from-gpt2-to-kimi3-explained-8f01b0fe
content_mode: faithful_synthesis
label: FAITHFUL SYNTHESIS
---

Twenty-two thousand five hundred and eighty. That’s how many GPT-2 (2019) models fit inside KimiK3 (2026). We scaled up by a factor of 22,580 in seven years. The path between them is a series of repairs to memory: what the model stores, how it updates that state, and how it retrieves information when the state cannot hold everything.

GPT-2 is a decoder-only transformer. It adds token and positional embeddings, then runs a stack of blocks, each with causal self-attention and an MLP connected by residual updates. A final language-model head maps hidden states to vocabulary logits. At decode time, only the final position’s logits choose the next token, though the model computes representations for every input position. Without caching, appending a token causes projections for all earlier tokens to be recomputed. The KV cache stores their keys and values, saving that work, but it grows with the sequence and can become a memory-bandwidth bottleneck. A model with about 50k possible tokens, 12 blocks, 12 heads, and an embedding dimension of 768 is about 124M parameters. KimiK3 has 2.8T, roughly 22,580 such models.

## Linear Attention

The paper’s O(N²) framing threw me off. Softmax attention applies its nonlinearity after every q·k product. Linear attention applies a feature map such as ELU+1 to q and k separately, so the product can be re-associated and the growing key/value history folded into a fixed D×D state. It keeps attention’s three moves: make scores nonnegative, divide by their sum, and take a weighted average of values. The feature map is less expressive than softmax, so fidelity can fall; practical accuracy loss depends on the architecture and workload. The fixed state removes the cache’s linear growth, although memory reads and writes still matter. At the time, training often materialized the full N×N matrix, and reference autoregressive implementations often recomputed history without a KV cache.

## DeltaNet (Fast Weight Programmers)

A finite D×D state must combine new information with old information. Additive linear attention writes into the same matrix, so once N is much larger than D, associations interfere and a query cannot recover an isolated earlier token. The regime that makes linear attention attractive, where N is much larger than D, also exposes its main limitation.

DeltaNet changes the write. For each key, it first reads what that key already retrieves, subtracts that old value from the value it wants to store, and writes the difference. With a normalized key, reading by the same key can return the value itself. This lets the model replace a specific fact. It still cannot efficiently clear many unrelated facts or decay memory in general. It can correct a fact when a replacement exists, but it has no general way to free capacity.

## Gated Delta Net

That gap is where gating enters. Mamba-style decay multiplies the old state by `alpha` before adding the new state, so every association fades together. Gated Delta combines this general forgetting with Delta’s targeted replacement: `alpha=1` recovers pure Delta, `alpha=0` clears memory, and intermediate values control how much previous state survives. The result is a data-dependent decay rather than one fixed rule.

## KDA/Kimi Linear

Kimi Linear makes decay fine-grained, learning a separate value for each channel. The authors reported that, under controlled comparisons, it outperformed full attention and presented it as a drop-in replacement with up to 6x higher decode throughput. The hybrid also interleaves Multi-head Latent Attention (MLA) and replaces the MLP with a Mixture-of-Experts (MoE). The extra capacity has a specific mathematical purpose: the per-channel scale gives the model finer control over memory decay.

## KimiK3

KimiK3 keeps that pattern. Its backbone contains 23 four-layer macrocycles. Three layers use Kimi Delta Attention and the fourth uses MLA; the first layer uses a dense feed-forward network, and the others use a latent MoE. KDA supplies constant-state recurrent memory, while periodic MLA retains full softmax retrieval over the context. Gated MLA controls how much of each retrieved feature enters the residual stream.

The MoE has 898 experts. Two are shared and process every token; a router selects 16 of the remaining 896 for each token. KimiK3 also changes the expert activation to SiTU. Without a fused kernel, that path is nearly three times slower than the original, while compressed latent experts nearly halve the FLOPs.

Each architecture in this progression changes what the model stores, how it updates that state, or how it retrieves information a fixed-size state cannot preserve. In essence, a fixed-capacity associative memory (fixed dimensions) needs an eviction policy, since a purely additive linear operation eventually adds interference once at capacity. To that end, learned selection, like gating, routing, or decay, is necessary, and attention is the most effective selective-read mechanism.
