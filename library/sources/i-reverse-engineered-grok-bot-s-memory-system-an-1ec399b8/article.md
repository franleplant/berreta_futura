# I Reverse Engineered Grok Bot's Memory System, and Here's What I Found
By Manthan Gupta · Manthan · Nov 4, 2026

When I asked Grok Bot to list everything it had saved about me, it worked through search after search for a few minutes and came back with 81 notes. Then it told me there were about 91. The other ten never showed up because, in its own words, *“my search only returns notes that match the words I search for.”*

That one sentence explains most of how Grok Bot’s memory works. Every bot on your account shares one pool of short text notes. A slice of that pool is pasted into every prompt, each note is cut off at 500 characters, and everything else can only be reached through keyword search. As far as I could see, nothing cleans the pool up automatically, so it fills with notes that contradict each other.

This is the fifth system in my memory series, after [ChatGPT](https://manthanguptaa.in/posts/chatgpt_memory), [Claude](https://manthanguptaa.in/posts/claude_memory), [OpenClaw](https://manthanguptaa.in/posts/clawdbot_memory), and [Hermes](https://manthanguptaa.in/posts/hermes_memory). Grok Bot is a set of cloud agents, which the app calls Bots. They keep running after you close the app and do work for you on a schedule. You can have many of them, so memory has to work across agents instead of inside one chat.

Let’s get into it.

## Methodology

Grok Bot was the least cooperative of the five systems. Claude described its own prompt layout when I asked. Grok Bot said no outright:

```text
I can't share my tool definitions, prompt text or how my memory is built and stored, so I'll skip pasting those.
```

So I couldn’t simply ask the model to describe itself, and I used three other sources instead:

1. **The desktop app bundle.** Grok Bot ships as an Electron app. The JavaScript inside it holds the names of every agent tool, the message formats (protobuf schemas) it uses to talk to the backend, and the UI text for the memory screens. None of that needs the model’s cooperation.
2. **Asking about memory contents instead of internals.** The bot won’t describe how it’s built, but it will tell you what it remembers, with dates and sources. How it groups and formats that answer gives a lot away.
3. **Experiments.** I wrote a note through one bot and asked a different bot about it, to see what is shared, how fast, and in what format.

Caveats, as always:

- Models can hallucinate, and some of what follows comes from the bots describing their own behavior.
- I’ve marked what I saw directly in code or behavior and what I’m inferring from it.
- The server-side parts (the system prompt, the tool schemas, the retrieval code) aren’t in the client, so I can’t read them.

## Many Bots, One Memory Pool

Grok Bot keeps memory at three scopes: notes private to a single bot, notes shared by all of a user’s bots, and, for team bots, notes shared across a team. The shared user scope matters most, because it lets every bot on your account read what any other bot has learned about you.

My account has 14 bots: a chief of staff, a research bot, and a dozen other specialists. When I asked the research bot what it remembered “without looking anything up”, it answered in three groups:

```text
Only I know these (my own memory)
  - 3 notes this bot saved for itself

Shared across all your bots: facts about you
  - ~20 notes, each tagged with the bot that saved it

Shared across all your bots: dated history
  - a few "On Oct 31 2026, ..." events
```

The shared notes came from four different bots: the main Grok Bot, the Chief of Staff, the research bot itself, and one other specialist. When one bot learns a fact about me, every other bot knows it on its next turn.

The client code backs up these scopes. The app bundle includes the protobuf schema the client and server use to send memory back and forth, which lists every field a memory record has. Here it is, with the field numbers from the schema and the type names left out. A memory record carries a `scope` and a `scope_key`, plus a folder that holds the actual notes:

```text
memory record
  1 scope
  2 scope_key
  3 version
  4 box_backfilled
  5 updated_at_ms
  6 folder

folder
  1 profile   string
  2 logs      map<string, string>
```

My reading is that each scope gets its own memory record. Your user scope has one, each bot has one, and each team has one, and `scope_key` says which user, bot, or team the record belongs to. Inside every record, the folder holds two things: a `profile` and a set of `logs`. That lines up with the two shared groups the bot described: **facts about you** are the profile, and **dated history** is the logs. It’s the same split OpenClaw makes between `MEMORY.md` and its daily `memory/YYYY-MM-DD.md` files, except here it lives in a server database instead of files you can open.

## How Memory Gets Into the Prompt

Each turn, every bot gets a block of memory pasted into its context. That block holds its own private notes, then the shared facts, then the shared history, one line per note:

```text
(learned 2026-11-04) [via Grok Bot] TEST NOTE (temporary, delete after Nov 4 2026 test): Manthan's test codeword is violet-kestrel-42.
```

I saved it through one bot as a test, and a different bot quoted it back to me word for word (more on that test below). Each line has three parts: the date the note was saved, the bot that saved it, and the text. Claude’s `userMemories` block and ChatGPT’s memory facts are both bare bullet points. Grok Bot adds the source and the date, which makes sense when 14 bots write to the same pool.

Two limits shape what the model sees: one on how long a single note can be, and one on how many notes fit in the block at all.

### Each note is cut at 500 characters

Several notes in the research bot’s answer were marked “cut off”. I measured them, and every truncated note was exactly 500 characters long, while the longest complete note was 475. Recall results are clipped the same way. A long note gets saved in full, but no bot ever reads past character 500.

### Only some of the notes get injected

Even with every note trimmed to 500 characters, the pool is too big to paste in whole. The research bot said outright that *“there are more shared entries I can’t see without searching.”* So the injected block as a whole is capped, by a note count or a token budget I couldn’t measure, and any note that doesn’t make the cut can only be found with search.

Hermes has a hard cap too (2,200 characters for `MEMORY.md`), but Hermes enforces it when a note is written, so the agent has to consolidate. Grok Bot applies the cap when notes are read: the pool keeps growing and the injected window stays the same size. In my account the pool had reached about 91 notes after five weeks.

## The Memory Tools

The tool list in the client has three memory tools: `UpdateMemory`, `RecallMemory`, and `SortMemories`. The parameter schemas live on the server, but the client builds a couple of prompts itself, and those show some of the arguments. This is the hidden instruction the app adds when you import memories from another assistant:

```text
Save each entry as its own fact with UpdateMemory action "write" and scope "user",
so all of the user's Bots can recall it. If scope "user" is not offered here,
use your default scope.
```

And this is from the prompt that sets up a new bot cloned from an existing one:

```text
For every memory, persist the content with UpdateMemory action "write" and type "journal".
Do not invent extra facts. Use the listed created_at when present.
```

So `UpdateMemory` takes an `action` (`write`, plus `forget`, which appears in the team review code), a `scope` (`user` among others), and a `type` (`journal` for dated history). Note the line *“if scope “user” is not offered here”*: the scopes offered seem to depend on the kind of bot.

I didn’t call `SortMemories`, and I couldn’t find out what it does. My guess is a tidy-up pass the model can run on request.

### Writing is explicit

Every note I saw reads like a deliberate write during a conversation: “(decided 2026-10-30)”, “As of Oct 31 2026, …”, “confirmed 2026-10-27”. I found nothing like Claude’s background job that rebuilds memory from your chats while you’re away. In Grok Bot, a note exists because a bot chose to call `UpdateMemory` in the middle of a task.

### Recall is keyword search

`RecallMemory` is how a bot reaches notes that aren’t in the injected block. When I asked for a full dump, the main bot ran query after query, found 81 notes, and explained the gap itself:

```text
I found 81 of the roughly 91 stored. My search only returns notes that match the
words I search for, so about 9 of mine and 1 shared note didn't come up.
```

Two things follow from that. First, going by the bot’s own account, recall is keyword search: it only returns notes that contain the words in the query. Semantic search works differently. It turns the query and every note into embeddings (lists of numbers that capture meaning) and returns the notes whose meaning is closest, so a search for “schedule” can find a note about “calendar”. With keyword search, that note stays hidden unless the bot happens to search for “calendar”. Second, there’s no “list everything” operation, even though the bot knows the total count. OpenClaw does hybrid semantic and keyword search over its notes. Grok Bot appears to do keyword search only.

## Testing Whether Memory Is Really Shared

The best way to check a description like this is to write something and watch where it shows up. So I ran a small test.

First, I asked the main Grok Bot to save one shared note:

```text
Small memory test, please do exactly this and nothing else: save one note shared with all my bots that says "TEST NOTE (temporary, delete after Nov 4 2026 test): Manthan's test codeword is violet-kestrel-42." Then reply with just "saved" and which scope/type you used.
```

It replied: *“saved, as a lasting note shared with all your bots.”*

About two minutes later, I asked Cooper, a different bot that hadn’t been part of the conversation:

```text
Quick check, answer only from what's already in your context, without searching memory, files or the web: do you see any saved note about a test codeword? If yes, quote it exactly with its date and which bot saved it. Then, separately, search your memory for "codeword" and tell me if the search finds anything different.
```

Cooper quoted the note straight from its context, with `(learned 2026-11-04) [via Grok Bot]`, and its search for “codeword” returned the same single note, *“saved by Grok Bot to your shared profile.”*

A note written by one bot was in another bot’s prompt on that bot’s first turn after the write, about two minutes later, with no indexing delay and no review step. On a personal account, a shared write goes live everywhere at once.

Afterwards I asked Grok Bot to forget the note. It deleted it, searched for the codeword again, and confirmed nothing came back.

## Team Bots Get a Review Queue

Team bots are the one place where Grok Bot doesn’t let a write go live immediately. When a teammate teaches a team bot something, the change goes into a review queue first. The protobuf schema for a queued change has three fields:

```text
team memory change
  1 action        (WRITE | FORGET)
  2 text
  3 memory_type
```

The app has a review screen for each team bot. When the queue is empty, it shows an “all caught up” message with the line *“New learnings show up here before {botName} applies them for everyone.”* A manager approves or rejects each one. Owners can also promote their own private notes to the team, and the response says how many were created, how many were already shared, and how many stayed private.

Team bots also don’t seem to get the raw notes. The client code also has a schema for a team memory summary, with a `prose` field, a `summary_model`, a `memory_version`, and a `stale` flag. My reading is that team memory gets rewritten by an LLM into a prose summary, which is regenerated when memory changes and injected in place of a long list of notes.

That gives a personal account and a team account quite different policies:

| | Personal bots | Team bots |
| --- | --- | --- |
| Who can write shared memory | Any of your bots, any time | Any teammate, through a review queue |
| Goes live | Next turn | After a manager approves |
| What gets injected | Raw notes, 500-char cap each | Probably an LLM-written summary |

## The Problem: Nothing Cleans Up Automatically

Both bots I asked for a full dump flagged the same thing without being asked: the shared pool contradicts itself.

- Three versions of the same weekly schedule were saved on the same day, each a few hours after the last. All three are still in the pool.
- A note from Oct 28 sets a hard rule for one of my recurring tasks. A note from Oct 31 makes the same rule optional. Both are injected.
- An early note about my preferred writing style was replaced by a later one, but the earlier note was never removed.

Each of these notes was correct on the day it was saved. The trouble is that writes only ever append. When a decision changes, the bot saves the new decision and the old one stays, unless the model happens to also call `forget` on it. I saw nothing that checks for duplicates or resolves conflicts. `forget` only runs when a bot decides to call it, and I never saw `SortMemories` run, so it may do some of this tidying when asked. With a read-time cap on top, which of two contradicting notes a bot sees can depend on which one fits in the injected window or which one a keyword search finds.

This is the failure I wrote about in [Most AI Products Shouldn’t Ship Memory](https://manthanguptaa.in/posts/memory_is_a_mistake/): storage is easy, and the hard part is the retrieval policy, the rule that decides which saved notes end up in which prompt. Grok Bot’s storage is fine. Its retrieval policy is “paste in a capped window of notes and keyword-search the rest”, and that has no answer for a pool where the latest note and the stale note both match.

Sharing makes the problem bigger. In ChatGPT, a stale fact only affects ChatGPT. In Grok Bot, a stale fact saved by one bot is pasted into every other bot’s prompt, and some of those bots act on it on a schedule while you’re not watching.

## How It All Works Together

Here’s what happens when one of your bots starts a turn:

1. **Base prompt and tools.** These come from the server. The client can’t see them, and the bot won’t share them.
2. **Injected memory.** The bot’s own private notes, then shared facts, then shared history, as dated, source-tagged lines, each cut at 500 characters and capped as a whole.
3. **The conversation.** The current chat history.
4. **Recall on demand.** If the bot thinks it’s missing something, it calls `RecallMemory` with keywords and gets back matching notes, also cut at 500 characters.
5. **Writes on demand.** If something should last, the bot calls `UpdateMemory` with a scope and a type. A user-scope write is live in every other bot on its next turn. A team-bot write waits for review.

## How Grok Bot Compares

| | Memory lives in | Gets into the prompt by | Shared across agents |
| --- | --- | --- | --- |
| ChatGPT | Server-side fact list | Always injected | n/a (one assistant) |
| Claude | Server-side memories + chat history | Small block injected, past chats by tool | n/a |
| OpenClaw | Markdown files on your disk | Search on demand (hybrid) | Per agent workspace |
| Hermes | Small `MEMORY.md` + SQLite | Small block fixed at session start, search on demand | Per agent |
| Grok Bot | Server-side records, one per scope | Capped injected block + keyword search | Yes, the whole user pool |

Grok Bot is the only one of the five built around many agents sharing memory. Its design is a sensible version of the ChatGPT pattern, an injected profile, adapted for that: tag each note with where it came from, keep a separate scope for private notes, and put review in front of team writes.

What it lacks is the part Hermes got right. Capping memory at write time forces the agent to decide what’s still true before it saves anything. Capping at read time, as Grok Bot does, leaves that decision to whichever notes happen to fit in the window.

## Conclusion

Grok Bot’s memory is a single pool of short, dated, source-tagged notes shared by all of your bots. A capped slice is pasted into every prompt and the rest is reachable by keyword search. A note written by one bot was in another bot’s prompt on its next turn, about two minutes later, which is why 14 specialised bots on my account behave like one assistant that knows me.

If I could change one thing, it would be to make a new note replace the old one it contradicts instead of sitting next to it. With 14 bots writing to one pool, stale notes pile up faster than any single bot will think to clean them up.

---

*This analysis is based on reading the desktop client and experimenting with my own bots, not official documentation. The server-side parts are inferred, so take it with a grain of salt. If you found this interesting, I’d love to hear your thoughts. Share it on [Twitter](https://twitter.com/manthanguptaa), [LinkedIn](https://www.linkedin.com/in/manthanguptaa/), or reach out at guptaamanthan01[at]gmail[dot]com.*
