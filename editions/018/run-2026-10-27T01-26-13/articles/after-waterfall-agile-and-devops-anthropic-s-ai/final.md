---
source_ids:
- after-waterfall-agile-and-devops-anthropic-s-ai-3a455a82
content_mode: article
label: ARTICLE
---

I finished Anthropic's *The AI-Native SDLC playbook* thinking it looks like a product manual but is very likely the first sketch of the next paradigm in software development. AI has made build fast, but planning, review, and deployment still move at human speed. The playbook's answer is a loop. Each phase ends by committing a file to git, the next phase begins by reading it, and humans and agents read the same files. By Anthropic's own disclosure, over 80% of the code merged there is written by Claude. It's still a frontrunner's draft, not a verdict.

## The problem

Once AI coding lands, code gets written much faster, but delivery doesn't. I've driven an AI transformation in our engineering org since last year. Our dev work now runs in three modes: AI-assisted, AI-collaborative, AI-autonomous. The gains are significant. Yet handoffs still run on the old pipeline: product to UI still means a Figma mock the agent can't consume, and the same holds from dev to test and from deploy to ops. Every step is faster, but the whole flow isn't.

The playbook names three effects. The bottleneck moves to either side of build. Agents write most of the diff, and line-by-line human review can't keep up. Approvals still route through weekly and monthly committees, so governance costs go up.

## The loop

The six phases survive: plan, design, build, test, deploy, maintain. What changes is the handoff. Meetings and sign-offs give way to a chain of files:

intent.md → spec.md → plan.md → code and tests → PR with review findings → incident record → a fresh intent.md.

Documents stop being memos for humans and become the interface between humans and agents. The commit chain is also the audit trail. The playbook offers sixteen plays across six non-linear stages. Four principles sit underneath them:

- Artifacts are the evidence.
- Use defense in depth.
- Humans hold intent, risk, and authorization.
- Coexist with Jira and Figma rather than tear them down.

## Plan and design

Whoever has the idea talks to the AI until the idea is clear, and the AI writes intent.md: problem, outcome, who's affected, constraints, open questions. The playbook's example comes from someone in claims operations, neither a PM nor an engineer. The product owner then reviews intent instead of writing requirements. How intent.md is best used still takes tuning to your team.

A design agent turns intent.md into a mock plus spec.md. Security, compliance, and brand rules are written as skills, so they bind as the spec is written. Conflicts go to the policy owner before engineering sees them. In our own practice, going from requirements straight to designed pages still needs heavy involvement from designers.

## Build and test

Engineers start in plan mode. The plan must be good enough that an engineer who missed the discussion could implement from it alone. Once it passes, implementation usually lands in one pass. CLAUDE.md holds commands, conventions, and repeated mistakes, stays under a page, and records a mistake only on its second occurrence. Skills are soft constraints, and hooks are hard ones. Skills make compliance probable, hooks make it certain.

Before handing over, the AI runs the build and tests and fixes until green. For bugs, it first commits a failing test, which a hook then locks, and only then fixes the code. Changes to CLAUDE.md, skills, or hooks rerun an eval suite of 20 to 50 real past tasks. Every production incident joins that suite.

## Deploy and maintain

AI reviews PRs and works through comments on its own. Humans answer two questions: is this what the plan called for, and is the risk acceptable? Autonomy is tiered. The AI ships freely to dev, has middle limits in staging, and needs a named human's sign-off for production. Rollback should be the best-rehearsed path in the pipeline.

Monitoring uses deterministic scripts, not AI. Its authority grows with the deviation from baseline:

- One standard deviation: log it.
- Two: read-only diagnosis.
- Three: act, but only by opening a PR or triggering a pre-approved runbook.

The diagnosis becomes a new intent.md, so production issues feed the next round of development. In the playbook's Slack example, Claude delivers a diagnosis three minutes after being mentioned, a human replies "Go," and four minutes later the rollback is done and the postmortem filed.

## Why I take it seriously

It works on the process layer, where paradigm shifts open. It addresses compliance, audit, and security, the last mile of enterprise adoption. And its authors run it themselves. Still, agile took nearly a decade from manifesto to global default. This will need its own run-up, though I doubt it needs that long.
