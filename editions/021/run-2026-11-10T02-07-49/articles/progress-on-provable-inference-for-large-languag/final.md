---
source_ids:
- progress-on-provable-inference-for-large-languag-43862ef7
content_mode: article
label: ARTICLE
---

A user who queries an AI model today cannot check that the reply came from the model the developer claims, rather than a cheaper one swapped in by a routing service or a token stream altered by an attacker. Judging by output alone is unreliable. Cryptographic proofs of inference solve this: the provider commits to a model, then proves each response was produced by it, and the proof hides the weights. We have built FlashProve, an open-source prototype based on a zkSNARK. On Llama 4 Maverick (a 400B-parameter mixture of experts, 4-bit weights), a single H100 proves around 110 tokens per second, with proofs of ~19 MB per 1,024-token request. That is ~70-95x the GPU time of running the model on vLLM. Prior open-source systems are orders of magnitude slower. Claude built the system. Its decisions in large systems are hard to evaluate, so the top-level security statements are proved in Lean. This is intermediate progress, not a finished agenda, released under Apache 2.0 so others can take it and improve it.

## Why prove inference

Most frontier weights are private. Even with the weights, checking a response means running the model, which few users or evaluators can afford. Provable inference lets someone with limited compute and no access to the weights verify that a response came from the requested model.

A zkSNARK does this. A prover convinces a verifier, through a short certificate, that a computation ran correctly. The certificate is zero-knowledge: it reveals nothing beyond that correctness. It is succinct: exponentially faster to verify than the computation it proves.

We see four uses:

- **Pacing.** A regulator may require a provider to devote hardware to inference rather than training. It can ask for proofs covering a period's requests, which the provider cannot supply unless its hardware really served the right model. This does not establish that the hardware isn't also training on the side.
- **Tamper detection.** An attacker who compromises an inference server, or a more capable model passing itself off as a weaker one to avoid monitoring, would have to produce valid proofs for the expected weights. They cannot. Our Frontier Safety Roadmap set a goal of a provable inference prototype by September 30, 2026. We met it through a separate, related project that signs our inference traffic and recomputes inference on a trusted server. This work pursues the same objective by a different method.
- **Text provenance.** Chat logs can be faked with a cheaper or degraded model. A proof attached to each response cannot. A provider could even issue a Proof-of-Failure: this model spent at least 1M tokens on a patch and found no bugs.
- **Model approval.** If only approved models may be served, a proof from an unapproved one will not verify. The regulator checks this without re-executing requests.

Prior work often relies on trusted execution environments, which depend on the manufacturer's tamper-resistant hardware. We focus on software-only cryptography, whose security rests on hard computational problems even if the hardware and operating system are compromised. The two approaches are complementary.

## How FlashProve works

In the **offline phase**, the prover publishes a commitment to the weights: a short fingerprint that pins down one exact set of weights while hiding them. This takes about 39 minutes per model. The commitment is good for about 16 million requests, after which the provider must commit again.

In the **online phase**, for each request the prover proves one statement: *the committed model produces these output tokens when evaluated.* Anyone holding the commitment, the prompt, and the reply can check it.

A proof is accepted if honest (completeness) and cannot be forged without breaking widely believed cryptographic assumptions (soundness). It reveals nothing about the weights, the intermediate values, or which experts ran (zero-knowledge). The architecture is not hidden. It is small and cheap to check (succinctness): the model is about 232 GB, the proof about 19 MB, verified in seconds on a 24-core CPU.

On one H100 with 24 CPU cores, a batch of 24 requests takes about 223 seconds, 110 tokens per second, at 18.78 MB per proof. The client downloads a ~6.5 MB commitment and checks each proof in 17 seconds on 24 threads, 21 on one. Against vLLM running the FP8 release on eight H100s, proving takes, per GPU, about 72 times longer (66 to 77 across runs), and about 94 times longer at the highest load we tried.

Three design choices carry most of this:

- The prover's work is proportional to the ~17B parameters each token actually uses, not all 400B, and the proof still hides which experts were chosen.
- Requests are proved in batches after the fact, in one parallel pass, opening the commitment once per batch.
- Layers are proved one segment at a time, with weights streamed from ~290 GB of host memory, so a single 80 GB GPU suffices.

Proving after the fact rather than in-line is slower, but need not trade security for speed. It brings the complexity of recomputation, a delay before guarantees arrive, and inherent non-determinism.

Underneath, an interactive oracle proof is compiled into a cryptographic proof using hash functions, which also gives post-quantum security.

## Why trust the code

Cryptographic code is notoriously brittle. We state completeness, soundness, and zero knowledge in Lean and prove them, in the random oracle model.

Two gaps remain. The formal statements must be audited by hand to confirm they match their intent; an interactive visualizer helps. The executable code must match the formal protocol, which depends on the property:

- **Soundness** depends only on the verifier. Trust the verifier and you can fully distrust the prover. Lean proves that our executable Lean verifier accepts only what the soundness theorem accepts. It is slow. The C++ verifier is the one for daily use. It carries no formal guarantee, and it agrees with the Lean verifier on every proof in our tests.
- **Completeness** assumes honest parties, so testing suffices: run the prover, check its proof with the Lean verifier.
- **Zero knowledge** depends only on the prover, and a Lean prover would be impractical. We provide nothing here. We expect a provider who wants to hide its weights to have the resources for careful agentic or human audits.

## Where this stands

zkML has moved fast. In 2024, zkLLM proved a 13B model at about 2.5 tokens per second on one A100. The only earlier proof of Llama 4 Maverick we know of, VerInf, took 14.3 hours for 1,000 tokens, with a 93.6 GB proof that took almost a day to verify. Commercially, Attestable reports 53–77 tokens per second for a dense 31B model, with no open-source library released at the time of writing. We believe the progress should transfer to more models and architectures, at roughly two orders of magnitude over native computation, much less than previously expected.

## Limitations

- **No formal guarantees on the fast code.** The paper and code derive from the Lean protocol, but we don't guarantee that all three match.
- **Integer model, greedy decoding.** A proof covers an exact integer version of the weights. Floating-point or sampled output could diverge. The integer version is expected, and empirically tested, to stay within a small error rate of floating-point inference, but this does not cover adversarially designed prompts.
- **Architecture is not hidden.** The system assumes a mixture-of-experts model and uses that structure for speed. Hiding the architecture as well is future work.
- **Side channels**, such as proof timing, could leak information about the weights. They are out of scope.
- **Short contexts.** Proofs cover up to 1,024 tokens, far short of the windows frontier models use.
