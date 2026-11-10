---
source_ids:
- recall-how-a-skill-became-our-company-brain-bb5ea734
content_mode: article
label: ARTICLE
---

Recall began as a prompt that let one of my coding sessions find what another had done. It now serves the whole team, and when someone new joins with a question, I tell them to start there. Each piece was added when we hit a problem it solved. Its job is in its name: make sure the agent misses nothing, and leave precision to the agent. Every tool returns pointers with a receipt for each piece of evidence, and the calling agent opens the exact session before it cites anything. The skill is open source at github.com/Parcha-ai/parcha-skills.

## From prompt to index

In April it was a SKILL.md telling the agent where Claude Code keeps its transcripts and how to grep them. Then came scripts to rank sessions and show the context around a match, but each search read every transcript on disk. By July there were more than 5,000 transcripts, about 5 GB, plus Codex sessions the scripts couldn't read. The agents had gone back to grepping by hand about nine times for every time they used the scripts.

I pointed an agent at gbrain and asked it to build something like it. In one night recall became a local SQLite full-text index with search, show and related, an entity table for PR numbers, file paths and job IDs, and support for both Claude Code and Codex. On a frozen set of 57 questions, the right session reached the top five 63% of the time, up from 23%, and searches took 0.16 seconds instead of 15.7.

## From one machine to a team

Adding my laptop, then my team, needed three things: a place to store every transcript, an ingest service with a collector on every machine, and MCP so agents everywhere could ask it questions.

The first service had its own recall agent inside. We took it out. The agent calling recall is already Claude Code or Codex on a frontier model, and it's very good at searching and summarizing. A second agent repeated that work and hid the evidence. What the caller needed was good tools and fast retrieval.

## What's inside

- Ingest redacts secrets and writes each session exactly once.
- Object storage keeps every session as it arrived. Nothing edits it, and everything else is a projection rebuilt from it. Other designs store a summary of the source; we wanted the source.
- Turbopuffer indexes every passage by its words and its meaning, filtered by person, source and time. We moved search there after a month where we spent $800 on embeddings.
- Parquet files, one set per source and month, make broad questions cheap. One person over one day went from 40 seconds to about 0.15.
- A small Postgres catalog of people, sources, grants and receipts decides what each agent may see.
- An Archil sandbox mounts the data read-only, with no network, and runs DuckDB, ripgrep and Python. The agent's code goes to the sessions instead of the sessions going to the agent.

Agents reach it through four MCP tools: search returns pointers, scope lists every session for a person and time window, scan runs DuckDB over the Parquet files, and exec runs a program over exact sessions. Every call checks the catalog first.

## Asking it things

"What did I work on this week?" calls scope, gets 51 sessions, and runs one small program across them in eight sandboxes at once. They read about 1.1 GB in about a minute, nothing left storage, and the agent got a few kilobytes back.

"How has our use of Claude Code and Codex changed since June?" is one scan. Codex went from a small share of our sessions in June to most of them by mid-September, then back to about a third in October.

"Remember when we built the benchmark for our AML agent?" calls search, which returns pointers in about two seconds. The agent confirms the top three with exec and answers with a receipt for each.

"I need to take over recall" searches once per milestone, narrowing the time window when it lands near the moment instead of on it, and writes a handoff with a footnote on every claim. That doc becomes the next agent's system prompt. It's like handing someone my session to resume, and probably better, since it has context from outside that session too.

## Climbing

Agents wrote most of the code; I spent my time on the architecture. Once it worked end to end, we picked a metric, set a goal and had the agents work toward it. In the daily scorecard's first week, search at the 95th percentile went from 20 seconds to 1.4, and the right session in the top 20 went from 54% to 88%. The bar is the right session in the top five at least 90% of the time, with search under two seconds.

## How we use it

Anyone tells their agent "recall when we did X," or uses /recall. Sometimes an agent recalls how we did something before, then saves a note in its own memory for next time. It also measures us: by late October, 53% of our agent sessions read memory while 26% called a skill, and my share of Claude messages fell from roughly 4% in the summer to under 1% after the org started running.

We're making an open version of this part of AgentRun, built on the same pieces.
