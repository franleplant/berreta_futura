---
source_ids:
- jalape-o-s-first-results-show-industry-leading-s-9edfd1ae
content_mode: article
label: ARTICLE
---

Jalapeño, our first custom inference chip, serves more AI work per unit of power and answers faster, with one architecture, where existing hardware often has to trade one for the other. Across GPT‑OSS 120B, DeepSeek R1, and Kimi K2.5 1T, it delivered 1.5 to 1.9 times more AI work per watt at peak throughput and 1.7 to 3.6 times lower end-to-end latency than the comparison systems. For highly interactive workloads, it delivered 2.1 to 4.1 times higher performance. We plan to begin deploying it within our compute infrastructure by the end of the year.

## How we measured

We evaluate performance at a matched user experience: how much useful work each system completes per unit of power while meeting the latency customers and agents require. Agents run many steps in sequence, so delays can compound across a task.

We tested on InferenceX, a public benchmark from SemiAnalysis that measures the full process of serving a request, against leading commercially available systems, from high-throughput serving to low-latency use. Although performance is sometimes reported per chip, we believe the more useful standard is performance per unit of power. We normalized results using each accelerator's published chip power rating. Jalapeño is rated at 700 watts, although its measured sustained power stayed at or below 550 watts on the workloads tested.

On Kimi, the largest public model we tested, Jalapeño delivered about 1.5 times higher peak performance per watt and 3.4 times lower end-to-end latency than the comparison system. In our internal testing, its advantage widened further on frontier OpenAI models, suggesting that the architecture becomes more valuable as workloads grow larger.

## Why the chip is fast

Inference moves through phases with different bottlenecks. Prefill, when the system processes a prompt, is compute-intensive; decode, when it generates the response token by token, is constrained more by memory bandwidth. Moving data between cores and chips adds latency and leaves units idle while they wait.

We designed Jalapeño to minimize that movement. Model state, including the KV cache, can be placed explicitly and kept local, while the system activates the right mix of compute, memory, and networking for each phase. The network's large domain keeps the whole workload within one connected system. The result is an accelerator that can excel at both prefill and decode and adapt as the balance between them changes.

## AI built the chip, and programs it

AI helped the team go from initial design to tapeout in nine months, and helped optimize the chip's arithmetic circuits so more compute fit on schedule. Jalapeño is a predictable programming target: engineers describe work through local tensors, explicit communication, and predictable synchronization, and AI optimizes how that work is mapped and scheduled.

Each new model family still requires new kernels and model-specific optimizations. Using Codex with GPT‑Astra, the team brought three open-weight models outside the original production plan to high performance within two months. For selected GPT‑OSS attention and mixture-of-experts blocks, AI-generated implementations ran 1.5 to 1.8 times faster than human-expert ones. Those figures apply to the selected blocks, not the full model.

## What comes next

More useful work from the same power and hardware can help us serve more demand and lower the cost of a successful result. Jalapeño is the first generation of a multigenerational roadmap: Gen 2 is deep in development, and Gen 3 is taking shape. We will keep deploying accelerators from NVIDIA and other partners for training and inference. Before deployment, we are continuing production qualification, maturing the software, and validating performance across more models.
