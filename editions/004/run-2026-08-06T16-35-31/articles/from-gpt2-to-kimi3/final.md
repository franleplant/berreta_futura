---
source_ids:
- 22580-from-gpt2-to-kimi3-explained-8f01b0fe
content_mode: faithful_synthesis
label: FAITHFUL SYNTHESIS
---

2.8 trillion parameters in KimiK3; 124 million in GPT-2. Twenty-two thousand five hundred and eighty of the old fit inside the new. The seven years between them are not scale. They are one argument, made five times: a memory of fixed size must choose what to throw away. GPT-2 threw away nothing and paid with a cache that grows forever. Linear attention fixed the cache and paid in interference. DeltaNet learned to overwrite one fact. Gated DeltaNet learned to decay all of them. Kimi Linear learned to decay each channel on its own. K3 keeps all of it and adds a way to read back through its own depth. Every step buys capacity for a named defect.

---

## Where the cost begins

GPT-2 is a stack of blocks: attention, then an MLP, each added back into a residual stream. Twelve layers, twelve heads, 768 dimensions, fifty thousand tokens of vocabulary.

The waste is at the end. The model computes a representation for every position, and decoding uses only the last position's logits. Recomputing the earlier keys and values each step is pure repetition, so you store them. That store is the KV cache, and it holds vectors for N−1 tokens. The bottleneck moves from arithmetic to memory bandwidth. A finite room now contains a corridor that lengthens with every word.

## Fixing the size

Softmax puts its nonlinearity after q·k, which couples every query to every key. Apply a feature map — ELU+1 — to q and k separately, and the product becomes re-associable: the growing set of K and V vectors folds into one D×D state. Reads and writes per step stop scaling with N.

Attention keeps its three steps. Make the scores non-negative, divide by their sum, average the values. Only the first step changed, and ELU+1 approximates the softmax kernel less expressively. What you lose in fidelity depends on the workload.

## Interference

The state from token i−1 gets no slot of its own; it is added into the same matrix. That addition is the saving and the damage. Schlag put it plainly: endlessly adding new associations to a memory of finite size inevitably reaches a limit, and past that limit the model should decide which associations to keep and which to delete.

DeltaNet decides. At each key it first reads what the cache already holds there, `v_old = k @ S`. It subtracts that from the value it wants, scales the difference by a learned per-token strength, and writes the difference back. Old information leaves as new information arrives. Because Wq and Wk read the same residual stream, the query for a fact points at the direction that fact was written into; with unit-normalized keys, the read returns the value exactly.

## Making it parallel

This is the hard part; it cost me about seven hours. A direct delta rule needs every intermediate state to know what to subtract, so prefill is a loop over T tokens.

The fix is chunking. Inside a chunk of size C, do real masked attention, q(kᵀv). Across chunks, fold everything into the state and read it back with one matmul, (kᵀv)q. The cost splits: a fixed term 2Ld² for state work, indifferent to C, plus a growing term 2LCd for the score tiles on the diagonal. Set C = L and you recover 2L²d, full quadratic attention. Set C = 1 and you get linear attention with the fewest FLOPs — and worse wall-clock time, because a GPU wants work shaped like its matrix-multiply units. C is usually 64 or 128.

The delta rule resists this until you rewrite it as a transition:

```
S_t = S_{t-1}(I − β_t k_t k_tᵀ) + β_t v_t k_tᵀ
```

A first-order linear recurrence with generalized Householder matrices. Vectorized forward substitution then produces all C corrections at once.

## Forgetting without a replacement

Delta can only erase an association it has something to put in place of. It cannot clear a context switch or free capacity in general.

Mamba-2 supplies that: decay the old state by α, add the new at full strength, and the state stops growing without bound. But a uniform decay treats every association as equally disposable.

The gated delta rule takes both. α = 1 is pure delta; α = 0 wipes the memory. The chunked form is nearly unchanged, plus a cumulative decay factor — a token written at x and read at x+t has been multiplied by every α in between, a prefix sum done in products.

Kimi Linear then makes α per-channel instead of scalar. Its claim, under controlled comparison, is that it beats full attention as a drop-in replacement, with up to 6x decode throughput. The extra parameters are not blind; they buy finer control over what decays.

## K3

Twenty-three four-layer macrocycles. Three Kimi Delta Attention layers, then one Multi-head Latent Attention layer. The first layer is a dense feed-forward; the rest are latent Mixture-of-Experts — 898 experts, two shared, sixteen of the remaining 896 routed per token.

KDA carries constant-state recurrent memory. The periodic MLA layers keep true softmax retrieval over the context, gated so the model controls how much of each retrieved feature enters the residual stream.

SiTU replaces the SiLU gate: `β·tanh(gate/β)·sigmoid(·)` against the up projection. Unfused it runs almost 3x slower, repaid because the experts work in a compressed latent space that nearly halves their FLOPs.

## Reading back through depth

Ordinarily a layer's input is the embedding plus every earlier layer's output, weighted equally:

```
h_l = h_1 + Σ f_i(h_i)
```

Every layer type receives the same aggregate, and to move it a late layer must learn a large output — which destabilizes training.

AttnRes weights each term. A learned per-layer query scores the earlier residual states, the scores are normalized to sum to one, and the layer retrieves the mixture it needs. Done at every layer it would cost too much, so K3 does it at block boundaries: twelve decoder layers to a block, eight blocks, about 2% added latency for a 1.25x compute advantage.

MLA retrieves across the context. AttnRes retrieves across depth. Both exist because KDA's fixed state must discard something.

## What the seven years bought

A fixed-capacity associative memory needs an eviction policy, because purely additive writes eventually store only interference. The policy has to be learned — gating, routing, decay — and attention remains the best selective read we have. K3 is those four answers stacked: constant-state memory, periodic softmax retrieval, sparse expert capacity, selective depth. The scale is real. It is not the argument.
