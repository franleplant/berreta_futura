---
source_id: the-new-rules-of-context-engineering-for-claude--aa1b1ea8
content_mode: faithful_synthesis
label: FAITHFUL SYNTHESIS
---

When you send a message to Claude, the prompt is only a small part of the context it gets: much is assembled from your system prompt, Skills, CLAUDE.md files, memory, and other sources. Unlike a prompt, this context serves many requests and cannot be as specific—we call it context engineering, and it makes a big impact on your results.

This can be surprisingly difficult as Claude’s own capabilities evolve. Most recently, we noticed a large jump in the way we prompt the newest generation of Claude models. We removed over 80% of Claude Code’s system prompt for models like Claude Opus 5 and Claude Fable 5 with no measurable loss on our coding evaluations.

## Unhobbling Claude

Overall, we found that we were over-constraining Claude Code, both through our system prompt and in our CLAUDE.md files and skills.

In transcripts of our own internal Claude Code usage we see conflicting messages in a single request—“leave documentation as appropriate,” “DO NOT add comments”—as system prompt, skills, and user requests clash. Claude can generally interpret the user’s intent and get to the right answer, but must think more carefully about these conflicts before deciding. Constraints once needed to avoid worst case scenarios can now be deleted—the model uses surrounding context and judgement instead.

## Then and now

### Then: Give Claude rules. Now: Let Claude use judgement

When we first rolled out Claude Code we gave particularly strong guidance to keep Claude from worst case scenarios, such as deleting files—guidance that might not always be true. In the system prompt we used to say:

> In code: default to writing no comments. Never write multi-paragraph docstrings or multi-line comment blocks — one short line max. Don't create planning, decision, or analysis documents unless the user asks for them — work from conversation context, not intermediate files.

For a certain subset of prompts this guidance would be wrong: the user may have their own documentation preferences, or very complex code might need multi-line comment blocks. Older models often wrote incorrect comments without these guardrails, a tradeoff we accepted; newer models have better judgement and handle these decisions without explicit rules.

In the new system prompt we say: Write code that reads like the surrounding code: match its comment density, naming, and idiom.

### Then: Give Claude examples. Now: Design interfaces

The number one rule for tool usage was to give Claude examples; with our newest models, examples actually constrain them to a certain exploration space. Instead, think about the design of your tools, scripts, and files—what parameters does Claude have, and how can they be more expressive? In the Todo tool, listing status as an enumeration between pending, in_progress, and completed hints at how to use it.

### Then: Put it all upfront. Now: Use progressive disclosure

Our coding-focused system prompt included detailed code review and verification information—not always needed, but crucial when it was. Claude Code has since gotten very competent at progressive disclosure, loading the right context at the right times, and we moved verification and code review into their own selectively invoked skills.

Progressive disclosure is not just for skills: some tools are ‘deferred loading’—the agent must search for their full definitions using ToolSearch—so they don’t take up context until needed. The same applies to your CLAUDE.md and Skill.md files: rather than a central repository of every known practice, consider a tree of files loaded at the right time.

### Then: Repeat yourself. Now: Simple tool descriptions

Earlier Claude models could need repeated instructions, or listen more to the end of their context window than the start, so our system prompt referenced tools whose descriptions carried the same guidance. We deleted these repeats and kept tool instructions in the tool descriptions rather than the system prompt.

### Then: Memory in CLAUDE.md files. Now: Auto-memory

We used to encourage users to save things to Claude’s memory, by using the # hotkey to write to their CLAUDE.md automatically. Instead, Claude now automatically saves memories that are relevant to the work and to you.

### Then: Simple specs. Now: Rich references

In plan mode, Claude Code has relied heavily on markdown plan files, and a similar practice was storing specs in the codebase for longer projects.

But we’ve found that Claude can handle increasingly more complicated references. Instead of simple markdown files, Claude can reference HTML artifacts created by our new artifacts feature.

You may also give references in the form of code—a detailed test suite, or a function in another codebase that Claude might port. Rubrics are another form: verifier agents in dynamic workflows try to verify your taste in a field such as API design.

## Applying this to your context

### CLAUDE.md

Keep your CLAUDE.md lightweight and briefly describe what your repo is for, but spend most of the tokens on gotchas inside of the codebase. For example, you may organize your code to keep types in one monolithic file and nowhere else. Avoid stating ‘the obvious’ things Claude should know by looking at your file system or your repo.

### Skills

Think of skills as lightweight guides that let Claude find information when needed, and avoid making them overconstrained except in highly important areas; divide long skills into many progressively disclosed files. Skills are best when they encode opinions, knowledge, or best practices particular to you, your team, or product.

### References

You can @ mention files as references to in-depth information about the current plan—specs, mockups, or even entire codebases. Generally prefer files in code: clear, high-fidelity instructions in a language Claude knows very well. An HTML mockup will generally produce better results than a description or a screenshot.

## Try simplifying

Across your system prompt, skills, and CLAUDE.md files, you may need to simplify just like we did. We rolled out a new command called `claude doctor,` which will help you do this automatically as well. For more details on prompting more advanced models specifically, check out our Fable field guide.
