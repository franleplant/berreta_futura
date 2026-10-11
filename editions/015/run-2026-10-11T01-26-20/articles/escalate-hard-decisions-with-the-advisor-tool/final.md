---
source_ids:
- escalate-hard-decisions-with-the-advisor-tool-ac6174fd
content_mode: article
label: ARTICLE
---

The advisor tool lets Claude consult a second, typically stronger model at key moments: before committing to an approach, when an error keeps recurring, or before declaring a task done. The advisor reads the full conversation, every tool call and result included, and returns guidance Claude applies before continuing. Claude decides when to call it. It's experimental, works only on the Anthropic API, and its behavior, pricing, and availability may change.

## When it helps

It fits long, multi-step tasks where most turns are routine but plan quality decides the outcome: large refactors, debugging a recurring error, work you want checked before Claude calls it done. It adds less on short tasks, or where every turn needs the strongest model. There, switch the main model instead.

## Turning it on

- `/advisor opus` sets it mid-session and saves it as your default. With no argument it opens a picker; on surfaces without one (`-p`, Agent SDK, desktop, Remote Control; v2.1.260+) it prints the current advisor.
- `"advisorModel": "opus"` in your settings file sets a persistent default.
- `claude --advisor opus` sets it for one session. The flag isn't listed in `--help`. Launch fails if the main model doesn't support the advisor, the requested model can't advise, `availableModels` excludes it, or Fable still needs usage-credits consent. Background sessions start without the advisor instead.

A saved advisor your main model doesn't support waits until you switch to a compatible one. If the API already refused it in the conversation, it stays off until `/clear` or `/compact`.

## Choosing a model

An advisor must rank at or above the main model.

| Main model | Accepted advisors |
| --- | --- |
| Haiku 4.5, Sonnet 4.6 | Fable, Opus, Sonnet, Haiku 5.5 |
| Opus 4.6 | Fable, Opus, Sonnet 5+, Haiku 5.5 |
| Sonnet 5, Haiku 5.5 | Fable, Opus 4.7+, Sonnet 5+, Haiku 5.5 |
| Opus 4.7, 4.8 | Fable, Opus 4.7+, Sonnet 5.5 |
| Sonnet 5.5 | Fable, Opus 5+, Sonnet 5.5 |
| Opus 5, 5.5 | Fable, Opus 5+ |
| Fable 5 | Fable 5.1, Fable 5 |
| Fable 5.1 | Fable 5.1 |

Fable needs Fable access, and Fable 5.1 needs v2.1.257+. Haiku 4.5 can call the advisor but can't be one. Aliases (`fable`, `opus`, `sonnet`) follow Claude Code's built-in defaults; full IDs like `claude-opus-5-5` also work. Subagents inherit the advisor and check pairing against their own model.

If the advisor ranks too low, Claude Code doesn't attach it and tells you. If the API refuses an attached pairing, Claude Code resends without it, silently: no error, no advisor calls.

On plans where Fable bills to usage credits, a Fable advisor does too. Until you accept that consent through `/model fable`, Claude Code won't apply Fable as the advisor and sends requests without it.

Common pairings: Sonnet with Opus for routine work that escalates planning and completion checks; Haiku with Opus for the lowest-cost main model with strong planning; Opus with Opus when an independent check matters more than cost; Fable with Fable for the highest capability. Claude Code doesn't apply an Opus or Sonnet advisor to a Fable main model.

## During a session

You can ask for a consultation in your prompt; there's no setting to cap or force calls. The transcript shows an `Advising` line, then one of three outcomes: reviewed (press `Ctrl+O` for the guidance), declined (with a reason, if given), or unavailable with an error code. Claude generally follows the advice, but when its own evidence contradicts a specific claim, it surfaces the conflict instead.

## Cost and caching

Each call bills the advisor's tokens at its own rates on the API, or against your plan's limits on a subscription. Because Claude calls it only at decision points, a fast main model with a strong advisor typically costs less than running the strong model throughout. Usage shows in `/usage`.

Toggling the advisor doesn't invalidate the main model's prompt cache. The advisor's own read is never cached: each call processes the whole transcript anew.

## Requirements and turning it off

It needs the Anthropic API (not Bedrock, AWS, Google Cloud, or Foundry; gateways work only if they forward the request intact), a supported main model, and feature-flag fetching. Setting a variable such as `DISABLE_TELEMETRY` keeps it off.

`/advisor off` stops it. `CLAUDE_CODE_DISABLE_ADVISOR_TOOL=1` disables it entirely, ignoring `advisorModel` and `--advisor`.

## Related features

The advisor runs at decision points, when Claude asks. `opusplan` runs the stronger model during plan mode, then switches to Sonnet. A subagent with `model` set runs it for a whole delegated subtask. `/model` switches from the next request onward.
