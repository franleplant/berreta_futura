---
source_ids:
- 22580-from-gpt2-to-kimi3-explained-8f01b0fe
content_mode: faithful_synthesis
label: FAITHFUL SYNTHESIS
---

Twenty-two thousand five hundred and eighty GPT-2 (2019) models fit inside KimiK3 (2026). We scaled up by a factor of 22,580 in seven years. But is it just... scale? The useful answer appears when you follow what each model stores, how it updates that memory, and how it retrieves information that the memory cannot keep.

## Start with a cache that grows

GPT-2 is a decoder-only Transformer. Each token receives a learned token embedding and a positional embedding, then passes through repeated blocks of causal self-attention and a feed-forward network. Attention makes a query, a key, and a value for every token. Each query compares itself with earlier keys, turns those scores into weights, and forms a weighted average of the values. The final hidden state becomes vocabulary logits, and the decoder chooses the next token from the logits at the last position.

That last detail creates an obvious waste. At every decoding step, the model computes representations for the whole sequence even though generation consumes only the final position. Without a cache, appending one token means recomputing the projections for all previous tokens. The KV cache stores those earlier key and value vectors instead. It removes repeated work, but its size grows with the sequence, until moving the cache between memory and the processor becomes the bottleneck.

The original GPT-2 configuration had about 50,000 possible tokens, 12 blocks, 12 heads, and an embedding dimension of 768. That is roughly 124 million parameters. KimiK3 has about 2.8 trillion. The comparison is memorable, but the parameter count does not explain the lineage. The important changes begin when the growing cache becomes a problem.

## Fold the history into a fixed state

Softmax attention compares every query with every key. Linear attention changes the order of operations. It applies a feature map such as ELU+1 to queries and keys separately, making the key-value product re-associable. Instead of retaining every key and value, the model folds them into a fixed \(D \times D\) state.

At each step, the state stores a sum of key-value outer products. A new query reads from that state. The cache no longer grows with the sequence length, so the memory traffic becomes constant in the number of tokens. The price is expressiveness. Replacing the exponential softmax kernel with a simpler feature map preserves the basic attention contract, but it approximates the score function and can lose accuracy depending on the architecture and workload.

That approximation exposes the central problem of finite memory. When a new association is added to the same matrix, it can interfere with associations already there. A query cannot always recover one earlier fact in isolation. The regime that makes linear attention attractive, with sequence length much larger than the state dimension, is also the regime in which the state reaches capacity.

## Write with a delta

DeltaNet changes the update. Before writing a new value, it asks what the current key would retrieve from the state. It subtracts that old information from the value it wants to store, then writes only the difference. If a key points to an existing association, the update can replace it instead of piling another association on top.

The same idea can be pictured as a board with a finite number of directions. A key points to one direction. The model reads what is already written there, calculates the correction, and writes the correction back. With normalized keys, reading the association can recover the stored value, so the correction has a precise target.

A direct DeltaNet implementation is sequential because every update depends on the state produced by the previous token. That is awkward for prefill, when a long prompt must be processed before generation begins. Chunking provides a compromise. Inside a chunk, the model performs masked attention among the chunk's tokens. Across chunks, it folds the key-value information into the recurrent state and reads that state back with a matrix multiplication. A chunk of size one gives ordinary linear attention. A chunk as large as the sequence gives full quadratic attention. Intermediate sizes trade extra within-chunk work for better use of the GPU's matrix hardware.

When written as a state transition, the update at each step applies a rank-one transformation to the old state and adds the new value. That form lets the model solve all corrections in a chunk together, then carry one resulting state to the next chunk. The computation remains linear in sequence length while the hardware sees larger, more useful matrix operations.

## Make memory forget

The delta rule can replace a specific association, but it cannot clear a group of unrelated associations when the subject changes. A separate decay mechanism solves the opposite problem. Mamba applies a learned decay to the entire previous state before adding the new information. The state cannot grow without bound, but every association decays by the same ratio at that step.

Gated DeltaNet combines these behaviors. A data-dependent gate controls how much of the old state survives, while the delta update changes a selected association. When the gate is near one, the update behaves like the delta rule. When it is near zero, the memory is cleared. The model can therefore edit one fact and also make room for a new context.

Kimi Linear adds finer control. Instead of one decay scalar for the whole state, it learns a separate decay value for each channel. Under the authors' controlled comparisons, this hybrid model outperformed full attention while offering up to six times higher decode throughput. Its architecture interleaves Gated DeltaNet with Multi-head Latent Attention, replaces the ordinary feed-forward block with a Mixture-of-Experts layer, and gives the recurrent memory more precise decay.

Scaling laws remain relevant, but capacity must be added in the right place and in a form the system can use. Each step in this progression answers a concrete limitation in the preceding system.

## Let different memories do different jobs

KimiK3 keeps the basic Kimi Linear pattern and expands it. Its backbone contains 23 four-layer macrocycles. In each cycle, three layers use Kimi Delta Attention and the fourth uses Multi-head Latent Attention. The first layer uses a dense feed-forward network; the remaining layers use latent Mixture-of-Experts blocks.

KDA provides constant-state recurrent memory. It is efficient, but a fixed state must eventually discard detail. Periodic MLA layers retain full softmax retrieval over the token context, giving the model a way to recover information that the recurrent state could not preserve.

The model also changes how it spends expert capacity. Its router has 898 experts: two shared experts process every token, and the router selects 16 of the other 896 for each token. The experts operate in a compressed latent space, reducing the cost of their forward pass. KimiK3 uses a new SiTU activation as well. Without a fused kernel, that activation is nearly three times slower than the original path, so the latent representation offsets some of the added work.

Gated MLA controls how much retrieved information enters the residual stream. Query LoRA and output gating further shape that path. These additions are small beside the parameter count, but each has a job: control retrieval, distribute computation, or regulate memory.

## Retrieve across depth

There is another finite-memory problem inside the network. In an ordinary residual stream, each layer receives the original embedding plus the accumulated output of every preceding layer, weighted equally. Later layers must produce increasingly large outputs to influence that sum, and each layer sees the same blended representation even when different earlier states would be more useful.

Attention Residuals, or AttnRes, make the mixture selective. A learned query for each layer compares with keys derived from earlier residual states. The normalized scores weight those states before combining them. A layer can retrieve the depth-wise representations that matter for its current computation instead of accepting one undifferentiated sum.

Applying this attention at every layer would cost too much, so KimiK3 applies it at block boundaries. Every 12 decoder layers, the accumulated block becomes a depth representation that later blocks can retrieve. Across the model, this produces eight AttnRes blocks and adds about two percent inference latency while providing selective access to earlier representations and a reported 1.25x compute advantage.

The final architecture is therefore a collection of memories with different failure modes. Kimi Delta Attention keeps a compact recurrent state and learns which associations to edit or decay. MLA periodically performs full retrieval over the context. Mixture-of-Experts adds sparse computation where a token needs it. AttnRes lets later depth blocks reach back to useful earlier representations.

The central change from GPT-2 to KimiK3 is the management of information under limits. A fixed-capacity associative memory eventually needs an eviction policy. Learned selection, routing, and decay decide what remains, while attention supplies a selective read when a compressed state has forgotten too much. The extra scale matters because it gives these mechanisms room to work. It is useful only when the architecture tells that capacity what to do.
