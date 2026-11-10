---
source_ids:
- i-reverse-engineered-grok-bot-s-memory-system-an-1ec399b8
content_mode: article
label: ARTICLE
---

When I asked Grok Bot to list everything it had saved about me, it searched for a few minutes, returned 81 notes, and then told me there were about 91. The other ten never appeared because, in its words, *"my search only returns notes that match the words I search for."* Every bot on an account shares one pool of short text notes. A slice of that pool is pasted into every prompt, each note is cut at 500 characters, and the rest can only be reached by keyword search. As far as I could see, nothing cleans the pool up automatically, so it fills with notes that contradict each other.

## How I looked

Grok Bot refused to describe its tools, prompt, or memory design. So I read the Electron app bundle (tool names, protobuf schemas, UI text), asked what it remembers instead of how it's built, and ran experiments across bots. Models can hallucinate, and some of this comes from the bots describing their own behavior. The server side (system prompt, tool schemas, retrieval code) isn't in the client, so I can't read it.

## One pool, three scopes

Memory lives at three scopes: private to one bot, shared by all of a user's bots, and, for team bots, shared across a team. My account has 14 bots. The research bot sorted what it remembered into its own notes, shared facts about me, and shared dated history. The shared notes came from four different bots, each tagged with the bot that saved it.

The schema gives each memory record a `scope`, a `scope_key`, and a folder holding a `profile` and a set of `logs`. My reading is one record per scope, with the profile holding facts and the logs holding history.

## What reaches the prompt

Each turn, a bot gets its private notes, then shared facts, then shared history, one line per note:

```text
(learned 2026-11-04) [via Grok Bot] TEST NOTE (temporary, delete after Nov 4 2026 test): Manthan's test codeword is violet-kestrel-42.
```

Two limits shape this. Every truncated note I measured was exactly 500 characters, while the longest complete one was 475; recall results are clipped the same way. And the block as a whole is capped, by a note count or token budget I couldn't measure. The research bot said *"there are more shared entries I can't see without searching."*

Hermes enforces its cap when a note is written, so the agent has to consolidate. Grok Bot applies the cap when notes are read: the pool keeps growing and the window stays the same size. Mine had reached about 91 notes after five weeks.

## Writing and recall

The client lists three memory tools: `UpdateMemory`, `RecallMemory`, and `SortMemories`. `UpdateMemory` takes an `action` (`write`, plus `forget`), a `scope`, and a `type` (`journal` for dated history). I couldn't find out what `SortMemories` does; my guess is a tidy-up pass the model can run on request.

Every note I saw reads like a deliberate write in the middle of a conversation. I found nothing like Claude's background job that rebuilds memory from your chats.

Going by the bot's own account, recall is keyword search. A search for "schedule" won't find a note about "calendar" unless the bot happens to search for "calendar". There's no "list everything" operation, even though the bot knows the total count.

## The test

I asked the main bot to save one shared note containing a codeword. About two minutes later I asked Cooper, a bot that hadn't been in that conversation. It quoted the note straight from its context, with date and source, and its search for "codeword" returned the same note. No indexing delay, no review step: on a personal account, a shared write goes live everywhere at once. Afterwards I had the note deleted and confirmed the search came back empty.

## Teams get a review queue

Team bots are the exception. A teammate's write goes into a queue, and a manager approves or rejects each one. The client also has a schema for a team memory summary with `prose`, `summary_model`, `memory_version`, and `stale` fields. My reading is that team memory is rewritten by an LLM into a prose summary and injected in place of the raw notes.

## Nothing cleans up

Both bots I asked for a full dump flagged, unprompted, that the shared pool contradicts itself:

- Three versions of one weekly schedule, saved hours apart on the same day, all still in the pool.
- An Oct 28 note setting a hard rule, and an Oct 31 note making it optional. Both are injected.
- An early writing-style note, replaced by a later one but never removed.

Each was correct the day it was saved. Writes only append; the old decision stays unless the model also calls `forget`. I saw nothing that checks for duplicates or resolves conflicts. Which of two contradicting notes a bot sees can depend on which fits in the window or which a keyword search finds.

Storage is easy; the hard part is the retrieval policy, the rule that decides which saved notes end up in which prompt. Sharing makes it worse. In ChatGPT a stale fact only affects ChatGPT. Here a stale fact saved by one bot is pasted into every other bot's prompt, and some of those bots act on it on a schedule while you're not watching.

## Where it stands

Of the five systems in my series (ChatGPT, Claude, OpenClaw, Hermes, Grok Bot), Grok Bot is the only one built around many agents sharing memory. It's a sensible version of the injected-profile pattern: source tags, a private scope, review in front of team writes. What it lacks is what Hermes got right. A write-time cap forces the agent to decide what's still true before it saves; a read-time cap leaves that decision to whichever notes happen to fit.

If I could change one thing, a new note would replace the old one it contradicts. With 14 bots writing to one pool, stale notes pile up faster than any single bot will think to clean them up.

*This is based on the desktop client and my own bots, not official documentation. The server-side parts are inferred.*
