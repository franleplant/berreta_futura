---
source_ids:
- 22580-from-gpt2-to-kimi3-explained-8f01b0fe
content_mode: faithful_synthesis
label: FAITHFUL SYNTHESIS
---

The number is twenty-two thousand five hundred and eighty. That’s how many GPT-2 (2019) models fit inside KimiK3 (2026). We scaled up by a factor of 22,580 in seven years. But is it just scale?

A language model must keep useful information somewhere. GPT-2 keeps a separate key and value for each earlier token in its KV cache. That avoids recomputing the history, but the cache grows with sequence length and can become a memory-bandwidth bottleneck. KimiK3 takes a different path: it combines several ways to store, forget, and retrieve information, each aimed at a failure in the one before it.

GPT-2 is the baseline. Tokens receive token and positional embeddings, then pass through twelve decoder blocks, each combining causal self-attention with an MLP. Its roughly 50,000-token vocabulary, twelve layers, twelve heads, and 768-wide embeddings produce about 124 million parameters. At 2.8 trillion parameters, one KimiK3 contains roughly as many parameters as 22,580 GPT-2 models.

At each decoding step, GPT-2 computes representations for every position but uses only the final position’s logits. The KV cache stores the previous keys and values so those projections do not have to be repeated:

```python
k=torch.cat((k_past, k), dim=2)
v=torch.cat((v_past, v), dim=2)
past_kv=(k, v)
```

The cache solves repeated work by retaining more history. Its cost therefore grows with the sequence.

Linear attention folds that growing history into a fixed D×D state. Softmax attention applies its nonlinearity after the q·k product, coupling every query to every key. Linear attention applies a feature map such as ELU+1 to q and k separately, making the product re-associable. The paper’s O(N²) framing threw me off. Older implementations often materialized the full attention matrix and recomputed token history without a KV cache. Linear attention replaces those reads and writes with state updates, but the feature map is a less expressive approximation to the softmax kernel, so the practical accuracy loss depends on the architecture and workload.

The basic attention contract remains recognizable: make the qk scores non-negative, divide by their sum, then compute a weighted average of the values. The difference is where the information lives. A fixed state cannot preserve every earlier association as a separate record.

That creates the next failure. Purely additive updates keep inserting key-value associations until they interfere. DeltaNet asks what the current key already retrieves, subtracts that old value from the value to be written, and adds only the difference:

```python
v_old = k @ S
u = beta * (v - v_old)
S = S + k.transpose(-1, -2) @ u
```

With normalized keys, a key can retrieve the value written in its direction. A new fact can replace an old fact instead of piling on top of it. The state remains fixed, but DeltaNet can forget an association only when a replacement arrives. It cannot efficiently clear several associations during a context switch.

The same recurrence also creates a training problem. A direct implementation processes every token in sequence, while hardware prefers matrix operations over chunks. The reparameterized update is:

```python
S_t = S_{t-1}(I − β_t k_t k_tᵀ) + β_t v_t k_tᵀ
o_t = S_t q_t
```

Chunking computes local masked attention inside each block and folds the block into the recurrent state. Setting the chunk size equal to the sequence length recovers standard quadratic attention; setting it to one gives regular linear attention. Intermediate sizes trade within-chunk work for better use of matrix-multiply hardware.

Mamba supplies the missing operation: decay the previous state before adding the new one.

```python
S_old=cache
S_new=k@v
cache=alpha * S_old + S_new
```

Uniform decay frees capacity but forgets every association together. The Delta rule can change one fact, while Mamba can make the whole memory fade. Gated DeltaNet combines them with a data-dependent value between zero and one. At one, the update behaves like the Delta rule; at zero, it clears the memory. The same reparameterization supports chunked computation, so training can use parallel passes while decoding keeps a constant-size recurrent state.

Kimi Linear makes the control finer. Instead of one decay value, it learns a separate value for each channel. Under controlled comparisons, its authors reported better quality than full attention and up to six times higher decode throughput. It also interleaves Multi-head Latent Attention, replaces the MLP with a mixture-of-experts layer, and gives the recurrent state this per-channel memory control.

Scaling laws remain relevant, but capacity must be added in the right place and in a form the system can use. Each step in the lineage adds capacity to answer a concrete limitation in the previous system.

KimiK3 keeps the Kimi Linear shape while enlarging and specializing it. Its backbone uses 23 four-layer macrocycles: three Kimi Delta Attention layers followed by one Multi-head Latent Attention layer. The first layer in a cycle uses a dense feed-forward network; later layers use latent mixture-of-experts blocks. KDA supplies constant-state recurrent memory, while periodic MLA layers retain full softmax retrieval over the token context.

The mixture-of-experts system has 898 experts. Two are shared and process every token; the router selects 16 of the remaining 896 for each token. The experts operate in a compressed latent space, reducing the cost of a mechanism that would otherwise be almost three times slower without a fused kernel. KimiK3 also gates the output of MLA and changes the expert activation to SiTU.

Its remaining major change is Attention Residuals every twelve layers. Ordinary residuals add each layer’s output with equal weight, so later layers receive an increasingly diluted mixture. AttnRes learns weights from query-key scores and lets a layer retrieve the earlier representations most useful to its current computation. The block-level retrieval is:

```python
V = torch.stack(blocks + [partial_block])
K = norm(V)
logits = torch.einsum('d, n b t d -> n b t', proj.weight.squeeze(
h = torch.einsum('n b t, n b t d -> b t d', logits.softmax(0), V)
return h
```

Applying residual attention at every layer would add too much cost. Fixed block boundaries capture the benefit with less training and inference work.

The progression from GPT-2 to KimiK3 is therefore a progression through memory failures. A growing cache avoids recomputation but consumes bandwidth. A fixed state is cheap but must overwrite or forget. Delta updates replace specific associations, gates control decay, MLA retrieves details from the context, sparse experts add capacity where needed, and AttnRes selects useful representations from earlier depth.

A fixed-capacity associative memory eventually needs an eviction policy. Learned selection, routing, or decay provides one, and attention remains the sharpest way to retrieve what the state could not keep.
