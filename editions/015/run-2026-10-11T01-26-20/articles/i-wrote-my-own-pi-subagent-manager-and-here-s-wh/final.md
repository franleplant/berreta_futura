---
source_ids:
- i-wrote-my-own-pi-subagent-manager-and-here-s-wh-921a4ad9
content_mode: article
label: ARTICLE
---

I've been a big fan of Pi, the coding harness, because I can bend it to my liking, and my own testing, objective and subjective, shows it gets most tasks done faster and cheaper than Claude Code or Codex CLI, simply because it bloats the context much less. Pi has no built-in subagents, though. For most of this year I wasn't a big subagent user, but I think the Claude 5.5 and GPT 6 generation is ready to be used regularly in subagent mode, and Opus 5.5 and GPT 6.1 Sol are the first models that are both good at it and economically feasible. I used two existing Pi subagent extensions, then wrote my own with exactly the features I wanted.

## Why I held off

Until before Opus 5.5 and GPT 6.1 Sol dropped, I had two reasons.

First, older models could call a subagent tool, since it's just another tool call, but they didn't think of work in a subagentic paradigm. GPT 5.3 and Opus 4.5 knew "how to hold the tool." By GPT 5.6 and Opus/Sonnet 5, models knew better when to fork context and when to start fresh. Fable and Astra were the first "Staff Software Engineer" class models: they could break a task into a multi-level hierarchy and run five copies of themselves without tripping over git and port conflicts.

Second, Fable and Astra are costly. Left unbounded, they eat a $200 plan window in 20 minutes. Claude had to ship a fix so that just saying "workflow" in a prompt wouldn't spin up 20 Fables at $100 a minute.

Opus 5.5 and 6.1 Sol changed that, so now I often end my prompts with "use subagents." That's all it takes to nudge the model. I'd even submit that it's better to use them as subagents than to check out worktrees and act as the orchestrator yourself.

By orchestration I don't mean running several copies of Claude Code in worktrees through tools like Conductor or T3 Code. I mean one session in one harness creating multiple threads internally.

## What I used before

I started with @nicopreme's `npm:pi-subagents`, the first one, the most popular, and it works really well. Then I moved to @nicht_tintin's `npm:@tintinweb/pi-subagents`, which pairs with his task-list extension. Its Claude-like UX is really great, you can steer the child as well as the parent, and agent-to-agent communication isn't over-engineered.

## What I wanted

I won't pretend I know better than Boris or Tibo how to build a harness. These are my tastes:

- **Claude's view:** agents listed near the input box, each with its status (running, paused, errored), and the ability to drop into one and steer it.
- **Codex's naming:** `/root` is the main agent, `/root/task-1` is forked from it and inherits its context, and `/task-2` is independent with untainted context, useful for adversarial reviews.
- **Pi-subagents' presets:** predefined agents with a fixed model and thinking level, such as a fast, low-thinking Luna agent for `git push` and a chonky, unhallucinating Fable or Astra for research and refactor plans, so I don't have to prompt "use an opus subagent" every time.
- Configurable nesting depth (I like three levels) and a cap on parallel subagents.
- The whole history of every subagent in a single `.jsonl` file, so everything resumes after a crash.
- Several models per agent, using whichever is available and allowed.
- Two modes: opportunistic, where the main model uses subagents when it wants, and orchestrator, where it always delegates and stays free to talk to you.

## So I built my own

It borrows many architectural decisions from both earlier extensions, and it is exactly the set of things I wanted. It's on npm and already getting some downloads, though I don't know why. If you want the same things from a subagent manager, feel free to use it.
