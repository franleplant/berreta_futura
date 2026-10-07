---
source_ids:
- memory-and-dreaming-how-devin-learns-from-workin-393f9bac
content_mode: verbatim
label: VERBATIM
---

Today we’re introducing Memory and Dreaming in Devin.

Memory lets Devin carry useful learnings about the way you like to work across sessions: your preferences, corrections you’ve made, and lessons learned about your projects and workflows.

Dreaming is a daily asynchronous process that improves the index of Devin’s memories about you. Memories generated during your sessions are deduplicated, linked to relevant sessions and artifacts, and new knowledge emerges.

You can browse Devin’s memories under Customize → Memory, and inspect recent dreaming sessions. Memory is personal to you within each organization on [devin.ai](https://app.devin.ai).

[Video](https://devin.ai/images/blog/memory-and-dreaming/customize-memory-dreaming.mp4)

We have also open sourced the standard we used to build Devin’s memory system. We invite you to integrate it into your agents and contribute at [cognition.ai/agent-memory-repo](https://cognition.ai/agent-memory-repo).

## Learning as you work

Some of the most useful context only emerges once work is underway. You correct an assumption, explain why an approach won’t work in your current project, or clarify a personal preference. Other lessons come out of the work itself: an environment gotcha that took several attempts to get right, or a project decision that will matter again later.

**Memory** gives Devin a way to proactively retain these lessons beyond the session itself, without you having to pause the session to update a skill. It is personal to **you**, rather than becoming shared instructions for your organization. Memories are not summaries of sessions. They are lessons Devin learned from working with you, written as short notes with a link back to the session where they were learned.

## Devin’s memory drive

Memories live in your personal **Memory Drive**, a persistent Git repository of markdown files. Notes can be organized by repository, project, or topic, while a short `MEMORY.md` holds general preferences and an index of the other files in the drive. At the start of a session, Devin receives `MEMORY.md` as context. From there, it can search and read relevant notes using the same tools it uses to navigate code, without loading the entire memory archive into its prompt.

Each session works with its own Git checkout of the drive. After editing a note, Devin commits its changes, merges updates from other sessions, and saves the result to your persistent memory drive. If another session saves an update while a sync is underway, a revision check rejects the stale write so Devin can retry against the newer version. Conflicting edits are surfaced for resolution rather than silently overwritten. This lets parallel sessions contribute to the same memory drive without treating any one session’s local copy as the source of truth.

## Dreaming: keeping memory useful

Capturing memories during a task is only the first step. Those memories also need to be revisited with the benefit of the global context across your sessions. **Dreaming** is a daily background session, in which Devin reviews past conversations alongside its existing memory to improve its index for future sessions.

When dreaming, Devin

- consolidates overlapping notes
- removes transient details
- looks for useful lessons that weren’t captured during the original work
- removes stale memories records that weren’t used by any sessions

Devin preserves source references and explicit preferences while reorganizing the notes and their index so relevant context is easier to find.

## How memory differs from skills

Skills capture a repeatable workflow; memory captures what Devin learns while working with you. A release skill might describe the steps for testing and publishing a change. Memory might record your tech stack preferences, along with the reason you gave.

The two work together: the skill provides the procedure, while memory supplies context for applying it to your work. Both can contain instructions, but their lifecycle differs — skills are deliberately packaged for reuse, while memory is accumulated through sessions and revisited through dreaming.

## Start dreaming

A preference you explained or a lesson learned the hard way should remain useful beyond one session. Memory and Dreaming are designed to make that experience carry forward, without making you responsible for maintaining it all.

At [devin.ai](https://app.devin.ai/customize?tab=memory) open **Customize → Memory** to explore what Devin has learned from working with you.
