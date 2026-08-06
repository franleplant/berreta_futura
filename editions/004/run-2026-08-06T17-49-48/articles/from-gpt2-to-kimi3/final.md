---
source_ids:
- 22580-from-gpt2-to-kimi3-explained-8f01b0fe
content_mode: faithful_synthesis
label: FAITHFUL SYNTHESIS
---

2.8 trillion parameters against 124 million. Twenty-two thousand five hundred and eighty GPT-2s fit inside KimiK3, and almost nothing worth knowing is in the multiplication. GPT-2 keeps every token it has seen in a cache that grows without end. Linear attention crushes that cache into a fixed square of numbers and pays for it: writes land on top of each other until they interfere. Everything since is a quarrel over that finite room. DeltaNet learns to overwrite one fact. Mamba learns to fade all facts. Gated DeltaNet does both. Kimi Linear gives every channel its own rate of fading. K3 stacks the result — three fading layers, one that remembers everything, repeat twenty-three times — and adds a retrieval that reaches back through depth instead of time. A memory of fixed size needs an eviction policy. Attention is the best read head we have.

## Where the cost sits

GPT-2 is a decoder: token and position embeddings, twelve blocks of attention and MLP wired as residuals, a head that maps the final hidden state to fifty thousand logits. At decode time only the last position's logits are used. The rest of the work would be repeated on the next token, so we store the keys and values instead. That store is the KV cache. It holds vectors for all N-1 previous tokens, it grows linearly, and it becomes a memory-bandwidth bottleneck long before it becomes a compute one.

## Folding the cache flat

Softmax puts its nonlinearity after the q·k product, which chains every query to every key. Apply a feature map — ELU+1 — to q and k separately, and the product becomes re-associable. The growing pile of K and V collapses into one D×D matrix S, plus a normaliser z. Two reads, two writes, constant size.

The bill comes as fidelity. ELU+1 is a poorer approximation of the softmax kernel. The contract survives — make the scores non-negative, divide by their sum, average the values — but the instrument is blunter.

The original paper's O(N²) framing misled me until I noticed the date. In 2020 the full N×N matrix was materialised and reference decoders often recomputed history with no cache at all.

## Writing one fact at a time

A finite square has no separate shelf for token i-1. It is added onto the same surface as everything else, and that addition is both the saving and the wound. Schlag put it plainly: past capacity, a model must decide what to keep and what to delete, and endless addition to a finite memory will reach its limit.

The delta rule reads before it writes. Ask what the current key retrieves, subtract that from the value you meant to store, scale by a learned per-token strength β, write the difference. Old information is displaced rather than piled on. The arithmetic is exact when keys are unit length: reading S = kᵀv back with k gives (k kᵀ)v, the squared norm times v. Q is a learned pointer, and Wq and Wk read the same residual stream, so the query for a fact points at the direction that fact was written into.

## Making it parallel

Written naively this is a loop over T tokens, which ruins prefill. The fix is chunking. Split into blocks of C. Inside a block, do real masked attention, q(kᵀv), score first. Across blocks, fold into the state, (kᵀv)q, state first. C=N recovers quadratic attention; C=1 recovers linear attention; the cost splits into a fixed 2Ld² of state work and a growing 2LCd of diagonal score matrices. Small C means fewer FLOPs and not necessarily less time — 64 or 128 is what tensor cores like.

The delta rule resists this, because the correction at each key needs every intermediate state. So rewrite the recurrence as a generalised Householder:

`S_t = S_{t-1}(I − β_t k_t k_tᵀ) + β_t v_t k_tᵀ`

A vectorised forward substitution then produces all C corrections at once, and the chunk loop runs on matmuls. It cost me most of a day to see why this works.

## Learning to forget

The delta rule can only forget what it has a replacement for. It cannot clear the board at a change of subject. Mamba-2 supplies the missing verb: decay the old state by α, add the new at full strength. But uniform decay treats every association as equally disposable.

Gated DeltaNet takes both. α at one is the pure delta rule; α at zero wipes the memory. Cumulative decay over a span is a product of α's — a prefix sum with multiplication in place of addition.

Kimi Linear's contribution is finer: not one decay scalar but one per channel. Its claim, under controlled comparison, was that it beat full attention outright, with up to six times the decode throughput. Beside a DeltaNet transformer it also interleaves Multi-head Latent Attention, swaps the MLP for a Mixture-of-Experts, and adds the alpha projection. The capacity is placed, not sprinkled.

## K3

Twenty-three macrocycles of four layers. Three use Kimi Delta Attention, the fourth uses MLA. The first layer is a dense feed-forward; the rest are latent MoE — 898 experts, two shared and always on, sixteen of the remaining 896 chosen per token. KDA holds constant-state recurrent memory; the periodic MLA layers keep full softmax retrieval over the context.

The smaller changes: a gate, projected from the input, decides element-wise how much of MLA's output reaches the residual stream. The expert activation becomes SiTU, `β·tanh(gate/β)·sigmoid(·)` times the up projection — nearly three times slower without a fused kernel, and repaid by running the experts in a compressed latent space, which almost halves the FLOPs.

## Attention across depth

Normally layer l reads the embedding plus every earlier layer's output, all weighted alike:

`h_l = h_1 + Σ f_i(h_i)`

Nothing is selective. Worse, later layers must learn ever larger outputs to be heard over the accumulated sum, and training pays for it. AttnRes gives each term a weight from a query-key dot product — a query learned per layer, keys and values taken from earlier residual states, scores softmaxed to one. Each layer can then reach back and pull the depth it actually needs.

Doing this everywhere would be too expensive, so it is done at block boundaries every twelve decoder layers: eight blocks, roughly two per cent added latency, a 1.25x compute advantage. MLA retrieves across the context; AttnRes retrieves across depth. Both exist because a fixed-size state must throw things away.

## What it comes to

The line from GPT-2 to K3 is not one of magnitude. Each step changes what is stored, how it is updated, or how something already discarded can be fetched from elsewhere. A fixed-capacity associative memory, left to pure addition, fills and then confuses itself. It needs a policy for forgetting — gating, routing, decay — and a good way to read. So far, attention.
