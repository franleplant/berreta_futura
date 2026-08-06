---
source_ids:
- 22580-from-gpt2-to-kimi3-explained-8f01b0fe
content_mode: faithful_synthesis
label: FAITHFUL SYNTHESIS
---

Twenty-two thousand five hundred and eighty. That’s how many GPT-2 (2019) models fit inside KimiK3 (2026). We scaled up by a factor of 22,580 in seven years. But is it just... scale? The useful answer appears when you follow what each model stores, how it changes that memory, and how it retrieves what the memory can no longer hold.

## The cache becomes the problem

GPT-2 is a decoder-only Transformer. It turns tokens and positions into hidden states, passes them through repeated blocks of causal self-attention and a feed-forward network, then maps the final hidden state to vocabulary logits. Each block adds attention and an MLP output back to the residual stream.

During generation, the model computes representations for every input position, but the next token uses only the logits at the final position. Without a cache, appending one token would force the model to recompute the projections for the entire history. The key-value cache keeps the previous tokens’ key and value vectors so the model can reuse them.

That saves computation and creates a different limit. The cache grows with sequence length, and every decode step reads the stored vectors from memory. A GPT-2-sized baseline has about 124 million parameters, with roughly 50,000 possible tokens, 12 layers, 12 heads, and an embedding dimension of 768. KimiK3 has 2.8 trillion parameters. The arithmetic comparison is startling, but the more important question is what happens when the cache cannot keep growing.

## Folding history into a fixed state

Linear attention changes the order of operations. Softmax attention first forms every query-key score, then normalizes it. A feature map such as ELU+1 can be applied to queries and keys separately, making the multiplication re-associable. The growing collection of keys and values can then be folded into a fixed \(D \times D\) state.

The model still makes scores non-negative, divides by their sum, and computes a weighted average of values. The feature map is less expressive than the exponential used by softmax, so the approximation can reduce fidelity, depending on the architecture and workload. In exchange, the state stays constant in size instead of growing with the sequence.

The gain exposes the cost. A finite state has no separate slot for every earlier token. Each new association is added to the same matrix, and eventually different facts interfere. As the sequence length exceeds the state’s effective capacity, the model needs to decide which associations to keep and which to remove. “There is a trade-off.”

## DeltaNet learns to overwrite

DeltaNet gives the state a way to replace information. For a new key, it first reads what the cache already returns at that key. It subtracts that old value from the value it wants to write, scales the difference by a learned write strength, and adds the resulting outer product to the state. If the key is normalized, reading at the same direction can recover the stored value.

The update therefore removes an old association when a replacement arrives. A query acts as a learned pointer, while the key says where the fact lives. This makes the fixed state more useful, but the update is sequential: each correction depends on the state produced by the previous token.

Chunking makes the operation practical for training. A sequence is divided into blocks. Within a block, the model performs ordinary masked attention. Across blocks, it folds key-value products into the recurrent state and reads that state back with a matrix multiplication. A block size of one gives regular linear attention; a block as large as the whole sequence recovers standard quadratic attention. Intermediate sizes trade more work inside each block for better use of matrix-multiply hardware.

DeltaNet’s correction term initially prevents the same straightforward parallelization. The update can be rewritten as a recurrence that applies a rank-one transformation to the previous state and adds a new value. That form allows the corrections within a chunk to be computed together, then combined with the state carried from earlier chunks.

## Forgetting needs a second control

DeltaNet can replace one association when it knows the replacement. It cannot efficiently clear many associations during a context switch. Gated memory adds a separate decay control. The state is multiplied by a learned factor before the new key-value information is added.

Uniform decay, as in Mamba, lets the model reduce the whole memory, but it forgets every association equally. The Delta rule can change one fact, while the gate can clear the state. Gated Delta combines them. A parameter called alpha can approach one and preserve the Delta update, or approach zero and clear the memory. The parallel chunk formulation carries the cumulative decay forward so that an old write becomes weaker over time.

Kimi Linear adds finer control. Instead of one decay value, it learns a separate value for each channel. Under controlled comparisons, its authors reported that it outperformed full attention and offered up to six times higher decode throughput. The architecture also interleaves Multi-head Latent Attention layers and replaces the ordinary MLP with a Mixture-of-Experts layer.

The change follows a pattern: each addition gives the model a way to handle a limitation in the preceding memory system. Scaling laws remain relevant, but capacity must be added in the right place and in a form the system can use.

## KimiK3 uses several kinds of memory

KimiK3 keeps the Kimi Linear shape and expands it. Its backbone contains 23 four-layer macrocycles. In each macrocycle, three layers use Kimi Delta Attention and the fourth uses Multi-head Latent Attention. The first layer uses a dense feed-forward network; the remaining layers use latent Mixture-of-Experts blocks.

KDA supplies constant-state recurrent memory. Periodic MLA layers retain full softmax retrieval over the token context, recovering information that a fixed state must eventually discard. Gated MLA controls how much of each retrieved feature enters the residual stream.

The MoE has 898 experts. Two shared experts process every token, and a router selects 16 of the other 896 for each token. The experts use SiTU rather than the usual SiLU path. Without a fused kernel, the new activation is almost three times slower, while operating in a compressed latent space nearly halves the expert forward-pass FLOPs.

KimiK3 also changes how layers retrieve earlier representations. In an ordinary residual stream, each layer receives the embedding plus the outputs of all preceding layers, added with equal weight. AttnRes assigns learned weights to those earlier states. A query for the current layer compares with keys from previous residual states, and the normalized scores choose a weighted combination.

This gives a layer selective access to earlier depth-wise representations instead of forcing it to use one undifferentiated sum. Applying the mechanism at every layer would be expensive, so KimiK3 uses fixed boundaries after each group of 12 decoder layers. Across the 23 macrocycles, that produces eight AttnRes blocks. The authors report roughly two percent added inference latency and a 1.25x compute advantage.

The progression from GPT-2 to KimiK3 is therefore a progression in memory management. GPT-2 stores every key and value, paying in bandwidth as context grows. Linear attention folds history into a fixed state, paying in recoverability. DeltaNet learns to replace entries. Gating controls general decay. Kimi Linear gives decay per channel and combines recurrent memory with occasional exact retrieval. KimiK3 adds sparse experts and selective access across depth.

At 2.8 trillion parameters, KimiK3 is vastly larger than GPT-2. Its additional capacity has jobs to do. A fixed-capacity associative memory needs an eviction policy, because additive updates eventually create interference. Learned selection, routing, and decay decide what remains available, while attention provides the strongest way to retrieve what the compressed state cannot preserve.
