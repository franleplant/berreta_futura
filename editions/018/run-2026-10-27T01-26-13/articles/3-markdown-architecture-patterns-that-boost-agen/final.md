---
source_ids:
- 3-markdown-architecture-patterns-that-boost-agen-5faf420c
content_mode: verbatim
label: VERBATIM
---

There is a running joke in modern software engineering that the hottest programming language isn't Rust, Zig, or Python: it’s Markdown. As coding agents become entrenched in developer workflows, many engineers find ourselves spending more time writing prompts and specifications than we do writing code.

Describing engineering concepts in natural language can be trickier than it seems. Coding agents can hallucinate APIs, produce features you didn’t ask for, drop existing architectural constraints, or gobble up more tokens than you budgeted. To get high-quality output from your agents and keep cost-per-task reasonable, engineering teams need concrete design patterns for agent instructions.

**By Tilde Thurium, Developer Marketing, Google Cloud**

## Designing a clean separation of concerns

Current emerging best practice for scaling agentic workflows across team environments relies on a modular separation of concerns. Teams should partition agent guidance into three standard markdown specifications:

| Specification File | Primary Domain | Core Responsibility |
| :--- | :--- | :--- |
| `AGENTS.md` | Global guidance | Defines high-level conventions that are relevant to every conversation with a coding agent |
| `DESIGN.md` | UI Design | Provides visual design constraints to keep the interface consistent across refactors |
| `SKILL.md` | Domain-specific instructions | Defines task-specific or domain-specific instructions |

## 1. AGENTS.md: a README for coding agents

The AGENTS.md file gives agents context on a software project. README files are primarily intended for human readers, but agents sometimes need additional layers of guidance on dev environment setup, test running, or anything you’d tell a new teammate to get them up and running.

For a strong example, check out [Agent Development Kit (ADK) Python](https://github.com/google/adk-python/blob/main/AGENTS.md). It defines key components succinctly, describes development setup, and points to [SKILL.md](http://skill.md/) files for more granular direction. (More on skills in a minute!)

**Evidence for AGENTS.md performance gains**

In July 2026, the Agentic AI Foundation ran [a benchmark study on including AGENTS.md in a repo](https://aaif.io/blog/measuring-agents-md-what-five-runs-show-that-one-doesn-t). For loosely defined tasks, using AGENTS.md resulted in:

- 26% reduction in diff size
- 27% reduction in wall clock time
- 25% reduction in tokens used

Now, including [AGENTS.md](http://agents.md/) does not speed up every single request. Instead, it eliminates the worst cases where the agent would get lost in a loop of running the wrong build commands, etc.

The other big takeaway: brevity. Keep your top line [AGENTS.md](http://agents.md/) file concise: around 12 lines is ideal.

## 2. DESIGN.md: codifying UI conventions

A DESIGN.md file codifies your team’s design system so agents can keep the brand and UI consistent while building new features, or refactoring old ones.

The [DESIGN.md](http://design.md/) spec is open-source and was introduced by Google in 2026. It consists of two layers:

The most important section is prose that describes how your design should look and feel.

For example: *“A graduate-level computer science lecture handout in the tradition of an old established university.”*

This sentence paints a vivid picture. Using it, your agents will understand what such a document is supposed to be styled like, so they can make good decisions.

What about specific brand fonts, colors, etc? For that, we move on to the second section. Using YAML frontmatter, we can specify values as we might in CSS.

```
Markdown
---
name: Heritage
colors:
  primary: "#1A1C1E"
  secondary: "#6C7278"
  tertiary: "#B8422E"
  neutral: "#F7F5F2"
…

```

These values, or tokens, can then be referred to in the prose section.

If you want to learn more, you can check out the [DESIGN.md specification on Google Labs GitHub](https://github.com/google-labs-code/design.md).

## 3. SKILL.md: procedural recipes for everyone

SKILL.md files are another flavor of reusable prompt. Skills provide step-by-step instructions required to complete specific operations. For example, you could write a skill that deploys an app using Cloud Run.

Skills are *progressively loaded*. The coding agent only uses a specific skill when it’s needed, which saves you tokens and prevents context bloat.

The good news is, you don’t have to write every skill yourself. Many open source skills repositories are available for free on GitHub. [Google’s is quite comprehensive](https://github.com/google/skills), offering everything from BigQuery and data science to GKE Platform Security.

Skills aren’t just for coding! Any business task that you can write a prompt for, that you might want to use again, can probably be converted to a skill. Brand writing that’s compliant with voice and tone. Copy editing. Writing your annual performance review. You get the idea.

Unfortunately, the agentic era has rapidly generated novel attack surfaces for bad actors. If you didn’t write a skill yourself, read it before you use it so you can be confident there are no surprises. Treat skills the same way you would any other third-party software dependency.

To dive deeper on agent skills, check out our [Skills vs MCP video](https://youtu.be/T6PQIPMlj3E?si=JAjHAnc726PrCsQh).

## Stop repeating yourself in prompt windows

Commit your specifications to version control, treat Markdown with the same rigor as source code, and scale your team's agentic productivity.
