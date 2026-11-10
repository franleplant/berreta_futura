---
source_ids:
- your-ai-coding-agents-need-a-manager-92402d58
content_mode: article
label: ARTICLE
---

In the near future, I think the highest-leverage developers will look like async-first managers running a small fleet of parallel AI coding agents. Agents can now work in the background, in isolated environments, and return with something reviewable, often a pull request. We still require quality checks, but the bottleneck is no longer "can the agent write code?" It's "should we build this?" and "can I manage multiple agents doing so effectively?" Once you run several at once, AI coding stops being a prompting problem and becomes a management problem. The value is real, but only if you treat it like management, not magic.

## Two modes

I run two modes side by side. Local, high-touch sessions, where I stay human-in-the-loop, are for architecture, tricky refactors, product nuance, ambiguous requirements: anything where taste and judgment dominate. Cloud or background sessions are for bounded tasks: straightforward features, migrations with clear patterns, test generation, docs, dependency bumps, small bugfixes. You fire them off, switch to something else, and come back to review.

Boris Cherny, Claude Code's creator, runs five sessions locally in terminal tabs, five to ten more in the browser, and starts some from his phone. That's orchestration. Simon Willison takes the skeptical side: the natural bottleneck isn't generating code, it's reviewing it. He still found real value in parallel tasks, so long as you're honest about your attention span. I agree.

## The four skills that transfer

**Scoping.** Write a brief, not a vibe: the outcome, the context, the constraints, the non-goals, acceptance criteria, integration notes, and a verification plan. Point agents at existing files so they anchor on real conventions, and put durable rules in `AGENTS.md`. This is the difference between a clean PR and a thousand-line mess you can't trust.

**Delegation.** The trap is over-delegating the human work: product intent, API tradeoffs, architectural boundaries. OpenAI's guide splits it as delegate, review, own, with engineers keeping sign-off. Hand off mechanical work with a crisp spec. Keep checkpoints on shared interfaces, likely merge conflicts, and data migrations. Don't delegate architecture, "should we build this?" calls, or security-critical design, except to explore options.

**Verification.** Agents can generate low-quality work at high speed. Require the test output in the final message, passing lint and typecheck for touched areas, tests for behavior changes, and a "PR packet": changes, reasoning, files, test results, risks. Anthropic recommends a two-agent pattern: one implements, another reviews, then the first (or a fresh one) applies the feedback and re-runs verification.

**Async check-ins.** With ten sessions you can't scroll through each one. Set a cadence ("If you haven't made significant progress in 15 minutes, stop and report blockers") and a fixed status format: what changed, what's next, risks, what you need from me. It looks a lot like managing a distributed team across time zones.

## The hard parts

Merge conflicts multiply fast. That's not a tooling failure; it's a boundary failure. Isolate work in git worktrees, as Claude Code's docs recommend. One agent owns one PR. If two agents might touch the same files, redesign the split. Shared interfaces go in a human-led first PR, and agents build on that seam.

When building gets cheap, you start building everything, and your product becomes a junk drawer of features. AI doesn't remove the need for judgment; it raises the value of judgment. Borrow WIP limits, to cap active agent streams, and kill criteria, defined before you start building.

## What I run

Four to five background agents handle low-to-medium complexity work while I stay in the loop locally across another three to five sessions. Delegating from mobile has tightened my loop from idea to draft to review. But not everyone needs ten to fifteen agents; Boris's workflow shows what's possible, not what's required.

The loop: plan like a manager, spawn with explicit boundaries, monitor async, verify aggressively, integrate in a deliberate order, then update your `AGENTS.md` so the next run starts smarter. The fastest way to get good at it is to learn what makes someone effective at leading engineers: clarity, delegation, feedback loops, and async communication.
