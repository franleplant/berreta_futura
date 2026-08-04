---
source_ids:
- 22580-from-gpt2-to-kimi3-explained-8f01b0fe
content_mode: faithful_synthesis
label: FAITHFUL SYNTHESIS
---

Twenty-two thousand five hundred and eighty. That's how many GPT-2 models from 2019 fit inside KimiK3 from 2026, 124 million parameters against 2.8 trillion. The two do not store the same kind of thing. GPT-2 kept a key and a value vector for every token it had seen, and that store grows with the sequence until reading it back is the bottleneck. KimiK3 keeps a state of fixed size and writes over it. Everything in between is an argument about what gets written over.

## GPT-2 and the cache

GPT-2 is a decoder-only architecture that wastes work as it decodes. It computes representations for every input position, but each decode step consumes only the final position's logits, and without caching it would recompute the projections for the whole prefix every time it appended a token. Storing the earlier keys and values removes that work and creates the next problem: the KV cache grows with the sequence, every decode step reads all of it, and it can get large enough to create a memory-bandwidth bottleneck.

## From linear attention to DeltaNet

Softmax attention applies its nonlinearity after the q·k product, coupling every query to every key. Linear attention applies a cheaper function to q and k separately, before they interact, which makes the product re-associable: the growing set of key and value vectors folds into a state whose size is set by the head dimension, never by the number of tokens. The trade-off is fidelity: that cheaper function is a less expressive approximation of the softmax kernel, and how much accuracy it costs depends on the architecture and the workload.

The linear attention paper's framing threw me off. It's not true that "the cost per time-step for transformers scales with the square of the current sequence length". That's what Flash Attention fixes... then I saw that it was released in 2020. At the time, training commonly materialized the full attention matrix, and reference implementations often recomputed the token history without a KV cache.

A finite state has to overwrite or combine with what it already holds. The previous token gets no slot of its own, so a new query can no longer retrieve a perfectly isolated representation of each earlier token. That addition is where the efficiency comes from, and the regime that makes linear attention attractive, far more tokens than the state has room for, is where the associations start to interfere.

DeltaNet buys the recoverability back by reading before it writes. The state is a board of fixed capacity, and the update asks what this key already holds on it, subtracts that from the value we want to store, and writes the difference back in its place.

Getting that to run in parallel was the hardest part, and it took me about seven hours to develop a working understanding of it. Purely additive attention splits into blocks that each run as ordinary attention, but the delta updates will not: we need every single state in order to compute the information that needs to be subtracted out, and we can't parallelize it the same way without some mathematical re-parameterization. The authors of Parallelizing Linear Transformers with Delta Rule supply one, and a whole block of corrections falls out at once.

## Adding the ability to forget

The delta rule can only forget an association it has a specific replacement for. It cannot clear several at a context switch, or let memory decay to free capacity. Mamba-2 supplies that half: decay the previous cache, then add the new one at full strength, so the state stops growing without bound. But one ratio applied to everything ignores that associations differ in importance: a model that needs to forget one forgets all of them equally. The Gated Delta rule combines the two through an alpha that is the pure delta rule at one and clears the memory at zero.

Kimi Linear then gives every channel its own decay value instead of one scalar, so a layer can drop one association without flattening the rest. It drew attention for a stronger claim than that: under controlled comparisons it outperformed full attention, offered as a drop-in replacement with better quality and up to 6x higher decode throughput.

## KimiK3

The KimiK3 backbone looks a lot like Kimi Linear: four-layer macrocycles, three layers of Kimi Delta Attention and a fourth of Multi-head Latent Attention in each, so the model runs a memory it overwrites alongside a memory it can still read whole. Every layer after the first swaps the feed-forward network for a bank of experts, of which a router wakes a handful per token and leaves the rest asleep.

The last change leaves the sequence alone. Normally each layer is handed the sum of the original embedding and every preceding layer's output, weighted equally, whether that suits it or not. Blockwise attention residuals weight each term of that sum by a query-key dot product, so a layer's learned query retrieves the earlier representations most useful to it. Doing it at every layer would cost too much, so KimiK3 does it every 12 decoder layers: roughly 2% added inference latency for a 1.25x compute advantage.

The residuals and the latent attention layers both exist because Kimi Delta Attention runs on a constant-size state and must inevitably discard information: one retrieves what was lost from the token context, the other from earlier depth. A fixed-capacity associative memory needs an eviction policy, since a purely additive linear operation eventually adds interference once it is at capacity, and learned selection, gating, routing, decay, is what supplies one. Attention is the most effective selective-read mechanism we have, which is why, inside a model that holds 22,580 GPT-2s, every fourth layer still reads the whole context with softmax, the way GPT-2 did.
