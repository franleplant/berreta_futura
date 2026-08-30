---
source_ids:
- how-warp-builds-self-improving-agents-on-claude-9e96ce55
content_mode: article
label: ARTICLE
---

Warp's internal code review agent annoyed its own engineers: unhelpful comments, low-quality output. Rewriting the prompt by hand made it more usable but didn't scale. The real issue was that feedback to an agent disappears when the session ends. Warp's fix is two skills, plain files, with a human in between: a base skill holding the domain knowledge, and an improver skill that runs on a schedule, reads the accumulated feedback, and opens a PR editing the base skill. A person reviews and merges, and the next run inherits the change. Warp now runs the pattern across its open-source repo, with separate spec-writing, review, and triage agents.

## The loop

Skills are file-based encodings of knowledge that keep instructions out of the raw prompt. The inner skill holds the domain knowledge: when a PR is opened, the code agent runs off it and produces a review. Humans respond, ideally with reasons. As Zach Lloyd puts it, a human can affirm that a comment was useful, "But the human could also give detailed reasons why a code review wasn't good."

The outer skill is an observer that runs on a schedule rather than per task. It pulls the feedback, compares what the agent suggested against how humans responded, and proposes one small edit to the base skill. Because skills are plain files, the edit moves through the ordinary review workflow: reviewable, approvable, mergeable.

"The framework is really simple actually," Zach says. "There's the base domain-specific skill and then there's the improver skill that refines that domain-specific skill."

## Writing the skills

Write principles, not rules. "Construct the skill as though you're instructing a smart person, not like you're programming a computer," Zach says. Give the rationale, so the agent can reason rather than follow rigid instructions.

Make feedback effortless: capture it where people already work, on the PR or the issue, with no extra step. "Low friction is what keeps signal flowing."

Detail beats volume, though volume helps. A small sample of specific feedback from a senior engineer can outweigh many thumbs, because a binary vote doesn't say why. Warp runs thousands of code reviews across hundreds of contributors.

Put extra effort into the improver skill. Outside the domain-specific part, it is largely reusable across agents.

## Triage, in practice

A new GitHub issue fires an Action; the agent analyzes complexity and feasibility, assigns labels, and suggests a direction. On a sample issue it did a solid job but missed one label, ready to spec. A maintainer left feedback on the issue itself, saying what he expected and why.

The improver runs in Oz, Warp's orchestration platform, as a scheduled "update triage" agent. It authenticated to GitHub, ran a Python script bundled with the skill to pull recent issues carrying feedback, summarized them to JSON, and read that back into context. Then it opened a PR teaching the inner skill to apply "ready to spec" when an issue describes a real problem whose UI shape is not yet defined. A human approved and merged.

## The cautions

Skills are procedural and stable, changed deliberately; memory is written by the agent at inference time and never stops changing. Assume some feedback will be wrong: give the agent context to sanity-check it, filter whose input counts, and keep a person at the filtering or final-review stage. If the domain is verifiable, build the harness first and tune against it. If it isn't, lean on deterministic evals against golden outputs, and restrict human feedback to domain experts.
