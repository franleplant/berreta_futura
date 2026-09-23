The widespread adoption of long-horizon agents has made model workloads increasingly input-heavy.

To address this challenge, we introduce DeepSeek-V4.1-Flash, a multimodal Mixture-of-Experts (MoE) model with 552B backbone parameters and support for contexts of up to one million tokens. With its Causal Encoder-Decoder (CED) architecture, the model activates 16B parameters per token during decode but only 8B parameters during prefill, substantially improving cost efficiency for agentic workloads.

To push the limits of KV cache compression, DeepSeek-V4.1-Flash combines cross-layer KV cache reuse in Compressed Sparse Attention 2 (CSA2) with FP4 KV caching.

We pretrain DeepSeek-V4.1-Flash on a multimodal corpus comprising 45T tokens and conduct comprehensive post-training, yielding strong performance across diverse text-based and multimodal agentic scenarios.

Figure 1 | (a) Performance of DeepSeek-V4.1-Flash and its counterparts on agentic benchmarks.

(b) Global KV cache size per token (in bytes) across generations of DeepSeek models, highlight-ing DeepSeek’s sustained efforts to reduce context memory requirements.

Applications of long-horizon agents have expanded rapidly in recent years, making ultra-long-context processing an increasingly important model workload.

For sufficiently long sequences, global KV therefore dominates the runtime KV footprint, which is constrained by HBM capacity. In addition, certain KV are persisted for prefix reuse, referred to as persistent KV caches, which are constrained by SSD and host memory capacity.

Despite being considerably larger than DeepSeek-V4-Flash, DeepSeek-V4.1-Flash requires only approximately 1/4 as much runtime KV cache storage and 1/8 as much persistent KV cache storage at the same sequence length.

This level of KV cache compression is achieved through joint optimizations in model archi-tecture, cache precision, and deployment strategy.

In addition, different from DeepSeek-V4 that employs the Compressed Sparse Attention (CSA)–Heavily Compressed Attention (HCA) hybrid architecture, DeepSeek-V4.1-Flash uses pure CSA2.
