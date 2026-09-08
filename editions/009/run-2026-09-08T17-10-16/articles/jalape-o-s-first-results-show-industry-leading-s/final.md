---
source_ids:
- jalape-o-s-first-results-show-industry-leading-s-9edfd1ae
content_mode: article
label: ARTICLE
---

Jalapeño, our first custom inference chip, is working silicon with measured results. Across GPT‑OSS 120B, DeepSeek R1, and Kimi K2.5 1T it delivered 1.5 to 1.9 times more AI work per watt at peak throughput and 1.7 to 3.6 times lower end-to-end latency than the comparison systems, and 2.1 to 4.1 times higher performance on highly interactive workloads. Higher throughput and lower latency from one architecture, where existing systems often trade one for the other. We plan to begin deploying it inside OpenAI's compute infrastructure by the end of the year.

## What we measured

We tested on InferenceX, a public benchmark from SemiAnalysis that measures the full process of serving a request, against leading commercially available systems across the tested operating range. We evaluate at a matched user experience: useful work per unit of power while meeting the latency customers and interactive agents require. Agents run many steps in sequence, so delays compound.

Performance is sometimes reported per chip. We believe performance per unit of power is the more useful standard. We normalized using each accelerator's published chip power rating. Jalapeño is rated at 700 watts, though its measured sustained power stayed at or below 550 watts on the workloads tested. On Kimi, the largest public model we tested, it delivered approximately 1.5 times higher peak performance per watt and 3.4 times lower end-to-end latency. In internal testing the advantage widened on frontier OpenAI models, suggesting the architecture becomes more valuable as workloads grow larger and more demanding.

## Why it is fast

We asked what hardware we would build if its primary job were serving modern and future language models, especially interactive agents. Inference moves through phases with different bottlenecks: prefill is compute-intensive, decode is constrained more by memory bandwidth, and communication between cores and chips leaves processing units idle while they wait. We designed Jalapeño to minimize that movement. Model state, including the KV cache, can be explicitly placed and kept local while the system activates the right combination of compute, memory, and networking for each phase. The network's large domain keeps the whole workload inside one connected system. The result is a balanced and fungible accelerator that excels at both prefill and decode and adapts as the balance between them changes.

## AI on both sides of the chip

AI helped take Jalapeño from initial design to tapeout in nine months, shortening design, measurement, and verification loops, and helped optimize its arithmetic circuits. The chip was then made a clear, predictable target for humans and AI alike: local tensors, explicit communication, predictable synchronization, with AI optimizing how work is mapped, placed, and scheduled.

New model families still require new kernels and model-specific optimizations. Using Codex with GPT‑Astra, the team brought three open-weight models that were not part of the original production plan to high performance within two months. For selected GPT‑OSS attention and mixture-of-experts blocks, AI-generated implementations ran 1.5 to 1.8 times faster than the existing human-expert-written implementations. Those figures apply to the selected blocks, not the full model.

## The path ahead

More useful work from the same power and hardware means more demand served and a lower cost per successful result. Jalapeño is the first generation of a multigenerational roadmap: Gen 2 is deep in development, Gen 3 is taking shape. We are continuing production qualification, maturing the software, and validating performance across more models. Meeting growing demand will require compute from every available source, and we will continue to widely deploy accelerators from NVIDIA and other partners for both training and inference.
