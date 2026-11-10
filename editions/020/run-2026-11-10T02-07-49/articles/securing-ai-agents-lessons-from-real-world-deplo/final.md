---
source_ids:
- securing-ai-agents-lessons-from-real-world-deplo-c5293c0a
content_mode: article
label: ARTICLE
---

Agents reason over content from users, webpages, documents, tools, and other agents, and then act on it. That moves part of the attack surface into the semantic layer: prompt injection, tool and memory poisoning, goal hijacking, behavioral drift, and hallucination-driven actions. Authorization decides *who* may act. It can't decide whether a proposed action fits what the user asked, the agent's persona and intents, the user's role, and everything that has already happened in the session. So we built a defense-in-depth framework covering the whole agent lifecycle: provisioning-time validation, runtime enforcement, and continuous assurance. These controls reduced risk and raised the cost of exploitation, but did not eliminate it. The most effective mitigation was also the least glamorous: restricting agents to explicit intents and constraints, at the cost of some flexibility.

## Why access control wasn't enough

We evaluated commercial guardrail platforms that detect direct prompt injection, jailbreaks, unsafe content, and sensitive data exposure, and we considered traditional policy engines. They remain part of a defense-in-depth architecture. None fully addressed our threat model: an agent manipulated into an unintended action even when the user, agent, tool, and every API call are legitimately authorized.

Rather than maintain detection rules for the near-infinite variations of direct and indirect prompt injection, we shifted to semantic, behavior-based enforcement. Prompts and proposed actions are checked against the agent's persona, permitted intents, semantic constraints, user context, and multi-turn history. An action outside those boundaries can be denied whether or not the attack technique has been seen before. The question is no longer only "Is this agent authorized to perform this action?" but also "Should it?"

Our central lesson: security, accuracy, latency, cost, agent autonomy, and developer experience can't be optimized independently. Agent guardrails are a distributed systems and engineering problem as much as a security problem.

## The three layers

**Provisioning.** The Uber AI Registry records each agent's identity, ownership, persona, permitted intents, constraints, dependencies, and risk tier. Together these form a behavioral contract. Argus, our automated analysis platform, reads the agent's code, prompts, configurations, dependencies, endpoints, and tool-invocation paths. It finds weaknesses and derives intents, so declared behavior can be compared with observed capabilities. Third-party MCP servers and tools go through static and dynamic analysis, software composition analysis, reputation signals, and semantic inspection of tool descriptions. LLMs are evaluated before deployment, and monorepo scanning finds unregistered agents and unauthorized MCP endpoints.

**Runtime.** We kept the familiar split between policy administration, decision, and enforcement, and extended it from resources to behavior. The Registry is the policy administration point. AI Guard is the policy decision point. Agent Guard hooks, with logic integrated through LangFx or the AI Guard SDK, are the enforcement points. An agent may hold valid credentials, and the user may have access to the resource, yet the action is still denied because it falls outside the agent's intent or the session's context.

Because these checks sit in the execution path, latency is an architectural requirement. General-purpose SaaS LLMs are impractical for every decision. AI Guard runs small, specialized models locally, some fine-tuned for single guardrail functions, in parallel, with in-memory vector search where appropriate.

Secure AI is embedded at common infrastructure points, so agents inherit protection as they're created, deployed, and operated. Security becomes a platform capability rather than work every product team repeats.

**Continuous assurance.** One execution trace connects agent actions, tool calls, and guardrail decisions. Prompt and response content is captured only when needed, with sensitive information minimized or redacted, access restricted by sensitivity, and traces deleted after defined retention periods. Recorded interactions are replayed against candidate guardrails before enforcement. Automated threat modeling drives penetration testing and continuous red teaming, and findings feed back into risk scores, policies, and calibration.

## What production taught us

**False blocks and false allows.** Policies that were too tight disrupted legitimate work; policies that were too loose weakened protection. Shadow mode, traffic replay, and per-agent calibration let teams measure both against real behavior before enforcing.

**Latency.** Stacked guardrails added measurable latency. We parallelized evaluation and moved suitable decisions to smaller, specialized models, which reduced latency and inference cost while helping maintain round-trip goals.

**Developer friction.** A strong control has limited value if teams bypass it. Argus now pre-generates personas and intents, and teams review them rather than start from scratch.

**Generic controls.** Uniform guardrails and static thresholds couldn't account for agents with different purposes, tools, and risk profiles. Generic controls give a broad baseline, but the strongest protections, persona, intent, and semantic constraint enforcement, required deeper integration with each agent.

## Where it stands

Core security, safety, and privacy guardrails were in place from the start for first-party and third-party agents. PersonaGuard and end-to-end visibility strengthened that foundation. Guardrails helped against known threat patterns; against new prompt injection and manipulation techniques their effectiveness remained less predictable.

Explicit intents and constraints substantially reduced the ability to act on manipulated instructions, at the cost of some of the flexibility that makes autonomous designs attractive. That tradeoff is real, and worth making today. Constraints bind each action to the conditions that make it legitimate. Operating principles govern goal-seeking behavior, which grows more consequential the longer an agent runs unattended. Provenance and evidence chaining keep every step traceable to something a person actually asked for. These aren't scaffolding we expect to remove as models improve; they're the controls we expect to matter most as autonomy increases. Durable protection will need safeguards in the models themselves as well as these agent-level controls.

Next, we'll expand prompt provenance and evidence chaining against indirect injection, advance semantic constraints and operating principles, keep cutting latency, false blocks, and false allows, and further automate discovery, registration, persona and intent generation, guardrail assignment, red teaming, and regression testing. Later posts in this series will cover the individual controls.
