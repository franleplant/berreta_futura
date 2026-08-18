---
source_ids:
- my-ai-adoption-journey-0036f2d9
content_mode: article
label: ARTICLE
---

Adopting any meaningful tool takes me through three phases: inefficiency, adequacy, then discovery that alters my workflow and life. With AI I had to force myself through the first two, because I already had a workflow I was happy with. Six steps got me from skeptic to no-way-back: drop the chatbot for an agent, reproduce your own commits agentically until expertise forms, kick off agents in the last 30 minutes of the day, hand agents the tasks you're confident they'll do well while you work on something else, engineer the harness so a mistake can't recur, and try to keep an agent running at all times. This was written by hand, in my own words. I hate that I have to say that.

## Drop the chatbot

Chatbots are a daily part of my AI workflow, but their utility in coding is limited: you're hoping their training produces the right answer, and correcting them means you telling them they're wrong repeatedly. My first "oh wow" was Gemini reproducing Zed's command palette in SwiftUI from a screenshot, very well; what ships in Ghostty is only lightly modified from that. In brownfield projects the same interface disappointed me, and the copying and pasting was obviously slower than doing the work myself. To find value you must use an agent: it needs at minimum to read files, execute programs, and make HTTP requests.

## Reproduce your own work

Claude Code didn't impress me at first. So I did the work twice: manually, then fighting an agent to reach identical quality without letting it see my solution. Excruciating, but expertise formed, and I discovered from first principles what others were already saying. Break work into clear, actionable tasks instead of drawing the owl in one session. Split vague requests into planning and execution. Give the agent a way to verify itself and it usually fixes its own mistakes. The negative space matters too: knowing when not to reach for an agent saves time, though the pace of models makes me revisit that constantly. I felt no slower than before, not faster, and I was content.

## End-of-day agents

Instead of trying to do more in the time I have, try to do more in the time I don't have. Unsuccessful and annoying at first, then three categories held up: deep research surveys, parallel agents on vague ideas to illuminate unknown unknowns, and issue and PR triage with `gh`. I would not allow agents to respond; I wanted reports. Most finished inside half an hour. I got a warm start the next morning.

## Outsource the slam dunks

Each morning I filter the triage results by hand for issues an agent will almost certainly solve, run them in the background one at a time, and go do my own deep work. Turn off desktop notifications: context switching is expensive, and it's my job to decide when I interrupt the agent. I think working on something else partly counteracts the [skill formation paper](https://www.anthropic.com/research/AI-assistance-coding-skills); you trade skills on the delegated tasks for skills on the ones you keep. Here I passed into no-way-back territory, mostly because I could spend my thinking on the tasks I love.

## Engineer the harness

Agents are more efficient when they get it right the first time, and the surest way is fast, high quality tools that tell them when they're wrong. Whenever an agent makes a mistake, engineer it so the mistake can't happen again. Two forms: better implicit prompting in `AGENTS.md`, where every line in Ghostty's file comes from a bad behavior it almost completely resolved, and actual programmed tools like screenshot scripts or filtered test runs, usually paired with an `AGENTS.md` note. This is where I'm at today.

## Always have an agent running

If none is running, I ask whether there's something an agent could be doing. I like pairing this with slower models like Amp's deep mode, which can take 30+ minutes for small changes and does tend to produce very good results. I'm not [yet?] running multiple agents and don't really want to. It's still a goal: maybe 10 to 20% of a working day. I don't want to run agents for the sake of it, only when the task would truly help, which means keeping a stream of work worth delegating.

## Today

I'm having success with modern tooling and I think my view is measured and grounded. I don't much care whether AI is here to stay, though skill formation in juniors without a strong grasp of fundamentals deeply worries me. The landscape moves fast enough that I expect to laugh at my naivete soon. I don't work for, invest in, or advise any AI companies, there are reasons beyond utility to avoid this, and I respect anyone's decision. I'm not here to convince you.
