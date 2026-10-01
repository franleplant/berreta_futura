---
source_ids:
- openclaw-enterprise-the-open-agent-platform-open-6f725bb8
content_mode: verbatim
label: VERBATIM
---

An open source, vendor neutral platform for managing persistent agents in sensitive environments.


Today, we are excited to announce OpenClaw Enterprise (OCE), an open source, vendor neutral platform for managing persistent agents in sensitive environments.

When OpenClaw first launched, it showed the world the capabilities of a good model paired with a harness optimized for agentic work. Now almost a year later, the actual deployment of persistent agents remains limited. The main feedback we hear from organizations is that a stronger common security, safety, and governance standard is needed before agents can be fully adopted. As a consequence, the default stance of IT in most organizations is to ban agentic platforms like OpenClaw altogether.

This is the problem we are trying to solve with OCE: how do we safely deploy powerful agents without nerfing their capabilities in enterprise environments?

OpenClaw Enterprise — currently being developed in the open before its 1.0 release — introduces an enterprise grade control plane for agents and builds upon the foundation set by OpenClaw with support for multi-tenancy, hard security boundaries, and standardized agentic primitives. OCE adds governance and auditability across the agent lifecycle while making sure that core primitives like the harness, model, and sandbox can be swapped out with third party solutions as well as internal implementations.

Today, we consider OCE something that organizations can use for internal pilot workloads. We prioritized open sourcing this work early in development in order to build in the open and co-develop with the wider community ahead of the 1.0 release later this year. You can self host OCE today by cloning the [repo](https://github.com/openclaw/openclaw-enterprise) and following the [getting started guide](https://docs-enterprise.openclaw.org/). You can run OCE using docker-compose for local development and deploy internally via kubernetes.

The development of OCE has been a joint effort of multiple organizations. It originally started at OpenAI and then was donated to the OpenClaw Foundation, where it is now an independent project and has been further developed in collaboration with [Red Hat](https://www.redhat.com/en/blog/why-red-hat-building-open-foundation-enterprise-agents-openclaw-enterprise) and [NVIDIA](https://developer.nvidia.com/blog/nvidia-open-agent-safety-platform-a-reference-for-continuous-in-silicon-agent-monitoring/). OCE is built to run on your own infrastructure and will always be free for any organization to use.

OCE is being piloted internally at companies like [Red Hat](https://www.redhat.com/en/blog/why-red-hat-building-open-foundation-enterprise-agents-openclaw-enterprise) and OpenAI. OpenAI is already running OpenClaw agents with full access to codebases and plugins.

> Our internal enterprise agent Androidclaw has really been well-adopted by our team. Having it help triage in channels is just epic. It's got all our context, git, github, logging, etc. Alert about a broken build? Androidclaw finds the PR and can quickly fix it. Someone gives feedback that the work tab disappeared? Androidclaw responds in like 30 seconds with the link to the SEV. Even for hilarious, obscure things like "the streaming seems glitchy," it can trace, find a fix for, publish a PR with video evidence and merge it. Kinda game changing. It's smart.

*-RJ Marsan,* Member of the Technical Staff at OpenAI

Security is the primary focus of OpenClaw Enterprise. OCE combines hard boundaries between trusted and untrusted workloads with sandboxing, LLM-based reviews, and fine-grained permissions. In the coming weeks, we'll share a reference architecture showing how these protections work together in practice.

The OpenClaw Foundation exists to make powerful AI agents open and accessible. OpenClaw Enterprise carries that mission into the workplace, giving organizations the security, governance and deployment controls they need to run agents on their own terms. We are early, and there is much more work ahead. As we continue building, we invite developers, operators, security teams and organizations to help shape the open foundation for enterprise agents.
