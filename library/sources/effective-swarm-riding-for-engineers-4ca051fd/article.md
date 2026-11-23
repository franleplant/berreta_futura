# Effective Swarm Riding for Engineers
By Georgios Konstantopoulos · Paradigm · November 20, 2026

Swarms are transforming software development, enabling [swarm riders](https://x.com/matthuang/status/2120209025099043286) to brute force through incredible software problems in hyperspeed, whether that is a research breakthrough or a performant and secure rewrite of a codebase. Swarms only became practical with models like Opus 5.5. Before, spawning subagents felt like doing it [for the sake of it](https://x.com/gakonst/status/2081138513962283184). But how do you make use of swarms?

***Be unreasonably ambitious.***

Training yourself to [think more ambitiously](https://danluu.com/ambitious/) is what lets you access swarms as a superpower. The [Bun in Rust rewrite](https://bun.com/blog/bun-in-rust) seemed crazy at the time, but now it seems obvious. You can now rewrite any part of your dependency stack that is slowing you down or concerns your security. You can just build your own database that's tailored to your workload now. You can roll your own cryptography. You can just produce [1000x more efficient software](https://x.com/_jxom/status/2112320010081501186). We've rebuilt [Tempo](https://tempo.com/) in >5 different languages in search of new efficiency and safety frontiers in days. Why not?

***Use Cloud Agents.***

Super obvious but no matter what you do, you'll need to run infrastructure on the cloud. It can be one of the well-known products, it can be with [Nanocode](https://github.com/nanocodexyz/nanocode), [Pi Durable](https://github.com/earendil-works/pi/tree/main/packages/durable), [Fx](https://fx.sh/), or you can do a bootleg setup with a devbox. Full guide on my setup soon!

***Say the right words.***

There seem to be some magic words that make models do the job better:

- Hillclimbing:
  - Do not say "Optimize X", say "Make this 10x faster".
  - Say "Measure and redesign for optimal IO, Mem and CPU utilization based on all our historical data".
  - Do not say "Fix all bugs", say "Differentially test this with  and close all gaps".
  - "Using TigerStyle reimplement  in ". Examples: [Tatami](https://github.com/gakonst/tatami) (tiling window manager) and [Goempo](https://github.com/gakonst/goempo) (Tempo node in Go).
- Superpowered-Find And Replace prompts:
  - "find all implicit state machines in my code, encode all correct states in the typesystem, and eliminate bug categories at compile time" [[original](https://x.com/steveruizok/status/2116552016218710389)]
  - "find shared state patterns in my code and replace them with lock-free alternatives using the tokio actor pattern"
  - "find all sequential async calls and replace with tokio::join " [[original](https://x.com/_dylanga/status/2117099613022732412)]
  - "add otel observability and measure all my bottlenecks e2e by component"
- "I am stepping away for 8hrs, believe in yourself". [[original](https://www.anthropic.com/research/riemann-zeta)]

These are some examples of things that work well for me. I think there's general principles here around persistence, thinking in higher levels of abstraction, and encoding domain specific knowledge in a few words that make these prompts effective.

***Do the simple thing.***

People tend to overcomplicate their setup.

- Use frontier models, ideally with Cyber access.
- Do not build plans, orchestration, memory, compaction, skills, or cross-review model outputs.
- Do the simple prompt in a well-setup codebase, and then get out of the way.

Each new model cycle obliterates customization over the last cycle, so less is more.

***Make your codebase swarm-ready.***

Codebases will need to be rethought around removing friction for swarms:

1. Comments waste tokens and they confuse agents. All the code you read is intermediated by agents anyway. Remove them.
2. Delete all `.skills` and `docs/` folders. Again, distractions.
3. Remove all unit tests written by the agent now and ban them in your [AGENTS.md](http://AGENTS.md). Agents are one-shotting code that doesn't need unit tests.
4. Introduce [Deterministic Simulation Tests](https://martinfowler.com/articles/deterministic-simulation-testing.html) instead. This allows agents to [automatically hunt for bugs](https://jhellerstein.github.io/blog/no-room-for-bugs/) and never repeat them.
5. Rewrite your dependencies / use [TigerStyle](https://tigerstyle.dev/). This will save you from supply chain attacks.
6. Monorepo everything, consolidate your codebases ASAP to avoid wasting everyone's time.
7. (Controversial) Push to master (hello merge queue) and remove CI. The agent thread is the new pull request & CI. This is currently debated in the engineering community. My take: A sufficiently swarm-pilled codebase is continuously tested, benchmarked, and ultimately released by the swarm itself. Of course you'll still have something that looks like CI, but I am telling you this won't be Github Actions or any neo-CI you see out there, it'll be something that runs on the same infrastructure your agents run.

I basically think there's a lot of glass to break. It will be an interesting time. I don't know what the right thing is yet, but I am definitely thinking about:

1. How much of my infrastructure / deps should I own?
2. How can I remove all the cruft that we've accumulated in our codebases over the years? Do I just start over with new codebases?
3. How can I manage the risk of doing so?

***Experiment with new ways to interact.***

Every app these days looks the same: thread sidebar on the left, chat with composer in the middle, github or a browser on the right. You can do a lot better than that. I really like currently using an Inbox that feeds me with tasks and I need to make a decision at a time (a bit like Superhuman), instead of me jumping around threads. For performance work, I am working towards a loss curve-style UI. If you are a GTM person you may need to build something to help you with optimizing your pipeline. Just build something custom for you, but do not settle for the default. If you're a creative, why not have an [infinite canvas](https://x.com/trq212/status/2122438328079524159) with parallel idea exploration?

***Conclusion.***

I think software development is going to look more like machine learning a year from now, with most developers' job tuning swarms to do well on the metrics they care about. We will need to unlearn a lot of habits & practices of the last years of software engineering.

I do very few special things with the agent itself, and spend most of my time optimizing the environment the agent operates in. Spawning a swarm from well setup environments is then just an accelerator.

Effective swarm riding to me ultimately reduces to code security, and so the area I am the most interested in right now is automated program verification and testing.

The frontier of the art of engineering is changing rapidly. If you are thinking about this, please reach out: [georgios@paradigm.xyz](mailto:georgios@paradigm.xyz).
