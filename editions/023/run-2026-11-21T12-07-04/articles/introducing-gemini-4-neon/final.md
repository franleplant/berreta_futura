---
source_ids:
- introducing-gemini-4-neon-f539fcda
content_mode: model_card
label: MODEL CARD
---

Today, we're introducing Gemini 4 Neon, which brings frontier-level intelligence with fast end-to-end task completion across complex software engineering, knowledge work, and science workflows. At its xhigh thinking level it scores 61 on the Artificial Analysis Intelligence Index, #3 overall, just behind larger, slower models. It ranks #1 on the Artificial Analysis Coding Agent Index (58.6). It costs $3 per million input tokens and $15 per million output tokens, with a 1 million-token context window. Carbon tackles the hardest, long-horizon projects, Hydrogen handles fast everyday execution, and Neon balances depth and efficiency. It's rolling out today in the Gemini API, Gemini for business, Google Antigravity, and the Gemini app.

## Enterprise and science

Neon can synthesize spreadsheets, PDFs, charts, audio, and video in a single context window and turn them into structured deliverables.

- **Vals Index:** #2 (70.9%), on the Pareto frontier; #1 on Legal Research Bench and Tax Agent Bench.
- **Agent Arena Index:** #2 globally (1336) across 4,200+ real-world agent sessions; #2 on steerability.
- **Long-horizon and automation:** #1 on Zapier's AutomationBench (56.3%) and Andon Labs' Vending-Bench 2 ($16,843).
- **Agents' Last Exam v1.1:** on par with leading models (75.8%).
- **Science and math:** best in class on Terminal-Bench Science (70.5%), RiemannBench (84.0%), and HLE-Diamond (71.3%).

It also recorded our lowest fabrication rate yet in internal Google Antigravity testing.

## Code

Neon is engineered for long-running, tool-heavy agent workflows, alone or as an Orchestrator directing parallel Hydrogen subagents in Google Antigravity. It cuts down on redundant file reads and handles context compaction reliably in long sessions.

- Terminal-Bench 4.1: 65.2%.
- FrontierCode 2.0: 46.2% at its default high setting.
- SWE-sweep: it leads on the mini-SWE harness (12.8%) and more than triples to a state-of-the-art 39.0% in Google Antigravity.

## Cost and control

Neon has four thinking levels, so teams can dial intelligence and token spend to each workload. Cached input costs $0.15 per million tokens, a 95% discount.

- **High (default):** 32% lower cost per task than Carbon; on the Pareto frontier on Vals and Agent Arena, with roughly 50% to 80% lower cost per task than top competing frontier models.
- **Xhigh:** its highest intelligence score, while still costing 36%+ less per task than competing models at their highest setting.

## Cyber defense

- **Secure code:** more secure than Carbon across all tiers of AutoBaxBench; state-of-the-art on the hard tier (76%).
- **Penetration testing:** state-of-the-art on WebExploitBench v1.2 (51.26%) at half the cost of competing large models.
- **Finding:** state-of-the-art on SEC-bench Pro (90.5%) at roughly half the cost per challenge.
- **Validating:** frontier-level on ExploitGym using half the tokens of Carbon.
- **Patching:** 70.7% on CWE-bench v2, a 3.4% uplift over Carbon.

Gemini 4 Neon for cyber is rolling out to trusted defenders in the coming days through the Fairwind Program.

## Safety

Neon keeps Carbon-level protections against severe misuse and prompt injection, with real-time safeguards against cyber and biosecurity misuse, while declining far less legitimate work: it refused 1.98% of tasks on Terminal-Bench 4.0 and 0% on Terminal-Bench-Science.

- 0.0% cheating on Terminal-Bench 4.0, matching Carbon; shortcuts on 2.45% of tasks on our coding cheating evaluation, the lowest of any Gemini 4 model.
- 0.09% misaligned action rate on our agentic safety suite; 99.2% pass rate on our agent honesty evaluation.
- Compared with Carbon, under-service fell 43%–56% and overreach 15%–35% across effort levels.
- On Gray Swan's indirect prompt injection benchmark, with real-time safeguards at its highest thinking level, Neon resisted every attack, a 0.0% attack success rate.

Details are in the Gemini 4 Neon model card.

## Availability

- **Developers:** Gemini API paid tier in Google AI Studio and Android Studio; Google Antigravity for paid Google AI Pro and Ultra subscribers.
- **Enterprises:** Gemini for business, via the API or model drop-down, and Google Antigravity.
- **Consumers:** Google AI Pro and Ultra subscribers can select it in the Gemini app.
- **Cybersecurity defenders:** eligible Fairwind Program members over the next few days; contact your Cloud account team to request access.
