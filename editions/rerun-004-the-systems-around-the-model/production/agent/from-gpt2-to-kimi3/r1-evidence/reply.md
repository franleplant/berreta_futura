result: changes_required
findings:
  - severity: major
    article: from-gpt2-to-kimi3
    locator: "From linear attention to DeltaNet | The answer is chunks of size C. | 1"
    category: qualification_loss
    note: |
      The manuscript states the delta-rule prefill problem and then answers it
      directly: "The problem is prefill: the delta rule needs a correction at
      every key vector, so the path to a parallel matrix multiplication is not
      obvious. The answer is chunks of size C. Inside a block I do real
      attention (the masked QK-transpose times V), and across blocks I fold
      everything into the state and read it back with one matmul."

      The source raises an explicit counterpoint against exactly that move and
      the manuscript drops it: "The underlying issue is simple: the chunking
      method used for purely additive attention does not directly apply to the
      delta updates" and "We need every single state in order to compute the
      information that needs to be subtracted out. We can't parallelize it the
      same way without some mathematical re-parameterization. The authors
      therefore rewrite the delta updates". The source then gives the
      reparameterized form (S_t = S_{t-1}(I - beta_t k_t k_t-transpose) +
      beta_t v_t k_t-transpose) and a chunked delta kernel whose intra-chunk
      term uses corrected values u_i, not v_i.

      The two sentences the manuscript keeps ("Inside a block I do real
      attention... C=N recovers standard O(N^2) attention and C=1 gives regular
      linear attention") are, in the source, a description of chunked purely
      additive linear attention, offered before the delta extension and then
      explicitly disclaimed for it. As condensed, the reader comes away
      believing plain chunked attention is sufficient for the delta rule, which
      is the one thing the source says it is not. Scope of the claim is
      distorted, not merely abbreviated.
  - severity: major
    article: from-gpt2-to-kimi3
    locator: "Gated DeltaNet and Kimi Linear | a drop-in architectural replacement with better quality and up to 6x higher decode throughput | 1"
    category: attribution_error
    note: |
      The source attributes this to the Kimi Linear authors: "Kimi Linear drew
      attention for one central claim: under controlled comparisons, it
      outperformed full attention. The authors presented it as a drop-in
      architectural replacement with better quality and up to 6x higher decode
      throughput."

      The manuscript deletes "The authors presented it as" and welds the
      remainder onto the preceding clause as an appositive: "under controlled
      comparisons, it outperformed full attention, a drop-in architectural
      replacement with better quality and up to 6x higher decode throughput."
      The drop-in status, the quality claim and the 6x decode figure now read
      as the article's own assertions of fact rather than as the paper's
      self-presentation. The numbers are correct; the attribution hedge that
      governed them is gone.
  - severity: minor
    article: from-gpt2-to-kimi3
    locator: "From linear attention to DeltaNet | then I saw that it was released in 2020. | 1"
    category: qualification_loss
    note: |
      The source follows its own aside with a defense of the paper it just
      corrected: "At the time, training commonly materialized the full NxN
      attention matrix, FlashAttention did not exist, and reference
      autoregressive implementations often recomputed the token history without
      a KV cache."

      The manuscript keeps the flat correction ("It's not true that...") and
      the retraction marker ("then I saw that it was released in 2020") but
      drops the sentence that explains why the paper's O(N-squared) framing was
      accurate for its moment. The self-correction survives implicitly through
      the retained date, which is why this is minor rather than major, but the
      criticism now reads harder than the source lets it stand.
scores:
  claim_support: 4
  qualification_survival: 3
  quote_accuracy: 5
  attribution: 3
notes: |
  I read the pinned extraction of 22580-from-gpt2-to-kimi3-explained-8f01b0fe
  in full, then listed every checkable assertion in the manuscript including
  the untitled opener, the four section headings, and the closing thesis. Every
  number, date, version and benchmark checks out against the extraction:
  22,580; 124M against 2.8 trillion (2.8e12/1.24e8 = 22,580.6, consistent);
  seven years; 2019 and 2026; N-1 cached tokens; ELU+1; the DxD state; Flash
  Attention released in 2020; seven hours; C=N and C=1; 6x decode throughput;
  23 four-layer macrocycles with three KDA layers and a fourth MLA layer; every
  12 decoder layers; eight AttnRes blocks (92 layers / 12 rounds to 8,
  matching the source's own count); roughly 2% inference latency; 1.25x compute
  advantage; the Mamba-2 attribution for gated decay. The one span presented as
  verbatim, "the cost per time-step for transformers scales with the square of
  the current sequence length", matches the extraction character for character.
  The byline ali matches the post's author. The closing conclusion (fixed-
  capacity associative memory needs an eviction policy; learned selection is
  necessary; attention is the most effective selective-read mechanism) is the
  source's own and is carried intact, as is "Scaling laws remain relevant, but
  capacity must be added in the right place". Dropped material I judged
  permissible condensation rather than finding: the code listings, the Schlag
  quotation, the C=64/128 tensor-core aside, the three-step attention contract,
  the MoE expert counts (898/896/16), the SiTU kernel-cost discussion, MLA query
  LoRA and output gating, and the softmax normalization detail in the AttnRes
  weights. The manuscript's "It cannot clear several associations" drops the
  source's "efficiently", but the source independently states the Delta rule
  "has no way to make the rest of the facts decay", so the absolute reading is
  grounded and I did not flag it. What I could not check: nothing in the
  manuscript falls outside the extraction's coverage, so there are no
  uncheckable assertions; the extraction itself is a screen-scraped post with
  interleaved "Don't miss what's happening" chrome and several figures rendered
  only as gaps, so any claim resting on an image would have been unverifiable,
  but the manuscript makes none.
