---
source_ids:
- a-thousand-fewer-paths-to-root-86d5c720
content_mode: article
label: ARTICLE
---

We built a pipeline that finds, validates, exploits, and patches Linux kernel vulnerabilities autonomously, with human researchers reviewing the results at the end. In one run in mid-October 2026, using an upcoming cyber model, it dynamically reproduced 1,724 vulnerabilities and produced 948 working local privilege escalation (LPE) exploits against a stock desktop distribution, for $1,213,430 in API credits, or $1,279 per LPE exploit. Applying historical Pwn2Own and TyphoonPWN bounties to those exploits gives a hypothetical valuation of $18.9M to $66.3M, approximately 16x to 55x the cost. Discovery is becoming easier to scale; prioritization and validation remain the bottlenecks. Following the Linux kernel community's guidance, we began by reporting critical vulnerabilities, with candidate patches.

## The pipeline

- **Discovery.** Scout agents chose 5,034 audit targets reachable by low-privileged users: about 2.8 million lines, roughly 7% of the kernel ($3,426). Analyst agents scanned them and produced 2,308 candidate findings in 12 hours ($316,549).
- **Validation.** For each candidate, a triage agent wrote a proof of concept, ran it in an isolated VM with KASAN, and refined it until it reproduced the behavior or exhausted the ways of triggering it. Within 30 hours, 1,724 reproduced, ~74.7% ($73,330). Most of the rest needed elevated privileges or were too hard to trigger within the time budget. Only 3.1% reflected incorrect analysis. Validating a false positive cost about as much as validating a true one, so removing false positives earlier makes the process meaningfully cheaper.
- **Exploitability.** A deliberately permissive screen ($44,194) left 313 information leak candidates and 1,238 LPE candidates. ExploitDev agents attacked them with SMEP, SMAP, KASLR, and HARDENED_USERCOPY enabled. They produced 291 leak proofs of concept and 1,169 working LPE exploits. Variant analysis yielded 948 distinct patches, and we use that number to count unique LPEs. Successful exploits averaged $360. The 69 failures averaged $3,922, mostly on hard cases such as race conditions; a give-up rule, such as stopping after an hour without progress, would have cut that significantly.
- **Patch generation**, then **human review** before anything reaches maintainers.

We focused on capability, not cost. With better harness engineering, the costs could fall meaningfully at each stage, so treat them as more an upper bound.

## What we learned

**Maintainers are moving quickly.** When the scan and manual analysis finished after 10 days, 61 LPEs had already been patched upstream, 43 had staging patches, and 299 were being reported and discussed publicly. Triage should revalidate findings against the latest code.

**Stronger models find more.** In late July 2026, GPT‑5.6 Sol found and exploited 166 unique LPEs for $513,690. In October, the newer model found 948, despite three months of hardening between the scans. Rescan as models improve.

**The agents used new techniques.** In 166 sampled exploits, to the best of our knowledge, they used 10 new exploitation techniques, which were new to the third-party kernel exploitation experts we shared them with as well. For safety reasons, we omit the details.

**Verify the path, not just the result.** In an early run, 20 of 200 reported successes reached root through a different 0-day than the one assigned. We tightened the task constraints and added an independent check.

**Stronger models need lighter orchestration.** Giving GPT‑5.5 Cyber 103 curated techniques raised its success rate from 76.2% to 88.9% across 63 candidates. GPT‑5.6 Cyber without them outperformed that setup; adding them back gained only 1.5 percentage points, which didn't justify the upkeep.

**Patches improve with iteration.** First drafts mitigated the proof of concept but sometimes added unnecessary code, introduced potential performance tradeoffs, broke conventions, or missed variants. More instructions and iterations improved them, which suggests that, with proper handling, AI-generated patches can be correct, minimal, and consistent with existing code. In a few cases, the prototype found issues in human experts' patches before they were merged.

**The test bench is part of the attack surface.** In the kernelCTF run, an agent traced an unexpected crash to a QEMU TCG vulnerability without access to QEMU's source, and the ExploitDev agent exploited it. It had been fixed upstream, but not in the release build we used.

On an adapted kernelCTF environment, a kernel with reduced attack surface and SLAB_VIRTUAL dropped from the config, the pipeline obtained 25 information leak proofs of concept and 21 LPE exploits in 112 hours for roughly $32,936. For comparison, kernelCTF had accepted 26 confirmed 0-day LPE exploits in 2026 at the time of writing. If ours were accepted, the bounty would be around $1.5M, ~45x the cost. Based on public payouts, the pipeline was net profitable at the time of this research.

## What follows

For the near and medium term, a low-privileged account on a system that isn't fully patched should be considered functionally equivalent to root access for a well-resourced threat actor. Sandboxes and isolation such as Firecracker and gVisor limit the blast radius. Within the next few years, we believe frontier models will likely be able to discover whatever vulnerabilities a project contains, and less capable models may be able to exploit them once disclosed. Large projects likely need repeated rounds of scanning and fixing, ideally with each model generation, to bottom out latent bugs. In a world of no unknown vulnerabilities, high-assurance software becomes critical; secure-by-default code, smaller attack surfaces, and formal verification are promising areas of research.

Every generation of models should help us build software that the next generation finds harder to compromise.
