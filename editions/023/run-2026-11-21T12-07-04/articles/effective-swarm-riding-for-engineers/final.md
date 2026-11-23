---
source_ids:
- effective-swarm-riding-for-engineers-4ca051fd
content_mode: article
label: ARTICLE
---

Swarms let you brute-force hard software problems at speed, and they only became practical with models like Opus 5.5. Be unreasonably ambitious, run your agents in the cloud, say the right words, keep the setup simple, and strip your codebase of whatever slows a swarm down. I spend most of my time on the environment, not the agent.

## Be unreasonably ambitious

Thinking more ambitiously is what lets you use swarms as a superpower. The Bun in Rust rewrite seemed crazy at the time; now it seems obvious. You can rewrite any part of your dependency stack that slows you down or concerns your security, build a database tailored to your workload, roll your own cryptography. We've rebuilt Tempo in more than five languages in days, in search of new efficiency and safety frontiers. Why not?

## Use cloud agents

Whatever you do, you'll need to run infrastructure on the cloud: a well-known product, Nanocode, Pi Durable, Fx, or a bootleg devbox.

## Say the right words

There seem to be some magic words that make models do the job better:

- Do not say "Optimize X", say "Make this 10x faster".
- Do not say "Fix all bugs", say "Differentially test this with … and close all gaps".
- "Find all implicit state machines in my code, encode all correct states in the typesystem, and eliminate bug categories at compile time."
- "I am stepping away for 8hrs, believe in yourself."

These work well for me. I think the general principles are persistence, thinking at higher levels of abstraction, and encoding domain-specific knowledge in a few words.

## Do the simple thing

People tend to overcomplicate their setup. Use frontier models, ideally with Cyber access. Do not build plans, orchestration, memory, compaction, skills, or cross-review of model outputs. Give the simple prompt in a well-set-up codebase, then get out of the way. Each new model cycle obliterates the last cycle's customization, so less is more.

## Make your codebase swarm-ready

Codebases will need to be rethought around removing friction for swarms:

- Remove comments. They waste tokens and confuse agents, and all the code you read is intermediated by agents anyway.
- Delete all `.skills` and `docs/` folders; they're distractions.
- Remove agent-written unit tests and ban them in your AGENTS.md. Agents are one-shotting code that doesn't need them.
- Introduce Deterministic Simulation Tests instead, so agents can hunt for bugs automatically and never repeat them.
- Rewrite your dependencies or use TigerStyle. This will save you from supply chain attacks.
- Monorepo everything.
- (Controversial, and currently debated.) Push to master and remove CI. The agent thread is the new pull request and CI. My take: a sufficiently swarm-pilled codebase is continuously tested, benchmarked, and released by the swarm itself. You'll still have something that looks like CI, but it won't be GitHub Actions; it'll run on the same infrastructure your agents run.

There's a lot of glass to break. I don't know what the right thing is yet, but I am thinking about how much of my infrastructure and dependencies I should own, whether to remove the accumulated cruft or just start over with new codebases, and how to manage the risk of doing so.

## Experiment with new ways to interact

Every app looks the same: threads on the left, chat in the middle, GitHub or a browser on the right. You can do a lot better. I like an inbox that feeds me one decision at a time, a bit like Superhuman, instead of jumping around threads. For performance work, I am working towards a loss curve-style UI. Build something custom for you; do not settle for the default.

## Conclusion

I think software development is going to look more like machine learning a year from now, with most developers tuning swarms to do well on the metrics they care about. We will need to unlearn a lot of habits. Spawning a swarm from a well-set-up environment is just an accelerator. Effective swarm riding to me ultimately reduces to code security, so the area I am most interested in right now is automated program verification and testing.
