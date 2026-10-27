---
source_ids:
- how-and-when-to-use-subagents-in-claude-code-e7d23b0f
content_mode: article
label: ARTICLE
---

Long sessions in Claude Code accumulate weight. Every file read, every tangent explored, every half-finished thought stays in the context window, slowing responses and driving up token costs. A subagent is an isolated Claude instance with its own context window: it takes a task, does the work, and returns only the result. Use subagents for heavy research, independent parallel tasks, a fresh review, or staged pipelines. For small, sequential, or same-file work, the overhead isn't worth it. Start by asking in conversation, and automate once patterns repeat.

## What a subagent is

Each subagent starts fresh, without the conversation's history or invoked skills. Several can run in parallel, each with its own permissions: a research subagent might be read-only, while an implementation subagent gets full editing rights. Built-in types include general-purpose agents for multi-step tasks, Plan agents that research before proposing a strategy, and Explore agents for fast, read-only code search. Claude Code often spawns them on its own, but you can direct it.

Think of subagents as the browser tabs of a session: a place to chase a tangent without losing the main thread.

## When to use them

- **Research-heavy tasks.** When gathering context means reading dozens of files, a subagent returns a summary instead of the raw content.
- **Independent tasks.** When sub-tasks don't depend on each other, three subagents working at once generally finish sooner.
- **Fresh perspective.** A subagent doesn't inherit the main conversation's assumptions or blind spots. `/clear` gives a similar clean slate but loses the history; a subagent keeps it intact.
- **Verification before committing.** An independent subagent can check that the implementation isn't overfitting to tests or missing edge cases.
- **Pipelines.** For design, then implement, then test, each stage gets focused attention.

A strong signal: the task requires exploring ten or more files, or involves three or more independent pieces of work.

## How to direct them

**Conversation.** Ask: "Use a subagent to explore how authentication works in this codebase." Be explicit. Scope the task ("Explore how payments work" beats "explore everything"), say when work can run in parallel, name the output you want, and ask for a subagent that doesn't see the previous discussion when unbiased analysis matters. Ctrl+B sends a slow subagent to the background; `/tasks` shows what's running.

**Custom subagents.** When the same specialist keeps getting requested, define it once as a markdown file in `.claude/agents/` (shared with the team) or `~/.claude/agents/` (yours, across projects), with its own system prompt, tools, and optionally its own model. `/agents` walks through setup. Claude delegates to it automatically when a task matches its description, so write the trigger, not just the capability: "Reviews code for security issues before commits" routes better than "security expert."

**CLAUDE.md.** Custom subagents define who the specialists are; CLAUDE.md defines when Claude reaches for them. Claude reads it at the start of every conversation, so a rule such as "code reviews always use a read-only subagent" holds across sessions and teammates.

**Skills.** A skill in `.claude/skills/` loads on demand, by `/skill-name` or when Claude matches its description, while CLAUDE.md is always loaded. That makes skills the place for workflows that should be available but not applied to every prompt. A skill is a directory: alongside `SKILL.md` it can hold templates, example outputs, or scripts.

**Hooks.** Shell commands, HTTP endpoints, or LLM prompts that run at fixed points in Claude Code's lifecycle. A Stop hook, for example, can run the test suite and, if it fails, return `decision: "block"` with a reason, which keeps Claude working; a `stop_hook_active` guard prevents infinite loops. Hooks are the most automated approach and come later, as workflows mature.

## When not to use them

Each subagent spins up its own context, consumes tokens, and adds indirection. Stay in the main conversation for:

- **Sequential, dependent work**, where each step needs the full output of the last.
- **Same-file edits**, where two subagents in parallel invite conflict.
- **Small tasks**, where delegation costs more than it saves.
- **Too many specialists**, which makes automatic delegation less reliable. Most teams settle on a handful.
- **Work that needs agents to talk to each other.** Subagents can't; agent teams can, across separate sessions, at greater weight and cost.

## Start conversational

Automatic invocation helps, but deliberate delegation produces better results than leaving it to chance. Begin with conversational prompts, notice which requests recur, and build automation as those patterns clarify.
