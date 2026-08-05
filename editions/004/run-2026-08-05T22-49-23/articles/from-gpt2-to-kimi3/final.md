---
source_ids:
- 22580-from-gpt2-to-kimi3-explained-8f01b0fe
content_mode: faithful_synthesis
label: FAITHFUL SYNTHESIS
---

A language model must keep useful information somewhere. KimiK3 has 2.8 trillion parameters, roughly the capacity of 22,580 GPT-2 models, but its defining changes are about what that capacity can remember, replace, and retrieve.

GPT-2 keeps a separate key and value for each earlier token in its KV cache. That avoids recomputing the history, but the cache grows with sequence length and can become a memory-bandwidth bottleneck. The update is simple:

```python
k=torch.cat((k_past, k), dim=2)
v=torch.cat((v_past, v), dim=2)
past_kv=(k, v)
```

Linear attention removes the growing list by folding history into a fixed D×D state. It applies a feature map such as ELU+1 to q and k separately, making the product re-associable. The paper’s O(N²) framing threw me off. Older implementations often materialized the full attention matrix and recomputed token history without a KV cache. Linear attention replaces those reads and writes with state updates, but its feature map is a less expressive approximation to the softmax kernel, so the practical accuracy loss depends on the architecture and workload.

The basic attention contract remains: make the qk scores non-negative, divide by their sum, then compute a weighted average of the values. The fixed state is cheaper, but it cannot preserve every earlier association as a separate record. Purely additive updates eventually make associations interfere.

DeltaNet changes the write. It asks what the current key already retrieves, subtracts that value from the value to be written, and adds only the difference:

```python
v_old = k @ S
u = beta * (v - v_old)
S = S + k.transpose(-1, -2) @ u
```

With normalized keys, a key can retrieve the value written in its direction. A new fact can replace an old one instead of piling on top of it. DeltaNet still cannot clear several associations during a context switch; it can forget an association only when a replacement arrives.

That sequential update creates a training problem. Hardware prefers matrix operations over chunks, so DeltaNet rewrites the recurrence as:

```python
S_t = S_{t-1}(I − β_t k_t k_tᵀ) + β_t v_t k_tᵀ
o_t = S_t q_t
```

Chunking performs masked attention inside each block and folds the block into the recurrent state. A chunk equal to the whole sequence recovers standard quadratic attention. A chunk of one gives regular linear attention. Intermediate sizes trade some within-chunk work for better use of matrix-multiply hardware.

DeltaNet can replace one association, but memory also needs a way to fade when the context changes. Mamba supplies uniform decay:

```python
S_old=cache
S_new=k@v
cache=alpha * S_old + S_new
```

This frees capacity, but it forgets every association together. Gated DeltaNet combines the two operations with a data-dependent value between zero and one. At one, the update behaves like DeltaNet; at zero, it clears the memory. The same reparameterization supports chunked computation, while decoding keeps a constant-size recurrent state.

Kimi Linear makes the control finer by learning a separate decay value for each channel. Under controlled comparisons, its authors reported better quality than full attention and up to six times higher decode throughput. It also interleaves Multi-head Latent Attention, replaces the MLP with a mixture-of-experts layer, and gives the recurrent state per-channel memory control.

Scaling laws remain relevant, but capacity must be added in the right place and in a form the system can use. Each step in the lineage adds capacity to answer a concrete limitation in the previous system.

KimiK3 keeps the Kimi Linear shape while enlarging and specializing it. Its backbone uses 23 four-layer macrocycles: three Kimi Delta Attention layers followed by one Multi-head Latent Attention layer. The first layer in a cycle uses a dense feed-forward network; later layers use latent mixture-of-experts blocks. KDA supplies constant-state recurrent memory, while periodic MLA layers retain full softmax retrieval over the token context.

The mixture-of-experts system has 898 experts. Two are shared and process every token; the router selects 16 of the remaining 896 for each token. The experts operate in a compressed latent space. Without a fused kernel, the new SiTU activation is almost three times slower than the original path, while the compressed experts make the forward pass much faster and nearly halve the FLOPs. KimiK3 also gates the output of MLA.

Its other major change is Attention Residuals every twelve layers. Ordinary residuals add each layer's output with equal weight, so later layers receive an increasingly diluted mixture. AttnRes learns weights from query-key scores and lets a layer retrieve the earlier representations most useful to its current computation:

```python
V = torch.stack(blocks + [partial_block])
K = norm(V)
logits = torch.einsum(
    'd, n b t d -> n b t',
    proj.weight.squeeze(), K)
h = torch.einsum(
    'n b t, n b t d -> b t d',
    logits.softmax(0), V)
return h
```

Applying residual attention at every layer would add too much cost. Fixed block boundaries capture the benefit with less training and inference work. In KimiK3, each boundary occurs after twelve decoder layers.

The progression from GPT-2 to KimiK3 is a set of repairs to memory failure. A growing cache avoids recomputation but consumes bandwidth. A fixed state is cheap but must overwrite or forget. Delta updates replace specific associations, gates control decay, MLA retrieves details from the context, sparse experts add capacity where needed, and AttnRes selects useful representations from earlier depth.

A fixed-capacity associative memory eventually needs an eviction policy. Learned selection, routing, or decay provides one, and attention retrieves what the state could not keep.
