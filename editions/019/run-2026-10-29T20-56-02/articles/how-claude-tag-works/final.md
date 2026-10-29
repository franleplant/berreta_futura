---
source_ids:
- how-claude-tag-works-b4c77dfa
content_mode: article
label: ARTICLE
---

Claude Tag is Claude working inside your team's Slack channels. An organization Owner gives it its own accounts to the tools your team uses, so anyone in a channel can tag it into a problem without setting anything up. A task that needs investigation or tools gets a session in a thread, runs in an ephemeral cloud sandbox, and posts its result back where the whole channel can see it. Access and memory belong to the channel, not the person asking; a one-to-one DM runs on your own claude.ai connectors instead.

## Starting and steering

Type `@Claude` and say what you need in the same message. A working indicator means Claude picked it up; in a channel thread it carries a **Stop** button. Short asks get a direct reply. A longer task gets a checklist that Claude edits in place. Slack sends no notification when a message is edited, so a quiet thread usually means Claude is mid-task, not stuck. If the work hits a wall, Claude usually says so.

Anyone in the channel can steer a running session by replying in its thread, without mentioning `@Claude` again. **Stop** halts the reply but keeps the session; mention `@Claude` to resume.

Edits and deletions don't steer:

- An edit reaches Claude as a note showing both versions, and both stay in the transcript. It doesn't re-address Claude, even if you add `@Claude`.
- A deleted reply sends no notification; Claude keeps the version it read.
- Deleting the thread's first message closes the session. It's archived, not deleted.

To correct course, say so in a new reply.

## Where you ask decides whose access

| Working in… | Access | Attribution |
| --- | --- | --- |
| A channel | The channel's connections, set by an admin | The agent's own accounts |
| A group DM | Connections set for the workspace and organization | The agent's own accounts |
| A one-to-one DM | Your own claude.ai connectors | You, except pull requests, which the Claude GitHub App authors |

The short version: team work goes to Claude Tag; personal work goes to Cowork or Claude Code.

## The loop

Every session follows the same five steps: someone tags Claude or a routine runs; a sandbox builds for the thread; the working loop runs with the channel's access; the result lands in the thread; a quiet period releases the sandbox while the thread persists, and a new reply rebuilds it.

The sandbox runs the same engine as Claude Code on the web. Claude clones your GitHub repositories there and pushes changes back as a branch or pull request. Two threads are two sessions with separate sandboxes and no shared state. A channel where Claude works at the top level also has one session of its own, which handles top-level mentions and starts thread sessions for bigger tasks.

With nothing connected, a session still reads its thread and the channel's history, including pinned items, searches the workspace, and writes and runs code.

Results come back as a reply, a file or chart, a page kept current, or a hosted page on claude.ai that stays available after the session ends. Code work usually becomes a draft pull request under the Claude GitHub App.

## Access

An admin applies access to all of Slack, to one workspace, or to a single channel, directly or through a bundle. A thread locks in its skills, plugins, and custom instructions when it starts; connectors and domain rules are enforced on each request, so a connector added mid-thread works, though Claude won't announce it. Ask for the service by name, or start a new top-level thread after any configuration change.

To learn what a session can reach, ask: `@Claude what can you access from this channel?` If it can't reach something, the channel wasn't granted it.

From a public channel, Claude can read and post in other public channels it's a member of. From a private channel or group DM it can read but not post. From a one-to-one DM it can make new top-level posts, each after you select **Approve and post**. Reading is blocked when the channel you ask from includes guests. Every such post carries a line naming where it came from and on whose behalf.

## What survives

A thread is durable, but the sandbox behind it is not. The transcript lives on Anthropic's side, and deleting messages in Slack doesn't remove them from it. A few minutes after a turn, the sandbox is released; the session resumes in a fresh one on the next message. Files that exist only in the sandbox don't survive, so for long tasks ask Claude to push branches and post drafts as it goes.

`@Claude !restart` archives the session and starts a fresh one that rereads the thread. The channel's own session is replaced after about an hour of inactivity, after a configuration change, or once it's about a day old and things are quiet. Claude stops reading top-level messages after about 100 arrive since it last posted; a mention starts it again. These thresholds are defaults and can change.

Mentioning `@Claude` partway into a thread gives it a window of messages, not the whole thread. In long threads, restate anything critical.

## Memory

Each channel keeps its own notes. From a public channel Claude can also save workspace notes, read in every channel; a private channel reads them but can't add to them. Ask `@Claude what do you remember about this channel?`; anyone in the channel can correct or remove entries.

## What admins see

Admins have no page or export of the individual messages people send Claude. They get analytics on spend by channel and kind of work, and Owners get an **Activity** page listing scheduled work, memory files, and network events. Everyone in a channel, admins included, can read its threads, and Anthropic keeps a transcript of each session.
