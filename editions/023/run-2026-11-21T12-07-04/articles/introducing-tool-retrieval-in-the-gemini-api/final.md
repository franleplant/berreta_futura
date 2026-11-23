---
source_ids:
- introducing-tool-retrieval-in-the-gemini-api-1b3aafed
content_mode: article
label: ARTICLE
---

Tool Retrieval is now in preview in the Gemini API, in the Interactions API. Instead of sending your full tool library in every prompt, your agent keeps it on standby and loads a parameter schema only when the task needs it. It's designed to reduce input tokens and keep tool selection accurate as your agent scales. It works with Gemini 3.6 and later models, at no separate charge.

## How it works

Sending every full schema on every request inflates input token counts, adds latency, and lowers tool-selection accuracy as the candidate list grows.

Add a `tool_search` tool to your request and set `defer_loading: true` on the tools you want to hold back. The model still sees each deferred tool's name and description, so it knows what's available, but the parameter schemas stay out of context. When it needs a tool, it asks for it by name, the API loads the full schema, and the model calls the function, all inside the same request. Each step appears in `interaction.steps`, so you can see which tools the model considered. From there it's normal function calling.

There's no index to build or host: Gemini runs the search on the server. Keep your most-used tools loaded up front and defer the long tail.

Deferred schemas stay out of the start of the prompt, and loaded ones are added later in the conversation, so the cached prefix stays the same from turn to turn.

It also works with remote MCP servers. Set `defer_loading: true` on an `mcp_server` tool and every tool that server exposes is loaded on demand.

## Client-side retrieval

If you maintain your own tool registry, embedding index, or per-user permission filter, declare `tool_search` with `"execution": "client"` and define your search parameters. Your app runs the lookup, which adds one round trip per search. Tools don't need to be declared upfront, so you can expose new ones mid-conversation when a user connects an integration.

## Pricing and models

Input and output tokens are billed at the model's standard rates. Turning on `tool_search` adds a small, fixed block of input tokens, and each schema the model loads is billed as input for the rest of the conversation, the same as a tool declared up front. You save tokens when the schemas you never load outweigh the ones you do, which is the usual case for large libraries. Measure it against your own traffic.

Tool Retrieval works with Gemini 3.6 and later models, including all Gemini 4 models, in the Interactions API.
