---
source_ids:
- one-month-without-ai-f51481a2
content_mode: article
label: ARTICLE
---

Several months ago I stopped accepting AI contributions to LibreWeddingPlanner, my FOSS project, but I kept using AI at work, where it's very, very common, as it is among my developer friends. It was turning me dumber, lazier, and a worse developer. I stopped writing code, stopped reading what the AI wrote, and started accepting code I'd once have rejected. When a coworker caught a test of mine that didn't test the change it was meant to, I quit AI, even if that costs me my job. I don't think I underperform now, and I've recovered the joy of programming.

## The sweet start

A friend told me that once you start, you cannot stop, and tasks that took days take hours. I enabled the enhanced autocomplete in VS Code (or was it enabled automatically?), and other code generation models followed. To some degree I consider it an addiction.

As a TDD guy, I asked the AI to write the tests first so I could write the code. Except I didn't write the code anymore, and half the purpose of TDD, not biasing the tests by the implementation, was gone. I went so fast I stopped caring. When I saw the agent co-signing my commits, I opted out. I wanted to pretend the code was my own.

## Losing control

I started pasting whole Jira tickets in. On a codebase relatively new to me, I lost track of which changes the task really needed: if the AI, which had read every line, said so, so be it. Other folks I've discussed this with agree they don't know 100% of what they push to production. I bet not even 20%.

Soon I had several agents working at once in separate git worktrees, connected to Jira through ACLI. Larger tasks I had the AI decompose. It gave me convincing PRs I didn't quite understand, so I forced myself to understand them, not to learn the architecture but to avoid humiliation in front of more experienced reviewers.

The focus changes exhausted me. A task I could have done in 20 minutes took an agent 5 minutes and me 2 days to review: code, tests, style, feedback, CI, the linter. In my personal experience, multiplied AI performance is just an illusion; multiplied frustration and exhaustion is guaranteed.

I think there wasn't a single task I could merge as is. I stopped reading the 7-paragraph PR descriptions it wrote. AI is so good at sounding professional that you relax, grow complacent, and accept code you would never have accepted, because you cannot tell why it's bad.

Months passed before I realized I hadn't written a line of code myself in several months. I typed "commit and push" countless times. The AI couldn't solve even half the tasks I gave it, and I babysat it like a junior. Its quality seemed to drop, which reminded me of Google lowering the quality of search results so users search several times and see more ads. With AI companies in uncertain financial times, they will do this and more. Once an agent stalled for 30 minutes; when I demanded the code, it apologized and delivered it in 20 seconds, having spent $30 in tokens for nothing.

## Regaining control

One month ago, a coworker reviewing my PR said a test I'd written didn't test the scenario I was changing. He was right. After 10+ years of TDD, that was a humiliation. I think trying harder with the AI is worthless, because it ends up convincing you and making you complacent again. So I stopped, even if that costs me my job.

When you rework an AI draft yourself, you see how little you knew of what it did, and you ultimately discard everything and start over. I felt rusty, though my side project kept it from being too bad. I went back to TDD, PRs with 5 files changed, 2-line descriptions, deploying with confidence, and asking my peers, not the AI, about architectural decisions. I'm pushing significant changes every day and getting the work done, so I'm not scared of being fired.

## A piece of advice

Say no to drugs. Kind of a metaphor, but not quite. First, realize how dependent you are on a technology you don't control, which costs your employer, if not you, a fortune. I don't think I underperform compared to 2 months ago. I'm more aware of what I'm doing, readier for an incident because I wrote the code that broke, and better the more I work on the codebase myself. That's what your manager should want. You'll also save them money when the AI budget cuts start, because they will, if they haven't already.

Your experience as a developer got you the job, and you're as good as the problems you've faced were difficult. If you turn off your brain and babysit AIs, your value as an engineer decreases.

Wake up. Be brave. Regain control.
