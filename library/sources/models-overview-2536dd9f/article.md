# Models overview
Claude Platform Docs

Claude is a family of state-of-the-art large language models developed by Anthropic. Compare the current lineup, find the model ID for every platform, and open each model’s page for its full specs and resources.

## Latest models

If you’re unsure which model to use, start with [Claude Opus 5.5](https://platform.claude.com/docs/en/models/opus-5-5/overview) for most workloads. Use [Claude Fable 5.2](https://platform.claude.com/docs/en/models/fable-5-2/overview) for demanding reasoning and long-horizon agentic work, or when your evals on Claude Opus 5.5 at higher effort still fall short. All current models support text and image input, text output, multilingual capabilities, vision, and tool use.

| | [Claude Fable 5.2](https://platform.claude.com/docs/en/models/fable-5-2/overview)<br>For demanding reasoning and long-horizon agentic work | [Claude Opus 5.5](https://platform.claude.com/docs/en/models/opus-5-5/overview)<br>For long-running agentic coding and knowledge work | [Claude Sonnet 5.5](https://platform.claude.com/docs/en/models/sonnet-5-5/overview)<br>The best combination of speed and intelligence | [Claude Haiku 5.5](https://platform.claude.com/docs/en/models/haiku-5-5/overview)<br>For high-volume, latency-sensitive tasks such as classification, extraction, and routing |
|---|---|---|---|---|
| Comparative latency | Moderate | Moderate | Fast | Fastest |
| Pricing | $8 / input MTok<br>$40 / output MTok | $4 / input MTok<br>$20 / output MTok | $2 / input MTok<br>$10 / output MTok | From $0.10 / input MTok<br>From $0.50 / output MTok |
| Claude API ID | `claude-fable-5-2` | `claude-opus-5-5` | `claude-sonnet-5-5` | `claude-haiku-5-5` |
| **Capabilities** | | | | |
| Thinking | Adaptive (always on) | Adaptive (always on) | Adaptive | Adaptive |
| Default effort | `high` | `medium` | `high` | `medium` |
| Context window | 1M tokens | 1M tokens | 1M tokens | 1M tokens |
| Max output | 128K tokens | 128K tokens | 128K tokens | 128K tokens |
| Reliable knowledge cutoff | Jun 2026 | Jun 2026 | Jun 2026 | Jun 2026 |
| Training data cutoff | Jun 2026 | Jun 2026 | Jun 2026 | Jun 2026 |
| Retirement | Not sooner than November 9, 2027 | Not sooner than September 22, 2027 | Not sooner than September 28, 2027 | Not sooner than October 7, 2027 |
| **Model IDs** | | | | |
| Claude API alias | `claude-fable-5-2` | `claude-opus-5-5` | `claude-sonnet-5-5` | `claude-haiku-5-5` |
| Amazon Bedrock ID | `global.anthropic.claude-fable-5-2` | `anthropic.claude-opus-5-5` | `anthropic.claude-sonnet-5-5` | `anthropic.claude-haiku-5-5` |
| Claude Models on Google Cloud (Google managed) ID | `claude-fable-5-2` | `claude-opus-5-5` | `claude-sonnet-5-5` | `claude-haiku-5-5` |
| Microsoft Foundry ID | `claude-fable-5-2` | `claude-opus-5-5` | `claude-sonnet-5-5` | `claude-haiku-5-5` |
| Claude Platform on AWS ID | `claude-fable-5-2` | `claude-opus-5-5` | `claude-sonnet-5-5` | `claude-haiku-5-5` |
| [Claude Models on Google Cloud (Anthropic managed) ID](https://platform.claude.com/docs/en/build-with-claude/claude-models-on-google-cloud/anthropic-managed) | `claude-fable-5-2` | `claude-opus-5-5` | `claude-sonnet-5-5` | `claude-haiku-5-5` |

Once you’ve picked a model, [learn how to make your first API call](https://platform.claude.com/docs/en/get-started). To understand how model IDs, aliases, and snapshots work, see [Model IDs and versioning](https://platform.claude.com/docs/en/about-claude/models/model-ids-and-versions). For the reliable-knowledge and training-data cutoffs behind each model, see Anthropic’s [Transparency Hub](https://www.anthropic.com/transparency).

## All models

Older models might still be available, but where possible, you should default to the [latest models](https://platform.claude.com/docs/en/about-claude/models/overview#latest-models-comparison). To move to a newer model, see the [migration guides](https://platform.claude.com/docs/en/about-claude/models/migration-guide). For retirement dates, see [model deprecations](https://platform.claude.com/docs/en/about-claude/model-deprecations).

| Model | Capabilities | | Base tokens | |
|---|---|---|---|---|
| Name | Context window | Max output | Input | Output |
| [Claude Fable 5.2](https://platform.claude.com/docs/en/models/fable-5-2/overview) | 1M tokens | 128K tokens | $8 / MTok | $40 / MTok |
| [Claude Opus 5.5](https://platform.claude.com/docs/en/models/opus-5-5/overview) | 1M tokens | 128K tokens | $4 / MTok | $20 / MTok |
| [Claude Sonnet 5.5](https://platform.claude.com/docs/en/models/sonnet-5-5/overview) | 1M tokens | 128K tokens | $2 / MTok | $10 / MTok |
| [Claude Haiku 5.5](https://platform.claude.com/docs/en/models/haiku-5-5/overview) | 1M tokens | 128K tokens | From $0.10 / MTok | From $0.50 / MTok |
| [Claude Mythos 5.2](https://platform.claude.com/docs/en/models/mythos-5-2/overview) | 1M tokens | 128K tokens | $8 / MTok | $40 / MTok |
| [Claude Fable 5.1](https://platform.claude.com/docs/en/models/fable-5-1/overview) | 1M tokens | 128K tokens | $10 / MTok | $50 / MTok |
| [Claude Mythos 5.1](https://platform.claude.com/docs/en/models/mythos-5-1/overview) | 1M tokens | 128K tokens | $10 / MTok | $50 / MTok |
| [Claude Fable 5](https://platform.claude.com/docs/en/models/fable-5/overview) | 1M tokens | 128K tokens | $10 / MTok | $50 / MTok |
| [Claude Mythos 5](https://platform.claude.com/docs/en/models/mythos-5/overview) | 1M tokens | 128K tokens | $10 / MTok | $50 / MTok |
| [Claude Opus 5](https://platform.claude.com/docs/en/models/opus-5/overview) | 1M tokens | 128K tokens | $5 / MTok | $25 / MTok |
| [Claude Opus 4.8](https://platform.claude.com/docs/en/models/opus-4-8/overview) | 1M tokens | 128K tokens | $5 / MTok | $25 / MTok |
| [Claude Opus 4.7](https://platform.claude.com/docs/en/models/opus-4-7/overview) | 1M tokens | 128K tokens | $5 / MTok | $25 / MTok |
| [Claude Opus 4.6](https://platform.claude.com/docs/en/models/opus-4-6/overview) | 1M tokens | 128K tokens | $5 / MTok | $25 / MTok |
| [Claude Opus 4.5](https://platform.claude.com/docs/en/models/opus-4-5/overview) | 200K tokens | 64K tokens | $5 / MTok | $25 / MTok |
| Claude Opus 4.1 | 200K tokens | 32K tokens | $15 / MTok | $75 / MTok |
| Claude Opus 4 | 200K tokens | 32K tokens | $15 / MTok | $75 / MTok |
| [Claude Sonnet 5](https://platform.claude.com/docs/en/models/sonnet-5/overview) | 1M tokens | 128K tokens | $2 / MTok | $10 / MTok |
| [Claude Sonnet 4.6](https://platform.claude.com/docs/en/models/sonnet-4-6/overview) | 1M tokens | 128K tokens | $3 / MTok | $15 / MTok |
| [Claude Sonnet 4.5](https://platform.claude.com/docs/en/models/sonnet-4-5/overview) | 200K tokens | 64K tokens | $3 / MTok | $15 / MTok |
| Claude Sonnet 4 | 200K tokens | 64K tokens | $3 / MTok | $15 / MTok |
| [Claude Haiku 4.5](https://platform.claude.com/docs/en/models/haiku-4-5/overview) | 200K tokens | 64K tokens | $1 / MTok | $5 / MTok |

## Using the Models API

You can query model capabilities and token limits programmatically with the [Models API](https://platform.claude.com/docs/en/api/models/list) . The response includes [`max_input_tokens`](https://platform.claude.com/docs/en/api/models#model_info.max_input_tokens) , [`max_tokens`](https://platform.claude.com/docs/en/api/models#model_info.max_tokens) , and a [`capabilities`](https://platform.claude.com/docs/en/api/models#model_info.capabilities)  object for every available model.

Each model in the response also has a [`line`](https://platform.claude.com/docs/en/api/models#model_info.line)  field, which names the model line it belongs to. Claude Opus 4.5 and Claude Opus 4.6 both report `opus`. Use `line` to group models, for example, in a model picker. `line` is `null` when a model belongs to no line. Read `line` instead of inferring it from the model’s `id`. Anthropic might add more lines, so don’t treat the set of values as fixed.

Each model’s `capabilities` object includes [`thinking.types.disabled`](https://platform.claude.com/docs/en/api/models#thinking_types.disabled) , which reports whether the model accepts `thinking: {type: "disabled"}`, the setting that [turns thinking off](https://platform.claude.com/docs/en/build-with-claude/thinking#turning-thinking-off). `supported` is `false` when the model rejects `"disabled"` with a 400 error, and `true` on a model that doesn’t support thinking. Even when `supported` is `true`, the API can still reject a `"disabled"` request for another reason. One such reason is an [effort](https://platform.claude.com/docs/en/build-with-claude/effort) level that the model doesn’t allow with thinking off.

Each model’s `capabilities` object also includes [`thinking.types.between_tools`](https://platform.claude.com/docs/en/api/models#thinking_types.between_tools) , which reports whether the model accepts `thinking: {type: "between_tools"}`, the setting that [turns off up-front thinking](https://platform.claude.com/docs/en/build-with-claude/thinking#turning-thinking-off). `supported` is `false` when the model rejects `"between_tools"` with a 400 error. Even when `supported` is `true`, the API can still reject a `"between_tools"` request for another reason, such as an [effort](https://platform.claude.com/docs/en/build-with-claude/effort) level that the model doesn’t allow with `"between_tools"`. For Claude Sonnet 5.5, for example, the Models API reports `thinking.types.between_tools.supported` as `true` and `thinking.types.disabled.supported` as `false`.

Each model’s `capabilities` object also includes [`server_tools`](https://platform.claude.com/docs/en/api/models#model_capabilities.server_tools) , which reports whether the model accepts the [web search](https://platform.claude.com/docs/en/agents-and-tools/tool-use/web-search-tool) and [code execution](https://platform.claude.com/docs/en/agents-and-tools/tool-use/code-execution-tool) tools. It doesn’t cover other server tools, such as web fetch. `server_tools.web_search.supported` and `server_tools.code_execution.supported` are `true` when the model accepts at least one version of that tool, not necessarily every version. `server_tools.supported` is `true` when the model accepts at least one of the two tools. Even when a tool is supported, your organization’s settings can still cause a request that uses it to fail. For example, an administrator can [disable web search](https://platform.claude.com/docs/en/agents-and-tools/tool-use/web-search-tool#how-to-use-web-search).

The top-level [`code_execution`](https://platform.claude.com/docs/en/api/models#model_capabilities.code_execution)  capability is a different check. It reports whether code that Claude runs in the code execution tool can call the request’s other tools, as in [programmatic tool calling](https://platform.claude.com/docs/en/agents-and-tools/tool-use/programmatic-tool-calling). For Claude Haiku 4.5, for example, the Models API reports `server_tools.code_execution.supported` as `true` and `code_execution.supported` as `false`.

The API reference lists the List Models endpoint’s parameters and full response.

## Prompt and output performance

Current Claude models excel in:

* **Performance:** Top-tier results in reasoning, coding, multilingual tasks, long-context handling, honesty, and image processing. See [Prompting best practices](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices) for general and model-specific prompting guidance.
* **Engaging responses:** Claude models are ideal for applications that require rich, human-like interactions. If you prefer more concise responses, adjust your prompts to guide the model toward the output length you want. Refer to the [prompt engineering guides](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering) for details.
* **Output quality:** When migrating from a previous model generation, you might notice larger improvements in overall performance. If you’re on Claude Opus 5 or earlier, see the [Claude Opus 5.5 migration guide](https://platform.claude.com/docs/en/models/opus-5-5/migration-guide).

## Get started with Claude

Whether you’re a developer looking to integrate Claude into your applications or a user wanting to experience the power of AI firsthand, the following resources can help.

[Intro to Claude](https://platform.claude.com/docs/en/intro)

Explore Claude’s capabilities and development flow.

[Quickstart](https://platform.claude.com/docs/en/get-started)

Learn how to make your first API call in minutes.

[Choosing a model](https://platform.claude.com/docs/en/about-claude/models/choosing-a-model)

Establish criteria and pick the right model for your use case.

[Pricing](https://platform.claude.com/docs/en/about-claude/pricing)

Complete pricing, including batch discounts and prompt caching rates.

[Model deprecations](https://platform.claude.com/docs/en/about-claude/model-deprecations)

Lifecycle status and retirement commitments for every model.

[Claude Console](https://platform.claude.com/)

Craft and test prompts directly in your browser.

Looking to chat with Claude? Visit [claude.ai](https://claude.ai). If you have questions, contact the [support team](https://support.claude.com/) or the [Discord community](https://www.anthropic.com/discord).
