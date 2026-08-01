result: changes_required
findings:
  - severity: major
    article: from-gpt2-to-kimi3
    locator: "- | We scaled up by a factor of 22,580 in seven years. | 1"
    category: duplication
    note: |
      The headline number is spent twice in three sentences. First: "Twenty-two
      thousand five hundred and eighty. That's how many GPT-2 models from 2019
      fit inside KimiK3 from 2026, 124 million parameters against 2.8
      trillion." Then immediately: "We scaled up by a factor of 22,580 in seven
      years." The third sentence restates the first two in digits and adds only
      the span, which the reader has already computed from "2019" and "2026" in
      the sentence above it. The two-sentence version is the stronger opener
      and the restatement blunts it, because the reader who just absorbed a
      spelled-out number is made to absorb it again as numerals before the
      piece has moved anywhere.
    suggestion: "Cut the sentence and run \"124 million parameters against 2.8 trillion\" straight into \"But is it just... scale?\""
  - severity: major
    article: from-gpt2-to-kimi3
    locator: "From linear attention to DeltaNet | The paper's O(N²) framing threw me off. | 1"
    category: orphan_referent
    note: |
      Three referents point at a document this article does not contain. "The
      paper's O(N²) framing threw me off." introduces a paper the piece has
      never mentioned; the reader looks back for it and finds nothing.
      "That's what Flash Attention fixes... then I saw that it was released in
      2020." depends on a moment of reading that the article does not stage,
      so "then I saw" is a beat in a story the reader is not in. Worst is
      "Parallelizing that is the most difficult section of the post.", which
      hands the reader the table of contents of a different document: this is
      not a post, it has no section by that name, and the sentence measures
      difficulty against a structure that is not on the page. Each is also the
      point at which the narrator switches to first person for the first time,
      so the reader is absorbing an unexplained "I" and an unexplained "the
      paper" in the same sentence.
    suggestion: "Name the source once on first reference: \"Kimi's own writeup frames the cost as O(N²), which threw me off.\""
  - severity: major
    article: from-gpt2-to-kimi3
    locator: "GPT-2 and the cache | GPT-2 is a decoder-only architecture, and its inefficiency is this: | 1"
    category: repeated_cadence
    note: |
      One sentence shape carries most of the piece's explanatory weight:
      abstract label, colon, gloss. Six instances. "GPT-2 is a decoder-only
      architecture, and its inefficiency is this: the model computes
      representations..."; "That addition is also the source of the efficiency
      gain: updating additively rather than by concatenation..."; "The problem
      is prefill: the delta rule needs a correction at every key vector..."
      "That is the Mamba-2 contribution: decay the previous cache..."; "Kimi
      Linear drew attention for one central claim: under controlled
      comparisons..."; "That capacity has a specific mathematical purpose: the
      per-channel scale gives finer control over memory decay." Three of the
      six open on a bare demonstrative ("That is", "That addition is", "That
      capacity has"), which is the version that tires fastest, because the
      reader has to resolve "that" before the colon pays out. The last one is
      also empty: the sentence before it already said the gating is per-channel
      rather than scalar, so "the per-channel scale gives finer control over
      memory decay" announces a purpose and then restates the mechanism as if
      it were the purpose.
    suggestion: "Recast at least four as plain subject-verb: \"Prefill is the problem. The delta rule needs a correction at every key vector, so the path to a parallel matrix multiplication is not obvious.\""
  - severity: major
    article: from-gpt2-to-kimi3
    locator: "Kimi K3 | At first glance the remaining changes appear modest: more scale, gated MLA, latent-space MoE, SiTU activations, and blockwise attention residuals every 12 layers. | 1"
    category: jargon
    note: |
      Five terms, four of them never defined anywhere in the piece, presented
      to the reader as "modest". Gated MLA is a modifier on an expansion given
      one sentence earlier and survives; latent-space MoE, SiTU activations and
      blockwise attention residuals arrive cold, and only the last is picked up
      by the paragraph that follows. The engineering manager the magazine
      writes for reaches this sentence having followed the argument cleanly
      through caches, linear attention, the delta rule and gating, and is
      stopped by a list that tells them these things are unremarkable while
      giving them no way to judge that. The problem is the enumeration, not the
      density: elsewhere the piece defines what it uses.
    suggestion: "Keep only the item the section explains: \"At first glance the remaining changes appear modest, until the last of them: blockwise attention residuals every 12 layers.\""
  - severity: major
    article: from-gpt2-to-kimi3
    locator: "Kimi K3 | Each architectural step changes what the model stores, how it updates that state, or how it retrieves information that a fixed-size state cannot preserve. | 1"
    repair_from: "- | But is it just... scale? Here is how much, or how little, actually changed. | 1"
    category: ending
    note: |
      The close summarises instead of landing, and it never answers the
      question the opening asked. The opening promises "But is it just...
      scale? Here is how much, or how little, actually changed", which sets up
      a verdict. The final paragraph delivers a taxonomy: store, update,
      retrieve; then an eviction-policy restatement; then "Learned selection,
      like gating, routing, or decay, is necessary."; then "Attention is the
      most effective selective-read mechanism." Two abstract three-item lists
      inside four sentences, one of them the penultimate line. Nothing here is
      new to a reader who has read the preceding four sections, which is the
      definition of a closing paragraph that restates what the reader just
      read. The last line is the interesting one, because after a whole piece
      about replacing full attention it says attention wins anyway, but it
      arrives as a flat assertion at the end of a summary rather than as the
      answer to "is it just scale?" The frame is set in the opening, so that is
      where the repair starts.
    suggestion: "Cut the paragraph to its reversal and answer the opening: \"So not just scale. Every step since GPT-2 is an argument about what to throw away, and the winner of that argument is still attention.\""
  - severity: minor
    article: from-gpt2-to-kimi3
    locator: "Kimi K3 | The KimiK3 language backbone looks similar to Kimi Linear | 1"
    category: house_style
    note: |
      The model's name is spelled two ways and the notation is set two ways.
      The heading reads "Kimi K3" while the body under it reads "The KimiK3
      language backbone", and the opening also uses "KimiK3". Separately, "This
      makes the product re-associable, so the growing set of K and V vectors
      can be folded into a fixed D×D state" later becomes "it is added to the
      same D by D matrix". Both are the same object described two ways within
      a few hundred words, and on the page a reader briefly wonders whether
      they are different things. Editor-owned copy-fitting, so fully
      actionable.
    suggestion: "Settle on \"Kimi K3\" and \"D x D\" throughout, heading and body alike."
  - severity: minor
    article: from-gpt2-to-kimi3
    locator: "From linear attention to DeltaNet | Old information is removed and new information is written in its place. | 1"
    category: passive
    note: |
      Two passives in one short sentence with the actor named in the sentence
      immediately before it. The paragraph has just walked through the delta
      rule's update as a sequence of things the update does ("asks what the
      current key retrieves", "subtracts that", "multiplies the key",
      "adds the result back"), all active, all with the rule as subject, and
      then the summary line drops the subject. The sentence is the payoff of
      the paragraph and it is the one that goes limp.
    suggestion: "The rule removes the old information and writes the new information in its place."
  - severity: minor
    article: from-gpt2-to-kimi3
    locator: "Kimi K3 | for roughly 2% inference latency and a 1.25x compute advantage | 1"
    category: dead_words
    note: |
      The clause does not parse on one read. "KimiK3 runs it at block
      boundaries every 12 decoder layers, eight blocks in all, for roughly 2%
      inference latency and a 1.25x compute advantage." Two percent of what,
      and added or total? A cost paid and an advantage gained are set in the
      same list joined by "and", so the reader cannot tell which side of the
      ledger each sits on until they work it out. This is the one place a
      reader has to stop and reconstruct the sentence rather than the idea.
    suggestion: "for roughly 2% added inference latency, against a 1.25x compute advantage"
