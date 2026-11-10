---
source_ids:
- critical-thinking-when-agents-do-the-work-dcced816
content_mode: article
label: ARTICLE
---

Increasingly, nothing in my day-to-day forces critical thinking on me, now that so much of my work runs through agents. I'm a big fan of these tools, and I'm not arguing for less agentic work. But as the models improve, fewer errors are obvious. Most outputs will be well-written and mostly correct, and they won't demand a second look. Even if you run many agents at once, you still have only one pair of eyes on what they produce. You have to build critical thinking into your day, because by default nothing will do it for you. Delegate entirely where being wrong is cheap; keep the reasoning where others will live with the consequences.

## Offloading, deferral and surrender

Most of our thinking used to happen in the space between question and answer. That space is now measured in seconds.

I see a spectrum. At the top is cognitive offloading: you delegate the task but keep ownership of the result. I do this all day, and you should too. In the middle is deferral: the tool's output becomes your new input and stops being a hypothesis. At the bottom is cognitive surrender, a term coined by Steven Shaw and Gideon Nave at Wharton: the output quietly becomes your own, and you feel no need to check it.

People drift down this spectrum as trust, or laziness, grows. Each step seems reasonable. You read the last answer well, so you skim the next, then scan only its skeleton. Then someone asks about a line and you can't explain it, even with your agent's help.

That is how cognitive debt accumulates. The codebase looks pristine and the tests pass; nobody notices until a change is needed and nobody understands the system anymore. The same holds when you sign off on a spec after reading its table of contents.

Holding the full model of a large codebase in your head is impossible. The Claude Code team has said they rebuild understanding on demand, asking Claude to explain a slice when they need it. You don't need the full model, as long as you can rebuild it locally. You just need to know what you don't have.

When I had to choose among three similar hotels for a course recording, I let an AI decide. It worked, and I'd do it again. I wouldn't do that with our money, our kids' careers, or decisions at work about what to build and whether it's safe to ship.

## The questions I ask myself

**Did I form a hypothesis before asking?** Even a bad guess. Once you've read a well-written answer, it's hard to imagine another. If you have nothing, ask the model for a blind spot pass to find your unknown unknowns.

**Am I asking it to help me think, or to think for me?** Both are fine if you know which.

**What would have to be true for this to be wrong?** Then go find out. A real test beats the model's self-assessed confidence.

**Have I heard the counterargument?** On open questions where I've taken a hard stance, I ask more than one model to argue the other side, then form my own view.

**Would I bet on this in front of the person who has to maintain it?**

**What am I no longer practicing?** Letting some routine debugging go is fine, if I choose to.

## Verification as a habit

The bottleneck has shifted from coding to being sure you're right. Give the agent a way to verify its work, through end-to-end tests, property tests or real app interactions, and it can change, check, read and retry before you look. You then build the loops and review the evidence.

You can surrender verification too. Agents make tests cheap, so you'll see a lot of green. A test written with the same mistake as the feature will pass, and a green check proves one property only. When a check goes green, ask what it proved, then what it didn't.

Define "verified" upfront; afterwards you'll rationalize any outcome. Make the finish line tangible: a passing test, a screenshot, a log. When an agent reports it's done, read the command it ran and its output before the summary. A self-critique subagent in a fresh context is worth running every time. I still ask, "Did I miss anything?", and it often returns two or three more things.

Outside code, the rule holds. If an agent summarized fifty customer calls, check a couple of the sources. Check the number your recommendation depends on.

## Actually paying attention

An agent hands you a 600-line PR. You glance at the structure, the names look reasonable, the tests pass, and you approve. Somewhere inside is a reordered transaction boundary or a flipped default. You reviewed only for what you already expected to find.

Read the diff as if the AI didn't write it, then look past it at what the agent decided: defaults, scope, which requirement it reinterpreted when two clashed. Ask it to list its decisions and assumptions. Pick lines at random and quiz yourself. For a document, close it and write the main argument from memory. Some people have Claude write a report with a quiz at the bottom, and merge only after passing it perfectly.

Agents can also guard your attention. On my open source project, they help sort incoming PRs and flag where I'm needed; I rarely let them decide that alone.

Be honest about volume. If finished work piles up faster than you can review it, another session won't help. Tighten the checks or slow down. When you produce more than you can stand behind, you're no longer reviewing. You're hoping.

## Quality in, quality out

Your thinking now sits at the front and the end of the task. A colleague would challenge a vague request; an agent often fills the gaps and returns something that looks done while the idea stays fuzzy. That is intent debt, and only you can pay it. If you can't express your prompt clearly, the problem may not be clear in your own mind.

Write your brief in your own words: audience, what's out of scope, definition of done. If a second round of corrections hasn't got you there, stop tweaking and rewrite the prompt. If you're unsure, have the agent interview you.

Watch the inputs, too. When each agent reads only the previous agent's summary, the third one never saw the original.

Polish is no longer a signal, since everything arrives formatted and confident. If I wouldn't attribute the output to myself, I don't put it out. When something falls short, record why in shared config, a hook or a test, so it doesn't recur.

## "But the models will be better at this than me"

You may be right about much of the detection, and I've argued for pushing more of it to agents. But someone is responsible for what ships. Deciding how far to trust an agent is itself a judgment call, and staying calibrated means reviewing the work, because what models get wrong keeps changing. Anthropic's research calls this the paradox of supervision: "supervising Claude requires the very coding skills that may atrophy from AI overuse."

What you're building, why it's worth it, whom it affects and what you'll sacrifice remain your questions. You may offload the work and much of the auditing, but not the accountability.

## Practices for the everyday

Once a week, write some code without an agent, or do one real thing you'd hate to forget how to do. Once a month, write down what you've stopped doing and decide which you're fine losing. Ask how lost you'd be if AI didn't exist. When something is beyond your understanding, learn it properly rather than pasting a one-line explanation.

Checking the machine is real work. Schedule it as a line item, or it won't happen. Skills you stop exercising will go away, probably faster than you'd guess.

One thing to try: before you ask, write down what you think will happen. When the agent finishes, write down one thing it didn't check.
