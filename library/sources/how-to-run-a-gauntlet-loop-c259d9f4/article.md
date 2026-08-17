# How to Run a Gauntlet Loop

By Matt Shumer · Something Big Is Happening · Jul 27, 2026

A few days ago, I posted a Call of Duty-style game built by Claude Opus 5 from a single prompt.

To be precise, I gave Claude Code [one prompt](https://x.com/mattshumer_/status/2081100592689324502), then left it alone. It spent many hours working, spawned a massive fleet of subagents, wrote roughly 55,000 lines of code, and generated every texture, mesh, animation, and sound in code from scratch. I did not sit there steering it, at all.

[Watch the run on X →](https://twitter.com/mattshumer_/status/2081054356405731740)

The post that started all of this.

[The post quickly racked up millions of views.](https://x.com/mattshumer_/status/2081054356405731740?s=20) As it was so much higher-quality than other Opus 5 demos, understandably, a lot of people called it fake. So, I published the prompt and [open-sourced all the code](https://github.com/mshumer/Claude-of-Duty).

Then something pretty funny happened: people who were skeptical started running versions of the prompt themselves, assuming they could prove it wouldn’t work. Of course, it worked, and [these folks ended up with fully-working games!](https://x.com/0xRishi/status/2081230708593590378?s=20) Other people adapted the same idea to completely different kinds of work.

I get why folks were skeptical… the quality level I demonstrated was so much higher than what other people were getting. So why was I able to do it? What was the difference?

The difference was the way I prompted the agent. Instead of letting it produce one decent result and stop, I made it keep comparing its work against a much higher bar.

I have started calling this a **Gauntlet Loop**.

And it applies to much more than games. You can use it for code, websites, product design, marketing campaigns, writing, research, or almost anything else where the output can be inspected and improved.

## The whole idea

A Gauntlet Loop works like this:

You give a lead agent a goal and a real example of what great looks like. The lead agent decides how to break the goal into the smallest pieces that can be improved separately. Each piece gets its own builder and a separate critic with fresh context.

The builder makes something. The critic compares it against the reference example. If the reference example wins, the critic explains the biggest remaining gap and sends the work back to the builder. The builder fixes it. Then another round begins.

That continues until the result reaches the bar (or, more likely, you decide it is ready).

## First, use an actual agent

Do not paste a Gauntlet Loop into a normal Claude chat and expect the same result.

You need to run it inside an agentic harness such as **Claude Code** or **Codex**. In plain English, that means the model can actually work: open files, run code, render the result, inspect screenshots, use tools, change things, and spawn other agents.

My default right now is Claude Code with Opus 5, especially for visual or creative work. Claude Code subagents can each run in their own clean context window, which is exactly what you want for independent critics.

Codex is very good for backend engineering and other work where visual creation matters less. It is also pretty good at looking at a visual result and criticizing it. But in my experience, it is much weaker than Opus 5 at creating the visual result in the first place.

For serious Gauntlet Loops, I also recommend turning on **ultracode** (type **/effort** and select **ultracode**). It costs much more, but the extra effort usually produces better work on large, multi-agent runs.

## 1. Give it the goal, not your implementation

Tell the agent what you want. Do not tell it exactly how to make it.

My original game prompt did not contain a detailed architecture. It did not list all the systems the game needed or explain how the renderer should work.

It basically said:

> Build a modern, AAA-quality first-person shooter in Three.js. Break the work among subagents. Put every important piece through its own loop with a separate, harsh visual critic. Compare our output side by side with real Call of Duty. If ours loses, keep improving it. Use ultracode.

That was almost the entire prompt.

The most recent models are often very good at deciding how to approach a large goal. When you prescribe the architecture, the workstreams, and every step, you replace the model’s judgment with your own.

Give it the destination. Let it choose the route.

## 2. Give it a real bar

The bar is the most important part.

“Make it amazing” is not a bar. Neither is “make it production-ready” or “keep improving it.”

The agent needs something concrete it can inspect and compare its work against.

For the game, I used actual Call of Duty screenshots. The critic was supposed to look at the two side by side, decide which was better, and keep going whenever ours lost.

For a website, the bar might be a set of the best real websites in the category.

For writing, you could give it paragraphs that have the level of clarity and information compression you want. If you admire Paul Graham’s clarity, for example, you could use a collection of his paragraphs as references… not to copy his voice, but to make the critic ask whether every paragraph in your piece is at least as clear.

For backend engineering, the bar may be a test suite, latency target, failure-recovery test, security review, or reference implementation.

A hard bar does not need to be realistically reachable. My game did not become better than Call of Duty. I stopped the run while it was still improving. Call of Duty gave the agent a direction and kept it from stopping when the game merely looked “pretty good for AI.”

When you do not know the right bar, make finding one part of the task. Do not simply tell the agent to decide what “good” means. Say something like:

> Find a concrete comparison or measurement that plays the same role for this task that real Call of Duty screenshots played for the game in Matt Shumer’s Claude of Duty project. Explain why it is a useful bar, then judge every round against it.

## 3. Let the agent split the work

Tell the lead agent to break the goal into the smallest pieces that can be improved and judged separately.

For a game, the gun, hands, trees, bushes, lighting, movement, enemy behavior, sound, and individual effects might all deserve their own loops.

For an article, the argument, opening, examples, sections, paragraphs, and transitions might be judged separately.

You should not decide all of those pieces in advance. Tell the lead agent to do it. It understands the artifact and can decide which parts should be separated, which should stay together, and which can run in parallel.

The important part is that “make the game better” is too large and vague. “Make this one tree compare favorably with this tree in the reference image” gives the agent a problem it can repeatedly attack.

## 4. Never let the builder grade itself

The builder and critic should be separate agents.

The builder has seen every decision it made. It remembers why it made them. That makes it very good at explaining why its work is reasonable.

You do not want reasonable. You want an independent judgment.

Spawn a fresh critic and give it the goal, the bar, the relevant rules, and the actual artifact. Do not give it the builder’s history or explanation.

The critic should behave almost like an A/B tester. It looks at our output and the reference, without being told which is which. It chooses the better one.

When ours loses, it identifies the largest meaningful gap. The builder fixes that gap. Then the work goes through the gauntlet again.

The critic should inspect the actual thing: the real pixels, running product, rendered page, test results, or finished writing. It should never grade a summary written by the builder.

## 5. Let it keep going

Do not tell it to do three rounds and stop.

Tell it to keep looping. Claude Code includes a **/loop** skill for repeated agent work, but the more important idea is that there should be no arbitrary final round.

The game I posted was still improving when I stopped it. With a sufficiently high bar, there is almost always another gap to close.

You can stop when you like the result, when improvements become too small to matter, or when you have spent as much compute as you are willing to spend.

## Watch it without interrupting it

For long runs, [tell the agent to create a simple live HTML page](https://shumer.dev/how-i-prompt-fable) or [workbench.md](https://workbench.md/) document and update it as it works.

You don’t need to over-specify the specifics of this (yes, this is a recurring theme I will keep talking about!)… just tell it to show progress over time using whatever makes sense for the task: screenshots, videos, drafts, test results, explanations, or other media.

Then you can open the page from your phone and immediately see how the work is evolving. You do not need to interrupt the agent every twenty minutes and ask for an update.

When you are happy, return to Claude Code or Codex and stop the run.

## An optional smoothing pass

When many agents are changing separate parts of one artifact, the pieces can become individually good but slightly inconsistent.

At the end of each major wave, you can spawn one fresh agent to inspect the complete result and smooth it out before the next wave begins.

Its job is not to redesign everything. It should make sure the pieces work together, fix conflicts, and make the result feel like one thing rather than a collection of separately improved parts.

This is useful, but it is not the core of the Gauntlet Loop. The core is still: split, build, judge, repeat.

## Build your own Gauntlet Loop prompt

Paste this into a strong model along with your goal. Let it choose the bar and write the final prompt. Then run the prompt it produces inside Claude Code or Codex.

```
I want to run a Gauntlet Loop for this goal:

[GOAL]

Possible references or quality bars:

[OPTIONAL REFERENCES]

Choose the strongest concrete bar that an agent can actually inspect and compare its work against. If I have not supplied one, propose a useful comp or measurement that plays the same role for this task that real Call of Duty screenshots played for Matt Shumer's Claude of Duty game (read the prompt: https://github.com/mshumer/Claude-of-Duty/blob/main/prompt.md). Explain the bar in one sentence.

Then write a short prompt for Claude Code or Codex in the style of Matt's prompt (minimal is better here, we want the agent to decide the specifics!).

Give the lead agent the goal and the bar, but let it choose the approach. Tell it to divide the goal into the smallest pieces that can be improved and judged independently. For each important piece, it should fan out a builder and a separate critic with fresh context.

Each critic must inspect the real output, compare it directly with the bar—using a blind A/B comparison when possible—identify the biggest remaining gap, and send it back for another round. Keep looping until our output wins or I stop the run.

Have the lead agent maintain a simple live progress page that shows the work evolving over time.

Have it use subagents and ultracode. Do not prescribe the architecture, exact decomposition, or a fixed number of rounds. Keep the final prompt short, just like Matt's.
```

That is really the entire method.

Set an ambitious goal. Give the agent a bar it cannot talk its way around. Let it decide how to split the work. Put every piece through an independent critic. Then keep the loops running longer than almost anyone else would.

## What people built with it

These are not my projects. People took the prompt, pointed it at whatever they wanted, and let it run. Most of these are playable in your browser right now — and there are more in [the full games directory](https://somethingbig.ai/games).

Pick of the bunch · Ryan Campbell

### [Kart Royale](https://racing.ryancampbell.com/)

Kart racing, running in a browser tab.

Pick of the bunch · Vesper

### [Der Koloss](https://www.derkoloss.com/)

Four-player co-op zombie survival with voice chat, Pack-a-Punch, wonder weapons, and relentless waves.

luckeysystems.com

### [Pastel Nuketown](https://nuketown.luckeysystems.com/)

A free-for-all arena shooter in pastel. Plays on a phone if you turn it sideways.

voidtalker.com

### [Dream Logic](https://voidtalker.com/games/dream-logic.html)

Playable in the browser.

Borelli Corp. Entertainment

### [Dungeon Crawler Carnage](https://dungeon-shooter.fly.dev/)

A floor-by-floor dungeon shooter staged as a televised bloodsport.

And more, posted on X

- [@majidmanzarpour](https://x.com/majidmanzarpour/status/2081582876311564447?s=20)
- [@moridinamael](https://x.com/moridinamael/status/2081769098799939950?s=20)
- [@suriadesign](https://x.com/suriadesign/status/2081476469415686576?s=20)
- [@markgadala](https://x.com/markgadala/status/2081372497660756032?s=20)
- [@0xRishi](https://x.com/0xRishi/status/2081230708593590378?s=20)

If you built something with the prompt and it belongs here, [submit it to the games directory](https://somethingbig.ai/games#submit).
