---
source_ids:
- 22580-from-gpt2-to-kimi3-explained-8f01b0fe
content_mode: faithful_synthesis
label: FAITHFUL SYNTHESIS
---

Twenty-two thousand five hundred and eighty. That’s how many GPT-2 (2019) models fit inside KimiK3 (2026). We scaled up by a factor of 22,580 in seven years. But is it just scale?

GPT-2 is a decoder-only transformer. Tokens receive token and positional embeddings, then pass through twelve blocks, each combining causal self-attention with an MLP. The model ends with vocabulary logits. Its roughly 50,000-token vocabulary, 12 layers, 12 heads, and 768-wide embeddings produce about 124 million parameters. KimiK3 has 2.8 trillion.

At each decoding step, GPT-2 computes representations for every position but uses only the final position’s logits. Without caching, it would repeat work for the whole history. The KV cache stores the previous keys and values, avoiding that recomputation, but the cache grows with sequence length and can become a memory-bandwidth bottleneck.

Linear attention changes the storage problem. Softmax attention compares every query with every key. Linear attention applies a feature map, such as ELU+1, to queries and keys separately, so the products can be reassociated into a fixed D×D state. The cache no longer grows with the sequence.

The paper’s O(N²) framing threw me off. The practical issue was that older implementations often materialized the full attention matrix and recomputed token history without a KV cache. Linear attention replaces that work with state updates and fewer reads and writes. It pays for this with a less expressive approximation to the softmax kernel, so accuracy loss depends on the architecture and workload.

The basic contract remains recognizable. Make the scores non-negative, divide by their sum, then compute a weighted average of the values. The difference is where the information lives: a fixed state instead of a separate record for every earlier token.

A finite state has to overwrite something. Purely additive updates keep inserting key-value associations until they interfere. DeltaNet addresses this by asking what the current key already retrieves, subtracting that old value from the value to be written, and adding only the difference. With a suitable normalization, a key can retrieve the value written in its direction. A new fact can replace an old fact instead of piling on top of it.

But DeltaNet can forget an association only when a replacement arrives. It has no general way to clear several associations during a context switch. Mamba supplies a different operation: decay the previous state by a learned factor before adding the new state. That frees capacity, but uniform decay forgets every association together. The Delta rule can change one fact, while Mamba can make the whole memory fade.

Gated DeltaNet combines them. A parameter between zero and one controls how much of the previous state survives. At one, the update behaves like the Delta rule; at zero, it clears the memory. The same reparameterization supports chunked computation, so training can use hardware-efficient parallel passes while decoding keeps a constant-size recurrent state.

Kimi Linear adds finer control. Instead of one decay value, it learns a separate value for each channel. Under controlled comparisons, its authors reported better quality than full attention and up to six times higher decode throughput. The architecture also interleaves Multi-head Latent Attention, replaces the MLP with a mixture-of-experts layer, and gives the recurrent state this per-channel memory control.

Scaling laws remain relevant, but capacity must be added in the right place and in a form the system can use. Each step in the lineage adds capacity to answer a concrete limitation in the previous system.

KimiK3 keeps the Kimi Linear shape while enlarging and specializing it. Its backbone uses 23 four-layer macrocycles: three Kimi Delta Attention layers followed by one Multi-head Latent Attention layer. The first layer in a cycle uses a dense feed-forward network; later layers use latent mixture-of-experts blocks.

The recurrent KDA state gives constant-size memory, while periodic MLA layers retain full softmax retrieval over the token context. The mixture-of-experts system has 898 experts, two shared across every token and 16 selected from the remaining experts for each token. Its experts operate in a compressed latent space, reducing the cost of a mechanism that would otherwise be much slower without a fused kernel.

KimiK3 also gates the output of MLA, changes the expert activation to SiTU, and adds Attention Residuals every twelve layers. Ordinary residuals add each layer’s output with equal weight, so later layers receive an increasingly diluted mixture. AttnRes learns weights from query-key scores and lets a layer retrieve the earlier representations most useful to its current computation. Applying this at block boundaries captures the benefit with lower cost.

The result is a model that spends different kinds of capacity on different failures. Recurrent memory stores information cheaply but must evict; MLA retrieves details from the context; routing supplies sparse expert capacity; residual attention selects useful representations from earlier depth. A fixed-capacity associative memory eventually needs an eviction policy. Learned selection, routing, or decay provides one, and attention remains the sharpest way to retrieve what the state could not keep.
