---
source_ids:
- how-to-run-a-gauntlet-loop-c259d9f4
- claude-of-duty-prompt-md-at-main-dd93105d
- github-mshumer-claude-of-duty-a-call-of-duty-qua-2a498bfc
content_mode: article
label: ARTICLE
---

A Gauntlet Loop is how I prompt an agent so it doesn't stop at one decent result. A lead agent gets a goal and a real example of what great looks like. It splits the goal into the smallest pieces that can be improved separately, and each piece gets a builder and a separate critic with fresh context. The critic compares the work against the example. If the example wins, it names the biggest remaining gap and sends the work back. That continues until the result reaches the bar or, more likely, you decide it is ready. My Call of Duty-style game came out of one such prompt. It did not become better than Call of Duty.

## Where it came from

I gave Claude Code one prompt and left it alone. Claude Opus 5 worked for many hours, spawned a massive fleet of subagents, wrote roughly 55,000 lines of code, and generated every texture, mesh, animation, and sound in code. The post racked up millions of views, and many people called it fake, so I published the prompt and open-sourced the code. Skeptics ran the prompt to prove it wouldn't work. They ended up with fully-working games.

The difference was the prompting. Instead of letting the agent produce one decent result and stop, I made it keep comparing its work against a much higher bar.

## Use a real agent

Run it in a harness such as Claude Code or Codex, where the model can open files, run code, render, inspect screenshots, and spawn agents. A normal chat won't give the same result. My default is Claude Code with Opus 5, especially for visual or creative work; its subagents each get a clean context, which is what independent critics need. Codex is very good for backend work and pretty good at criticizing a visual result, but in my experience much weaker at creating one. For serious loops I recommend ultracode. It costs much more, but usually produces better work on large, multi-agent runs.

## Give the goal, not the implementation

My prompt had no architecture and no list of systems. It said, in effect: build an AAA shooter in Three.js, fan out subagents, give each piece a harsh visual critic, compare blind and side by side with real Call of Duty, and keep going if ours loses. The most recent models are often very good at deciding how to approach a large goal. Prescribe the route and you replace their judgment with yours.

## Give it a real bar

This is the most important part. "Make it amazing" is not a bar. The agent needs something concrete to inspect:

- **Game:** actual Call of Duty screenshots.
- **Website:** the best real sites in the category.
- **Writing:** paragraphs with the clarity you want, as a measure rather than a voice to copy.
- **Backend:** a test suite, latency target, security review, or reference implementation.

The bar doesn't need to be reachable. It gives direction and keeps the agent from stopping when the work merely looks "pretty good for AI." If you don't know the right bar, make finding one part of the task. Don't simply let the agent decide what "good" means.

## Split the work, and never let the builder grade itself

Let the lead agent choose the pieces: for a game, the gun, hands, trees, lighting, sound; for an article, the argument, opening, sections, transitions. "Make the game better" is too vague. "Make this tree compare favorably with this reference tree" is a problem the agent can attack again and again.

The builder remembers why it made each decision, which makes it good at explaining why its work is reasonable. You don't want reasonable. You want an independent judgment. Give a fresh critic the goal, the bar, the rules, and the real artifact (pixels, running product, test results, finished prose), never the builder's history or summary. When possible it compares blind, picks the better one, and, when ours loses, names the largest gap.

## Keep going

Don't set a final round. Stop when you like the result, when improvements become too small to matter, or when you've spent as much compute as you're willing to. For long runs, have the agent keep a simple live HTML page or workbench.md showing progress, so you can check from your phone without interrupting it. After each major wave, a fresh agent can optionally smooth out conflicts between separately improved pieces. That is useful, but it is not the core.

## What the run actually scored

The repository's own assessment states the goal was to match a modern Call of Duty, and it does not. Eleven adversarial critics scored frames 3.59, 4.14, 4.05, then 5.05 out of 10. Two shots reached "close"; the rest stayed "amateur." In a blind A/B, every critic in every round picked the real Call of Duty frame. Hands, materials, characters, indirect light, and frame rate (28–30 fps at Retina) all fall short.

It also records that sequential single-owner passes beat parallel fan-out decisively. Three rounds of six agents, each owning one directory, moved the score +0.46 and left frame-ruining defects higher than they started (60, 47, 66), because tonemapping, sky, and indirect light are one coupled system. One sequential pass with a single owner per coupled concern moved it +1.00 and cut defects from 66 to 26. The most valuable single result came from an agent contradicting its own brief: critics kept calling the weapon "untextured," but it was specular-dominated, and the fix was the opposite of what was asked for.
