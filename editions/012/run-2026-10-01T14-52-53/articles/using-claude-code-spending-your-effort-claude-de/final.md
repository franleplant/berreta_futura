---
source_ids:
- using-claude-code-spending-your-effort-claude-de-806ec4a7
content_mode: article
label: ARTICLE
---

Effort tells Claude roughly how much compute you want spent on a task. In my tests, it mostly changed how much verification and edge-case testing Claude did and how much of its own judgment it used. Extra effort gave better results where verification and edge-case testing were more useful, like hardware, code review, and security. For normal software engineering, I have Claude interview me, implement on low effort, review what it built, then run verification on high effort.

## What effort is

If someone asked you to do something in 12 hours straight, you might assume they want you to try very hard. Given 1 hour for the same task, you'd deliver the best version that meets it and expect to iterate. Or you might push back that it needs at least 3 hours, and then work for 3 hours. Claude will always try to do your task reasonably. Higher effort means Claude takes more independent action for judgment and verification.

Fable 5.1 and Opus 5.5 show an uptick in benchmark scores and tokens consumed at each effort level.

## Everyday work

I ran the same tasks at several effort levels on Opus 5.5.

Asked to "build a personal fitness and workout tracker app," low effort gave a log and a simple graph. Higher levels added detail and had Claude making more choices along the way; max effort added a heat chart.

Asked to redesign the `/config` menu in Claude Code, every pass had roughly the same idea: submenus and better search. Low effort took 1 minute and gave a sketch that didn't look much like Claude Code. Max took 28 minutes and gave a mockup that looked very much like Claude Code, with walkthroughs for different flows. For this task, I think I prefer low effort to understand Claude's vision.

Given a detailed spec from an interview, the models behaved much more similarly. At max effort, Claude took time to simplify a few details.

For feature work, effort depends on how in the loop I want to be. Low effort gives a quick starting point; higher effort gets more done but makes more assumptions on my behalf. My loop:

- Give Claude a spec and ask it to interview me about missing details
- Implement on low effort
- Review that it got the gist; iterate on low as needed
- Verify and test on high effort

## Hard tasks

For problems where effort decides whether Claude completes the task at all, I went to Terminal-Bench 3.0, a community-sourced benchmark spanning security, hardware, ML, science, software, operations, and media. Its tasks are much more complicated than the average task I'd face, such as building an 8-bit game console in Verilog or formally proving Takens' embedding theorem in Lean 4.

My main takeaway: **higher effort is best for tasks with lots of hidden edge cases.**

On `html-js-filter`, an HTML sanitizer that must strip every way of smuggling JavaScript into a page, Fable 5.1 went from 1/5 at low to 5/5 at xhigh. A typical low attempt took about 2 minutes: one pass, tested against a single hand-written page. The high-effort run I traced took about 33 minutes. It adversarially reviewed its first draft, read the installed parser's source for bugs, ran clean test cases until output matched input, ran a standard XSS suite, and wrote a random-document fuzzer. You don't need this level of effort for every task.

On these tasks, Opus 5.5 failed at low effort and succeeded at high, mostly because it tested and accounted for edge cases:

- `mvcc-lsm-compaction` (fix a storage-engine bug from its crash report without breaking compaction): 0/5 at low, 4/5 at xhigh. At low, Claude edited the code before building it or running the reproducer, and didn't check that its new test would have caught the bug. At xhigh, it reproduced the crash first, wrote a randomized test against a reference that never compacts, and checked that its tests failed on half-finished fixes.
- `cli-2ph-simplex` (a CLI linear-program solver in Python): 0/5 at low, 5/5 at high. Low warned it might be slow on big problems but didn't check. High tested against a brute-force solver, timed bigger problems, hit cases that ran far too long or crashed, and reworked its search.
- `gsea-proteomics`: 0/5 at low, 4/5 at high. High tried two ways of prepping the data, noticed the significant treatments changed, and dug into why before choosing. With a user in the loop, Claude may have asked about the setup; without one, high effort does better.

Across all results, more effort tends to reduce failures from missed edge cases but doesn't fix a wrong approach. Some problem areas benefit from effort more than others.

These numbers come from our internal runs, 5 attempts per task, with production safety interventions off for Fable 5.1; in Claude products, Fable 5.1's safeguards hand some security requests to Opus. Security tasks ran without internet access, so per-task counts won't match the public leaderboard or the launch post. The worked examples come from individual runs, some at intermediate effort settings.

## Rule of thumb

- **Low**: quick, in-the-loop responses, such as brainstorming, sketching, and easy changes.
- **Medium**: most regular software engineering, such as new feature implementation.
- **High**: work where verification matters or there are edge cases, such as fixing a bug in a brownfield codebase.
- **Max**: fully autonomous work on difficult problems, such as building and verifying an app end to end or finding security vulnerabilities in critical software.

Try varying effort for Opus 5.5 and Fable 5.1, even mid-conversation, with `/effort` in Claude Code, and let me know if this matches your intuition.
