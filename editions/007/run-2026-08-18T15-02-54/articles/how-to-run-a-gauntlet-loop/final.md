---
source_ids:
- how-to-run-a-gauntlet-loop-c259d9f4
- claude-of-duty-prompt-md-at-main-dd93105d
- github-mshumer-claude-of-duty-a-call-of-duty-qua-2a498bfc
content_mode: article
label: ARTICLE
---

I gave Claude Code one prompt and left it alone. It worked for many hours, spawned a massive fleet of subagents, wrote roughly 55,000 lines, and generated every texture, mesh, animation and sound in code from scratch: a Call of Duty-style game. The difference wasn't the model. It was that I never let the agent produce one decent result and stop. I made it keep comparing its work against a much higher bar. I call this a Gauntlet Loop, and it applies to anything whose output can be inspected and improved.

## The loop

You give a lead agent a goal and a real example of what great looks like. The lead agent breaks the goal into the smallest pieces that can be improved separately. Each piece gets its own builder and a separate critic with fresh context. The builder makes something. The critic compares it against the reference. If the reference wins, the critic names the biggest remaining gap and sends the work back. Then another round begins, until the result reaches the bar or you decide it is ready.

## What makes it work

Run it in an agentic harness, Claude Code or Codex, where the model can open files, run code, render, inspect screenshots, and spawn other agents. Pasting this into a normal chat will not do. My default right now is Claude Code with Opus 5, especially for visual or creative work. Codex is very good for backend engineering, and pretty good at criticizing a visual result, but much weaker at creating one. For serious runs I turn on ultracode; it costs much more, but usually produces better work on large, multi-agent runs.

Tell it the goal, not your implementation. My prompt contained no architecture and no list of systems. Give it the destination. Let it choose the route.

Then give it a real bar. "Make it amazing" is not a bar. I used actual Call of Duty screenshots, judged side by side. For writing, it might be paragraphs with the clarity you want; for backend work, a test suite or latency target. The bar does not need to be reachable. My game did not become better than Call of Duty. It kept the agent from stopping at "pretty good for AI."

Never let the builder grade itself. The builder remembers every decision and is very good at explaining why its work is reasonable. Spawn a fresh critic with the goal, the bar, and the artifact, not the builder's history. Have it behave like an A/B tester, blind where possible, inspecting the real pixels or test results, never a summary. And set no final round. The game I posted was still improving when I stopped it.

For long runs, have the agent keep a simple live page: screenshots, drafts, test results, whatever fits. You can watch from your phone instead of interrupting every twenty minutes.

## Where it landed

The goal was to match a modern Call of Duty. It does not. Eleven adversarial critics scored the frames 3.59, 4.14, 4.05, then 5.05 out of ten. Two shots reached "CLOSE"; the rest remain "AMATEUR". In blind A/B, every critic in every round picked the real Call of Duty frame. Hands are blocky, enemies read as mannequins at distance, indirect light is an approximation, and it runs 28 to 30 fps at Retina.

One process finding worth recording: sequential single-owner passes beat parallel fan-out decisively. Three rounds of six agents each owning one directory moved the score +0.46 and left frame-ruining defects higher than they started, 60 to 47 to 66, because tonemapping, sky and indirect light are one coupled system. One sequential pass with a single owner per coupled concern moved it +1.00 and cut defects from 66 to 26.
