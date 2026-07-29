---
source_id: 22580-from-gpt2-to-kimi3-explained-8f01b0fe
content_mode: faithful_synthesis
label: FAITHFUL SYNTHESIS
---

Twenty-two thousand five hundred and eighty. That is how many 124-million-parameter GPT-2 models fit inside a 2.8-trillion-parameter KimiK3. The scale changed by that factor in seven years, but the architecture did not simply become a larger copy.

This progression follows the pressure created by sequence length, memory bandwidth, recurrent state, selective retrieval, and sparse capacity.

## GPT-2 and the cache

GPT-2 is a decoder-only transformer. Token and positional embeddings enter a stack of blocks. Each block applies causal self-attention and an MLP through residual connections. A final normalization and language-model head produce vocabulary logits.

During autoregressive generation, only the logits at the final position select the next token. Without caching, each new token would force the model to recompute projections for the entire preceding sequence.

The KV cache stores the keys and values from earlier tokens. It removes redundant compute, but the cache grows with sequence length and can become a memory-bandwidth bottleneck. Full softmax attention also compares every query with every key, so long contexts remain expensive even when generation is cached.

## From linear attention to DeltaNet

Softmax attention applies its nonlinearity after the query-key product. Linear attention applies a feature map to queries and keys separately, which allows the computation to be reassociated. Instead of retaining every key-value pair, the model can fold history into a fixed-size state.

That changes the scaling behavior, but it also compresses information. Multiple keys write into the same state. Similar representations interfere, and the feature map is less expressive than full softmax attention.

DeltaNet treats the state like fast weights and applies a delta rule. Before writing a new key-value association, it estimates what the current state would retrieve for that key. The update stores the difference between the desired value and the existing prediction.

The correction reduces interference. It does not make the recurrence free. Prefill still has sequential structure, and a useful implementation must recover parallel work.

Chunkwise formulations provide the bridge. A chunk can compute ordinary attention-like work within the block while carrying a recurrent state between blocks. A chunk size of one resembles pure recurrence. A chunk as large as the sequence approaches full quadratic attention. Intermediate sizes trade local pairwise capacity for bounded recurrent state.

## Gated DeltaNet

Purely additive recurrent state never forgets. A gate lets the model decay old information before applying the delta update.

Gated DeltaNet combines a Mamba-style gated recurrence with the delta rule. The gate decides how much state survives. The delta correction decides how a new association should replace what the state currently predicts.

This is more than an optimization. Fixed-size memory must choose what to preserve and what to overwrite. Gating makes that choice learnable.

## Kimi Linear

Kimi Linear builds on Gated DeltaNet with Kimi Delta Attention and more fine-grained gating. It is a hybrid architecture rather than a declaration that one mechanism replaces every other one.

The design interleaves recurrent KDA layers with periodic Multi-head Latent Attention layers. KDA provides constant-state recurrent memory. MLA can retrieve selectively from token context when compressed state is not enough.

The architecture also replaces dense MLP blocks with Mixture-of-Experts layers. Sparse routing increases parameter capacity without activating every parameter for every token. Additional projections expand the capacity of the delta path.

The important shift is division of labor. Recurrent state handles cheap continuous memory. Periodic attention performs selective reads from fuller context. Experts provide conditional computation.

## KimiK3

KimiK3 keeps the hybrid shape. Three of every four attention layers use Kimi Delta Attention, while the fourth uses Multi-head Latent Attention. Its feed-forward capacity comes from a large Mixture-of-Experts system.

The model has 898 experts in total. Two are shared, while the router selects among the remaining experts for each token. The experts operate in a compressed latent space, reducing the cost of sparse capacity.

Gated MLA controls how much of each retrieved feature passes into the residual stream. MLA query compression and output gating reduce the cost and regulate what the attention layer contributes.

KimiK3 also uses blockwise attention residuals. A standard transformer carries one residual stream through every layer. Here, blocks can retrieve from accumulated attention and MLP outputs across a group of layers. The model gains selective access across depth without paying for that mechanism at every layer.

The recurrence and depth mechanisms address related losses. KDA compresses sequence history into fixed state and must discard information. MLA can retrieve from the token context. Blockwise residual access lets later layers recover selected information from earlier computation.

## What changed

The progression from GPT-2 to KimiK3 is not a straight replacement of attention.

The KV cache avoids recomputing the past but keeps a growing memory. Linear attention compresses the past into fixed state but loses expressive precision. DeltaNet corrects writes to reduce interference. Gating learns what to forget. KDA makes those updates more selective. Periodic MLA restores full-context retrieval. Sparse experts add conditional capacity. Blockwise residual access adds selective depth-wise memory.

KimiK3 combines constant-state recurrent memory, periodic softmax retrieval, sparse expert capacity, and selective access across layers. The model is vastly larger than GPT-2, but the more interesting story is how its components divide the work that one uniform transformer block once tried to do alone.
