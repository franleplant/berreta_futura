---
source_ids:
- state-of-agentic-coding-11-the-curiosity-test-li-52c408d9
content_mode: article
label: ARTICLE
---

Software developers are failing a curiosity test. If you're displaced by AI as a software developer, it's self-inflicted, because you haven't been curious in a time of rapid transformation. Armin Ronacher and Ben Vinegar had me on episode 11 of State of Agentic Coding to talk about it, along with DHH coming around, durable agents, and a Lisp you program by talking to it.

## The curiosity test

I published the Ralph loop research in July last year. Cursor thought it was garbage. Nine months later they'd implemented it, then Anthropic did, then OpenAI. Dex calculated it at about $10.42 an hour when it runs in the loop and builds AFK overnight.

Ben pushed back, fairly. People entered the industry young, with infinite time. Now many are in their thirties or forties with responsibilities, and it's hard to retool at this rate, or feel optimistic, when your income and self-worth are in flux. I concur. This change has been forced on the world non-consensually, and it displaces your identity. Whether you're a .NET, Golang or Python developer doesn't matter anymore. What matters is how good a developer you are, and whether you're using what employers now expect as the bare minimum.

Armin noted that people in AI talk a very confident game externally, us included. I don't bloody know. Every new technique strips me raw: you thought you had a mental model, and then the game changes.

## Boom and bust

Ben pointed to Buffalo and Detroit as a long history of people believing the good times will never end. Senior compensation went through the roof in the ZIRP era because the previous bust didn't develop enough talent. The same cycle will repeat. CS enrolments are down; I remember seeing something like 22% in Singapore this year. If you've stayed curious, you can get placed anywhere right now: stand at a whiteboard and explain how to build a coding agent as a sequence diagram, how inferencing works, and what a prompt cache is.

Armin read it differently. We were paid well because we were scarce and competed only with other engineers. He's convinced that exceptional role won't return in the same form. There will probably be a period of more demand, but it will commoditize quickly.

## DHH did the funeral

If you're in love with typing code in an IDE, DHH did the funeral last week, and he's right. You can still type code in your personal workshop. Employers now want you to be very good with the CNC machine, not artisanal woodworking. In his Rails World keynote, photography made portrait painting uneconomic, so painting went to impressionism and cubism.

Chad Fowler told Armin the agent never writes Ruby for him anymore. So what's the point of a language full of sugar for humans if humans aren't writing the code? The languages won't go away, but the communities that swallow this pill and evolve will be the ones that survive. Stop being a cow mooing at other developers. Learn business, talk to founders, be a product engineer. If your company has banned AI outright, quit.

For Armin, the strongest signal is the vocal holdouts turning: DHH, and recently Notch. I can't carry all that water myself. The best I can do is help a curious person reach their own moment. Mine was seeing how easy it is to build a coding agent.

## Four months in 2026

Earendil shipped something around 10,000 lines that took four months. Armin's explanation: LLMs suck at the shape of a contract and the human feel of an API. They solved the problem about twenty times, each in two hours, and none felt right. Finding the right trade-offs took four months.

The result is Pi Durable: shut down the harness, restart it, and it picks up exactly where it left off, over the network and through sub-agents talking to each other. Nearly every agent copied Claude Code's session model: transcript, tool call, tool result, in a loop. Background compaction, or five people talking to one agent in Slack, maps poorly onto that. Armin called it a little bit of cargo culting:

> this technology is moving really, really quickly and is held back by ideas about how it should work that are a year plus old.

My hot take: delete your AGENTS.md and many of your skills after every model release, or every couple of months, and redo them. Why do we even have a shell? Because we used to have a human operator.

## A Lisp you grow by talking to it

Three months earlier Armin had called Lisp the worst language for agents, since they're terrible at counting closing parentheses. I connected an LLM to a running Lisp. I asked what functions were defined, and it asked the image. I asked for a string reverse, typos and all, and it defined one directly into the image. I can roll back to the previous generation. There are only two tool calls: evaluate an expression, or define one as a function.

Imagine a staff-only menu on your website where you evolve the running program by chatting with it, no IDE. What if that's how a user feedback request gets actioned?

## Why Lisp died

You used to have to be a Lisp programmer to do Lisp; now a natural-language interface lets anyone. Armin's answer was more precise: the problem with software is effects, and Lisp can serialise its entire state more than most languages. It died because it was slow without a machine that suited it, it didn't survive the shift to the personal computer, and it's awful for humans to look at. Maybe it's great for LLMs.

Credit to Krzysztof Cieślak, the person behind what everyone now calls spec-driven development, who asked in the GPT-3 era whether Markdown could be how we publish software. For the record, though: code is the spec, folks. As Armin put it, there are specifications and there are vibe specifications.

---

The pasted text ends before the labs section and the chapter links, so neither is covered here.
