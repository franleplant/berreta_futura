---
source_ids:
- how-warp-builds-self-improving-agents-on-claude-9e96ce55
content_mode: article
label: ARTICLE
---

Warp's internal code review agent made unhelpful comments, and engineers complained. Rewriting the prompt by hand made the output more usable but didn't scale; improving context files like AGENTS.md helped but was far from a complete fix. The real issue, the team realized, was that feedback to an agent typically disappears when the session ends. Their solution is two skills with human feedback between them. A base skill does the work. An improver skill runs on a schedule, reads the accumulated feedback, and proposes a small edit to the base skill as a pull request. A human reviews and merges it, and the next run inherits the improvement. Warp now runs this pattern across its entire open-source repo.

## The loop

Skills are file-based encodings of knowledge that keep instructions out of the raw prompt. Warp's architecture has three parts.

**The base skill** holds the domain knowledge and instructions. When a PR is opened, the review agent runs with it.

**Human feedback** can be as simple as a thumbs up, but the more explicit the better. "Specifics like 'you suggested renaming this variable, but our code base convention is this type of global variable uses this particular naming context' tell the agent how to do it right next time," says founder Zach Lloyd.

**The improver skill** is an observer agent that runs on a schedule rather than per task. It compares what the agent suggested against how humans responded and proposes a small, focused edit to the base skill.

Because skills are plain files, agents are extremely good at updating them, and the updates flow through normal code review. "The framework is really simple actually," Zach says. "This simplicity is the beauty of this approach."

## Writing the skills

- **Write principles, not rules.** "Construct the skill as though you're instructing a smart person, not like you're programming a computer." "Look for repeated code" directs better than exhaustive naming rules.
- **Explain the why.** The rationale lets the agent reason instead of following rigid instructions.
- **Make feedback effortless.** Capture it where people already work, such as a PR or issue comment, with no extra submission step. "If you make it too hard you're not going to get the feedback."
- **Keep skills small.** A good skill references resource files and scripts rather than loading everything into context at once.
- **Quality over volume, but volume helps.** A thumbs up or down doesn't say why; a little detailed feedback from a senior engineer can be worth more. Still, the bigger the corpus of quality signal, the better. Warp has hundreds of contributors and does thousands of code reviews.
- **Invest in the improver.** Outside the domain knowledge, it is fairly reusable: Zach says the improver for a code review agent is not that different from the improver for any other agent.

## The triage agent

When someone files a GitHub issue, an Action fires an agent that analyzes complexity and feasibility, assigns labels, and suggests a direction for the fix. On one sample issue it did a solid job but missed the "ready to spec" label. A maintainer left feedback on the issue, explaining both what he expected and why.

The improver ran in Oz, Warp's orchestration platform, as a scheduled "update triage" agent. It ran a Python script bundled with the skill to pull recent issues carrying feedback, summarized them into JSON, and read that back into context. It then proposed the smallest edit that captured the signal: apply "ready to spec" when an issue describes a real problem, even if the exact UI or UX shape is not yet defined. The PR explained which signals prompted the change. A human reviewed, approved, and merged it. That final step keeps a person in control of what actually changes.

## Questions the team answers

- **Skills or memory?** Skills are procedural and stable, changed deliberately. Memory is auto-written by the agent at inference time and never stops changing.
- **One improver per agent?** Meet in the middle: a templated base loop with domain-specific weights layered on. A handful of improvers can each own one; a hundred should share.
- **What if the feedback is wrong?** Assume it will be. Give the agent context to sanity-check, filter whose input counts, and keep a human at the filtering or final-review stage.
- **Is the domain verifiable?** Build the verification harness first, then let the agent tune against it. If it isn't, use deterministic evals against golden outputs where they exist, and restrict human feedback to domain experts.
- **Is the whole system improving?** Track the metrics humans already eyeball, such as time to merge, contributor count, and cost, and feed them back to the improvers. Go crawl-walk-run on deployment.

Any agent, no matter what its task, gets better over time if you build one of these loops into it from the start.
