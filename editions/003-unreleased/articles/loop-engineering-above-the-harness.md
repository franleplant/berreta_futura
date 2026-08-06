---
source_id: loop-engineering-f0ddfd76
content_mode: faithful_synthesis
label: FAITHFUL SYNTHESIS
---

Loop engineering is replacing yourself as the person who prompts the agent: you design the system that does it instead, a recursive goal where the AI iterates until complete. I believe this may be the future of how we work with coding agents — but it’s early, I’m skeptical, and token costs need watching.

Peter Steinberger recently said: “You shouldn’t be prompting coding agents anymore. You should be designing loops that prompt your agents.” Similarly, Boris Cherny, head of Claude Code at Anthropic, said “I don’t prompt Claude anymore. I have loops running that prompt Claude and figuring out what to do. My job is to write loops”.

For two years you typed a prompt, read what came back, typed the next thing. That part is kind of over, or at least some think so. Now a small system finds the work, hands it out, checks it, records what is done, decides what’s next — the agent harness one floor up, feeding itself.

This is not really a tool thing anymore. A year ago a loop was a pile of bash you maintained forever; now the pieces ship inside the products, the same shape in Codex and in Claude Code, so you design a loop that works in either.

## The five pieces, and then notes

A loop needs five things and a place to remember stuff: automations doing discovery and triage on a schedule; worktrees so parallel agents don’t step on each other; skills for what the agent would otherwise guess; plugins and connectors into your tools; and sub-agents so one has the idea and another checks it.

The sixth is memory: a markdown file or a Linear board, anything outside the conversation that holds what’s done and what is next. The model forgets everything between runs, so the memory lives on disk. The agent forgets, the repo doesn’t.

Automations are what make a loop an actual loop, not one run you did once. Codex schedules them in an Automations tab; Claude Code uses /loop, cron, hooks, or GitHub Actions. And /goal, in both, runs until a condition you wrote is true — in Claude Code, a separate small model checks each turn, so the agent that wrote the code isn’t grading it.

Worktrees keep parallel from turning into chaos: a separate working directory on its own branch, so one agent’s edits literally can not touch another’s checkout. But you are still the ceiling — your review bandwidth decides how many you can run, not the tool.

A skill is how you stop re-explaining the project every session — a folder with a SKILL.md, your intent written down once, where the agent reads it every run. Without skills the loop re-derives your project from zero every cycle; with skills it compounds.

A loop that can only see the filesystem is a tiny loop. Connectors, built on MCP, let it read your issue tracker, message Slack — the difference between “here is the fix” and a loop that opens the PR and pings the channel once CI is green.

Sub-agents keep the maker away from the checker: the model is way too nice grading its own homework, and a second agent catches what the first talked itself into. The loop runs while you are not watching, so a verifier you trust is the only reason you can walk away.

## What one loop looks like

An automation runs every morning; a triage skill reads yesterday’s CI failures, issues and commits. Each finding worth doing gets an isolated worktree, where one sub-agent drafts the fix and a second reviews it; anything the loop can’t handle lands in my triage inbox. The state file remembers what got tried and what is open, so tomorrow’s run picks up where today stopped. You designed it once; you prompted nothing. Steinberger’s point made real.

## What the loop still does not do for you

The loop changes the work, it does not delete you from it. Verification is still on you: “done” is a claim and not a proof. Comprehension debt grows faster the more the loop ships code you did not write, unless you read what it made. And the comfortable posture is the dangerous one: cognitive surrender. Designing the loop with judgement is the cure; designing it to avoid thinking is the accelerant.

I think this is a preview of how our work will evolve — but if I stopped reviewing the code myself, or if I relied entirely on loops, quality would suffer. Set up your loops — but prompting your agents directly is also effective; it’s about balance.

Two people can build the exact same loop and get completely opposite results — one to move faster on work they understand deeply, the other to avoid understanding it at all. The loop doesn’t know the difference. You do.

That’s what makes loop design harder than prompt engineering, not easier. Cherny’s point isn’t that the work got easier. It’s that the leverage point moved.

Build the loop. But build it like someone who intends to stay the engineer, not just the person who presses go.
