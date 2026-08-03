---
source_id: how-we-built-our-knowledge-base-e986baa0
content_mode: selected_extracts
label: SELECTED EXTRACTS
---

Employees ask our internal knowledge base more than 15,000 questions every day. It's become one of the most widely adopted internal tools at the company since launching 3 months ago. Used by humans, automations and agents.

At Cerebras, our teams work across data center operations, chip design, hardware, training, inference, cloud platform, and more. With hundreds of new employees joining every year, our communication channels were filling up with the same questions:

We built Cerebras Knowledge to help people connect people and systems to useful information.

## Meeting data where it lives

Finding information inside an organization is hard. The data is scattered across tools, and every quarter or so someone proposes the same brilliant fix: let’s record everything in one platform so that all information is in a single place. The dream of a single source of truth, of course, rarely works in practice.

Information is generated wherever it is convenient and ergonomic: suggested edits in a document, threads in Slack, code references in GitHub, and status metadata in Jira. These platforms are tailor-made for their specific domains, optimized through years of product engineering and analytics. Discussing a pull request in Google Docs would be a terrible experience.

So we set out to design a system that required minimal change to existing behavior. On the data collection side, this meant extracting data from each platform directly.

## Anatomy of a knowledge base

Our knowledge base provides three things:

At the core is a single Postgres table that holds embeddings, raw summaries, and metadata from many sources. The system continually ingests data from across the company and maintains a query-ready datastore.

We wanted a data interface that was simple but could work with most forms of data. We also wanted other developers at Cerebras to be able to build custom connectors. The result is deliberately simple: every source, from Slack threads to netlists, lands in the same embeddings table, and anything in that table is immediately queryable through the same interface:

Each data source defines what the data is, how to connect to it, and how often it should be fetched. Each resulting embedding row follows the same interface regardless of whether it came from Slack, a code repository, a document system, or a custom database.

## Slack

Slack was the most important data source we needed to design for. It is where the most up-to-date engineering discussions happen across the company.

## How we process unstructured Slack conversations

We initially tested whether simple embeddings over raw text performed well enough. We quickly realized that vector search alone was insufficient for matching all relevant data.

We needed a hybrid approach. We built Slack ingestion so every thread is retrievable through several search techniques at once, where each technique makes up for the weaknesses of the others:

## Planning and tool fan-out

For every query, we first run a short planning pass where an LLM decides which tools and data sources are likely to matter. The main tools:

- subsystem_index: per-file LLM summaries.

- search: the unified vector pipeline across Slack, wiki, code, and other indexed sources, merged and reranked internally.

- search_slack: direct Slack retrieval.

- search_code: ripgrep over source repositories.

- recent_prs: recent pull requests relevant to the question.

- who_knows: people with demonstrated expertise on a topic.

The planner works over a compact description of what we have indexed: which projects exist, which sources are available in each project, and what each source is good at answering. Given the user’s query and active scope, it emits tool selections that the executor fans out in parallel, normalizes into a common evidence format, and passes to a final synthesis LLM.(4)

## Reranking

A document can surface near the top simply because it shares vocabulary with the query while answering a different question. Before reranking, we combine the retrievers’ incompatible result lists with reciprocal rank fusion, or RRF. For every document, we add weight / (60 + rank) for each list in which it appears, with a default weight of 1.0 and a smoothing constant of 60.

We send the original query and those candidates to a small reranker model. It gives each document a score from zero to ten, and we keep the top ten.(6)

So the output of search is a rich packet of evidence: results fused from different retrievers, deduplicated at the source level, reranked against the actual question, and only then expanded with surrounding context.

## MCP

In the MCP integration, we expose retrieval building blocks as direct tools instead of hiding them behind one “answer this question” endpoint. These tools are intentionally simple and as LLM-free as possible so clients can query them quickly and cheaply.(5)

Each MCP tool corresponds to one underlying retrieval primitive, such as search_slack, search_code, search, or who_knows. Tool inputs and outputs are narrow, structured, and stable, making them easy to call from any client or agent without embedding additional orchestration logic inside the tool itself.

Claude Code, or any MCP-compatible agent, becomes the orchestration engine. It decides which tools to call, in what order, and how to assemble the results into a final answer or code edit. The retrieval layer itself does not depend on those LLM decisions in order to serve requests.

## Web UI

In the web UI, the same tools exist, but they are connected to a complete query pipeline that runs end to end for every user question. The UI agent owns the planner and executor steps.

Synthesis: A final LLM pass takes the typed evidence bundle and original question, then produces the answer shown in the UI, including citations, caveats, and cross-source synthesis.

From the user’s perspective, the web UI is simply “ask a question and get an answer.” Under the hood, it runs the same planner → executor → synthesizer pattern that MCP clients can recreate explicitly.

## Final Thoughts

In the end, the knowledge base works because it meets people where the information already lives, instead of forcing everything into one rigid system. By combining various search techniques, we can surface evidence quickly. The result is a search experience that stays flexible enough for real company data, but structured enough to remain useful as Cerebras keeps growing.

### References

- 4 — Li et al., Search-o1: Agentic Search-Enhanced Large Reasoning Models, arXiv:2501.05366, 2025.

- 5 — Anthropic, Code Execution with MCP, 2025.

- 6 — Liu et al., Lost in the Middle: How Language Models Use Long Contexts, arXiv:2307.03172, 2023.
