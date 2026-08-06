---
source_ids:
- 22580-from-gpt2-to-kimi3-explained-8f01b0fe
content_mode: faithful_synthesis
label: FAITHFUL SYNTHESIS
---

Twenty-two thousand five hundred and eighty GPT-2s fit inside KimiK3. Almost none of the difference is scale.

GPT-2 keeps every token it has ever seen and pays for it in memory bandwidth. Linear attention burns the archive and keeps a fixed D×D board instead — cheap, but it forgets by accident. Everything after that is a better eviction policy. DeltaNet erases the old value at a key before writing the new one. Gated DeltaNet adds decay, so memory can fade without a replacement in hand. Kimi Linear makes the decay per-channel. K3 stacks those with periodic softmax layers that still read the whole context, sparse experts, and a residual stream each layer can query rather than merely inherit.

A finite memory needs a rule for what leaves it. Attention is the best selective read we have.

## The baseline

Token and position embeddings, twelve blocks of attention and MLP with residuals, a final norm, a head that maps hidden states to logits over ~50k tokens. 768 dimensions, twelve heads, 124M parameters.

At decode, the model computes every position and uses only the last one. So we store the keys and values of the previous N−1 tokens rather than recompute them. That store grows linearly and eventually becomes the bottleneck itself.

One correction to the literature I had to make for myself: the cost per decode step does not scale with the square of the sequence length. That claim describes 2019 practice — full N×N matrices materialized in training, no FlashAttention until 2020, reference implementations replaying the whole history.

## Linear attention

Softmax puts its nonlinearity after q·k, which chains every query to every key. Apply a feature map — ELU+1 — to q and k separately instead, and the product becomes re-associable. The growing K and V collapse into a fixed D×D state S with a running normalizer z. Two matmuls, constant memory.

Attention was only ever three steps: make the scores non-negative, divide by their sum, average the values. Linear attention keeps the contract and pays with a weaker kernel.

## The delta rule

A fixed board has no slot per token. Writes are added on top of each other, and past associations interfere. That addition is exactly what buys the constant memory.

Schlag names the condition: past capacity, the model must decide what to keep and what to delete; endlessly adding to a finite memory reaches a limit.

So read before you write. Query the board at the incoming key, subtract what is already there, scale the difference by a learned per-token strength, add that back. Normalize k to unit length and a read returns its value exactly. The query is a learned pointer — Wq and Wk read the same residual stream, so the query for a fact points at the direction that fact was written into.

## Making it parallel

Prefill is the problem. A literal delta loop walks the sequence one token at a time.

Chunking splits the difference. Inside a chunk, do real masked attention — score first. Across chunks, fold everything into the state and read it back with one matmul — state first. The cost separates cleanly: a fixed 2Ld² of state work that ignores chunk size, plus 2LCd of diagonal score matrices that does not. C=L is full quadratic attention; C=1 is plain linear attention and the cheapest in FLOPs, though not in wall-clock. In practice 64 or 128, because that is where tensor-core instructions live.

Delta resists this, because the correction needs every intermediate state. The fix is a reparameterization — a first-order linear recurrence with generalized Householder transitions:

```
S_t = S_{t-1}(I − β_t k_t k_tᵀ) + β_t v_t k_tᵀ
```

A triangular T built by forward substitution then produces all C corrections at once. Seven hours of my life; one matrix.

## Forgetting

The delta rule can only displace an association it holds the key to. It cannot clear a context switch or free capacity in general.

Mamba-2's answer is a scalar: decay the old state, add the new at full strength. Uniform, and indifferent to which associations mattered.

Gated DeltaNet takes both. Alpha at one is the pure delta rule; alpha at zero wipes the board. Cumulative decay across a span is a product of alphas — the multiplicative twin of a prefix sum.

Kimi Linear sharpens alpha into a vector: one decay per channel. It also interleaves Multi-head Latent Attention layers, swaps the MLP for a Mixture-of-Experts, and claims to beat full attention under controlled comparison at up to 6× decode throughput.

The capacity is not sprinkled. Each step adds it exactly where the previous system was blind.

## K3

Twenty-three four-layer macrocycles: three KDA layers, then one MLA. First layer a dense feed-forward network, the rest latent MoE. KDA carries constant-state recurrent memory; the periodic MLA layers keep true softmax retrieval over the context.

Gated MLA multiplies retrieved features by a gate projected from the input, deciding how much reaches the residual stream. The router sees 898 experts — two shared, sixteen chosen from the other 896 per token — and they compute in a compressed latent space, which nearly halves their FLOPs. SiTU replaces the SiLU gate; without a fused kernel it runs almost 3× slower, and the latent compression pays that back.

## AttnRes

Ordinarily a layer inherits the sum of the embedding and every output before it, all weighted equally. Later layers must then shout to be heard over the accumulation, which destabilizes training.

AttnRes weights each term. Each layer learns a query; earlier residual states supply keys and values; the softmaxed scores mix them. A layer no longer has to accept the past as one undifferentiated inheritance — it can ask for the parts it needs.

Doing this every layer costs too much, so K3 does it at block boundaries: twelve decoder layers summed into one depth representation, eight blocks across the stack. Roughly 2% added latency for a 1.25× compute advantage and relief from residual dilution.

MLA retrieves across the context. AttnRes retrieves across depth. Both exist because a constant-size state must throw something away.
