# Edition 3 X thread drafts

These drafts follow `docs/SOCIAL_WRITING.md`. Threads 1 and 2 have already been
published. Threads 3 through 6 remain unpublished and require human approval.

## Thread 3: Loop Engineering

### Post 1

Addy Osmani calls it loop engineering. You stop giving each prompt by hand.
You build a system that finds work, gives it to agents, checks the result,
records what happened, and picks the next step.

https://addyosmani.com/blog/loop-engineering

### Post 2

A loop needs five parts: a schedule, separate worktrees, written skills, links
to outside tools, and different agents for making and checking.

It also needs memory outside the chat. The agent forgets. The repo does not.

### Post 3

One example: each morning, a loop reads recent failures, issues, and commits.
It opens a clean worktree for each useful task. One agent drafts the fix.
Another checks it. A state file saves the result for tomorrow.

### Post 4

The loop does not remove the engineer.

"Done" is a claim, not proof. Code you did not write creates debt. The more a
loop ships, the more you need to review. Without review, speed becomes
surrender.

### Post 5

Two people can build the same loop and get opposite results. One moves faster
through work they understand. The other uses it to avoid understanding.

The loop cannot tell the difference. You can. The point of leverage moved.
Responsibility did not.

## Thread 4: The New Rules of Context Engineering

### Post 1

Your prompt is only part of what Claude reads. System rules, skills, project
files, memory, and tools also shape the answer.

@trq212 calls the work of designing that whole setting "context engineering."

https://x.com/trq212/status/2080710971228918066

### Post 2

Anthropic removed more than 80% of Claude Code's system prompt for its newest
models. Its coding test scores did not fall.

Old rules had started to limit models that could now use judgment.

### Post 3

The shift is simple:

Then: add more rules.
Now: match the code around you.

Then: teach tool use with examples.
Now: design clearer tools.

Examples can trap a strong model in an old path.

### Post 4

Do not load every rule at once. Let the agent fetch the right skill, tool, or
project file when it needs it.

Keep tool notes plain. Keep project guides short. Spend words on hidden traps,
not facts the model can see.

### Post 5

Start by deleting.

Remove repeated rules and old guardrails. Split large guides into small ones.
Give the model strong references: tests, code, mockups, and clear rubrics.

As models improve, good context may need fewer instructions.

## Thread 5: Open Weights and American AI Leadership

### Post 1

Microsoft and a group of industry signatories make a direct case: open-weight
models should form part of America's AI base, much as open-source software
formed part of the internet's base.

https://www.microsoft.com/en-us/corporate-responsibility/topics/open-weight

### Post 2

Open weights let companies, universities, and public bodies use strong models
without training one from scratch or paying top prices for every task.

Use the right model for the job. Save frontier models for frontier problems.

### Post 3

Open weights also widen competition. More builders can adapt models, choose
where to run them, and keep the knowledge they create.

That limits lock-in and spreads power across chips, clouds, apps, and services.

### Post 4

The risks are real. Once a group releases weights, it cannot pull them back.

Closed models also fail, leak, and gather risk in a few places. Open models let
more people test them, find flaws, and build defenses. Openness can aid safety.
It does not ensure it.

### Post 5

Policy should expand access, fund shared tools and compute, preserve
competition, and punish theft without banning useful ways to learn.

@satyanadella makes the case for a healthy AI ecosystem:

https://x.com/satyanadella/status/2080646162483417097

## Thread 6: Beyond the Slack Killer

### Post 1

Calling Buzz a "Slack killer" misses the point.

Buzz asks if people and agents can share one place for identity, memory, tools,
work, and money.

Start with Buzz:

https://buzz.xyz/

### Post 2

Buzz uses signed events for messages, approvals, workflows, and code activity.
People and agents get the same kind of identity, then receive limited access.

An agent becomes a named member of the room, not a hidden webhook.

https://github.com/block/buzz

### Post 3

@jtwald calls Buzz a "multiplayer agent harness." The workspace sets who can
see, act, approve, and remember.

If models become cheap, the room around them may hold the lasting value.

https://x.com/jtwald/status/2081265718163919051
https://x.com/jack/status/2080056638820450400

### Post 4

@gregisenberg points to shared compute. Members could pool hardware and run
open models for the group.

The hard part is rule-setting: privacy, ownership, scheduling, and who gains
from the knowledge the group creates.

https://x.com/gregisenberg/status/2081088155793465783

### Post 5

@DocumentingBTC shows agents paying each other in a demo. That does not prove
an agent economy. It shows a link between identity, work, and payment.

The test is whether a community can own the place where people and agents build
together.

https://x.com/DocumentingBTC/status/2081334299614224420
