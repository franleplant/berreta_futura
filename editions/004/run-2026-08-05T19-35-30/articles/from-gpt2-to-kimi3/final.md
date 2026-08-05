---
source_ids:
- 22580-from-gpt2-to-kimi3-explained-8f01b0fe
content_mode: faithful_synthesis
label: FAITHFUL SYNTHESIS
---

Twenty-two thousand five hundred and eighty GPT-2 models fit inside KimiK3. That comparison is a useful warning: the model grew by a factor of 22,580 in seven years, but its story is not scale alone. Each generation changed what the model stores, how it updates that state, or how it retrieves information the state can no longer hold.

GPT-2 is a decoder-only transformer. Tokens receive token and positional embeddings, then pass through repeated blocks of causal self-attention and an MLP before the language-model head produces vocabulary logits. The baseline has about 124 million parameters: roughly 50,000 possible tokens, 12 blocks, 12 heads, and an embedding dimension of 768. KimiK3 has 2.8 trillion parameters.

The original architecture has an obvious inference inefficiency. At each decoding step it computes representations for every position, although only the final position’s logits select the next token. Without caching, appending one token means repeating work for the entire history. The KV cache stores the key and value vectors for previous tokens, avoiding that recomputation. It also grows with the sequence and can become large enough to create a memory-bandwidth bottleneck.

Linear attention attacks that cost by changing the operation itself. Softmax attention compares every query with every key, then normalizes the scores. Linear attention applies a feature map such as ELU+1 to queries and keys separately, so the products can be reassociated and the growing collection of key-value vectors folded into a fixed D by D state. The cache no longer grows with sequence length.

The linear-attention paper’s O(N²) framing threw me off. It's not true that "the cost per time-step for transformers scales with the square of the current sequence length." FlashAttention fixes part of that problem, but in the period being discussed FlashAttention did not exist, and reference autoregressive implementations often recomputed token history without a KV cache.

The fixed state buys memory efficiency by giving up expressive power. Linear attention still makes scores non-negative, divides by their sum, and computes a weighted average of values, but ELU+1 is a less expressive feature map than the exponential used by softmax. The practical accuracy loss depends on the architecture and workload.

A finite state must eventually combine or overwrite information. Purely additive updates put every new association into the same D by D matrix, so once the sequence exceeds the state’s effective capacity, associations interfere. New queries can no longer retrieve every earlier token in isolation. DeltaNet addresses this by asking what the current key already retrieves, subtracting that information from the value to be written, and adding back only the difference. Old information can be replaced instead of endlessly accumulated.

That repair introduces a different limit. DeltaNet can forget an association when it has a specific replacement, but it cannot efficiently clear multiple unrelated associations during a context switch or decay memory generally to free capacity. The direct update is sequential, which makes long-sequence prefill difficult to parallelize. DeltaNet rewrites the recurrence into a form that can process chunks in parallel. Within a chunk it performs masked attention; across chunks it folds the state forward. A chunk size of one gives regular linear attention, while a chunk the length of the whole sequence recovers ordinary quadratic attention. Intermediate sizes trade extra within-chunk work for better use of GPU matrix hardware.

The gated Delta rule adds the missing general forgetting mechanism. A learned decay value controls how much of the previous state survives before the new association is added. Setting the gate near one behaves like the Delta rule; setting it near zero clears memory. This combines selective replacement with broader memory management. Kimi Linear makes the control finer still, learning a separate decay value for each channel rather than one scalar for the whole state. Under controlled comparisons, its authors reported better quality than full attention and up to six times higher decode throughput.

Kimi Linear also interleaves Multi-head Latent Attention layers and replaces the ordinary MLP with a Mixture-of-Experts layer. The additional capacity has a job. The recurrent layers provide constant-state memory, while periodic MLA layers retain full softmax retrieval over the token context. The MoE layer routes each token to a small subset of experts. KimiK3 has 898 experts, two shared by every token and 16 selected from the remaining 896.

KimiK3’s backbone contains 23 four-layer macrocycles. Three layers in each cycle use Kimi Delta Attention and the fourth uses MLA. The first layer uses a dense feed-forward network; the rest use latent-space MoE. The experts operate in compressed space, which nearly halves their forward-pass FLOPs and offsets some of the cost of the new SiTU activation. Without a fused kernel, that activation is almost three times slower than the original path.

The model also adds Gated MLA and Attention Residuals. Gated MLA controls how much retrieved information enters the residual stream. Ordinary residuals add every earlier layer’s output with equal weight, so later layers must produce increasingly large outputs to affect the sum. AttnRes learns query-key weights over earlier residual states, letting each layer retrieve the representations useful for its current computation. KimiK3 applies this at block boundaries after every 12 decoder layers, producing eight AttnRes blocks across the backbone. The change adds roughly 2% inference latency and supplies selective access to earlier depth-wise representations.

The progression from GPT-2 to KimiK3 is therefore a progression through storage limits. A KV cache preserves exact token history but grows with context. Linear attention keeps constant state but loses expressive retrieval. DeltaNet replaces associations, gated variants decay them, MLA restores full-context lookup periodically, MoE adds sparse capacity, and AttnRes lets depth retrieve selectively instead of passing one undifferentiated sum forward.

A fixed-capacity associative memory eventually needs an eviction policy. Learned selection, routing, and decay provide one; attention remains the strongest way to read what the fixed state cannot preserve. Scaling laws still matter, but capacity has to arrive in a form the system can use.