scores:
  structure: 3
  flow: 2
  sentence_craft: 2
  house_style: 3
  voice_consistency: 2
notes: |
  The spine is genuinely good and I could restate it after one read: the KV
  cache grows without bound, linear attention trades it for a fixed state,
  the fixed state interferes, the delta rule restores recoverability, gating
  adds the ability to forget, per-channel gating makes forgetting selective,
  and K3 alternates that against periodic full attention while doing the same
  trick down the depth axis. Four sections, each one earning the next. What
  works against it is the surface. The prose keeps reaching for the same
  device, an abstract noun and a colon, until the explanations start sounding
  interchangeable, and the voice cannot decide whether it is a narrator or an
  exposition. Most of the piece is impersonal technical prose; then a first
  person appears twice to report hours spent and confusion felt, pointing at a
  paper and a post the reader cannot see. That is where I went back a
  paragraph, and it is also what breaks the "one writer's continuous prose"
  test: the reading-diary asides and the synthesised exposition are audibly
  different hands. The opener is close to right and spoils itself with a third
  sentence that repeats the second; the close then abandons the question the
  opener asked and summarises instead. Density is mostly earned, with one
  exception: a five-item list of undefined acronyms called "modest" in the
  section where the manager reader is most likely to be lost. No U+2014
  anywhere and the headings are sentence-case, so house style is otherwise
  clean.
