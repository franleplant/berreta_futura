---
source_ids:
- my-ai-adoption-journey-0036f2d9
content_mode: article
label: ARTICLE
---

Adopting any meaningful tool has taken me through three phases: inefficiency, adequacy, and then workflow and life-altering discovery. With AI, the path ran like this. I dropped the chatbot for an agent. I forced the agent to reproduce my own work. I handed it the hours I can't work and the tasks it will almost certainly solve. Whenever it makes a mistake, I engineer the harness so it never makes that mistake again. I have no skin in the game, and I'm not here to convince you.

## Drop the Chatbot

Chatbots are a daily part of my AI workflow, but their use in coding is highly limited. You're mostly hoping they come up with the right results from prior training, and correcting them means telling them they're wrong, repeatedly.

My first "oh wow" moment was Gemini reproducing Zed's command palette in SwiftUI from a screenshot. The palette that ships for macOS in Ghostty today is only very lightly modified from it. On brownfield projects, though, results were often poor, and copying code and output back and forth was far less efficient than doing the work myself.

To find value, you *must* use an agent: an LLM that can chat and invoke external behavior in a loop. At a minimum, it must be able to read files, execute programs, and make HTTP requests.

## Reproduce Your Own Work

Claude Code didn't impress me at first. I was touching up everything it produced, and that took longer than doing it myself.

Instead of giving up, I did the work twice. I'd do it by hand, then fight an agent to match it in quality and function, without letting it see my solution. It was excruciating, but expertise formed:

- Break sessions into separate, clear, actionable tasks. Don't try to "draw the owl" in one mega session.
- For vague requests, split planning and execution into separate sessions.
- If you give an agent a way to verify its work, it more often than not fixes its own mistakes.

I also learned when *not* to reach for an agent, which saves time on its own. Models change so fast that I have to keep revisiting that judgment. At this stage, I was no slower than working alone, but no faster either, because I was mostly babysitting.

## End-of-Day Agents

Next, I blocked out the last 30 minutes of each day to start one or more agents. Instead of trying to do more in the time I have, I'd try to do more in the time I don't.

It was annoying at first, but three kinds of work paid off:

- Deep research surveys.
- Parallel agents trying vague ideas I hadn't started.
- Triage of issues and PRs through `gh`. The agents wrote reports, but I didn't allow them to respond.

Most finished in under half an hour. I got a warm start each morning, and I felt I was doing more than before AI, if only slightly.

## Outsource the Slam Dunks

Each morning, I filtered the night's triage for issues an agent would almost certainly solve well. I kept those going in the background, one at a time. Meanwhile, I worked on something else in my normal deep-thinking mode.

Turn off agent desktop notifications. Context switching is very expensive. It's my job to decide when to check on the agent, not the agent's job to interrupt me.

I think working on something else also helps counteract the findings of Anthropic's skill formation paper. It's a trade-off: I don't form skills in what I delegate, but I keep forming them in what I do by hand.

From here, there was no going back. Even if I wasn't more efficient, I could focus my thinking on tasks I loved.

## Engineer the Harness

Agents are most efficient when they get it right the first time. The surest way there is to give them fast, high-quality tools that tell them when they're wrong. I call this "harness engineering": whenever an agent makes a mistake, I engineer a solution so it never makes that mistake again.

It takes two forms:

- **AGENTS.md.** For simple things, like wrong commands or wrong APIs, I update the `AGENTS.md` file. Each line in Ghostty's is based on a bad agent behavior, and it almost completely resolved them all.
- **Actual tools.** For everything else, I write scripts to take screenshots, run filtered tests, and so on, and I mention them in `AGENTS.md`.

This is where I'm at today.

## Always Have an Agent Running

Alongside that, my goal is to always have an agent running. I like pairing this with slow, thoughtful models such as Amp's deep mode. It can take 30+ minutes for small changes, but it tends to produce very good results.

I'm not [yet?] running multiple agents, and I don't really want to. One agent is a good balance between deep manual work I enjoy and babysitting my kind of stupid and yet mysteriously productive robot friend.

It's still just a goal. Right now, I'm maybe effective at it 10 to 20% of a working day. I don't want to run agents for the sake of running agents, only when a task would truly help me.

## Today

I've reached a point where I'm having success with modern AI tooling, with what I believe is a measured view grounded in reality. I really don't care one way or the other if AI is here to stay. The skill formation issues, particularly in juniors without a strong grasp of fundamentals, deeply worry me, however.

I don't work for, invest in, or advise any AI companies. I'm not here to convince you. I just wanted to share how I approach new tools in general, regardless of AI.
