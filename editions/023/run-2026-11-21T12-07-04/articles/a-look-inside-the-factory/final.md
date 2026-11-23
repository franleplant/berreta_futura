---
source_ids:
- a-look-inside-the-factory-04c53aba
content_mode: article
label: ARTICLE
---

I built my own coding harness in June 2026 to see how protectable one is. It was not hard, and anyone can do it. I then turned it into a software factory: I give it a goal, approve the plan, and it gives me pull requests. Since August 21 it has merged 1,940 PRs into our monorepo. Getting the human's place in the loop right took six rounds. Now the bottleneck is compute, so we are moving the factory to the cloud.

## Building the harness

I believe foundational models become commodities as intelligence gets cheaper, so I asked whether the harness could be the moat. I dismissed the idea after watching harnesses multiply, and I built one to check.

On June 26 I asked Codex to turn the most used Claude Code features into a spec. It came back with about 30 ranked features. I cut anything skills or bash tools could cover, plus the enterprise features. Then I had it break the rest into small tasks in a CSV, each with acceptance criteria and dependencies, and two empty columns for DONE and implementation notes. That CSV turned out to be a pretty good "harness" for a /goal to oneshot the whole thing.

Every task had to ship with tests and pass the type, lint and test gates before it could be committed. The run lasted about two days, made 146 commits and checked off 130 of the 188 tasks. The key trick for that much autonomy was making it write real PTY tests that drive the TUI.

There were bugs, but they were small, like Skills not getting injected or token caching, the kind you find by just using it. I fixed them and ended up with a harness at rough parity with Claude Code that could use any model. On August 11 I added factory mode with a badly spelled prompt. At first I used another harness to fix the factory, but it soon got good enough to fix and improve itself.

## How the factory works

I give the overseer a goal and approve its plan. It turns the plan into tasks in the cloud and hands the ready ones to workers. Each worker writes code in its own worktree and pushes to a private remote on my machine. A daemon runs my rules and workflows on each change, pushes it to GitHub once they pass, then fixes review comments, CI failures and merge conflicts. I touch a Task when I describe the goal and when I approve the plan; after that it runs without me unless a question comes up.

## Design choices

**The unit of work is a Task.** I hate reading verbose agent output, and long plans suffer from context rot. Tasks are easier to review, can be verified independently and automatically, give one PR each, fit the context window, and form DAGs that suit a workflow-style runner. Reviewing them in the TUI was hard, so I moved review to a web page, which let Tasks get richer and more visual.

**Two processes.** The overseer runs live in my terminal; its bigger job is reviewing the workers as an adversary. The daemon runs headless. I designed it on August 7, four days before factory mode: each `archdev push` becomes a durable job in SQLite that runs against the exact commit in a throwaway worktree. The split lets me pick how to do human in the loop separately from the adversarial pre-push workflow, and it builds in tension, which gets better results.

**One supervisor per process.** Past the overseer/daemon split I had no opinion about process design. Then the bugs started. My rule for agentic coding is that enough bugs in one area means an architecture problem, so each group of similar sub-processes got a supervisor. Each became the source of truth for its runtime state, cleans up the whole group when something dies, and keeps orchestration in one place.

**Mechanism apart from policy.** The daemon handles git hooks, jobs against exact SHAs, workflows defined in JSON, and observability. The policy lives in each repo's `archdev.json`, where every workflow step is a prompt and a model alias. Changing it needs no daemon change, and it can be evaluated: we freeze real findings from past PRs, run the fix step in a sandbox, and an independent grader checks what got fixed and whether anything regressed. On October 20 I ran six arms over 19 graded cases. No arm beat the current config on accuracy. Sol 6.1 was about 3.5x cheaper per fixed finding, but on a case it should have declined, it deleted the public wrapper the reviewer had complained about. Grok 4.7 fixed 7 of 9 high findings, with 2 regressions.

## Where the human fits

I meant to automate everything between planning and clicking merge. It didn't work out that way. Unless your whole stack runs on a computer under your desk, a real feature needs credentials, vendor data, QA and production data, and unless you give agents the keys to the kingdom, they need some handholding. Agent-authored plans can also be ambiguous or wrong. Once I ran the factory 24/7, the overseer kept raising questions and blocking on me.

It took six rounds to get this right. Plan approval moved to the browser. The overseer reported "blocked" to Herdr, my terminal multiplexer; that fixed nothing, but I could see which terminal needed me. A `factory.autonomy` setting added an `auto` mode in which the overseer follows a playbook to unblock workers; by September 28 it never blocked on me in `auto`.

Then questions became part of the Task. The overseer had paused Tasks 67 times without telling me, and when I did answer, the next worker never saw it. Now a question is a paused Task carrying the kind of pause, the question, why the worker stopped, and a recommended answer. My answer goes on the Task, the Task reopens, and the next worker gets it in its prompt.

The same day I limited what the factory can ask. Workers had sent the overseer 151 decision requests in about 21 hours, many of which they could have decided themselves. Now a question must name one of six kinds of decision that belong to me: credentials, spending, live infrastructure (merging counts), irreversible actions, product decisions, and anything the Task says needs my sign-off. For everything else, the overseer decides and writes down why. In October the questions went where I already look: the TUI, archdev.ai/tasks, the CLI, my phone and a daily digest.

## Compute

The factory has merged 1,940 PRs since August 21, peaking at 251 in the week of September 28. It runs 24/7, even while folks are on vacation. Because it executes task DAGs, using it fully takes enough parallel work, so it encourages working on many things at once.

Compute became the bottleneck. My M5 Max Pro 128GB can run only 4 worker processes and 4 daemon jobs at once, and with my Claude Code sessions on top it basically stalls. Moving the factory to a System76 laptop helped, until the bottleneck became the amount of work I could churn through. I now run the factory on two machines, and it is still not enough. CI, token spend and other things also break at this pace.

So we are moving the factory to the cloud. If a machine just transforms tasks into PRs, what does it mean to "author" a PR? Why do tasks need to be assigned to anyone but the bot? Who is responsible for work? What do engineers do?
