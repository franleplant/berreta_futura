# Your AI coding agents need a manager

By Addy Osmani · addyosmani.com · January 8, 2026

**The skills that make someone a strong tech lead or manager translate directly to AI coding. Once you’re running multiple agents in parallel, you stop just debugging context and start managing a team. Clarity, delegation, verification loops, async communication. The shape of the work is changing as [orchestration](https://addyosmani.com/blog/future-agentic-coding/) becomes more mainstream.**

In the near future, I think the highest-leverage developers will look like **async-first managers** running a small fleet of parallel AI coding agents. Agents can now do meaningful work in the background, in isolated environments, and return with something reviewable - often a pull request. We of course require quality checks, but the bottleneck is no longer “can the agent write code?” It’s “should we build this?” and “can I manage multiple agents doing so effectively?”.

We’re seeing the [workflows](https://code.claude.com/docs/en/common-workflows) that foreshadow this future. A recent [thread](https://twitter-thread.com/t/2007179832300581177) from Boris Cherny, Claude Code’s creator, went viral because it made the shift feel concrete: he runs five Claude Code sessions locally in terminal tabs, plus another five to ten in the browser, and even starts sessions from his phone to check on later. That’s orchestration.

At the same time, thoughtful engineers have been documenting the parallel agent lifestyle from a more skeptical angle. Simon Willison’s [take](https://simonwillison.net/2025/Oct/5/parallel-coding-agents/) is the one I keep coming back to: the natural bottleneck isn’t generating code - it’s reviewing it. He still found real value in firing off parallel tasks, so long as you’re honest about your attention span and choose tasks that don’t overload your brain. I’ve been building similar workflows and agree: the value is real, but only if you treat it like management, not magic.

This is the mindset shift: you’re no longer pairing with a single agent. You’re running a small team.

This is the reason the skills that make someone a strong tech lead, engineering manager, or engineering leader suddenly translate directly into “being good at AI coding.” Because AI coding at scale stops being a prompting problem and becomes a management problem.

## A mental model for the new workflow

I think about two modes running side-by-side.

The first is **local, high-touch sessions where you stay [human-in-the-loop](https://addyosmani.com/agentic-engineering/human-in-the-loop/)**. These are for architecture decisions, tricky refactors, product nuance, ambiguous requirements, and anything where taste and judgment dominate. You’re pairing with the agent, course-correcting in real time, and making calls that require context the agent doesn’t have.

The second is **cloud or background sessions that run asynchronously**. These are for focused, bounded tasks: straightforward features, migrations with clear patterns, test generation, documentation updates, dependency bumps, small bugfixes, and targeted refactors. You fire them off, context-switch to something else, and come back to review the output.

This split maps cleanly onto how modern tools are evolving. Cloud agents (think GitHub Copilot Agent, Claude Web, Codex, Jules etc.) are explicitly positioned as parallelizable, [sandboxed](https://addyosmani.com/agentic-engineering/sandboxing/) tasks that can write code, run commands, and propose changes for review.

GitHub’s Copilot coding agent frames itself similarly - an asynchronous background agent that opens a draft PR, works in the background, then requests review where you can comment and have it iterate. And platforms are moving toward “mission control” dashboards for multiple agents, not just one. GitHub even previewed “Agent HQ” as a control plane for coordinating multiple third-party coding agents in one place, including running them in parallel on the same tasks to compare outputs.

So the question becomes less “which model writes the best code?” and more “can I run this like a high-performing team?”

That’s where manager skills show up.

## Why manager skills make you a better AI coder

*I’ve written about [effective management skills](https://leanpub.com/effective-software-engineering-management) in some depth*

When you manage humans, you learn the hard way that output quality is shaped upstream. Ambiguity, fuzzy ownership, missing definitions of done, and lack of feedback loops create churn. The same is true - maybe even more true - when your “team” is a set of fast, non-human agents.

Anthropic’s best-practices guide for Claude Code says this plainly: specificity up front materially improves success rate and reduces course correction. That’s manager language, even if it’s written for a tool.

Here are the four skills that transfer most directly.

### Clear task scoping: Write a brief, not a vibe

If ambiguity kills agent effectiveness, then your job is to turn idea-shaped thoughts into a brief that can survive contact with implementation. This is exactly what good managers do: convert intent into something executable.

A practical agent brief covers: the outcome (what should be true when we’re done), the context (where in the codebase this lives and what patterns exist), the constraints (performance, security, API shape, dependency rules, style conventions), the non-goals (what we’re explicitly not doing), acceptance criteria (concrete checks like tests passing or endpoints behaving a certain way), integration notes (which files are off-limits and where seams should be), and a verification plan (how we’ll know it works).

This is the difference between getting a clean PR and getting a thousand-line mess you can’t trust.

Two tactics make this dramatically easier. First, point agents at existing patterns - Anthropic’s guide explicitly recommends mentioning the files you want the agent to follow or update, so it anchors on real conventions instead of inventing its own.

Second, put durable rules somewhere agents can always find them. Now standard, OpenAI’s Codex docs describe using your `AGENTS.md` file to give consistent expectations about tests to run, lint rules, dependency policies, and documentation requirements. If you’ve ever onboarded someone new to a codebase, this will feel familiar: give them the map, the conventions, and the definition of done before they start writing.

### Delegation: Decide what to fully hand off vs. what needs your judgment

A surprising trap with agents is over-delegating the parts that are actually human work: product intent, API design tradeoffs, architectural boundaries, and long-term maintenance calls.

OpenAI’s “AI-native engineering team” guide frames this as a three-part split across the software development lifecycle: delegate, review, own. Even in their optimistic view, engineers keep ownership of final decisions and sign-off, especially for ambiguous problems.

That maps cleanly onto orchestration. Some work you can fully delegate - mechanical implementation with a crisp spec, boilerplate refactors, test generation with strong review, docs updates, and low-risk maintenance chores. Other work you delegate but stay in the loop with checkpoints - anything touching shared interfaces, anything likely to create merge conflicts, anything with tricky product edge cases, anything involving data migrations. And some work you simply don’t delegate, or delegate only to explore options - system architecture and new abstractions, cross-cutting refactors that require taste, product decisions and “should we build this?” calls, and security-critical or privacy-sensitive design decisions.

This is the same muscle as assigning work on a team: you’re constantly deciding who owns what, how much autonomy is safe, and where you want a checkpoint before the work hardens.

### Verification loops help to catch issues early

When you manage people, you learn that the fastest way to lose time is reviewing low-quality work too late. You want early feedback loops and quality gates. Agents are the same - except they can generate low-quality work at high speed.

Verification loops are the unlock, and the best toolmakers are baking them into their guidance. Anthropic’s [best practices](https://www.anthropic.com/engineering/claude-code-best-practices) explicitly suggest running multiple Claude instances where one writes code and another verifies via review and tests, treating it like a two-person workflow with separation of concerns. OpenAI’s Codex positioning is also explicit about tool use: run commands, run tests, iterate to passing states, then propose a PR.

What verification loops look like in practice: require the agent to run the test suite (or a scoped subset) and include the output in its final message. Require lint and typecheck to pass for touched areas. Require the agent to add or modify tests for behavior changes. Require a structured “PR packet” at the end - a summary of changes, why this approach, files touched, test plan plus results, and risks or follow-ups.

If you want to go one step further, use the two-agent pattern: Agent A implements, Agent B reviews for correctness, style, edge cases, and missed tests, then Agent A (or a fresh Agent C) applies the review feedback and re-runs verification. That’s not theoretical - Anthropic literally recommends it as a workflow upgrade.

This is also where manager instincts matter: you’re not just checking that code compiles. You’re checking whether it aligns with conventions, whether it’s maintainable, and whether it matches intent.

### Async check-ins: Treat agents like reports

If you’re running ten parallel sessions, you cannot afford to scroll through each one trying to understand what happened. You need lightweight, repeatable check-ins. This is the async-management playbook applied to agents.

Set a check-in cadence: “If you haven’t made significant progress in 15 minutes, stop and report blockers.” Ask for status in a predictable format: What changed? What’s next? What are the risks or blockers? What do you need from me?

This sounds small, but it’s how you keep parallel work from going off the rails without constantly babysitting. If you want a concrete analogy, managing agents looks a lot like managing a distributed team across time zones. You front-load clarity, you rely on written updates, and you reserve real-time attention for decisions and unblockers.

## The hard parts are real (and they’re management problems)

### Merge conflicts multiply fast

Parallel agents touching adjacent code is like putting five engineers in the same file without coordination. It’s not a tooling failure; it’s a boundary failure. The fix is exactly what you’d do on a human team: create intentional task boundaries, isolate work, and define interfaces.

Practically, that often means running agents in isolated working directories or branches. [Git worktrees](https://git-scm.com/docs/git-worktree) are a clean pattern here - they let you check out multiple branches at once from the same repo, each in its own directory. Claude Code’s docs explicitly recommend using git worktrees for parallel sessions so instances don’t interfere with each other, and Anthropic’s best practices give a step-by-step for using worktrees plus “one terminal tab per worktree” as an operating pattern. Even if you’re using cloud agents, you want the same principle: separate branches, small PRs, and clear ownership of modules.

My favorite boundary rules, borrowed from team coordination: one agent owns one PR, no mega-PRs from multiple agents. If two agents might touch the same files, redesign the task split. Shared interfaces get handled in a first PR (human-led), then agents build on top of that seam.

### Taste and “should we build this?” becomes the real bottleneck

When building gets cheap, you start building everything. That feels productive right up until your product becomes a junk drawer of features.

This is the part of the shift that doesn’t get enough attention: AI doesn’t remove the need for judgment; it raises the value of judgment. “Should we?” starts to matter more than “can we?”

That is a manager skill in disguise: prioritization, saying no, defining success, running small experiments, and killing bad ideas quickly.

If you want to operationalize this, borrow two concepts from management. First, WIP limits: cap how many active agent streams you allow at once, so you don’t drown in reviews (the same bottleneck Willison called out). Second, kill criteria: define what would cause you to stop pursuing a feature before you start building it.

## What I’m enjoying (and why this is worth the effort)

The “on the go” delegation effect is real. When background agents can work against a repo and come back with reviewable changes, you move from “file an issue for later” to “start building the idea now.”

My current setup runs four to five background agents handling low-to-medium complexity work while I stay human-in-the-loop locally for architecture and nuanced product work across another three to five sessions. The ability to delegate work from mobile has shifted my creative loop: idea to implementation draft to review to iterate.

That is incredibly gratifying when you have a quality bar and a process, because your creative loop tightens. But it only stays gratifying if you treat orchestration like management, not like magic. You have to be realistic about your bandwidth to multi-task and context switch. Not everyone needs ten to fifteen agents running at once. Boris’s workflow is useful as an extreme that shows what’s possible, not as a requirement.

## A simple operating system for orchestration

If you want one repeatable loop to practice:

Plan like a manager - write the brief with outcome, constraints, and acceptance criteria. Spawn like an orchestrator - assign tasks to parallel agents with explicit boundaries. Monitor async - lightweight check-ins, unblock quickly, avoid mid-flight thrash. Verify aggressively - tests, lint, structured PR packets, second-agent review where useful. Integrate carefully - merge in a deliberate order, watch for boundary violations. And retro - update your [AGENTS.md](https://developers.openai.com/codex/guides/agents-md/) and checklists so the next run starts smarter.

For most of us, the sweet spot looks closer to a handful of background agents doing low-to-medium complexity work while you stay human-in-the-loop for architecture and product nuance, realistic about how much context switching you can tolerate.

That’s orchestration. And the fastest way to get good at it is to learn the same skills that make someone effective at leading engineers: clarity, delegation, feedback loops, and async communication.
