---
source_ids:
- 22580-from-gpt2-to-kimi3-explained-8f01b0fe
content_mode: faithful_synthesis
label: FAITHFUL SYNTHESIS
---

The count is twenty-two thousand five hundred and eighty. That’s how many GPT-2 (2019) models fit inside KimiK3 (2026). We scaled up by a factor of 22,580 in seven years. But is it just... scale?

GPT-2 is a decoder-only transformer. It turns tokens into embeddings, adds position information, passes the result through repeated blocks, and maps the final hidden states to vocabulary logits. Each block applies causal self-attention and a feed-forward network through residual connections. With roughly 50,000 possible tokens, 12 blocks, 12 heads, and a 768-dimensional embedding, the baseline has about 124 million parameters. KimiK3 has 2.8 trillion.

That number describes the distance traveled. It does not explain the journey.

## The cache becomes the problem

During generation, the model computes representations for every position but uses only the logits at the final position. Without a cache, appending one token would force it to recompute projections for the entire history. The key-value cache stores the previous keys and values instead. This avoids repeated work, but the cache grows linearly with sequence length and can turn memory bandwidth into the bottleneck.

Linear attention changes the order of operations. Softmax attention compares every query with every key, then normalizes the scores. A feature map such as ELU+1 can be applied to queries and keys separately, making the products re-associable. The growing collection of key-value vectors becomes a fixed D × D state. Each decode step reads that state instead of reading an ever-growing list.

The gain comes with a cost. The feature map is a less expressive approximation of the softmax kernel, so accuracy can fall depending on the architecture and workload. The basic attention contract remains: make scores non-negative, divide by their sum, and take a weighted average of the values. The approximation changes how the scores are made, while the fixed state changes how memory is stored.

There is a trade-off.

A fixed state must eventually combine information that would have occupied separate slots. Additive updates prevent the cache from growing with the sequence, but they also make associations interfere. The regime that makes linear attention attractive, where N is much larger than D, also exposes its main limitation. Once the state exceeds its effective capacity, associations begin to interfere because the update is additive and nothing leaves the cache.

## Writing over old information

DeltaNet addresses this interference by asking what the current key already retrieves. It subtracts that old value from the value the model wants to write, then adds only the difference. If the same key is used to read the association later, a normalized key can recover the stored value. The update acts like a small programmable memory: old information is removed where a replacement exists, and new information is written in its place.

This solves one problem and reveals another. DeltaNet can replace a particular association, but it cannot clear many unrelated associations when the context changes. Nor can it make the rest of the memory gradually less important.

A direct implementation would update the state once per token, which is efficient at decode time but sequential during prefill. Chunking provides a middle path. Within a chunk, the model performs masked attention. Across chunks, it folds key-value products into the recurrent state. Chunk size C controls the balance: C = 1 gives regular linear attention, while C = N recovers full quadratic attention. Intermediate chunks, often 64 or 128, trade some within-chunk work for better use of matrix-multiply hardware.

The delta rule seems to block this parallelization because each correction depends on the state produced by the previous token. A re-parameterized recurrence turns the updates into a form that can compute all corrections in a chunk together, then carry the resulting state to the next chunk. The model keeps linear-time state updates while making training friendlier to the hardware.

## Forgetting becomes a learned operation

The next step combines precise replacement with general forgetting. A gated update multiplies the old state by a learned decay value before adding the new information. Mamba uses this kind of uniform decay, which reduces every association together. DeltaNet can replace one association, but has no general decay. Gated DeltaNet combines the two: a gate of one gives the pure delta rule, while a gate of zero clears the memory.

The same chunked method can implement the gated recurrence. The mathematics adds a data-dependent scalar between zero and one, with cumulative products tracking how much an older write survives through later decay steps.

Kimi Linear adds finer control. Instead of one decay scalar, it learns a separate value for each channel. Under controlled comparisons, its authors reported better quality than full attention and up to six times higher decode throughput. The architecture also interleaves Multi-head Latent Attention layers and replaces the ordinary feed-forward network with a Mixture-of-Experts layer.

The pattern is now visible. Each generation adds capacity where the preceding memory system loses something: a fixed state needs replacement, replacement needs forgetting, and forgetting needs selective control.

## KimiK3 uses several kinds of memory

KimiK3's backbone resembles Kimi Linear, arranged as 23 four-layer macrocycles. In each cycle, three layers use Kimi Delta Attention and the fourth uses Multi-head Latent Attention. The first layer uses a dense feed-forward network; later layers use latent Mixture-of-Experts blocks.

Kimi Delta Attention supplies constant-state recurrent memory. Periodic MLA layers retain full softmax retrieval over the context, restoring access to details that a fixed state must discard. Gated MLA controls how much of each retrieved feature enters the residual stream by multiplying it with a gate projected from the input.

The expert system is sparse. KimiK3 has 898 experts: two shared experts process every token, and a router selects 16 of the remaining 896 for each token. The experts operate in a compressed latent space, reducing the work of their forward pass and nearly halving the FLOPs.

The activation function also changes. SiTU replaces the usual SiLU path with bounded transformations involving tanh and sigmoid. Without a fused kernel, this new activation is almost three times slower than the original. The latent-space computation offsets much of that cost.

KimiK3 also adds query LoRA, output gating, and Attention Residuals, or AttnRes, at block boundaries. Ordinary residual streams add the original embedding and every preceding layer output with equal weight. As depth increases, later layers must produce larger outputs to influence that accumulated sum, and the representation can dilute or grow.

AttnRes gives each layer a learned query over earlier residual states. It normalizes query-key scores and uses them to form a weighted combination, so a layer can retrieve the representations most useful for its current computation. Applying this at every layer would cost too much, so KimiK3 groups twelve decoder layers into a block and applies residual attention at fixed boundaries. Across the 23 macrocycles, this produces eight AttnRes blocks. The reported overhead is about two percent inference latency, alongside a 1.25x compute advantage.

## What scale is buying

The final model is large, but size alone is not the architectural story. KimiK3 combines recurrent memory with selective forgetting, periodic exact retrieval, sparse expert capacity, and learned access to earlier depth-wise representations.

The central constraint is storage. A fixed-capacity associative memory eventually reaches a point where additive writes interfere. The model needs ways to decide which associations to replace, which to decay, which channels to preserve, and which earlier representations to retrieve. Gating, routing, and attention supply those decisions at different places in the system. Among them, attention remains the most effective selective-read mechanism.
